"""Post-process B3 predictions with an evidence-span consistency check.

For each (record, field) emission in the B3 prediction file:
  - Canonicalise both the value and the evidence quote (lowercase + collapse
    whitespace; for numeric fields, also extract a digit string of the value).
  - If the canonical value substring is not contained in the canonical
    evidence quote, replace the (value, unit, evidence_quote) triple with
    NOT_REPORTED.
  - Otherwise leave the prediction unchanged.

The variant is reported as an analysis-only ablation (B3+QuoteCheck) on the
gold-hard tier and is not promoted to a main baseline.

Outputs:
    baselines/llm/qwen25-7b-instruct-quotecheck_predictions.csv
    results/metrics/qwen25-7b-instruct-quotecheck.csv

Run:
    python3 scripts/verification/build_b3_quotecheck.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nanobubbleval.evaluator import Evaluator  # noqa: E402
from nanobubbleval.frames import AnnotationFrame  # noqa: E402
from nanobubbleval.schema import (  # noqa: E402
    HEADLINE_FIELDS,
    NR,
    NUMERIC_FIELDS,
    UnitNormalizer,
)

GOLD = ROOT / "dataset_release" / "gold_hard" / "iaa_subset.csv"
B3_IN = ROOT / "dataset_release" / "predictions" / "qwen25-7b-instruct.csv"
OUT_PRED = ROOT / "baselines" / "llm" / "qwen25-7b-instruct-quotecheck_predictions.csv"
OUT_METRICS = ROOT / "results" / "metrics" / "qwen25-7b-instruct-quotecheck.csv"


def value_in_evidence(value: str, unit: str, evidence: str, field: str,
                      norm: UnitNormalizer) -> bool:
    """Return True iff a canonicalised form of ``value`` appears in ``evidence``."""
    if norm.is_nr(value) or norm.is_nr(evidence):
        return False
    e = norm.canonicalise_text(evidence)
    if not e:
        return False

    if field in NUMERIC_FIELDS:
        num = norm.parse_number(value)
        if num is not None:
            num_str = str(int(num)) if abs(num - int(num)) < 1e-9 else f"{num:g}"
            if num_str in e:
                return True
        # Fallback: also try the raw value substring (covers ranges like "150-250")
    v = norm.canonicalise_text(value)
    return bool(v) and v in e


def main() -> int:
    norm = UnitNormalizer()
    pred = pd.read_csv(B3_IN, low_memory=False)
    pred = pred.copy()

    n_quote_failed = 0
    for f in HEADLINE_FIELDS:
        v_col = f"{f}_value"
        u_col = f"{f}_unit"
        e_col = f"{f}_evidence_quote"
        for i, row in pred.iterrows():
            v = row.get(v_col, "")
            u = row.get(u_col, "")
            e = row.get(e_col, "")
            v = "" if pd.isna(v) else str(v)
            u = "" if pd.isna(u) else str(u)
            e = "" if pd.isna(e) else str(e)
            if norm.is_nr(v):
                continue
            if not value_in_evidence(v, u, e, f, norm):
                pred.at[i, v_col] = NR
                pred.at[i, u_col] = NR
                pred.at[i, e_col] = NR
                n_quote_failed += 1

    OUT_PRED.parent.mkdir(parents=True, exist_ok=True)
    pred.to_csv(OUT_PRED, index=False)
    print(f"Wrote {OUT_PRED.relative_to(ROOT)} (n_emissions_dropped={n_quote_failed})")

    gold_af = AnnotationFrame.from_csv(GOLD)
    pred_af = AnnotationFrame.from_csv(OUT_PRED)
    table = Evaluator().evaluate(gold_af, pred_af, fields=HEADLINE_FIELDS)
    OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_METRICS, index=False)
    print(f"Wrote {OUT_METRICS.relative_to(ROOT)}")
    print()
    print(table[["field", "naive_f1", "nr_f1", "acal_f1", "num_match", "ae_consistency"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
