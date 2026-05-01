"""Baseline abstract base class.

All extraction baselines (regex, encoder, LLM) implement the same interface:

    Baseline.predict_record(record_id, abstract) -> {field: FieldPrediction}

The :meth:`Baseline.predict_frame` default implementation iterates over rows
of an annotation-shape DataFrame and writes prediction columns in-place.
Subclasses only need to implement ``predict_record`` to get the full
DataFrame-level pipeline for free.

Example:
    >>> class MyBaseline(Baseline):
    ...     name = "my-baseline"
    ...     def predict_record(self, rid, abstract):
    ...         return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
    >>> bl = MyBaseline()
    >>> pred_frame = bl.predict_frame(input_frame)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.schema import HEADLINE_FIELDS, NR

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldPrediction:
    """Immutable per-field prediction.

    ``value`` is the predicted value (or ``NOT_REPORTED``).
    ``unit`` is the predicted unit (numeric fields) or empty (text fields).
    ``evidence_quote`` is the predicted supporting span (or ``NOT_REPORTED``).
    """

    value: str = NR
    unit: str = ""
    evidence_quote: str = NR

    @classmethod
    def nr(cls) -> "FieldPrediction":
        """Helper: an explicit `NOT_REPORTED` triple."""
        return cls(value=NR, unit=NR, evidence_quote=NR)

    @classmethod
    def numeric(cls, value: str, unit: str, evidence: str) -> "FieldPrediction":
        return cls(value=value, unit=unit, evidence_quote=evidence)

    @classmethod
    def text(cls, value: str, evidence: str) -> "FieldPrediction":
        return cls(value=value, unit="", evidence_quote=evidence)

    def is_emit(self) -> bool:
        return self.value != NR and self.value != ""


# ---------------------------------------------------------------------------
# Abstract baseline
# ---------------------------------------------------------------------------

class Baseline(ABC):
    """Abstract extraction baseline.

    Subclasses must:
      * set the class attribute ``name`` (used for filenames and logging)
      * implement :meth:`predict_record`

    Subclasses may:
      * override :meth:`predict_frame` for batched inference (e.g., LLM batch)
    """

    name: str = "abstract"

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name == "abstract":
            raise TypeError(f"{cls.__name__} must override the class attribute `name`")

    # ----------------------------------------------------------------- core

    @abstractmethod
    def predict_record(
        self, record_id: str, abstract: str,
    ) -> Mapping[str, FieldPrediction]:
        """Return one :class:`FieldPrediction` per headline field.

        Implementations should always return a key for every field in
        :data:`HEADLINE_FIELDS`. Use :meth:`FieldPrediction.nr` for absent.
        """
        raise NotImplementedError

    # ------------------------------------------------------- batched default

    def predict_frame(
        self,
        input_frame: AnnotationFrame,
        *,
        fields: Iterable[str] = HEADLINE_FIELDS,
        abstract_col: str = "abstract_or_summary",
    ) -> AnnotationFrame:
        """Apply :meth:`predict_record` row-by-row, returning a new
        AnnotationFrame in the same schema with annotation columns filled."""
        df = input_frame.df.copy()
        if abstract_col not in df.columns:
            raise KeyError(
                f"input frame has no abstract column '{abstract_col}'; "
                f"available: {list(df.columns)[:6]}..."
            )
        n = len(df)
        LOG.info("[%s] predicting on %d records", self.name, n)
        for i, row in df.iterrows():
            preds = self.predict_record(str(row["record_id"]), str(row[abstract_col]))
            for f in fields:
                pred = preds.get(f, FieldPrediction.nr())
                df.at[i, f"{f}_value"] = pred.value
                df.at[i, f"{f}_unit"] = pred.unit
                df.at[i, f"{f}_evidence_quote"] = pred.evidence_quote
        for col in ("ambiguity_flag", "annotator_notes"):
            if col not in df.columns:
                df[col] = ""
        return AnnotationFrame(df, fields=list(fields))

    # --------------------------------------------------------------- io

    def write_predictions(self, frame: AnnotationFrame, out_csv) -> None:
        """Persist a prediction frame to disk."""
        frame.to_csv(out_csv)
        LOG.info("[%s] wrote predictions to %s", self.name, out_csv)
