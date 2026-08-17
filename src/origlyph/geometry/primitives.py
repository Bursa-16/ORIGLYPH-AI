"""Core geometric primitives for the Origlyph geometry domain.

All primitives are immutable frozen dataclasses holding canonical geometry
only (millimetre coordinates). They carry no provenance, source IDs, or
unit metadata — those belong to the future import/provenance wrapper.

Zero-vector policy:

* constructing ``Vector3D(0, 0, 0)`` is allowed (a legitimate mathematical
  result, e.g. the difference of two coincident points);
* normalizing a zero vector raises :class:`InvalidGeometryError`;
* using a zero vector as a ``Line3D`` direction or ``Plane3D`` normal is
  rejected at construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .exceptions import InvalidGeometryError
from .tolerance import GeometryTolerancePolicy


def _as_float(value: float) -> float:
    return float(value)


@dataclass(frozen=True)
class Point3D:
    """A point in canonical millimetre coordinates."""

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _as_float(self.x))
        object.__setattr__(self, "y", _as_float(self.y))
        object.__setattr__(self, "z", _as_float(self.z))

    def __add__(self, vector: "Vector3D") -> "Point3D":
        return Point3D(self.x + vector.x, self.y + vector.y, self.z + vector.z)

    def __sub__(self, other: "Point3D") -> "Vector3D":
        return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)


@dataclass(frozen=True)
class Vector3D:
    """A free vector in canonical millimetre coordinates.

    A zero vector is allowed; only normalization/orientation-requiring uses
    reject it.
    """

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _as_float(self.x))
        object.__setattr__(self, "y", _as_float(self.y))
        object.__setattr__(self, "z", _as_float(self.z))

    def magnitude(self) -> float:
        """Euclidean magnitude in canonical millimetres."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def is_zero(self) -> bool:
        """True if the vector is effectively zero under the computational policy."""
        return GeometryTolerancePolicy.near_zero(self.magnitude())

    def dot(self, other: "Vector3D") -> float:
        """Dot product with ``other``."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vector3D") -> "Vector3D":
        """Cross product with ``other``."""
        return Vector3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def scaled(self, factor: float) -> "Vector3D":
        """This vector scaled by ``factor``."""
        return Vector3D(self.x * factor, self.y * factor, self.z * factor)

    def normalize(self) -> "Vector3D":
        """Return a unit vector in the same direction.

        Raises :class:`InvalidGeometryError` for an (effectively) zero vector.
        """
        mag = self.magnitude()
        if GeometryTolerancePolicy.near_zero(mag):
            raise InvalidGeometryError(
                "cannot normalize a zero vector"
            )
        return Vector3D(self.x / mag, self.y / mag, self.z / mag)

    def __add__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> "Vector3D":
        return Vector3D(-self.x, -self.y, -self.z)


@dataclass(frozen=True)
class Line3D:
    """An infinite line through a point with a normalized non-zero direction.

    Representation policy: the direction is always stored normalized to unit
    magnitude at construction.
    """

    point: Point3D
    direction: Vector3D

    def __post_init__(self) -> None:
        if self.direction.is_zero():
            raise InvalidGeometryError(
                "Line3D requires a non-zero direction vector"
            )
        object.__setattr__(self, "direction", self.direction.normalize())


@dataclass(frozen=True)
class Plane3D:
    """An infinite plane through a point with a normalized non-zero normal.

    Representation policy: the normal is always stored normalized to unit
    magnitude at construction.
    """

    point: Point3D
    normal: Vector3D

    def __post_init__(self) -> None:
        if self.normal.is_zero():
            raise InvalidGeometryError(
                "Plane3D requires a non-zero normal vector"
            )
        object.__setattr__(self, "normal", self.normal.normalize())