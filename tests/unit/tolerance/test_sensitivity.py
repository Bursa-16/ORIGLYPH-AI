"""Independent engineering tests for sensitivity and contributor impact.

Stage 15F. Every expected value is hand-calculated here and asserted
explicitly, independently of the implementation under test. Sensitivity is
explanatory only: these tests also verify that authoritative engine results
are used unchanged and that inputs are never mutated.

Covered categories:

A. worst-case two-contributor impact and ranking
B. worst-case zero-span policy
C. worst-case mixed directions (span stays positive)
D. independent RSS variance decomposition
E. three-contributor RSS (hand-calculated)
F/G. signed covariance terms (positive and negative preserved)
H. mixed directions + correlation sign behavior
I/J. perfect positive / negative correlation
K. zero-sigma contributors
L. near-zero total variance policy
M. stable ranking across repeated execution
N. deterministic tie-breaking (input order preserved)
O. input immutability
P/Q/R. authoritative-engine regression and decomposition identity
plus validation propagation (invalid input stays invalid).
"""

from __future__ import annotations

import copy
import math

import pytest

from origlyph.tolerance import (
    Correlation,
    CovariancePairImpact,
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidVarianceError,
    StackDirection,
    StatisticalContribution,
    StatisticalResult,
    StatisticalSensitivityResult,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
    WorstCaseSensitivityResult,
    statistical,
    statistical_sensitivity,
    worst_case,
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


def _ss_stack() -> StatisticalStack:
    """A (sigma 0.1) + B (sigma 0.2): total variance 0.05."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2),
        )
    )


# ---------------------------------------------------------------------------
# A. Worst-case two contributors
# ---------------------------------------------------------------------------


def test_worst_case_two_contributor_impact_and_ranking() -> None:
    # Hand-calculated: span_A = 0.20 - (-0.10) = 0.30,
    #                 span_B = 0.10 - (-0.05) = 0.15, total = 0.45.
    result = worst_case_sensitivity(_wc_stack())
    assert isinstance(result, WorstCaseSensitivityResult)
    assert result.total_span == pytest.approx(0.45)

    assert len(result.impacts) == 2
    top, second = result.impacts
    assert top.name == "A"
    assert second.name == "B"

    assert top.span == pytest.approx(0.30)
    assert top.fraction == pytest.approx(2.0 / 3.0)
    assert top.percentage == pytest.approx(200.0 / 3.0)

    assert second.span == pytest.approx(0.15)
    assert second.fraction == pytest.approx(1.0 / 3.0)
    assert second.percentage == pytest.approx(100.0 / 3.0)

    assert top.direction is StackDirection.FORWARD
    assert top.signed_nominal == pytest.approx(100.0)
    assert top.lower_deviation == pytest.approx(-0.10)
    assert top.upper_deviation == pytest.approx(0.20)


def test_worst_case_impact_fractions_sum_to_one() -> None:
    result = worst_case_sensitivity(_wc_stack())
    assert math.fsum(i.fraction for i in result.impacts) == pytest.approx(1.0)


def test_worst_case_impact_matches_authoritative_total() -> None:
    stack = _wc_stack()
    sensitivity = worst_case_sensitivity(stack)
    authoritative = worst_case(stack)
    assert sensitivity.total_span == authoritative.total_span


# ---------------------------------------------------------------------------
# B. Worst-case zero-span policy
# ---------------------------------------------------------------------------


def test_worst_case_zero_span_uses_documented_policy() -> None:
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 10.0, 0.0, 0.0),
            ToleranceContribution("B", 5.0, 0.0, 0.0),
        )
    )
    result = worst_case_sensitivity(stack)
    assert result.total_span == 0.0
    for impact in result.impacts:
        assert impact.span == 0.0
        assert impact.fraction == 0.0
        assert impact.percentage == 0.0
        assert not math.isnan(impact.fraction)
        assert not math.isinf(impact.fraction)


# ---------------------------------------------------------------------------
# C. Worst-case mixed directions
# ---------------------------------------------------------------------------


def test_worst_case_mixed_directions_keep_span_positive() -> None:
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10, StackDirection.INVERSE),
        )
    )
    result = worst_case_sensitivity(stack)
    by_name = {impact.name: impact for impact in result.impacts}
    # An INVERSE contribution reverses its interval in stack space but its
    # width — and therefore its span impact — is unchanged.
    assert by_name["A"].span == pytest.approx(0.30)
    assert by_name["B"].span == pytest.approx(0.15)
    assert by_name["B"].direction is StackDirection.INVERSE
    assert by_name["B"].signed_nominal == pytest.approx(-40.0)
    assert by_name["B"].fraction == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# N. Deterministic tie-breaking (worst case)
# ---------------------------------------------------------------------------


def test_worst_case_equal_spans_preserve_input_order() -> None:
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.15, 0.15),
            ToleranceContribution("B", 40.0, -0.15, 0.15),
        )
    )
    result = worst_case_sensitivity(stack)
    assert [impact.name for impact in result.impacts] == ["A", "B"]


# ---------------------------------------------------------------------------
# M. Stable ranking across repeated execution (worst case)
# ---------------------------------------------------------------------------


def test_worst_case_ranking_deterministic_across_runs() -> None:
    first = worst_case_sensitivity(_wc_stack())
    second = worst_case_sensitivity(_wc_stack())
    assert first == second
    assert [i.name for i in first.impacts] == [i.name for i in second.impacts]


# ---------------------------------------------------------------------------
# D. Independent RSS variance decomposition
# ---------------------------------------------------------------------------


def test_independent_rss_variance_decomposition() -> None:
    # Hand-calculated: var_A = 0.1^2 = 0.01, var_B = 0.2^2 = 0.04,
    # total = 0.05 -> fractions 0.20 / 0.80.
    result = statistical_sensitivity(_ss_stack())
    assert isinstance(result, StatisticalSensitivityResult)
    assert result.total_variance == pytest.approx(0.05)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.05))
    assert result.sigma_multiplier == 1.0

    top, second = result.contributions  # ranked by descending variance
    assert top.name == "B"
    assert top.variance == pytest.approx(0.04)
    assert top.fraction == pytest.approx(0.80)
    assert top.percentage == pytest.approx(80.0)

    assert second.name == "A"
    assert second.variance == pytest.approx(0.01)
    assert second.fraction == pytest.approx(0.20)
    assert second.percentage == pytest.approx(20.0)

    assert result.covariance_pairs == ()  # no correlations declared


def test_independent_rss_impact_fractions_sum_to_one() -> None:
    result = statistical_sensitivity(_ss_stack())
    assert math.fsum(c.fraction for c in result.contributions) == pytest.approx(1.0)


def test_independent_rss_matches_authoritative_result() -> None:
    stack = _ss_stack()
    sensitivity = statistical_sensitivity(stack)
    authoritative = statistical(stack)
    assert sensitivity.nominal == authoritative.nominal
    assert sensitivity.combined_sigma == authoritative.combined_sigma
    assert sensitivity.sigma_multiplier == authoritative.sigma_multiplier
    assert sensitivity.total_variance == pytest.approx(
        authoritative.combined_sigma**2
    )


def test_sensitivity_does_not_rank_by_sigma_alone() -> None:
    # The documented metric is variance: B (sigma 0.2) has 4x the variance
    # of A (sigma 0.1), not 2x — ranking must reflect variance order.
    result = statistical_sensitivity(_ss_stack())
    assert result.contributions[0].sigma == pytest.approx(0.2)
    assert result.contributions[0].variance == pytest.approx(0.04)


# ---------------------------------------------------------------------------
# E. Three-contributor RSS (hand-calculated)
# ---------------------------------------------------------------------------


def test_three_contributor_rss_decomposition() -> None:
    # Hand-calculated: 0.01 + 0.04 + 0.09 = 0.14.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.3, StackDirection.INVERSE),
        )
    )
    result = statistical_sensitivity(stack)
    assert result.total_variance == pytest.approx(0.14)
    assert result.nominal == pytest.approx(110.0)  # 100 + 30 - 20

    by_name = {c.name: c for c in result.contributions}
    assert by_name["A"].variance == pytest.approx(0.01)
    assert by_name["B"].variance == pytest.approx(0.04)
    assert by_name["C"].variance == pytest.approx(0.09)  # a^2 = 1 even if INVERSE
    assert by_name["A"].fraction == pytest.approx(0.01 / 0.14)
    assert by_name["B"].fraction == pytest.approx(0.04 / 0.14)
    assert by_name["C"].fraction == pytest.approx(0.09 / 0.14)

    # Ranking: C (0.09) > B (0.04) > A (0.01).
    assert [c.name for c in result.contributions] == ["C", "B", "A"]


# ---------------------------------------------------------------------------
# F/G. Signed covariance terms
# ---------------------------------------------------------------------------


def test_positive_covariance_term_is_positive() -> None:
    # Same direction, rho = +0.5: term = 2*(+1)(+1)(0.5)(0.1)(0.2) = +0.02.
    # Total variance = 0.05 + 0.02 = 0.07.
    result = statistical_sensitivity(
        _ss_stack(), correlations=(Correlation("A", "B", 0.5),)
    )
    assert len(result.covariance_pairs) == 1
    pair = result.covariance_pairs[0]
    assert isinstance(pair, CovariancePairImpact)
    assert pair.first == "A"
    assert pair.second == "B"
    assert pair.rho == pytest.approx(0.5)
    assert pair.covariance_term == pytest.approx(0.02)
    assert pair.abs_covariance == pytest.approx(0.02)
    assert pair.fraction == pytest.approx(0.02 / 0.07)
    assert pair.percentage == pytest.approx(100.0 * 0.02 / 0.07)


def test_negative_covariance_term_is_preserved() -> None:
    # Same direction, rho = -1: term = 2*(+1)(+1)(-1)(0.1)(0.2) = -0.04.
    # Total variance = 0.05 - 0.04 = 0.01.
    result = statistical_sensitivity(
        _ss_stack(), correlations=(Correlation("A", "B", -1.0),)
    )
    pair = result.covariance_pairs[0]
    assert pair.covariance_term == pytest.approx(-0.04)
    assert pair.abs_covariance == pytest.approx(0.04)  # magnitude for ranking only
    assert pair.fraction == pytest.approx(-4.0)  # -0.04 / 0.01 — cancellation kept
    assert pair.percentage == pytest.approx(-400.0)
    # Cancellation must not be normalized away in the authoritative total.
    assert result.total_variance == pytest.approx(0.01)
    assert result.combined_sigma == pytest.approx(0.1)


def test_covariance_pair_not_assigned_to_single_contributor() -> None:
    # The pair impact is a separate, joint object — individual variance
    # terms remain exactly a_i^2 * sigma_i^2 with no covariance attribution.
    result = statistical_sensitivity(
        _ss_stack(), correlations=(Correlation("A", "B", 0.5),)
    )
    by_name = {c.name: c for c in result.contributions}
    assert by_name["A"].variance == pytest.approx(0.01)
    assert by_name["B"].variance == pytest.approx(0.04)


def test_decomposition_identity_with_covariance() -> None:
    correlations = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.15, StackDirection.INVERSE),
        )
    )
    result = statistical_sensitivity(stack, correlations=correlations)
    reconstructed = math.fsum(c.variance for c in result.contributions) + math.fsum(
        p.covariance_term for p in result.covariance_pairs
    )
    assert reconstructed == pytest.approx(result.total_variance)
    # Total must match the authoritative engine's sigma squared.
    authoritative = statistical(stack, correlations=correlations)
    assert result.total_variance == pytest.approx(authoritative.combined_sigma**2)


# ---------------------------------------------------------------------------
# H. Mixed directions + correlation
# ---------------------------------------------------------------------------


def test_mixed_directions_positive_correlation_is_negative_term() -> None:
    # A FORWARD, B INVERSE, rho = +1: term = 2*(+1)(-1)(1)(0.1)(0.2) = -0.04.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2, StackDirection.INVERSE),
        )
    )
    result = statistical_sensitivity(
        stack, correlations=(Correlation("A", "B", 1.0),)
    )
    assert result.covariance_pairs[0].covariance_term == pytest.approx(-0.04)
    assert result.total_variance == pytest.approx(0.01)


def test_mixed_directions_negative_correlation_is_positive_term() -> None:
    # A FORWARD, B INVERSE, rho = -1: term = 2*(+1)(-1)(-1)(0.1)(0.2) = +0.04.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2, StackDirection.INVERSE),
        )
    )
    result = statistical_sensitivity(
        stack, correlations=(Correlation("A", "B", -1.0),)
    )
    assert result.covariance_pairs[0].covariance_term == pytest.approx(0.04)
    assert result.total_variance == pytest.approx(0.09)


def test_absolute_directions_are_never_taken_for_covariance() -> None:
    # If directions were abs()-ed, both stacks would produce +0.04 terms.
    # They must differ — sign-sensitivity is contractual.
    fwd = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2),
        )
    )
    inv = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 40.0, 0.2, StackDirection.INVERSE),
        )
    )
    corr = (Correlation("A", "B", 1.0),)
    term_fwd = statistical_sensitivity(fwd, correlations=corr).covariance_pairs[0]
    term_inv = statistical_sensitivity(inv, correlations=corr).covariance_pairs[0]
    assert term_fwd.covariance_term == pytest.approx(0.04)
    assert term_inv.covariance_term == pytest.approx(-0.04)


# ---------------------------------------------------------------------------
# I/J. Perfect correlations
# ---------------------------------------------------------------------------


def test_perfect_positive_correlation_variance_fractions() -> None:
    # rho = +1, same direction: total = 0.05 + 0.04 = 0.09.
    # Individual fractions 1/9 and 4/9, pair fraction 4/9; grand sum = 1.
    result = statistical_sensitivity(
        _ss_stack(), correlations=(Correlation("A", "B", 1.0),)
    )
    assert result.total_variance == pytest.approx(0.09)
    by_name = {c.name: c for c in result.contributions}
    assert by_name["A"].fraction == pytest.approx(0.01 / 0.09)
    assert by_name["B"].fraction == pytest.approx(0.04 / 0.09)
    assert result.covariance_pairs[0].fraction == pytest.approx(0.04 / 0.09)
    grand_total = math.fsum(
        [c.fraction for c in result.contributions]
        + [p.fraction for p in result.covariance_pairs]
    )
    assert grand_total == pytest.approx(1.0)


def test_perfect_negative_correlation_zero_variance_policy() -> None:
    # Equal sigmas, rho = -1, same direction: variance cancels exactly to 0.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.1),
            StatisticalContribution("B", 5.0, 0.1),
        )
    )
    result = statistical_sensitivity(
        stack, correlations=(Correlation("A", "B", -1.0),)
    )
    assert result.total_variance == pytest.approx(0.0, abs=1e-15)
    assert result.combined_sigma == pytest.approx(0.0, abs=1e-15)
    # Documented zero-variance policy: all fractions/percentages exactly 0.0.
    for contribution in result.contributions:
        assert contribution.fraction == 0.0
        assert contribution.percentage == 0.0
    for pair in result.covariance_pairs:
        assert pair.fraction == 0.0
        assert pair.percentage == 0.0
    # No NaN and no infinity anywhere in the decomposition.
    for value in (result.total_variance, result.combined_sigma):
        assert not math.isnan(value)
        assert not math.isinf(value)


# ---------------------------------------------------------------------------
# K. Zero sigma contributors
# ---------------------------------------------------------------------------


def test_zero_sigma_contributor_has_zero_variance_impact() -> None:
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.0),
            StatisticalContribution("B", 5.0, 0.2),
        )
    )
    result = statistical_sensitivity(stack)
    by_name = {c.name: c for c in result.contributions}
    assert by_name["A"].variance == 0.0
    assert by_name["A"].fraction == 0.0
    assert by_name["B"].variance == pytest.approx(0.04)
    assert by_name["B"].fraction == 1.0
    assert not math.isnan(by_name["A"].fraction)
    assert not math.isinf(by_name["A"].fraction)


def test_all_zero_sigma_stack_all_zero_policy() -> None:
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.0),
            StatisticalContribution("B", 5.0, 0.0),
        )
    )
    result = statistical_sensitivity(stack)
    assert result.total_variance == 0.0
    assert result.combined_sigma == 0.0
    for contribution in result.contributions:
        assert contribution.fraction == 0.0
        assert contribution.percentage == 0.0


# ---------------------------------------------------------------------------
# L. Near-zero total variance policy
# ---------------------------------------------------------------------------


def test_near_zero_variance_reuses_engine_threshold_not_new_policy() -> None:
    # Cancellation to exact zero via perfect negative correlation is the
    # documented pathway into the zero-variance policy; the decomposition
    # must remain finite and never divide by the negligible total.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 10.0, 0.1),
            StatisticalContribution("B", 5.0, 0.1),
        )
    )
    result = statistical_sensitivity(
        stack, correlations=(Correlation("A", "B", -1.0),)
    )
    for contribution in result.contributions:
        assert math.isfinite(contribution.fraction)
        assert math.isfinite(contribution.percentage)
    assert result.covariance_pairs[0].covariance_term == pytest.approx(-0.02)


# ---------------------------------------------------------------------------
# M. Stable ranking across repeated execution
# ---------------------------------------------------------------------------


def test_worst_case_ranking_stable_across_repeated_execution() -> None:
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
            ToleranceContribution("C", 25.0, -0.02, 0.03),
        )
    )
    first = worst_case_sensitivity(stack)
    second = worst_case_sensitivity(stack)
    # Spans 0.30 / 0.15 / 0.05 -> strictly descending ranking A > B > C.
    assert [i.name for i in first.impacts] == ["A", "B", "C"]
    assert [i.name for i in second.impacts] == ["A", "B", "C"]


def test_statistical_ranking_stable_across_repeated_execution() -> None:
    stack = _ss_stack()
    first = statistical_sensitivity(stack)
    second = statistical_sensitivity(stack)
    # Variances 0.01 / 0.04 -> descending ranking B > A.
    assert [c.name for c in first.contributions] == ["B", "A"]
    assert [c.name for c in second.contributions] == ["B", "A"]


def test_covariance_pair_ranking_stable_across_repeated_execution() -> None:
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.2),
            StatisticalContribution("D", 10.0, 0.15),
        )
    )
    correlations = (
        Correlation("A", "B", 0.6),
        Correlation("A", "C", 0.6),
        Correlation("A", "D", 0.3),
    )
    first = statistical_sensitivity(stack, correlations=correlations)
    second = statistical_sensitivity(stack, correlations=correlations)
    # |terms| 0.024 / 0.024 / 0.009 -> descending, tie in declaration order.
    assert [(p.first, p.second) for p in first.covariance_pairs] == [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
    ]
    assert [(p.first, p.second) for p in second.covariance_pairs] == [
        (p.first, p.second) for p in first.covariance_pairs
    ]


# ---------------------------------------------------------------------------
# N. Deterministic tie-breaking (input order preserved)
# ---------------------------------------------------------------------------


def test_worst_case_tie_preserves_input_order() -> None:
    # B declared before A; both spans are exactly 0.15.
    stack = ToleranceStack(
        (
            ToleranceContribution("B", 40.0, -0.05, 0.10),
            ToleranceContribution("A", 100.0, -0.05, 0.10),
        )
    )
    impacts = worst_case_sensitivity(stack).impacts
    assert [i.name for i in impacts] == ["B", "A"]


def test_statistical_tie_preserves_input_order() -> None:
    # Equal sigmas -> equal variances; X declared before Y.
    stack = StatisticalStack(
        (
            StatisticalContribution("X", 1.0, 0.1),
            StatisticalContribution("Y", 2.0, 0.1),
        )
    )
    contributions = statistical_sensitivity(stack).contributions
    assert [c.name for c in contributions] == ["X", "Y"]


def test_covariance_pair_tie_preserves_declaration_order() -> None:
    # Two pairs with identical |covariance term| = 0.024.
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.2),
        )
    )
    correlations = (Correlation("A", "C", 0.6), Correlation("A", "B", 0.6))
    pairs = statistical_sensitivity(
        stack, correlations=correlations
    ).covariance_pairs
    assert [(p.first, p.second) for p in pairs] == [("A", "C"), ("A", "B")]


# ---------------------------------------------------------------------------
# O. Input immutability
# ---------------------------------------------------------------------------


def test_worst_case_sensitivity_does_not_mutate_input() -> None:
    stack = _wc_stack()
    snapshot = copy.deepcopy(stack)
    worst_case_sensitivity(stack)
    assert stack == snapshot


def test_statistical_sensitivity_does_not_mutate_input() -> None:
    stack = _ss_stack()
    correlations = (Correlation("A", "B", 0.5),)
    stack_snapshot = copy.deepcopy(stack)
    correlations_snapshot = copy.deepcopy(correlations)
    statistical_sensitivity(stack, sigma_multiplier=2.0, correlations=correlations)
    assert stack == stack_snapshot
    assert correlations == correlations_snapshot


# ---------------------------------------------------------------------------
# P/Q/R. Authoritative-engine regression and decomposition identity
# ---------------------------------------------------------------------------


def test_worst_case_engine_regression_unchanged() -> None:
    # Hand-calculated: A [99.90, 100.20] + B [39.95, 40.10]
    # -> nominal 140, min 139.85, max 140.30, span 0.45.
    result = worst_case(_wc_stack())
    assert isinstance(result, WorstCaseResult)
    assert result.nominal == pytest.approx(140.0)
    assert result.minimum == pytest.approx(139.85)
    assert result.maximum == pytest.approx(140.30)
    assert result.total_span == pytest.approx(0.45)


def test_worst_case_sensitivity_uses_authoritative_total_span() -> None:
    # The sensitivity total must come from the authoritative engine result.
    engine = worst_case(_wc_stack())
    sensitivity = worst_case_sensitivity(_wc_stack())
    assert sensitivity.total_span == engine.total_span
    # Fraction identity: individual fractions sum to 1.0 for nonzero span.
    assert sum(i.fraction for i in sensitivity.impacts) == pytest.approx(1.0)


def test_independent_rss_engine_regression_unchanged() -> None:
    # Stage 15D hand example: sqrt(0.1^2 + 0.2^2) = sqrt(0.05).
    result = statistical(_ss_stack())
    assert isinstance(result, StatisticalResult)
    assert result.nominal == pytest.approx(140.0)
    assert result.combined_sigma == pytest.approx(math.sqrt(0.05), rel=1e-12)


def test_statistical_sensitivity_uses_authoritative_total_variance() -> None:
    engine = statistical(_ss_stack())
    sensitivity = statistical_sensitivity(_ss_stack())
    assert sensitivity.total_variance == engine.combined_sigma**2
    assert sensitivity.combined_sigma == engine.combined_sigma
    assert sensitivity.sigma_multiplier == engine.sigma_multiplier


def test_correlated_rss_engine_regression_unchanged() -> None:
    # Stage 15E hand example: rho = 0.5 -> Var = 0.05 + 2*0.5*0.1*0.2 = 0.07.
    correlations = (Correlation("A", "B", 0.5),)
    engine = statistical(_ss_stack(), correlations=correlations)
    sensitivity = statistical_sensitivity(_ss_stack(), correlations=correlations)
    assert engine.combined_sigma == pytest.approx(math.sqrt(0.07), rel=1e-12)
    assert sensitivity.total_variance == engine.combined_sigma**2
    assert sensitivity.covariance_pairs[0].covariance_term == pytest.approx(0.02)


def test_variance_decomposition_identity_with_correlation() -> None:
    # total_variance == sum(individual variances) + sum(covariance terms).
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.15, StackDirection.INVERSE),
        )
    )
    correlations = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    result = statistical_sensitivity(stack, correlations=correlations)
    decomposed = math.fsum(
        [c.variance for c in result.contributions]
        + [p.covariance_term for p in result.covariance_pairs]
    )
    assert decomposed == pytest.approx(result.total_variance, rel=1e-12)
    # Hand-calculated: 0.0725 + 0.024 + 0.024 = 0.1205.
    assert result.total_variance == pytest.approx(0.1205, rel=1e-12)


def test_covariance_fractions_sum_with_individual_fractions() -> None:
    # Signed fractions of variance sum to exactly 1.0 (no renormalization).
    stack = StatisticalStack(
        (
            StatisticalContribution("A", 100.0, 0.1),
            StatisticalContribution("B", 30.0, 0.2),
            StatisticalContribution("C", 20.0, 0.15, StackDirection.INVERSE),
        )
    )
    correlations = (Correlation("A", "B", 0.6), Correlation("B", "C", -0.4))
    result = statistical_sensitivity(stack, correlations=correlations)
    total = math.fsum(
        [c.fraction for c in result.contributions]
        + [p.fraction for p in result.covariance_pairs]
    )
    assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Validation propagation: invalid input stays invalid
# ---------------------------------------------------------------------------


def test_empty_worst_case_stack_rejected() -> None:
    with pytest.raises(InvalidStackError):
        worst_case_sensitivity(ToleranceStack(()))


def test_empty_statistical_stack_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical_sensitivity(StatisticalStack(()))


def test_invalid_sigma_multiplier_rejected_by_sensitivity() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical_sensitivity(_ss_stack(), sigma_multiplier=0.0)


def test_unknown_correlation_contributor_rejected_by_sensitivity() -> None:
    with pytest.raises(InvalidCorrelationError, match="unknown contributor"):
        statistical_sensitivity(_ss_stack(), correlations=(Correlation("Z", "B", 0.5),))


def test_non_psd_correlations_rejected_by_sensitivity() -> None:
    # Stage 15E non-PSD example: Var = 0.03 - 2*(0.9 + 0.9 + 0.9)*0.01 < 0.
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
    with pytest.raises(InvalidVarianceError, match="negative"):
        statistical_sensitivity(stack, correlations=correlations)