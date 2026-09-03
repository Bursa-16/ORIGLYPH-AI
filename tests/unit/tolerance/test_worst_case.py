"""Unit tests for the Origlyph deterministic 1D worst-case engine (Stage 15C-R).

All expected values are hand-calculated independently of the implementation.
Floating-point comparisons use pytest.approx to handle IEEE 754 rounding.
"""

from __future__ import annotations

import pytest

from origlyph.tolerance import (
    InvalidStackError,
    OriglyphToleranceError,
    StackDirection,
    ToleranceContribution,
    ToleranceStack,
    worst_case,
)


def _tc(
    name: str = "x",
    nominal: float = 10.0,
    lower: float = -0.1,
    upper: float = 0.1,
    direction: StackDirection = StackDirection.FORWARD,
) -> ToleranceContribution:
    return ToleranceContribution(
        name=name,
        nominal=nominal,
        lower_deviation=lower,
        upper_deviation=upper,
        direction=direction,
    )


def _stack(*contributions: ToleranceContribution) -> ToleranceStack:
    return ToleranceStack(contributions=contributions)


# --------------------------------------------------------------------------- #
# Single contributor
# --------------------------------------------------------------------------- #
def test_single_forward_symmetric() -> None:
    result = worst_case(_stack(_tc(name="A", nominal=100.0, lower=-0.1, upper=0.2)))
    assert result.nominal == pytest.approx(100.0)
    assert result.minimum == pytest.approx(99.9)
    assert result.maximum == pytest.approx(100.2)
    assert result.lower_deviation == pytest.approx(-0.1)
    assert result.upper_deviation == pytest.approx(0.2)
    assert result.total_span == pytest.approx(0.3)


def test_single_inverse() -> None:
    result = worst_case(_stack(
        _tc(name="B", nominal=40.0, lower=-0.05, upper=0.1,
            direction=StackDirection.INVERSE)
    ))
    assert result.nominal == pytest.approx(-40.0)
    assert result.minimum == pytest.approx(-40.1)
    assert result.maximum == pytest.approx(-39.95)
    assert result.lower_deviation == pytest.approx(-0.1)
    assert result.upper_deviation == pytest.approx(0.05)
    assert result.total_span == pytest.approx(0.15)


# --------------------------------------------------------------------------- #
# Multiple positive contributors
# --------------------------------------------------------------------------- #
def test_two_forward_symmetric() -> None:
    result = worst_case(_stack(
        _tc(name="A", nominal=100.0),
        _tc(name="B", nominal=50.0, lower=-0.05, upper=0.15),
    ))
    assert result.nominal == pytest.approx(150.0)
    assert result.minimum == pytest.approx(149.85)
    assert result.maximum == pytest.approx(150.25)
    assert result.lower_deviation == pytest.approx(-0.15)
    assert result.upper_deviation == pytest.approx(0.25)
    assert result.total_span == pytest.approx(0.40)


def test_three_forward() -> None:
    result = worst_case(_stack(
        _tc(name="A", nominal=80.0),
        _tc(name="B", nominal=60.0, lower=-0.05, upper=0.05),
        _tc(name="C", nominal=40.0, lower=-0.08, upper=0.12),
    ))
    assert result.nominal == pytest.approx(180.0)
    assert result.minimum == pytest.approx(179.77)
    assert result.maximum == pytest.approx(180.27)
    assert result.lower_deviation == pytest.approx(-0.23)
    assert result.upper_deviation == pytest.approx(0.27)
    assert result.total_span == pytest.approx(0.50)


# --------------------------------------------------------------------------- #
# Mixed positive / negative directions (subtraction stacks)
# --------------------------------------------------------------------------- #
def test_a_minus_b_hand_calculated() -> None:
    """Hand-calculated stack = A - B.

    A = 100 +0.20/-0.10 (FORWARD), B = 40 +0.10/-0.05 (INVERSE)

    A (FORWARD): interval = [99.90, 100.20]
    B (INVERSE): interval in stack = [-(40.0+0.10), -(40.0-0.05)] = [-40.10, -39.95]

    nominal = 100.0 - 40.0 = 60.0
    minimum  = 99.90 + (-40.10) = 59.80
    maximum  = 100.20 + (-39.95) = 60.25
    """
    result = worst_case(_stack(
        _tc(name="A", nominal=100.0, lower=-0.10, upper=0.20),
        _tc(name="B", nominal=40.0, lower=-0.05, upper=0.10,
            direction=StackDirection.INVERSE),
    ))
    assert result.nominal == pytest.approx(60.0)
    assert result.minimum == pytest.approx(59.80)
    assert result.maximum == pytest.approx(60.25)
    assert result.lower_deviation == pytest.approx(-0.20)
    assert result.upper_deviation == pytest.approx(0.25)
    assert result.total_span == pytest.approx(0.45)


def test_three_contributors_mixed_signs() -> None:
    """Hand-calculated stack = A - B + C with mixed directions.

    A=50 +0.1/-0.05 (FWD), B=20 +0.05/-0.02 (INV), C=30 +0.08/-0.04 (FWD).

    A (FWD): [49.95, 50.10]
    B (INV): [-(20.0+0.05), -(20.0-0.02)] = [-20.05, -19.98]
    C (FWD): [29.96, 30.08]

    nominal = 50.0 - 20.0 + 30.0 = 60.0
    minimum  = 49.95 + (-20.05) + 29.96 = 59.86
    maximum  = 50.10 + (-19.98) + 30.08 = 60.20
    """
    result = worst_case(_stack(
        _tc(name="A", nominal=50.0, lower=-0.05, upper=0.10),
        _tc(name="B", nominal=20.0, lower=-0.02, upper=0.05,
            direction=StackDirection.INVERSE),
        _tc(name="C", nominal=30.0, lower=-0.04, upper=0.08),
    ))
    assert result.nominal == pytest.approx(60.0)
    assert result.minimum == pytest.approx(59.86)
    assert result.maximum == pytest.approx(60.20)
    assert result.lower_deviation == pytest.approx(-0.14)
    assert result.upper_deviation == pytest.approx(0.20)
    assert result.total_span == pytest.approx(0.34)

