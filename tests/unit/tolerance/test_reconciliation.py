"""Independent engineering tests for deterministic allocation reconciliation.

Stage 15I. Every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test.
Reconciliation compares a validated allocation plan with actual tolerance
consumption; it does not generate a new allocation.
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    AllocationComplianceStatus,
    AllocationPlan,
    AllocationStatus,
    BudgetStatus,
    InvalidAllocationError,
    ReconciliationStatus,
    StackDirection,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceStack,
    reconcile_allocation,
    validate_allocation,
)


def _simple_stack() -> ToleranceStack:
    """A (span 0.30) + B (span 0.15): total worst-case span 0.45."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )


def _mixed_stack() -> ToleranceStack:
    """A FORWARD (span 0.30) + B INVERSE (span 0.15): total span 0.45."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10, StackDirection.INVERSE),
        )
    )


def _single_stack() -> ToleranceStack:
    """Single contributor with span 0.50."""
    return ToleranceStack(
        (ToleranceContribution("Only", 50.0, -0.20, 0.30),)
    )


def _zero_span_stack() -> ToleranceStack:
    """Contributor with zero span."""
    return ToleranceStack(
        (ToleranceContribution("Zero", 100.0, 0.0, 0.0),)
    )


def test_actual_within_allocation() -> None:
    """allocated = 0.60, actual = 0.50 -> UNDER_ALLOCATION, margin = +0.10."""
    stack = _single_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Only", 0.60),),
    )
    result = reconcile_allocation(stack, plan)
    cc = result.contributor_compliances[0]
    assert cc.allocated_span == pytest.approx(0.60)
    assert cc.actual_span == pytest.approx(0.50)
    assert cc.margin == pytest.approx(0.10)
    assert cc.status is AllocationComplianceStatus.UNDER_ALLOCATION


def test_actual_at_allocation() -> None:
    """allocated == actual -> AT_ALLOCATION, margin = 0."""
    stack = _single_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Only", 0.50),),
    )
    result = reconcile_allocation(stack, plan)
    cc = result.contributor_compliances[0]
    assert cc.allocated_span == pytest.approx(0.50)
    assert cc.actual_span == pytest.approx(0.50)
    assert cc.margin == pytest.approx(0.0)
    assert cc.status is AllocationComplianceStatus.AT_ALLOCATION


def test_actual_exceeds_allocation() -> None:
    """allocated = 0.20, actual = 0.50 -> OVER_ALLOCATION, margin = -0.30."""
    stack = _single_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Only", 0.20),),
    )
    result = reconcile_allocation(stack, plan)
    cc = result.contributor_compliances[0]
    assert cc.allocated_span == pytest.approx(0.20)
    assert cc.actual_span == pytest.approx(0.50)
    assert cc.margin == pytest.approx(-0.30)
    assert cc.status is AllocationComplianceStatus.OVER_ALLOCATION


def test_zero_allocation_zero_actual() -> None:
    """Zero allocation and zero actual -> AT_ALLOCATION, no divide-by-zero."""
    stack = _zero_span_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Zero", 0.0),),
    )
    result = reconcile_allocation(stack, plan)
    cc = result.contributor_compliances[0]
    assert cc.allocated_span == pytest.approx(0.0)
    assert cc.actual_span == pytest.approx(0.0)
    assert cc.status is AllocationComplianceStatus.AT_ALLOCATION
    assert cc.utilization_fraction is None


def test_zero_allocation_nonzero_actual() -> None:
    """Zero allocation with nonzero actual -> OVER_ALLOCATION, no divide-by-zero."""
    stack = _single_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Only", 0.0),),
    )
    result = reconcile_allocation(stack, plan)
    cc = result.contributor_compliances[0]
    assert cc.allocated_span == pytest.approx(0.0)
    assert cc.actual_span == pytest.approx(0.50)
    assert cc.status is AllocationComplianceStatus.OVER_ALLOCATION
    assert cc.utilization_fraction is None


def test_total_reconciliation() -> None:
    """Hand-calculate allocated_total, actual_total, margins, overall status."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.40),
            ToleranceAllocation("B", 0.30),
        ),
    )
    result = reconcile_allocation(stack, plan)
    assert result.allocated_total == pytest.approx(0.70)
    assert result.actual_total_span == pytest.approx(0.45)
    assert result.allocation_remaining == pytest.approx(0.30)
    assert result.engineering_remaining_margin == pytest.approx(0.55)
    assert result.total_allocation_margin == pytest.approx(0.25)
    assert result.reconciliation_status is ReconciliationStatus.ACTUAL_WITHIN_ALLOCATION
    assert result.allocation_plan_status is AllocationStatus.UNDER_ALLOCATED
    assert result.engineering_budget_status is BudgetStatus.UNDER_BUDGET


