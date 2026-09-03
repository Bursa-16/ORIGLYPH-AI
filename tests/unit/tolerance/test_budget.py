"""Independent engineering tests for deterministic tolerance-budget analysis.

Stage 15G. Every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test. Budget
analysis is compliance-only: these tests verify that authoritative engine
results are used unchanged, that inputs are never mutated, and that the
compliance semantics (UNDER/AT/OVER) are deterministic.

Covered categories:

A. worst-case UNDER_BUDGET / AT_BUDGET / OVER_BUDGET
B. invalid allowed span (zero, negative, NaN, +inf, -inf)
C. zero actual span policy
D. contributor share calculations
E. asymmetric tolerance stack
F. mixed stack directions
G. statistical under-budget / over-budget
H. correlated statistical budget
I. deterministic repeated execution
J. input immutability
K. window compliance
L. validation propagation from authoritative engines
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    BudgetStatus,
    Correlation,
    InvalidBudgetError,
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
    InvalidVarianceError,
    StackDirection,
    StatisticalContribution,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    statistical_budget,
    worst_case,
    worst_case_budget,
    worst_case_window_compliance,
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


def _wc_stack_mixed() -> ToleranceStack:
    """A FORWARD (span 0.30) - B INVERSE (span 0.15): total span 0.45."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10, StackDirection.INVERSE),
        )
    )


def _wc_stack_asymmetric() -> ToleranceStack:
    """A with asymmetric tolerance: +0.30/-0.05 (span 0.35)."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 50.0, -0.05, 0.30),
            ToleranceContribution("B", 30.0, -0.10, 0.10),
        )
    )


def _wc_zero_span_stack() -> ToleranceStack:
    """Zero-tolerance contributors: total span 0.0."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, 0.0, 0.0),
            ToleranceContribution("B", 40.0, 0.0, 0.0),
        )
    )


def _ss_stack() -> StatisticalStack:
    """A (sigma 0.1) + B (sigma 0.2): total variance 0.05."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2),
        )
    )


def _ss_stack_mixed() -> StatisticalStack:
    """A FORWARD (sigma 0.1) - B INVERSE (sigma 0.2)."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2, StackDirection.INVERSE),
        )
    )


# ---------------------------------------------------------------------------
# A. Worst-case UNDER_BUDGET / AT_BUDGET / OVER_BUDGET
# ---------------------------------------------------------------------------


def test_worst_case_under_budget() -> None:
    # Hand-calculated: total span 0.45, allowed 1.0.
    # remaining = 0.55, utilization = 0.45.
    result = worst_case_budget(_wc_stack(), 1.0)
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert math.isclose(result.actual_span, 0.45, abs_tol=1e-12)
    assert math.isclose(result.remaining_margin, 0.55, abs_tol=1e-12)
    assert math.isclose(result.utilization_fraction, 0.45, abs_tol=1e-12)
    assert math.isclose(result.utilization_percentage, 45.0, abs_tol=1e-12)


def test_worst_case_at_budget() -> None:
    # allowed == actual (within tolerance).
    result = worst_case_budget(_wc_stack(), 0.44999999999998863)
    assert result.status == BudgetStatus.AT_BUDGET


def test_worst_case_over_budget() -> None:
    # Hand-calculated: total span 0.45, allowed 0.30.
    # remaining = -0.15, utilization = 1.5.
    result = worst_case_budget(_wc_stack(), 0.30)
    assert result.status == BudgetStatus.OVER_BUDGET
    assert math.isclose(result.actual_span, 0.45, abs_tol=1e-12)
    assert math.isclose(result.remaining_margin, -0.15, abs_tol=1e-12)
    assert math.isclose(result.utilization_fraction, 1.5, abs_tol=1e-12)
    assert math.isclose(result.utilization_percentage, 150.0, abs_tol=1e-12)


def test_worst_case_budget_preserves_authoritative_fields() -> None:
    result = worst_case_budget(_wc_stack(), 1.0)
    authoritative = worst_case(_wc_stack())
    assert result.nominal == authoritative.nominal
    assert result.minimum == authoritative.minimum
    assert result.maximum == authoritative.maximum
    assert result.actual_span == authoritative.total_span


# ---------------------------------------------------------------------------
# B. Invalid allowed span
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_span", [0.0, -1.0, -0.001])
def test_worst_case_budget_rejects_non_positive_allowed_span(
    invalid_span: float,
) -> None:
    with pytest.raises(InvalidBudgetError, match="strictly positive"):
        worst_case_budget(_wc_stack(), invalid_span)


