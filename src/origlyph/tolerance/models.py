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
    InvalidAllocationError,
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalAllocationError,
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


# ---------------------------------------------------------------------------
# Stage 15H — Deterministic allocation validation models
# ---------------------------------------------------------------------------


class AllocationStatus(Enum):
    """Status of a user-supplied tolerance allocation plan.

    Allocation status describes whether a *plan* is under-, fully, or
    over-allocated against its stated budget. It does **not** describe
    actual engineering consumption; for that see :class:`BudgetStatus`.

    Members
    -------
    UNDER_ALLOCATED:
        ``allocated_total < allowed_budget`` (beyond equality tolerance).
        Positive remaining unallocated amount.
    FULLY_ALLOCATED:
        ``allocated_total`` equals ``allowed_budget`` within the established
        Origlyph tolerance numerical equality tolerance.
    OVER_ALLOCATED:
        ``allocated_total > allowed_budget`` (beyond equality tolerance).
        Negative remaining unallocated amount.
    """

    UNDER_ALLOCATED = "under_allocated"
    FULLY_ALLOCATED = "fully_allocated"
    OVER_ALLOCATED = "over_allocated"


@dataclass(frozen=True)
class ToleranceAllocation:
    """A single allocated tolerance span for one contributor.

    Attributes
    ----------
    contributor_id:
        Identifier of the contributor this allocation applies to. Must
        match a contributor name in the referenced stack exactly.
    allocated_span:
        The allocated tolerance span for this contributor. Must be finite
        and non-negative. NaN and infinity are rejected.
    """

    contributor_id: str
    allocated_span: float

    def __post_init__(self) -> None:
        if not isinstance(self.contributor_id, str) or not self.contributor_id.strip():
            raise InvalidAllocationError(
                "contributor_id must be a non-empty string, "
                f"got {self.contributor_id!r}"
            )
        try:
            object.__setattr__(
                self,
                "allocated_span",
                _validate_finite(self.allocated_span, "allocated_span"),
            )
        except InvalidToleranceError as exc:
            raise InvalidAllocationError(str(exc)) from exc
        if self.allocated_span < 0.0:
            raise InvalidAllocationError(
                f"allocated_span must be non-negative, got {self.allocated_span}"
            )


@dataclass(frozen=True)
class AllocationPlan:
    """A user-supplied tolerance allocation plan.

    Attributes
    ----------
    allowed_budget:
        The total tolerance budget allowed for this allocation plan. Must
        be finite and strictly positive.
    allocations:
        The per-contributor allocation entries. Each contributor may appear
        at most once; duplicate contributor IDs are rejected.
    """

    allowed_budget: float
    allocations: tuple[ToleranceAllocation, ...]

    def __post_init__(self) -> None:
        if math.isnan(self.allowed_budget) or math.isinf(self.allowed_budget):
            raise InvalidAllocationError(
                "allowed_budget must be a finite number, "
                f"got {'NaN' if math.isnan(self.allowed_budget) else 'infinity'}"
            )
        if self.allowed_budget <= 0.0:
            raise InvalidAllocationError(
                f"allowed_budget must be strictly positive, got {self.allowed_budget}"
            )
        seen: set[str] = set()
        for allocation in self.allocations:
            if allocation.contributor_id in seen:
                raise InvalidAllocationError(
                    f"duplicate contributor_id: {allocation.contributor_id!r}"
                )
            seen.add(allocation.contributor_id)


@dataclass(frozen=True)
class AllocationContributorResult:
    """Per-contributor comparison between allocated and current spans.

    Attributes
    ----------
    contributor_id:
        Identifier of the contributor.
    allocated_span:
        The span allocated to this contributor in the plan.
    current_span:
        The current tolerance span of this contributor in the stack,
        derived using the same semantics as Stage 15F / Stage 15G.
    delta_from_current:
        ``allocated_span - current_span``.
    fraction_of_allowed_budget:
        ``allocated_span / allowed_budget``.
    """

    contributor_id: str
    allocated_span: float
    current_span: float
    delta_from_current: float
    fraction_of_allowed_budget: float


