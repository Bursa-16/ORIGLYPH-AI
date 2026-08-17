"""Canonical unit representation for the Origlyph geometry domain.

The canonical internal system is:
  * length -> millimetres (``mm``)
  * angle  -> radians    (``rad``)

``Length`` and ``Angle`` are dimensionally separate and immutable. There is no
implicit unit guessing: boundary helpers convert from an explicit unit or raise
:class:`UnitError`. Pure geometry value objects never store source-unit
metadata; conversion happens only at construction/import boundaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .exceptions import UnitError

# Conversion factors mapping a source unit name to the canonical unit value.
# A value ``v`` in source unit ``u`` equals ``v * _LENGTH_TO_MM[u]`` millimetres.
_LENGTH_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "inch": 25.4,
}

# A value ``v`` in source unit ``u`` equals ``v * _ANGLE_TO_RAD[u]`` radians.
_ANGLE_TO_RAD = {
    "rad": 1.0,
    "radian": 1.0,
    "radians": 1.0,
    "deg": math.pi / 180.0,
    "degree": math.pi / 180.0,
    "degrees": math.pi / 180.0,
}


def _length_factor(unit: str) -> float:
    key = unit.strip().lower()
    try:
        return _LENGTH_TO_MM[key]
    except KeyError as exc:
        raise UnitError(
            f"unsupported or ambiguous length unit {unit!r}; expected one of "
            f"{sorted(_LENGTH_TO_MM)}"
        ) from exc


def _angle_factor(unit: str) -> float:
    key = unit.strip().lower()
    try:
        return _ANGLE_TO_RAD[key]
    except KeyError as exc:
        raise UnitError(
            f"unsupported or ambiguous angle unit {unit!r}; expected one of "
            f"{sorted(_ANGLE_TO_RAD)}"
        ) from exc


@dataclass(frozen=True)
class Length:
    """An immutable length expressed in canonical millimetres."""

    mm: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "mm", float(self.mm))

    @classmethod
    def millimetres(cls, value: float) -> "Length":
        """Construct a ``Length`` from a value already in millimetres."""
        return cls(float(value))

    @classmethod
    def of(cls, value: float, unit: str) -> "Length":
        """Construct a ``Length`` from ``value`` in the explicit ``unit``."""
        return cls(float(value) * _length_factor(unit))

    def in_unit(self, unit: str) -> float:
        """Return this length converted into the requested ``unit``."""
        return self.mm / _length_factor(unit)

    def __float__(self) -> float:
        return float(self.mm)


@dataclass(frozen=True)
class Angle:
    """An immutable angle expressed in canonical radians."""

    rad: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "rad", float(self.rad))

    @classmethod
    def radians(cls, value: float) -> "Angle":
        """Construct an ``Angle`` from a value already in radians."""
        return cls(float(value))

    @classmethod
    def degrees(cls, value: float) -> "Angle":
        """Construct an ``Angle`` from a value in degrees."""
        return cls(float(value) * _ANGLE_TO_RAD["deg"])

    @classmethod
    def of(cls, value: float, unit: str) -> "Angle":
        """Construct an ``Angle`` from ``value`` in the explicit ``unit``."""
        return cls(float(value) * _angle_factor(unit))

    def in_unit(self, unit: str) -> float:
        """Return this angle converted into the requested ``unit``."""
        return self.rad / _angle_factor(unit)

    def __float__(self) -> float:
        return float(self.rad)


def as_length(value: float, unit: str) -> Length:
    """Boundary helper: convert an explicit length quantity to canonical mm."""
    return Length.of(value, unit)


def as_angle(value: float, unit: str) -> Angle:
    """Boundary helper: convert an explicit angle quantity to canonical rad."""
    return Angle.of(value, unit)