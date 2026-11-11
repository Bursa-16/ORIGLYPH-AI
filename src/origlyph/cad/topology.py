"""Canonical topology contracts for Origlyph CAD (Stage 22C).

Introduces a kernel-independent topology layer capable of representing
CAD/B-Rep connectivity without depending on a specific geometry kernel.

Conceptual hierarchy
--------------------
TopologyVertex   – a 0-dimensional topological element; optional Point3D
TopologyEdge     – a 1-dimensional element bounded by two vertices
TopologyWire     – an ordered sequence of edges forming a connected path
TopologyFace     – a 2-dimensional element bounded by an outer wire + holes
TopologyShell    – an ordered set of faces forming a surface network
TopologySolid    – a volumetric element bounded by an outer shell + voids

All types are immutable frozen dataclasses following existing Origlyph style.

Separation of concerns
-----------------------
Topology:  connectivity and identity (what is adjacent to what).
Geometry:  shape and location (where things are in space).

A topology entity may carry a geometry binding (e.g. ``TopologyVertex.point``)
but topology identity never depends on geometry values.

Persistent naming across CAD revisions
---------------------------------------
Canonical topology identity within one model snapshot does NOT by itself
solve persistent topology naming across CAD revisions.  A face ID that is
stable within one import result may be assigned differently when the source
CAD file is revised.  This limitation is intentional, explicit, and documented.
Stage 22C does not claim to solve this problem.

CAD kernel / STEP
-----------------
Stage 22C does not implement production STEP import.
Stage 22C does not introduce a B-Rep CAD kernel dependency.
No external geometry kernel (OpenCascade, OCP, pythonocc, or any equivalent)
is imported, bundled, or required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from origlyph.geometry import Point3D

from .exceptions import OriglyphCadError
from .identity import SourceDocumentIdentity, SourceEntityIdentity

__all__ = [
    "CanonicalTopologyModel",
    "DanglingTopologyReferenceError",
    "DuplicateTopologyIdError",
    "TopologyEdge",
    "TopologyEntityId",
    "TopologyFace",
    "TopologyOrientation",
    "TopologyShell",
    "TopologySolid",
    "TopologyValidationError",
    "TopologyVertex",
    "TopologyWire",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TopologyValidationError(OriglyphCadError):
    """Base class for topology structural validation failures.

    Raised when a topology entity or model is malformed.  Every topology
    validation failure is fail-closed: no partial or repaired state is
    produced.
    """


class DuplicateTopologyIdError(TopologyValidationError):
    """Raised when two entities of the same kind share the same id."""


class DanglingTopologyReferenceError(TopologyValidationError):
    """Raised when a topology reference points to a non-existent entity."""


# ---------------------------------------------------------------------------
# TopologyEntityId
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyEntityId:
    """Deterministic, immutable identifier for one topology entity.

    IDs are unique within their entity kind collection inside a
    :class:`CanonicalTopologyModel`.  Cross-kind collision is permitted and
    expected (following B-Rep source format conventions where vertex #1 and
    face #1 are distinct entities despite sharing the same integer key).

    The ``value`` is stripped and must not be empty; identity is purely
    value-based (no memory address, no random UUID, no timestamp).
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("topology entity id must not be empty")
        object.__setattr__(self, "value", normalized)


# ---------------------------------------------------------------------------
# TopologyOrientation
# ---------------------------------------------------------------------------


class TopologyOrientation(str, Enum):
    """Orientation of a topology entity relative to its parent.

    ``FORWARD``   – the entity is used in its natural parametric sense.
    ``REVERSED``  – the entity is used with reversed sense (flip normal /
                    traverse direction).

    Invalid orientation values are rejected at construction; there is no
    ``UNKNOWN`` member.
    """

    FORWARD = "forward"
    REVERSED = "reversed"


# ---------------------------------------------------------------------------
# TopologyVertex
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyVertex:
    """A 0-dimensional topology element.

    May carry a :class:`~origlyph.geometry.Point3D` geometry binding; that
    binding is explicitly optional (a topology snapshot may be incomplete).
    When present, all coordinates must be finite.

    ``source_identity`` traces the vertex back to its originating source
    entity; it is explicitly ``None`` for synthesised vertices.
    """

    entity_id: TopologyEntityId
    point: Optional[Point3D] = None
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        if self.point is not None:
            for coord in (self.point.x, self.point.y, self.point.z):
                if not math.isfinite(coord):
                    raise TopologyValidationError(
                        f"vertex point coordinates must be finite; got {coord!r}"
                    )


# ---------------------------------------------------------------------------
# TopologyEdge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyEdge:
    """A 1-dimensional topology element bounded by two vertices.

    ``start_vertex_id`` and ``end_vertex_id`` are references into the
    vertex collection of the containing :class:`CanonicalTopologyModel`; the
    model validates that both IDs exist (fail-closed dangling-reference check).

    ``orientation`` expresses the edge sense relative to its underlying curve.
    Arbitrary string orientations are rejected; only
    :class:`TopologyOrientation` members are accepted.
    """

    entity_id: TopologyEntityId
    start_vertex_id: TopologyEntityId
    end_vertex_id: TopologyEntityId
    orientation: TopologyOrientation = TopologyOrientation.FORWARD
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        if not isinstance(self.orientation, TopologyOrientation):
            raise TopologyValidationError(
                f"orientation must be a TopologyOrientation; "
                f"got {self.orientation!r}"
            )


# ---------------------------------------------------------------------------
# TopologyWire
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyWire:
    """An ordered sequence of edges forming a connected path.

    ``edge_ids`` is an ordered tuple of references into the edge collection of
    the containing :class:`CanonicalTopologyModel`.  The declared order is the
    traversal order; it is stored verbatim (no silent reordering).

    An empty wire is rejected: a wire without edges is not a valid topological
    entity in this architecture.
    """

    entity_id: TopologyEntityId
    edge_ids: tuple[TopologyEntityId, ...]
    orientation: TopologyOrientation = TopologyOrientation.FORWARD
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_ids", tuple(self.edge_ids))
        if len(self.edge_ids) == 0:
            raise TopologyValidationError(
                "wire must reference at least one edge"
            )
        if not isinstance(self.orientation, TopologyOrientation):
            raise TopologyValidationError(
                f"orientation must be a TopologyOrientation; "
                f"got {self.orientation!r}"
            )


# ---------------------------------------------------------------------------
# TopologyFace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyFace:
    """A 2-dimensional topology element bounded by wires.

    ``outer_wire_id`` is the outer boundary (required).
    ``inner_wire_ids`` are inner boundary loops (holes); empty by default.

    Both outer and inner wire IDs are references into the wire collection of
    the containing :class:`CanonicalTopologyModel`; the model validates all
    IDs for existence.
    """

    entity_id: TopologyEntityId
    outer_wire_id: TopologyEntityId
    inner_wire_ids: tuple[TopologyEntityId, ...] = ()
    orientation: TopologyOrientation = TopologyOrientation.FORWARD
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inner_wire_ids", tuple(self.inner_wire_ids))
        if not isinstance(self.orientation, TopologyOrientation):
            raise TopologyValidationError(
                f"orientation must be a TopologyOrientation; "
                f"got {self.orientation!r}"
            )


# ---------------------------------------------------------------------------
# TopologyShell
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyShell:
    """An ordered set of faces forming a surface network.

    ``face_ids`` is an ordered tuple of references into the face collection of
    the containing :class:`CanonicalTopologyModel`.

    An empty shell is rejected: a shell without faces is not a valid topology
    entity in this architecture.
    """

    entity_id: TopologyEntityId
    face_ids: tuple[TopologyEntityId, ...]
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "face_ids", tuple(self.face_ids))
        if len(self.face_ids) == 0:
            raise TopologyValidationError(
                "shell must reference at least one face"
            )


