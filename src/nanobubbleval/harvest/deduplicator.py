"""Deduplication of harvested records.

Order: DOI > PMID/PMCID > normalised title > URL. Duplicates are merged,
preferring fields from the source with richer metadata (longer abstract,
non-null DOI / PMID).

Title normalisation lowercases, removes punctuation, and collapses
whitespace.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, List

from nanobubbleval.harvest.base import HarvestRecord

LOG = logging.getLogger(__name__)

_PUNCT = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def _norm_title(t: str) -> str:
    t = (t or "").lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def _is_richer(a: HarvestRecord, b: HarvestRecord) -> bool:
    """Return True if record A is 'richer' than B and should be preferred."""
    a_score = (
        bool(a.doi), bool(a.pmid), bool(a.pmcid),
        len(a.abstract_or_summary or ""), len(a.title or ""),
    )
    b_score = (
        bool(b.doi), bool(b.pmid), bool(b.pmcid),
        len(b.abstract_or_summary or ""), len(b.title or ""),
    )
    return a_score >= b_score


class Deduplicator:
    """Merge duplicates across sources following the v1.0 dedup order."""

    def deduplicate(self, records: Iterable[HarvestRecord]) -> List[HarvestRecord]:
        seen_doi = {}
        seen_pmid = {}
        seen_pmcid = {}
        seen_title = {}
        seen_url = {}

        kept: list[HarvestRecord] = []

        def _replace_if_richer(idx: int, new: HarvestRecord) -> None:
            old = kept[idx]
            if _is_richer(new, old):
                kept[idx] = new

        for rec in records:
            # 1. DOI
            if rec.doi:
                key = rec.doi.lower().strip()
                if key in seen_doi:
                    _replace_if_richer(seen_doi[key], rec); continue
            # 2. PMID / PMCID
            if rec.pmid:
                k = rec.pmid.strip()
                if k in seen_pmid:
                    _replace_if_richer(seen_pmid[k], rec); continue
            if rec.pmcid:
                k = rec.pmcid.strip()
                if k in seen_pmcid:
                    _replace_if_richer(seen_pmcid[k], rec); continue
            # 3. Normalised title
            nt = _norm_title(rec.title)
            if nt and nt in seen_title:
                _replace_if_richer(seen_title[nt], rec); continue
            # 4. URL
            if rec.url:
                u = rec.url.strip().lower()
                if u in seen_url:
                    _replace_if_richer(seen_url[u], rec); continue

            # Not seen: keep it
            idx = len(kept)
            kept.append(rec)
            if rec.doi: seen_doi[rec.doi.lower().strip()] = idx
            if rec.pmid: seen_pmid[rec.pmid.strip()] = idx
            if rec.pmcid: seen_pmcid[rec.pmcid.strip()] = idx
            if nt: seen_title[nt] = idx
            if rec.url: seen_url[rec.url.strip().lower()] = idx

        n_in = sum(1 for _ in records) if not isinstance(records, list) else len(records)
        LOG.info("Deduplicated %d -> %d (kept %.1f%%)",
                 n_in, len(kept),
                 100 * len(kept) / max(1, n_in))
        return kept
