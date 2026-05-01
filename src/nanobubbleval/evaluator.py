"""Evaluator: per-field metrics for NanoBubbleEval.

The Evaluator computes:

    naive_f1         F1 over the EMIT class (correct emit vs wrong/missed)
    nr_f1            F1 over the NR class (correctly emitted NOT_REPORTED)
    acal_f1          Macro mean of (naive_f1, nr_f1) — abstention-calibrated F1
    num_match        Tolerance-bounded numeric match after unit canonicalisation
    unit_accuracy    Canonical-unit equality among emit-emit pairs
    span_iou         Character-set IoU of evidence quotes among emit-emit pairs
    ae_consistency   Fraction of non-NR predictions whose value substring
                     appears in the predicted evidence quote (prediction-side)

The Evaluator separates the *match policy* from the *aggregation*: subclassing
``MatchPolicy`` lets you swap in a different value-matching rule (e.g. a
stricter exact-match policy for v1.1) without rewriting the metric code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

import pandas as pd

from nanobubbleval.frames import AnnotationFrame, FieldCell
from nanobubbleval.schema import (
    FIELD_REGISTRY, HEADLINE_FIELDS, NR, NUMERIC_FIELDS, UnitNormalizer,
)

DEFAULT_REL_TOLERANCE: float = 0.05


# ---------------------------------------------------------------------------
# Match policy
# ---------------------------------------------------------------------------

class MatchPolicy:
    """Decides whether two annotation cells refer to the same value.

    Default behaviour:
      * numeric fields: relative tolerance (``rel_tol``) on canonical value
      * text fields:    case-insensitive substring either-direction match
    """

    def __init__(
        self, normalizer: UnitNormalizer, rel_tol: float = DEFAULT_REL_TOLERANCE,
    ) -> None:
        self._norm = normalizer
        self._rel_tol = rel_tol

    @property
    def normalizer(self) -> UnitNormalizer:
        return self._norm

    def is_emit(self, cell: FieldCell) -> bool:
        return not self._norm.is_nr(cell.value)

    def values_match(self, gold: FieldCell, pred: FieldCell) -> bool:
        if not (self.is_emit(gold) and self.is_emit(pred)):
            return False
        if gold.field != pred.field:
            raise ValueError(f"cell field mismatch: {gold.field} vs {pred.field}")
        if gold.field in NUMERIC_FIELDS:
            return self._numeric_match(gold, pred)
        return self._text_match(gold.value, pred.value)

    def _numeric_match(self, g: FieldCell, p: FieldCell) -> bool:
        gx, _ = self._norm.to_canonical(g.value, g.unit, g.field)
        px, _ = self._norm.to_canonical(p.value, p.unit, p.field)
        if gx is None or px is None:
            # fall back to text equality on raw value strings
            return self._norm.canonicalise_text(g.value) == self._norm.canonicalise_text(p.value)
        if abs(gx) < 1e-12:
            return abs(px) < 1e-12
        return abs(gx - px) <= self._rel_tol * abs(gx)

    def _text_match(self, a: str, b: str) -> bool:
        ca = self._norm.canonicalise_text(a)
        cb = self._norm.canonicalise_text(b)
        if not ca or not cb or ca == NR.lower() or cb == NR.lower():
            return False
        return ca in cb or cb in ca


# ---------------------------------------------------------------------------
# Per-field metrics
# ---------------------------------------------------------------------------

@dataclass
class FieldMetrics:
    """Computed metrics for a single field."""

    field: str
    n: int
    naive_f1: float
    nr_f1: float
    acal_f1: float
    n_emit_gold: int
    n_emit_pred: int
    n_nr_gold: int
    span_iou: Optional[float] = None
    n_iou_evaluable: int = 0
    num_match: Optional[float] = None
    unit_accuracy: Optional[float] = None
    n_num_evaluable: int = 0
    n_unit_evaluable: int = 0
    ae_consistency: Optional[float] = None

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}  # noqa: PLC0206


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """Runs per-field and macro metrics for a (gold, pred) pair.

    Example:
        >>> ev = Evaluator()
        >>> table = ev.evaluate(gold_af, pred_af)
        >>> table[table["field"] == "MACRO"][["naive_f1", "acal_f1"]]
    """

    def __init__(
        self,
        normalizer: Optional[UnitNormalizer] = None,
        match_policy: Optional[MatchPolicy] = None,
        rel_tol: float = DEFAULT_REL_TOLERANCE,
    ) -> None:
        self._norm = normalizer or UnitNormalizer()
        self._policy = match_policy or MatchPolicy(self._norm, rel_tol=rel_tol)
        self._rel_tol = rel_tol

    @property
    def policy(self) -> MatchPolicy:
        return self._policy

    # --------------------------------------------------------------- metrics

    def field_metrics(
        self, gold: AnnotationFrame, pred: AnnotationFrame, field_name: str,
    ) -> FieldMetrics:
        if field_name not in gold.fields:
            raise KeyError(f"field '{field_name}' not in gold")
        if field_name not in pred.fields:
            raise KeyError(f"field '{field_name}' not in pred")

        merged = self._align(gold, pred)
        n = len(merged)

        emit_tp = emit_fp = emit_fn = 0
        nr_tp = nr_fp = nr_fn = 0
        n_num_eval = num_match = 0
        n_unit_eval = unit_match = 0
        ious: list[float] = []

        for rid in merged:
            g = gold.cell(rid, field_name)
            p = pred.cell(rid, field_name)
            ge = self._policy.is_emit(g)
            pe = self._policy.is_emit(p)
            match = self._policy.values_match(g, p) if (ge and pe) else False

            # emit-class confusion
            if ge and pe and match:
                emit_tp += 1
            elif pe and (not ge or not match):
                emit_fp += 1
            elif ge and (not pe or not match):
                emit_fn += 1

            # NR-class confusion
            if not ge and not pe:
                nr_tp += 1
            elif not pe and ge:
                nr_fp += 1
            elif not ge and pe:
                nr_fn += 1

            if field_name in NUMERIC_FIELDS and ge and pe:
                gx, gcu = self._norm.to_canonical(g.value, g.unit, field_name)
                px, pcu = self._norm.to_canonical(p.value, p.unit, field_name)
                if gx is not None and px is not None:
                    n_num_eval += 1
                    if abs(gx) < 1e-12:
                        if abs(px) < 1e-12:
                            num_match += 1
                    elif abs(gx - px) <= self._rel_tol * abs(gx):
                        num_match += 1
                if gcu is not None and pcu is not None and not self._norm.is_nr(g.unit) and not self._norm.is_nr(p.unit):
                    n_unit_eval += 1
                    if gcu == pcu:
                        unit_match += 1

            if ge and pe:
                gq = self._norm.canonicalise_text(g.evidence_quote)
                pq = self._norm.canonicalise_text(p.evidence_quote)
                if gq and pq and gq != NR.lower() and pq != NR.lower():
                    ious.append(self._char_iou(gq, pq))

        naive = self._binary_f1(emit_tp, emit_fp, emit_fn)
        nr = self._binary_f1(nr_tp, nr_fp, nr_fn)
        acal = (naive + nr) / 2.0

        out = FieldMetrics(
            field=field_name, n=n,
            naive_f1=naive, nr_f1=nr, acal_f1=acal,
            n_emit_gold=emit_tp + emit_fn,
            n_emit_pred=emit_tp + emit_fp,
            n_nr_gold=nr_tp + nr_fn,
            span_iou=(sum(ious) / len(ious)) if ious else None,
            n_iou_evaluable=len(ious),
            num_match=(num_match / n_num_eval) if n_num_eval else None,
            unit_accuracy=(unit_match / n_unit_eval) if n_unit_eval else None,
            n_num_evaluable=n_num_eval,
            n_unit_evaluable=n_unit_eval,
            ae_consistency=self.answer_evidence_consistency(pred, field_name),
        )
        return out

    def evaluate(
        self,
        gold: AnnotationFrame,
        pred: AnnotationFrame,
        fields: Iterable[str] = HEADLINE_FIELDS,
    ) -> pd.DataFrame:
        rows = [self.field_metrics(gold, pred, f).as_dict() for f in fields]
        df = pd.DataFrame(rows)
        df = pd.concat([df, pd.DataFrame([self._macro_row(df)])], ignore_index=True)
        return df

    # ----------------------------------------------------------- AE side metric

    def answer_evidence_consistency(
        self, pred: AnnotationFrame, field_name: str,
    ) -> Optional[float]:
        n = consistent = 0
        for cell in pred.iter_cells(field_name):
            if self._norm.is_nr(cell.value):
                continue
            n += 1
            if self._norm.is_nr(cell.evidence_quote):
                continue
            v_text = self._norm.canonicalise_text(cell.value)
            e_text = self._norm.canonicalise_text(cell.evidence_quote)
            if field_name in NUMERIC_FIELDS:
                num = self._norm.parse_number(cell.value)
                if num is None:
                    if v_text in e_text:
                        consistent += 1
                else:
                    num_str = (str(int(num)) if abs(num - int(num)) < 1e-9 else f"{num:g}")
                    if num_str in e_text:
                        consistent += 1
            else:
                if v_text in e_text:
                    consistent += 1
        return (consistent / n) if n else None

    # -------------------------------------------------------------- internals

    @staticmethod
    def _binary_f1(tp: int, fp: int, fn: int) -> float:
        if tp == 0 and (fp == 0 or fn == 0):
            return 0.0
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    @staticmethod
    def _char_iou(a: str, b: str) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    @staticmethod
    def _align(gold: AnnotationFrame, pred: AnnotationFrame) -> list[str]:
        common = sorted(set(gold.record_ids()) & set(pred.record_ids()))
        return common

    @staticmethod
    def _macro_row(df: pd.DataFrame) -> dict:
        macro = {"field": "MACRO", "n": int(df["n"].iloc[0]) if not df.empty else 0}
        for c in ["naive_f1", "nr_f1", "acal_f1", "num_match",
                  "unit_accuracy", "span_iou", "ae_consistency"]:
            if c in df.columns and df[c].notna().any():
                macro[c] = float(df[c].dropna().mean())
        return macro
