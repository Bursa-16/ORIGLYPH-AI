"""Deterministic statistical allocation reconciliation (Stage 15J).

This module reconciles a user-supplied *statistical* allocation plan
against actual statistical uncertainty consumption produced by the
authoritative Stage 15D/15E engine.

Stage 15I reconciles worst-case allocation (linear spans) vs worst-case
actual spans.  Stage 15J adds statistical reconciliation: allocated sigma
vs actual sigma.

These are different physical quantities and are never interchanged:

* Worst-case span = upper_deviation - lower_deviation (linear, absolute).
* Statistical sigma = standard deviation propagated via RSS / covariance.

The statistical allocation plan allocates sigma budgets per contributor;
reconciliation compares those against the actual sigma of each contributor
and the actual combined sigma from the authoritative statistical engine.

This module is reconciliation and compliance analysis only. It does **not**:

- create a new allocation plan
- change tolerance values
- optimize allocations
- recommend design actions
- infer manufacturing capability
- redistribute tolerance
- use AI

Equality policy
---------------
Reuses the deterministic engineering tolerance of 1e-12 from Stage 15G,
15H, and 15I. No new or contradictory epsilon is introduced.

Numerical stability
--------------------
Sums use math.fsum. Engineering values are never rounded internally.

Determinism
-----------
Identical inputs always produce identical outputs. No random sources,
timestamps, network access, or AI participation.
"""

from __future__ import annotations

import math

from .allocation import AllocationStatus
from .exceptions import (
    InvalidStatisticalAllocationError,
)
from .models import (
    Correlation,
    StackDirection,
    StatisticalAllocationCovarianceImpact,
    StatisticalAllocationPlan,
    StatisticalAllocationReconciliationResult,
    StatisticalAllocationReconciliationStatus,
    StatisticalAllocationStatus,
    StatisticalContributorCompliance,
    StatisticalResult,
    StatisticalStack,
)
from .statistical import _build_correlation_map, statistical

__all__ = [
    "reconcile_statistical_allocation",
]

# Reuse the same deterministic engineering equality tolerance as Stage 15G,
# 15H, and 15I. This is a deterministic engineering tolerance, not a
# statistical confidence interval.
_EQUALITY_TOLERANCE = 1e-12

_NEGLIGIBLE_VARIANCE = 1e-15


def _sign(direction: StackDirection) -> float:
    """Return the algebraic stack coefficient (+1 FORWARD, -1 INVERSE)."""
    if direction is StackDirection.FORWARD:
        return 1.0
    return -1.0


def _classify_sigma_margin(
    actual_sigma: float,
    allocated_sigma: float,
) -> StatisticalAllocationStatus:
    """Classify per-contributor sigma margin status.

    When allocated_sigma == 0:
    - actual_sigma == 0 -> AT_ALLOCATION
    - actual_sigma > 0 -> OVER_ALLOCATION
    """
    if allocated_sigma == 0.0:
        if actual_sigma == 0.0:
            return StatisticalAllocationStatus.AT_ALLOCATION
        return StatisticalAllocationStatus.OVER_ALLOCATION

    difference = actual_sigma - allocated_sigma
    if abs(difference) <= _EQUALITY_TOLERANCE:
        return StatisticalAllocationStatus.AT_ALLOCATION
    if difference < 0.0:
        return StatisticalAllocationStatus.UNDER_ALLOCATION
    return StatisticalAllocationStatus.OVER_ALLOCATION


def _classify_total_sigma_margin(
    actual_combined_sigma: float,
    allocated_combined_sigma: float,
) -> StatisticalAllocationReconciliationStatus:
    """Classify total reconciliation status (actual vs allocated sigma)."""
    difference = actual_combined_sigma - allocated_combined_sigma
    if abs(difference) <= _EQUALITY_TOLERANCE:
        return StatisticalAllocationReconciliationStatus.ACTUAL_AT_ALLOCATION
    if difference < 0.0:
        return StatisticalAllocationReconciliationStatus.ACTUAL_WITHIN_ALLOCATION
    return StatisticalAllocationReconciliationStatus.ACTUAL_EXCEEDS_ALLOCATION


def _classify_allocation_total(
    allocated_total: float,
    allowed_budget: float,
) -> AllocationStatus:
    """Classify whether allocated_total fills allowed_budget."""
    difference = allocated_total - allowed_budget
    if abs(difference) <= _EQUALITY_TOLERANCE:
        return AllocationStatus.FULLY_ALLOCATED
    if difference < 0.0:
        return AllocationStatus.UNDER_ALLOCATED
    return AllocationStatus.OVER_ALLOCATED


