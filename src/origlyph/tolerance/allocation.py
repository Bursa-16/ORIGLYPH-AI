"""Deterministic tolerance allocation validation (Stage 15H).

This module validates **user-supplied** tolerance allocation plans against
a stated budget and an existing tolerance stack.

Given:
- an explicit total tolerance budget
- contributor-level allocated tolerance spans

it determines whether the plan is:
- structurally valid
- complete
- internally consistent
- under-allocated
- fully allocated
- over-allocated
- compatible with the referenced tolerance stack

This module validates a supplied plan **only**. It does **not**:
- generate a new allocation
- redistribute tolerance
- optimize tolerance values
- choose which contributor should change
- recommend design changes
- infer manufacturing capability
- use AI

Allocation status vs. budget status
-------------------------------------
* **Allocation status** (:class:`AllocationStatus`): whether a *plan* is
  under-, fully, or over-allocated against its *stated budget*.
* **Budget status** (:class:`BudgetStatus`, Stage 15G): whether the
  *actual engineering consumption* is under, at, or over budget.

These are distinct concepts. A valid allocation plan does **not** prove
actual stack compliance.

Equality policy
---------------
``FULLY_ALLOCATED`` uses the same absolute-tolerance semantics as Stage 15G's
``AT_BUDGET``: an absolute tolerance of ``1e-12`` on the difference between
allocated total and allowed budget. This is a deterministic engineering
tolerance, not a statistical confidence interval.

Numerical stability
-------------------
Sums use :func:`math.fsum`. Engineering values are never rounded internally.
The established tolerance equality threshold is reused; no contradictory
epsilon is introduced.

Determinism
-----------
Identical inputs always produce identical outputs. There are no random
sources, no timestamps, no network access, no environment-dependent
behavior, and no AI participation in the calculation path.
"""

from __future__ import annotations

import math

from .exceptions import InvalidAllocationError
from .models import (
    AllocationContributorResult,
    AllocationPlan,
    AllocationStatus,
    AllocationValidationResult,
    ToleranceContribution,
    ToleranceStack,
)

__all__ = [
    "validate_allocation",
]

_ALLOCATION_EQUALITY_TOLERANCE = 1e-12


def _current_span(contribution: ToleranceContribution) -> float:
    """Derive the current tolerance span for a stack contributor.

    Uses the same semantics as Stage 15F / Stage 15G: the span is
    ``upper_deviation - lower_deviation``, always non-negative.
    """
    return contribution.upper_deviation - contribution.lower_deviation


def _compute_status(allocated_total: float, allowed_budget: float) -> AllocationStatus:
    """Compute allocation status using the established equality policy.

    ``FULLY_ALLOCATED`` when ``allocated_total`` equals ``allowed_budget``
    within ``_ALLOCATION_EQUALITY_TOLERANCE``; ``UNDER_ALLOCATED`` when
    below; ``OVER_ALLOCATED`` when above.
    """
    difference = allocated_total - allowed_budget
    if abs(difference) <= _ALLOCATION_EQUALITY_TOLERANCE:
        return AllocationStatus.FULLY_ALLOCATED
    if difference < 0.0:
        return AllocationStatus.UNDER_ALLOCATED
    return AllocationStatus.OVER_ALLOCATED


def validate_allocation(
    stack: ToleranceStack,
    plan: AllocationPlan,
    *,
    require_complete: bool = True,
) -> AllocationValidationResult:
    """Validate a user-supplied tolerance allocation plan.

    Determines whether the plan is structurally valid, complete,
    internally consistent, and correctly allocated against its stated
    budget. Performs stack-aware validation to detect unknown,
    duplicate, or missing contributors.

    Parameters
    ----------
    stack:
        The existing tolerance stack to validate the plan against.
        Must contain at least one contribution.
    plan:
        The user-supplied allocation plan containing the allowed budget
        and per-contributor allocated spans.
    require_complete:
        If ``True`` (default), all stack contributors must appear exactly
        once in the plan; missing contributors cause validation failure.
        If ``False``, partial allocation plans are accepted but the
        result explicitly reports incompleteness.

    Returns
    -------
    AllocationValidationResult
        The validation result with status, completeness, and
        per-contributor comparisons.

    Raises
    ------
    InvalidAllocationError
        If the plan references unknown contributors, or if
        ``require_complete=True`` and contributors are missing.
    """
    # Build lookup of stack contributors by name (preserves input order)
    stack_contributions: dict[str, ToleranceContribution] = {}
    for contribution in stack.contributions:
        stack_contributions[contribution.name] = contribution

    # Check for unknown contributors in the plan
    unknown_ids: list[str] = []
    for allocation in plan.allocations:
        if allocation.contributor_id not in stack_contributions:
            unknown_ids.append(allocation.contributor_id)

    if unknown_ids:
        raise InvalidAllocationError(
            f"unknown contributor(s) in allocation plan: {unknown_ids}"
        )

    # Check completeness
    allocated_ids: set[str] = {
        allocation.contributor_id for allocation in plan.allocations
    }
    missing_ids: list[str] = [
        name for name in stack_contributions if name not in allocated_ids
    ]

    is_complete = len(missing_ids) == 0

    if require_complete and not is_complete:
        raise InvalidAllocationError(
            f"incomplete allocation plan; missing contributor(s): {missing_ids}"
        )

    # Compute allocation totals using math.fsum for numerical stability
    allocated_total = math.fsum(
        allocation.allocated_span for allocation in plan.allocations
    )
    allowed_budget = plan.allowed_budget
    remaining_unallocated = allowed_budget - allocated_total
    utilization_fraction = allocated_total / allowed_budget
    utilization_percentage = 100.0 * utilization_fraction

    status = _compute_status(allocated_total, allowed_budget)

    # Build per-contributor results in deterministic stack input order
    contributor_results: list[AllocationContributorResult] = []
    allocation_by_id: dict[str, float] = {
        allocation.contributor_id: allocation.allocated_span
        for allocation in plan.allocations
    }
    for contribution in stack.contributions:
        cid = contribution.name
        if cid in allocation_by_id:
            allocated_span = allocation_by_id[cid]
            current_span = _current_span(contribution)
            delta_from_current = allocated_span - current_span
            fraction_of_allowed_budget = allocated_span / allowed_budget
            contributor_results.append(
                AllocationContributorResult(
                    contributor_id=cid,
                    allocated_span=allocated_span,
                    current_span=current_span,
                    delta_from_current=delta_from_current,
                    fraction_of_allowed_budget=fraction_of_allowed_budget,
                )
            )

    return AllocationValidationResult(
        allowed_budget=allowed_budget,
        allocated_total=allocated_total,
        remaining_unallocated=remaining_unallocated,
        utilization_fraction=utilization_fraction,
        utilization_percentage=utilization_percentage,
        status=status,
        is_complete=is_complete,
        contributor_results=tuple(contributor_results),
        missing_contributors=tuple(missing_ids),
    )
