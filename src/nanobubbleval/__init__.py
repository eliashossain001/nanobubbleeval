"""NanoBubbleEval: schema extraction, numerical grounding, and evidence
attribution benchmark for the nanobubble / nanocarrier literature.

Architecture (clean layered design):

    Domain layer
        schema.py            FieldSpec, UnitNormalizer  (value objects)
        frames.py            AnnotationFrame, FieldCell (typed wrappers)
        baselines/base.py    FieldPrediction            (value object)

    Application / use-case layer
        evaluator.py         Evaluator, MatchPolicy     (services)
        reconciliation.py    Reconciler                 (service)
        splits.py            SplitBuilder, Sampler      (services)
        baselines/base.py    Baseline (ABC)             (strategy)
        baselines/regex_baseline.py  RegexBaseline      (concrete strategy)

    Infrastructure layer
        paths.py             ProjectPaths               (path resolution)
        cli.py               argparse subcommands       (CLI)

Public API (stable across minor releases):
    from nanobubbleval import (
        AnnotationFrame, Evaluator, FieldMetrics, FieldSpec,
        HEADLINE_FIELDS, NR, NUMERIC_FIELDS, ReconciliationReport,
        Reconciler, SplitBuilder, StratifiedSampler, TEXT_FIELDS,
        UnitNormalizer,
        # baselines
        Baseline, FieldPrediction, RegexBaseline,
        # paths
        ProjectPaths, paths,
    )
"""

from nanobubbleval.baselines import (
    Baseline, EncoderConfig, EncoderQABaseline,
    FieldPrediction, LLMBaseline, LLMConfig, RegexBaseline,
)
from nanobubbleval.evaluator import Evaluator, FieldMetrics
from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.paths import ProjectPaths, paths
from nanobubbleval.reconciliation import ReconciliationReport, Reconciler
from nanobubbleval.schema import (
    HEADLINE_FIELDS,
    NR,
    NUMERIC_FIELDS,
    TEXT_FIELDS,
    FieldSpec,
    UnitNormalizer,
)
from nanobubbleval.splits import SplitBuilder, StratifiedSampler

__all__ = [
    # data / domain
    "AnnotationFrame",
    "FieldSpec",
    "HEADLINE_FIELDS",
    "NR",
    "NUMERIC_FIELDS",
    "TEXT_FIELDS",
    "UnitNormalizer",
    # use cases
    "Evaluator",
    "FieldMetrics",
    "ReconciliationReport",
    "Reconciler",
    "SplitBuilder",
    "StratifiedSampler",
    # baselines
    "Baseline",
    "EncoderConfig",
    "EncoderQABaseline",
    "FieldPrediction",
    "LLMBaseline",
    "LLMConfig",
    "RegexBaseline",
    # infrastructure
    "ProjectPaths",
    "paths",
]

__version__ = "0.1.0"
