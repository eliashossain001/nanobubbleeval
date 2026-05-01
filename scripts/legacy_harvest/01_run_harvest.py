"""Stage A: run the multi-source harvest.

Drives the :class:`HarvestOrchestrator` across the canonical query-family
table for the configured sources. Outputs the deduplicated warehouse to
``data/raw/master_inventory.csv`` and the raw cache (one CSV per source)
to ``data/harvest_cache/``.

I/O:
    out  data/raw/master_inventory.csv
         data/harvest_cache/<source>.csv      one per source

Run (small smoke test, ~5 minutes):
    python3 scripts/legacy_harvest/01_run_harvest.py --per-query-cap 50

Run (full v1.0 harvest, several hours wall-clock, ~50K records):
    python3 scripts/legacy_harvest/01_run_harvest.py --per-query-cap 5000

Sources active in v1.0:
    PubMed (E-utilities) — biomedical core
    OpenAlex             — broad scholarly graph

Additional sources (Europe PMC, CrossRef, Semantic Scholar,
ClinicalTrials.gov) are scheduled for the v1.1 harvest expansion.
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from nanobubbleval.harvest import (
    HarvestOrchestrator,
    OpenAlexSource,
    PubMedSource,
    QUERY_FAMILIES,
)
from nanobubbleval.paths import paths


def _argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the multi-source harvest")
    p.add_argument("--per-query-cap", type=int, default=200,
                   help="Max records to fetch per (source, query) pair")
    p.add_argument("--mailto", default=None,
                   help="Optional polite-pool email for OpenAlex")
    p.add_argument("--family", default=None,
                   help="Restrict to one query family (default: all)")
    p.add_argument("--source", choices=["pubmed", "openalex", "all"],
                   default="all", help="Restrict to one source")
    return p


def main() -> int:
    args = _argparser().parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("harvest")

    sources = []
    if args.source in ("pubmed", "all"):
        sources.append(PubMedSource())
    if args.source in ("openalex", "all"):
        sources.append(OpenAlexSource(mailto=args.mailto))

    families = QUERY_FAMILIES
    if args.family:
        if args.family not in families:
            log.error("unknown family %r; valid: %s", args.family, list(families))
            return 1
        families = {args.family: families[args.family]}

    orch = HarvestOrchestrator(sources)

    # Run. For traceability, also save raw per-source CSVs (pre-dedup).
    raw_records = orch.run(query_families=families,
                           per_query_cap=args.per_query_cap,
                           deduplicate=False)

    cache_dir = paths.data / "harvest_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        sub = [r for r in raw_records if r.source_api == src.api_name]
        if sub:
            df = pd.DataFrame(rec.to_dict() for rec in sub)
            df.to_csv(cache_dir / f"{src.api_name.lower()}.csv", index=False)
            log.info("Wrote %d %s records to %s",
                     len(sub), src.api_name,
                     cache_dir / f"{src.api_name.lower()}.csv")

    deduped = orch.deduplicator.deduplicate(raw_records)
    paths.warehouse.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rec.to_dict() for rec in deduped)
    df.to_csv(paths.warehouse, index=False)
    log.info("Wrote %d deduplicated records to %s", len(df), paths.warehouse)

    print(f"\nDone. Raw: {len(raw_records)}, deduplicated: {len(deduped)}")
    print(f"Warehouse: {paths.warehouse}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
