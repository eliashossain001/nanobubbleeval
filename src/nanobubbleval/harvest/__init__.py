"""Harvest subpackage: API-first reconstruction of the warehouse from
public scholarly sources.

Public API
----------
    HarvestRecord       value object: one harvested record (DOI, PMID, title,
                        abstract, year, source_api, etc.)
    HarvestSource       abstract base for source-specific harvesters
    PubMedSource        E-utils-backed PubMed harvester
    OpenAlexSource      OpenAlex API harvester
    EuropePMCSource     Europe PMC harvester
    CrossRefSource      CrossRef harvester
    ClinicalTrialsSource  ClinicalTrials.gov v2 harvester
    HarvestOrchestrator drives all sources across all query families
    Deduplicator        DOI > PMID > title > URL deduplication

The query families themselves live in ``QUERY_FAMILIES`` (a dict of family
name to list of search terms) and mirror the v1.0 schema in the paper's
Appendix A.
"""

from nanobubbleval.harvest.base import (
    HarvestRecord,
    HarvestSource,
    SourceResult,
)
from nanobubbleval.harvest.deduplicator import Deduplicator
from nanobubbleval.harvest.orchestrator import (
    HarvestOrchestrator,
    QUERY_FAMILIES,
)
from nanobubbleval.harvest.pubmed import PubMedSource
from nanobubbleval.harvest.openalex import OpenAlexSource

__all__ = [
    "Deduplicator",
    "HarvestOrchestrator",
    "HarvestRecord",
    "HarvestSource",
    "OpenAlexSource",
    "PubMedSource",
    "QUERY_FAMILIES",
    "SourceResult",
]
