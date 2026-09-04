"""Independent engineering tests for deterministic tolerance allocation validation.

Stage 15H. Every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test. Allocation
validation checks a user-supplied plan; it does not generate or optimize
allocations.

Covered categories:

A. FULLY ALLOCATED
B. UNDER-ALLOCATED
C. OVER-ALLOCATED
D. INVALID BUDGET (zero, negative, NaN, +inf, -inf)
E. INVALID ALLOCATION (negative, NaN, +inf, -inf)
F. DUPLICATE CONTRIBUTOR
G. UNKNOWN CONTRIBUTOR
H. COMPLETE MODE — MISSING CONTRIBUTOR
I. INCOMPLETE MODE
J. ZERO ALLOCATION
K. ALL-ZERO PLAN
L. CURRENT-SPAN COMPARISON
M. ZERO CURRENT SPAN
N. FRACTION OF ALLOWED BUDGET
O. MIXED DIRECTIONS
P. DETERMINISM
Q. INPUT IMMUTABILITY
R. WORST-CASE REGRESSION
S. INDEPENDENT RSS REGRESSION
T. CORRELATED RSS REGRESSION
U. SENSITIVITY REGRESSION
V. BUDGET REGRESSION
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    AllocationPlan,
    AllocationStatus,
    InvalidAllocationError,
    StackDirection,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceStack,
    validate_allocation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# A. FULLY ALLOCATED
# ---------------------------------------------------------------------------


def test_fully_allocated() -> None:
    """allowed = 1.0, allocations = 0.4 + 0.6 -> FULLY_ALLOCATED."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.6),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.allocated_total == 1.0
    assert result.remaining_unallocated == 0.0
    assert result.status is AllocationStatus.FULLY_ALLOCATED
    assert result.is_complete is True
    assert result.utilization_fraction == 1.0
    assert result.utilization_percentage == 100.0


# ---------------------------------------------------------------------------
# B. UNDER-ALLOCATED
# ---------------------------------------------------------------------------


def test_under_allocated() -> None:
    """allowed = 1.0, allocations total = 0.7 -> UNDER_ALLOCATED."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.3),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.allocated_total == pytest.approx(0.7)
    assert result.remaining_unallocated == pytest.approx(0.3)
    assert result.status is AllocationStatus.UNDER_ALLOCATED
    assert result.is_complete is True


# ---------------------------------------------------------------------------
# D. INVALID BUDGET
# ---------------------------------------------------------------------------


def test_invalid_budget_zero() -> None:
    """Zero budget rejected."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=0.0,
            allocations=(ToleranceAllocation("A", 0.5),),
        )


def test_invalid_budget_negative() -> None:
    """Negative budget rejected."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=-1.0,
            allocations=(ToleranceAllocation("A", 0.5),),
        )


def test_invalid_budget_nan() -> None:
    """NaN budget rejected."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=math.nan,
            allocations=(ToleranceAllocation("A", 0.5),),
        )


def test_invalid_budget_positive_infinity() -> None:
    """+inf budget rejected."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=math.inf,
            allocations=(ToleranceAllocation("A", 0.5),),
        )


def test_invalid_budget_negative_infinity() -> None:
    """-inf budget rejected."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=-math.inf,
            allocations=(ToleranceAllocation("A", 0.5),),
        )


# ---------------------------------------------------------------------------
# E. INVALID ALLOCATION
# ---------------------------------------------------------------------------


def test_invalid_allocation_negative() -> None:
    """Negative allocated span rejected."""
    with pytest.raises(InvalidAllocationError):
        ToleranceAllocation("A", -0.1)


def test_invalid_allocation_nan() -> None:
    """NaN allocated span rejected."""
    with pytest.raises(InvalidAllocationError):
        ToleranceAllocation("A", math.nan)


def test_invalid_allocation_positive_infinity() -> None:
    """+inf allocated span rejected."""
    with pytest.raises(InvalidAllocationError):
        ToleranceAllocation("A", math.inf)


def test_invalid_allocation_negative_infinity() -> None:
    """-inf allocated span rejected."""
    with pytest.raises(InvalidAllocationError):
        ToleranceAllocation("A", -math.inf)


