"""Independent engineering tests for deterministic statistical allocation
reconciliation.

Stage 15J.  Every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test.  Statistical
allocation reconciliation compares a user-supplied sigma allocation plan
against actual statistical consumption from the authoritative Stage 15D/15E
engine.  It does not generate or optimize allocations.

Covered categories:

A. INDEPENDENT - ACTUAL BELOW ALLOCATED SIGMA
B. INDEPENDENT - AT ALLOCATION
C. INDEPENDENT - OVER ALLOCATION
D. ZERO ALLOCATION / ZERO ACTUAL SIGMA
E. ZERO ALLOCATION / NONZERO ACTUAL SIGMA
F. TWO-CONTRIBUTOR RSS TOTAL
G. THREE-CONTRIBUTOR RSS TOTAL
H. POSITIVE CORRELATION
I. NEGATIVE CORRELATION
J. OPPOSITE DIRECTIONS (sign-sensitive covariance)
K. PERFECT +1 CORRELATION
L. PERFECT -1 CORRELATION
M. INVALID CORRELATION
N. UNKNOWN CONTRIBUTOR
O. DUPLICATE ALLOCATION
P. INCOMPLETE PLAN (complete mode)
Q. PARTIAL PLAN (incomplete mode)
R. SIGMA MULTIPLIER
S. DETERMINISM
T. INPUT IMMUTABILITY
U. STAGE 15I WORST-CASE RECONCILIATION REGRESSION
V. FULL TOLERANCE REGRESSION (Stages 15C-R through 15I)
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    Correlation,
    InvalidCorrelationError,
    InvalidStatisticalAllocationError,
    StackDirection,
    StatisticalAllocation,
    StatisticalAllocationPlan,
    StatisticalAllocationReconciliationStatus,
    StatisticalAllocationStatus,
    StatisticalContribution,
    StatisticalStack,
    reconcile_statistical_allocation,
    statistical,
)


def _stat_stack_two() -> StatisticalStack:
    """Two contributors: A sigma=0.10, B sigma=0.20, both FORWARD."""
    return StatisticalStack(
        (StatisticalContribution("A", 0.0, 0.1), StatisticalContribution("B", 0.0, 0.2))
    )


def _stat_stack_three() -> StatisticalStack:
    """Three contributors: A sigma=0.10, B sigma=0.20, C sigma=0.30."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 0.0, 0.1),
            StatisticalContribution("B", 0.0, 0.2),
            StatisticalContribution("C", 0.0, 0.3),
        )
    )


def _plan_two(
    alloc_a: float, alloc_b: float, k: float = 3.0
) -> StatisticalAllocationPlan:
    return StatisticalAllocationPlan(
        sigma_multiplier=k,
        allocations=(
            StatisticalAllocation("A", alloc_a),
            StatisticalAllocation("B", alloc_b),
        ),
    )


def test_under_allocation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    result = reconcile_statistical_allocation(stack, plan)
    comp_a, comp_b = result.contributor_compliances
    assert comp_a.contributor_id == "A"
    assert comp_a.allocated_sigma == 0.2
    assert comp_a.actual_sigma == 0.1
    assert comp_a.sigma_margin == pytest.approx(0.1)
    assert comp_a.utilization_fraction == pytest.approx(0.5)
    assert comp_a.utilization_percentage == pytest.approx(50.0)
    assert comp_a.status is StatisticalAllocationStatus.UNDER_ALLOCATION
    assert comp_b.contributor_id == "B"
    assert comp_b.allocated_sigma == 0.3
    assert comp_b.actual_sigma == 0.2
    assert comp_b.sigma_margin == pytest.approx(0.1)
    assert comp_b.status is StatisticalAllocationStatus.UNDER_ALLOCATION
    alloc_combined = math.sqrt(0.2**2 + 0.3**2)
    actual_combined = math.sqrt(0.1**2 + 0.2**2)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert result.actual_combined_sigma == pytest.approx(actual_combined)
    assert result.combined_sigma_margin == pytest.approx(
        alloc_combined - actual_combined
    )
    assert (
        result.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_WITHIN_ALLOCATION
    )
    assert result.is_complete is True
    assert result.missing_contributors == ()


def test_at_allocation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.1, 0.2)
    result = reconcile_statistical_allocation(stack, plan)
    comp_a, comp_b = result.contributor_compliances
    assert comp_a.status is StatisticalAllocationStatus.AT_ALLOCATION
    assert comp_a.sigma_margin == pytest.approx(0.0)
    assert comp_b.status is StatisticalAllocationStatus.AT_ALLOCATION
    assert comp_b.sigma_margin == pytest.approx(0.0)
    alloc_combined = math.sqrt(0.1**2 + 0.2**2)
    actually = math.sqrt(0.1**2 + 0.2**2)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert result.actual_combined_sigma == pytest.approx(actually)
    assert result.combined_sigma_margin == pytest.approx(0.0, abs=1e-12)
    assert (
        result.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_AT_ALLOCATION
    )


