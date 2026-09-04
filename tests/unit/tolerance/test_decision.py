"""Independent engineering tests for deterministic tolerance decision layer.

Stage 15K. The decision layer orchestrates the existing
tolerance-analysis engines into one deterministic engineering
decision; these tests verify that orchestration against the
established equality policy (``1e-12``) and fail-closed behavior.

Covered categories: A simple PASS, B-C FAIL paths, D both FAIL,
E-F WC/Stat disagreement, G MARGINAL boundary, H-I WC allocation,
J-K Stat allocation, L zero allocation, M incomplete fail-closed,
N-P covariance effects, Q-R negative/zero covariance, S canonical
pair, T invalid rho, U-V sensitivity, W covariance classification,
X-Y no fabrication, Z immutability, AA repeatability, AB malformed
inputs, AC-AD prior-stage API, AE-AI prior-stage regression.
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    AllocationPlan,
    Correlation,
    StatisticalAllocation,
    StatisticalAllocationPlan,
    StatisticalAllocationReconciliationStatus,
    StatisticalContribution,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceDecisionCovarianceEffect,
    ToleranceDecisionReasonCode,
    ToleranceDecisionStatus,
    ToleranceStack,
    evaluate_tolerance_decision,
    reconcile_allocation,
    reconcile_statistical_allocation,
    statistical,
    worst_case,
)
from origlyph.tolerance.allocation import validate_allocation
from origlyph.tolerance.budget import (
    statistical_budget,
    worst_case_budget,
)
from origlyph.tolerance.exceptions import (
    InvalidAllocationError,
    InvalidCorrelationError,
    InvalidToleranceDecisionError,
)
from origlyph.tolerance.sensitivity import (
    statistical_sensitivity,
    worst_case_sensitivity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wc_stack() -> ToleranceStack:
    """A (span 0.30) + B (span 0.15): total worst-case span 0.45."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )


def _stat_stack() -> StatisticalStack:
    """A sigma=0.05, B sigma=0.05, both FORWARD."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 0.0, 0.05),
            StatisticalContribution("B", 0.0, 0.05),
        )
    )


def _wc_allocation(span_a: float, span_b: float) -> AllocationPlan:
    return AllocationPlan(
        allowed_budget=0.50,
        allocations=(
            ToleranceAllocation("A", span_a),
            ToleranceAllocation("B", span_b),
        ),
    )


def _stat_allocation(
    sigma_a: float, sigma_b: float, k: float = 3.0
) -> StatisticalAllocationPlan:
    return StatisticalAllocationPlan(
        sigma_multiplier=k,
        allocations=(
            StatisticalAllocation("A", sigma_a),
            StatisticalAllocation("B", sigma_b),
        ),
    )


# ---------------------------------------------------------------------------
# A. Simple PASS decision
# ---------------------------------------------------------------------------


def test_simple_pass_decision() -> None:
    """Both worst-case and statistical criteria pass cleanly."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )
    assert result.overall_status is ToleranceDecisionStatus.PASS
    assert result.worst_case_passed is True
    assert result.statistical_passed is True
    assert result.is_complete is True
    assert result.evidence.worst_case_actual_span == pytest.approx(0.45)
    assert result.evidence.statistical_actual_combined_sigma == pytest.approx(
        math.sqrt(0.05 ** 2 + 0.05 ** 2)
    )


# ---------------------------------------------------------------------------
# B. Hard worst-case FAIL
# ---------------------------------------------------------------------------


