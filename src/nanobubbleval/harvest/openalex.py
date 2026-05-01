"""OpenAlex harvester.

OpenAlex provides a free, unauthenticated REST API
(https://docs.openalex.org/). We page through results and reconstruct
abstracts from the inverted-index field that OpenAlex returns in lieu of
plaintext.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from nanobubbleval.harvest.base import HarvestRecord, HarvestSource, SourceResult

LOG = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"
PAGE_SIZE = 100              # OpenAlex max per-page
MIN_DELAY_S = 0.10           # OpenAlex polite-pool rate is ~10 req/s


def _abstract_from_inverted_index(idx: dict) -> str:
    """OpenAlex returns abstract as ``{token: [pos1, pos2, ...]}``;
    reconstruct the linear text."""
    if not idx:
        return ""
    positions = []
    for tok, ps in idx.items():
        for p in ps:
            positions.append((p, tok))
    positions.sort()
    return " ".join(t for _, t in positions)


class OpenAlexSource(HarvestSource):
    api_name = "OpenAlex"

    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        mailto: Optional[str] = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        # The polite-pool email lifts rate limits to ~10 req/s; without it
        # we share the public pool. The mailto stays in HTTP headers only.
        self.mailto = mailto
        self._last_request_t = 0.0

    def _wait_rate_limit(self) -> None:
        dt = time.time() - self._last_request_t
        if dt < MIN_DELAY_S:
            time.sleep(MIN_DELAY_S - dt)
        self._last_request_t = time.time()

    def _get(self, url: str, params: dict) -> Optional[requests.Response]:
        if self.mailto:
            params = {**params, "mailto": self.mailto}
        for attempt in range(1, self.max_retries + 1):
            self._wait_rate_limit()
            try:
                r = requests.get(url, params=params, timeout=self.timeout_s)
                if r.status_code == 200:
                    return r
                if r.status_code in (429, 500, 502, 503, 504):
                    LOG.warning("[%s] HTTP %d, attempt %d/%d", self.api_name,
                                r.status_code, attempt, self.max_retries)
                    time.sleep(2 ** attempt)
                    continue
                LOG.warning("[%s] HTTP %d (no retry)", self.api_name, r.status_code)
                return None
            except requests.exceptions.RequestException as exc:
                LOG.warning("[%s] %s on attempt %d/%d", self.api_name, exc, attempt, self.max_retries)
                time.sleep(2 ** attempt)
        return None

    def search(self, query: str, *, per_query_cap: int = 200) -> SourceResult:
        records = []
        cursor = "*"
        n_total_available = 0
        while len(records) < per_query_cap:
            params = {
                "search": query,
                "per-page": str(min(PAGE_SIZE, per_query_cap - len(records))),
                "cursor": cursor,
            }
            r = self._get(OPENALEX_WORKS, params)
            if r is None:
                break
            payload = r.json()
            n_total_available = payload.get("meta", {}).get("count", 0)
            for w in payload.get("results", []):
                try:
                    records.append(self._parse_work(w))
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("[%s] failed to parse one work: %s", self.api_name, exc)
            cursor = payload.get("meta", {}).get("next_cursor")
            if not cursor:
                break
        return SourceResult(records, self.api_name, query,
                            n_total_available=n_total_available)

    def _parse_work(self, w: dict) -> HarvestRecord:
        oid = (w.get("id") or "").rsplit("/", 1)[-1]      # W-id
        doi = w.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]

        # Authors
        authorships = w.get("authorships") or []
        authors = "; ".join(
            (a.get("author") or {}).get("display_name", "")
            for a in authorships
            if (a.get("author") or {}).get("display_name")
        )

        # Document type
        type_ = (w.get("type") or "").lower()
        doc_type = "review" if type_ in ("review", "review-article") else "original"

        # Journal
        host = w.get("primary_location", {}).get("source", {}) or {}
        journal = host.get("display_name", "") or ""

        # Abstract from inverted index
        abstract = _abstract_from_inverted_index(w.get("abstract_inverted_index") or {})

        return HarvestRecord(
            record_id=f"OpenAlex_{oid}",
            source_api=self.api_name,
            source_id=oid,
            title=w.get("title") or w.get("display_name") or "",
            authors=authors,
            year=w.get("publication_year"),
            journal_or_venue=journal,
            doi=doi,
            pmid=(w.get("ids") or {}).get("pmid"),
            pmcid=(w.get("ids") or {}).get("pmcid"),
            url=w.get("doi") or w.get("id"),
            abstract_or_summary=abstract,
            citation_count=w.get("cited_by_count"),
            document_type=doc_type,
        )