# ---------------------------------------------------------------------------
# F. DUPLICATE CONTRIBUTOR
# ---------------------------------------------------------------------------


def test_duplicate_contributor() -> None:
    """Duplicate contributor ID rejected at plan construction."""
    with pytest.raises(InvalidAllocationError):
        AllocationPlan(
            allowed_budget=1.0,
            allocations=(
                ToleranceAllocation("A", 0.5),
                ToleranceAllocation("A", 0.3),
            ),
        )


# ---------------------------------------------------------------------------
# G. UNKNOWN CONTRIBUTOR
# ---------------------------------------------------------------------------


def test_unknown_contributor() -> None:
    """Unknown contributor in plan raises InvalidAllocationError."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.5),
            ToleranceAllocation("Z", 0.3),
        ),
    )
    with pytest.raises(InvalidAllocationError):
        validate_allocation(stack, plan)


# ---------------------------------------------------------------------------
# H. COMPLETE MODE — MISSING CONTRIBUTOR
# ---------------------------------------------------------------------------


def test_complete_mode_missing_contributor() -> None:
    """Missing contributor with require_complete=True raises."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("A", 0.5),),
    )
    with pytest.raises(InvalidAllocationError):
        validate_allocation(stack, plan, require_complete=True)


# ---------------------------------------------------------------------------
# I. INCOMPLETE MODE
# ---------------------------------------------------------------------------


def test_incomplete_mode() -> None:
    """Partial plan accepted when require_complete=False."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("A", 0.5),),
    )
    result = validate_allocation(stack, plan, require_complete=False)
    assert result.is_complete is False
    assert "B" in result.missing_contributors
    assert result.status is AllocationStatus.UNDER_ALLOCATED


# ---------------------------------------------------------------------------
# J. ZERO ALLOCATION
# ---------------------------------------------------------------------------


def test_zero_allocation_valid() -> None:
    """Zero allocation is valid."""
    stack = _single_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Only", 0.0),),
    )
    result = validate_allocation(stack, plan)
    assert result.allocated_total == 0.0
    assert result.status is AllocationStatus.UNDER_ALLOCATED
    assert result.is_complete is True


# ---------------------------------------------------------------------------
# K. ALL-ZERO PLAN
# ---------------------------------------------------------------------------


def test_all_zero_plan() -> None:
    """All-zero plan is valid UNDER_ALLOCATED when budget > 0."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.0),
            ToleranceAllocation("B", 0.0),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.allocated_total == 0.0
    assert result.remaining_unallocated == 1.0
    assert result.status is AllocationStatus.UNDER_ALLOCATED


# ---------------------------------------------------------------------------
# L. CURRENT-SPAN COMPARISON
# ---------------------------------------------------------------------------


def test_current_span_comparison() -> None:
    """Verify hand-calculated current_span, delta_from_current."""
    stack = _simple_stack()
    # A: span = 0.20 - (-0.10) = 0.30
    # B: span = 0.10 - (-0.05) = 0.15
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.2),
        ),
    )
    result = validate_allocation(stack, plan)
    assert len(result.contributor_results) == 2

    a_result = result.contributor_results[0]
    assert a_result.contributor_id == "A"
    assert a_result.current_span == pytest.approx(0.30)
    assert a_result.allocated_span == pytest.approx(0.4)
    assert a_result.delta_from_current == pytest.approx(0.4 - 0.30)

    b_result = result.contributor_results[1]
    assert b_result.contributor_id == "B"
    assert b_result.current_span == pytest.approx(0.15)
    assert b_result.allocated_span == pytest.approx(0.2)
    assert b_result.delta_from_current == pytest.approx(0.2 - 0.15)


# ---------------------------------------------------------------------------
# M. ZERO CURRENT SPAN
# ---------------------------------------------------------------------------