@dataclass(frozen=True)
class AllocationValidationResult:
    """Result of validating a user-supplied allocation plan.

    Attributes
    ----------
    allowed_budget:
        The total tolerance budget allowed (from the plan).
    allocated_total:
        Sum of all allocated spans.
    remaining_unallocated:
        ``allowed_budget - allocated_total``.
    utilization_fraction:
        ``allocated_total / allowed_budget``.
    utilization_percentage:
        ``100 * utilization_fraction``.
    status:
        ``UNDER_ALLOCATED``, ``FULLY_ALLOCATED``, or ``OVER_ALLOCATED``.
    is_complete:
        ``True`` when every stack contributor appears exactly once in
        the plan (or when ``require_complete=False`` and no unknown
        contributors are present).
    contributor_results:
        Per-contributor comparison results, in deterministic input order.
    missing_contributors:
        Stack contributor IDs not present in the plan (empty when
        ``is_complete`` is ``True``).
    """

    allowed_budget: float
    allocated_total: float
    remaining_unallocated: float
    utilization_fraction: float
    utilization_percentage: float
    status: AllocationStatus
    is_complete: bool
    contributor_results: tuple[AllocationContributorResult, ...]
    missing_contributors: tuple[str, ...]


# ---------------------------------------------------------------------------
# Stage 15I — Deterministic allocation reconciliation models
# ---------------------------------------------------------------------------


class AllocationComplianceStatus(Enum):
    """Per-contributor allocation compliance status.

    Describes whether actual tolerance consumption is within, at, or
    exceeding the allocated span for a single contributor.

    Members
    -------
    UNDER_ALLOCATION:
        ``actual_span < allocated_span`` (beyond tolerance). Positive margin.
    AT_ALLOCATION:
        ``actual_span`` equals ``allocated_span`` within tolerance.
    OVER_ALLOCATION:
        ``actual_span > allocated_span`` (beyond tolerance). Negative margin.
        Also used when ``allocated_span == 0`` and ``actual_span > 0``.
    """

    UNDER_ALLOCATION = "under_allocation"
    AT_ALLOCATION = "at_allocation"
    OVER_ALLOCATION = "over_allocation"


class ReconciliationStatus(Enum):
    """Total reconciliation status between allocated plan and actual consumption.

    Members
    -------
    ACTUAL_WITHIN_ALLOCATION:
        ``actual_total_span < allocated_total`` (beyond tolerance).
    ACTUAL_AT_ALLOCATION:
        ``actual_total_span`` equals ``allocated_total`` within tolerance.
    ACTUAL_EXCEEDS_ALLOCATION:
        ``actual_total_span > allocated_total`` (beyond tolerance).
    """

    ACTUAL_WITHIN_ALLOCATION = "actual_within_allocation"
    ACTUAL_AT_ALLOCATION = "actual_at_allocation"
    ACTUAL_EXCEEDS_ALLOCATION = "actual_exceeds_allocation"


@dataclass(frozen=True)
class ContributorAllocationCompliance:
    """Per-contributor allocation-vs-actual compliance.

    Attributes
    ----------
    contributor_id:
        Identifier of the contributor.
    allocated_span:
        The span allocated to this contributor in the plan.
    actual_span:
        The actual tolerance span consumed by this contributor.
    margin:
        ``allocated_span - actual_span``. Positive means unused room.
    utilization_fraction:
        ``actual_span / allocated_span`` when ``allocated_span > 0``;
        ``None`` when ``allocated_span == 0`` (division by zero avoided).
    utilization_percentage:
        ``100 * utilization_fraction`` when defined; ``None`` otherwise.
    status:
        ``UNDER_ALLOCATION``, ``AT_ALLOCATION``, or ``OVER_ALLOCATION``.
    """

    contributor_id: str
    allocated_span: float
    actual_span: float
    margin: float
    utilization_fraction: float | None
    utilization_percentage: float | None
    status: AllocationComplianceStatus