def test_over_allocation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.05, 0.1)
    result = reconcile_statistical_allocation(stack, plan)
    comp_a, comp_b = result.contributor_compliances
    assert comp_a.status is StatisticalAllocationStatus.OVER_ALLOCATION
    assert comp_a.sigma_margin == pytest.approx(-0.05)
    assert comp_b.status is StatisticalAllocationStatus.OVER_ALLOCATION
    assert comp_b.sigma_margin == pytest.approx(-0.1)
    alloc_combined = math.sqrt(0.05**2 + 0.1**2)
    actual_combined = math.sqrt(0.1**2 + 0.2**2)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert result.actual_combined_sigma == pytest.approx(actual_combined)
    assert result.combined_sigma_margin == pytest.approx(
        alloc_combined - actual_combined
    )
    assert (
        result.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_EXCEEDS_ALLOCATION
    )


def test_zero_allocation_zero_actual() -> None:
    stack = StatisticalStack((StatisticalContribution("A", 0.0, 0.0),))
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0, allocations=(StatisticalAllocation("A", 0.0),)
    )
    result = reconcile_statistical_allocation(stack, plan)
    comp = result.contributor_compliances[0]
    assert comp.allocated_sigma == 0.0
    assert comp.actual_sigma == 0.0
    assert comp.sigma_margin == 0.0
    assert comp.utilization_fraction is None
    assert comp.utilization_percentage is None
    assert comp.status is StatisticalAllocationStatus.AT_ALLOCATION
    assert result.allocated_combined_sigma == 0.0
    assert result.actual_combined_sigma == 0.0
    assert result.combined_sigma_margin == 0.0
    assert (
        result.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_AT_ALLOCATION
    )


def test_zero_allocation_nonzero_actual() -> None:
    stack = StatisticalStack((StatisticalContribution("A", 0.0, 0.1),))
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0, allocations=(StatisticalAllocation("A", 0.0),)
    )
    result = reconcile_statistical_allocation(stack, plan)
    comp = result.contributor_compliances[0]
    assert comp.allocated_sigma == 0.0
    assert comp.actual_sigma == 0.1
    assert comp.sigma_margin == pytest.approx(-0.1)
    assert comp.utilization_fraction is None
    assert comp.utilization_percentage is None
    assert comp.status is StatisticalAllocationStatus.OVER_ALLOCATION
    assert result.allocated_combined_sigma == 0.0
    assert result.actual_combined_sigma == pytest.approx(0.1)
    assert result.combined_sigma_margin == pytest.approx(-0.1)
    assert (
        result.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_EXCEEDS_ALLOCATION
    )


def test_two_contributor_rss() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    result = reconcile_statistical_allocation(stack, plan)
    alloc_expected = math.sqrt(0.2**2 + 0.3**2)
    actual_expected = math.sqrt(0.1**2 + 0.2**2)
    assert result.allocated_combined_sigma == pytest.approx(alloc_expected)
    assert result.actual_combined_sigma == pytest.approx(actual_expected)
    assert result.combined_sigma_margin == pytest.approx(
        alloc_expected - actual_expected
    )
    assert result.correlation_impacts == ()
    assert result.sigma_multiplier == 3.0


def test_three_contributor_rss() -> None:
    stack = _stat_stack_three()
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(
            StatisticalAllocation("A", 0.15),
            StatisticalAllocation("B", 0.25),
            StatisticalAllocation("C", 0.35),
        ),
    )
    result = reconcile_statistical_allocation(stack, plan)
    alloc_expected = math.sqrt(0.15**2 + 0.25**2 + 0.35**2)
    actual_expected = math.sqrt(0.1**2 + 0.2**2 + 0.3**2)
    assert result.allocated_combined_sigma == pytest.approx(alloc_expected)
    assert result.actual_combined_sigma == pytest.approx(actual_expected)
    assert result.combined_sigma_margin == pytest.approx(
        alloc_expected - actual_expected
    )


def test_positive_correlation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    corr = (Correlation("A", "B", 0.5),)
    result = reconcile_statistical_allocation(stack, plan, correlations=corr)
    alloc_var = 0.2**2 + 0.3**2 + 2.0 * 0.5 * 0.2 * 0.3
    alloc_combined = math.sqrt(alloc_var)
    actual_var = 0.1**2 + 0.2**2 + 2.0 * 0.5 * 0.1 * 0.2
    actual_combined = math.sqrt(actual_var)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert result.actual_combined_sigma == pytest.approx(actual_combined)
    assert len(result.correlation_impacts) == 1
    impact = result.correlation_impacts[0]
    assert impact.first_contributor == "A"
    assert impact.second_contributor == "B"
    assert impact.coefficient == 0.5
    assert impact.variance_contribution == pytest.approx(2.0 * 0.5 * 0.2 * 0.3)


