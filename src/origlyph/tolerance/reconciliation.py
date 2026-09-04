"""Deterministic allocation reconciliation (Stage 15I).

This module reconciles a user-supplied tolerance allocation plan against
actual authoritative tolerance consumption.

It answers:
- Is the allocation plan valid?
- How much tolerance is allocated?
- How much tolerance is actually consumed?
- Is actual consumption within the allocation?
- Which contributors are over their allocated span?
- Which contributors are under their allocated span?
- What allocation margin remains per contributor?
- Is total allocated budget consistent with actual engineering budget?

This is reconciliation and compliance analysis only. It does **not**:
- create a new allocation plan
- change tolerance values
- optimize allocations
- recommend which tolerances to loosen/tighten
- infer manufacturing capability
- use AI

Relationship to other stages
-----------------------------
* **Stage 15G** (budget): actual budget utilization.
* **Stage 15H** (allocation): validation of a user-supplied allocation plan.
* **Stage 15I** (reconciliation): comparison of validated allocation against
  actual engineering consumption.

These responsibilities are kept distinct. A fully allocated plan can still
fail actual engineering compliance. An under-allocated plan may still
temporarily contain actual consumption.

Equality policy
---------------
Reuses the established Origlyph tolerance numerical equality tolerance
(``1e-12``) from Stage 15G / Stage 15H. No new or contradictory epsilon
is introduced.

Numerical stability
-------------------
Sums use :func:`math.fsum`. Engineering values are never rounded internally.
"""

from __future__ import annotations

import math

from .allocation import _ALLOCATION_EQUALITY_TOLERANCE, validate_allocation
from .budget import _classify_status
from .models import (
    AllocationComplianceStatus,
    AllocationPlan,
    AllocationReconciliationResult,
    ContributorAllocationCompliance,
    ReconciliationStatus,
    ToleranceContribution,
    ToleranceStack,
)

__all__ = [
    "reconcile_allocation",
]


def _actual_span(contribution: ToleranceContribution) -> float:
    """Derive the actual tolerance span for a stack contributor.

    Uses the same semantics as Stage 15F / Stage 15G / Stage 15H:
    ``upper_deviation - lower_deviation``, always non-negative.
    """
    return contribution.upper_deviation - contribution.lower_deviation


def _contributor_compliance_status(
    actual_span: float,
    allocated_span: float,
) -> AllocationComplianceStatus:
    """Determine per-contributor allocation compliance status.

    When ``allocated_span == 0``:
    - ``actual_span == 0`` -> ``AT_ALLOCATION``
    - ``actual_span > 0`` -> ``OVER_ALLOCATION``
    """
    if allocated_span == 0.0:
        if actual_span == 0.0:
            return AllocationComplianceStatus.AT_ALLOCATION
        return AllocationComplianceStatus.OVER_ALLOCATION

    difference = actual_span - allocated_span
    if abs(difference) <= _ALLOCATION_EQUALITY_TOLERANCE:
        return AllocationComplianceStatus.AT_ALLOCATION
    if difference < 0.0:
        return AllocationComplianceStatus.UNDER_ALLOCATION
    return AllocationComplianceStatus.OVER_ALLOCATION


def _reconciliation_status(
    actual_total_span: float,
    allocated_total: float,
) -> ReconciliationStatus:
    """Determine total reconciliation status (actual vs allocated)."""
    difference = actual_total_span - allocated_total
    if abs(difference) <= _ALLOCATION_EQUALITY_TOLERANCE:
        return ReconciliationStatus.ACTUAL_AT_ALLOCATION
    if difference < 0.0:
        return ReconciliationStatus.ACTUAL_WITHIN_ALLOCATION
    return ReconciliationStatus.ACTUAL_EXCEEDS_ALLOCATION


def reconcile_allocation(
    stack: ToleranceStack,
    plan: AllocationPlan,
    *,
    require_complete: bool = True,
) -> AllocationReconciliationResult:
    """Reconcile a validated allocation plan against actual consumption.

    Determines whether actual tolerance consumption is within, at, or
    exceeding the allocated spans. Delegates plan validation to Stage 15H
    and reuses the authoritative engines for actual span computation.

    Parameters
    ----------
    stack:
        The existing tolerance stack to reconcile against.
    plan:
        The user-supplied allocation plan.
    require_complete:
        If ``True`` (default), all stack contributors must appear exactly
        once in the plan; missing contributors cause validation failure.

    Returns
    -------
    AllocationReconciliationResult
        The reconciliation result with total and per-contributor compliance.

    Raises
    ------
    InvalidAllocationError
        If the plan is invalid (propagated from Stage 15H validation).
    """
    # Validate the allocation plan using Stage 15H (raises on invalid)
    validation = validate_allocation(stack, plan, require_complete=require_complete)

    # Build lookup structures
    stack_contributions: dict[str, ToleranceContribution] = {}
    for contribution in stack.contributions:
        stack_contributions[contribution.name] = contribution

    allocation_by_id: dict[str, float] = {
        allocation.contributor_id: allocation.allocated_span
        for allocation in plan.allocations
    }

    # Compute per-contributor compliance in deterministic stack order
    contributor_compliances: list[ContributorAllocationCompliance] = []
    actual_spans: list[float] = []

    for contribution in stack.contributions:
        cid = contribution.name
        if cid not in allocation_by_id:
            continue

        allocated_span = allocation_by_id[cid]
        actual_span = _actual_span(contribution)
        actual_spans.append(actual_span)

        margin = allocated_span - actual_span
        status = _contributor_compliance_status(actual_span, allocated_span)

        # utilization_fraction is None when allocated_span == 0
        if allocated_span > 0.0:
            utilization_fraction = actual_span / allocated_span
            utilization_percentage = 100.0 * utilization_fraction
        else:
            utilization_fraction = None
            utilization_percentage = None

        contributor_compliances.append(
            ContributorAllocationCompliance(
                contributor_id=cid,
                allocated_span=allocated_span,
                actual_span=actual_span,
                margin=margin,
                utilization_fraction=utilization_fraction,
                utilization_percentage=utilization_percentage,
                status=status,
            )
        )

    # Compute totals
    allocated_total = validation.allocated_total
    actual_total_span = math.fsum(actual_spans)
    allowed_budget = plan.allowed_budget

    allocation_remaining = allowed_budget - allocated_total
    engineering_remaining_margin = allowed_budget - actual_total_span
    total_allocation_margin = allocated_total - actual_total_span

    # Determine statuses
    allocation_plan_status = validation.status
    engineering_budget_status = _classify_status(actual_total_span, allowed_budget)
    reconciliation_status = _reconciliation_status(actual_total_span, allocated_total)

    return AllocationReconciliationResult(
        allowed_budget=allowed_budget,
        allocated_total=allocated_total,
        actual_total_span=actual_total_span,
        allocation_remaining=allocation_remaining,
        engineering_remaining_margin=engineering_remaining_margin,
        total_allocation_margin=total_allocation_margin,
        allocation_plan_status=allocation_plan_status,
        engineering_budget_status=engineering_budget_status,
        reconciliation_status=reconciliation_status,
        contributor_compliances=tuple(contributor_compliances),
    )
