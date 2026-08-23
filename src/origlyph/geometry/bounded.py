"""Bounded planar face: the first finite-region geometry primitive.

PURE GEOMETRY module — no CAD identity/provenance, no datum semantics, no
I/O, deterministic only. Depends solely on the existing primitives and the
central :class:`~origlyph.geometry.tolerance.GeometryTolerancePolicy`
(no new epsilons).

A face is an ordered cycle of coplanar ``Point3D`` vertices; closure is
implicit (last vertex connects back to the first). The input winding order is
preserved verbatim — never sorted, reordered, or canonicalized — and no
duplicate vertex is silently removed.

Fail-closed construction rejects:

* fewer than 3 vertices / fewer than 3 unique vertices;
* adjacent duplicate vertices, including a duplicate closing vertex
  (zero-length edge);
* a fully collinear boundary or any zero-area degeneracy;
* a non-coplanar boundary.

``plane``, ``area``, ``centroid`` and ``perimeter`` are *derived* properties,
never stored state. Area is the winding-independent magnitude in canonical
mm²; the centroid is geometrically winding-invariant. Lengths are mm.

Self-intersection detection, holes, curved edges, and topology adjacency are
deliberately deferred. This type carries no ranking/scoring/recommendation
semantics of any kind.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .primitives import Plane3D, Point3D, Vector3D
from .tolerance import GeometryTolerancePolicy

__all__ = ["BoundedPlanarFace"]


@dataclass(frozen=True)
class BoundedPlanarFace:
    """A finite planar region defined by an ordered, closed vertex cycle.

    Stored state is exactly ``vertices``; every geometric quantity is derived
    on access. See the module docstring for the full construction contract.
    """

    vertices: tuple[Point3D, ...]

    def __post_init__(self) -> None:
        self._validate_elements()
        self._validate_vertex_graph()
        self._validate_planarity_and_area()

    def _validate_elements(self) -> None:
        if not isinstance(self.vertices, Sequence):
            raise TypeError("vertices must be a sequence of Point3D")
        for vertex in self.vertices:
            if not isinstance(vertex, Point3D):
                raise TypeError("every vertex must be a Point3D")

    def _validate_vertex_graph(self) -> None:
        vertices = self.vertices
        count = len(vertices)
        if count < 3:
            raise ValueError(
                "a bounded planar face requires at least 3 vertices"
            )
        for index in range(count):
            current = vertices[index]
            nxt = vertices[(index + 1) % count]
            if current == nxt:
                if index == count - 1:
                    raise ValueError(
                        "duplicate closing vertex produces a zero-length "
                        "closing edge"
                    )
                raise ValueError(
                    f"adjacent duplicate vertices at positions {index} and "
                    f"{(index + 1) % count}"
                )
        if len(set(vertices)) < 3:
            raise ValueError(
                "a bounded planar face requires at least 3 unique vertices"
            )

    def _validate_planarity_and_area(self) -> None:
        vertices = self.vertices
        anchor = _anchor_indices(vertices)
        if anchor is None:
            raise ValueError(
                "boundary is fully collinear; no non-degenerate triangle exists"
            )
        i0, i1, i2 = anchor
        a = vertices[i0]
        b = vertices[i1]
        c = vertices[i2]
        for index, vertex in enumerate(vertices):
            if index in (i0, i1, i2):
                continue
            if not GeometryTolerancePolicy.points_coplanar(a, b, c, vertex):
                raise ValueError(
                    f"vertex {index} is not coplanar with the boundary plane"
                )
        u, v_axis, origin = _face_basis(vertices, anchor)
        if GeometryTolerancePolicy.near_zero(
            abs(_doubled_area(_projected(vertices, u, v_axis, origin)))
        ):
            raise ValueError("boundary encloses zero area")

    @property
    def plane(self) -> Plane3D:
        """Supporting infinite plane derived from the anchor triplet."""
        vertices = self.vertices
        i0, i1, i2 = _anchor_indices(vertices)  # type: ignore[misc]
        a = vertices[i0]
        b = vertices[i1]
        c = vertices[i2]
        normal = (b - a).cross(c - a).normalize()
        return Plane3D(point=a, normal=normal)

    @property
    def area(self) -> float:
        """Winding-independent enclosed area in canonical mm²."""
        vertices = self.vertices
        anchor = _anchor_indices(vertices)
        assert anchor is not None  # noqa: S101 - validated at construction
        u, v_axis, origin = _face_basis(vertices, anchor)
        return abs(_doubled_area(_projected(vertices, u, v_axis, origin))) / 2.0

    @property
    def centroid(self) -> Point3D:
        """Area-weighted polygon centroid; winding-invariant in 3-D."""
        vertices = self.vertices
        anchor = _anchor_indices(vertices)
        assert anchor is not None  # noqa: S101 - validated at construction
        u, v_axis, origin = _face_basis(vertices, anchor)
        points = _projected(vertices, u, v_axis, origin)
        doubled = _doubled_area(points)
        cx = 0.0
        cy = 0.0
        total = len(points)
        for index in range(total):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % total]
            cross = x1 * y2 - x2 * y1
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        return origin + u.scaled(cx / (3.0 * doubled)) + v_axis.scaled(
            cy / (3.0 * doubled)
        )

    @property
    def perimeter(self) -> float:
        """Total boundary length in mm, including the closing edge."""
        vertices = self.vertices
        total = len(vertices)
        length = 0.0
        for index in range(total):
            length += (
                vertices[(index + 1) % total] - vertices[index]
            ).magnitude()
        return length


def _anchor_indices(vertices: tuple[Point3D, ...]) -> tuple[int, int, int] | None:
    """First deterministic non-collinear vertex triplet, or ``None``.

    The first vertex is fixed as anchor; the second candidate is the first
    vertex distinct from it; the third is the first subsequent vertex that
    breaks collinearity with that pair under the central tolerance policy.
    Never assumes the literal first three vertices are usable.
    """
    total = len(vertices)
    first = 0
    second = -1
    for index in range(1, total):
        if vertices[index] != vertices[first]:
            second = index
            break
    if second == -1:
        return None
    for third in range(second + 1, total):
        if not GeometryTolerancePolicy.points_collinear(
            vertices[first], vertices[second], vertices[third]
        ):
            return (first, second, third)
    return None


def _face_basis(
    vertices: tuple[Point3D, ...], anchor: tuple[int, int, int]
) -> tuple[Vector3D, Vector3D, Point3D]:
    """Orthonormal in-plane basis ``(u, v)`` with origin at the anchor."""
    origin = vertices[anchor[0]]
    arm1 = vertices[anchor[1]] - origin
    arm2 = vertices[anchor[2]] - origin
    u = arm1.normalize()
    normal = arm1.cross(arm2).normalize()
    v_axis = normal.cross(u)
    return (u, v_axis, origin)


def _projected(
    vertices: tuple[Point3D, ...],
    u: Vector3D,
    v_axis: Vector3D,
    origin: Point3D,
) -> list[tuple[float, float]]:
    projected: list[tuple[float, float]] = []
    for vertex in vertices:
        relative = vertex - origin
        projected.append((relative.dot(u), relative.dot(v_axis)))
    return projected


def _doubled_area(points: Sequence[tuple[float, float]]) -> float:
    doubled = 0.0
    total = len(points)
    for index in range(total):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % total]
        doubled += x1 * y2 - x2 * y1
    return doubled