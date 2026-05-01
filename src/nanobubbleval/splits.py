"""Split builder and stratified sampler for the gold pool.

``StratifiedSampler``  proportional sampling within (column-tuple) groups.
``SplitBuilder``       builds dev/test splits + slice membership over a
                       gold-pool DataFrame, with IAA records pinned to test.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Stratified sampler
# ---------------------------------------------------------------------------

class StratifiedSampler:
    """Proportional stratified sampler within tuple-keyed groups.

    Example:
        >>> s = StratifiedSampler(seed=42)
        >>> picks = s.sample(df, group_cols=["nb_label", "doc_type"], n=40)
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    def sample(
        self,
        df: pd.DataFrame,
        group_cols: Sequence[str],
        n: int,
        *,
        quotas: Optional[Mapping[tuple, int]] = None,
    ) -> pd.DataFrame:
        """Draw ``n`` rows stratified by ``group_cols``.

        If ``quotas`` is provided, those exact counts are used per group
        (subject to availability) and ``n`` is the sum.

        Otherwise quotas are derived proportionally to group size, rounded,
        and adjusted to sum to ``n``.
        """
        if quotas is not None:
            picked = []
            used = set()
            for key, q in quotas.items():
                pool = self._select_group(df, group_cols, key)
                pool = pool.loc[~pool.index.isin(used)]
                if pool.empty or q <= 0:
                    continue
                take = min(int(q), len(pool))
                sample = pool.sample(n=take, random_state=int(self._rng.integers(0, 2**32 - 1)))
                picked.append(sample)
                used.update(sample.index.tolist())
            out = pd.concat(picked, ignore_index=False) if picked else df.iloc[0:0]
            if len(out) < n:
                remaining = df.loc[~df.index.isin(out.index)]
                topup = remaining.sample(
                    n=min(n - len(out), len(remaining)),
                    random_state=int(self._rng.integers(0, 2**32 - 1)),
                )
                out = pd.concat([out, topup])
            return out.sample(frac=1, random_state=int(self._rng.integers(0, 2**32 - 1))).reset_index(drop=True)

        sizes = df.groupby(list(group_cols)).size()
        if sizes.sum() == 0:
            return df.iloc[0:0]
        props = sizes / sizes.sum()
        q = (props * n).round().astype(int)
        diff = n - int(q.sum())
        if diff != 0:
            order = sizes.sort_values(ascending=(diff < 0)).index.tolist()
            for k in order:
                if diff == 0:
                    break
                step = 1 if diff > 0 else -1
                new_val = int(q[k]) + step
                if new_val < 0 or new_val > int(sizes[k]):
                    continue
                q[k] = new_val
                diff -= step
        return self.sample(df, group_cols, n, quotas={tuple(k) if isinstance(k, tuple) else (k,): int(v) for k, v in q.items()})

    @staticmethod
    def _select_group(df: pd.DataFrame, group_cols: Sequence[str], key) -> pd.DataFrame:
        if not isinstance(key, tuple):
            key = (key,)
        mask = pd.Series(True, index=df.index)
        for col, val in zip(group_cols, key):
            mask &= df[col] == val
        return df[mask]


# ---------------------------------------------------------------------------
# Split builder
# ---------------------------------------------------------------------------

@dataclass
class SplitConfig:
    dev_fraction: float = 0.10
    seed: int = 42
    iaa_pinned_to: str = "test"
    stratify_by: tuple[str, ...] = ("nb_label", "document_type")


@dataclass
class SplitArtifacts:
    df: pd.DataFrame                       # original df with split + slice columns
    splits_payload: dict                   # serialisable splits.json content
    slice_summary_md: str
    leakage_report_md: str

    def write(self, out_dir: str | Path) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "splits.json").open("w") as f:
            json.dump(self.splits_payload, f, indent=2)
        (out / "slice_summary.md").write_text(self.slice_summary_md)
        (out / "leakage_report.md").write_text(self.leakage_report_md)


