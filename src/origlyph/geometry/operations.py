"""Stage 2B deterministic geometry operations.

Foundation set only: distances, angles, projections, and closest-point
computations for the four primitives. No intersections, no CAD, no kernels.

Return types are domain results: :class:`~.units.Length`,
:class:`~.units.Angle`, :class:`~.primitives.Point3D`, or
:class:`~.primitives.Vector3D`.
"""

from __future__ import annotations

import math

from .exceptions import InvalidGeometryError
from .primitives import Line3D, Plane3D, Point3D, Vector3D
from .units import Angle, Length


def _clamp_unit(value: float) -> float:
    """Clamp a cosine to the valid [-1, 1] range for acos/asin."""
    return max(-1.0, min(1.0, value))


# --------------------------------------------------------------------------- #
# Distances
# --------------------------------------------------------------------------- #
def distance_point_to_point(p1: Point3D, p2: Point3D) -> Length:
    """Distance in millimetres between two points."""
    return Length.millimetres((p2 - p1).magnitude())


def distance_point_to_line(point: Point3D, line: Line3D) -> Length:
    """Distance in millimetres from a point to an infinite line."""
    diff = point - line.point
    return Length.millimetres(line.direction.cross(diff).magnitude())


def distance_point_to_plane(point: Point3D, plane: Plane3D) -> Length:
    """Absolute distance in millimetres from a point to a plane."""
    diff = point - plane.point
    return Length.millimetres(abs(plane.normal.dot(diff)))


# --------------------------------------------------------------------------- #
# Angles
# --------------------------------------------------------------------------- #
def angle_line_to_line(line_a: Line3D, line_b: Line3D) -> Angle:
    """Acute angle in radians between two lines' directions."""
    cos_theta = _clamp_unit(abs(line_a.direction.dot(line_b.direction)))
    return Angle.radians(math.acos(cos_theta))


def angle_line_to_plane(line: Line3D, plane: Plane3D) -> Angle:
    """Angle in radians between a line and a plane (0 when parallel)."""
    sin_theta = _clamp_unit(abs(line.direction.dot(plane.normal)))
    return Angle.radians(math.asin(sin_theta))


def angle_plane_to_plane(plane_a: Plane3D, plane_b: Plane3D) -> Angle:
    """Acute dihedral angle in radians between two planes."""
    cos_theta = _clamp_unit(abs(plane_a.normal.dot(plane_b.normal)))
    return Angle.radians(math.acos(cos_theta))


# --------------------------------------------------------------------------- #
# Projections
# --------------------------------------------------------------------------- #
def project_point_onto_line(point: Point3D, line: Line3D) -> Point3D:
    """Orthogonal projection of a point onto an infinite line."""
    diff = point - line.point
    scalar = diff.dot(line.direction)
    return line.point + line.direction.scaled(scalar)


def project_point_onto_plane(point: Point3D, plane: Plane3D) -> Point3D:
    """Orthogonal projection of a point onto a plane."""
    diff = point - plane.point
    scalar = plane.normal.dot(diff)
    n = plane.normal
    return Point3D(
        point.x - n.x * scalar,
        point.y - n.y * scalar,
        point.z - n.z * scalar,
    )


def project_vector_onto(vector: Vector3D, onto: Vector3D) -> Vector3D:
    """Project a vector onto a non-zero direction vector."""
    if onto.is_zero():
        raise InvalidGeometryError("cannot project onto a zero vector")
    direction = onto.normalize()
    return direction.scaled(vector.dot(direction))


# --------------------------------------------------------------------------- #
# Closest point
# --------------------------------------------------------------------------- #
def closest_point_on_line(point: Point3D, line: Line3D) -> Point3D:
    """Closest point on the line to ``point`` (its orthogonal projection)."""
    return project_point_onto_line(point, line)


def closest_point_on_plane(point: Point3D, plane: Plane3D) -> Point3D:
    """Closest point on the plane to ``point`` (its orthogonal projection)."""
    return project_point_onto_plane(point, plane)