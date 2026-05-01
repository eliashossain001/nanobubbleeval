"""Baseline subpackage.

Public API:
    Baseline           abstract base class for any extraction baseline
    FieldPrediction    immutable per-field prediction value object
    RegexBaseline      B1: rule-based regex extractor (D1)
"""

from nanobubbleval.baselines.base import Baseline, FieldPrediction
from nanobubbleval.baselines.regex_baseline import RegexBaseline

__all__ = ["Baseline", "FieldPrediction", "RegexBaseline"]
