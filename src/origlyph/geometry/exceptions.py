"""Domain exceptions for the Origlyph geometry domain.

The hierarchy is intentionally minimal. All geometry-domain failures derive
from :class:`OriglyphGeometryError` so callers can catch the whole domain with
one base type while still discriminating specific failure classes.
"""


class OriglyphGeometryError(Exception):
    """Base class for all Origlyph geometry domain errors."""


class InvalidGeometryError(OriglyphGeometryError):
    """Raised when a geometric object or operation is invalid or degenerate.

    Examples: normalizing a zero vector, using a zero direction for a
    ``Line3D``, or using a zero normal for a ``Plane3D``.
    """


class UnitError(OriglyphGeometryError):
    """Raised for ambiguous, unsupported, or incorrectly mixed units.

    Origlyph never guesses units; an unknown or ambiguous unit is a failure.
    """


class UnsupportedGeometryError(OriglyphGeometryError):
    """Raised for geometry that the Origlyph domain does not support."""