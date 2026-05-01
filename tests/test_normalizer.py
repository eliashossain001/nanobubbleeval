"""Unit tests for UnitNormalizer."""

from __future__ import annotations

import pytest

from nanobubbleval.schema import UnitNormalizer


@pytest.fixture
def norm() -> UnitNormalizer:
    return UnitNormalizer()


@pytest.mark.parametrize("v, expected", [
    ("200", 200.0),
    ("200.5", 200.5),
    ("-12.5", -12.5),
    ("approximately 200", 200.0),
    ("~150", 150.0),
    ("1.5e-3", 1.5e-3),
    ("NOT_REPORTED", None),
    ("", None),
    (None, None),
    ("150-250", None),       # range -> reject
    ("<200", None),          # bound -> reject
    (">10", None),
])
def test_parse_number(norm, v, expected):
    got = norm.parse_number(v)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected)


@pytest.mark.parametrize("v, u, field, expected", [
    ("200", "nm", "size", 200.0),
    ("0.5", "um", "size", 500.0),
    ("0.5", "μm", "size", 500.0),
    ("0.5", "micrometer", "size", 500.0),
    ("1", "mm", "size", 1e6),
    ("-12.5", "mV", "zeta_potential", -12.5),
    ("0.5", "V", "zeta_potential", 500.0),
    ("48", "h", "stability", 48.0),
    ("2", "days", "stability", 48.0),
    ("3", "weeks", "stability", 504.0),
    ("0.72", "", "loading_efficiency", 72.0),       # fraction auto-detect
    ("72", "%", "loading_efficiency", 72.0),
    ("NOT_REPORTED", "nm", "size", None),
    ("200", "parsec", "size", None),                # bad unit
])
def test_to_canonical(norm, v, u, field, expected):
    got, _ = norm.to_canonical(v, u, field)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected)


def test_is_nr(norm):
    assert norm.is_nr("NOT_REPORTED")
    assert norm.is_nr("")
    assert norm.is_nr(None)
    assert not norm.is_nr("200")
    assert not norm.is_nr("doxorubicin")


def test_canonicalise_text(norm):
    assert norm.canonicalise_text("  Lots of   Whitespace  ") == "lots of whitespace"
    assert norm.canonicalise_text("NOT_REPORTED") == "NOT_REPORTED"
