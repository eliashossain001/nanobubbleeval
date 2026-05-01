"""Unit tests for the LLM baseline JSON-repair / parsing logic.

The model itself is not loaded here (would download ~14 GB). Instead we
test the parsing path end-to-end with synthetic LLM outputs that cover
the realistic failure modes (code fences, trailing commas, smart quotes,
embedded prose, missing keys, embedded nulls)."""

from __future__ import annotations

import pytest

from nanobubbleval.baselines.llm_baseline import (
    LLMBaseline, LLMConfig, _to_prediction, parse_llm_json,
)
from nanobubbleval.schema import HEADLINE_FIELDS, NR


# ---------------------------------------------------------------------------
# parse_llm_json
# ---------------------------------------------------------------------------

def test_parse_clean_json():
    raw = '{"size": {"value": "200", "unit": "nm", "evidence_quote": "200 nm"}}'
    out = parse_llm_json(raw)
    assert out is not None
    assert out["size"]["value"] == "200"


def test_parse_with_code_fence():
    raw = '```json\n{"size": {"value": "200", "unit": "nm", "evidence_quote": "200 nm"}}\n```'
    out = parse_llm_json(raw)
    assert out is not None
    assert out["size"]["unit"] == "nm"


def test_parse_with_trailing_commas():
    raw = '{"size": {"value": "200", "unit": "nm", "evidence_quote": "200 nm",},}'
    out = parse_llm_json(raw)
    assert out is not None


def test_parse_with_smart_quotes():
    raw = '{“size”: {“value”: “200”, “unit”: “nm”, “evidence_quote”: “200 nm”}}'
    out = parse_llm_json(raw)
    assert out is not None
    assert out["size"]["value"] == "200"


def test_parse_with_embedded_prose():
    raw = (
        "Sure! Here's the extracted JSON:\n\n"
        '{"size": {"value": "150", "unit": "nm", "evidence_quote": "150 nm diameter"}}'
        "\n\nLet me know if you have questions!"
    )
    out = parse_llm_json(raw)
    assert out is not None
    assert out["size"]["value"] == "150"


def test_parse_returns_none_on_garbage():
    assert parse_llm_json("this is not json at all") is None
    assert parse_llm_json("") is None
    assert parse_llm_json(None) is None


# ---------------------------------------------------------------------------
# _to_prediction
# ---------------------------------------------------------------------------

def test_to_prediction_full_field():
    fp = _to_prediction({"value": "200", "unit": "nm", "evidence_quote": "200 nm"})
    assert fp.value == "200"
    assert fp.unit == "nm"
    assert fp.evidence_quote == "200 nm"


def test_to_prediction_missing_keys_become_nr():
    fp = _to_prediction({})
    assert fp.value == NR


def test_to_prediction_null_becomes_nr():
    fp = _to_prediction({"value": None, "unit": None, "evidence_quote": None})
    assert fp.value == NR
    assert fp.evidence_quote == NR


def test_to_prediction_non_dict_becomes_nr():
    assert _to_prediction("just a string").value == NR
    assert _to_prediction(None).value == NR
    assert _to_prediction(42).value == NR


def test_to_prediction_coerces_numbers_to_string():
    fp = _to_prediction({"value": 200, "unit": "nm", "evidence_quote": "200 nm"})
    assert fp.value == "200"


# ---------------------------------------------------------------------------
# LLMBaseline (without loading the model)
# ---------------------------------------------------------------------------

def test_llm_baseline_constructor_does_not_load_model():
    """Constructor must be cheap; loading happens lazily on first prediction."""
    bl = LLMBaseline()
    assert bl.name == "qwen25-7b-instruct"
    assert bl._model is None
    assert bl._tokenizer is None


def test_llm_baseline_name_changes_with_model_id():
    bl = LLMBaseline(LLMConfig(model_id="meta-llama/Llama-3.1-8B-Instruct"))
    assert bl.name == "llama-3.1-8b-instruct"


def test_llm_baseline_returns_nr_on_empty_abstract():
    bl = LLMBaseline()
    preds = bl.predict_record("r1", "")
    for f in HEADLINE_FIELDS:
        assert preds[f].value == NR


def test_llm_baseline_returns_nr_dict_on_unparseable_response(monkeypatch):
    bl = LLMBaseline()
    # Bypass model loading; force generation to return garbage
    monkeypatch.setattr(bl, "_generate", lambda _abstract: "not valid json at all")
    preds = bl.predict_record("r1", "Some abstract.")
    for f in HEADLINE_FIELDS:
        assert preds[f].value == NR


def test_llm_baseline_parses_valid_response(monkeypatch):
    bl = LLMBaseline()
    fake = (
        '{"size": {"value": "200", "unit": "nm", "evidence_quote": "200 nm"},'
        ' "zeta_potential": {"value": "NOT_REPORTED", "unit": "NOT_REPORTED", "evidence_quote": "NOT_REPORTED"},'
        ' "stability": {"value": "NOT_REPORTED", "unit": "NOT_REPORTED", "evidence_quote": "NOT_REPORTED"},'
        ' "payload": {"value": "doxorubicin", "unit": "", "evidence_quote": "doxorubicin"},'
        ' "loading_efficiency": {"value": "80", "unit": "%", "evidence_quote": "80% loading"},'
        ' "release_profile": {"value": "NOT_REPORTED", "unit": "NOT_REPORTED", "evidence_quote": "NOT_REPORTED"}}'
    )
    monkeypatch.setattr(bl, "_generate", lambda _abstract: fake)
    preds = bl.predict_record("r1", "Some abstract.")
    assert preds["size"].value == "200"
    assert preds["payload"].value == "doxorubicin"
    assert preds["zeta_potential"].value == NR
