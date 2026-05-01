"""Unit tests for the harvest subpackage. Network is NOT exercised here;
we only test pure logic (deduplicator, abstract reconstruction,
HarvestRecord dataclass, ABC enforcement)."""

from __future__ import annotations

import pytest

from nanobubbleval.harvest import (
    Deduplicator, HarvestRecord, HarvestSource, OpenAlexSource, PubMedSource,
    QUERY_FAMILIES,
)
from nanobubbleval.harvest.openalex import _abstract_from_inverted_index
from nanobubbleval.harvest.deduplicator import _norm_title, _is_richer


def _rec(**kwargs) -> HarvestRecord:
    base = dict(record_id="x", source_api="X", source_id="x")
    base.update(kwargs)
    return HarvestRecord(**base)


# --- HarvestRecord ----------------------------------------------------------

def test_harvest_record_to_dict_drops_raw():
    r = _rec(title="t", raw={"big": "blob"})
    d = r.to_dict()
    assert "raw" not in d
    assert d["title"] == "t"


def test_harvest_record_default_doc_type():
    assert _rec().document_type == "original"


# --- HarvestSource ABC ------------------------------------------------------

def test_subclass_must_set_api_name():
    with pytest.raises(TypeError):
        class Bad(HarvestSource):
            def search(self, q, *, per_query_cap=200):
                return None


def test_pubmed_and_openalex_have_api_names():
    assert PubMedSource().api_name == "PubMed"
    assert OpenAlexSource().api_name == "OpenAlex"


# --- Deduplicator -----------------------------------------------------------

def test_dedup_doi():
    d = Deduplicator()
    a = _rec(record_id="a", doi="10.1/X", title="A")
    b = _rec(record_id="b", doi="10.1/X", title="B", abstract_or_summary="long abstract")
    out = d.deduplicate([a, b])
    assert len(out) == 1
    # b is richer (longer abstract) so should win
    assert out[0].abstract_or_summary == "long abstract"


def test_dedup_pmid():
    d = Deduplicator()
    a = _rec(record_id="a", pmid="123", title="A")
    b = _rec(record_id="b", pmid="123", title="B")
    assert len(d.deduplicate([a, b])) == 1


def test_dedup_normalised_title():
    d = Deduplicator()
    a = _rec(record_id="a", title="Some Title!")
    b = _rec(record_id="b", title="some title")
    assert len(d.deduplicate([a, b])) == 1


def test_dedup_keeps_distinct_records():
    d = Deduplicator()
    a = _rec(record_id="a", doi="10.1/A", title="A")
    b = _rec(record_id="b", doi="10.1/B", title="B")
    assert len(d.deduplicate([a, b])) == 2


def test_norm_title_lowercases_strips_punct():
    assert _norm_title("Some Title!") == "some title"
    assert _norm_title("  Multi   spaces  ") == "multi spaces"


def test_is_richer_prefers_doi_and_abstract():
    a = _rec(doi="10.1/X")
    b = _rec()
    assert _is_richer(a, b)
    assert not _is_richer(b, a)


# --- OpenAlex helpers ------------------------------------------------------

def test_abstract_from_inverted_index_reconstructs_order():
    idx = {"hello": [0], "world": [1], "again": [2]}
    assert _abstract_from_inverted_index(idx) == "hello world again"


def test_abstract_from_inverted_index_handles_repeats():
    idx = {"a": [0, 2], "b": [1]}
    assert _abstract_from_inverted_index(idx) == "a b a"


def test_abstract_from_inverted_index_empty():
    assert _abstract_from_inverted_index({}) == ""


# --- Query families --------------------------------------------------------

def test_query_families_have_five_clusters():
    assert len(QUERY_FAMILIES) == 5


def test_query_families_nonempty():
    for name, qs in QUERY_FAMILIES.items():
        assert len(qs) > 0, f"family {name} has no queries"
