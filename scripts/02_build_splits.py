"""Stage 2: Build dev/test splits + 5-slice tagging.

Stratified by nb_label x document_type, IAA records pinned to test.

I/O:
    in   data/gold/gold_annotation_set_v3.csv
         annotation/packet/iaa_subset_keys.csv
    out  data/splits/splits.json
         data/splits/slice_summary.md
         data/splits/leakage_report.md

Run:
    python3 scripts/02_build_splits.py
"""

from __future__ import annotations

from nanobubbleval.cli import main
from nanobubbleval.paths import paths


if __name__ == "__main__":
    main([
        "build-splits",
        "--gold", str(paths.gold_pool),
        "--iaa-keys", str(paths.iaa_subset_keys),
        "--out", str(paths.data_splits),
    ])