def test_hard_worst_case_fail() -> None:
    """Worst-case exceeds the allowed span."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.40,
    )
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.worst_case_passed is False
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# C. Statistical FAIL
# ---------------------------------------------------------------------------


def test_statistical_fail() -> None:
    """Statistical combined sigma exceeds the allowed combined sigma."""
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        allowed_combined_sigma=0.05,
    )
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.statistical_passed is False
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.STAT_REQUIREMENT_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# D. Both analyses FAIL
# ---------------------------------------------------------------------------


def test_both_analyses_fail() -> None:
    """Worst-case and statistical both fail."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.40,
        allowed_combined_sigma=0.05,
    )
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED in reason_codes
    )
    assert (
        ToleranceDecisionReasonCode.STAT_REQUIREMENT_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# E. WC FAIL + stat PASS preserved
# ---------------------------------------------------------------------------


def test_wc_fail_stat_pass_preserved_as_disagreement() -> None:
    """Worst-case fails; statistical passes; both visible in result."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.40,
        allowed_combined_sigma=0.20,
    )
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.worst_case_passed is False
    assert result.statistical_passed is True
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED in reason_codes
    )
    assert (
        ToleranceDecisionReasonCode.WC_STAT_INCONSISTENT in reason_codes
    )


# ---------------------------------------------------------------------------
# F. WC PASS + stat FAIL preserved
# ---------------------------------------------------------------------------


def test_wc_pass_stat_fail_preserved_as_disagreement() -> None:
    """Worst-case passes; statistical fails; both visible in result."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.05,
    )
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.worst_case_passed is True
    assert result.statistical_passed is False
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_STAT_INCONSISTENT in reason_codes
    )
    assert (
        ToleranceDecisionReasonCode.STAT_REQUIREMENT_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# G. Exact-boundary / equality-policy behavior (MARGINAL)
# ---------------------------------------------------------------------------


def test_exact_boundary_marginal() -> None:
    """Decision is at the equality boundary -> MARGINAL."""
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.45,
    )
    assert result.overall_status is ToleranceDecisionStatus.MARGINAL
    assert result.worst_case_passed is True
    assert result.evidence.worst_case_actual_span == pytest.approx(0.45)
    assert result.evidence.worst_case_margin == pytest.approx(0.0, abs=1e-12)
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_REQUIREMENT_AT_BOUNDARY
        in reason_codes
    )


# ---------------------------------------------------------------------------
# H. Worst-case allocation compliant
# ---------------------------------------------------------------------------


def test_worst_case_allocation_compliant() -> None:
    """Worst-case allocation larger than actual total span -> PASS."""
    plan = _wc_allocation(0.30, 0.20)
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
        allowed_worst_case_span=0.50,
    )
    assert result.worst_case_reconciliation_passed is True
    assert result.overall_status is ToleranceDecisionStatus.PASS


# ---------------------------------------------------------------------------
# I. Worst-case allocation exceeded
# ---------------------------------------------------------------------------


def test_worst_case_allocation_exceeded() -> None:
    """Worst-case allocation smaller than actual -> FAIL."""
    plan = _wc_allocation(0.20, 0.10)
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
    )
    assert result.worst_case_reconciliation_passed is False
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.WC_ALLOCATION_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# J. Statistical allocation compliant
# ---------------------------------------------------------------------------


def test_statistical_allocation_compliant() -> None:
    plan = _stat_allocation(0.10, 0.10)
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        statistical_allocation=plan,
    )
    assert result.statistical_reconciliation_passed is True
    assert result.overall_status is ToleranceDecisionStatus.PASS


# ---------------------------------------------------------------------------
# K. Statistical allocation exceeded
# ---------------------------------------------------------------------------


def test_statistical_allocation_exceeded() -> None:
    plan = _stat_allocation(0.02, 0.02)
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        statistical_allocation=plan,
    )
    assert result.statistical_reconciliation_passed is False
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.STAT_ALLOCATION_EXCEEDED in reason_codes
    )


# ---------------------------------------------------------------------------
# L. Zero allocation behavior inherited
# ---------------------------------------------------------------------------


def test_zero_allocation_behavior_inherited() -> None:
    """Zero allocated sigma with non-zero actual -> over-allocation."""
    plan = _stat_allocation(0.0, 0.0)
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        statistical_allocation=plan,
    )
    # Stat allocation dimension reports a fail (over allocation).
    assert result.statistical_reconciliation_passed is False
    assert result.overall_status is ToleranceDecisionStatus.FAIL


# ---------------------------------------------------------------------------
# M. Incomplete allocation fail-closed behavior
# ---------------------------------------------------------------------------


