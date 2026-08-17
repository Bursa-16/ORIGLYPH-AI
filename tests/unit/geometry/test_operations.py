"""Unit tests for Stage 2B geometry operations (known analytic cases)."""

import math

import pytest

from origlyph.geometry import (
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
    angle_line_to_line,
    angle_line_to_plane,
    angle_plane_to_plane,
    closest_point_on_line,
    closest_point_on_plane,
    distance_point_to_line,
    distance_point_to_plane,
    distance_point_to_point,
    project_point_onto_line,
    project_point_onto_plane,
    project_vector_onto,
)

ORIGIN = Point3D(0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- #
# Distances
# --------------------------------------------------------------------------- #
def test_point_to_point_distance() -> None:
    assert distance_point_to_point(ORIGIN, Point3D(3, 4, 0)).mm == 5.0


def test_point_to_line_distance() -> None:
    line = Line3D(point=ORIGIN, direction=Vector3D(1, 0, 0))
    result = distance_point_to_line(Point3D(0, 3, 4), line)
    assert result.mm == pytest.approx(5.0)


def test_point_to_plane_distance() -> None:
    plane = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    assert distance_point_to_plane(Point3D(0, 0, 7), plane).mm == 7.0


# --------------------------------------------------------------------------- #
# Angles
# --------------------------------------------------------------------------- #
def test_line_to_line_angle_perpendicular() -> None:
    line_x = Line3D(point=ORIGIN, direction=Vector3D(1, 0, 0))
    line_y = Line3D(point=ORIGIN, direction=Vector3D(0, 1, 0))
    assert angle_line_to_line(line_x, line_y).rad == pytest.approx(math.pi / 2)


def test_line_to_line_angle_parallel() -> None:
    line_a = Line3D(point=ORIGIN, direction=Vector3D(1, 2, 0))
    line_b = Line3D(point=Point3D(5, 5, 5), direction=Vector3D(-2, -4, 0))
    assert angle_line_to_line(line_a, line_b).rad == pytest.approx(0.0, abs=1e-7)


def test_line_to_plane_angle_parallel() -> None:
    line = Line3D(point=ORIGIN, direction=Vector3D(1, 0, 0))
    plane_xy = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    assert angle_line_to_plane(line, plane_xy).rad == pytest.approx(0.0)


def test_line_to_plane_angle_perpendicular() -> None:
    line = Line3D(point=ORIGIN, direction=Vector3D(0, 0, 1))
    plane_xy = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    assert angle_line_to_plane(line, plane_xy).rad == pytest.approx(math.pi / 2)


def test_plane_to_plane_angle_perpendicular() -> None:
    plane_xy = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    plane_yz = Plane3D(point=ORIGIN, normal=Vector3D(1, 0, 0))
    assert angle_plane_to_plane(plane_xy, plane_yz).rad == pytest.approx(
        math.pi / 2
    )


def test_plane_to_plane_angle_parallel() -> None:
    plane_a = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    plane_b = Plane3D(point=Point3D(0, 0, 10), normal=Vector3D(0, 0, 1))
    assert angle_plane_to_plane(plane_a, plane_b).rad == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Projections and closest-point
# --------------------------------------------------------------------------- #
def test_point_projection_onto_line() -> None:
    line = Line3D(point=ORIGIN, direction=Vector3D(1, 0, 0))
    projected = project_point_onto_line(Point3D(2, 3, 4), line)
    assert projected == Point3D(2, 0, 0)


def test_closest_point_on_line() -> None:
    line = Line3D(point=ORIGIN, direction=Vector3D(1, 0, 0))
    assert closest_point_on_line(Point3D(0, 3, 4), line) == ORIGIN


def test_point_projection_onto_plane() -> None:
    plane = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    projected = project_point_onto_plane(Point3D(1, 2, 3), plane)
    assert projected == Point3D(1, 2, 0)


def test_closest_point_on_plane() -> None:
    plane = Plane3D(point=ORIGIN, normal=Vector3D(0, 0, 1))
    assert closest_point_on_plane(Point3D(4, 5, 6), plane) == Point3D(4, 5, 0)


def test_vector_projection() -> None:
    projected = project_vector_onto(Vector3D(2, 2, 0), Vector3D(1, 0, 0))
    assert projected == Vector3D(2, 0, 0)


def test_vector_projection_on_skew_direction() -> None:
    projected = project_vector_onto(Vector3D(0, 0, 1), Vector3D(1, 1, 0))
    assert projected == Vector3D(0, 0, 0)