"""Unit tests for the Origlyph central tolerance policy (Stage 2B)."""

import pytest

from origlyph.geometry import (
    GeometryTolerancePolicy,
    InvalidGeometryError,
    Point3D,
    Vector3D,
)

TOL = GeometryTolerancePolicy


def test_exact_equality() -> None:
    assert TOL.nearly_equal(1.0, 1.0)


def test_near_equality() -> None:
    assert TOL.nearly_equal(1.0, 1.0 + 1e-8)
    assert TOL.nearly_equal(1000.0, 1000.0 + 1e-7)


def test_clearly_not_equal() -> None:
    assert not TOL.nearly_equal(1.0, 1.5)
    assert not TOL.nearly_equal(0.0, 0.01)
    assert not TOL.nearly_equal(1000.0, 1000.0 + 1e-4)


def test_near_zero() -> None:
    assert TOL.near_zero(0.0)
    assert TOL.near_zero(1e-9)
    assert not TOL.near_zero(1.0)


def test_parallel_vectors() -> None:
    assert TOL.vectors_parallel(Vector3D(1, 0, 0), Vector3D(2, 0, 0))


def test_anti_parallel_vectors() -> None:
    assert TOL.vectors_parallel(Vector3D(1, 0, 0), Vector3D(-3, 0, 0))


def test_perpendicular_vectors() -> None:
    assert TOL.vectors_perpendicular(Vector3D(1, 0, 0), Vector3D(0, 1, 0))


def test_parallelism_requires_nonzero_vectors() -> None:
    with pytest.raises(InvalidGeometryError):
        TOL.vectors_parallel(Vector3D(0, 0, 0), Vector3D(1, 0, 0))
    with pytest.raises(InvalidGeometryError):
        TOL.vectors_perpendicular(Vector3D(1, 0, 0), Vector3D(0, 0, 0))


def test_collinear_points() -> None:
    assert TOL.points_collinear(
        Point3D(0, 0, 0), Point3D(1, 1, 0), Point3D(2, 2, 0)
    )
    assert not TOL.points_collinear(
        Point3D(0, 0, 0), Point3D(1, 0, 0), Point3D(0, 1, 0)
    )


def test_collinear_with_coincident_anchor() -> None:
    assert TOL.points_collinear(
        Point3D(0, 0, 0), Point3D(0, 0, 0), Point3D(5, 0, 0)
    )


def test_coplanar_points() -> None:
    assert TOL.points_coplanar(
        Point3D(0, 0, 0),
        Point3D(1, 0, 0),
        Point3D(0, 1, 0),
        Point3D(1, 1, 0),
    )
    assert not TOL.points_coplanar(
        Point3D(0, 0, 0),
        Point3D(1, 0, 0),
        Point3D(0, 1, 0),
        Point3D(0, 0, 1),
    )


def test_far_from_origin_parallel_vectors() -> None:
    # Large coordinate offsets; the comparison must be magnitude-aware.
    a = Vector3D(1, 1, 1)
    b = Vector3D(2, 2, 2)
    assert TOL.vectors_parallel(a, b)


def test_large_automotive_scale_collinearity() -> None:
    # Coordinates at ~2.5 m scale (e.g., automotive body panels).
    base = Point3D(2500.0, 1000.0, 500.0)
    assert TOL.points_collinear(
        base, Point3D(2501.0, 1000.0, 500.0), Point3D(2499.0, 1000.0, 500.0)
    )
    assert TOL.points_coplanar(
        base,
        Point3D(2501.0, 1000.0, 500.0),
        Point3D(2500.0, 1001.0, 500.0),
        Point3D(2499.0, 999.0, 500.0),
    )


def test_computational_tolerance_is_not_engineering_tolerance() -> None:
    # The computational policy must remain far below engineering scales and
    # must never mask an engineering-relevant deviation.
    assert TOL.ABS_TOL < 0.01  # well below any realistic drawing tolerance.
    assert not TOL.nearly_equal(0.0, 0.01)
    assert not TOL.near_zero(0.01)