def test_multiple_contributors_mixed_status() -> None:
    """Mix under/at/over contributors."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.50),
            ToleranceAllocation("B", 0.10),
        ),
    )
    result = reconcile_allocation(stack, plan)
    assert len(result.contributor_compliances) == 2
    assert (
        result.contributor_compliances[0].status
        is AllocationComplianceStatus.UNDER_ALLOCATION
    )
    assert (
        result.contributor_compliances[1].status
        is AllocationComplianceStatus.OVER_ALLOCATION
    )


def test_mixed_directions_no_span_corruption() -> None:
    """Direction must not corrupt actual span."""
    stack = _mixed_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.40),
            ToleranceAllocation("B", 0.20),
        ),
    )
    result = reconcile_allocation(stack, plan)
    assert result.contributor_compliances[0].actual_span == pytest.approx(0.30)
    assert result.contributor_compliances[1].actual_span == pytest.approx(0.15)
    assert result.actual_total_span == pytest.approx(0.45)


def test_asymmetric_tolerances() -> None:
    """Actual span comparison must remain correct with asymmetric tolerances."""
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 50.0, -0.05, 0.30),
            ToleranceContribution("B", 30.0, -0.10, 0.10),
        )
    )
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.40),
            ToleranceAllocation("B", 0.15),
        ),
    )
    result = reconcile_allocation(stack, plan)
    assert result.contributor_compliances[0].actual_span == pytest.approx(0.35)
    assert result.contributor_compliances[1].actual_span == pytest.approx(0.20)
    assert result.contributor_compliances[0].margin == pytest.approx(0.05)
    assert result.contributor_compliances[1].margin == pytest.approx(-0.05)


def test_invalid_plan_budget_zero() -> None:
    """Reconciliation must fail with invalid plan (zero budget)."""
    stack = _simple_stack()
    with pytest.raises(InvalidAllocationError):
        plan = AllocationPlan(
            allowed_budget=0.0,
            allocations=(ToleranceAllocation("A", 0.5),),
        )
        reconcile_allocation(stack, plan)


def test_unknown_contributor() -> None:
    """Unknown contributor must fail."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.5),
            ToleranceAllocation("Z", 0.3),
        ),
    )
    with pytest.raises(InvalidAllocationError):
        reconcile_allocation(stack, plan)


def test_incomplete_plan_complete_mode() -> None:
    """Incomplete plan must fail in complete mode."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("A", 0.5),),
    )
    with pytest.raises(InvalidAllocationError):
        reconcile_allocation(stack, plan, require_complete=True)


def test_incomplete_plan_incomplete_mode() -> None:
    """Incomplete plan accepted in incomplete mode."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("A", 0.5),),
    )
    result = reconcile_allocation(stack, plan, require_complete=False)
    assert len(result.contributor_compliances) == 1
    assert result.contributor_compliances[0].contributor_id == "A"


def test_determinism() -> None:
    """Repeated calls produce identical result and order."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.3),
        ),
    )
    result1 = reconcile_allocation(stack, plan)
    result2 = reconcile_allocation(stack, plan)
    assert result1 == result2
    assert result1.contributor_compliances == result2.contributor_compliances


def test_input_immutability() -> None:
    """Input stack and allocation plan must remain unchanged."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.3),
        ),
    )
    original_contributions = stack.contributions
    original_allocations = plan.allocations
    reconcile_allocation(stack, plan)
    assert stack.contributions is original_contributions
    assert plan.allocations is original_allocations


def test_worst_case_regression() -> None:
    """Stage 15C-R tests remain passing."""
    from origlyph.tolerance import worst_case

    stack = _simple_stack()
    result = worst_case(stack)
    assert result.total_span == pytest.approx(0.45)
    assert result.nominal == pytest.approx(140.0)


def test_independent_rss_regression() -> None:
    """Stage 15D tests remain passing."""
    from origlyph.tolerance import (
        StatisticalContribution,
        StatisticalStack,
        statistical,
    )

    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2),
        )
    )
    result = statistical(stack, sigma_multiplier=3.0)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.01 + 0.04))


def test_correlated_rss_regression() -> None:
    """Stage 15E tests remain passing."""
    from origlyph.tolerance import (
        Correlation,
        StatisticalContribution,
        StatisticalStack,
        statistical,
    )

    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.1),
            StatisticalContribution("B", 10.0, 0.1),
        )
    )
    correlations = (Correlation("A", "B", 0.5),)
    result = statistical(stack, sigma_multiplier=3.0, correlations=correlations)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.03))


def test_sensitivity_regression() -> None:
    """Stage 15F tests remain passing."""
    from origlyph.tolerance import worst_case_sensitivity

    stack = _simple_stack()
    result = worst_case_sensitivity(stack)
    assert result.total_span == pytest.approx(0.45)
    assert len(result.impacts) == 2


def test_budget_regression() -> None:
    """Stage 15G tests remain passing."""
    from origlyph.tolerance import worst_case_budget

    stack = _simple_stack()
    result = worst_case_budget(stack, 0.5)
    assert result.actual_span == pytest.approx(0.45)
    assert result.allowed_span == pytest.approx(0.5)


def test_allocation_regression() -> None:
    """Stage 15H tests remain passing."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.6),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.allocated_total == pytest.approx(1.0)
    assert result.status is AllocationStatus.FULLY_ALLOCATED
    assert result.is_complete is True
