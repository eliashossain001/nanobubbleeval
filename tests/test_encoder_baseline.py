"""Unit tests for EncoderQABaseline (B2). Model loading is NOT exercised
here; we test the parsing + thresholding logic on synthetic QA outputs."""

from __future__ import annotations

import pytest

from nanobubbleval.baselines.encoder_baseline import (
    EncoderConfig, EncoderQABaseline, _parse_numeric_span, _parse_text_span,
)
from nanobubbleval.schema import HEADLINE_FIELDS, NR, UnitNormalizer


@pytest.fixture
def normalizer() -> UnitNormalizer:
    return UnitNormalizer()


# ---------------------------------------------------------------------------
# Numeric span parsing
# ---------------------------------------------------------------------------

def test_parse_numeric_span_with_unit(normalizer):
    fp = _parse_numeric_span("200 nm in diameter", "size", normalizer)
    assert fp.value == "200"
    assert fp.unit == "nm"


def test_parse_numeric_span_negative(normalizer):
    fp = _parse_numeric_span("zeta -12.5 mV", "zeta_potential", normalizer)
    assert fp.value == "-12.5"
    assert fp.unit.lower() == "mv"


def test_parse_numeric_span_percent(normalizer):
    fp = _parse_numeric_span("80% encapsulation", "loading_efficiency", normalizer)
    assert fp.value == "80"
    assert fp.unit == "%"


def test_parse_numeric_span_empty(normalizer):
    assert _parse_numeric_span("", "size", normalizer).value == NR
    assert _parse_numeric_span(None, "size", normalizer).value == NR


def test_parse_numeric_span_no_unit_falls_back_to_number(normalizer):
    fp = _parse_numeric_span("approximately 200", "size", normalizer)
    assert fp.value == "200"
    assert fp.unit == NR


def test_parse_numeric_span_unparseable(normalizer):
    fp = _parse_numeric_span("not a number at all", "size", normalizer)
    assert fp.value == NR


# ---------------------------------------------------------------------------
# Text span parsing
# ---------------------------------------------------------------------------

def test_parse_text_span():
    fp = _parse_text_span("doxorubicin")
    assert fp.value == "doxorubicin"
    assert fp.unit == ""


def test_parse_text_span_empty():
    assert _parse_text_span("").value == NR
    assert _parse_text_span("   ").value == NR


# ---------------------------------------------------------------------------
# Baseline class (mocked pipeline)
# ---------------------------------------------------------------------------

def test_constructor_does_not_load_model():
    bl = EncoderQABaseline()
    assert bl.name == "biobert-squadv2"
    assert bl._model is None
    assert bl._tokenizer is None


def test_name_changes_with_model_id():
    bl = EncoderQABaseline(EncoderConfig(model_id="dmis-lab/biobert-base-cased-v1.1-squad"))
    assert bl.name == "biobert-base-cased-v1.1-squad"


def test_returns_nr_on_empty_abstract():
    bl = EncoderQABaseline()
    preds = bl.predict_record("r1", "")
    for f in HEADLINE_FIELDS:
        assert preds[f].value == NR


def test_threshold_drops_low_confidence(monkeypatch):
    bl = EncoderQABaseline(EncoderConfig(confidence_threshold=0.5))
    monkeypatch.setattr(bl, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(bl, "_qa", lambda q, c: ("200 nm", 0.10))  # below threshold
    preds = bl.predict_record("r1", "Some abstract.")
    assert preds["size"].value == NR


def test_threshold_keeps_high_confidence(monkeypatch):
    bl = EncoderQABaseline(EncoderConfig(confidence_threshold=0.10))
    answers = {
        "size": ("200 nm", 0.9),
        "zeta_potential": ("", 0.05),
        "stability": ("", 0.0),
        "payload": ("doxorubicin", 0.8),
        "loading_efficiency": ("", 0.0),
        "release_profile": ("", 0.0),
    }
    field_iter = iter(HEADLINE_FIELDS)
    monkeypatch.setattr(bl, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(bl, "_qa", lambda q, c: answers[next(field_iter)])
    preds = bl.predict_record("r1", "200 nm doxorubicin")
    assert preds["size"].value == "200"
    assert preds["zeta_potential"].value == NR
    assert preds["payload"].value == "doxorubicin"