# ---------------------------------------------------------------------------
# TopologySolid
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologySolid:
    """A volumetric topology element bounded by shells.

    ``outer_shell_id`` is the outer bounding shell (required).
    ``inner_shell_ids`` are interior voids (empty by default).

    Both outer and inner shell IDs are references into the shell collection of
    the containing :class:`CanonicalTopologyModel`.
    """

    entity_id: TopologyEntityId
    outer_shell_id: TopologyEntityId
    inner_shell_ids: tuple[TopologyEntityId, ...] = ()
    source_identity: Optional[SourceEntityIdentity] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "inner_shell_ids", tuple(self.inner_shell_ids)
        )


# ---------------------------------------------------------------------------
# CanonicalTopologyModel
# ---------------------------------------------------------------------------


@dataclass(frozen=True, init=False)
class CanonicalTopologyModel:
    """An immutable, validated canonical topology model.

    Aggregates vertices, edges, wires, faces, shells, and solids into one
    deterministic snapshot.  Construction is fail-closed:

    * duplicate IDs within any entity kind collection are rejected
      (:class:`DuplicateTopologyIdError`);
    * dangling references (a reference to a non-existent entity) are rejected
      (:class:`DanglingTopologyReferenceError`);
    * wrong-kind references are impossible by construction (each reference
      field names the expected kind explicitly).

    ID namespaces are per-kind: the same string value may appear as both a
    vertex ID and an edge ID without collision, following B-Rep source format
    conventions.

    Traversal order is deterministic: entities are stored in the order
    supplied to the constructor; no silent sorting or reordering occurs.

    ``source`` is the originating :class:`~origlyph.cad.identity.SourceDocumentIdentity`
    when the model was produced by a CAD importer; it is ``None`` for
    programmatically constructed models.
    """

    source: Optional[SourceDocumentIdentity]
    vertices: tuple[TopologyVertex, ...]
    edges: tuple[TopologyEdge, ...]
    wires: tuple[TopologyWire, ...]
    faces: tuple[TopologyFace, ...]
    shells: tuple[TopologyShell, ...]
    solids: tuple[TopologySolid, ...]

    def __init__(
        self,
        *,
        source: Optional[SourceDocumentIdentity] = None,
        vertices: Optional[Sequence[TopologyVertex]] = None,
        edges: Optional[Sequence[TopologyEdge]] = None,
        wires: Optional[Sequence[TopologyWire]] = None,
        faces: Optional[Sequence[TopologyFace]] = None,
        shells: Optional[Sequence[TopologyShell]] = None,
        solids: Optional[Sequence[TopologySolid]] = None,
    ) -> None:
        vertices_t = tuple(vertices or ())
        edges_t = tuple(edges or ())
        wires_t = tuple(wires or ())
        faces_t = tuple(faces or ())
        shells_t = tuple(shells or ())
        solids_t = tuple(solids or ())

        # Duplicate-ID check within each kind collection
        _assert_no_duplicate_ids(vertices_t, "vertex")
        _assert_no_duplicate_ids(edges_t, "edge")
        _assert_no_duplicate_ids(wires_t, "wire")
        _assert_no_duplicate_ids(faces_t, "face")
        _assert_no_duplicate_ids(shells_t, "shell")
        _assert_no_duplicate_ids(solids_t, "solid")

        # Build resolved ID sets for reference validation
        vertex_ids: frozenset[TopologyEntityId] = frozenset(
            v.entity_id for v in vertices_t
        )
        edge_ids: frozenset[TopologyEntityId] = frozenset(
            e.entity_id for e in edges_t
        )
        wire_ids: frozenset[TopologyEntityId] = frozenset(
            w.entity_id for w in wires_t
        )
        face_ids: frozenset[TopologyEntityId] = frozenset(
            f.entity_id for f in faces_t
        )
        shell_ids: frozenset[TopologyEntityId] = frozenset(
            s.entity_id for s in shells_t
        )

        # Dangling-reference checks
        for edge in edges_t:
            _assert_ref_exists(
                edge.start_vertex_id, vertex_ids, "vertex", "edge start_vertex_id"
            )
            _assert_ref_exists(
                edge.end_vertex_id, vertex_ids, "vertex", "edge end_vertex_id"
            )
        for wire in wires_t:
            for eid in wire.edge_ids:
                _assert_ref_exists(eid, edge_ids, "edge", "wire edge_ids")
        for face in faces_t:
            _assert_ref_exists(
                face.outer_wire_id, wire_ids, "wire", "face outer_wire_id"
            )
            for wid in face.inner_wire_ids:
                _assert_ref_exists(wid, wire_ids, "wire", "face inner_wire_ids")
        for shell in shells_t:
            for fid in shell.face_ids:
                _assert_ref_exists(fid, face_ids, "face", "shell face_ids")
        for solid in solids_t:
            _assert_ref_exists(
                solid.outer_shell_id, shell_ids, "shell", "solid outer_shell_id"
            )
            for sid in solid.inner_shell_ids:
                _assert_ref_exists(
                    sid, shell_ids, "shell", "solid inner_shell_ids"
                )

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "vertices", vertices_t)
        object.__setattr__(self, "edges", edges_t)
        object.__setattr__(self, "wires", wires_t)
        object.__setattr__(self, "faces", faces_t)
        object.__setattr__(self, "shells", shells_t)
        object.__setattr__(self, "solids", solids_t)

    # ------------------------------------------------------------------
    # Adjacency helpers (derived, no mutable cache)
    # ------------------------------------------------------------------

    def edges_for_vertex(
        self, vertex_id: TopologyEntityId
    ) -> tuple[TopologyEdge, ...]:
        """Return all edges whose start or end is ``vertex_id``."""
        return tuple(
            e
            for e in self.edges
            if e.start_vertex_id == vertex_id or e.end_vertex_id == vertex_id
        )

    def wires_for_edge(
        self, edge_id: TopologyEntityId
    ) -> tuple[TopologyWire, ...]:
        """Return all wires that reference ``edge_id``."""
        return tuple(w for w in self.wires if edge_id in w.edge_ids)

    def faces_for_wire(
        self, wire_id: TopologyEntityId
    ) -> tuple[TopologyFace, ...]:
        """Return all faces whose outer or inner boundary references ``wire_id``."""
        return tuple(
            f
            for f in self.faces
            if f.outer_wire_id == wire_id or wire_id in f.inner_wire_ids
        )

    def shells_for_face(
        self, face_id: TopologyEntityId
    ) -> tuple[TopologyShell, ...]:
        """Return all shells that reference ``face_id``."""
        return tuple(s for s in self.shells if face_id in s.face_ids)

    def solids_for_shell(
        self, shell_id: TopologyEntityId
    ) -> tuple[TopologySolid, ...]:
        """Return all solids whose outer or inner shell is ``shell_id``."""
        return tuple(
            s
            for s in self.solids
            if s.outer_shell_id == shell_id or shell_id in s.inner_shell_ids
        )


# ---------------------------------------------------------------------------
# Internal validation helpers (not exported)
# ---------------------------------------------------------------------------


def _assert_no_duplicate_ids(
    entities: tuple[object, ...], kind_label: str
) -> None:
    seen: set[TopologyEntityId] = set()
    for entity in entities:
        eid: TopologyEntityId = entity.entity_id  # type: ignore[attr-defined]
        if eid in seen:
            raise DuplicateTopologyIdError(
                f"duplicate {kind_label} id {eid.value!r}"
            )
        seen.add(eid)


def _assert_ref_exists(
    ref_id: TopologyEntityId,
    id_set: frozenset[TopologyEntityId],
    ref_kind: str,
    context: str,
) -> None:
    if ref_id not in id_set:
        raise DanglingTopologyReferenceError(
            f"{context} references {ref_kind} id {ref_id.value!r} "
            f"that does not exist in this model"
        )
