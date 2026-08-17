"""Unit tests for Origlyph coordinate frames and transforms (Stage 2B)."""

import pytest

from origlyph.geometry import (
    Angle,
    Frame,
    InvalidGeometryError,
    Point3D,
    Transform,
    Vector3D,
)


def test_identity_transform() -> None:
    transform = Transform.identity()
    point = Point3D(1, 2, 3)
    assert transform.apply_point(point) == point
    assert transform.apply_vector(Vector3D(4, 5, 6)) == Vector3D(4, 5, 6)


def test_translation() -> None:
    transform = Transform.translation(1, 2, 3)
    assert transform.apply_point(Point3D(0, 0, 0)) == Point3D(1, 2, 3)
    # Vectors translate unaffected.
    assert transform.apply_vector(Vector3D(1, 1, 1)) == Vector3D(1, 1, 1)


def test_90_degree_rotation_about_z() -> None:
    z_axis = Vector3D(0, 0, 1)
    rotation = Transform.rotation(z_axis, Angle.degrees(90))
    rotated = rotation.apply_point(Point3D(1, 0, 0))
    assert rotated.x == pytest.approx(0.0)
    assert rotated.y == pytest.approx(1.0)
    assert rotated.z == pytest.approx(0.0)


def test_180_degree_rotation_about_y() -> None:
    rotation = Transform.rotation(Vector3D(0, 1, 0), Angle.degrees(180))
    rotated = rotation.apply_point(Point3D(1, 0, 0))
    assert rotated.x == pytest.approx(-1.0)
    assert rotated.y == pytest.approx(0.0)
    assert rotated.z == pytest.approx(0.0)


def test_composition_order() -> None:
    translation = Transform.translation(10, 0, 0)
    rotation = Transform.rotation(Vector3D(0, 0, 1), Angle.degrees(90))
    # Apply translation first, then rotation.
    combined = rotation.compose(translation)
    result = combined.apply_point(Point3D(0, 0, 0))
    # (10,0,0) then rotated about z -> (0,10,0).
    assert result.x == pytest.approx(0.0)
    assert result.y == pytest.approx(10.0)
    assert result.z == pytest.approx(0.0)


def test_inverse_translation() -> None:
    transform = Transform.translation(1, 2, 3)
    inverse = transform.inverse()
    restored = inverse.apply_point(transform.apply_point(Point3D(5, 5, 5)))
    assert restored == Point3D(5, 5, 5)


def test_inverse_rotation() -> None:
    rotation = Transform.rotation(Vector3D(1, 0, 0), Angle.degrees(30))
    inverse = rotation.inverse()
    point = Point3D(0, 3, 4)
    restored = inverse.apply_point(rotation.apply_point(point))
    assert restored.x == pytest.approx(point.x)
    assert restored.y == pytest.approx(point.y)
    assert restored.z == pytest.approx(point.z)


def test_compose_with_inverse_is_identity() -> None:
    transform = Transform.rotation(Vector3D(0, 1, 0), Angle.degrees(45)).compose(
        Transform.translation(5, 0, 0)
    )
    combined = transform.compose(transform.inverse())
    point = Point3D(-3, 7, 2)
    result = combined.apply_point(point)
    assert result.x == pytest.approx(point.x)
    assert result.y == pytest.approx(point.y)
    assert result.z == pytest.approx(point.z)


def test_vector_transform_ignores_translation() -> None:
    translation = Transform.translation(100, 100, 100)
    assert translation.apply_vector(Vector3D(1, 2, 3)) == Vector3D(1, 2, 3)


def test_world_frame() -> None:
    frame = Frame.world()
    assert frame.origin == Point3D(0, 0, 0)
    assert frame.x_axis == Vector3D(1, 0, 0)
    assert frame.y_axis == Vector3D(0, 1, 0)
    assert frame.z_axis == Vector3D(0, 0, 1)


def test_valid_right_handed_frame() -> None:
    frame = Frame(
        origin=Point3D(1, 2, 3),
        x_axis=Vector3D(1, 0, 0),
        y_axis=Vector3D(0, 1, 0),
        z_axis=Vector3D(0, 0, 1),
    )
    assert frame.origin == Point3D(1, 2, 3)


def test_invalid_left_handed_frame_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Frame(
            origin=Point3D(0, 0, 0),
            x_axis=Vector3D(1, 0, 0),
            y_axis=Vector3D(0, 1, 0),
            z_axis=Vector3D(0, 0, -1),
        )


def test_invalid_non_orthonormal_frame_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Frame(
            origin=Point3D(0, 0, 0),
            x_axis=Vector3D(1, 0, 0),
            y_axis=Vector3D(1, 0, 0),
            z_axis=Vector3D(0, 0, 1),
        )


def test_invalid_zero_axis_frame_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Frame(
            origin=Point3D(0, 0, 0),
            x_axis=Vector3D(1, 0, 0),
            y_axis=Vector3D(0, 0, 0),
            z_axis=Vector3D(0, 0, 1),
        )


def test_rotation_zero_axis_rejected() -> None:
    with pytest.raises(InvalidGeometryError):
        Transform.rotation(Vector3D(0, 0, 0), Angle.degrees(45))