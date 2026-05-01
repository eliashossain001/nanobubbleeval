"""Harvest orchestrator and the canonical query-family table.

The query families below mirror the paper's Appendix~A and the recovered
``docs/query_families.md``. They are the contract under which the v1.0
warehouse was harvested and must not be edited without bumping the v1.0
release.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from nanobubbleval.harvest.base import HarvestRecord, HarvestSource, SourceResult
from nanobubbleval.harvest.deduplicator import Deduplicator

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical query families (frozen for v1.0)
# ---------------------------------------------------------------------------

QUERY_FAMILIES: dict[str, list[str]] = {
    "nanobubble_core": [
        "nanobubble", "bulk nanobubble", "ultrafine bubble",
        "micro nanobubble", "oxygen nanobubble", "nanobubble stability",
        "nanobubble characterization", "nanobubble generation",
        "nanobubble cavitation", "nanobubble imaging", "nanobubble therapy",
        "nanobubble drug delivery",
    ],
    "ultrasound_imaging": [
        "ultrasound contrast agent", "gas-filled liposome",
        "acoustic nanocarrier", "targeted ultrasound imaging",
        "molecular ultrasound imaging", "ultrasound-triggered drug delivery",
        "sonodynamic therapy nanocarrier",
        "theranostic ultrasound nanoparticle",
    ],
    "delivery_release": [
        "nanoparticle payload", "loading efficiency",
        "encapsulation efficiency", "release profile",
        "controlled release nanoparticle", "sustained release nanocarrier",
        "drug loading nanoparticle", "carrier stability",
        "colloidal stability", "particle size zeta potential",
    ],
    "biomedical_nanocarriers": [
        "lipid nanoparticle drug delivery", "polymer nanoparticle delivery",
        "liposome drug loading", "cubosome drug delivery",
        "niosome drug delivery", "exosome-coated nanocarrier",
        "PLGA nanoparticle release", "targeted cancer nanocarrier",
        "nanomedicine", "nanocarrier", "drug delivery system",
        "controlled release", "biomedical nanocarrier",
    ],
    "environmental_water_agriculture": [
        "nanobubble water treatment", "micro nanobubble irrigation",
        "oxygen nanobubble aquaculture", "nanobubble flotation",
        "nanobubble biofilm removal", "nanobubble wastewater treatment",
        "nanobubble agriculture",
    ],
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class HarvestOrchestrator:
    """Drive a list of sources across a query-family table.

    Example:
        >>> orch = HarvestOrchestrator([PubMedSource(), OpenAlexSource()])
        >>> records = orch.run(query_families=QUERY_FAMILIES, per_query_cap=200)
        >>> df = orch.records_to_dataframe(records)
    """

    def __init__(
        self,
        sources: Sequence[HarvestSource],
        deduplicator: Optional[Deduplicator] = None,
    ) -> None:
        self.sources = list(sources)
        self.deduplicator = deduplicator or Deduplicator()

    def run(
        self,
        query_families: dict[str, list[str]] = QUERY_FAMILIES,
        *,
        per_query_cap: int = 200,
        deduplicate: bool = True,
    ) -> List[HarvestRecord]:
        """Harvest every (source, query) pair, tag records with their
        query_family, optionally deduplicate."""
        all_records: list[HarvestRecord] = []
        for family_name, queries in query_families.items():
            for source in self.sources:
                t0 = time.time()
                for q in queries:
                    res = self._safe_search(source, q, per_query_cap)
                    for rec in res.records:
                        rec.query_family = family_name
                    all_records.extend(res.records)
                    LOG.info(
                        "[%s] family=%s query=%r got %d records (total avail %d)",
                        source.api_name, family_name, q,
                        len(res.records), res.n_total_available,
                    )
                LOG.info(
                    "[%s] family=%s done in %.1fs (cumulative %d records)",
                    source.api_name, family_name, time.time() - t0, len(all_records),
                )
        LOG.info("Total raw records across all sources: %d", len(all_records))

        if not deduplicate:
            return all_records
        deduped = self.deduplicator.deduplicate(all_records)
        return deduped

    @staticmethod
    def _safe_search(source: HarvestSource, query: str, cap: int) -> SourceResult:
        try:
            return source.search(query, per_query_cap=cap)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("[%s] search failed for %r: %s", source.api_name, query, exc)
            return SourceResult([], source.api_name, query, error=str(exc))

    @staticmethod
    def records_to_dataframe(records: Iterable[HarvestRecord]) -> "pd.DataFrame":
        """Flatten records to a CSV-shaped DataFrame."""
        return pd.DataFrame(rec.to_dict() for rec in records)