def _compute_allocation_variance(
    stack: StatisticalStack,
    plan: StatisticalAllocationPlan,
    corr_map: dict[tuple[str, str], float],
) -> tuple[float, tuple[StatisticalAllocationCovarianceImpact, ...]]:
    """Compute the allocation-side variance and covariance impacts."""
    signs = [_sign(cont.direction) for cont in stack.contributions]
    alloc_by_id: dict[str, float] = {
        alloc.contributor_id: alloc.allocated_sigma for alloc in plan.allocations
    }

    variance_terms: list[float] = []
    for i, contribution in enumerate(stack.contributions):
        if contribution.name not in alloc_by_id:
            continue
        a_i = signs[i]
        s_i = alloc_by_id[contribution.name]
        variance_terms.append(a_i * a_i * s_i * s_i)

    cov_impacts: list[StatisticalAllocationCovarianceImpact] = []
    for i in range(len(stack.contributions)):
        for j in range(i + 1, len(stack.contributions)):
            ci = stack.contributions[i]
            cj = stack.contributions[j]
            if ci.name not in alloc_by_id or cj.name not in alloc_by_id:
                continue
            first_name, second_name = sorted((ci.name, cj.name))
            rho = corr_map.get((first_name, second_name), 0.0)
            if rho == 0.0:
                continue
            a_i = signs[i]
            a_j = signs[j]
            s_i = alloc_by_id[ci.name]
            s_j = alloc_by_id[cj.name]
            cov_term = 2.0 * a_i * a_j * rho * s_i * s_j
            variance_terms.append(cov_term)
            cov_impacts.append(
                StatisticalAllocationCovarianceImpact(
                    first_contributor=first_name,
                    second_contributor=second_name,
                    coefficient=rho,
                    variance_contribution=cov_term,
                )
            )

    variance_sum = math.fsum(variance_terms)
    return variance_sum, tuple(cov_impacts)


def _build_contributor_compliances(
    stack: StatisticalStack,
    alloc_by_id: dict[str, float],
) -> tuple[StatisticalContributorCompliance, ...]:
    """Build per-contributor compliance results in stack order."""
    compliances: list[StatisticalContributorCompliance] = []
    for contribution in stack.contributions:
        actual_sigma = contribution.sigma
        allocated_sigma = alloc_by_id.get(contribution.name, 0.0)
        sigma_margin = allocated_sigma - actual_sigma
        if allocated_sigma > 0.0:
            utilization_fraction = actual_sigma / allocated_sigma
            utilization_percentage = 100.0 * utilization_fraction
        else:
            utilization_fraction = None
            utilization_percentage = None
        status = _classify_sigma_margin(actual_sigma, allocated_sigma)
        compliances.append(
            StatisticalContributorCompliance(
                contributor_id=contribution.name,
                allocated_sigma=allocated_sigma,
                actual_sigma=actual_sigma,
                sigma_margin=sigma_margin,
                utilization_fraction=utilization_fraction,
                utilization_percentage=utilization_percentage,
                status=status,
            )
        )
    return tuple(compliances)


def _resolve_allocation_plan_status(
    allocated_combined_sigma: float,
    plan: StatisticalAllocationPlan,
) -> AllocationStatus:
    """Classify the allocation plan against its total budget."""
    if plan.allowed_combined_sigma is None:
        return AllocationStatus.FULLY_ALLOCATED
    return _classify_allocation_total(
        allocated_combined_sigma, plan.allowed_combined_sigma
    )


def _validate_inputs(stack: object, plan: object) -> None:
    """Type-check primary inputs."""
    if not isinstance(stack, StatisticalStack):
        raise InvalidStatisticalAllocationError("stack must be a StatisticalStack")
    if not isinstance(plan, StatisticalAllocationPlan):
        raise InvalidStatisticalAllocationError(
            "plan must be a StatisticalAllocationPlan"
        )


def _build_alloc_by_id(
    plan: StatisticalAllocationPlan,
    stack_id_set: set[str],
) -> dict[str, float]:
    """Validate allocation entries and build id->sigma map."""
    alloc_by_id: dict[str, float] = {}
    for alloc in plan.allocations:
        if alloc.contributor_id not in stack_id_set:
            raise InvalidStatisticalAllocationError(
                f"unknown contributor in allocation: {alloc.contributor_id!r}"
            )
        if alloc.contributor_id in alloc_by_id:
            raise InvalidStatisticalAllocationError(
                f"duplicate allocation for contributor: {alloc.contributor_id!r}"
            )
        alloc_by_id[alloc.contributor_id] = alloc.allocated_sigma
    return alloc_by_id


def _find_missing_contributors(
    stack_contributor_ids: list[str],
    alloc_by_id: dict[str, float],
) -> list[str]:
    """Return stack contributors not present in the allocation map."""
    return [cid for cid in stack_contributor_ids if cid not in alloc_by_id]


