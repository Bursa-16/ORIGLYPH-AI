"""Origlyph geometry domain (Stage 2B foundation).

Exposes only the approved public geometry API. Pure value objects carry no
provenance, source IDs, or unit metadata.
"""

from .exceptions import (
    InvalidGeometryError,
    OriglyphGeometryError,
    UnitError,
    UnsupportedGeometryError,
)
from .frames import Frame, Transform
from .operations import (
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
from .primitives import Line3D, Plane3D, Point3D, Vector3D
from .tolerance import GeometryTolerancePolicy
from .units import Angle, Length, as_angle, as_length

__all__ = [
    "Angle",
    "Frame",
    "GeometryTolerancePolicy",
    "InvalidGeometryError",
    "Length",
    "Line3D",
    "OriglyphGeometryError",
    "Plane3D",
    "Point3D",
    "Transform",
    "UnitError",
    "UnsupportedGeometryError",
    "Vector3D",
    "angle_line_to_line",
    "angle_line_to_plane",
    "angle_plane_to_plane",
    "as_angle",
    "as_length",
    "closest_point_on_line",
    "closest_point_on_plane",
    "distance_point_to_line",
    "distance_point_to_plane",
    "distance_point_to_point",
    "project_point_onto_line",
    "project_point_onto_plane",
    "project_vector_onto",
]