def test_incomplete_allocation_fail_closed() -> None:
    """Incomplete worst-case allocation in complete mode raises."""
    plan = AllocationPlan(
        allowed_budget=0.50,
        allocations=(ToleranceAllocation("A", 0.20),),
    )
    # Complete mode: the underlying allocation validation raises.
    with pytest.raises(InvalidAllocationError):
        evaluate_tolerance_decision(
            worst_case_stack=_wc_stack(),
            worst_case_allocation=plan,
        )
    # Incomplete mode: the decision layer surfaces an INCOMPLETE/FAIL
    # decision with a deterministic reason.
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
        require_complete=False,
    )
    assert result.worst_case_reconciliation_passed is False
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.INCOMPLETE_ALLOCATION in reason_codes
    )


# ---------------------------------------------------------------------------
# N. Independent RSS mode
# ---------------------------------------------------------------------------


def test_independent_rss_mode() -> None:
    """No correlations -> independent RSS propagation."""
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        allowed_combined_sigma=0.20,
    )
    expected = math.sqrt(0.05 ** 2 + 0.05 ** 2)
    assert result.evidence.statistical_actual_combined_sigma == pytest.approx(
        expected
    )
    assert result.covariance_effect is (
        ToleranceDecisionCovarianceEffect.NOT_REQUESTED
    )


# ---------------------------------------------------------------------------
# O. Correlated statistical mode
# ---------------------------------------------------------------------------


def test_correlated_statistical_mode() -> None:
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        allowed_combined_sigma=0.20,
        correlations=(Correlation("A", "B", 1.0),),
    )
    assert result.evidence.statistical_actual_combined_sigma == pytest.approx(
        0.10
    )
    assert result.covariance_effect is (
        ToleranceDecisionCovarianceEffect.INCREASES
    )


# ---------------------------------------------------------------------------
# P. Positive covariance increases sigma
# ---------------------------------------------------------------------------


def test_positive_covariance_increases_sigma() -> None:
    corr = (Correlation("A", "B", 0.5),)
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=corr,
    )
    expected = math.sqrt(0.0075)
    assert result.evidence.statistical_actual_combined_sigma == pytest.approx(
        expected
    )
    assert result.covariance_effect is (
        ToleranceDecisionCovarianceEffect.INCREASES
    )
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.CORRELATION_INCREASES_SIGMA
        in reason_codes
    )


# ---------------------------------------------------------------------------
# Q. Negative covariance reduces sigma
# ---------------------------------------------------------------------------


def test_negative_covariance_reduces_sigma() -> None:
    corr = (Correlation("A", "B", -0.5),)
    result = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=corr,
    )
    expected = math.sqrt(0.0025)
    assert result.evidence.statistical_actual_combined_sigma == pytest.approx(
        expected
    )
    assert result.covariance_effect is (
        ToleranceDecisionCovarianceEffect.DECREASES
    )
    reason_codes = [r.code for r in result.reasons]
    assert (
        ToleranceDecisionReasonCode.CORRELATION_DECREASES_SIGMA
        in reason_codes
    )


# ---------------------------------------------------------------------------
# R. Zero covariance equivalent to independent
# ---------------------------------------------------------------------------


def test_zero_covariance_equivalent_to_independent() -> None:
    result_corr = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", 0.0),),
    )
    result_indep = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
    )
    assert result_corr.evidence.statistical_actual_combined_sigma == (
        pytest.approx(result_indep.evidence.statistical_actual_combined_sigma)
    )
    assert result_corr.covariance_effect is (
        ToleranceDecisionCovarianceEffect.NEUTRAL
    )


# ---------------------------------------------------------------------------
# S. Canonical correlation-pair behavior
# ---------------------------------------------------------------------------


def test_canonical_correlation_pair() -> None:
    r1 = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", 0.5),),
    )
    r2 = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("B", "A", 0.5),),
    )
    assert r1.evidence.statistical_actual_combined_sigma == pytest.approx(
        r2.evidence.statistical_actual_combined_sigma
    )


# ---------------------------------------------------------------------------
# T. Invalid rho rejected
# ---------------------------------------------------------------------------