@dataclass(frozen=True)
class AllocationReconciliationResult:
    """Result of reconciling a validated allocation plan against actual consumption.

    Attributes
    ----------
    allowed_budget:
        The total tolerance budget allowed (from the plan).
    allocated_total:
        Sum of all allocated spans.
    actual_total_span:
        Sum of all actual contributor spans.
    allocation_remaining:
        ``allowed_budget - allocated_total``.
    engineering_remaining_margin:
        ``allowed_budget - actual_total_span``.
    total_allocation_margin:
        ``allocated_total - actual_total_span``.
    allocation_plan_status:
        Status of the allocation plan (from Stage 15H validation).
    engineering_budget_status:
        Status of actual consumption vs allowed budget.
    reconciliation_status:
        Total reconciliation status (actual vs allocated).
    contributor_compliances:
        Per-contributor compliance results, in deterministic stack order.
    """

    allowed_budget: float
    allocated_total: float
    actual_total_span: float
    allocation_remaining: float
    engineering_remaining_margin: float
    total_allocation_margin: float
    allocation_plan_status: AllocationStatus
    engineering_budget_status: BudgetStatus
    reconciliation_status: ReconciliationStatus
    contributor_compliances: tuple[ContributorAllocationCompliance, ...]


# ===========================================================================
# Stage 15J — Deterministic Statistical Allocation Reconciliation
# ===========================================================================
#
# This section adds typed immutable domain contracts for reconciling a
# user-supplied *statistical* allocation plan against *actual* statistical
# uncertainty consumption produced by the authoritative Stage 15D/15E engine.
#
# A statistical allocation plan is conceptually distinct from the worst-case
# AllocationPlan (Stage 15H): it allocates standard-deviation (sigma) budgets,
# not linear worst-case spans.  Comparing allocated sigma with actual sigma
# is the correct statistical reconciliation; worst-case spans and statistical
# sigmas are different physical quantities and are never interchanged.


class StatisticalAllocationStatus(Enum):
    """Per-contributor statistical allocation compliance status.

    Allocation status describes whether a *plan's sigma allocation* for a
    single contributor is under, at, or over the contributor's *actual sigma*.

    It does **not** describe worst-case span consumption; for that see
    :class:`AllocationComplianceStatus` (Stage 15I).

    Members
    -------
    UNDER_ALLOCATION:
        ``actual_sigma < allocated_sigma`` (beyond equality tolerance).
        Positive sigma margin.
    AT_ALLOCATION:
        ``actual_sigma`` equals ``allocated_sigma`` within tolerance, or
        both are zero.
    OVER_ALLOCATION:
        ``actual_sigma > allocated_sigma`` (beyond tolerance). Negative margin.
        Also used when ``allocated_sigma == 0`` and ``actual_sigma > 0``.
    """

    UNDER_ALLOCATION = "under_allocation"
    AT_ALLOCATION = "at_allocation"
    OVER_ALLOCATION = "over_allocation"


class StatisticalAllocationReconciliationStatus(Enum):
    """Total statistical reconciliation status.

    Between the allocation plan and the actual statistical consumption.

    Members
    -------
    ACTUAL_WITHIN_ALLOCATION:
        ``actual_combined_sigma < allocated_combined_sigma`` (beyond tolerance).
        Positive combined sigma margin.
    ACTUAL_AT_ALLOCATION:
        ``actual_combined_sigma`` equals ``allocated_combined_sigma`` within
        tolerance.
    ACTUAL_EXCEEDS_ALLOCATION:
        ``actual_combined_sigma > allocated_combined_sigma`` (beyond tolerance).
        Negative combined sigma margin.
    """

    ACTUAL_WITHIN_ALLOCATION = "actual_within_allocation"
    ACTUAL_AT_ALLOCATION = "actual_at_allocation"
    ACTUAL_EXCEEDS_ALLOCATION = "actual_exceeds_allocation"


class StatisticalReconciliationEquality:
    """Constant: absolute tolerance reused for statistical reconciliation equality.

    Reuses the same deterministic engineering equality tolerance as Stage 15G
    (``_BUDGET_EQUALITY_TOLERANCE = 1e-12``) and Stage 15H
    (``_ALLOCATION_EQUALITY_TOLERANCE = 1e-12``).  No new or contradictory
    epsilon is introduced for Stage 15J.
    """

    TOLERANCE = 1e-12


