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

Correlation modeling:

* ``Correlation`` captures an explicit pairwise Pearson correlation
  coefficient between two contributors in a statistical stack.
  Correlations must be supplied explicitly by the engineer; Origlyph
  does **not** infer manufacturing correlations.
* Missing pairwise correlation defaults to ρ = 0 (independent).
* Correlation terms are validated to be finite and within [-1, 1];
  no clamping is performed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .exceptions import (
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
)

if TYPE_CHECKING:
    from .sensitivity import CovariancePairImpact


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


@dataclass(frozen=True)
class Correlation:
    """Explicit pairwise Pearson correlation between two statistical contributors.

    A correlation captures an explicit engineering assumption about how two
    contributors co-vary.  Origlyph never infers correlations on its own;
    every correlation must be supplied explicitly by the caller.

    Canonical ordering:

    The two contributor names are normalized so that ``first <= second``
    lexicographically.  This guarantees that ``Correlation("B", "A", 0.5)``
    and ``Correlation("A", "B", 0.5)`` are equal and hash identically, so
    pair symmetry is enforced automatically and duplicate definitions are
    rejected.

    Attributes
    ----------
    first:
        Identifier of the first contributor.  Must be a non-empty string
        and must refer to a contributor present in the statistical stack.
    second:
        Identifier of the second contributor.  Must be a non-empty string,
        different from ``first``, and must refer to a contributor present
        in the statistical stack.
    coefficient:
        Pearson correlation coefficient ρ.  Must be finite and within the
        closed interval [-1, 1].  No clamping is performed.
    """

    first: str
    second: str
    coefficient: float

    def __post_init__(self) -> None:
        if not isinstance(self.first, str) or self.first == "":
            raise InvalidCorrelationError(
                "correlation 'first' contributor must be a non-empty string"
            )
        if not isinstance(self.second, str) or self.second == "":
            raise InvalidCorrelationError(
                "correlation 'second' contributor must be a non-empty string"
            )
        if self.first == self.second:
            raise InvalidCorrelationError(
                "correlation between a contributor and itself is not permitted; "
                "self-correlation is defined implicitly as rho = 1.0"
            )
        # Canonical ordering for pair symmetry and deduplication.
        first, second = sorted((self.first, self.second))
        object.__setattr__(self, "first", first)
        object.__setattr__(self, "second", second)
        rho = _validate_finite(
            self.coefficient, "coefficient", InvalidCorrelationError
        )
        if rho < -1.0 or rho > 1.0:
            raise InvalidCorrelationError(
                f"correlation coefficient must be within [-1, 1], got {rho}"
            )
        object.__setattr__(self, "coefficient", rho)

    @property
    def pair(self) -> tuple[str, str]:
        """Return the canonical ordered pair ``(first, second)``."""
        return (self.first, self.second)


# ---------------------------------------------------------------------------
# Budget analysis (Stage 15G) — compliance status and contributor impact
# ---------------------------------------------------------------------------


class BudgetStatus(Enum):
    """Tolerance-budget compliance status.

    ``UNDER_BUDGET``: the stack's actual span fits within the allowed budget
    with positive remaining margin.

    ``AT_BUDGET``: the actual span equals the allowed span within a small
    deterministic tolerance. Neither ``UNDER_BUDGET`` nor ``OVER_BUDGET``.

    ``OVER_BUDGET``: the actual span exceeds the allowed budget; the remaining
    margin is negative.
    """

    UNDER_BUDGET = "under_budget"
    AT_BUDGET = "at_budget"
    OVER_BUDGET = "over_budget"


@dataclass(frozen=True)
class WorstCaseContributionBudget:
    """Budget impact of one contributor on the worst-case stack span.

    Every numeric field is derived read-only from the contributor and the
    authoritative worst-case result. Fractions and percentages are
    deterministic; a zero actual span yields ``share_of_consumed = 0.0``
    (documented policy — no division is performed).

    Attributes
    ----------
    name:
        Human-readable contributor identifier (for traceability).
    signed_nominal:
        Signed nominal contribution to the stack total.
    direction:
        How the contributor enters the stack (FORWARD adds, INVERSE
        subtracts).
    lower_deviation:
        Lower deviation of this contributor from its nominal.
    upper_deviation:
        Upper deviation of this contributor from its nominal.
    span:
        Contributor tolerance span (always ``upper - lower >= 0``).
    share_of_consumed:
        Fraction of the actual stack span attributed to this contributor.
        ``span / total_span``. Zero if ``total_span`` is zero.
    share_of_allowed:
        Fraction of the allowed budget consumed by this contributor.
        ``span / allowed_span``.
    percentage_of_consumed:
        ``100 * share_of_consumed``.
    percentage_of_allowed:
        ``100 * share_of_allowed``.
    """

    name: str
    signed_nominal: float
    direction: StackDirection
    lower_deviation: float
    upper_deviation: float
    span: float
    share_of_consumed: float
    share_of_allowed: float
    percentage_of_consumed: float
    percentage_of_allowed: float