class SplitBuilder:
    """Build dev/test splits + five orthogonal slice tags over a gold pool.

    The five slice columns are:
        ``year_bucket``, ``source_api``, ``document_type``, ``nb_label``,
        ``application_bucket``.

    Example:
        >>> b = SplitBuilder()
        >>> art = b.build(gold_df, iaa_record_ids={"ORG003", ...})
        >>> art.write("neurips_workspace/splits/")
    """

    def __init__(self, config: SplitConfig | None = None) -> None:
        self._cfg = config or SplitConfig()

    # -------------------------------------------------------------- features

    @staticmethod
    def year_bucket(year: object) -> str:
        if pd.isna(year):
            return "unknown"
        try:
            y = int(year)
        except (TypeError, ValueError):
            return "unknown"
        if y <= 2014:
            return "pre_2015"
        if y <= 2020:
            return "y2015_2020"
        return "post_2020"

    @staticmethod
    def application_bucket(category: object) -> str:
        if not isinstance(category, str) or not category:
            return "unknown"
        c = category.lower()
        if any(k in c for k in [
            "biomed", "translational", "clinical", "drug",
            "delivery", "therap", "imaging", "diagnost",
        ]):
            return "biomedical"
        if any(k in c for k in [
            "environ", "water", "wastewater", "agri", "aquacult", "flotation",
        ]):
            return "environmental"
        if any(k in c for k in ["fundament", "physic", "stab", "characteriz"]):
            return "fundamental"
        if any(k in c for k in ["industrial", "process", "engin"]):
            return "industrial"
        return "other"

    # ----------------------------------------------------------------- build

    def build(
        self,
        df: pd.DataFrame,
        iaa_record_ids: Iterable[str] | None = None,
    ) -> SplitArtifacts:
        df = df.loc[:, ~df.columns.duplicated()].copy()
        df["record_id"] = df["record_id"].astype(str)
        iaa_ids = set(map(str, iaa_record_ids or []))

        df["year_bucket"] = df["year"].apply(self.year_bucket)
        df["source_api"] = df["source_api"].fillna("unknown")
        df["document_type"] = df["document_type"].fillna("unknown")
        df["nb_label"] = df["nanobubble_vs_nanoparticle"].fillna("unknown")
        df["application_bucket"] = df["application_category"].apply(self.application_bucket)
        df["in_iaa"] = df["record_id"].isin(iaa_ids)

        sampler = StratifiedSampler(seed=self._cfg.seed)
        eligible = df[~df["in_iaa"]]
        target = int(round(len(df) * self._cfg.dev_fraction))
        dev_pick = sampler.sample(eligible, list(self._cfg.stratify_by), target)
        df["split"] = np.where(df["record_id"].isin(set(dev_pick["record_id"])), "dev", "test")

        payload = self._build_payload(df, target)
        return SplitArtifacts(
            df=df,
            splits_payload=payload,
            slice_summary_md=self._build_slice_summary(df),
            leakage_report_md=self._build_leakage_report(df, iaa_ids),
        )

    # ------------------------------------------------------------- helpers

    def _build_payload(self, df: pd.DataFrame, target_dev: int) -> dict:
        out = {
            "meta": {
                "n_total": int(len(df)),
                "n_dev": int((df["split"] == "dev").sum()),
                "n_test": int((df["split"] == "test").sum()),
                "n_iaa": int(df["in_iaa"].sum()),
                "seed": self._cfg.seed,
                "dev_fraction_target": self._cfg.dev_fraction,
                "iaa_pinned_to": self._cfg.iaa_pinned_to,
                "stratified_by": list(self._cfg.stratify_by),
                "slices": {
                    "year_bucket": ["pre_2015", "y2015_2020", "post_2020", "unknown"],
                    "source_api": sorted(df["source_api"].unique().tolist()),
                    "document_type": sorted(df["document_type"].unique().tolist()),
                    "nb_label": sorted(df["nb_label"].unique().tolist()),
                    "application_bucket": sorted(df["application_bucket"].unique().tolist()),
                },
            },
            "records": {},
        }
        for _, r in df.iterrows():
            out["records"][r["record_id"]] = {
                "split": r["split"],
                "in_iaa": bool(r["in_iaa"]),
                "year_bucket": r["year_bucket"],
                "source_api": r["source_api"],
                "document_type": r["document_type"],
                "nb_label": r["nb_label"],
                "application_bucket": r["application_bucket"],
            }
        return out

    @staticmethod
    def _build_slice_summary(df: pd.DataFrame) -> str:
        lines = ["# Slice Summary", ""]
        lines.append(
            f"Total records: **{len(df)}** "
            f"(dev={int((df['split']=='dev').sum())}, "
            f"test={int((df['split']=='test').sum())}, "
            f"IAA={int(df['in_iaa'].sum())})"
        )
        lines.append("")
        for col in ["year_bucket", "source_api", "document_type", "nb_label", "application_bucket"]:
            lines.append(f"## {col}")
            lines.append("")
            lines.append("| Slice | Total | Dev | Test | IAA |")
            lines.append("|---|---:|---:|---:|---:|")
            for v in sorted(df[col].unique()):
                sub = df[df[col] == v]
                lines.append(
                    f"| {v} | {len(sub)} | {(sub['split']=='dev').sum()} | "
                    f"{(sub['split']=='test').sum()} | {int(sub['in_iaa'].sum())} |"
                )
            lines.append("")
        return "\n".join(lines)

    def _build_leakage_report(self, df: pd.DataFrame, iaa_ids: set[str]) -> str:
        checks = []
        n_dup = int(df["record_id"].duplicated().sum())
        checks.append(("No duplicate record_id in gold pool", n_dup == 0, f"{n_dup} duplicates"))

        overlap = set(df[df["split"] == "dev"]["record_id"]) & set(df[df["split"] == "test"]["record_id"])
        checks.append(("Dev and test are disjoint", len(overlap) == 0, f"{len(overlap)} overlapping ids"))

        iaa_in_test = df[df["in_iaa"] & (df["split"] == "test")].shape[0]
        iaa_total = int(df["in_iaa"].sum())
        checks.append((
            f"All IAA records are in {self._cfg.iaa_pinned_to}",
            iaa_in_test == iaa_total,
            f"{iaa_in_test}/{iaa_total} in test",
        ))

        for col, label in [("year", "Year"), ("abstract_or_summary", "Abstract")]:
            n_missing = int(df[col].isna().sum()) if col in df.columns else 0
            checks.append((
                f"{label} present for all records (informational)",
                n_missing == 0,
                f"{n_missing} missing",
            ))

        present = sum(1 for k in iaa_ids if k in set(df["record_id"]))
        checks.append((
            "All IAA record_ids exist in gold pool",
            present == len(iaa_ids),
            f"{present}/{len(iaa_ids)} found",
        ))

        lines = ["# Leakage & Integrity Report", ""]
        lines.append("| Check | Status | Details |")
        lines.append("|---|---|---|")
        for name, ok, detail in checks:
            lines.append(f"| {name} | **{'PASS' if ok else 'FAIL'}** | {detail} |")
        lines.append("")
        lines.append(f"Built with seed={self._cfg.seed}, dev_fraction={self._cfg.dev_fraction}.")
        return "\n".join(lines)