def test_zero_current_span_no_division_by_zero() -> None:
    """Zero current span does not produce NaN or division-by-zero."""
    stack = _zero_span_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(ToleranceAllocation("Zero", 0.5),),
    )
    result = validate_allocation(stack, plan)
    assert result.contributor_results[0].current_span == 0.0
    assert result.contributor_results[0].allocated_span == 0.5
    assert result.contributor_results[0].delta_from_current == 0.5
    # fraction_of_allowed_budget should be valid (0.5 / 1.0 = 0.5)
    assert result.contributor_results[0].fraction_of_allowed_budget == 0.5
    # No NaN anywhere
    assert not math.isnan(result.contributor_results[0].fraction_of_allowed_budget)


# ---------------------------------------------------------------------------
# N. FRACTION OF ALLOWED BUDGET
# ---------------------------------------------------------------------------


def test_fraction_of_allowed_budget() -> None:
    """Hand-calculated fraction_of_allowed_budget."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=2.0,
        allocations=(
            ToleranceAllocation("A", 0.5),
            ToleranceAllocation("B", 0.3),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.contributor_results[0].fraction_of_allowed_budget == 0.5 / 2.0
    assert result.contributor_results[1].fraction_of_allowed_budget == 0.3 / 2.0


# ---------------------------------------------------------------------------
# O. MIXED DIRECTIONS
# ---------------------------------------------------------------------------


def test_mixed_directions_no_span_corruption() -> None:
    """Contributor direction must not corrupt span semantics."""
    stack = _mixed_stack()
    # A FORWARD: span = 0.30, B INVERSE: span = 0.15
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.25),
            ToleranceAllocation("B", 0.10),
        ),
    )
    result = validate_allocation(stack, plan)
    assert result.contributor_results[0].current_span == pytest.approx(0.30)
    assert result.contributor_results[1].current_span == pytest.approx(0.15)
    assert result.allocated_total == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# P. DETERMINISM
# ---------------------------------------------------------------------------


def test_determinism() -> None:
    """Repeated calls produce identical results and ordering."""
    stack = _simple_stack()
    plan = AllocationPlan(
        allowed_budget=1.0,
        allocations=(
            ToleranceAllocation("A", 0.4),
            ToleranceAllocation("B", 0.3),
        ),
    )
    result1 = validate_allocation(stack, plan)
    result2 = validate_allocation(stack, plan)
    assert result1 == result2
    assert result1.contributor_results == result2.contributor_results


# ---------------------------------------------------------------------------
# Q. INPUT IMMUTABILITY
# ---------------------------------------------------------------------------


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
    validate_allocation(stack, plan)
    assert stack.contributions is original_contributions
    assert plan.allocations is original_allocations


# ---------------------------------------------------------------------------
# R. WORST-CASE REGRESSION
# ---------------------------------------------------------------------------


def test_worst_case_regression() -> None:
    """Stage 15C-R tests remain passing."""
    from origlyph.tolerance import worst_case

    stack = _simple_stack()
    result = worst_case(stack)
    assert result.total_span == pytest.approx(0.45)
    assert result.nominal == pytest.approx(140.0)


# ---------------------------------------------------------------------------
# S. INDEPENDENT RSS REGRESSION
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# T. CORRELATED RSS REGRESSION
# ---------------------------------------------------------------------------


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
    # variance = 0.01 + 0.01 + 2*1*1*0.5*0.1*0.1 = 0.02 + 0.01 = 0.03
    assert result.combined_sigma == pytest.approx(math.sqrt(0.03))


# ---------------------------------------------------------------------------
# U. SENSITIVITY REGRESSION
# ---------------------------------------------------------------------------


def test_sensitivity_regression() -> None:
    """Stage 15F tests remain passing."""
    from origlyph.tolerance import worst_case_sensitivity

    stack = _simple_stack()
    result = worst_case_sensitivity(stack)
    assert result.total_span == pytest.approx(0.45)
    assert len(result.impacts) == 2


# ---------------------------------------------------------------------------
# V. BUDGET REGRESSION
# ---------------------------------------------------------------------------


def test_budget_regression() -> None:
    """Stage 15G tests remain passing."""
    from origlyph.tolerance import worst_case_budget

    stack = _simple_stack()
    result = worst_case_budget(stack, 0.5)
    assert result.actual_span == pytest.approx(0.45)
    assert result.allowed_span == pytest.approx(0.5)
