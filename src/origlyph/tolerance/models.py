"""Domain models for deterministic 1D worst-case tolerance analysis.

This module defines the typed value objects that represent a 1D tolerance
stack and its worst-case analysis result. All objects are immutable frozen
dataclasses. Validation is performed at construction time; no silent
repair or undocumented defaults are applied.

Engineering meaning of a tolerance contribution:

* ``nominal`` is the signed nominal dimension of the contribution.
* ``lower_deviation`` is the lower deviation from nominal (typically negative
  or zero). The actual dimension is never below ``nominal + lower_deviation``.
* ``upper_deviation`` is the upper deviation from nominal (typically positive
  or zero). The actual dimension is never above ``nominal + upper_deviation``.
* ``direction`` specifies how the contribution enters the stack:
  ``StackDirection.FORWARD`` adds the contribution; ``StackDirection.INVERSE``
  subtracts it.

Numeric policy: standard Python ``float``. No ``Decimal``, NumPy, or other
numeric dependency is introduced. All values must be finite; NaN and
infinity are rejected at construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .exceptions import (
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
)


class StackDirection(Enum):
    """Direction in which a tolerance contribution enters the stack.

    ``FORWARD`` adds the contribution to the stack. ``INVERSE`` subtracts
    it, which reverses the interval propagation in worst-case analysis.
    """

    FORWARD = "forward"
    INVERSE = "inverse"


@dataclass(frozen=True)
class ToleranceContribution:
    """A single deterministic contribution to a 1D tolerance stack.

    The admissible interval for this contribution is::

        [nominal + lower_deviation, nominal + upper_deviation]

    Attributes
    ----------
    name:
        Human-readable identifier for traceability.
    nominal:
        Signed nominal dimension of the contribution.
    lower_deviation:
        Lower deviation from nominal. Must not exceed ``upper_deviation``.
    upper_deviation:
        Upper deviation from nominal. Must not be less than
        ``lower_deviation``.
    direction:
        How the contribution enters the stack (FORWARD adds, INVERSE
        subtracts).
    """

    name: str
    nominal: float
    lower_deviation: float
    upper_deviation: float
    direction: StackDirection = StackDirection.FORWARD

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "nominal", _validate_finite(self.nominal, "nominal")
        )
        object.__setattr__(
            self,
            "lower_deviation",
            _validate_finite(self.lower_deviation, "lower_deviation"),
        )
        object.__setattr__(
            self,
            "upper_deviation",
            _validate_finite(self.upper_deviation, "upper_deviation"),
        )
        if self.lower_deviation > self.upper_deviation:
            raise InvalidToleranceError(
                f"lower_deviation ({self.lower_deviation}) must not exceed "
                f"upper_deviation ({self.upper_deviation})"
            )

    def interval(self) -> tuple[float, float]:
        """Return the admissible interval ``(lower_bound, upper_bound)`` in stack space.

        For a ``FORWARD`` contribution the interval is::

            (nominal + lower_deviation, nominal + upper_deviation)

        For an ``INVERSE`` contribution the interval is reversed because the
        contribution is subtracted from the stack::

            (-(nominal + upper_deviation), -(nominal + lower_deviation))
        """
        if self.direction is StackDirection.FORWARD:
            lower = self.nominal + self.lower_deviation
            upper = self.nominal + self.upper_deviation
        else:
            lower = -(self.nominal + self.upper_deviation)
            upper = -(self.nominal + self.lower_deviation)
        return (lower, upper)


def _validate_finite(
    value: float,
    field_name: str,
    error_cls: type[Exception] = InvalidToleranceError,
) -> float:
    """Coerce to floatand reject NaN / infinity.

    Parameters
    ----------
    value:
        The raw numeric value to validate.

    field_name:
        Human-readable field name for error messages.

    error_cls:
        Exception class to raise on invalid input. Defaults to
        :class:`InvalidToleranceError`; statistical models pass
        :class:`InvalidStatisticalError`.
    """
    result = float(value)
    if math.isnan(result):
        raise error_cls(
            f"{field_name} must be a finite number, got NaN"
        )
    if math.isinf(result):
        raise error_cls(
            f"{field_name} must be a finite number, got infinity"
        )
    return result


@dataclass(frozen=True)
class ToleranceStack:
    """An ordered, immutable 1D tolerance stack.

    The stack is an ordered sequence of contributions. Ordering is part of
    traceability and is preserved.

    Attributes
    ----------
    contributions:
        Ordered tuple of tolerance contributions.
    """

    contributions: tuple[ToleranceContribution, ...]

    def __post_init__(self) -> None:
        if not self.contributions:
            raise InvalidStackError(
                "tolerance stack must contain at least one contribution"
            )
        for index, contribution in enumerate(self.contributions):
            if not isinstance(contribution, ToleranceContribution):
                raise InvalidStackError(
                    f"stack element at index {index} is not a ToleranceContribution"
                )


@dataclass(frozen=True)
class WorstCaseResult:
    """Deterministic result of a 1D worst-case tolerance stack analysis.

    Attributes
    ----------
    nominal:
        Nominal stack value (sum of signed nominals).
    minimum:
        Minimum possible stack value under worst-case combination.
    maximum:
        Maximum possible stack value under worst-case combination.
    lower_deviation:
        ``minimum - nominal`` (typically negative or zero).
    upper_deviation:
        ``maximum - nominal`` (typically positive or zero).
    total_span:
        ``maximum - minimum`` (total worst-case tolerance span).
    """

    nominal: float
    minimum: float
    maximum: float
    lower_deviation: float
    upper_deviation: float
    total_span: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "nominal", _validate_finite(self.nominal, "nominal")
        )
        object.__setattr__(
            self, "minimum", _validate_finite(self.minimum, "minimum")
        )
        object.__setattr__(
            self, "maximum", _validate_finite(self.maximum, "maximum")
        )
        object.__setattr__(
            self,
            "lower_deviation",
            _validate_finite(self.lower_deviation, "lower_deviation"),
        )
        object.__setattr__(
            self,
            "upper_deviation",
            _validate_finite(self.upper_deviation, "upper_deviation"),
        )
        object.__setattr__(
            self,
            "total_span",
            _validate_finite(self.total_span, "total_span"),
        )

@dataclass(frozen=True)
class StatisticalContribution:
    """A single statistical contribution to a 1D tolerance stack.

    Each contribution is defined by its nominal value, standard deviation
    (sigma), and stack direction. The standard deviation must be non-negative
    and finite. Zero sigma is permitted (deterministic contributor).

    Attributes
    ----------
    name:
        Human-readable identifier for traceability.
    nominal:
        Signed nominal dimension of the contribution.
    sigma:
        Standard deviation of the contribution. Must be non-negative and
        finite. Zero indicates a deterministic (non-statistical) contributor.
    direction:
        How the contribution enters the stack (FORWARD adds, INVERSE
        subtracts).
    """

    name: str
    nominal: float
    sigma: float
    direction: StackDirection = StackDirection.FORWARD

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "nominal",
            _validate_finite(
                self.nominal, "nominal", InvalidStatisticalError
            ),
        )
        object.__setattr__(
            self,
            "sigma",
            _validate_finite(self.sigma, "sigma", InvalidStatisticalError),
        )
        if self.sigma < 0.0:
            raise InvalidStatisticalError(
                f"sigma must be non-negative, got {self.sigma}"
            )


@dataclass(frozen=True)
class StatisticalStack:
    """An ordered, immutable 1D statistical tolerance stack.

    The stack is an ordered sequence of statistical contributions.
    Ordering is part of traceability and is preserved.

    Attributes
    ----------
    contributions:
        Ordered tuple of statistical contributions.
    """

    contributions: tuple[StatisticalContribution, ...]

    def __post_init__(self) -> None:
        if not self.contributions:
            raise InvalidStatisticalError(
                "statistical stack must contain at least one contribution"
            )
        for index, contribution in enumerate(self.contributions):
            if not isinstance(contribution, StatisticalContribution):
                raise InvalidStatisticalError(
                    f"stack element at index {index} is not a "
                    "StatisticalContribution"
                )


@dataclass(frozen=True)
class StatisticalResult:
    """Deterministic result of a 1D statistical (RSS) tolerance analysis.

    Attributes
    ----------
    nominal:
        Nominal stack value (sum of signed nominals).
    combined_sigma:
        Root-sum-square combined standard deviation.
    sigma_multiplier:
        Multiplier k applied to combined_sigma for bound computation.
    lower_bound:
        ``nominal - k * combined_sigma``.
    upper_bound:
        ``nominal + k * combined_sigma``.
    """

    nominal: float
    combined_sigma: float
    sigma_multiplier: float
    lower_bound: float
    upper_bound: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "nominal",
            _validate_finite(
                self.nominal, "nominal", InvalidStatisticalError
            ),
        )
        object.__setattr__(
            self,
            "combined_sigma",
            _validate_finite(
                self.combined_sigma, "combined_sigma", InvalidStatisticalError
            ),
        )
        object.__setattr__(
            self,
            "sigma_multiplier",
            _validate_finite(
                self.sigma_multiplier,
                "sigma_multiplier",
                InvalidStatisticalError,
            ),
        )
        object.__setattr__(
            self,
            "lower_bound",
            _validate_finite(
                self.lower_bound, "lower_bound", InvalidStatisticalError
            ),
        )
        object.__setattr__(
            self,
            "upper_bound",
            _validate_finite(
                self.upper_bound, "upper_bound", InvalidStatisticalError
            ),
        )
