"""B1: Regex baseline (stub for D1).

Pattern-matches numeric fields directly in the abstract. Non-numeric fields
default to ``NOT_REPORTED`` because regex over abstracts is unreliable for
free-text payload / release-profile cells.

This file ships the SCAFFOLD with one working pattern per numeric field;
D1 work refines and tunes patterns on the dev split. The structure is:

    PATTERNS: dict[field_name, list[(regex, value_group, unit_group)]]

so adding a pattern is one line in PATTERNS, no method changes required.

Example:
    >>> bl = RegexBaseline()
    >>> bl.predict_record("ORG003", "Particles 200 nm in diameter, zeta -12 mV.")
    {'size': FieldPrediction(value='200', unit='nm', ...), ...}
"""

from __future__ import annotations

import re
from typing import Mapping

from nanobubbleval.baselines.base import Baseline, FieldPrediction
from nanobubbleval.schema import HEADLINE_FIELDS, NUMERIC_FIELDS


# (regex, value_group, unit_group). Patterns search anywhere in the abstract;
# the first match wins. Tune on dev split; ship the locked set for test.
PATTERNS: dict[str, list[tuple[re.Pattern, int, int]]] = {
    "size": [
        # "200 nm", "200.5 nm", "200 +/- 22 nm", "0.5 um"
        (re.compile(r"(\d+(?:\.\d+)?)\s*(?:[±\+\-/]+\s*\d+(?:\.\d+)?\s*)?(nm|um|μm|micrometer|micron)\b", re.I), 1, 2),
    ],
    "zeta_potential": [
        # "zeta potential of -12.5 mV", "-12 mV", "+ 25 mV"
        (re.compile(r"zeta\s*(?:potential)?[^\d\-+]{0,20}([+\-]?\s*\d+(?:\.\d+)?)\s*(mV|V)\b", re.I), 1, 2),
    ],
    "stability": [
        # "stable for 7 days", "stability of 48 h"
        (re.compile(r"(?:stable\s*for|stability\s*(?:of|over)?)\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|d|day|days|wk|week|weeks|min|minute|minutes)\b", re.I), 1, 2),
    ],
    "loading_efficiency": [
        # "encapsulation efficiency of 80%", "loading efficiency 72.4 %"
        (re.compile(r"(?:loading|encapsulation|drug\s*loading)\s*(?:efficiency)?[^\d]{0,15}(\d+(?:\.\d+)?)\s*(%)", re.I), 1, 2),
    ],
}


class RegexBaseline(Baseline):
    """B1: hand-written regular expressions for numeric headline fields.

    Non-numeric fields (``payload``, ``release_profile``) always return
    ``NOT_REPORTED`` -- this is intentional: regex over abstracts is too
    noisy for free-text fields.
    """

    name = "regex-v1"

    def __init__(self, patterns: dict | None = None) -> None:
        self._patterns = patterns or PATTERNS

    def predict_record(
        self, record_id: str, abstract: str,
    ) -> Mapping[str, FieldPrediction]:
        out: dict[str, FieldPrediction] = {}
        for f in HEADLINE_FIELDS:
            if f not in NUMERIC_FIELDS:
                out[f] = FieldPrediction.nr()
                continue
            out[f] = self._match_first(f, abstract)
        return out

    def _match_first(self, field: str, abstract: str) -> FieldPrediction:
        for pat, v_group, u_group in self._patterns.get(field, []):
            m = pat.search(abstract or "")
            if not m:
                continue
            value = re.sub(r"\s+", "", m.group(v_group))
            unit = m.group(u_group)
            evidence = m.group(0).strip()
            return FieldPrediction(value=value, unit=unit, evidence_quote=evidence)
        return FieldPrediction.nr()
