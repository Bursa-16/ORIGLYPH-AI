"""Deterministic tolerance-budget compliance analysis (Stage 15G).

This module answers budget-compliance questions for 1D tolerance stacks:

* What tolerance budget is allowed?
* How much is consumed?
* How much margin remains?
* Is the stack UNDER_BUDGET, AT_BUDGET, or OVER_BUDGET?
* What share of the allowed budget is consumed by each contributor?

Budget analysis is **analysis only**. It does not:

* modify tolerances,
* optimize the stack,
* recommend design changes,
* infer manufacturing capability,
* use AI.

All authoritative numbers are delegated to the existing engines:

* Stage 15C-R worst-case engine (:func:`origlyph.tolerance.worst_case`)
* Stage 15D/15E statistical engine (:func:`origlyph.tolerance.statistical`)
* Stage 15F sensitivity analysis (:func:`origlyph.tolerance.sensitivity`)

Budget analysis evaluates compliance; it does not automatically
redistribute tolerances.

Statistical budget compliance does not imply worst-case compliance.

Sensitivity and budget analysis do not change authoritative tolerance
results.

AI does not override deterministic tolerance calculations.

Compliance semantics
---------------------

* ``UNDER_BUDGET``: ``actual_span < allowed_span`` (with equality
  tolerance). Positive remaining margin.
* ``AT_BUDGET``: ``actual_span`` equals ``allowed_span`` within a small
  deterministic tolerance (``_BUDGET_EQUALITY_TOLERANCE = 1e-12``).
* ``OVER_BUDGET``: ``actual_span > allowed_span`` (beyond tolerance).
  Negative remaining margin.

Zero-span policy
----------------

If the actual span is exactly zero, every contributor's
``share_of_consumed`` is ``0.0`` (no division is performed, no NaN or
infinity is produced). ``share_of_allowed`` is also ``0.0`` since each
contributor span is zero.

Equality policy
---------------

``AT_BUDGET`` is determined by an absolute tolerance of ``1e-12`` on the
difference between actual and allowed spans. This is a deterministic
engineering tolerance, not a statistical confidence interval.

Determinism
-----------

Identical inputs always produce identical outputs. There are no random
sources, no timestamps, no network access, no environment-dependent
behavior, and no AI participation in the calculation path.
"""

from __future__ import annotations

import math

from .exceptions import InvalidBudgetError
from .models import (
    BudgetStatus,
    Correlation,
    StackDirection,
    StatisticalBudgetResult,
    StatisticalContributionBudget,
    StatisticalStack,
    ToleranceStack,
    WorstCaseBudgetResult,
    WorstCaseContributionBudget,
    WorstCaseWindowResult,
)
from .sensitivity import statistical_sensitivity
from .worst_case import worst_case

__all__ = [
    "statistical_budget",
    "worst_case_budget",
    "worst_case_window_compliance",
]

_BUDGET_EQUALITY_TOLERANCE = 1e-12


def _validate_allowed_span(allowed_span: float) -> float:
    """Validate and return the allowed budget span.

    The allowed span must be finite and strictly positive. Zero, negative,
    NaN, and infinity are all rejected — invalid input is never silently
    repaired.

    Raises
    ------
    InvalidBudgetError
        If the allowed span is not finite and strictly positive.
    """
    value = float(allowed_span)
    if math.isnan(value):
        raise InvalidBudgetError(
            "allowed_span must be a finite number, got NaN"
        )
    if math.isinf(value):
        raise InvalidBudgetError(
            "allowed_span must be a finite number, got infinity"
        )
    if value <= 0.0:
        raise InvalidBudgetError(
            f"allowed_span must be strictly positive, got {value}"
        )
    return value


def _classify_status(actual_span: float, allowed_span: float) -> BudgetStatus:
    """Classify budget compliance status from actual and allowed spans.

    Uses an absolute equality tolerance to determine AT_BUDGET status.
    """
    diff = actual_span - allowed_span
    if abs(diff) <= _BUDGET_EQUALITY_TOLERANCE:
        return BudgetStatus.AT_BUDGET
    if diff < 0.0:
        return BudgetStatus.UNDER_BUDGET
    return BudgetStatus.OVER_BUDGET