# ---------------------------------------------------------------------------
# I. Negative correlation
# ---------------------------------------------------------------------------


def test_negative_correlation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    corr = (Correlation("A", "B", -0.5),)
    result = reconcile_statistical_allocation(stack, plan, correlations=corr)

    alloc_var = 0.2**2 + 0.3**2 + 2.0 * (-0.5) * 0.2 * 0.3
    alloc_combined = math.sqrt(alloc_var)
    actual_var = 0.1**2 + 0.2**2 + 2.0 * (-0.5) * 0.1 * 0.2
    actual_combined = math.sqrt(actual_var)

    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert result.actual_combined_sigma == pytest.approx(actual_combined)
    assert len(result.correlation_impacts) == 1
    assert result.correlation_impacts[0].variance_contribution == pytest.approx(
        2.0 * (-0.5) * 0.2 * 0.3
    )


# ---------------------------------------------------------------------------
# J. Opposite directions (sign-sensitive covariance)
# ---------------------------------------------------------------------------


def test_opposite_directions() -> None:
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 0.0, 0.1, StackDirection.FORWARD),
            StatisticalContribution("B", 0.0, 0.2, StackDirection.INVERSE),
        )
    )
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(
            StatisticalAllocation("A", 0.2),
            StatisticalAllocation("B", 0.3),
        ),
    )
    corr = (Correlation("A", "B", 0.5),)
    result = reconcile_statistical_allocation(stack, plan, correlations=corr)

    # Cov term: 2 * (+1) * (-1) * 0.5 * 0.2 * 0.3 = -0.06
    assert result.correlation_impacts[0].variance_contribution == pytest.approx(-0.06)
    alloc_var = 0.2**2 + 0.3**2 + 2.0 * 1.0 * (-1.0) * 0.5 * 0.2 * 0.3
    assert result.allocated_combined_sigma == pytest.approx(math.sqrt(alloc_var))


# ---------------------------------------------------------------------------
# K. Perfect +1 correlation
# ---------------------------------------------------------------------------


def test_perfect_plus_one_correlation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    corr = (Correlation("A", "B", 1.0),)
    result = reconcile_statistical_allocation(stack, plan, correlations=corr)

    alloc_combined = math.sqrt(0.2**2 + 0.3**2 + 2.0 * 0.2 * 0.3)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert alloc_combined == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# L. Perfect -1 correlation
# ---------------------------------------------------------------------------


def test_perfect_minus_one_correlation() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    corr = (Correlation("A", "B", -1.0),)
    result = reconcile_statistical_allocation(stack, plan, correlations=corr)

    alloc_combined = math.sqrt(0.2**2 + 0.3**2 - 2.0 * 0.2 * 0.3)
    assert result.allocated_combined_sigma == pytest.approx(alloc_combined)
    assert alloc_combined == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# M. Invalid correlation
# ---------------------------------------------------------------------------


def test_invalid_correlation_rho_above_one() -> None:
    """Correlation validation rejects rho > 1.0."""
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", 1.5)


def test_invalid_correlation_rho_below_minus_one() -> None:
    """Correlation validation rejects rho < -1.0."""
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", -1.5)


def test_invalid_correlation_unknown_contributor() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    bad = (Correlation("X", "B", 0.5),)
    with pytest.raises(InvalidCorrelationError):
        reconcile_statistical_allocation(stack, plan, correlations=bad)


# ---------------------------------------------------------------------------
# N. Unknown contributor in plan
# ---------------------------------------------------------------------------


def test_unknown_contributor_rejected() -> None:
    stack = _stat_stack_two()
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(
            StatisticalAllocation("A", 0.2),
            StatisticalAllocation("Z", 0.3),
        ),
    )
    with pytest.raises(InvalidStatisticalAllocationError):
        reconcile_statistical_allocation(stack, plan)


# ---------------------------------------------------------------------------
# O. Duplicate allocation
# ---------------------------------------------------------------------------


def test_duplicate_allocation_rejected_by_plan_constructor() -> None:
    with pytest.raises(InvalidStatisticalAllocationError):
        StatisticalAllocationPlan(
            sigma_multiplier=3.0,
            allocations=(
                StatisticalAllocation("A", 0.1),
                StatisticalAllocation("A", 0.2),
            ),
        )


# ---------------------------------------------------------------------------
# P. Incomplete plan in complete mode
# ---------------------------------------------------------------------------


