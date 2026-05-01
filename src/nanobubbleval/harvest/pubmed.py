"""PubMed harvester via NCBI E-utilities.

Uses the unauthenticated E-utils JSON endpoints
(``esearch.fcgi`` -> ``efetch.fcgi``). The implementation respects NCBI's
3-requests-per-second rate limit and includes a polite retry policy on
transient HTTP errors.

Reference: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from xml.etree import ElementTree as ET

from nanobubbleval.harvest.base import HarvestRecord, HarvestSource, SourceResult

LOG = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI rate limit (unauthenticated): 3 req/s
MIN_DELAY_S = 0.34


class PubMedSource(HarvestSource):
    api_name = "PubMed"

    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        api_key: Optional[str] = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.api_key = api_key
        self._last_request_t = 0.0

    # ----------------------------------------------------------- HTTP helpers

    def _wait_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        dt = time.time() - self._last_request_t
        if dt < MIN_DELAY_S:
            time.sleep(MIN_DELAY_S - dt)
        self._last_request_t = time.time()

    def _get(self, url: str, params: dict) -> Optional[requests.Response]:
        if self.api_key:
            params = {**params, "api_key": self.api_key}
        for attempt in range(1, self.max_retries + 1):
            self._wait_rate_limit()
            try:
                r = requests.get(url, params=params, timeout=self.timeout_s)
                if r.status_code == 200:
                    return r
                if r.status_code in (429, 500, 502, 503, 504):
                    LOG.warning("[%s] HTTP %d on attempt %d/%d, backing off",
                                self.api_name, r.status_code, attempt, self.max_retries)
                    time.sleep(2 ** attempt)
                    continue
                LOG.warning("[%s] HTTP %d (no retry)", self.api_name, r.status_code)
                return None
            except requests.exceptions.RequestException as exc:
                LOG.warning("[%s] %s on attempt %d/%d", self.api_name, exc, attempt, self.max_retries)
                time.sleep(2 ** attempt)
        return None

    # ---------------------------------------------------------------- search

    def search(self, query: str, *, per_query_cap: int = 200) -> SourceResult:
        # 1. esearch -> list of PMIDs
        params = {
            "db": "pubmed", "term": query,
            "retmax": str(per_query_cap), "retmode": "json",
        }
        r = self._get(ESEARCH_URL, params)
        if r is None:
            return SourceResult([], self.api_name, query, error="esearch failed")
        try:
            payload = r.json()
        except ValueError:
            return SourceResult([], self.api_name, query, error="esearch non-JSON")
        esr = payload.get("esearchresult", {})
        pmids = esr.get("idlist", [])
        n_total = int(esr.get("count", 0)) if esr.get("count") else len(pmids)
        if not pmids:
            return SourceResult([], self.api_name, query, n_total_available=n_total)

        # 2. efetch -> XML with abstracts and metadata
        records = self._fetch_records(pmids)
        return SourceResult(records, self.api_name, query, n_total_available=n_total)

    def _fetch_records(self, pmids) -> list:
        params = {
            "db": "pubmed", "id": ",".join(pmids),
            "retmode": "xml", "rettype": "abstract",
        }
        r = self._get(EFETCH_URL, params)
        if r is None:
            return []
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as exc:
            LOG.warning("[%s] XML parse error: %s", self.api_name, exc)
            return []
        records = []
        for article in root.findall(".//PubmedArticle"):
            try:
                records.append(self._parse_article(article))
            except Exception as exc:  # noqa: BLE001
                LOG.warning("[%s] failed to parse one article: %s", self.api_name, exc)
        return records

    # ------------------------------------------------------------ XML parser

    @staticmethod
    def _text(node, path: str, default: str = "") -> str:
        if node is None:
            return default
        n = node.find(path)
        return (n.text or "").strip() if n is not None and n.text else default

    def _parse_article(self, article) -> HarvestRecord:
        article_node = article.find(".//Article")

        pmid = self._text(article, ".//PMID")
        title = self._text(article_node, ".//ArticleTitle")

        abstract_parts = []
        for ab_text in article_node.findall(".//Abstract/AbstractText"):
            label = ab_text.attrib.get("Label", "")
            piece = (ab_text.text or "").strip()
            abstract_parts.append(f"{label}: {piece}" if label else piece)
        abstract = " ".join(p for p in abstract_parts if p).strip()

        year_str = self._text(article, ".//PubDate/Year") or self._text(article, ".//PubDate/MedlineDate")
        year = None
        if year_str:
            for tok in year_str.split():
                if tok.isdigit() and 1900 <= int(tok) <= 2100:
                    year = int(tok); break

        journal = self._text(article_node, ".//Journal/Title")

        # Authors
        authors = []
        for au in article_node.findall(".//AuthorList/Author"):
            last = self._text(au, "LastName")
            first = self._text(au, "ForeName") or self._text(au, "Initials")
            if last:
                authors.append(f"{first} {last}".strip())
        authors_str = "; ".join(authors)

        # DOI / PMCID
        doi = pmcid = None
        for aid in article.findall(".//ArticleId"):
            t = aid.attrib.get("IdType", "")
            v = (aid.text or "").strip()
            if t == "doi": doi = v
            elif t == "pmc": pmcid = v

        # Document type
        doc_type = "original"
        for pt in article_node.findall(".//PublicationType"):
            pt_text = (pt.text or "").lower()
            if "review" in pt_text:
                doc_type = "review"; break

        return HarvestRecord(
            record_id=f"PubMed_{pmid}",
            source_api=self.api_name,
            source_id=pmid,
            title=title,
            authors=authors_str,
            year=year,
            journal_or_venue=journal,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            abstract_or_summary=abstract,
            document_type=doc_type,
        )
