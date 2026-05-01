"""Shared pytest fixtures."""

from __future__ import annotations

import pandas as pd
import pytest

from nanobubbleval.frames import AnnotationFrame
from nanobubbleval.schema import HEADLINE_FIELDS, NR


def _empty_row(rid: str) -> dict:
    row = {"record_id": rid, "ambiguity_flag": "", "annotator_notes": ""}
    for f in HEADLINE_FIELDS:
        for s in ("value", "unit", "evidence_quote"):
            row[f"{f}_{s}"] = NR
    return row


@pytest.fixture
def gold_frame() -> AnnotationFrame:
    """Fixture: 6 gold-labelled records with mixed emit/NR cells."""
    rows = []
    r = _empty_row("r1")
    r.update({
        "size_value": "200", "size_unit": "nm",
        "size_evidence_quote": "200 nm particles",
        "zeta_potential_value": "-12.5", "zeta_potential_unit": "mV",
        "zeta_potential_evidence_quote": "zeta -12.5 mV",
        "payload_value": "doxorubicin", "payload_unit": "",
        "payload_evidence_quote": "loaded with doxorubicin",
        "loading_efficiency_value": "80", "loading_efficiency_unit": "%",
        "loading_efficiency_evidence_quote": "80% encapsulation",
    })
    rows.append(r)

    r = _empty_row("r2")
    r.update({
        "size_value": "500", "size_unit": "nm",
        "size_evidence_quote": "diameter 500 nm",
        "stability_value": "48", "stability_unit": "h",
        "stability_evidence_quote": "stable for 48 h",
    })
    rows.append(r)

    rows.append(_empty_row("r3"))  # all NR

    r = _empty_row("r4")
    r.update({
        "size_value": "0.5", "size_unit": "um",
        "size_evidence_quote": "0.5 um diameter",
        "loading_efficiency_value": "0.72", "loading_efficiency_unit": "",
        "loading_efficiency_evidence_quote": "loading 0.72",
        "payload_value": "paclitaxel", "payload_unit": "",
        "payload_evidence_quote": "paclitaxel-loaded",
    })
    rows.append(r)

    r = _empty_row("r5")
    r.update({
        "size_value": "180", "size_unit": "nm",
        "size_evidence_quote": "180 nm",
        "release_profile_value": "sustained 72 h",
        "release_profile_evidence_quote": "sustained release over 72 h",
    })
    rows.append(r)

    rows.append(_empty_row("r6"))  # all NR

    return AnnotationFrame(pd.DataFrame(rows))


@pytest.fixture
def pred_good_frame(gold_frame) -> AnnotationFrame:
    """A near-perfect extractor: matches gold, with one numeric drift on r1
    (200 -> 205 nm, within 5% tolerance)."""
    df = gold_frame.df.copy()
    df.loc[df["record_id"] == "r1", "size_value"] = "205"
    df.loc[df["record_id"] == "r4", "size_value"] = "500"
    df.loc[df["record_id"] == "r4", "size_unit"] = "nm"
    df.loc[df["record_id"] == "r4", "loading_efficiency_value"] = "72"
    df.loc[df["record_id"] == "r4", "loading_efficiency_unit"] = "%"
    return AnnotationFrame(df)


@pytest.fixture
def pred_hallucinator_frame(gold_frame) -> AnnotationFrame:
    """A 'never-abstain' hallucinator: same as gold for emit cells, but every
    NR cell is replaced by a fabricated value."""
    df = gold_frame.df.copy()
    fab = {
        "size": ("100", "nm", "guessed"),
        "zeta_potential": ("-20", "mV", "guessed"),
        "stability": ("24", "h", "guessed"),
        "payload": ("drug", "", "guessed"),
        "loading_efficiency": ("70", "%", "guessed"),
        "release_profile": ("sustained", "", "guessed"),
    }
    for f, (v, u, e) in fab.items():
        mask = df[f"{f}_value"].astype(str).str.upper() == NR
        df.loc[mask, f"{f}_value"] = v
        df.loc[mask, f"{f}_unit"] = u
        df.loc[mask, f"{f}_evidence_quote"] = e
    return AnnotationFrame(df)
