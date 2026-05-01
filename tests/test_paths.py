"""Unit tests for ProjectPaths."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanobubbleval.paths import ProjectPaths, paths


def test_singleton_resolves_repo_root_with_pyproject():
    assert (paths.root / "pyproject.toml").is_file()


def test_well_known_files_point_inside_data():
    assert paths.gold_pool.parent == paths.data_gold
    assert paths.warehouse.parent == paths.data_raw
    assert paths.task_structured.parent == paths.data_tasks


def test_baseline_family_routing():
    assert paths.predictions_for("regex-v1").parent == paths.baselines_regex
    assert paths.predictions_for("pubmedbert-qa").parent == paths.baselines_encoder
    assert paths.predictions_for("qwen25_7b").parent == paths.baselines_llm


def test_results_for_baseline():
    p = paths.results_metrics_for("qwen25_7b")
    assert p.parent == paths.results_metrics
    assert p.name == "qwen25_7b.csv"


def test_can_override_root(tmp_path: Path):
    sandbox = ProjectPaths(root=tmp_path)
    assert sandbox.root == tmp_path
    assert sandbox.gold_pool == tmp_path / "data" / "gold" / "gold_annotation_set_v3.csv"


def test_discover_raises_outside_project(tmp_path: Path):
    nowhere = tmp_path / "no_pyproject_anywhere"
    nowhere.mkdir()
    with pytest.raises(FileNotFoundError):
        ProjectPaths.discover(start=nowhere)
