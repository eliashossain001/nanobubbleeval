"""Unit tests for Reconciler."""

from __future__ import annotations

from nanobubbleval.reconciliation import Reconciler


def test_perfect_agreement_kappa_one(gold_frame):
    """Two identical annotators -> kappa = 1.0 on every field with both
    emit and NR examples."""
    rec = Reconciler()
    report = rec.run(gold_frame, gold_frame, label_a="A", label_b="B")
    for _, row in report.stats.iterrows():
        if row["n_emit_both"] > 0 and row["n"] > row["n_emit_both"]:
            assert row["kappa_NR_vs_emit"] == 1.0


def test_disagreement_count(gold_frame, pred_hallucinator_frame):
    """Hallucinator disagrees on every NR cell of gold."""
    rec = Reconciler()
    report = rec.run(gold_frame, pred_hallucinator_frame, label_a="gold", label_b="hall")
    assert len(report.disagreements) > 0
    assert (report.disagreements["disagreement_type"] == "hall_emit_gold_NR").any()


def test_outputs_have_expected_columns(gold_frame, pred_good_frame):
    rec = Reconciler()
    report = rec.run(gold_frame, pred_good_frame, label_a="A", label_b="B")
    assert "kappa_NR_vs_emit" in report.stats.columns
    assert "value_match_rate_among_both_emit" in report.stats.columns
    if not report.agreements.empty:
        assert "resolved_value" in report.agreements.columns
    if not report.disagreements.empty:
        assert "adjudicated_value" in report.disagreements.columns


def test_paper_table_renders(gold_frame, pred_good_frame):
    rec = Reconciler()
    report = rec.run(gold_frame, pred_good_frame, label_a="A", label_b="B")
    md = report.to_paper_table()
    assert "IAA Summary" in md
    assert "Field" in md
