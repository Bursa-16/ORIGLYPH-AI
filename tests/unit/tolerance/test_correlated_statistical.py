"""Independent engineering tests for covariance-aware statistical analysis.

Stage 15E. These tests verify the correlated RSS contract from first
principles: every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test.

Covered categories:

A. backward compatibility with Stage 15D independent RSS
B/C. perfect positive / negative correlation
D/E. direction-sensitive covariance (opposite stack directions)
F. explicit zero correlation equals independence
G. partial correlation (hand-calculated)
H. three-contributor stack with multiple correlation pairs
I. invalid rho rejection (range, NaN, infinities)
J. unknown contributor rejection
K. duplicate / conflicting pair policy
L. pair symmetry (no double counting)
M. zero-sigma contributors
N. sigma multiplier bounds
O. determinism
P/Q. worst-case and independent-RSS regression separation
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    Correlation,
    InvalidCorrelationError,
    InvalidStatisticalError,
    InvalidVarianceError,
    StackDirection,
    StatisticalContribution,
    StatisticalResult,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    statistical,
    worst_case,
)


def _stack(*contributions: StatisticalContribution) -> StatisticalStack:
    return StatisticalStack(tuple(contributions))


def _ab_stack() -> StatisticalStack:
    """sigma 0.1 (A) + sigma 0.2 (B), both FORWARD."""
    return _stack(
        StatisticalContribution("A", 100.0, 0.1),
        StatisticalContribution("B", 40.0, 0.2),
    )


def _opposite_stack() -> StatisticalStack:
    """A FORWARD minus B INVERSE: sigmas 0.1 and 0.2."""
    return _stack(
        StatisticalContribution("A", 100.0, 0.1),
        StatisticalContribution("B", 40.0, 0.2, StackDirection.INVERSE),
    )


def _three_stack() -> StatisticalStack:
    """A + B - C with sigmas 0.1 / 0.2 / 0.15."""
    return _stack(
        StatisticalContribution("A", 100.0, 0.1),
        StatisticalContribution("B", 30.0, 0.2),
        StatisticalContribution("C", 20.0, 0.15, StackDirection.INVERSE),
    )


def _wc_stack() -> ToleranceStack:
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10, StackDirection.INVERSE),
        )
    )


# ---------------------------------------------------------------------------
# Correlation model contract
# ---------------------------------------------------------------------------


def test_correlation_canonical_ordering_normalizes_pair() -> None:
    corr = Correlation("B", "A", 0.5)
    assert corr.first == "A"
    assert corr.second == "B"
    assert corr.pair == ("A", "B")


def test_correlation_symmetric_constructions_are_equal_and_hash_equal() -> None:
    assert Correlation("A", "B", 0.5) == Correlation("B", "A", 0.5)
    assert hash(Correlation("A", "B", 0.5)) == hash(Correlation("B", "A", 0.5))


def test_correlation_rejects_empty_name() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("", "B", 0.5)
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "", 0.5)


def test_correlation_rejects_self_correlation() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "A", 1.0)


@pytest.mark.parametrize("rho", [1.0000001, 2.0, -1.0000001, -2.0])
def test_correlation_rejects_rho_outside_interval(rho: float) -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", rho)


def test_correlation_rejects_nan() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", math.nan)


def test_correlation_rejects_plus_infinity() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", math.inf)


def test_correlation_rejects_minus_infinity() -> None:
    with pytest.raises(InvalidCorrelationError):
        Correlation("A", "B", -math.inf)


@pytest.mark.parametrize("rho", [-1.0, 0.0, 1.0])
def test_correlation_accepts_boundary_and_zero_values(rho: float) -> None:
    assert Correlation("A", "B", rho).coefficient == rho


def test_correlation_is_immutable() -> None:
    corr = Correlation("A", "B", 0.5)
    with pytest.raises(AttributeError):
        corr.coefficient = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# A. Backward compatibility with Stage 15D independent RSS
# ---------------------------------------------------------------------------


def test_no_correlations_reproduces_independent_rss() -> None:
    # Hand-calculated independent RSS: sqrt(0.1^2 + 0.2^2) = sqrt(0.05).
    result = statistical(_ab_stack())
    assert result.nominal == 140.0
    assert result.combined_sigma == pytest.approx(math.sqrt(0.05))


def test_keyword_only_usage_unchanged() -> None:
    by_keyword = statistical(_ab_stack(), sigma_multiplier=2.0)
    by_positional = statistical(_ab_stack(), 2.0)
    assert by_keyword == by_positional


def test_explicit_zero_correlation_equals_independence() -> None:
    independent = statistical(_ab_stack())
    declared_zero = statistical(
        _ab_stack(), correlations=(Correlation("A", "B", 0.0),)
    )
    assert declared_zero == independent


def test_duplicate_contributor_names_without_correlations_still_valid() -> None:
    # Ambiguity only matters for correlation references; Stage 15D stacks
    # with repeated display names must remain constructible/analysable.
    stack = _stack(
        StatisticalContribution("X", 10.0, 0.1),
        StatisticalContribution("X", 20.0, 0.2),
    )
    result = statistical(stack)
    assert result.nominal == pytest.approx(30.0)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.05))


# ---------------------------------------------------------------------------
# B/C/G. Perfect and partial correlation (same direction)
# ---------------------------------------------------------------------------


def test_perfect_positive_correlation_sums_sigmas() -> None:
    # Var = 0.01 + 0.04 + 2*(1)(1)(1)(0.1)(0.2) = 0.09 -> sigma = 0.3
    result = statistical(_ab_stack(), correlations=(Correlation("A", "B", 1.0),))
    assert result.combined_sigma == pytest.approx(0.3, abs=1e-12)


def test_perfect_negative_correlation_cancels() -> None:
    # Var = 0.01 + 0.01 + 2*(1)(1)(-1)(0.1)(0.1) = 0.0 -> sigma = 0
    stack = _stack(
        StatisticalContribution("A", 10.0, 0.1),
        StatisticalContribution("B", 5.0, 0.1),
    )
    result = statistical(stack, correlations=(Correlation("A", "B", -1.0),))
    assert result.combined_sigma == pytest.approx(0.0, abs=1e-15)
    assert result.lower_bound == pytest.approx(result.nominal, abs=1e-12)
    assert result.upper_bound == pytest.approx(result.nominal, abs=1e-12)


def test_partial_correlation_hand_calculated() -> None:
    # Var = 0.1^2 + 0.2^2 + 2*0.5*0.1*0.2 = 0.05 + 0.02 = 0.07
    result = statistical(_ab_stack(), correlations=(Correlation("A", "B", 0.5),))
    assert result.combined_sigma == pytest.approx(math.sqrt(0.07), rel=1e-12)
    assert result.combined_sigma == pytest.approx(0.2645751, abs=1e-6)


# ---------------------------------------------------------------------------
# D/E. Direction-sensitive covariance
# ---------------------------------------------------------------------------


def test_opposite_directions_positive_correlation_reduces_variance() -> None:
    # Var = 0.01 + 0.04 + 2*(+1)(-1)(+1)(0.1)(0.2) = 0.05 - 0.04 = 0.01
    result = statistical(
        _opposite_stack(), correlations=(Correlation("A", "B", 1.0),)
    )
    assert result.nominal == pytest.approx(60.0)
    assert result.combined_sigma == pytest.approx(0.1, abs=1e-12)


def test_opposite_directions_negative_correlation_increases_variance() -> None:
    # Var = 0.01 + 0.04 + 2*(+1)(-1)(-1)(0.1)(0.2) = 0.05 + 0.04 = 0.09
    result = statistical(
        _opposite_stack(), correlations=(Correlation("A", "B", -1.0),)
    )
    assert result.nominal == pytest.approx(60.0)
    assert result.combined_sigma == pytest.approx(0.3, abs=1e-12)


def test_same_nominal_three_rhos_three_sigmas() -> None:
    # rho = -1 / 0 / +1 on the opposite-direction stack gives
    # 0.3 / sqrt(0.05) / 0.1 respectively — signs are never absolutized.
    rho_minus = statistical(
        _opposite_stack(), correlations=(Correlation("A", "B", -1.0),)
    )
    rho_zero = statistical(
        _opposite_stack(), correlations=(Correlation("A", "B", 0.0),)
    )
    rho_plus = statistical(
        _opposite_stack(), correlations=(Correlation("A", "B", 1.0),)
    )
    assert rho_minus.combined_sigma == pytest.approx(0.3, abs=1e-12)
    assert rho_zero.combined_sigma == pytest.approx(math.sqrt(0.05), rel=1e-12)
    assert rho_plus.combined_sigma == pytest.approx(0.1, abs=1e-12)


# ---------------------------------------------------------------------------
# H. Three-contributor stack with multiple pairs (hand-calculated)
# ---------------------------------------------------------------------------


def test_three_contributor_multiple_pairs_hand_calculated() -> None:
    # Independent part: 0.01 + 0.04 + 0.0225 = 0.0725
    # Pair AB (both +1, rho 0.6):  2*(1)(1)(0.6)(0.1)(0.2)    = +0.024
    # Pair BC (+1 / -1, rho -0.4): 2*(1)(-1)(-0.4)(0.2)(0.15) = +0.024
    # Pair AC undeclared -> rho = 0 -> contributes nothing.
    # Var = 0.1205, sigma = sqrt(0.1205); nominal = 100 + 30 - 20 = 110.
    correlations = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    result = statistical(_three_stack(), correlations=correlations)
    assert result.nominal == pytest.approx(110.0)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.1205), rel=1e-12)
    assert result.combined_sigma == pytest.approx(0.3471311, abs=1e-6)


def test_missing_pair_defaults_to_zero() -> None:
    # Declaring the missing AC pair as rho = 0 must not change anything.
    base = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    with_pairs = statistical(_three_stack(), correlations=base)
    with_explicit_zero = statistical(
        _three_stack(),
        correlations=(*base, Correlation("A", "C", 0.0)),
    )
    assert with_explicit_zero == with_pairs


# ---------------------------------------------------------------------------
# J/K. Contributor identity: unknown names, ambiguity, duplicates
# ---------------------------------------------------------------------------


def test_unknown_first_contributor_rejected() -> None:
    with pytest.raises(InvalidCorrelationError, match="unknown contributor"):
        statistical(_ab_stack(), correlations=(Correlation("Z", "B", 0.5),))


def test_unknown_second_contributor_rejected() -> None:
    with pytest.raises(InvalidCorrelationError, match="unknown contributor"):
        statistical(_ab_stack(), correlations=(Correlation("A", "Z", 0.5),))


def test_conflicting_duplicate_pair_rejected() -> None:
    with pytest.raises(InvalidCorrelationError, match="conflicting"):
        statistical(
            _ab_stack(),
            correlations=(
                Correlation("A", "B", 0.5),
                Correlation("B", "A", 0.7),
            ),
        )


def test_identical_duplicate_pair_is_idempotent() -> None:
    single = statistical(_ab_stack(), correlations=(Correlation("A", "B", 0.5),))
    twice = statistical(
        _ab_stack(),
        correlations=(
            Correlation("A", "B", 0.5),
            Correlation("B", "A", 0.5),
        ),
    )
    assert twice == single


def test_duplicate_contributor_names_with_correlations_rejected() -> None:
    ambiguous = _stack(
        StatisticalContribution("X", 10.0, 0.1),
        StatisticalContribution("X", 20.0, 0.2),
    )
    with pytest.raises(InvalidCorrelationError, match="unique"):
        statistical(ambiguous, correlations=(Correlation("X", "Y", 0.5),))


# ---------------------------------------------------------------------------
# I/M/N. Validation, zero sigma, sigma multiplier
# ---------------------------------------------------------------------------


def test_materially_negative_variance_raises() -> None:
    # Non-PSD correlation set: rho_AB = rho_AC = 0.9, rho_BC = -0.9.
    # With signs (+1, -1, -1) and sigma 0.1 each:
    # Var = 0.03 - 2*(0.9 + 0.9 + 0.9)*0.01 = 0.03 - 0.054 = -0.024.
    stack = _stack(
        StatisticalContribution("A", 10.0, 0.1),
        StatisticalContribution("B", 10.0, 0.1, StackDirection.INVERSE),
        StatisticalContribution("C", 10.0, 0.1, StackDirection.INVERSE),
    )
    correlations = (
        Correlation("A", "B", 0.9),
        Correlation("A", "C", 0.9),
        Correlation("B", "C", -0.9),
    )
    with pytest.raises(InvalidVarianceError, match="negative"):
        statistical(stack, correlations=correlations)


def test_zero_sigma_contributor_with_correlation_is_valid() -> None:
    # Var = 0 + 0.04 + 2*(1)(1)(1)(0)(0.2) = 0.04 -> sigma = 0.2
    stack = _stack(
        StatisticalContribution("A", 10.0, 0.0),
        StatisticalContribution("B", 5.0, 0.2),
    )
    result = statistical(stack, correlations=(Correlation("A", "B", 1.0),))
    assert result.combined_sigma == pytest.approx(0.2, abs=1e-15)


def test_all_zero_sigma_with_perfect_correlation_collapses() -> None:
    stack = _stack(
        StatisticalContribution("A", 10.0, 0.0),
        StatisticalContribution("B", 5.0, 0.0),
    )
    result = statistical(stack, correlations=(Correlation("A", "B", 1.0),))
    assert result.combined_sigma == 0.0
    assert result.lower_bound == result.nominal
    assert result.upper_bound == result.nominal


@pytest.mark.parametrize("k", [1.0, 2.0, 3.0])
def test_sigma_multiplier_bounds(k: float) -> None:
    result = statistical(
        _ab_stack(), sigma_multiplier=k, correlations=(Correlation("A", "B", 0.5),)
    )
    expected = math.sqrt(0.07)
    assert result.sigma_multiplier == k
    assert result.lower_bound == pytest.approx(result.nominal - k * expected)
    assert result.upper_bound == pytest.approx(result.nominal + k * expected)
    assert result.upper_bound - result.lower_bound == pytest.approx(
        2.0 * k * expected
    )


def test_invalid_multiplier_still_rejected_with_correlations() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(
            _ab_stack(),
            sigma_multiplier=0.0,
            correlations=(Correlation("A", "B", 0.5),),
        )


# ---------------------------------------------------------------------------
# O. Determinism
# ---------------------------------------------------------------------------


def test_repeated_execution_identical() -> None:
    correlations = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    first = statistical(
        _three_stack(), sigma_multiplier=2.0, correlations=correlations
    )
    second = statistical(
        _three_stack(), sigma_multiplier=2.0, correlations=correlations
    )
    assert first == second
    assert repr(first) == repr(second)


def test_rebuilt_stack_identical() -> None:
    def build() -> StatisticalStack:
        return _ab_stack()

    left = statistical(build(), correlations=(Correlation("A", "B", 0.5),))
    right = statistical(build(), correlations=(Correlation("A", "B", 0.5),))
    assert left == right


# ---------------------------------------------------------------------------
# P/Q. Method separation and regression
# ---------------------------------------------------------------------------


def test_result_type_is_statistical_not_worst_case() -> None:
    result = statistical(_ab_stack(), correlations=(Correlation("A", "B", 0.5),))
    worst = worst_case(_wc_stack())
    assert isinstance(result, StatisticalResult)
    assert type(result) is not type(worst)


def test_worst_case_unchanged_by_statistical_work() -> None:
    # Hand-calculated Stage 15C-R example: A - B with
    # A = 100 +0.20/-0.10, B = 40 +0.10/-0.05.
    # Interval of A: [99.90, 100.20]; interval of B: [39.95, 40.10].
    # A - B: nominal 60, minimum 59.80, maximum 60.25, span 0.45.
    result = worst_case(_wc_stack())
    assert result.nominal == pytest.approx(60.0)
    assert result.minimum == pytest.approx(59.80)
    assert result.maximum == pytest.approx(60.25)
    assert result.lower_deviation == pytest.approx(-0.20)
    assert result.upper_deviation == pytest.approx(0.25)
    assert result.total_span == pytest.approx(0.45)


def test_independent_rss_regression_values() -> None:
    # Stage 15D hand example: sqrt(0.1^2 + 0.2^2), k = 3.
    result = statistical(_ab_stack(), sigma_multiplier=3.0)
    sigma = math.sqrt(0.05)
    assert result.combined_sigma == pytest.approx(sigma, rel=1e-12)
    assert result.lower_bound == pytest.approx(140.0 - 3.0 * sigma, rel=1e-12)
    assert result.upper_bound == pytest.approx(140.0 + 3.0 * sigma, rel=1e-12)
