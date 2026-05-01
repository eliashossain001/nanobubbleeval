"""Smoke tests for the annotation helper. We do not exercise the
interactive prompts; we only test the structure-level helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from nanobubbleval.schema import HEADLINE_FIELDS, NR

# Load scripts/05_annotate.py as a module for testing
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "05_annotate.py"
spec = importlib.util.spec_from_file_location("annotate_mod", SCRIPT_PATH)
annotate_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(annotate_mod)


def _row(**kwargs) -> pd.Series:
    base = {f"{f}_{s}": "" for f in HEADLINE_FIELDS for s in ("value", "unit", "evidence_quote")}
    base.update(kwargs)
    return pd.Series(base)


def test_is_complete_row_empty_returns_false():
    r = _row()
    assert annotate_mod._is_complete_row(r) is False


def test_is_complete_row_partial_returns_false():
    r = _row(size_value="200", size_unit="nm", size_evidence_quote="200 nm")
    assert annotate_mod._is_complete_row(r) is False


def test_is_complete_row_all_filled_returns_true():
    fields = {}
    for f in HEADLINE_FIELDS:
        fields[f"{f}_value"] = NR if f != "size" else "200"
        fields[f"{f}_unit"] = NR
        fields[f"{f}_evidence_quote"] = NR
    r = _row(**fields)
    assert annotate_mod._is_complete_row(r) is True


def test_field_help_table_covers_all_headline_fields():
    for f in HEADLINE_FIELDS:
        assert f in annotate_mod.FIELD_HELP


def test_wrap_preserves_content():
    out = annotate_mod._wrap("hello world " * 20)
    assert "hello" in out and "world" in out
