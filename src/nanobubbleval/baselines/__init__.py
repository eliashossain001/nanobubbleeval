"""Baseline subpackage.

Public API:
    Baseline           abstract base class for any extraction baseline
    FieldPrediction    immutable per-field prediction value object
    RegexBaseline      B1: rule-based regex extractor (D1)
    LLMBaseline        B3: schema-constrained zero-shot instruction LLM (D2)
    LLMConfig          configuration dataclass for LLMBaseline
"""

from nanobubbleval.baselines.base import Baseline, FieldPrediction
from nanobubbleval.baselines.encoder_baseline import EncoderConfig, EncoderQABaseline
from nanobubbleval.baselines.llm_baseline import LLMBaseline, LLMConfig, parse_llm_json
from nanobubbleval.baselines.regex_baseline import RegexBaseline

__all__ = [
    "Baseline",
    "EncoderConfig",
    "EncoderQABaseline",
    "FieldPrediction",
    "LLMBaseline",
    "LLMConfig",
    "RegexBaseline",
    "parse_llm_json",
]
