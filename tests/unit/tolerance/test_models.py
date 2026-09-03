"""Unit tests for the Origlyph tolerance domain models (Stage 15C-R)."""

import math

import pytest

from origlyph.tolerance import (
    InvalidStackError,
    InvalidToleranceError,
    OriglyphToleranceError,
    StackDirection,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
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


# --------------------------------------------------------------------------- #
# ToleranceContribution — valid construction
# --------------------------------------------------------------------------- #
def test_symmetric_tolerance() -> None:
    tc = _tc(name="plate", nominal=50.0, lower=-0.1, upper=0.1)
    assert tc.name == "plate"
    assert tc.nominal == 50.0
    assert tc.lower_deviation == -0.1
    assert tc.upper_deviation == 0.1
    assert tc.direction == StackDirection.FORWARD


def test_asymmetric_tolerance() -> None:
    tc = _tc(name="shaft", nominal=30.0, lower=-0.05, upper=0.15)
    assert tc.lower_deviation == -0.05
    assert tc.upper_deviation == 0.15


def test_unilateral_tolerance_positive() -> None:
    tc = _tc(name="gap", nominal=10.0, lower=0.0, upper=0.2)
    assert tc.lower_deviation == 0.0
    assert tc.upper_deviation == 0.2


def test_unilateral_tolerance_negative() -> None:
    tc = _tc(name="interference", nominal=5.0, lower=-0.3, upper=0.0)
    assert tc.lower_deviation == -0.3
    assert tc.upper_deviation == 0.0


def test_negative_nominal() -> None:
    tc = _tc(name="offset", nominal=-20.0, lower=-0.1, upper=0.1)
    assert tc.nominal == -20.0


def test_zero_nominal() -> None:
    tc = _tc(name="zero_ref", nominal=0.0, lower=-0.05, upper=0.05)
    assert tc.nominal == 0.0


def test_inverse_direction() -> None:
    tc = _tc(name="hole", nominal=25.0, direction=StackDirection.INVERSE)
    assert tc.direction == StackDirection.INVERSE


def test_integer_inputs_coerced_to_float() -> None:
    tc = _tc(name="int_test", nominal=100, lower=-1, upper=1)
    assert isinstance(tc.nominal, float)
    assert isinstance(tc.lower_deviation, float)
    assert isinstance(tc.upper_deviation, float)
    assert tc.nominal == 100.0


def test_frozen_immutability() -> None:
    tc = _tc(name="frozen")
    with pytest.raises(AttributeError):
        tc.nominal = 20.0  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# ToleranceContribution — interval computation
# --------------------------------------------------------------------------- #
def test_forward_interval() -> None:
    tc = _tc(name="fwd", nominal=100.0, lower=-0.1, upper=0.2)
    assert tc.interval() == (99.9, 100.2)


def test_inverse_interval_reversed() -> None:
    tc = _tc(
        name="inv", nominal=40.0, lower=-0.05, upper=0.1,
        direction=StackDirection.INVERSE,
    )
    assert tc.interval() == (-40.1, -39.95)


def test_zero_deviations_interval() -> None:
    tc = _tc(name="exact", nominal=50.0, lower=0.0, upper=0.0)
    assert tc.interval() == (50.0, 50.0)


# --------------------------------------------------------------------------- #
# ToleranceContribution — validation rejections
# --------------------------------------------------------------------------- #
def test_lower_exceeds_upper_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="bad", nominal=10.0, lower=0.2, upper=0.1)


def test_nan_nominal_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="nan_nom", nominal=math.nan)


def test_nan_lower_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="nan_low", lower=math.nan)


def test_nan_upper_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="nan_up", upper=math.nan)


def test_positive_infinity_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="inf", nominal=math.inf)


def test_negative_infinity_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        _tc(name="neg_inf", nominal=-math.inf)


def test_exception_hierarchy() -> None:
    """All tolerance errors derive from OriglyphToleranceError."""
    with pytest.raises(OriglyphToleranceError):
        _tc(name="bad", lower=0.5, upper=0.1)
    with pytest.raises(OriglyphToleranceError):
        _tc(name="nan", nominal=math.nan)

# --------------------------------------------------------------------------- #
# ToleranceStack — construction and validation
# --------------------------------------------------------------------------- #
def test_single_contribution_stack() -> None:
    stack = ToleranceStack(contributions=(_tc(name="only"),))
    assert len(stack.contributions) == 1


def test_multiple_contributions_stack() -> None:
    a = _tc(name="a", nominal=100.0, lower=-0.1, upper=0.2)
    b = _tc(name="b", nominal=40.0, direction=StackDirection.INVERSE)
    stack = ToleranceStack(contributions=(a, b))
    assert len(stack.contributions) == 2
    assert stack.contributions[0].name == "a"
    assert stack.contributions[1].name == "b"


def test_empty_stack_rejected() -> None:
    with pytest.raises(InvalidStackError):
        ToleranceStack(contributions=())


def test_stack_exception_hierarchy() -> None:
    with pytest.raises(OriglyphToleranceError):
        ToleranceStack(contributions=())


# --------------------------------------------------------------------------- #
# WorstCaseResult — construction
# --------------------------------------------------------------------------- #
def test_valid_worst_case_result() -> None:
    result = WorstCaseResult(
        nominal=60.0,
        minimum=59.8,
        maximum=60.25,
        lower_deviation=-0.2,
        upper_deviation=0.25,
        total_span=0.45,
    )
    assert result.nominal == 60.0
    assert result.minimum == 59.8
    assert result.maximum == 60.25
    assert result.lower_deviation == -0.2
    assert result.upper_deviation == 0.25
    assert result.total_span == 0.45


def test_worst_case_result_nan_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        WorstCaseResult(
            nominal=math.nan,
            minimum=0.0,
            maximum=1.0,
            lower_deviation=0.0,
            upper_deviation=1.0,
            total_span=1.0,
        )


def test_worst_case_result_infinity_rejected() -> None:
    with pytest.raises(InvalidToleranceError):
        WorstCaseResult(
            nominal=0.0,
            minimum=-math.inf,
            maximum=1.0,
            lower_deviation=0.0,
            upper_deviation=1.0,
            total_span=1.0,
        )

