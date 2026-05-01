"""Annotation frames: typed wrappers around iaa-subset-shaped DataFrames.

``AnnotationFrame`` enforces the column schema (``record_id``,
``<field>_value``, ``<field>_unit``, ``<field>_evidence_quote`` for each
headline field) and provides typed accessors used by the Evaluator and
Reconciler.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import pandas as pd

from nanobubbleval.schema import HEADLINE_FIELDS, NR


@dataclass(frozen=True)
class FieldCell:
    """A single (record, field) annotation cell."""
    record_id: str
    field: str
    value: str
    unit: str
    evidence_quote: str

    def is_emit(self, is_nr_fn) -> bool:  # pragma: no cover - trivial
        return not is_nr_fn(self.value)


class AnnotationFrame:
    """Typed wrapper around an annotation DataFrame.

    The expected column schema is::

        record_id
        <field>_value
        <field>_unit
        <field>_evidence_quote
        ambiguity_flag       (optional)
        annotator_notes      (optional)

    for each ``field`` in ``HEADLINE_FIELDS``.

    Example:
        >>> af = AnnotationFrame.from_csv("iaa_subset.csv")
        >>> af.cell("ORG003", "size")
        FieldCell(record_id='ORG003', field='size', value='200', unit='nm', ...)
    """

    META_COLUMNS = ("record_id",)
    ANNOTATION_SUFFIXES = ("value", "unit", "evidence_quote")
    OPTIONAL_COLUMNS = ("ambiguity_flag", "annotator_notes")

    def __init__(
        self,
        df: pd.DataFrame,
        fields: Iterable[str] = HEADLINE_FIELDS,
        *,
        validate: bool = True,
    ) -> None:
        self._fields = list(fields)
        self._df = df.copy()
        if validate:
            self._validate()
        self._df["record_id"] = self._df["record_id"].astype(str)

    # ------------------------------------------------------------------ ctor

    @classmethod
    def from_csv(
        cls, path: str | Path, fields: Iterable[str] = HEADLINE_FIELDS,
    ) -> "AnnotationFrame":
        df = pd.read_csv(path, low_memory=False)
        df = df.loc[:, ~df.columns.duplicated()].copy()
        return cls(df, fields=fields)

    # ---------------------------------------------------------------- schema

    @classmethod
    def required_columns(cls, fields: Iterable[str] = HEADLINE_FIELDS) -> list[str]:
        cols: list[str] = list(cls.META_COLUMNS)
        for f in fields:
            for s in cls.ANNOTATION_SUFFIXES:
                cols.append(f"{f}_{s}")
        return cols

    def _validate(self) -> None:
        missing = [c for c in self.required_columns(self._fields) if c not in self._df.columns]
        if missing:
            raise ValueError(
                f"AnnotationFrame is missing required columns: {missing}. "
                f"Got columns: {sorted(self._df.columns)[:10]}..."
            )
        if self._df["record_id"].duplicated().any():
            n_dup = int(self._df["record_id"].duplicated().sum())
            raise ValueError(f"AnnotationFrame has {n_dup} duplicate record_id values")

    # -------------------------------------------------------------- accessors

    @property
    def fields(self) -> list[str]:
        return list(self._fields)

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    def __len__(self) -> int:
        return len(self._df)

    def record_ids(self) -> list[str]:
        return self._df["record_id"].tolist()

    def cell(self, record_id: str, field: str) -> FieldCell:
        if field not in self._fields:
            raise KeyError(f"unknown field '{field}'")
        sub = self._df[self._df["record_id"] == str(record_id)]
        if sub.empty:
            raise KeyError(f"unknown record_id '{record_id}'")
        row = sub.iloc[0]
        return FieldCell(
            record_id=str(row["record_id"]),
            field=field,
            value=str(row.get(f"{field}_value", "") or ""),
            unit=str(row.get(f"{field}_unit", "") or ""),
            evidence_quote=str(row.get(f"{field}_evidence_quote", "") or ""),
        )

    def iter_cells(self, field: str) -> Iterator[FieldCell]:
        if field not in self._fields:
            raise KeyError(f"unknown field '{field}'")
        v_col = f"{field}_value"
        u_col = f"{field}_unit"
        e_col = f"{field}_evidence_quote"
        for _, row in self._df.iterrows():
            yield FieldCell(
                record_id=str(row["record_id"]),
                field=field,
                value=str(row.get(v_col, "") or ""),
                unit=str(row.get(u_col, "") or ""),
                evidence_quote=str(row.get(e_col, "") or ""),
            )

    # ----------------------------------------------------------------- write

    def to_csv(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._df.to_csv(path, index=False)

    # ----------------------------------------------------------- constructor

    @classmethod
    def empty(
        cls, record_ids: Iterable[str], fields: Iterable[str] = HEADLINE_FIELDS,
    ) -> "AnnotationFrame":
        ids = list(record_ids)
        cols = cls.required_columns(fields) + list(cls.OPTIONAL_COLUMNS)
        df = pd.DataFrame({c: [""] * len(ids) for c in cols})
        df["record_id"] = ids
        return cls(df, fields=fields)