def _enforce_completeness(missing: list[str], require_complete: bool) -> None:
    """Raise if the plan is incomplete but completeness is required."""
    if require_complete and missing:
        raise InvalidStatisticalAllocationError(
            f"allocation plan is incomplete; missing contributors: {missing}"
        )


def reconcile_statistical_allocation(
    stack: StatisticalStack,
    plan: StatisticalAllocationPlan,
    *,
    correlations: tuple[Correlation, ...] | None = None,
    require_complete: bool = True,
) -> StatisticalAllocationReconciliationResult:
    """Reconcile a statistical allocation plan against actual statistical consumption.

    Compares user-supplied sigma allocations against the actual sigma
    consumption produced by the authoritative Stage 15D/15E statistical engine.

    This is reconciliation analysis only. It does **not** generate,
    optimize, or redistribute allocations.

    Parameters
    ----------
    stack:
        The ordered statistical stack whose actual sigma consumption will be
        compared against the allocation plan. Must contain at least one
        contribution.
    plan:
        The user-supplied statistical allocation plan.
    correlations:
        Optional sequence of explicit pairwise correlations used for both
        the allocation-side variance computation and the actual statistical
        analysis, ensuring a valid like-for-like comparison.  Missing pairs
        default to rho = 0 (independent).
    require_complete:
        If True (default), all stack contributors must appear in the
        allocation plan; missing contributors cause failure.  If False,
        missing contributors are reported but do not cause failure.

    Returns
    -------
    StatisticalAllocationReconciliationResult
        The reconciliation result with total and per-contributor compliance.

    Raises
    ------
    InvalidStatisticalAllocationError
        If the plan is invalid, if require_complete is True and any stack
        contributor is missing from the plan, or if an allocation references
        a contributor not in the stack.
    InvalidStatisticalError
        Propagated from the underlying statistical engine if it rejects
        the stack.
    InvalidVarianceError
        Propagated if propagated variance becomes materially negative.
    """
    if not isinstance(stack, StatisticalStack):
        raise InvalidStatisticalAllocationError("stack must be a StatisticalStack")
    if not isinstance(plan, StatisticalAllocationPlan):
        raise InvalidStatisticalAllocationError(
            "plan must be a StatisticalAllocationPlan"
        )

    stack_contributor_ids = [cont.name for cont in stack.contributions]
    stack_id_set = set(stack_contributor_ids)
    alloc_by_id = _build_alloc_by_id(plan, stack_id_set)
    missing = _find_missing_contributors(stack_contributor_ids, alloc_by_id)
    _enforce_completeness(missing, require_complete)

    # --- Build canonical correlation lookup (reuses Stage 15E validation) ---
    corr_map = _build_correlation_map(stack, correlations)

    # --- Compute actual statistical result from authoritative engine ---
    actual_result: StatisticalResult = statistical(
        stack,
        sigma_multiplier=plan.sigma_multiplier,
        correlations=correlations,
    )

    # --- Compute allocation-side variance ---
    alloc_variance, cov_impacts = _compute_allocation_variance(stack, plan, corr_map)

    if alloc_variance < -_NEGLIGIBLE_VARIANCE:
        raise InvalidStatisticalAllocationError(
            f"allocation-side variance is materially negative ({alloc_variance}); "
            "correlation/allocation inputs may be inconsistent"
        )
    alloc_variance = max(alloc_variance, 0.0)
    allocated_combined_sigma = math.sqrt(alloc_variance)

    # --- Allocation plan status ---
    allocation_plan_status = _resolve_allocation_plan_status(
        allocated_combined_sigma, plan
    )

    # --- Per-contributor compliance ---
    contributor_compliances = _build_contributor_compliances(stack, alloc_by_id)

    # --- Total reconciliation ---
    actual_combined_sigma = actual_result.combined_sigma
    combined_sigma_margin = allocated_combined_sigma - actual_combined_sigma
    actual_statistical_status = _classify_total_sigma_margin(
        actual_combined_sigma, allocated_combined_sigma
    )

    return StatisticalAllocationReconciliationResult(
        sigma_multiplier=plan.sigma_multiplier,
        allocated_combined_sigma=allocated_combined_sigma,
        actual_combined_sigma=actual_combined_sigma,
        combined_sigma_margin=combined_sigma_margin,
        allocation_plan_status=allocation_plan_status,
        actual_statistical_status=actual_statistical_status,
        contributor_compliances=tuple(contributor_compliances),
        correlation_impacts=cov_impacts,
        missing_contributors=tuple(missing),
        is_complete=(len(missing) == 0),
    )
