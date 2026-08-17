"""Unit tests for the Origlyph geometry primitives (Stage 2B)."""

import dataclasses

import pytest

from origlyph.geometry import (
    InvalidGeometryError,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)


def test_point_construction_coerces_to_float() -> None:
    point = Point3D(1, 2, 3)
    assert point.x == 1.0
    assert point.y == 2.0
    assert point.z == 3.0


def test_point_subtract_returns_vector() -> None:
    diff = Point3D(4, 5, 6) - Point3D(1, 1, 1)
    assert isinstance(diff, Vector3D)
    assert diff == Vector3D(3, 4, 5)


def test_point_add_vector_returns_point() -> None:
    result = Point3D(1, 1, 1) + Vector3D(1, 2, 3)
    assert isinstance(result, Point3D)
    assert result == Point3D(2, 3, 4)


def test_value_objects_are_frozen() -> None:
    point = Point3D(0.0, 0.0, 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        point.x = 5.0  # type: ignore
    vector = Vector3D(1.0, 0.0, 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        vector.y = 5.0  # type: ignore


def test_zero_vector_construction_allowed() -> None:
    zero = Vector3D(0.0, 0.0, 0.0)
    assert zero.is_zero()
    assert zero.magnitude() == 0.0


def test_zero_vector_difference_allowed() -> None:
    resulting = Point3D(1, 2, 3) - Point3D(1, 2, 3)
    assert resulting.is_zero()


def test_zero_vector_normalization_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Vector3D(0.0, 0.0, 0.0).normalize()


def test_near_zero_normalization_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Vector3D(1e-9, 0.0, 0.0).normalize()


def test_vector_magnitude() -> None:
    assert Vector3D(3.0, 4.0, 0.0).magnitude() == 5.0
    assert Vector3D(1.0, 2.0, 2.0).magnitude() == 3.0


def test_vector_dot() -> None:
    assert Vector3D(1.0, 2.0, 3.0).dot(Vector3D(4.0, -5.0, 6.0)) == 12.0


def test_vector_cross() -> None:
    assert Vector3D(1.0, 0.0, 0.0).cross(Vector3D(0.0, 1.0, 0.0)) == Vector3D(
        0.0, 0.0, 1.0
    )


def test_normalization() -> None:
    unit = Vector3D(1.0, 2.0, 2.0).normalize()
    assert unit == Vector3D(1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0)


def test_zero_line_direction_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Line3D(point=Point3D(0, 0, 0), direction=Vector3D(0, 0, 0))


def test_zero_plane_normal_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Plane3D(point=Point3D(0, 0, 0), normal=Vector3D(0, 0, 0))


def test_line_direction_normalized_at_construction() -> None:
    line = Line3D(point=Point3D(0, 0, 0), direction=Vector3D(2, 0, 0))
    assert line.direction == Vector3D(1, 0, 0)


def test_plane_normal_normalized_at_construction() -> None:
    plane = Plane3D(point=Point3D(0, 0, 0), normal=Vector3D(0, 0, 5))
    assert plane.normal == Vector3D(0, 0, 1)