def _sign(direction: StackDirection) -> float:
    """Return the algebraic stack coefficient (+1 FORWARD, -1 INVERSE)."""
    if direction is StackDirection.FORWARD:
        return 1.0
    return -1.0


def worst_case_budget(
    stack: ToleranceStack, allowed_span: float
) -> WorstCaseBudgetResult:
    """Compute deterministic worst-case tolerance-budget compliance.

    Parameters
    ----------
    stack:
        The ordered tolerance stack to analyse. Must contain at least one
        contribution.
    allowed_span:
        Maximum permitted worst-case span. Must be finite and strictly
        positive.

    Returns
    -------
    WorstCaseBudgetResult
        The deterministic worst-case budget compliance result.

    Raises
    ------
    InvalidBudgetError
        If ``allowed_span`` is not finite and strictly positive.
    InvalidStackError
        If the stack is empty (propagated from the authoritative engine).
    InvalidToleranceError
        If any contribution definition is invalid (propagated from the
        authoritative engine).
    """
    allowed = _validate_allowed_span(allowed_span)
    authoritative = worst_case(stack)

    actual_span = authoritative.total_span
    remaining = allowed - actual_span
    utilization = actual_span / allowed
    status = _classify_status(actual_span, allowed)

    # Per-contributor budget impacts.
    contributions: list[WorstCaseContributionBudget] = []
    for contribution in stack.contributions:
        lower, upper = contribution.interval()
        span = upper - lower
        signed_nominal = _sign(contribution.direction) * contribution.nominal
        lower_dev = lower - signed_nominal
        upper_dev = upper - signed_nominal

        if actual_span == 0.0:
            share_consumed = 0.0
        else:
            share_consumed = span / actual_span
        share_allowed = span / allowed

        contributions.append(
            WorstCaseContributionBudget(
                name=contribution.name,
                signed_nominal=signed_nominal,
                direction=contribution.direction,
                lower_deviation=lower_dev,
                upper_deviation=upper_dev,
                span=span,
                share_of_consumed=share_consumed,
                share_of_allowed=share_allowed,
                percentage_of_consumed=share_consumed * 100.0,
                percentage_of_allowed=share_allowed * 100.0,
            )
        )

    # Stable sort: descending span, ties keep original input order.
    contributions.sort(key=lambda c: c.span, reverse=True)

    return WorstCaseBudgetResult(
        nominal=authoritative.nominal,
        minimum=authoritative.minimum,
        maximum=authoritative.maximum,
        actual_span=actual_span,
        allowed_span=allowed,
        remaining_margin=remaining,
        utilization_fraction=utilization,
        utilization_percentage=utilization * 100.0,
        status=status,
        contributions=tuple(contributions),
    )


