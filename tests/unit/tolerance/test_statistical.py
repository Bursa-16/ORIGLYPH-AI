"""Unit tests for the Origlyph deterministic 1D statistical engine (Stage 15D).

All expected values are hand-calculated independently of the implementation.
Floating-point comparisons use pytest.approx to handle IEEE 754 rounding.
"""

from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    InvalidStatisticalError,
    OriglyphToleranceError,
    StackDirection,
    StatisticalContribution,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
    statistical,
    worst_case,
)


def _sc(
    name: str = "x",
    nominal: float = 10.0,
    sigma: float = 0.1,
    direction: StackDirection = StackDirection.FORWARD,
) -> StatisticalContribution:
    return StatisticalContribution(
        name=name,
        nominal=nominal,
        sigma=sigma,
        direction=direction,
    )


def _sstack(*contributions: StatisticalContribution) -> StatisticalStack:
    return StatisticalStack(contributions=contributions)


# --------------------------------------------------------------------------- #
# A. Simple RSS — two contributors
# --------------------------------------------------------------------------- #
def test_two_contributors_rss() -> None:
    """Hand-calculated: sigma1=0.1, sigma2=0.2.

    combined_sigma = sqrt(0.1^2 + 0.2^2) = sqrt(0.05)
    """
    result = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
        _sc(name="B", nominal=50.0, sigma=0.2),
    ))
    expected_sigma = math.sqrt(0.01 + 0.04)
    assert result.nominal == pytest.approx(150.0)
    assert result.combined_sigma == pytest.approx(expected_sigma)
    assert result.sigma_multiplier == pytest.approx(1.0)
    assert result.lower_bound == pytest.approx(150.0 - expected_sigma)
    assert result.upper_bound == pytest.approx(150.0 + expected_sigma)


def test_two_contributors_explicit_numerical() -> None:
    """Assert explicit numerical result for two-contributor RSS."""
    result = statistical(_sstack(
        _sc(name="A", nominal=10.0, sigma=0.1),
        _sc(name="B", nominal=20.0, sigma=0.2),
    ))
    assert result.combined_sigma == pytest.approx(0.22360679774997896)
    assert result.nominal == pytest.approx(30.0)


# --------------------------------------------------------------------------- #
# B. Three-contributor RSS
# --------------------------------------------------------------------------- #
def test_three_contributors_rss() -> None:
    """Hand-calculated: sigma1=0.1, sigma2=0.15, sigma3=0.2.

    combined_sigma = sqrt(0.01 + 0.0225 + 0.04) = sqrt(0.0725)
    """
    result = statistical(_sstack(
        _sc(name="A", nominal=50.0, sigma=0.1),
        _sc(name="B", nominal=30.0, sigma=0.15),
        _sc(name="C", nominal=20.0, sigma=0.2),
    ))
    expected_sigma = math.sqrt(0.01 + 0.0225 + 0.04)
    assert result.nominal == pytest.approx(100.0)
    assert result.combined_sigma == pytest.approx(expected_sigma)
    assert result.lower_bound == pytest.approx(100.0 - expected_sigma)
    assert result.upper_bound == pytest.approx(100.0 + expected_sigma)


# --------------------------------------------------------------------------- #
# C. Sign handling
# --------------------------------------------------------------------------- #
def test_inverse_direction_changes_nominal_not_sigma() -> None:
    """INVERSE direction changes nominal but not sigma contribution."""
    forward = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
        _sc(name="B", nominal=40.0, sigma=0.2),
    ))
    inverse = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
        _sc(name="B", nominal=40.0, sigma=0.2,
            direction=StackDirection.INVERSE),
    ))
    assert forward.nominal == pytest.approx(140.0)
    assert inverse.nominal == pytest.approx(60.0)
    assert forward.combined_sigma == pytest.approx(inverse.combined_sigma)


def test_negative_nominal_forward() -> None:
    result = statistical(_sstack(
        _sc(name="neg", nominal=-25.0, sigma=0.05),
    ))
    assert result.nominal == pytest.approx(-25.0)
    assert result.combined_sigma == pytest.approx(0.05)
    assert result.lower_bound == pytest.approx(-25.05)
    assert result.upper_bound == pytest.approx(-24.95)


# --------------------------------------------------------------------------- #
# D. Sigma multiplier
# --------------------------------------------------------------------------- #
def test_k_equals_1() -> None:
    result = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
    ), sigma_multiplier=1.0)
    assert result.sigma_multiplier == pytest.approx(1.0)
    assert result.lower_bound == pytest.approx(99.9)
    assert result.upper_bound == pytest.approx(100.1)


def test_k_equals_2() -> None:
    result = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
    ), sigma_multiplier=2.0)
    assert result.sigma_multiplier == pytest.approx(2.0)
    assert result.lower_bound == pytest.approx(99.8)
    assert result.upper_bound == pytest.approx(100.2)