def test_invalid_rho_rejected() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", 1.5)
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", -1.5)


# ---------------------------------------------------------------------------
# U. Sensitivity controlling contributor
# ---------------------------------------------------------------------------


def test_sensitivity_controlling_contributor() -> None:
    result = evaluate_tolerance_decision(worst_case_stack=_wc_stack())
    assert result.sensitivity.worst_case_controlling[0] == "A"
    assert result.sensitivity.worst_case_controlling == ("A", "B")


# ---------------------------------------------------------------------------
# V. Deterministic contributor ordering
# ---------------------------------------------------------------------------


def test_deterministic_contributor_ordering_with_ties() -> None:
    stat = StatisticalStack(
        (
            StatisticalContribution("B", 0.0, 0.10),
            StatisticalContribution("A", 0.0, 0.10),
        )
    )
    result = evaluate_tolerance_decision(statistical_stack=stat)
    assert result.sensitivity.statistical_controlling == ("A", "B")


# ---------------------------------------------------------------------------
# W. Covariance impact classification
# ---------------------------------------------------------------------------


def test_covariance_impact_classification() -> None:
    r1 = evaluate_tolerance_decision(statistical_stack=_stat_stack())
    assert r1.covariance_effect is (
        ToleranceDecisionCovarianceEffect.NOT_REQUESTED
    )
    r2 = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", 0.0),),
    )
    assert r2.covariance_effect is (
        ToleranceDecisionCovarianceEffect.NEUTRAL
    )
    r3 = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", 0.5),),
    )
    assert r3.covariance_effect is (
        ToleranceDecisionCovarianceEffect.INCREASES
    )
    r4 = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", -0.5),),
    )
    assert r4.covariance_effect is (
        ToleranceDecisionCovarianceEffect.DECREASES
    )


# ---------------------------------------------------------------------------
# X. Missing optional allocation plans
# ---------------------------------------------------------------------------


def test_missing_optional_allocation_plans() -> None:
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )
    assert result.worst_case_reconciliation_passed is None
    assert result.statistical_reconciliation_passed is None


# ---------------------------------------------------------------------------
# Y. No accidental allocation fabrication
# ---------------------------------------------------------------------------


def test_no_accidental_allocation_fabrication() -> None:
    result = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )
    assert result.worst_case_reconciliation_passed is None
    assert result.statistical_reconciliation_passed is None
    dim_names = [d.name for d in result.dimensions]
    assert "worst_case_allocation" not in dim_names
    assert "statistical_allocation" not in dim_names


# ---------------------------------------------------------------------------
# Z. Input immutability
# ---------------------------------------------------------------------------


def test_input_immutability() -> None:
    wc = _wc_stack()
    stat = _stat_stack()
    plan = _wc_allocation(0.30, 0.15)
    snap_wc_contributions = list(wc.contributions)
    snap_stat_contributions = list(stat.contributions)
    snap_plan = list(plan.allocations)
    evaluate_tolerance_decision(
        worst_case_stack=wc,
        statistical_stack=stat,
        worst_case_allocation=plan,
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )
    assert list(wc.contributions) == snap_wc_contributions
    assert list(stat.contributions) == snap_stat_contributions
    assert list(plan.allocations) == snap_plan


# ---------------------------------------------------------------------------
# AA. Repeatability
# ---------------------------------------------------------------------------


def test_repeatability_deterministic() -> None:
    kwargs = {
        "worst_case_stack": _wc_stack(),
        "statistical_stack": _stat_stack(),
        "allowed_worst_case_span": 0.50,
        "allowed_combined_sigma": 0.20,
    }
    r1 = evaluate_tolerance_decision(**kwargs)
    r2 = evaluate_tolerance_decision(**kwargs)
    r3 = evaluate_tolerance_decision(**kwargs)
    assert r1 == r2 == r3


# ---------------------------------------------------------------------------
# AB. Malformed inputs rejected
# ---------------------------------------------------------------------------


def test_no_stack_raises() -> None:
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision()


