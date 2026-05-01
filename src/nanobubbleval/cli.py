"""Command-line entry points for NanoBubbleEval.

Single ``nanoeval`` CLI with subcommands:

    nanoeval build-iaa-subset --gold <path> --out <dir> [--n 40]
    nanoeval build-splits     --gold <path> --iaa-keys <path> --out <dir>
    nanoeval evaluate         --gold <path> --pred <path>
    nanoeval reconcile        --a <path> --b <path> --out <dir>
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from nanobubbleval.evaluator import Evaluator
from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.reconciliation import Reconciler
from nanobubbleval.schema import HEADLINE_FIELDS
from nanobubbleval.splits import SplitBuilder, StratifiedSampler

LOG = logging.getLogger("nanoeval")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_build_iaa_subset(args: argparse.Namespace) -> int:
    df = pd.read_csv(args.gold, low_memory=False)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df = df[df["abstract_or_summary"].notna()]
    df = df[df["abstract_or_summary"].str.len() >= args.min_abstract_chars]

    df["nb_label"] = df["nanobubble_vs_nanoparticle"].fillna("unknown")
    df["doc_label"] = df["document_type"].fillna("unknown")

    quotas = {
        ("nanobubble", "original"): 14,
        ("nanobubble", "review"): 4,
        ("nanoparticle", "original"): 12,
        ("nanoparticle", "review"): 4,
        ("microbubble-adjacent", "original"): 3,
        ("micro/nanobubble", "original"): 3,
    }
    sampler = StratifiedSampler(seed=args.seed)
    sampled = sampler.sample(df, ["nb_label", "doc_label"], args.n, quotas=quotas)

    front_cols = [
        "record_id", "title", "year", "journal_or_venue", "document_type",
        "nanobubble_vs_nanoparticle", "application_category", "abstract_or_summary",
    ]
    annot = AnnotationFrame.empty(sampled["record_id"].tolist())
    out_df = sampled[front_cols].merge(annot.df.drop(columns=["record_id"]), how="cross")
    # Above cross-join would explode; instead concat by row:
    annotation_cols = [c for c in annot.df.columns if c != "record_id"]
    out_df = sampled[front_cols].copy().reset_index(drop=True)
    for c in annotation_cols:
        out_df[c] = ""

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "iaa_subset.csv"
    keys_path = out_dir / "iaa_subset_keys.csv"
    out_df.to_csv(out_path, index=False)
    sampled[["record_id", "nb_label", "doc_label", "year"]].to_csv(keys_path, index=False)
    LOG.info("Wrote %d records to %s", len(out_df), out_path)
    print(sampled.groupby(["nb_label", "doc_label"]).size().to_string())
    return 0


def cmd_build_splits(args: argparse.Namespace) -> int:
    gold = pd.read_csv(args.gold, low_memory=False)
    iaa_ids: set[str] = set()
    if args.iaa_keys:
        iaa_keys = pd.read_csv(args.iaa_keys)
        iaa_ids = set(iaa_keys["record_id"].astype(str))
    builder = SplitBuilder()
    art = builder.build(gold, iaa_record_ids=iaa_ids)
    art.write(args.out)
    LOG.info(
        "Built splits: dev=%d, test=%d, IAA=%d",
        art.splits_payload["meta"]["n_dev"],
        art.splits_payload["meta"]["n_test"],
        art.splits_payload["meta"]["n_iaa"],
    )
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    gold = AnnotationFrame.from_csv(args.gold)
    pred = AnnotationFrame.from_csv(args.pred)
    ev = Evaluator()
    table = ev.evaluate(gold, pred, fields=HEADLINE_FIELDS)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.out, index=False)
        LOG.info("Wrote %s", args.out)
    print(table.to_string(index=False))
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    a = AnnotationFrame.from_csv(args.a)
    b = AnnotationFrame.from_csv(args.b)
    label_a = Path(args.a).stem.split("_")[-1] or "A"
    label_b = Path(args.b).stem.split("_")[-1] or "B"
    if label_a == label_b:
        label_a, label_b = "A", "B"
    rec = Reconciler()
    report = rec.run(a, b, label_a=label_a, label_b=label_b)
    report.write(args.out)
    print(report.stats.to_string(index=False))
    print()
    print(f"agreed cells: {len(report.agreements)}, disagreed cells: {len(report.disagreements)}")
    return 0


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nanoeval", description="NanoBubbleEval CLI")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build-iaa-subset", help="Sample a stratified IAA subset")
    s.add_argument("--gold", required=True, help="path to gold_annotation_set_v3.csv")
    s.add_argument("--out", required=True, help="output directory")
    s.add_argument("--n", type=int, default=40)
    s.add_argument("--min-abstract-chars", type=int, default=200)
    s.add_argument("--seed", type=int, default=42)
    s.set_defaults(func=cmd_build_iaa_subset)

    s = sub.add_parser("build-splits", help="Build dev/test splits + slice tags")
    s.add_argument("--gold", required=True)
    s.add_argument("--iaa-keys", default=None)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_build_splits)

    s = sub.add_parser("evaluate", help="Run the evaluator on a (gold, pred) pair")
    s.add_argument("--gold", required=True)
    s.add_argument("--pred", required=True)
    s.add_argument("--out", default=None, help="optional CSV output path")
    s.set_defaults(func=cmd_evaluate)

    s = sub.add_parser("reconcile", help="Compute IAA between two annotators")
    s.add_argument("--a", required=True, help="annotator A CSV")
    s.add_argument("--b", required=True, help="annotator B CSV")
    s.add_argument("--out", required=True, help="output directory")
    s.set_defaults(func=cmd_reconcile)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