def test_k_equals_3() -> None:
    result = statistical(_sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
    ), sigma_multiplier=3.0)
    assert result.sigma_multiplier == pytest.approx(3.0)
    assert result.lower_bound == pytest.approx(99.7)
    assert result.upper_bound == pytest.approx(100.3)

# --------------------------------------------------------------------------- #
# E. Zero sigma
# --------------------------------------------------------------------------- #
def test_zero_sigma_contribution() -> None:
    """All-zero statistical uncertainty produces exact bounds."""
    result = statistical(_sstack(
        _sc(name="exact", nominal=50.0, sigma=0.0),
    ))
    assert result.combined_sigma == pytest.approx(0.0)
    assert result.lower_bound == pytest.approx(50.0)
    assert result.upper_bound == pytest.approx(50.0)


def test_mixed_zero_and_nonzero_sigma() -> None:
    """Zero-sigma contributor adds no uncertainty."""
    result = statistical(_sstack(
        _sc(name="exact", nominal=50.0, sigma=0.0),
        _sc(name="stat", nominal=30.0, sigma=0.15),
    ))
    assert result.nominal == pytest.approx(80.0)
    assert result.combined_sigma == pytest.approx(0.15)
    assert result.lower_bound == pytest.approx(79.85)
    assert result.upper_bound == pytest.approx(80.15)


# --------------------------------------------------------------------------- #
# F. Invalid inputs
# --------------------------------------------------------------------------- #
def test_negative_sigma_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="bad", nominal=10.0, sigma=-0.1)


def test_nan_sigma_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="nan", nominal=10.0, sigma=float("nan"))


def test_infinity_sigma_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="inf", nominal=10.0, sigma=float("inf"))


def test_negative_infinity_sigma_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="neg_inf", nominal=10.0, sigma=float("-inf"))


def test_nan_nominal_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="nan_nom", nominal=float("nan"), sigma=0.1)


def test_infinity_nominal_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        _sc(name="inf_nom", nominal=float("inf"), sigma=0.1)


def test_zero_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(_sstack(_sc(name="A", sigma=0.1)), sigma_multiplier=0.0)


def test_negative_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(_sstack(_sc(name="A", sigma=0.1)), sigma_multiplier=-1.0)


def test_nan_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(_sstack(_sc(name="A", sigma=0.1)),
                   sigma_multiplier=float("nan"))


def test_infinity_multiplier_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(_sstack(_sc(name="A", sigma=0.1)),
                   sigma_multiplier=float("inf"))


def test_empty_stack_rejected() -> None:
    with pytest.raises(InvalidStatisticalError):
        statistical(StatisticalStack(contributions=()))


def test_exception_hierarchy() -> None:
    """All statistical errors derive from OriglyphToleranceError."""
    with pytest.raises(OriglyphToleranceError):
        _sc(name="bad", sigma=-0.1)
    with pytest.raises(OriglyphToleranceError):
        statistical(StatisticalStack(contributions=()))


# --------------------------------------------------------------------------- #
# G. Determinism
# --------------------------------------------------------------------------- #
def test_repeated_execution_identical() -> None:
    stack = _sstack(
        _sc(name="A", nominal=100.0, sigma=0.1),
        _sc(name="B", nominal=40.0, sigma=0.2),
        _sc(name="C", nominal=30.0, sigma=0.15),
    )
    first = statistical(stack)
    for _ in range(10):
        assert statistical(stack) == first


# --------------------------------------------------------------------------- #
# I. Method separation
# --------------------------------------------------------------------------- #
def test_worst_case_unchanged() -> None:
    """Verify worst-case engine behavior is not affected by statistical."""
    stack = ToleranceStack(contributions=(
        ToleranceContribution(
            name="A", nominal=100.0,
            lower_deviation=-0.1, upper_deviation=0.2,
        ),
        ToleranceContribution(
            name="B", nominal=40.0,
            lower_deviation=-0.05, upper_deviation=0.1,
            direction=StackDirection.INVERSE,
        ),
    ))
    result = worst_case(stack)
    assert isinstance(result, WorstCaseResult)
    assert result.nominal == pytest.approx(60.0)
    assert result.minimum == pytest.approx(59.80)
    assert result.maximum == pytest.approx(60.25)


def test_statistical_and_worst_case_are_distinct_types() -> None:
    """StatisticalResult and WorstCaseResult are different types."""
    stat_result = statistical(_sstack(_sc(name="A", sigma=0.1)))
    assert not isinstance(stat_result, WorstCaseResult)


def test_statistical_does_not_modify_worst_case_module() -> None:
    """Importing statistical does not break worst_case imports."""
    from origlyph.tolerance import statistical as stat
    from origlyph.tolerance import worst_case as wc
    assert callable(wc)
    assert callable(stat)

