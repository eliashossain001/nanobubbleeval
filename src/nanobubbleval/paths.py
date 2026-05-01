"""Project path resolution.

Centralises every well-known file and directory path so scripts and tests
do not hard-code strings that drift when the layout changes. The
:class:`ProjectPaths` class auto-discovers the project root by walking up
from ``__file__`` until it finds ``pyproject.toml``.

Usage:
    >>> from nanobubbleval.paths import paths
    >>> paths.gold_pool                # PosixPath('.../data/gold/...')
    >>> paths.iaa_packet               # PosixPath('.../annotation/packet')
    >>> paths.results_metrics_for("qwen25_7b")
    PosixPath('.../results/metrics/qwen25_7b.csv')

To override (tests, custom checkouts):
    >>> paths_alt = ProjectPaths(root=Path("/tmp/sandbox"))
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT_MARKER = "pyproject.toml"


@dataclass(frozen=True)
class ProjectPaths:
    """Immutable directory bundle for the project layout.

    All attributes are :class:`pathlib.Path` instances, computed lazily from
    ``root``. Construct without arguments to auto-discover the project root,
    or pass ``root=Path(...)`` to point at a custom checkout (used in tests).
    """

    root: Path

    # ------------------------------------------------------------------ ctor

    @classmethod
    def discover(cls, start: Optional[Path] = None) -> "ProjectPaths":
        """Walk upward from ``start`` (default: this module's directory)
        until a directory containing ``pyproject.toml`` is found."""
        cur = (start or Path(__file__)).resolve()
        for parent in (cur, *cur.parents):
            if (parent / PROJECT_ROOT_MARKER).is_file():
                return cls(root=parent)
        raise FileNotFoundError(
            f"could not find project root (no {PROJECT_ROOT_MARKER} above {cur})"
        )

    # -------------------------------------------------------------- top-level

    @property
    def src(self) -> Path: return self.root / "src" / "nanobubbleval"
    @property
    def tests(self) -> Path: return self.root / "tests"
    @property
    def configs(self) -> Path: return self.root / "configs"
    @property
    def docs(self) -> Path: return self.root / "docs"
    @property
    def paper(self) -> Path: return self.root / "paper"
    @property
    def archive(self) -> Path: return self.root / "archive"

    # ---------------------------------------------------------------- data

    @property
    def data(self) -> Path: return self.root / "data"
    @property
    def data_raw(self) -> Path: return self.data / "raw"
    @property
    def data_curated(self) -> Path: return self.data / "curated"
    @property
    def data_gold(self) -> Path: return self.data / "gold"
    @property
    def data_tasks(self) -> Path: return self.data / "tasks"
    @property
    def data_seeds(self) -> Path: return self.data / "seeds"
    @property
    def data_splits(self) -> Path: return self.data / "splits"

    # well-known dataset files
    @property
    def warehouse(self) -> Path: return self.data_raw / "master_inventory.csv"
    @property
    def core(self) -> Path: return self.data_curated / "nanobubble_core_high_precision.csv"
    @property
    def gold_pool(self) -> Path: return self.data_gold / "gold_annotation_set_v3.csv"
    @property
    def gold_pool_v2(self) -> Path: return self.data_gold / "gold_annotation_set_v2.csv"
    @property
    def schema(self) -> Path: return self.configs / "extraction_schema.json"

    # task views
    @property
    def task_structured(self) -> Path:
        return self.data_tasks / "structured_extraction_benchmark.csv"
    @property
    def task_numerical(self) -> Path:
        return self.data_tasks / "numerical_grounding_benchmark.csv"
    @property
    def task_evidence(self) -> Path:
        return self.data_tasks / "evidence_attribution_benchmark.csv"

    # split artefacts
    @property
    def splits_json(self) -> Path: return self.data_splits / "splits.json"
    @property
    def slice_summary(self) -> Path: return self.data_splits / "slice_summary.md"
    @property
    def leakage_report(self) -> Path: return self.data_splits / "leakage_report.md"

    # ---------------------------------------------------------- annotation

    @property
    def annotation(self) -> Path: return self.root / "annotation"
    @property
    def iaa_packet(self) -> Path: return self.annotation / "packet"
    @property
    def iaa_received(self) -> Path: return self.annotation / "received"
    @property
    def iaa_gold_hard(self) -> Path: return self.annotation / "gold_hard"

    # well-known annotation files
    @property
    def iaa_subset(self) -> Path: return self.iaa_packet / "iaa_subset.csv"
    @property
    def iaa_subset_keys(self) -> Path: return self.iaa_packet / "iaa_subset_keys.csv"
    @property
    def iaa_guide(self) -> Path: return self.iaa_packet / "annotation_guide.md"
    @property
    def iaa_instructions(self) -> Path: return self.iaa_packet / "instructions.md"
    @property
    def gold_hard(self) -> Path: return self.iaa_gold_hard / "gold_hard.csv"

    # ------------------------------------------------------------- baselines

    @property
    def baselines(self) -> Path: return self.root / "baselines"
    @property
    def baselines_regex(self) -> Path: return self.baselines / "regex"
    @property
    def baselines_encoder(self) -> Path: return self.baselines / "encoder"
    @property
    def baselines_llm(self) -> Path: return self.baselines / "llm"

    def predictions_for(self, baseline_name: str) -> Path:
        """Conventional location for a baseline's prediction CSV."""
        family = self._baseline_family(baseline_name)
        return self.baselines / family / f"{baseline_name}_predictions.csv"

    @staticmethod
    def _baseline_family(name: str) -> str:
        n = name.lower()
        if "regex" in n:
            return "regex"
        if "bert" in n or "encoder" in n or "qa" in n:
            return "encoder"
        return "llm"

    # ---------------------------------------------------------------- results

    @property
    def results(self) -> Path: return self.root / "results"
    @property
    def results_metrics(self) -> Path: return self.results / "metrics"
    @property
    def results_slices(self) -> Path: return self.results / "slices"
    @property
    def results_errors(self) -> Path: return self.results / "error_taxonomy"

    def results_metrics_for(self, baseline_name: str) -> Path:
        return self.results_metrics / f"{baseline_name}.csv"

    def results_slices_for(self, baseline_name: str) -> Path:
        return self.results_slices / f"{baseline_name}.csv"

    # --------------------------------------------------------------- helpers

    def ensure_writable_dirs(self) -> None:
        """Create every output directory that scripts may write to."""
        for p in (
            self.data_splits,
            self.iaa_received, self.iaa_gold_hard,
            self.baselines_regex, self.baselines_encoder, self.baselines_llm,
            self.results_metrics, self.results_slices, self.results_errors,
        ):
            p.mkdir(parents=True, exist_ok=True)


# Module-level singleton: import as `paths` for scripts.
paths: ProjectPaths = ProjectPaths.discover()
