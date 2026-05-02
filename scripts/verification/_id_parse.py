"""Identifier parsing for gold-hard record_ids.

Gold-hard record_id format: API_<source>_<encoded_id>
where encoded_id replaces certain DOI punctuation with underscores.

This module recovers canonical identifiers (DOI / PMID / OpenAlex ID /
EuropePMC PMC-ID) from the encoded record_id strings.

Recovery strategy
-----------------
We parse the record_id by:
  1. Stripping the leading "API_<source>_" prefix.
  2. Treating the remainder as a DOI in which '/' (the registrant/suffix
     separator) and '.' (intra-suffix punctuation) have been replaced
     with '_'. The DOI prefix always begins with '10', so we anchor on
     `10_xxxx_...` and rebuild the canonical form.

Because some DOIs legitimately contain underscores (e.g. ``10.1186/s12951-023-01776-8``
becomes ``10_1186_s12951_023_01776_8`` and the tail tokens are
ambiguous between '.' and '-'), we cannot deterministically recover
the exact ASCII separators from the encoding alone. We therefore
emit a small set of *canonicalisation candidates* and validate each
candidate against the source API. A candidate is the canonical
identifier in DOI form using the rule:

  * The first underscore (between '10' and the registrant) becomes '/'.
  * Subsequent underscores within the registrant prefix (e.g. '10/1186')
    become '.' until the registrant is closed.

Since DOI registrants follow the pattern '10.<digits>' (4-5 digits), we
detect the registrant by the second-token rule: the first underscore
that follows the registrant digit block becomes '/'. After that,
remaining underscores stay ambiguous between '.' and '-'. We emit
a small candidate set and let the caller validate against the source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedId:
    """Result of parsing a gold-hard record_id."""
    record_id: str
    source: str  # PubMed | OpenAlex | EuropePMC
    encoded_tail: str
    doi_candidates: list[str] = field(default_factory=list)
    primary_doi: Optional[str] = None  # most likely DOI
    pmid: Optional[str] = None
    openalex_id: Optional[str] = None
    europepmc_id: Optional[str] = None
    notes: str = ""


# DOI registrant: '10.<4-7 digits>' typically; we accept 4-7.
_REG_DIGITS = re.compile(r"^(\d{4,7})_")


def _doi_candidates_from_tail(tail: str) -> list[str]:
    """Generate DOI candidates from an encoded tail.

    Encoding rules used by the gold-hard record_ids:
      * '/' between DOI registrant and suffix becomes '_'
      * '.' within the registrant or suffix becomes '_'
      * '-' within the suffix becomes '_'

    So a tail like '10_1186_s12951_023_01776_8' may decode to:
      - 10.1186/s12951-023-01776-8  (most common pattern)
      - 10.1186/s12951.023.01776.8

    We generate candidates by:
      1. Anchoring '10_' as DOI prefix '10.'.
      2. Splitting the registrant block (digits after '10.').
      3. The next underscore becomes '/' (registrant -> suffix separator).
      4. For the remaining underscores in the suffix, we generate
         candidates with '-' replacements (the most common in modern
         DOIs) and a fallback with '.' replacements.
    """
    if not tail.startswith("10_"):
        return []

    rest = tail[len("10_"):]
    m = _REG_DIGITS.match(rest)
    if not m:
        return []
    registrant = m.group(1)
    suffix_encoded = rest[m.end():]
    if not suffix_encoded:
        return []

    # Common modern DOI suffix uses '-' between version-like fields.
    # But '.' is also common (e.g. '10.1021/acs.biomac.5b01003').
    # Generate two candidates: all '-' and all '.'; also one mixed form.
    cand_dash = f"10.{registrant}/{suffix_encoded.replace('_', '-')}"
    cand_dot = f"10.{registrant}/{suffix_encoded.replace('_', '.')}"

    candidates = [cand_dash, cand_dot]

    # Heuristic: if suffix begins with a token like 'acs', 'acsami',
    # 'acsptsci', 'acs_nanolett', etc. (ACS journals) then internal
    # separators are '.'. If it begins with 's' followed by digits and
    # date-like patterns (Springer Nature: s12951-023-01776-8) then
    # '-'. We keep both forms; validation chooses.
    return candidates


# Source slugs we know about
_SOURCES = ("PubMed", "OpenAlex", "EuropePMC")


def parse_record_id(record_id: str) -> ParsedId:
    """Parse a gold-hard record_id of the form `API_<source>_<encoded>`."""
    out = ParsedId(record_id=record_id, source="", encoded_tail="")
    if not isinstance(record_id, str):
        out.notes = "non-string record_id"
        return out
    if not record_id.startswith("API_"):
        out.notes = "missing API_ prefix"
        return out

    rest = record_id[len("API_"):]
    src = next((s for s in _SOURCES if rest.startswith(s + "_")), None)
    if not src:
        out.notes = f"unknown source slug; rest={rest[:30]!r}"
        return out
    out.source = src
    tail = rest[len(src) + 1:]
    out.encoded_tail = tail

    cands = _doi_candidates_from_tail(tail)
    out.doi_candidates = cands
    if cands:
        out.primary_doi = cands[0]

    # Source-specific id placeholders. We only get DOIs from record_ids;
    # PMID / OpenAlex IDs / PMC IDs are looked up via DOI on the API side.
    return out


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Lowercase and strip URL prefixes so DOIs match across sources."""
    if not isinstance(doi, str) or not doi:
        return None
    s = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "https://dx.doi.org/", "http://dx.doi.org/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.strip() or None


def normalize_title(title: Optional[str]) -> str:
    """Lowercase, strip punctuation, collapse whitespace for title match."""
    if not isinstance(title, str):
        return ""
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