def test_invalid_sigma_multiplier_raises() -> None:
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            statistical_stack=_stat_stack(),
            sigma_multiplier=0.0,
        )
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            statistical_stack=_stat_stack(),
            sigma_multiplier=-1.0,
        )
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            statistical_stack=_stat_stack(),
            sigma_multiplier=float("nan"),
        )


def test_invalid_allowed_worst_case_span_raises() -> None:
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            worst_case_stack=_wc_stack(),
            allowed_worst_case_span=0.0,
        )
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            worst_case_stack=_wc_stack(),
            allowed_worst_case_span=-0.1,
        )


def test_invalid_allowed_combined_sigma_raises() -> None:
    with pytest.raises(InvalidToleranceDecisionError):
        evaluate_tolerance_decision(
            statistical_stack=_stat_stack(),
            allowed_combined_sigma=0.0,
        )


# ---------------------------------------------------------------------------
# AC. Stage 15I API unchanged
# ---------------------------------------------------------------------------


def test_stage15i_reconcile_allocation_unchanged() -> None:
    plan = _wc_allocation(0.30, 0.15)
    res = reconcile_allocation(_wc_stack(), plan)
    assert res.allowed_budget == 0.50
    assert res.allocated_total == pytest.approx(0.45)
    assert len(res.contributor_compliances) == 2


# ---------------------------------------------------------------------------
# AD. Stage 15J API unchanged
# ---------------------------------------------------------------------------


def test_stage15j_statistical_reconciliation_unchanged() -> None:
    plan = _stat_allocation(0.10, 0.10)
    res = reconcile_statistical_allocation(_stat_stack(), plan)
    assert res.allocated_combined_sigma == pytest.approx(
        math.sqrt(0.10 ** 2 + 0.10 ** 2)
    )
    assert res.actual_combined_sigma == pytest.approx(
        math.sqrt(0.05 ** 2 + 0.05 ** 2)
    )
    assert (
        res.actual_statistical_status
        is StatisticalAllocationReconciliationStatus.ACTUAL_WITHIN_ALLOCATION
    )


# ---------------------------------------------------------------------------
# AE. Worst-case engine regression
# ---------------------------------------------------------------------------


def test_worst_case_engine_regression() -> None:
    res = worst_case(_wc_stack())
    assert res.total_span == pytest.approx(0.45)
    assert res.minimum == pytest.approx(139.85)
    assert res.maximum == pytest.approx(140.30)


# ---------------------------------------------------------------------------
# AF. Statistical engine regression
# ---------------------------------------------------------------------------


def test_statistical_engine_regression() -> None:
    res = statistical(_stat_stack(), sigma_multiplier=3.0)
    assert res.combined_sigma == pytest.approx(
        math.sqrt(0.05 ** 2 + 0.05 ** 2)
    )
    assert res.sigma_multiplier == 3.0


# ---------------------------------------------------------------------------
# AG. Sensitivity regression
# ---------------------------------------------------------------------------


def test_sensitivity_engine_regression() -> None:
    res = worst_case_sensitivity(_wc_stack())
    names = [i.name for i in res.impacts]
    assert names == ["A", "B"]
    assert res.impacts[0].fraction == pytest.approx(0.30 / 0.45)
    res_stat = statistical_sensitivity(_stat_stack(), sigma_multiplier=3.0)
    assert res_stat.contributions[0].name == "A"


# ---------------------------------------------------------------------------
# AH. Budget regression
# ---------------------------------------------------------------------------


def test_budget_engine_regression() -> None:
    res = worst_case_budget(_wc_stack(), allowed_span=0.50)
    assert res.allowed_span == 0.50
    assert res.actual_span == pytest.approx(0.45)
    res_stat = statistical_budget(
        _stat_stack(), allowed_span=0.20
    )
    assert res_stat.allowed_span == 0.20


# ---------------------------------------------------------------------------
# AI. Allocation regression
# ---------------------------------------------------------------------------


def test_allocation_validation_regression() -> None:
    plan = _wc_allocation(0.30, 0.15)
    res = validate_allocation(_wc_stack(), plan)
    assert res.allowed_budget == 0.50
    assert res.allocated_total == pytest.approx(0.45)
    assert res.is_complete is True