def statistical_budget(
    stack: StatisticalStack,
    allowed_span: float,
    sigma_multiplier: float = 3.0,
    correlations: tuple[Correlation, ...] | None = None,
) -> StatisticalBudgetResult:
    """Compute deterministic statistical tolerance-budget compliance.

    The statistical interval span is ``upper_bound - lower_bound`` from the
    authoritative statistical engine. Contributor shares reuse the variance
    decomposition from Stage 15F sensitivity analysis.

    Statistical budget compliance does NOT imply worst-case compliance.
    The two methods are separate and must be evaluated independently.

    Parameters
    ----------
    stack:
        The ordered statistical stack to analyse. Must contain at least one
        contribution.
    allowed_span:
        Maximum permitted statistical interval span. Must be finite and
        strictly positive.
    sigma_multiplier:
        Multiplier ``k`` applied to ``combined_sigma`` for bound computation.
        Must be finite and strictly positive.
    correlations:
        Optional sequence of explicit pairwise ``Correlation`` objects.
        Missing pairwise correlations default to ρ = 0 (independent).

    Returns
    -------
    StatisticalBudgetResult
        The deterministic statistical budget compliance result.

    Raises
    ------
    InvalidBudgetError
        If ``allowed_span`` is not finite and strictly positive.
    InvalidStatisticalError
        If the stack is empty or the multiplier is invalid.
    InvalidCorrelationError
        If any correlation references an unknown contributor or if a
        duplicate/conflicting pair is supplied.
    InvalidVarianceError
        If propagated variance becomes materially negative.
    """
    allowed = _validate_allowed_span(allowed_span)
    sensitivity = statistical_sensitivity(
        stack, sigma_multiplier=sigma_multiplier, correlations=correlations
    )

    # The actual span is the statistical interval width.
    actual_span = 2.0 * sensitivity.sigma_multiplier * sensitivity.combined_sigma
    remaining = allowed - actual_span
    utilization = actual_span / allowed
    status = _classify_status(actual_span, allowed)

    # Per-contributor budget impacts reuse sensitivity variance fractions.
    contributions: list[StatisticalContributionBudget] = []
    for impact in sensitivity.contributions:
        contributions.append(
            StatisticalContributionBudget(
                name=impact.name,
                direction=impact.direction,
                sigma=impact.sigma,
                variance=impact.variance,
                share_of_consumed=impact.fraction,
                share_of_allowed=impact.fraction * utilization,
                percentage_of_consumed=impact.percentage,
                percentage_of_allowed=impact.fraction * utilization * 100.0,
            )
        )

    # Covariance pairs are carried over unchanged from sensitivity analysis.
    covariance_pairs = sensitivity.covariance_pairs

    lower_bound = sensitivity.nominal - actual_span / 2.0
    upper_bound = sensitivity.nominal + actual_span / 2.0

    return StatisticalBudgetResult(
        nominal=sensitivity.nominal,
        combined_sigma=sensitivity.combined_sigma,
        sigma_multiplier=sensitivity.sigma_multiplier,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        actual_span=actual_span,
        allowed_span=allowed,
        remaining_margin=remaining,
        utilization_fraction=utilization,
        utilization_percentage=utilization * 100.0,
        status=status,
        contributions=tuple(contributions),
        covariance_pairs=covariance_pairs,
    )


def _validate_window_bounds(
    allowed_lower: float, allowed_upper: float
) -> tuple[float, float]:
    """Validate window bounds and return them as a tuple.

    Both bounds must be finite. ``allowed_lower`` must not exceed
    ``allowed_upper``.

    Raises
    ------
    InvalidBudgetError
        If either bound is non-finite or if the ordering is invalid.
    """
    lower = float(allowed_lower)
    upper = float(allowed_upper)
    if math.isnan(lower) or math.isinf(lower):
        raise InvalidBudgetError(
            "allowed_lower must be a finite number, got "
            f"{'NaN' if math.isnan(lower) else 'infinity'}"
        )
    if math.isnan(upper) or math.isinf(upper):
        raise InvalidBudgetError(
            "allowed_upper must be a finite number, got "
            f"{'NaN' if math.isnan(upper) else 'infinity'}"
        )
    if lower > upper:
        raise InvalidBudgetError(
            f"allowed_lower ({lower}) must not exceed "
            f"allowed_upper ({upper})"
        )
    return lower, upper


def worst_case_window_compliance(
    stack: ToleranceStack, allowed_lower: float, allowed_upper: float
) -> WorstCaseWindowResult:
    """Check whether the worst-case interval lies inside a permitted window.

    Window compliance is independent of span-based budget analysis. A stack
    can be within its span budget yet outside its permitted window, or
    vice versa.

    Parameters
    ----------
    stack:
        The ordered tolerance stack to analyse. Must contain at least one
        contribution.
    allowed_lower:
        Lower bound of the permitted window. Must be finite.
    allowed_upper:
        Upper bound of the permitted window. Must be finite and
        ``>= allowed_lower``.

    Returns
    -------
    WorstCaseWindowResult
        The window compliance result.

    Raises
    ------
    InvalidBudgetError
        If window bounds are non-finite or improperly ordered.
    InvalidStackError
        If the stack is empty (propagated from the authoritative engine).
    InvalidToleranceError
        If any contribution definition is invalid (propagated from the
        authoritative engine).
    """
    lower, upper = _validate_window_bounds(allowed_lower, allowed_upper)
    authoritative = worst_case(stack)

    is_compliant = bool(
        lower <= authoritative.minimum and authoritative.maximum <= upper
    )

    return WorstCaseWindowResult(
        nominal=authoritative.nominal,
        minimum=authoritative.minimum,
        maximum=authoritative.maximum,
        allowed_lower=lower,
        allowed_upper=upper,
        is_compliant=is_compliant,
    )