def test_worst_case_budget_rejects_nan_allowed_span() -> None:
    with pytest.raises(InvalidBudgetError, match="NaN"):
        worst_case_budget(_wc_stack(), math.nan)


def test_worst_case_budget_rejects_plus_infinity_allowed_span() -> None:
    with pytest.raises(InvalidBudgetError, match="infinity"):
        worst_case_budget(_wc_stack(), math.inf)


def test_worst_case_budget_rejects_minus_infinity_allowed_span() -> None:
    with pytest.raises(InvalidBudgetError, match="infinity"):
        worst_case_budget(_wc_stack(), -math.inf)


def test_statistical_budget_rejects_invalid_allowed_span() -> None:
    with pytest.raises(InvalidBudgetError):
        statistical_budget(_ss_stack(), 0.0, sigma_multiplier=3.0)
    with pytest.raises(InvalidBudgetError):
        statistical_budget(_ss_stack(), -1.0, sigma_multiplier=3.0)
    with pytest.raises(InvalidBudgetError):
        statistical_budget(_ss_stack(), math.nan, sigma_multiplier=3.0)
    with pytest.raises(InvalidBudgetError):
        statistical_budget(_ss_stack(), math.inf, sigma_multiplier=3.0)


# ---------------------------------------------------------------------------
# C. Zero actual span policy
# ---------------------------------------------------------------------------


def test_worst_case_budget_zero_span() -> None:
    # Zero total span: all shares are 0.0, utilization is 0.0.
    result = worst_case_budget(_wc_zero_span_stack(), 1.0)
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert result.actual_span == 0.0
    assert result.remaining_margin == 1.0
    assert result.utilization_fraction == 0.0
    assert result.utilization_percentage == 0.0
    for contribution in result.contributions:
        assert contribution.share_of_consumed == 0.0
        assert contribution.share_of_allowed == 0.0
        assert contribution.percentage_of_consumed == 0.0
        assert contribution.percentage_of_allowed == 0.0


# ---------------------------------------------------------------------------
# D. Contributor share calculations
# ---------------------------------------------------------------------------


def test_worst_case_budget_contributor_shares() -> None:
    # A: span 0.30, B: span 0.15, total 0.45, allowed 1.0.
    # A: share_consumed = 0.30/0.45 = 2/3, share_allowed = 0.30/1.0 = 0.30
    # B: share_consumed = 0.15/0.45 = 1/3, share_allowed = 0.15/1.0 = 0.15
    result = worst_case_budget(_wc_stack(), 1.0)
    assert len(result.contributions) == 2

    # Ordered by descending span: A first, B second.
    top, second = result.contributions
    assert top.name == "A"
    assert second.name == "B"

    assert math.isclose(top.span, 0.30, abs_tol=1e-12)
    assert math.isclose(top.share_of_consumed, 2.0 / 3.0, abs_tol=1e-12)
    assert math.isclose(top.share_of_allowed, 0.30, abs_tol=1e-12)
    assert math.isclose(top.percentage_of_consumed, 200.0 / 3.0, abs_tol=1e-12)
    assert math.isclose(top.percentage_of_allowed, 30.0, abs_tol=1e-12)

    assert math.isclose(second.span, 0.15, abs_tol=1e-12)
    assert math.isclose(second.share_of_consumed, 1.0 / 3.0, abs_tol=1e-12)
    assert math.isclose(second.share_of_allowed, 0.15, abs_tol=1e-12)


