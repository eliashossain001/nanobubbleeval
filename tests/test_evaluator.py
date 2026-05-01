"""Unit tests for Evaluator."""

from __future__ import annotations

from nanobubbleval.evaluator import Evaluator


def test_perfect_extractor_acal_geq_naive(gold_frame, pred_good_frame):
    """A near-perfect extractor that emits NR when gold is NR should have
    Acal-F1 >= Naive-F1 (the NR class lifts the macro)."""
    ev = Evaluator()
    df = ev.evaluate(gold_frame, pred_good_frame)
    macro = df[df["field"] == "MACRO"].iloc[0]
    assert macro["acal_f1"] >= macro["naive_f1"]


def test_hallucinator_has_zero_nr_f1(gold_frame, pred_hallucinator_frame):
    """A model that never says NR should have nr_f1 == 0 on every field
    where gold has any NR labels."""
    ev = Evaluator()
    df = ev.evaluate(gold_frame, pred_hallucinator_frame)
    df = df[df["field"] != "MACRO"]
    has_nr_gold = df["n_nr_gold"] > 0
    assert (df.loc[has_nr_gold, "nr_f1"] == 0).all()


def test_acal_lower_than_naive_for_hallucinator(gold_frame, pred_hallucinator_frame):
    """Hallucinator: Acal-F1 should be <= Naive-F1 because NR-class scores 0."""
    ev = Evaluator()
    df = ev.evaluate(gold_frame, pred_hallucinator_frame)
    macro = df[df["field"] == "MACRO"].iloc[0]
    assert macro["acal_f1"] <= macro["naive_f1"] + 1e-9


def test_size_field_metric_shape(gold_frame, pred_good_frame):
    ev = Evaluator()
    fm = ev.field_metrics(gold_frame, pred_good_frame, "size")
    assert fm.field == "size"
    assert fm.n == 6
    assert fm.naive_f1 >= 0.0 and fm.naive_f1 <= 1.0
    assert fm.acal_f1 >= 0.0 and fm.acal_f1 <= 1.0
    assert fm.n_emit_gold == 4
    assert fm.unit_accuracy is not None


def test_unit_normalisation_credits_equivalent_units(gold_frame, pred_good_frame):
    """gold says 0.5 um, pred says 500 nm. After normalisation both are 500
    nm and num_match should credit it."""
    ev = Evaluator()
    fm = ev.field_metrics(gold_frame, pred_good_frame, "size")
    assert fm.num_match == 1.0