@dataclass(frozen=True)
class StatisticalAllocation:
    """A single statistical allocation (sigma budget) for one contributor.

    ``allocated_sigma`` is the standard-deviation budget allocated to the
    contributor. It is a different physical quantity from the worst-case
    ``allocated_span`` defined in :class:`~origlyph.tolerance.ToleranceAllocation`.

    Attributes
    ----------
    contributor_id:
        Identifier of the contributor this allocation applies to. Must
        match a contributor name in the referenced statistical stack.
    allocated_sigma:
        The allocated standard deviation (sigma) for this contributor.
        Must be finite and non-negative. Zero is permitted. NaN and
        infinity are rejected.
    """

    contributor_id: str
    allocated_sigma: float

    def __post_init__(self) -> None:
        if not isinstance(self.contributor_id, str) or not self.contributor_id.strip():
            raise InvalidStatisticalAllocationError(
                "contributor_id must be a non-empty string"
            )
        object.__setattr__(
            self,
            "allocated_sigma",
            _validate_finite(
                self.allocated_sigma,
                "allocated_sigma",
                InvalidStatisticalAllocationError,
            ),
        )
        if self.allocated_sigma < 0.0:
            raise InvalidStatisticalAllocationError(
                f"allocated_sigma must be non-negative, got {self.allocated_sigma}"
            )


@dataclass(frozen=True)
class StatisticalAllocationPlan:
    """A user-supplied statistical allocation plan.

    The plan assigns a per-contributor sigma budget and optionally a
    total combined-sigma budget.  It is validated independently of any
    stack; the caller may also validate it against a specific stack via
    the statistical reconciliation entry point.

    Attributes
    ----------
    sigma_multiplier:
        Sigma multiplier ``k`` applied to the combined sigma for interval
        bound computation. Must be finite and strictly positive. Common
        values are 1, 2, or 3.
    allocations:
        Per-contributor sigma allocations. Each contributor may appear at
        most once; duplicate IDs are rejected.
    allowed_combined_sigma:
        Optional total combined-sigma budget. If supplied, must be finite
        and strictly positive. When omitted (``None``), total reconciliation
        uses the RSS of per-contributor allocations as the authoritative
        allocation-side combined sigma.
    """

    sigma_multiplier: float
    allocations: tuple[StatisticalAllocation, ...]
    allowed_combined_sigma: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sigma_multiplier",
            _validate_finite(
                self.sigma_multiplier,
                "sigma_multiplier",
                InvalidStatisticalAllocationError,
            ),
        )
        if self.sigma_multiplier <= 0.0:
            raise InvalidStatisticalAllocationError(
                f"sigma_multiplier must be strictly positive, "
                f"got {self.sigma_multiplier}"
            )
        seen: set[str] = set()
        for allocation in self.allocations:
            if allocation.contributor_id in seen:
                raise InvalidStatisticalAllocationError(
                    f"duplicate contributor_id: {allocation.contributor_id!r}"
                )
            seen.add(allocation.contributor_id)
        if self.allowed_combined_sigma is not None:
            object.__setattr__(
                self,
                "allowed_combined_sigma",
                _validate_finite(
                    self.allowed_combined_sigma,
                    "allowed_combined_sigma",
                    InvalidStatisticalAllocationError,
                                ),
            )
            if self.allowed_combined_sigma <= 0.0:
                raise InvalidStatisticalAllocationError(
                    f"allowed_combined_sigma must be strictly positive, "
                    f"got {self.allowed_combined_sigma}"
                )


@dataclass(frozen=True)
class StatisticalAllocationCovarianceImpact:
    """Signed covariance-pair impact within a correlated statistical allocation.

    Exposes the contribution of a pairwise correlation to the
    allocation-side variance so that the origin of every covariance term
    is traceable.

    Attributes
    ----------
    first_contributor:
        The lexicographically-first contributor name in the pair.
    second_contributor:
        The lexicographically-second contributor name in the pair.
    coefficient:
        Pearson correlation coefficient rho for the allocation plan.
    variance_contribution:
        The signed term
        ``2 * a_i * a_j * rho * alloc_sigma_i * alloc_sigma_j`` added to
        the allocation-side variance.
    """

    first_contributor: str
    second_contributor: str
    coefficient: float
    variance_contribution: float


