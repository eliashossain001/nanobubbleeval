"""Reconciliation: dual-annotator IAA computation and gold-hard adjudication.

The :class:`Reconciler` compares two :class:`AnnotationFrame` objects
representing the same record set as labelled by two annotators. It produces:

    * per-field IAA stats (Cohen's kappa on NR-vs-emit; value match rate;
      unit-normalised numeric match; mean span IoU)
    * a `disagreements` frame, one row per disagreed cell, ready for manual
      adjudication (downstream becomes `gold_hard.csv` once the user fills
      `adjudicated_*` columns)
    * an `agreements` frame: all cells where annotators agreed; these become
      the agreed slice of `gold_hard.csv` automatically
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from nanobubbleval.evaluator import MatchPolicy
from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.schema import HEADLINE_FIELDS, NR, NUMERIC_FIELDS, UnitNormalizer


@dataclass
class ReconciliationReport:
    """Bundle of artefacts produced by :class:`Reconciler.run`."""

    stats: pd.DataFrame
    agreements: pd.DataFrame
    disagreements: pd.DataFrame
    label_a: str
    label_b: str

    def to_paper_table(self) -> str:
        lines = ["# IAA Summary (paper §9.3)", ""]
        lines.append(
            "| Field | n | κ (NR vs emit) | Match rate (both emit) | "
            "Num match | Span IoU | n IoU |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for _, r in self.stats.iterrows():
            lines.append(
                "| {field} | {n} | {kappa} | {vmr} | {num} | {iou} | {n_iou} |".format(
                    field=r["field"], n=int(r["n"]),
                    kappa=_fmt(r["kappa_NR_vs_emit"]),
                    vmr=_fmt(r["value_match_rate_among_both_emit"]),
                    num=_fmt(r["num_match_canonical"]),
                    iou=_fmt(r["mean_span_iou_among_both_emit"]),
                    n_iou=int(r["n_iou_evaluable"]) if not pd.isna(r["n_iou_evaluable"]) else 0,
                )
            )
        return "\n".join(lines) + "\n"

    def write(self, out_dir: str) -> None:
        from pathlib import Path
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        self.stats.to_csv(out / "iaa_stats.csv", index=False)
        self.agreements.to_csv(out / "gold_hard_template.csv", index=False)
        self.disagreements.to_csv(out / "disagreements.csv", index=False)
        (out / "iaa_summary.md").write_text(self.to_paper_table())


def _fmt(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


class Reconciler:
    """Compute IAA between two annotators and produce adjudication artefacts.

    Reuses the same :class:`MatchPolicy` as the Evaluator so reconciliation
    and evaluation always agree on what counts as a match.
    """

    def __init__(
        self,
        normalizer: UnitNormalizer | None = None,
        match_policy: MatchPolicy | None = None,
    ) -> None:
        self._norm = normalizer or UnitNormalizer()
        self._policy = match_policy or MatchPolicy(self._norm)

    def run(
        self,
        a: AnnotationFrame,
        b: AnnotationFrame,
        *,
        label_a: str = "A",
        label_b: str = "B",
        fields: Iterable[str] = HEADLINE_FIELDS,
    ) -> ReconciliationReport:
        common_ids = sorted(set(a.record_ids()) & set(b.record_ids()))
        if not common_ids:
            raise ValueError("annotators have no common record_ids")

        stats_rows = []
        agree_rows: list[dict] = []
        dis_rows: list[dict] = []

        for f in fields:
            nr_a, nr_b = [], []
            n_emit_both = n_match = 0
            n_num_eval = n_num_match = 0
            ious: list[float] = []

            for rid in common_ids:
                ca = a.cell(rid, f)
                cb = b.cell(rid, f)
                ae = self._policy.is_emit(ca)
                be = self._policy.is_emit(cb)
                nr_a.append(0 if ae else 1)
                nr_b.append(0 if be else 1)

                cell_match = False
                disagree_type = None

                if ae and be:
                    n_emit_both += 1
                    if self._policy.values_match(ca, cb):
                        n_match += 1
                        cell_match = True
                    else:
                        disagree_type = "value_mismatch"
                    if f in NUMERIC_FIELDS:
                        ax, _ = self._norm.to_canonical(ca.value, ca.unit, f)
                        bx, _ = self._norm.to_canonical(cb.value, cb.unit, f)
                        if ax is not None and bx is not None:
                            n_num_eval += 1
                            if abs(ax) < 1e-12:
                                if abs(bx) < 1e-12:
                                    n_num_match += 1
                            elif abs(ax - bx) <= self._policy._rel_tol * abs(ax):
                                n_num_match += 1
                    aq = self._norm.canonicalise_text(ca.evidence_quote)
                    bq = self._norm.canonicalise_text(cb.evidence_quote)
                    if aq and bq and aq != NR.lower() and bq != NR.lower():
                        ious.append(self._char_iou(aq, bq))
                elif ae and not be:
                    disagree_type = f"{label_a}_emit_{label_b}_NR"
                elif be and not ae:
                    disagree_type = f"{label_b}_emit_{label_a}_NR"
                else:
                    cell_match = True  # both NR

                row = {
                    "record_id": rid, "field": f,
                    f"{label_a}_value": ca.value,
                    f"{label_a}_unit": ca.unit,
                    f"{label_a}_evidence_quote": ca.evidence_quote,
                    f"{label_b}_value": cb.value,
                    f"{label_b}_unit": cb.unit,
                    f"{label_b}_evidence_quote": cb.evidence_quote,
                }
                if cell_match:
                    row.update({
                        "resolved_value": ca.value,
                        "resolved_unit": ca.unit,
                        "resolved_evidence_quote": ca.evidence_quote,
                    })
                    agree_rows.append(row)
                else:
                    row.update({
                        "disagreement_type": disagree_type,
                        "adjudicated_value": "",
                        "adjudicated_unit": "",
                        "adjudicated_evidence_quote": "",
                    })
                    dis_rows.append(row)

            try:
                kappa = float(cohen_kappa_score(nr_a, nr_b))
            except Exception:
                kappa = float("nan")

            n = len(common_ids)
            stats_rows.append({
                "field": f,
                "n": n,
                "kappa_NR_vs_emit": kappa,
                "raw_NR_vs_emit_agreement": (
                    sum(int(x == y) for x, y in zip(nr_a, nr_b)) / n if n else None
                ),
                "n_emit_both": n_emit_both,
                "value_match_rate_among_both_emit": (
                    n_match / n_emit_both if n_emit_both else None
                ),
                "num_match_canonical": (
                    n_num_match / n_num_eval if n_num_eval else None
                ),
                "n_num_evaluable": n_num_eval,
                "mean_span_iou_among_both_emit": (
                    sum(ious) / len(ious) if ious else None
                ),
                "n_iou_evaluable": len(ious),
            })

        return ReconciliationReport(
            stats=pd.DataFrame(stats_rows),
            agreements=pd.DataFrame(agree_rows),
            disagreements=pd.DataFrame(dis_rows),
            label_a=label_a,
            label_b=label_b,
        )

    @staticmethod
    def _char_iou(a: str, b: str) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)
