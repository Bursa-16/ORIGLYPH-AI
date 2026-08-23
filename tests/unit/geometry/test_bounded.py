"""Stage 5C tests: BoundedPlanarFace pure-geometry foundation.

All coordinates are synthetic; no engineering/welding values appear.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from origlyph.geometry import (
    BoundedPlanarFace,
    GeometryTolerancePolicy,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)
from origlyph.geometry.exceptions import InvalidGeometryError

_SQUARE = (
    Point3D(0.0, 0.0, 0.0),
    Point3D(2.0, 0.0, 0.0),
    Point3D(2.0, 2.0, 0.0),
    Point3D(0.0, 2.0, 0.0),
)


def _square() -> BoundedPlanarFace:
    return BoundedPlanarFace(vertices=_SQUARE)


def _rectangle() -> BoundedPlanarFace:
    return BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(4.0, 0.0, 0.0),
            Point3D(4.0, 1.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
        )
    )


def _triangle() -> BoundedPlanarFace:
    return BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(3.0, 0.0, 0.0),
            Point3D(0.0, 3.0, 0.0),
        )
    )


def test_valid_square_constructs() -> None:
    face = _square()
    assert isinstance(face, BoundedPlanarFace)


def test_vertices_stored_as_tuple() -> None:
    face = _square()
    assert isinstance(face.vertices, tuple)
    assert all(isinstance(v, Point3D) for v in face.vertices)


def test_input_order_preserved() -> None:
    face = _square()
    assert face.vertices == _SQUARE


def test_square_area() -> None:
    assert _square().area == pytest.approx(4.0)


def test_rectangle_area() -> None:
    assert _rectangle().area == pytest.approx(4.0)


def test_translated_rectangle_area_invariant() -> None:
    shift = Vector3D(12.0, -7.0, 3.0)
    moved = BoundedPlanarFace(
        vertices=tuple(
            Point3D(v.x + shift.x, v.y + shift.y, v.z + shift.z)
            for v in _rectangle().vertices
        )
    )
    assert moved.area == pytest.approx(_rectangle().area)


def test_triangle_area() -> None:
    assert _triangle().area == pytest.approx(4.5)


def test_rectangle_centroid() -> None:
    centroid = _rectangle().centroid
    assert GeometryTolerancePolicy.nearly_equal(centroid.x, 2.0)
    assert GeometryTolerancePolicy.nearly_equal(centroid.y, 0.5)
    assert GeometryTolerancePolicy.near_zero(centroid.z)


def test_triangle_centroid() -> None:
    centroid = _triangle().centroid
    assert GeometryTolerancePolicy.nearly_equal(centroid.x, 1.0)
    assert GeometryTolerancePolicy.nearly_equal(centroid.y, 1.0)
    assert GeometryTolerancePolicy.near_zero(centroid.z)


def test_centroid_translation_behavior() -> None:
    shifted_square = BoundedPlanarFace(
        vertices=tuple(
            Point3D(v.x + 10.0, v.y + 20.0, v.z + 30.0) for v in _SQUARE
        )
    )
    base_centroid = _square().centroid
    moved_centroid = shifted_square.centroid
    assert GeometryTolerancePolicy.nearly_equal(
        moved_centroid.x, base_centroid.x + 10.0
    )
    assert GeometryTolerancePolicy.nearly_equal(
        moved_centroid.y, base_centroid.y + 20.0
    )
    assert GeometryTolerancePolicy.nearly_equal(
        moved_centroid.z, base_centroid.z + 30.0
    )


def test_perimeter_includes_closing_edge() -> None:
    # Square 2x2: three visible edges (2 each) plus the implicit closing
    # edge back to the first vertex (also 2) must total 8.
    assert _square().perimeter == pytest.approx(8.0)
    # Rectangle 4x1: closing edge included -> 2*(4+1) = 10.
    assert _rectangle().perimeter == pytest.approx(10.0)


def test_supporting_plane_derived() -> None:
    plane = _square().plane
    assert isinstance(plane, Plane3D)
    assert plane.point == Point3D(0.0, 0.0, 0.0)
    expected_normal = Vector3D(0.0, 0.0, 1.0)
    assert plane.normal == expected_normal


def test_collinear_leading_triplet_still_valid() -> None:
    # First three vertices are collinear along x; anchor search must skip
    # them and still build a valid 2x1 face.
    face = BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(1.0, 0.0, 0.0),
            Point3D(2.0, 0.0, 0.0),
            Point3D(2.0, 1.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
        )
    )
    assert face.area == pytest.approx(2.0)
    assert GeometryTolerancePolicy.nearly_equal(face.centroid.x, 1.0)
    assert GeometryTolerancePolicy.nearly_equal(face.centroid.y, 0.5)


def test_derived_values_not_dataclass_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(BoundedPlanarFace)}
    assert field_names == {"vertices"}
    face = _square()
    for derived in ("area", "centroid", "perimeter", "plane"):
        assert derived not in getattr(face, "__dict__", {})


def test_frozen_immutable() -> None:
    face = _square()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(face, "vertices", ())  # noqa: B010


def test_equality_identical_ordered_vertices() -> None:
    assert _square() == _square()


def test_equal_hashes_for_equal_faces() -> None:
    assert hash(_square()) == hash(_square())


def test_reversed_winding_not_equal() -> None:
    reversed_face = BoundedPlanarFace(vertices=tuple(reversed(_SQUARE)))
    assert _square() != reversed_face


def test_reversed_winding_same_area() -> None:
    reversed_face = BoundedPlanarFace(vertices=tuple(reversed(_SQUARE)))
    assert reversed_face.area == pytest.approx(_square().area)


def test_reversed_winding_same_centroid() -> None:
    reversed_face = BoundedPlanarFace(vertices=tuple(reversed(_SQUARE)))
    base = _square().centroid
    moved = reversed_face.centroid
    assert GeometryTolerancePolicy.nearly_equal(base.x, moved.x)
    assert GeometryTolerancePolicy.nearly_equal(base.y, moved.y)
    assert GeometryTolerancePolicy.near_zero(moved.z)


def test_fewer_than_three_vertices_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedPlanarFace(vertices=())
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(Point3D(0.0, 0.0, 0.0), Point3D(1.0, 0.0, 0.0))
        )


def test_fewer_than_three_unique_vertices_rejected() -> None:
    # Four vertices but only two distinct positions.
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(1.0, 0.0, 0.0),
                Point3D(0.0, 0.0, 0.0),
                Point3D(1.0, 1.0, 0.0),
            )
        )


def test_adjacent_duplicate_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(2.0, 0.0, 0.0),
                Point3D(2.0, 0.0, 0.0),  # adjacent duplicate
                Point3D(0.0, 2.0, 0.0),
            )
        )


def test_duplicate_closing_vertex_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(2.0, 0.0, 0.0),
                Point3D(2.0, 2.0, 0.0),
                Point3D(0.0, 0.0, 0.0),  # repeats first vertex
            )
        )


def test_collinear_boundary_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(1.0, 0.0, 0.0),
                Point3D(2.0, 0.0, 0.0),
                Point3D(3.0, 0.0, 0.0),
            )
        )


def test_zero_area_degeneracy_rejected() -> None:
    # Near-degenerate sliver whose area is below the central computational
    # tolerance must fail closed (collinear/zero-area family).
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(1.0, 0.0, 0.0),
                Point3D(2.0, 5e-7, 0.0),
                Point3D(0.0, 5e-7, 0.0),
            )
        )


def test_non_coplanar_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedPlanarFace(
            vertices=(
                Point3D(0.0, 0.0, 0.0),
                Point3D(2.0, 0.0, 0.0),
                Point3D(2.0, 2.0, 0.0),
                Point3D(0.0, 2.0, 5.0),  # clearly off the z=0 plane
            )
        )


def test_central_tolerance_policy_reused() -> None:
    # A vertex displaced well below ABS_TOL stays coplanar under the central
    # policy and must be accepted (proves no hidden stricter epsilon exists).
    face = BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(2.0, 0.0, 0.0),
            Point3D(2.0, 2.0, 0.0),
            Point3D(0.0, 2.0, 5e-7),
        )
    )
    assert face.area == pytest.approx(4.0, abs=1e-6)


def test_no_cad_identity_or_provenance_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(BoundedPlanarFace)}
    assert "entity_id" not in field_names
    assert "source_identity" not in field_names
    assert "domain_identity" not in field_names
    assert "neutral_identity" not in field_names
    face = _square()
    for attribute in (
        "entity_id",
        "neutral_identity",
        "domain_identity",
        "source_identity",
    ):
        assert not hasattr(face, attribute)


def test_module_has_no_cad_or_datum_imports() -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "origlyph"
        / "geometry"
        / "bounded.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for module_name in imported:
        assert not module_name.startswith("origlyph.cad"), module_name
        assert not module_name.startswith("origlyph.datum"), module_name


def test_no_ranking_scoring_recommendation_behavior() -> None:
    face = _square()
    for forbidden in ("rank", "score", "prefer", "recommend", "assign"):
        assert not hasattr(face, forbidden)
    source = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "origlyph"
        / "geometry"
        / "bounded.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            identifiers.add(node.name.lower())
        elif isinstance(node, ast.Import):
            identifiers.update(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                identifiers.add(node.module.lower())
            identifiers.update(alias.name.lower() for alias in node.names)
    for token in ("rank", "score", "recommend"):
        assert not any(token in identifier for identifier in identifiers), token


def test_existing_point_line_plane_behavior_unaffected() -> None:
    point = Point3D(1.0, 2.0, 3.0)
    assert (point + Vector3D(1.0, 1.0, 1.0)) == Point3D(2.0, 3.0, 4.0)
    line = Line3D(point=point, direction=Vector3D(0.0, 2.0, 0.0))
    assert line.direction == Vector3D(0.0, 1.0, 0.0)
    with pytest.raises(InvalidGeometryError):
        Line3D(point=point, direction=Vector3D(0.0, 0.0, 0.0))
    with pytest.raises(InvalidGeometryError):
        Plane3D(point=point, normal=Vector3D(0.0, 0.0, 0.0))
    plane = Plane3D(point=point, normal=Vector3D(0.0, 0.0, 5.0))
    assert plane.normal == Vector3D(0.0, 0.0, 1.0)