@dataclass(frozen=True)
class StatisticalContributorCompliance:
    """Per-contributor statistical allocation-vs-actual compliance.

    Attributes
    ----------
    contributor_id:
        Identifier of the contributor.
    allocated_sigma:
        The sigma allocated to this contributor in the plan.
    actual_sigma:
        The actual sigma of this contributor from the statistical stack.
    sigma_margin:
        ``allocated_sigma - actual_sigma``. Positive means unused room.
    utilization_fraction:
        ``actual_sigma / allocated_sigma`` when ``allocated_sigma > 0``;
        ``None`` when ``allocated_sigma == 0`` (division by zero avoided).
    utilization_percentage:
        ``100 * utilization_fraction`` when defined; ``None`` otherwise.
    status:
        ``UNDER_ALLOCATION``, ``AT_ALLOCATION``, or ``OVER_ALLOCATION``.
    """

    contributor_id: str
    allocated_sigma: float
    actual_sigma: float
    sigma_margin: float
    utilization_fraction: float | None
    utilization_percentage: float | None
    status: StatisticalAllocationStatus


@dataclass(frozen=True)
class StatisticalAllocationReconciliationResult:
    """Result of reconciling a statistical allocation plan against actual consumption.

    Attributes
    ----------
    sigma_multiplier:
        The sigma multiplier ``k`` used for bound computation.
    allocated_combined_sigma:
        RSS (or correlated) combined sigma derived from the allocation plan.
    actual_combined_sigma:
        Combined sigma from the authoritative Stage 15D/15E engine.
    combined_sigma_margin:
        ``allocated_combined_sigma - actual_combined_sigma``.  Positive
        means the allocation has unused room; negative means the actual
        consumption exceeds the allocation.
    allocation_plan_status:
        Status of the allocation plan against its stated budget
        (``AllocationStatus`` from Stage 15H).
    actual_statistical_status:
        Whether actual combined sigma is within, at, or exceeds the
        allocation-side combined sigma.
    contributor_compliances:
        Per-contributor compliance results, in deterministic stack order.
    correlation_impacts:
        Signed covariance-pair impacts for the allocation-side variance.
        Empty for independent-mode reconciliation.
    missing_contributors:
        Contributor IDs present in the stack but absent from the allocation
        plan (only non-empty when ``require_complete=False``).
    is_complete:
        Whether every stack contributor has a corresponding allocation.
    """

    sigma_multiplier: float
    allocated_combined_sigma: float
    actual_combined_sigma: float
    combined_sigma_margin: float
    allocation_plan_status: AllocationStatus
    actual_statistical_status: StatisticalAllocationReconciliationStatus
    contributor_compliances: tuple[StatisticalContributorCompliance, ...]
    correlation_impacts: tuple[StatisticalAllocationCovarianceImpact, ...]
    missing_contributors: tuple[str, ...]
    is_complete: bool


# ===========================================================================
# Stage 15K — Deterministic Tolerance Decision Layer
# ===========================================================================
#
# The decision layer orchestrates the existing tolerance-analysis engines
# into a single coherent, traceable engineering decision.  It does **not**
# recompute any of the existing math; it delegates to the authoritative
# engines and combines their outputs under deterministic decision rules.
#
# The decision statuses are intentionally distinct from the existing
# BudgetStatus / AllocationStatus / ReconciliationStatus enums.  Those enums
# describe compliance of a single dimension (budget, allocation plan, or
# reconciliation).  ToleranceDecisionStatus describes the **overall**
# engineering decision, including consistency between worst-case and
# statistical analysis and the state of any optional reconciliation
# dimensions.