def test_worst_case_budget_shares_sum_to_one() -> None:
    result = worst_case_budget(_wc_stack(), 1.0)
    total_share = math.fsum(c.share_of_consumed for c in result.contributions)
    assert math.isclose(total_share, 1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# E. Asymmetric tolerance stack
# ---------------------------------------------------------------------------


def test_worst_case_budget_asymmetric_stack() -> None:
    # A: +0.30/-0.05 (span 0.35), B: +0.10/-0.10 (span 0.20).
    # Total span 0.55.
    result = worst_case_budget(_wc_stack_asymmetric(), 1.0)
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert math.isclose(result.actual_span, 0.55, abs_tol=1e-12)
    assert math.isclose(result.remaining_margin, 0.45, abs_tol=1e-12)
    assert math.isclose(result.utilization_fraction, 0.55, abs_tol=1e-12)

    top, second = result.contributions
    assert top.name == "A"
    assert second.name == "B"
    assert math.isclose(top.span, 0.35, abs_tol=1e-12)
    assert math.isclose(top.share_of_consumed, 0.35 / 0.55, abs_tol=1e-12)
    assert math.isclose(second.span, 0.20, abs_tol=1e-12)
    assert math.isclose(second.share_of_consumed, 0.20 / 0.55, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# F. Mixed stack directions
# ---------------------------------------------------------------------------


def test_worst_case_budget_mixed_directions() -> None:
    # A FORWARD (span 0.30) - B INVERSE (span 0.15): total span 0.45.
    result = worst_case_budget(_wc_stack_mixed(), 1.0)
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert math.isclose(result.actual_span, 0.45, abs_tol=1e-12)
    # Nominal should be 100 - 40 = 60.
    assert math.isclose(result.nominal, 60.0, abs_tol=1e-12)

    for contribution in result.contributions:
        if contribution.name == "A":
            assert contribution.direction is StackDirection.FORWARD
            assert contribution.signed_nominal == 100.0
        elif contribution.name == "B":
            assert contribution.direction is StackDirection.INVERSE
            assert contribution.signed_nominal == -40.0


# ---------------------------------------------------------------------------
# G. Statistical under-budget / over-budget
# ---------------------------------------------------------------------------


def test_statistical_budget_under_budget() -> None:
    # A (sigma 0.1) + B (sigma 0.2): combined_sigma = sqrt(0.05).
    # With k=3: interval span = 6 * sqrt(0.05) ~= 1.3416.
    result = statistical_budget(_ss_stack(), 2.0, sigma_multiplier=3.0)
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert math.isclose(
        result.actual_span, 6.0 * math.sqrt(0.05), abs_tol=1e-12
    )
    assert math.isclose(
        result.utilization_fraction, result.actual_span / 2.0, abs_tol=1e-12
    )
    assert result.remaining_margin > 0.0


def test_statistical_budget_over_budget() -> None:
    # Same stack, allowed 1.0: actual ~= 1.3416 > 1.0 -> OVER_BUDGET.
    result = statistical_budget(_ss_stack(), 1.0, sigma_multiplier=3.0)
    assert result.status == BudgetStatus.OVER_BUDGET
    assert result.remaining_margin < 0.0
    assert result.utilization_fraction > 1.0


def test_statistical_budget_contributor_shares_reuse_sensitivity() -> None:
    # Variance: A = 0.01, B = 0.04, total = 0.05.
    # A share = 0.01/0.05 = 0.20, B share = 0.04/0.05 = 0.80.
    result = statistical_budget(_ss_stack(), 2.0, sigma_multiplier=3.0)
    top, second = result.contributions  # ordered by descending variance

    assert top.name == "B"
    assert second.name == "A"
    assert math.isclose(top.share_of_consumed, 0.80, abs_tol=1e-12)
    assert math.isclose(second.share_of_consumed, 0.20, abs_tol=1e-12)

    # share_of_allowed = share_of_consumed * utilization_fraction
    utilization = result.utilization_fraction
    assert math.isclose(
        top.share_of_allowed, 0.80 * utilization, abs_tol=1e-12
    )
    assert math.isclose(
        second.share_of_allowed, 0.20 * utilization, abs_tol=1e-12
    )


# ---------------------------------------------------------------------------
# H. Correlated statistical budget
# ---------------------------------------------------------------------------


def test_statistical_budget_with_correlation() -> None:
    # A (sigma 0.1) + B (sigma 0.2), rho = 0.5.
    # Var = 0.01 + 0.04 + 2*1*1*0.5*0.1*0.2 = 0.07
    # With k=3: span = 6 * sqrt(0.07).
    correlations = (Correlation("A", "B", 0.5),)
    result = statistical_budget(
        _ss_stack(), 2.0, sigma_multiplier=3.0, correlations=correlations
    )
    assert result.status == BudgetStatus.UNDER_BUDGET
    assert math.isclose(
        result.actual_span, 6.0 * math.sqrt(0.07), abs_tol=1e-12
    )

    # Sensitivity analysis should be carried over.
    assert len(result.covariance_pairs) == 1
    pair = result.covariance_pairs[0]
    assert pair.first == "A"
    assert pair.second == "B"
    assert pair.rho == 0.5


# ---------------------------------------------------------------------------
# I. Deterministic repeated execution
# ---------------------------------------------------------------------------


def test_worst_case_budget_deterministic() -> None:
    results = [worst_case_budget(_wc_stack(), 1.0) for _ in range(5)]
    first = results[0]
    for other in results[1:]:
        assert other == first
        assert other.status == first.status
        assert other.utilization_fraction == first.utilization_fraction
        assert len(other.contributions) == len(first.contributions)


def test_statistical_budget_deterministic() -> None:
    results = [
        statistical_budget(_ss_stack(), 2.0, sigma_multiplier=3.0)
        for _ in range(5)
    ]
    first = results[0]
    for other in results[1:]:
        assert other == first
        assert other.status == first.status
        assert other.actual_span == first.actual_span


# ---------------------------------------------------------------------------
# J. Input immutability
# ---------------------------------------------------------------------------


def test_worst_case_budget_does_not_mutate_stack() -> None:
    stack = _wc_stack()
    original_contributions = tuple(stack.contributions)
    worst_case_budget(stack, 1.0)
    assert tuple(stack.contributions) == original_contributions


def test_statistical_budget_does_not_mutate_stack() -> None:
    stack = _ss_stack()
    original_contributions = tuple(stack.contributions)
    statistical_budget(stack, 2.0, sigma_multiplier=3.0)
    assert tuple(stack.contributions) == original_contributions


# ---------------------------------------------------------------------------
# K. Window compliance
# ---------------------------------------------------------------------------


def test_worst_case_window_compliant() -> None:
    # Stack minimum = 99.90 + 39.95 = 139.85, maximum = 100.20 + 40.10 = 140.30.
    result = worst_case_window_compliance(_wc_stack(), 139.0, 141.0)
    assert result.is_compliant is True
    assert result.nominal == 140.0
    assert result.allowed_lower == 139.0
    assert result.allowed_upper == 141.0


def test_worst_case_window_non_compliant() -> None:
    # Window too tight: maximum (140.30) > allowed_upper (140.10).
    result = worst_case_window_compliance(_wc_stack(), 139.0, 140.10)
    assert result.is_compliant is False


def test_worst_case_window_invalid_bounds() -> None:
    with pytest.raises(InvalidBudgetError):
        worst_case_window_compliance(_wc_stack(), 141.0, 139.0)  # lower > upper
    with pytest.raises(InvalidBudgetError):
        worst_case_window_compliance(_wc_stack(), math.nan, 141.0)
    with pytest.raises(InvalidBudgetError):
        worst_case_window_compliance(_wc_stack(), 139.0, math.inf)


# ---------------------------------------------------------------------------
# L. Validation propagation from authoritative engines
# ---------------------------------------------------------------------------


def test_worst_case_budget_propagates_empty_stack() -> None:
    with pytest.raises(InvalidStackError):
        worst_case_budget(ToleranceStack(()), 1.0)


def test_worst_case_budget_propagates_invalid_contribution() -> None:
    # Invalid: lower > upper raises at model construction.
    with pytest.raises(InvalidToleranceError):
        bad = ToleranceStack(
            (ToleranceContribution("A", 100.0, 0.20, -0.10),)
        )
        worst_case_budget(bad, 1.0)


def test_statistical_budget_propagates_empty_stack() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical_budget(StatisticalStack(()), 2.0, sigma_multiplier=3.0)


def test_statistical_budget_propagates_invalid_sigma() -> None:
    # Negative sigma raises at model construction.
    with pytest.raises(InvalidStatisticalError):
        bad = StatisticalStack(
            (StatisticalContribution("A", 100.0, -0.1),)
        )
        statistical_budget(bad, 2.0, sigma_multiplier=3.0)


def test_statistical_budget_propagates_invalid_multiplier() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical_budget(_ss_stack(), 2.0, sigma_multiplier=0.0)
    with pytest.raises(InvalidStatisticalError):
        statistical_budget(_ss_stack(), 2.0, sigma_multiplier=-1.0)


def test_statistical_budget_propagates_invalid_correlation() -> None:
    # Unknown contributor reference.
    correlations = (Correlation("A", "Z", 0.5),)
    with pytest.raises(InvalidCorrelationError):
        statistical_budget(
            _ss_stack(), 2.0, sigma_multiplier=3.0, correlations=correlations
        )


def test_statistical_budget_propagates_negative_variance() -> None:
    # Non-PSD correlation set.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.1),
            StatisticalContribution("B", 10.0, 0.1, StackDirection.INVERSE),
            StatisticalContribution("C", 10.0, 0.1, StackDirection.INVERSE),
        )
    )
    correlations = (
        Correlation("A", "B", 0.9),
        Correlation("A", "C", 0.9),
        Correlation("B", "C", -0.9),
    )
    with pytest.raises(InvalidVarianceError):
        statistical_budget(
            stack, 2.0, sigma_multiplier=3.0, correlations=correlations
        )