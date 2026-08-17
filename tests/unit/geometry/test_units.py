"""Unit tests for the Origlyph geometry unit handling (Stage 2B)."""

import math

import pytest

from origlyph.geometry import Angle, Length, UnitError, as_angle, as_length


def test_length_mm_canonical() -> None:
    assert Length.millimetres(25.4).mm == 25.4


def test_length_conversions_to_mm() -> None:
    assert as_length(1, "cm").mm == 10.0
    assert as_length(1, "m").mm == 1000.0
    assert as_length(1, "inch").mm == 25.4


def test_length_conversion_from_mm() -> None:
    assert Length.millimetres(25.4).in_unit("inch") == pytest.approx(1.0)
    assert Length.millimetres(1000.0).in_unit("m") == pytest.approx(1.0)


def test_angle_conversions() -> None:
    assert as_angle(180, "degree").rad == pytest.approx(math.pi)
    assert as_angle(90, "deg").rad == pytest.approx(math.pi / 2)
    assert as_angle(1, "radian").rad == 1.0


def test_angle_conversion_from_radians() -> None:
    assert Angle.radians(math.pi).in_unit("degree") == pytest.approx(180.0)


def test_angle_helpers() -> None:
    assert Angle.degrees(180).rad == pytest.approx(math.pi)
    assert Angle.radians(1.0).rad == 1.0


def test_unit_case_and_whitespace_insensitive() -> None:
    assert as_length(1, "  CM ").mm == 10.0
    assert as_angle(180, "DEGREE").rad == pytest.approx(math.pi)


@pytest.mark.parametrize(
    ("function", "value", "unit"),
    [
        (as_length, 1.0, "furlong"),
        (as_length, 1.0, ""),
        (as_length, 1.0, "rad"),
        (as_angle, 1.0, "mm"),
        (as_angle, 1.0, "seconds"),
        (as_length, 1.0, "in"),  # unambiguous alternative names are not guessed
    ],
)
def test_unsupported_or_wrong_dimension_units_fail_closed(
    function, value: float, unit: str
) -> None:
    with pytest.raises(UnitError):
        function(value, unit)


def test_length_and_angle_are_dimensionally_distinct() -> None:
    length = as_length(1, "mm")
    angle = as_angle(1, "rad")
    assert length != angle
    assert not isinstance(length, Angle)
    assert not isinstance(angle, Length)
    assert type(length).__name__ == "Length"
    assert type(angle).__name__ == "Angle"