class ToleranceDecisionStatus(Enum):
    """Overall deterministic tolerance decision status.

    Members
    -------
    PASS:
        All required deterministic criteria pass with no boundary
        condition.  No mandatory analysis dimension reports a failure
        and no dimension is at the equality boundary.
    MARGINAL:
        The design technically passes but is at the deterministic
        decision boundary according to the established equality policy
        (``1e-12``).  A MARGINAL decision requires explicit engineering
        review; it is not a PASS.
    FAIL:
        A mandatory engineering criterion is violated.  The decision
        layer never silently downgrades a FAIL.
    INCOMPLETE:
        The decision cannot be safely completed because mandatory
        deterministic inputs are absent or the input configuration is
        not sufficient to make a deterministic statement.  A required
        stack or a required allowed window was not supplied.
    """

    PASS = "pass"
    MARGINAL = "marginal"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class ToleranceDecisionSeverity(Enum):
    """Severity classification for a single deterministic reason.

    Members
    -------
    INFO:
        Informational observation; does not change the decision.
    BOUNDARY:
        The observation is at the deterministic decision boundary.
    FAILURE:
        The observation reports a violation of a required criterion.
    """

    INFO = "info"
    BOUNDARY = "boundary"
    FAILURE = "failure"


class ToleranceDecisionReasonCode(Enum):
    """Stable reason codes for decision-layer observations.

    Each reason code is paired with a severity and (when relevant) a
    numeric evidence payload.  The codes are stable; downstream tooling
    may rely on them.
    """

    WC_REQUIREMENT_EXCEEDED = "wc_requirement_exceeded"
    WC_REQUIREMENT_AT_BOUNDARY = "wc_requirement_at_boundary"
    STAT_REQUIREMENT_EXCEEDED = "stat_requirement_exceeded"
    STAT_REQUIREMENT_AT_BOUNDARY = "stat_requirement_at_boundary"
    WC_ALLOCATION_EXCEEDED = "wc_allocation_exceeded"
    WC_ALLOCATION_AT_BOUNDARY = "wc_allocation_at_boundary"
    STAT_ALLOCATION_EXCEEDED = "stat_allocation_exceeded"
    STAT_ALLOCATION_AT_BOUNDARY = "stat_allocation_at_boundary"
    INCOMPLETE_ALLOCATION = "incomplete_allocation"
    CORRELATION_INCREASES_SIGMA = "correlation_increases_sigma"
    CORRELATION_DECREASES_SIGMA = "correlation_decreases_sigma"
    CORRELATION_EFFECTIVELY_NEUTRAL = "correlation_effectively_neutral"
    WC_STAT_INCONSISTENT = "wc_stat_inconsistent"
    NO_STACK_PROVIDED = "no_stack_provided"
    NO_REQUIREMENT_PROVIDED = "no_requirement_provided"


@dataclass(frozen=True)
class ToleranceDecisionReason:
    """A single deterministic observation in a decision result.

    Reasons are deterministic, typed, and self-explanatory.  No
    free-form text is generated; downstream tooling may rely on the
    ``code`` field to render its own message.

    Attributes
    ----------
    code:
        Stable reason code identifying the kind of observation.
    severity:
        Severity classification of this observation.
    scope:
        Optional scope identifier (for example, a contributor name, an
        allocation plan identifier, or a stack identifier).  ``None``
        when the observation is global.
    detail:
        Optional deterministic numeric or short-string payload providing
        the evidence for the observation.
    """

    code: ToleranceDecisionReasonCode
    severity: ToleranceDecisionSeverity
    scope: str | None
    detail: str | None


class ToleranceDecisionEvaluationState(Enum):
    """State of an individual evaluation dimension within a decision.

    Members
    -------
    PASS:
        The dimension passes the deterministic criterion.
    AT_BOUNDARY:
        The dimension is at the equality boundary (see Stage 15G/15H
        policy of ``1e-12``).
    FAIL:
        The dimension violates the deterministic criterion.
    NOT_REQUESTED:
        No criterion was supplied for this dimension.
    INCOMPLETE:
        A criterion was supplied but the dimension could not be
        evaluated because a required input was missing.
    """

    PASS = "pass"
    AT_BOUNDARY = "at_boundary"
    FAIL = "fail"
    NOT_REQUESTED = "not_requested"
    INCOMPLETE = "incomplete"