@dataclass(frozen=True)
class WorstCaseBudgetResult:
    """Result of deterministic worst-case tolerance-budget compliance analysis.

    All authoritative numbers are delegated to the existing worst-case engine.
    Budget analysis evaluates compliance; it does not modify tolerances.

    Attributes
    ----------
    nominal:
        Stack nominal value from the authoritative engine.
    minimum:
        Stack minimum from the authoritative engine.
    maximum:
        Stack maximum from the authoritative engine.
    actual_span:
        Worst-case span consumed by the stack (``maximum - minimum``).
    allowed_span:
        Maximum permitted span (validated as finite and strictly positive).
    remaining_margin:
        ``allowed_span - actual_span``.
    utilization_fraction:
        ``actual_span / allowed_span``.
    utilization_percentage:
        ``100 * utilization_fraction``.
    status:
        ``UNDER_BUDGET``, ``AT_BUDGET``, or ``OVER_BUDGET``.
    contributions:
        Per-contributor budget impacts (ordered by descending span, ties
        preserve input order).
    """

    nominal: float
    minimum: float
    maximum: float
    actual_span: float
    allowed_span: float
    remaining_margin: float
    utilization_fraction: float
    utilization_percentage: float
    status: BudgetStatus
    contributions: tuple[WorstCaseContributionBudget, ...]


@dataclass(frozen=True)
class StatisticalContributionBudget:
    """Budget impact of one contributor on the statistical stack.

    Statistical budget analysis reuses the variance decomposition from
    Stage 15F sensitivity analysis. The statistical interval span
    (``upper_bound - lower_bound``) is not linearly decomposable, so
    contributor shares use variance fractions from the authoritative
    sensitivity analysis.

    Attributes
    ----------
    name:
        Human-readable contributor identifier.
    direction:
        How the contributor enters the stack.
    sigma:
        Standard deviation of the contributor.
    variance:
        Individual variance contribution ``a_i^2 * sigma_i^2``.
    share_of_consumed:
        Fraction of total variance attributed to this contributor.
        Reuses the authoritative Stage 15F sensitivity fraction.
    share_of_allowed:
        ``share_of_consumed * utilization_fraction`` — the fraction of
        the allowed statistical budget attributed to this contributor.
    percentage_of_consumed:
        ``100 * share_of_consumed``.
    percentage_of_allowed:
        ``100 * share_of_allowed``.
    """

    name: str
    direction: StackDirection
    sigma: float
    variance: float
    share_of_consumed: float
    share_of_allowed: float
    percentage_of_consumed: float
    percentage_of_allowed: float


@dataclass(frozen=True)
class StatisticalBudgetResult:
    """Result of deterministic statistical tolerance-budget compliance analysis.

    All authoritative numbers are delegated to the existing statistical engine
    and Stage 15F sensitivity analysis. Budget analysis evaluates compliance;
    it does not modify tolerances.

    Statistical budget compliance does NOT imply worst-case compliance.

    Attributes
    ----------
    nominal:
        Stack nominal value from the authoritative engine.
    combined_sigma:
        Combined standard deviation from the authoritative engine.
    sigma_multiplier:
        Sigma multiplier used for bound computation.
    lower_bound:
        Lower statistical bound from the authoritative engine.
    upper_bound:
        Upper statistical bound from the authoritative engine.
    actual_span:
        Statistical interval span (``upper_bound - lower_bound``).
    allowed_span:
        Maximum permitted span (validated as finite and strictly positive).
    remaining_margin:
        ``allowed_span - actual_span``.
    utilization_fraction:
        ``actual_span / allowed_span``.
    utilization_percentage:
        ``100 * utilization_fraction``.
    status:
        ``UNDER_BUDGET``, ``AT_BUDGET``, or ``OVER_BUDGET``.
    contributions:
        Per-contributor budget impacts (ordered by descending variance, ties
        preserve input order).
    covariance_pairs:
        Per-pair covariance impacts from Stage 15F sensitivity analysis.
    """

    nominal: float
    combined_sigma: float
    sigma_multiplier: float
    lower_bound: float
    upper_bound: float
    actual_span: float
    allowed_span: float
    remaining_margin: float
    utilization_fraction: float
    utilization_percentage: float
    status: BudgetStatus
    contributions: tuple[StatisticalContributionBudget, ...]
    covariance_pairs: tuple["CovariancePairImpact", ...]


@dataclass(frozen=True)
class WorstCaseWindowResult:
    """Result of worst-case interval window-compliance check.

    Checks whether the authoritative worst-case interval lies completely
    inside a permitted window. Window compliance is independent of
    span-based budget analysis.

    Attributes
    ----------
    nominal:
        Stack nominal value.
    minimum:
        Stack minimum from the authoritative engine.
    maximum:
        Stack maximum from the authoritative engine.
    allowed_lower:
        Lower bound of the permitted window.
    allowed_upper:
        Upper bound of the permitted window.
    is_compliant:
        ``True`` if ``allowed_lower <= minimum`` and
        ``maximum <= allowed_upper``.
    """

    nominal: float
    minimum: float
    maximum: float
    allowed_lower: float
    allowed_upper: float
    is_compliant: bool
