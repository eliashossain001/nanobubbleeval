"""Unit tests for the Baseline ABC and RegexBaseline."""

from __future__ import annotations

import pandas as pd
import pytest

from nanobubbleval.baselines import Baseline, FieldPrediction, RegexBaseline
from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.schema import HEADLINE_FIELDS, NR, NUMERIC_FIELDS


def test_field_prediction_defaults_to_nr():
    fp = FieldPrediction()
    assert fp.value == NR
    assert fp.evidence_quote == NR
    assert not fp.is_emit()


def test_field_prediction_nr_helper():
    fp = FieldPrediction.nr()
    assert fp.value == NR and fp.unit == NR and fp.evidence_quote == NR


def test_subclass_must_set_name():
    with pytest.raises(TypeError):
        class Bad(Baseline):  # missing `name = ...`
            def predict_record(self, rid, abs_): return {}


def test_subclass_with_name_is_valid():
    class Ok(Baseline):
        name = "ok"
        def predict_record(self, rid, abs_):
            return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
    assert Ok().name == "ok"


def test_regex_baseline_matches_size():
    bl = RegexBaseline()
    preds = bl.predict_record(
        "r1", "Lipid nanobubbles 200 nm in diameter were prepared.",
    )
    assert preds["size"].value == "200"
    assert preds["size"].unit == "nm"


def test_regex_baseline_matches_zeta_potential():
    bl = RegexBaseline()
    preds = bl.predict_record("r1", "Zeta potential -12.5 mV measured by DLS.")
    assert preds["zeta_potential"].value == "-12.5"
    assert preds["zeta_potential"].unit.lower() == "mv"


def test_regex_baseline_matches_loading_efficiency():
    bl = RegexBaseline()
    preds = bl.predict_record(
        "r1", "Encapsulation efficiency 81% with sustained release.",
    )
    assert preds["loading_efficiency"].value == "81"
    assert preds["loading_efficiency"].unit == "%"


def test_regex_baseline_returns_nr_for_text_fields():
    bl = RegexBaseline()
    preds = bl.predict_record("r1", "Particles loaded with doxorubicin.")
    # text fields are always NR for B1
    assert preds["payload"].value == NR
    assert preds["release_profile"].value == NR


def test_regex_baseline_returns_nr_when_unmatched():
    bl = RegexBaseline()
    preds = bl.predict_record("r1", "We review applications in water treatment.")
    for f in NUMERIC_FIELDS:
        assert preds[f].value == NR


def test_predict_frame_default_iterates_records():
    df = pd.DataFrame({
        "record_id": ["r1", "r2"],
        "abstract_or_summary": [
            "Particles 150 nm in diameter, zeta -20 mV.",
            "We review water-treatment applications of nanobubbles.",
        ],
    })
    # add empty annotation columns expected by AnnotationFrame
    for f in HEADLINE_FIELDS:
        for s in ("value", "unit", "evidence_quote"):
            df[f"{f}_{s}"] = ""
    frame = AnnotationFrame(df)

    out = RegexBaseline().predict_frame(frame)
    assert out.cell("r1", "size").value == "150"
    assert out.cell("r1", "size").unit == "nm"
    assert out.cell("r2", "size").value == NR