class ToleranceDecisionCovarianceEffect(Enum):
    """Deterministic effect of supplied correlations on combined sigma.

    Members
    -------
    NOT_REQUESTED:
        No correlations were supplied.
    INCREASES:
        Correlations increase the combined sigma versus the
        independent reference, beyond the equality tolerance.
    DECREASES:
        Correlations decrease the combined sigma versus the
        independent reference, beyond the equality tolerance.
    NEUTRAL:
        The independent and correlated combined sigmas agree within
        the equality tolerance.
    """

    NOT_REQUESTED = "not_requested"
    INCREASES = "increases"
    DECREASES = "decreases"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ToleranceDecisionSensitivity:
    """Deterministic controlling-contributor summary.

    Attributes
    ----------
    worst_case_controlling:
        Contributor IDs in deterministic order (most controlling first)
        based on the worst-case sensitivity engine.  Empty when no
        worst-case stack was supplied.
    statistical_controlling:
        Contributor IDs in deterministic order (most controlling first)
        based on the statistical variance-contribution engine.  Empty
        when no statistical stack was supplied.
    """

    worst_case_controlling: tuple[str, ...]
    statistical_controlling: tuple[str, ...]


@dataclass(frozen=True)
class ToleranceDecisionEvidence:
    """Structured numeric evidence supporting a decision result.

    All numeric fields use the established engineering equality policy
    (``1e-12``) for any boundary comparison.  None of the values are
    recomputed from formulas here; they are taken from the
    authoritative engines and from the decision-classification rules.
    """

    worst_case_actual_span: float | None
    worst_case_allowed_span: float | None
    worst_case_margin: float | None
    worst_case_utilization_fraction: float | None
    statistical_actual_combined_sigma: float | None
    statistical_allowed_combined_sigma: float | None
    statistical_independent_combined_sigma: float | None
    statistical_margin: float | None
    statistical_utilization_fraction: float | None
    equality_tolerance: float


@dataclass(frozen=True)
class ToleranceDecisionDimension:
    """A single evaluation dimension within a decision result.

    Each dimension is one of: worst-case requirement, statistical
    requirement, worst-case allocation reconciliation, or statistical
    allocation reconciliation.
    """

    name: str
    state: ToleranceDecisionEvaluationState
    actual: float | None
    allowed: float | None
    margin: float | None


@dataclass(frozen=True)
class ToleranceDecisionResult:
    """Result of a deterministic tolerance decision evaluation.

    Attributes
    ----------
    overall_status:
        The deterministic overall engineering decision status
        (PASS, MARGINAL, FAIL, INCOMPLETE).
    dimensions:
        Ordered sequence of per-dimension evaluation outcomes.
    worst_case_passed:
        Convenience boolean reflecting only the worst-case requirement
        dimension.  ``None`` when the worst-case requirement was not
        requested.
    statistical_passed:
        Convenience boolean reflecting only the statistical requirement
        dimension.  ``None`` when the statistical requirement was not
        requested.
    worst_case_reconciliation_passed:
        Convenience boolean reflecting only the worst-case allocation
        reconciliation dimension.  ``None`` when no worst-case
        allocation plan was supplied.
    statistical_reconciliation_passed:
        Convenience boolean reflecting only the statistical allocation
        reconciliation dimension.  ``None`` when no statistical
        allocation plan was supplied.
    sensitivity:
        Controlling-contributor summary from existing sensitivity
        engines.
    covariance_effect:
        Effect of supplied correlations on combined sigma.
    evidence:
        Structured numeric evidence.
    reasons:
        Ordered tuple of deterministic reason observations.  The
        ordering is deterministic.
    is_complete:
        ``True`` when every requested dimension was evaluated and no
        dimension reports an INCOMPLETE state.  ``False`` when at least
        one requested dimension is INCOMPLETE.
    """

    overall_status: ToleranceDecisionStatus
    dimensions: tuple[ToleranceDecisionDimension, ...]
    worst_case_passed: bool | None
    statistical_passed: bool | None
    worst_case_reconciliation_passed: bool | None
    statistical_reconciliation_passed: bool | None
    sensitivity: ToleranceDecisionSensitivity
    covariance_effect: ToleranceDecisionCovarianceEffect
    evidence: ToleranceDecisionEvidence
    reasons: tuple[ToleranceDecisionReason, ...]
    is_complete: bool