def test_incomplete_plan_rejected_complete_mode() -> None:
    stack = _stat_stack_two()
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(StatisticalAllocation("A", 0.2),),
    )
    with pytest.raises(InvalidStatisticalAllocationError):
        reconcile_statistical_allocation(stack, plan, require_complete=True)


# ---------------------------------------------------------------------------
# Q. Partial plan accepted in incomplete mode
# ---------------------------------------------------------------------------


def test_partial_plan_accepted_incomplete_mode() -> None:
    stack = _stat_stack_two()
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(StatisticalAllocation("A", 0.2),),
    )
    result = reconcile_statistical_allocation(stack, plan, require_complete=False)
    assert result.is_complete is False
    assert "B" in result.missing_contributors
    comp_b = result.contributor_compliances[1]
    assert comp_b.contributor_id == "B"
    assert comp_b.allocated_sigma == 0.0
    assert comp_b.actual_sigma == 0.2
    assert comp_b.utilization_fraction is None
    assert comp_b.utilization_percentage is None
    assert comp_b.status is StatisticalAllocationStatus.OVER_ALLOCATION


# ---------------------------------------------------------------------------
# R. Sigma multiplier
# ---------------------------------------------------------------------------


def test_sigma_multiplier_propagated() -> None:
    stack = _stat_stack_two()
    plan = StatisticalAllocationPlan(
        sigma_multiplier=2.0,
        allocations=(
            StatisticalAllocation("A", 0.2),
            StatisticalAllocation("B", 0.3),
        ),
    )
    result = reconcile_statistical_allocation(stack, plan)
    assert result.sigma_multiplier == 2.0


def test_invalid_sigma_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalAllocationError):
        StatisticalAllocationPlan(
            sigma_multiplier=0.0,
            allocations=(StatisticalAllocation("A", 0.2),),
        )
    with pytest.raises(InvalidStatisticalAllocationError):
        StatisticalAllocationPlan(
            sigma_multiplier=-1.0,
            allocations=(StatisticalAllocation("A", 0.2),),
        )


def test_nan_sigma_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalAllocationError):
        StatisticalAllocationPlan(
            sigma_multiplier=float("nan"),
            allocations=(StatisticalAllocation("A", 0.2),),
        )


# ---------------------------------------------------------------------------
# S. Determinism
# ---------------------------------------------------------------------------


def test_determinism_repeated_calls() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    r1 = reconcile_statistical_allocation(stack, plan)
    r2 = reconcile_statistical_allocation(stack, plan)
    r3 = reconcile_statistical_allocation(stack, plan)
    assert r1 == r2 == r3


# ---------------------------------------------------------------------------
# T. Input immutability
# ---------------------------------------------------------------------------


def test_input_immutability() -> None:
    stack = _stat_stack_two()
    plan = _plan_two(0.2, 0.3)
    stack_snapshot = list(stack.contributions)
    plan_snapshot = list(plan.allocations)
    reconcile_statistical_allocation(stack, plan)
    assert list(stack.contributions) == stack_snapshot
    assert list(plan.allocations) == plan_snapshot


# ---------------------------------------------------------------------------
# U. Stage 15I worst-case reconciliation regression
# ---------------------------------------------------------------------------


def test_stage15i_reconcile_allocation_still_works() -> None:
    from origlyph.tolerance import (
        AllocationPlan,
        ToleranceAllocation,
        ToleranceContribution,
        ToleranceStack,
        reconcile_allocation,
    )

    wc_stack = ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )
    wc_plan = AllocationPlan(
        allowed_budget=0.50,
        allocations=(
            ToleranceAllocation("A", 0.30),
            ToleranceAllocation("B", 0.15),
        ),
    )
    res = reconcile_allocation(wc_stack, wc_plan)
    assert res.allowed_budget == 0.50
    assert res.allocated_total == pytest.approx(0.45)
    assert len(res.contributor_compliances) == 2


# ---------------------------------------------------------------------------
# V. Full tolerance regression - all stages still importable and working
# ---------------------------------------------------------------------------


def test_full_tolerance_regression_all_apis() -> None:
    from origlyph.tolerance import (
        reconcile_allocation,
        reconcile_statistical_allocation,
        statistical_budget,
        statistical_sensitivity,
        validate_allocation,
        worst_case,
        worst_case_budget,
        worst_case_sensitivity,
        worst_case_window_compliance,
    )

    assert callable(worst_case)
    assert callable(statistical)
    assert callable(worst_case_budget)
    assert callable(statistical_budget)
    assert callable(worst_case_sensitivity)
    assert callable(statistical_sensitivity)
    assert callable(worst_case_window_compliance)
    assert callable(validate_allocation)
    assert callable(reconcile_allocation)
    assert callable(reconcile_statistical_allocation)
