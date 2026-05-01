"""Harvest base classes.

Every source-specific harvester (PubMed, OpenAlex, ...) subclasses
:class:`HarvestSource`, declares its ``api_name``, and implements
:meth:`HarvestSource.search`. The orchestrator iterates a query-family
table over each source and collects the results.

Records are produced as :class:`HarvestRecord` value objects so that the
deduplicator and downstream curation stages do not need to know which API
emitted a particular record.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass
class HarvestRecord:
    """One harvested record from a public scholarly API.

    Fields are nullable because not every source returns every key; the
    deduplicator reconciles across sources by DOI > PMID > title > URL.
    """

    record_id: str                    # synthetic id, ``<api>_<source_id>``
    source_api: str                   # PubMed / OpenAlex / EuropePMC / ...
    source_id: str                    # API-native id (PMID, OpenAlex W-id, DOI)
    title: str = ""
    authors: str = ""                 # semicolon-separated
    year: Optional[int] = None
    journal_or_venue: str = ""
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    url: Optional[str] = None
    abstract_or_summary: str = ""
    citation_count: Optional[int] = None
    document_type: str = "original"   # original | review | clinical_trial
    query_family: str = ""            # populated by the orchestrator
    raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        """Flat dict for CSV export. The ``raw`` blob is dropped."""
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "raw"}  # noqa: PLC0206
        return d


@dataclass
class SourceResult:
    """Bundle returned by a single :meth:`HarvestSource.search` call.

    Attributes
    ----------
    records:
        The harvested records.
    api_name:
        Name of the source.
    query:
        The exact query string issued.
    n_total_available:
        Total hits the API reports (may exceed ``len(records)`` if capped).
    rate_limited:
        True if the source applied rate-limiting and we backed off.
    error:
        Non-None if the search failed; the orchestrator logs and continues.
    """

    records: List[HarvestRecord]
    api_name: str
    query: str
    n_total_available: int = 0
    rate_limited: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Abstract source
# ---------------------------------------------------------------------------

class HarvestSource(ABC):
    """Abstract harvest source.

    Subclasses must:
      * set the class attribute ``api_name`` (e.g., ``"PubMed"``).
      * implement :meth:`search`, returning a :class:`SourceResult`.

    Subclasses should:
      * accept a ``per_query_cap`` constructor argument that limits the
        records returned per individual search.
      * apply backoff and retry on transient HTTP errors.
      * emit one log line on entry/exit so the orchestrator's progress
        is visible.
    """

    api_name: str = "abstract"

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.api_name == "abstract":
            raise TypeError(f"{cls.__name__} must override class attribute `api_name`")

    @abstractmethod
    def search(self, query: str, *, per_query_cap: int = 200) -> SourceResult:
        """Run a single search query. Must always return a SourceResult,
        even on error (with ``error`` set and an empty record list)."""
        raise NotImplementedError

    def search_many(
        self, queries: Iterable[str], *, per_query_cap: int = 200,
    ) -> List[SourceResult]:
        """Default: serially call :meth:`search` for each query."""
        out: List[SourceResult] = []
        for q in queries:
            LOG.info("[%s] searching %r", self.api_name, q)
            try:
                res = self.search(q, per_query_cap=per_query_cap)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("[%s] %r raised %s", self.api_name, q, exc)
                res = SourceResult(records=[], api_name=self.api_name,
                                   query=q, error=str(exc))
            out.append(res)
        return out
