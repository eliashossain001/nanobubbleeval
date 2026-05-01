# Pipeline scripts

Numbered orchestration scripts that drive the four stages of the v1.0 pipeline.
Each script is a thin wrapper around the `nanoeval` CLI exposed by the
`nanobubbleval` package — pipeline logic lives in `src/nanobubbleval/`.

## Stage order

| # | Script | Purpose |
|---|---|---|
| 01 | [`01_build_iaa_subset.py`](01_build_iaa_subset.py) | Sample 40 stratified records into `annotation/packet/` |
| 02 | [`02_build_splits.py`](02_build_splits.py) | Build dev/test splits + 5-slice tags into `data/splits/` |
| 03 | [`03_reconcile.py`](03_reconcile.py) | IAA computation between two annotator CSVs |
| 04 | [`04_evaluate.py`](04_evaluate.py) | Score a baseline's predictions against gold |

## Legacy harvest pipeline

The original API harvest scripts have moved to [`legacy_harvest/`](legacy_harvest/).
They produced the v1.0 warehouse (`data/raw/master_inventory.csv`, 52,519 records)
and are not re-run before the deadline. Kept for reproducibility:

| Script | Purpose |
|---|---|
| `api_bulk_harvest.py` | Multi-source harvest (PubMed, Europe PMC, OpenAlex, CrossRef, S2, CT.gov) |
| `build_master_inventory.py` | Dedup + merge into the master warehouse |
| `build_benchmark_curation.py` | Tier curation + benchmark candidate pools |
| `build_slices.py` | Coverage slices |
| `run_quality_checks.py` | Quality and dedup audits |

## Equivalent CLI commands

Each numbered script is equivalent to a `nanoeval` subcommand:

```bash
# 01: nanoeval build-iaa-subset --gold ... --out ... --n 40 --seed 42
# 02: nanoeval build-splits     --gold ... --iaa-keys ... --out ...
# 03: nanoeval reconcile        --a <A.csv> --b <B.csv> --out ...
# 04: nanoeval evaluate         --gold ... --pred ... --out ...
```
