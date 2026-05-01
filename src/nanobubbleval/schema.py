"""Schema definitions and unit normalisation.

The headline schema covers six fields evaluated in NanoBubbleEval v1.0:
``size``, ``zeta_potential``, ``stability``, ``payload``,
``loading_efficiency``, ``release_profile``. Numeric fields carry a canonical
unit and a conversion table; text fields do not.

Public classes:
    FieldSpec       declarative description of one schema field
    UnitNormalizer  parses and canonicalises (value, unit) pairs

Module constants:
    HEADLINE_FIELDS  ordered list of field names reported in headline tables
    NUMERIC_FIELDS   subset of HEADLINE_FIELDS with a canonical unit
    TEXT_FIELDS      subset of HEADLINE_FIELDS that are free text
    NR               sentinel string for ``NOT_REPORTED``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional

NR: str = "NOT_REPORTED"

_NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")
_RANGE_PATTERN = re.compile(r"\d\s*[-–]\s*\d")
_BOUND_TOKENS = ("<", ">", "≤", "≥")


@dataclass(frozen=True)
class FieldSpec:
    """Declarative description of one schema field.

    Attributes:
        name: machine-readable field name
        is_numeric: True if the field has a canonical numeric unit
        canonical_unit: canonical unit symbol (numeric fields only)
        unit_table: synonym -> conversion factor to canonical unit
        description: human-readable description for guideline / paper use
    """

    name: str
    is_numeric: bool
    canonical_unit: Optional[str] = None
    unit_table: Mapping[str, float] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if self.is_numeric and not self.canonical_unit:
            raise ValueError(f"numeric field '{self.name}' must declare a canonical_unit")
        if not self.is_numeric and self.canonical_unit:
            raise ValueError(f"text field '{self.name}' must not declare a canonical_unit")


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

_SIZE_TABLE = {
    "nm": 1.0, "nanometer": 1.0, "nanometre": 1.0, "nanometers": 1.0, "nanometres": 1.0,
    "um": 1e3, "μm": 1e3, "micrometer": 1e3, "micrometre": 1e3,
    "micron": 1e3, "microns": 1e3,
    "mm": 1e6, "millimeter": 1e6, "millimetre": 1e6,
    "m": 1e9, "meter": 1e9, "metre": 1e9,
    "pm": 1e-3, "picometer": 1e-3, "picometre": 1e-3,
    "a": 0.1, "Å": 0.1, "angstrom": 0.1, "angstroms": 0.1,
}

_ZETA_TABLE = {
    "mv": 1.0, "millivolt": 1.0, "millivolts": 1.0,
    "v": 1e3, "volt": 1e3, "volts": 1e3,
}

_STABILITY_TABLE = {
    "h": 1.0, "hr": 1.0, "hrs": 1.0, "hour": 1.0, "hours": 1.0,
    "d": 24.0, "day": 24.0, "days": 24.0,
    "wk": 168.0, "week": 168.0, "weeks": 168.0,
    "mo": 730.0, "month": 730.0, "months": 730.0,
    "yr": 8760.0, "year": 8760.0, "years": 8760.0,
    "min": 1 / 60.0, "minute": 1 / 60.0, "minutes": 1 / 60.0,
    "s": 1 / 3600.0, "sec": 1 / 3600.0, "second": 1 / 3600.0, "seconds": 1 / 3600.0,
}

_LOADING_TABLE = {
    "%": 1.0, "percent": 1.0, "pct": 1.0,
}

FIELD_REGISTRY: dict[str, FieldSpec] = {
    "size": FieldSpec(
        name="size", is_numeric=True, canonical_unit="nm", unit_table=_SIZE_TABLE,
        description="Particle / bubble diameter or hydrodynamic size.",
    ),
    "zeta_potential": FieldSpec(
        name="zeta_potential", is_numeric=True, canonical_unit="mV", unit_table=_ZETA_TABLE,
        description="Surface charge.",
    ),
    "stability": FieldSpec(
        name="stability", is_numeric=True, canonical_unit="h", unit_table=_STABILITY_TABLE,
        description="Persistence, lifetime, or shelf-life duration.",
    ),
    "loading_efficiency": FieldSpec(
        name="loading_efficiency", is_numeric=True, canonical_unit="%", unit_table=_LOADING_TABLE,
        description="Encapsulation / loading percentage.",
    ),
    "payload": FieldSpec(
        name="payload", is_numeric=False,
        description="Drug, dye, gene, gas, or cargo loaded into the carrier.",
    ),
    "release_profile": FieldSpec(
        name="release_profile", is_numeric=False,
        description="Release behaviour described in text.",
    ),
}

HEADLINE_FIELDS: list[str] = [
    "size", "zeta_potential", "stability", "payload",
    "loading_efficiency", "release_profile",
]
NUMERIC_FIELDS: list[str] = [name for name, spec in FIELD_REGISTRY.items() if spec.is_numeric]
TEXT_FIELDS: list[str] = [name for name, spec in FIELD_REGISTRY.items() if not spec.is_numeric]


# ---------------------------------------------------------------------------
# UnitNormalizer
# ---------------------------------------------------------------------------

class UnitNormalizer:
    """Parses raw ``(value, unit)`` strings into canonical numeric form.

    Single instance is reusable across records and fields. Stateless w.r.t.
    inputs; thread-safe for read-only access.

    Example:
        >>> norm = UnitNormalizer()
        >>> norm.is_nr("NOT_REPORTED")
        True
        >>> norm.parse_number("approximately 200")
        200.0
        >>> norm.to_canonical("0.5", "um", "size")
        (500.0, 'nm')
    """

    NR = NR

    def __init__(self, registry: Mapping[str, FieldSpec] = FIELD_REGISTRY) -> None:
        self._registry = dict(registry)

    @staticmethod
    def is_nr(value: object) -> bool:
        """True when the cell is empty or marked as ``NOT_REPORTED``."""
        if value is None:
            return True
        s = str(value).strip()
        if not s:
            return True
        return s.upper() == NR

    @staticmethod
    def parse_number(value: object) -> Optional[float]:
        """Extract a single numeric value. Returns None for ranges, bounds,
        and unparseable input."""
        if UnitNormalizer.is_nr(value):
            return None
        s = str(value).strip()
        if not s:
            return None
        if any(tok in s for tok in _BOUND_TOKENS):
            return None
        if _RANGE_PATTERN.search(s):
            return None
        s = s.replace("−", "-").replace("±", " ").replace("+/-", " ")
        m = _NUMERIC_PATTERN.search(s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except ValueError:
            return None

    @staticmethod
    def normalise_unit_string(unit: object) -> str:
        if UnitNormalizer.is_nr(unit):
            return ""
        s = str(unit).strip().lower()
        return s.replace(" ", "").replace("·", "").replace(".", "")

    def to_canonical(
        self, value: object, unit: object, field_name: str,
    ) -> tuple[Optional[float], Optional[str]]:
        """Map ``(value, unit)`` to ``(canonical_value, canonical_unit)``.

        Returns ``(None, None)`` if the field isn't numeric, the value isn't
        parseable, or the unit isn't in the field's conversion table. For
        ``loading_efficiency``, fractions in [0, 1] without a unit are
        auto-converted to percent.
        """
        spec = self._registry.get(field_name)
        if spec is None or not spec.is_numeric:
            return None, None
        x = self.parse_number(value)
        if x is None:
            return None, None
        u = self.normalise_unit_string(unit)
        table = spec.unit_table

        if field_name == "loading_efficiency":
            if u in ("", "fraction") and 0.0 <= x <= 1.0:
                return x * 100.0, spec.canonical_unit
            if u in ("", "fraction"):
                return x, spec.canonical_unit
            if u in table:
                return x * table[u], spec.canonical_unit
            return None, None

        if u == "":
            return None, None
        if u in table:
            return x * table[u], spec.canonical_unit
        return None, None

    @staticmethod
    def canonicalise_text(value: object) -> str:
        """For free-text fields and evidence quotes."""
        if UnitNormalizer.is_nr(value):
            return NR
        return re.sub(r"\s+", " ", str(value)).strip().lower()
