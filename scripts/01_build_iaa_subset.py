"""Stage 1: Sample the IAA subset.

Reproduces the v1.0 IAA subset (40 records, seed=42, stratified by
nanobubble_vs_nanoparticle x document_type).

I/O:
    in   data/gold/gold_annotation_set_v3.csv
    out  annotation/packet/iaa_subset.csv
         annotation/packet/iaa_subset_keys.csv

Run:
    python3 scripts/01_build_iaa_subset.py
"""

from __future__ import annotations

from nanobubbleval.cli import main
from nanobubbleval.paths import paths


if __name__ == "__main__":
    main([
        "build-iaa-subset",
        "--gold", str(paths.gold_pool),
        "--out", str(paths.iaa_packet),
        "--n", "40",
        "--seed", "42",
    ])