# --------------------------------------------------------------------------- #
# Symmetric tolerances
# --------------------------------------------------------------------------- #
def test_two_symmetric() -> None:
    result = worst_case(_stack(
        _tc(name="A", nominal=100.0),
        _tc(name="B", nominal=50.0),
    ))
    assert result.nominal == pytest.approx(150.0)
    assert result.minimum == pytest.approx(149.8)
    assert result.maximum == pytest.approx(150.2)
    assert result.lower_deviation == pytest.approx(-0.2)
    assert result.upper_deviation == pytest.approx(0.2)
    assert result.total_span == pytest.approx(0.4)


# --------------------------------------------------------------------------- #
# Asymmetric tolerances
# --------------------------------------------------------------------------- #
def test_two_asymmetric() -> None:
    result = worst_case(_stack(
        _tc(name="A", nominal=100.0, lower=-0.05, upper=0.20),
        _tc(name="B", nominal=50.0, lower=-0.10, upper=0.05),
    ))
    assert result.nominal == pytest.approx(150.0)
    assert result.minimum == pytest.approx(149.85)
    assert result.maximum == pytest.approx(150.25)
    assert result.lower_deviation == pytest.approx(-0.15)
    assert result.upper_deviation == pytest.approx(0.25)
    assert result.total_span == pytest.approx(0.40)


# --------------------------------------------------------------------------- #
# Unilateral tolerances
# --------------------------------------------------------------------------- #
def test_unilateral_positive() -> None:
    result = worst_case(_stack(
        _tc(name="gap", nominal=10.0, lower=0.0, upper=0.3),
    ))
    assert result.nominal == pytest.approx(10.0)
    assert result.minimum == pytest.approx(10.0)
    assert result.maximum == pytest.approx(10.3)
    assert result.lower_deviation == pytest.approx(0.0)
    assert result.upper_deviation == pytest.approx(0.3)


def test_unilateral_negative() -> None:
    result = worst_case(_stack(
        _tc(name="interference", nominal=5.0, lower=-0.2, upper=0.0),
    ))
    assert result.nominal == pytest.approx(5.0)
    assert result.minimum == pytest.approx(4.8)
    assert result.maximum == pytest.approx(5.0)
    assert result.lower_deviation == pytest.approx(-0.2)
    assert result.upper_deviation == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Zero deviations
# --------------------------------------------------------------------------- #
def test_zero_deviation_contribution() -> None:
    result = worst_case(_stack(
        _tc(name="exact", nominal=25.0, lower=0.0, upper=0.0),
    ))
    assert result.nominal == pytest.approx(25.0)
    assert result.minimum == pytest.approx(25.0)
    assert result.maximum == pytest.approx(25.0)
    assert result.total_span == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Negative nominal dimensions
# --------------------------------------------------------------------------- #
def test_negative_nominal_forward() -> None:
    result = worst_case(_stack(
        _tc(name="neg", nominal=-30.0),
    ))
    assert result.nominal == pytest.approx(-30.0)
    assert result.minimum == pytest.approx(-30.1)
    assert result.maximum == pytest.approx(-29.9)


def test_negative_nominal_inverse() -> None:
    result = worst_case(_stack(
        _tc(name="neg_inv", nominal=-20.0, lower=-0.05, upper=0.05,
            direction=StackDirection.INVERSE),
    ))
    assert result.nominal == pytest.approx(20.0)
    assert result.minimum == pytest.approx(19.95)
    assert result.maximum == pytest.approx(20.05)


# --------------------------------------------------------------------------- #
# Cancellation of nominal values
# --------------------------------------------------------------------------- #
def test_nominal_cancellation() -> None:
    result = worst_case(_stack(
        _tc(name="A", nominal=50.0),
        _tc(name="B", nominal=50.0, direction=StackDirection.INVERSE),
    ))
    assert result.nominal == pytest.approx(0.0)
    assert result.minimum == pytest.approx(-0.2)
    assert result.maximum == pytest.approx(0.2)
    assert result.total_span == pytest.approx(0.4)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_repeated_execution_identical() -> None:
    stack = _stack(
        _tc(name="A", nominal=100.0, lower=-0.1, upper=0.2),
        _tc(name="B", nominal=40.0, direction=StackDirection.INVERSE),
        _tc(name="C", nominal=30.0, lower=-0.04, upper=0.08),
    )
    first = worst_case(stack)
    for _ in range(10):
        assert worst_case(stack) == first


# --------------------------------------------------------------------------- #
# Empty stack behavior
# --------------------------------------------------------------------------- #
def test_empty_stack_rejected_at_construction() -> None:
    with pytest.raises(InvalidStackError):
        ToleranceStack(contributions=())


def test_empty_stack_exception_hierarchy() -> None:
    with pytest.raises(OriglyphToleranceError):
        ToleranceStack(contributions=())

