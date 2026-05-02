"""Direct identifier-lookup helpers against PubMed, OpenAlex, EuropePMC.

All calls are read-only and cite the canonical identifier from the
gold-hard record_id; we never search by query terms here.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Optional
from xml.etree import ElementTree as ET

LOG = logging.getLogger(__name__)

USER_AGENT = "NanoBubbleEval-Verification/1.0 (research; contact: anonymous)"
DEFAULT_TIMEOUT = 20


def _http_get(url: str, accept: str = "application/json") -> Optional[bytes]:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": accept,
    })
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return resp.read()
    except Exception as exc:
        LOG.debug("GET %s failed: %s", url, exc)
        return None


def openalex_by_doi(doi: str) -> Optional[dict]:
    """OpenAlex /works/doi:<doi>. Returns the work dict or None."""
    if not doi:
        return None
    url = f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}"
    data = _http_get(url, accept="application/json")
    if not data:
        return None
    try:
        obj = json.loads(data)
        if isinstance(obj, dict) and obj.get("id"):
            return obj
    except Exception as exc:
        LOG.debug("OpenAlex parse failed for %s: %s", doi, exc)
    return None


def _reconstruct_abstract(inverted: dict) -> str:
    """OpenAlex returns abstracts as inverted index. Reconstruct flat text."""
    if not isinstance(inverted, dict) or not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def openalex_extract(work: dict) -> dict:
    """Pull the fields we care about from an OpenAlex work."""
    if not isinstance(work, dict):
        return {}
    pl = work.get("primary_location") or {}
    src = (pl.get("source") or {}) if isinstance(pl, dict) else {}
    doi = work.get("doi") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index") or {})
    return {
        "openalex_id": (work.get("id") or "").split("/")[-1] or None,
        "doi": doi or None,
        "title": work.get("title") or work.get("display_name") or "",
        "year": work.get("publication_year"),
        "journal_or_venue": src.get("display_name") if isinstance(src, dict) else None,
        "abstract_or_summary": abstract,
        "document_type": work.get("type") or None,
        "url": (pl.get("landing_page_url") if isinstance(pl, dict) else None) or None,
    }


def pubmed_idconv_doi_to_pmid(doi: str) -> Optional[str]:
    """NCBI ID converter: DOI -> PMID."""
    if not doi:
        return None
    url = (
        "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?"
        f"ids={urllib.parse.quote(doi)}&format=json&tool=nanobubbleeval&email=anonymous@example.org"
    )
    data = _http_get(url)
    if not data:
        return None
    try:
        obj = json.loads(data)
        for rec in obj.get("records", []) or []:
            pmid = rec.get("pmid")
            if pmid:
                return str(pmid)
    except Exception as exc:
        LOG.debug("idconv parse failed for %s: %s", doi, exc)
    return None


def pubmed_esearch_doi(doi: str) -> Optional[str]:
    """E-utilities esearch: DOI -> PMID via [DOI] field."""
    if not doi:
        return None
    term = f"{doi}[DOI]"
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        f"db=pubmed&term={urllib.parse.quote(term)}&retmode=json"
    )
    data = _http_get(url)
    if not data:
        return None
    try:
        obj = json.loads(data)
        ids = (obj.get("esearchresult") or {}).get("idlist") or []
        if ids:
            return str(ids[0])
    except Exception as exc:
        LOG.debug("esearch parse failed for %s: %s", doi, exc)
    return None


def pubmed_efetch(pmid: str) -> Optional[dict]:
    """E-utilities efetch (XML) -> normalised dict."""
    if not pmid:
        return None
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
        f"db=pubmed&id={pmid}&retmode=xml"
    )
    data = _http_get(url, accept="application/xml")
    if not data:
        return None
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        LOG.debug("efetch XML parse failed for %s: %s", pmid, exc)
        return None
    art = root.find(".//PubmedArticle")
    if art is None:
        return None
    title_el = art.find(".//ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""
    abst_parts: list[str] = []
    for ab in art.findall(".//Abstract/AbstractText"):
        label = ab.attrib.get("Label")
        text = "".join(ab.itertext()).strip()
        if label and text:
            abst_parts.append(f"{label}: {text}")
        elif text:
            abst_parts.append(text)
    abstract = " ".join(abst_parts).strip()
    journal = art.findtext(".//Journal/Title") or art.findtext(".//Journal/ISOAbbreviation") or ""
    year = art.findtext(".//Journal/JournalIssue/PubDate/Year") or ""
    doi = ""
    for aid in art.findall(".//ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            doi = (aid.text or "").strip()
            break
    return {
        "pmid": pmid,
        "doi": doi or None,
        "title": title,
        "abstract_or_summary": abstract,
        "year": int(year) if year.isdigit() else None,
        "journal_or_venue": journal or None,
        "document_type": "Journal Article",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def europepmc_by_doi(doi: str) -> Optional[dict]:
    """EuropePMC search by DOI."""
    if not doi:
        return None
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
        f"query=DOI:%22{urllib.parse.quote(doi)}%22&format=json&resultType=core"
    )
    data = _http_get(url)
    if not data:
        return None
    try:
        obj = json.loads(data)
        hits = ((obj.get("resultList") or {}).get("result") or [])
        if not hits:
            return None
        r = hits[0]
        return {
            "europepmc_id": r.get("id"),
            "pmid": r.get("pmid"),
            "pmcid": r.get("pmcid"),
            "doi": (r.get("doi") or doi).lower() if r.get("doi") else doi.lower(),
            "title": r.get("title") or "",
            "abstract_or_summary": r.get("abstractText") or "",
            "year": int(r.get("pubYear")) if str(r.get("pubYear", "")).isdigit() else None,
            "journal_or_venue": r.get("journalTitle"),
            "document_type": r.get("pubType") or "Journal Article",
            "url": (r.get("fullTextUrlList") or {}).get("fullTextUrl", [{}])[0].get("url") if isinstance(r.get("fullTextUrlList"), dict) else None,
        }
    except Exception as exc:
        LOG.debug("europepmc parse failed for %s: %s", doi, exc)
    return None


def polite_sleep(seconds: float = 0.34) -> None:
    """NCBI rate limit: 3 req/s without API key. We're conservative."""
    time.sleep(seconds)
