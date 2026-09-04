"""Domain exceptions for the Origlyph tolerance analysis package.

All tolerance-domain failures derive from :class:`OriglyphToleranceError` so
callers can catch the whole domain with one base type while still
discriminating specific failure classes. This hierarchy is intentionally
minimal. It does not modify the geometry or CAD exception hierarchies.

Failure classes are not warnings: raising one of these aborts the analysis.
Non-fatal issues are represented by explicit result objects instead.
"""


class OriglyphToleranceError(Exception):
    """Base class for all Origlyph tolerance analysis domain errors."""


class InvalidToleranceError(OriglyphToleranceError):
    """Raised when a tolerance contribution definition is invalid.

    Examples: lower deviation exceeding upper deviation, non-finite numeric
    values, or NaN/infinity in tolerance fields.
    """


class InvalidStackError(OriglyphToleranceError):
    """Raised when a tolerance stack definition is invalid.

    Examples: empty stack, or a stack containing an invalid contribution.
    """


class InvalidStatisticalError(OriglyphToleranceError):
    """Raised when a statistical tolerance definition is invalid.

    Examples: negative sigma, non-finite sigma, invalid sigma multiplier,
    or malformed statistical stack.
    """


class InvalidVarianceError(OriglyphToleranceError):
    """Raised when propagated variance is materially invalid.

    A small tolerance (±1e-15) is permitted for floating-point round-off; but
    any materially negative variance resulting from correlation inputs is
    rejected so that invalid engineering data is never silently repaired.
    """


class InvalidCorrelationError(OriglyphToleranceError):
    """Raised when a correlation definition is invalid.

    Examples: rho outside [-1, 1], non-finite rho, unknown contributor
    reference, duplicate/conflicting correlation pairs.
    """


class InvalidBudgetError(OriglyphToleranceError):
    """Raised when a tolerance-budget definition is invalid.

    Examples: non-positive, non-finite, or NaN allowed span;
    non-finite or NaN allowed window bounds; invalid window ordering.
    """


class InvalidAllocationError(OriglyphToleranceError):
    """Raised when a tolerance allocation plan is invalid.

    Examples: non-positive or non-finite allowed budget; negative or
    non-finite allocated span; duplicate contributor IDs; unknown
    contributor references; malformed or ambiguous identifiers.
    """
