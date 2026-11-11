"""Unit tests for origlyph.cad.topology (Stage 22C).

Covers sections A–K of the Stage 22C test specification:

A  TopologyVertex
B  TopologyEdge
C  TopologyWire
D  TopologyFace
E  TopologyShell
F  TopologySolid
G  CanonicalTopologyModel
H  Adjacency helpers
I  Provenance binding
J  (see test_topology_adapter.py)
K  Security / robustness contracts
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from origlyph.cad.identity import (
    CadFormat,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
)
from origlyph.cad.topology import (
    CanonicalTopologyModel,
    DanglingTopologyReferenceError,
    DuplicateTopologyIdError,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyOrientation,
    TopologyShell,
    TopologySolid,
    TopologyValidationError,
    TopologyVertex,
    TopologyWire,
)
from origlyph.geometry import Point3D

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _tid(value: str) -> TopologyEntityId:
    return TopologyEntityId(value)


def _source_doc(sid: str = "doc-topo") -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=sid,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source_ent(
    key: str,
    doc: Optional[SourceDocumentIdentity] = None,
) -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=doc or _source_doc(),
        source_entity_key=key,
    )


def _point(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Point3D:
    return Point3D(x, y, z)


def _edge(eid: str, sv: str, ev: str) -> TopologyEdge:
    return TopologyEdge(
        entity_id=_tid(eid),
        start_vertex_id=_tid(sv),
        end_vertex_id=_tid(ev),
    )


def _make_full_model() -> CanonicalTopologyModel:
    """Return a minimal valid model: vertex→edge→wire→face→shell→solid chain."""
    v0 = TopologyVertex(entity_id=_tid("v0"), point=_point(0, 0, 0))
    v1 = TopologyVertex(entity_id=_tid("v1"), point=_point(1, 0, 0))
    v2 = TopologyVertex(entity_id=_tid("v2"), point=_point(1, 1, 0))
    v3 = TopologyVertex(entity_id=_tid("v3"), point=_point(0, 1, 0))

    e0 = _edge("e0", "v0", "v1")
    e1 = _edge("e1", "v1", "v2")
    e2 = _edge("e2", "v2", "v3")
    e3 = _edge("e3", "v3", "v0")

    outer = TopologyWire(
        entity_id=_tid("w0"),
        edge_ids=(_tid("e0"), _tid("e1"), _tid("e2"), _tid("e3")),
    )
    face = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    shell = TopologyShell(entity_id=_tid("s0"), face_ids=(_tid("f0"),))
    solid = TopologySolid(
        entity_id=_tid("sol0"), outer_shell_id=_tid("s0")
    )

    return CanonicalTopologyModel(
        vertices=[v0, v1, v2, v3],
        edges=[e0, e1, e2, e3],
        wires=[outer],
        faces=[face],
        shells=[shell],
        solids=[solid],
    )


# ---------------------------------------------------------------------------
# Section A: TopologyVertex
# ---------------------------------------------------------------------------


def test_a_vertex_valid_construction() -> None:
    """TopologyVertex with a finite point constructs without error."""
    v = TopologyVertex(entity_id=_tid("v1"), point=_point(1.0, 2.0, 3.0))
    assert v.entity_id == _tid("v1")
    assert v.point == _point(1.0, 2.0, 3.0)


def test_a_vertex_no_point_allowed() -> None:
    """TopologyVertex with no point is valid (topology may precede geometry)."""
    v = TopologyVertex(entity_id=_tid("v-nopoint"))
    assert v.point is None


def test_a_vertex_infinite_x_rejected() -> None:
    """Non-finite x coordinate raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyVertex(entity_id=_tid("v-inf"), point=_point(math.inf, 0.0, 0.0))


def test_a_vertex_nan_y_rejected() -> None:
    """NaN y coordinate raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyVertex(entity_id=_tid("v-nan"), point=_point(0.0, math.nan, 0.0))


def test_a_vertex_negative_infinite_z_rejected() -> None:
    """Negative-infinite z coordinate raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyVertex(
            entity_id=_tid("v-ninf"), point=_point(0.0, 0.0, -math.inf)
        )


def test_a_vertex_deterministic_equality() -> None:
    """Two TopologyVertex instances with same field values are equal."""
    v1 = TopologyVertex(entity_id=_tid("v1"), point=_point(1.0, 0.0, 0.0))
    v2 = TopologyVertex(entity_id=_tid("v1"), point=_point(1.0, 0.0, 0.0))
    assert v1 == v2


def test_a_vertex_different_id_not_equal() -> None:
    """TopologyVertex with different entity_id values are not equal."""
    v1 = TopologyVertex(entity_id=_tid("v1"), point=_point(0.0, 0.0, 0.0))
    v2 = TopologyVertex(entity_id=_tid("v2"), point=_point(0.0, 0.0, 0.0))
    assert v1 != v2


def test_a_vertex_is_frozen() -> None:
    """TopologyVertex is immutable (frozen=True)."""
    v = TopologyVertex(entity_id=_tid("vfrozen"))
    with pytest.raises((AttributeError, TypeError)):
        v.point = _point(1.0, 0.0, 0.0)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Section B: TopologyEdge
# ---------------------------------------------------------------------------


def test_b_edge_valid_construction() -> None:
    """TopologyEdge with valid vertex references constructs without error."""
    e = _edge("e1", "v0", "v1")
    assert e.entity_id == _tid("e1")
    assert e.start_vertex_id == _tid("v0")
    assert e.end_vertex_id == _tid("v1")


def test_b_edge_default_orientation_is_forward() -> None:
    """TopologyEdge orientation defaults to FORWARD."""
    e = _edge("e1", "v0", "v1")
    assert e.orientation is TopologyOrientation.FORWARD


def test_b_edge_reversed_orientation_accepted() -> None:
    """REVERSED orientation is accepted."""
    e = TopologyEdge(
        entity_id=_tid("e1"),
        start_vertex_id=_tid("v0"),
        end_vertex_id=_tid("v1"),
        orientation=TopologyOrientation.REVERSED,
    )
    assert e.orientation is TopologyOrientation.REVERSED


def test_b_edge_invalid_orientation_string_rejected() -> None:
    """An arbitrary string as orientation raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyEdge(
            entity_id=_tid("e-bad"),
            start_vertex_id=_tid("v0"),
            end_vertex_id=_tid("v1"),
            orientation="diagonal",  # type: ignore[arg-type]
        )


def test_b_edge_dangling_start_vertex_raises_in_model() -> None:
    """Edge referencing a non-existent start vertex is caught by the model."""
    v = TopologyVertex(entity_id=_tid("v1"))
    e = TopologyEdge(
        entity_id=_tid("e0"),
        start_vertex_id=_tid("MISSING"),
        end_vertex_id=_tid("v1"),
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(vertices=[v], edges=[e])


def test_b_edge_dangling_end_vertex_raises_in_model() -> None:
    """Edge referencing a non-existent end vertex is caught by the model."""
    v = TopologyVertex(entity_id=_tid("v0"))
    e = TopologyEdge(
        entity_id=_tid("e0"),
        start_vertex_id=_tid("v0"),
        end_vertex_id=_tid("MISSING"),
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(vertices=[v], edges=[e])


def test_b_edge_deterministic_equality() -> None:
    """Two edges with identical fields are equal."""
    e1 = _edge("e1", "v0", "v1")
    e2 = _edge("e1", "v0", "v1")
    assert e1 == e2


def test_b_edge_different_orientation_not_equal() -> None:
    """Edges that differ only by orientation are not equal."""
    e_fwd = _edge("e1", "v0", "v1")
    e_rev = TopologyEdge(
        entity_id=_tid("e1"),
        start_vertex_id=_tid("v0"),
        end_vertex_id=_tid("v1"),
        orientation=TopologyOrientation.REVERSED,
    )
    assert e_fwd != e_rev


# ---------------------------------------------------------------------------
# Section C: TopologyWire
# ---------------------------------------------------------------------------


def test_c_wire_valid_construction() -> None:
    """TopologyWire with one edge reference constructs without error."""
    w = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"),))
    assert len(w.edge_ids) == 1


def test_c_wire_stores_edge_ids_in_order() -> None:
    """Edge order is preserved verbatim (no silent reordering)."""
    w = TopologyWire(
        entity_id=_tid("w0"),
        edge_ids=(_tid("e2"), _tid("e0"), _tid("e1")),
    )
    assert w.edge_ids == (_tid("e2"), _tid("e0"), _tid("e1"))


def test_c_empty_wire_rejected() -> None:
    """A wire with zero edges raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError, match="at least one edge"):
        TopologyWire(entity_id=_tid("w-empty"), edge_ids=())


def test_c_wire_dangling_edge_reference_caught_by_model() -> None:
    """Wire referencing a non-existent edge raises DanglingTopologyReferenceError."""
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    e = _edge("e0", "v0", "v1")
    w = TopologyWire(
        entity_id=_tid("w0"), edge_ids=(_tid("e0"), _tid("MISSING"))
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(vertices=[v0, v1], edges=[e], wires=[w])


def test_c_wire_orientation_default_forward() -> None:
    """Wire orientation defaults to FORWARD."""
    w = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"),))
    assert w.orientation is TopologyOrientation.FORWARD


def test_c_wire_orientation_reversed_accepted() -> None:
    """REVERSED orientation on a wire is accepted."""
    w = TopologyWire(
        entity_id=_tid("w0"),
        edge_ids=(_tid("e0"),),
        orientation=TopologyOrientation.REVERSED,
    )
    assert w.orientation is TopologyOrientation.REVERSED


def test_c_wire_invalid_orientation_rejected() -> None:
    """An invalid orientation string on a wire raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyWire(
            entity_id=_tid("w-bad"),
            edge_ids=(_tid("e0"),),
            orientation="unknown",  # type: ignore[arg-type]
        )


def test_c_wire_edge_ids_are_tuple() -> None:
    """edge_ids is stored as a tuple regardless of input type."""
    w = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"), _tid("e1")))
    assert isinstance(w.edge_ids, tuple)


# ---------------------------------------------------------------------------
# Section D: TopologyFace
# ---------------------------------------------------------------------------


def test_d_face_valid_outer_wire() -> None:
    """TopologyFace with a valid outer_wire_id constructs without error."""
    f = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    assert f.outer_wire_id == _tid("w0")


def test_d_face_no_inner_wires_by_default() -> None:
    """inner_wire_ids defaults to empty tuple."""
    f = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    assert f.inner_wire_ids == ()


def test_d_face_inner_wires_stored() -> None:
    """Inner wire IDs are stored as a tuple."""
    f = TopologyFace(
        entity_id=_tid("f0"),
        outer_wire_id=_tid("w0"),
        inner_wire_ids=(_tid("w1"), _tid("w2")),
    )
    assert len(f.inner_wire_ids) == 2


def test_d_face_dangling_outer_wire_caught_by_model() -> None:
    """Face with non-existent outer_wire_id raises DanglingTopologyReferenceError."""
    f = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("MISSING"))
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(faces=[f])


def test_d_face_dangling_inner_wire_caught_by_model() -> None:
    """Face with non-existent inner wire raises DanglingTopologyReferenceError."""
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    e0 = _edge("e0", "v0", "v1")
    w0 = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"),))
    f = TopologyFace(
        entity_id=_tid("f0"),
        outer_wire_id=_tid("w0"),
        inner_wire_ids=(_tid("MISSING"),),
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(
            vertices=[v0, v1], edges=[e0], wires=[w0], faces=[f]
        )


def test_d_face_orientation_default_forward() -> None:
    """Face orientation defaults to FORWARD."""
    f = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    assert f.orientation is TopologyOrientation.FORWARD


def test_d_face_orientation_reversed_accepted() -> None:
    """REVERSED orientation on a face is accepted."""
    f = TopologyFace(
        entity_id=_tid("f0"),
        outer_wire_id=_tid("w0"),
        orientation=TopologyOrientation.REVERSED,
    )
    assert f.orientation is TopologyOrientation.REVERSED


def test_d_face_invalid_orientation_rejected() -> None:
    """Invalid orientation string on a face raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError):
        TopologyFace(
            entity_id=_tid("f-bad"),
            outer_wire_id=_tid("w0"),
            orientation="flat",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Section E: TopologyShell
# ---------------------------------------------------------------------------


def test_e_shell_valid_construction() -> None:
    """TopologyShell with one face reference constructs without error."""
    s = TopologyShell(entity_id=_tid("s0"), face_ids=(_tid("f0"),))
    assert s.entity_id == _tid("s0")
    assert len(s.face_ids) == 1


def test_e_shell_multiple_faces() -> None:
    """Shell with multiple face references stores all of them."""
    s = TopologyShell(
        entity_id=_tid("s0"),
        face_ids=(_tid("f0"), _tid("f1"), _tid("f2")),
    )
    assert len(s.face_ids) == 3


def test_e_empty_shell_rejected() -> None:
    """A shell with zero faces raises TopologyValidationError."""
    with pytest.raises(TopologyValidationError, match="at least one face"):
        TopologyShell(entity_id=_tid("s-empty"), face_ids=())


def test_e_shell_dangling_face_caught_by_model() -> None:
    """Shell referencing a non-existent face raises DanglingTopologyReferenceError."""
    s = TopologyShell(entity_id=_tid("s0"), face_ids=(_tid("MISSING"),))
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(shells=[s])


def test_e_shell_face_ids_stored_in_order() -> None:
    """Shell face IDs are stored in declared order."""
    s = TopologyShell(
        entity_id=_tid("s0"),
        face_ids=(_tid("f2"), _tid("f0"), _tid("f1")),
    )
    assert s.face_ids == (_tid("f2"), _tid("f0"), _tid("f1"))


def test_e_shell_face_ids_are_tuple() -> None:
    """face_ids is a tuple."""
    s = TopologyShell(entity_id=_tid("s0"), face_ids=(_tid("f0"),))
    assert isinstance(s.face_ids, tuple)


# ---------------------------------------------------------------------------
# Section F: TopologySolid
# ---------------------------------------------------------------------------


def test_f_solid_valid_outer_shell() -> None:
    """TopologySolid with valid outer_shell_id constructs without error."""
    sol = TopologySolid(entity_id=_tid("sol0"), outer_shell_id=_tid("s0"))
    assert sol.outer_shell_id == _tid("s0")


def test_f_solid_no_inner_shells_by_default() -> None:
    """inner_shell_ids defaults to empty tuple."""
    sol = TopologySolid(entity_id=_tid("sol0"), outer_shell_id=_tid("s0"))
    assert sol.inner_shell_ids == ()


def test_f_solid_inner_shells_stored() -> None:
    """Inner shell IDs are stored as a tuple."""
    sol = TopologySolid(
        entity_id=_tid("sol0"),
        outer_shell_id=_tid("s0"),
        inner_shell_ids=(_tid("s1"), _tid("s2")),
    )
    assert len(sol.inner_shell_ids) == 2


def test_f_solid_dangling_outer_shell_caught_by_model() -> None:
    """Solid with non-existent outer_shell_id raises DanglingTopologyReferenceError."""
    sol = TopologySolid(
        entity_id=_tid("sol0"), outer_shell_id=_tid("MISSING")
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(solids=[sol])


def test_f_solid_dangling_inner_shell_caught_by_model() -> None:
    """Solid with non-existent inner shell raises DanglingTopologyReferenceError."""
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    e0 = _edge("e0", "v0", "v1")
    w0 = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"),))
    f0 = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    s0 = TopologyShell(entity_id=_tid("s0"), face_ids=(_tid("f0"),))
    sol = TopologySolid(
        entity_id=_tid("sol0"),
        outer_shell_id=_tid("s0"),
        inner_shell_ids=(_tid("MISSING"),),
    )
    with pytest.raises(DanglingTopologyReferenceError):
        CanonicalTopologyModel(
            vertices=[v0, v1],
            edges=[e0],
            wires=[w0],
            faces=[f0],
            shells=[s0],
            solids=[sol],
        )


# ---------------------------------------------------------------------------
# Section G: CanonicalTopologyModel
# ---------------------------------------------------------------------------


def test_g_empty_model_constructs() -> None:
    """An empty CanonicalTopologyModel (no entities) constructs without error."""
    m = CanonicalTopologyModel()
    assert len(m.vertices) == 0
    assert len(m.edges) == 0
    assert len(m.wires) == 0
    assert len(m.faces) == 0
    assert len(m.shells) == 0
    assert len(m.solids) == 0


def test_g_full_model_constructs() -> None:
    """A complete vertex→edge→wire→face→shell→solid chain constructs."""
    m = _make_full_model()
    assert len(m.vertices) == 4
    assert len(m.edges) == 4
    assert len(m.wires) == 1
    assert len(m.faces) == 1
    assert len(m.shells) == 1
    assert len(m.solids) == 1


def test_g_duplicate_vertex_id_rejected() -> None:
    """Two vertices sharing an entity_id raise DuplicateTopologyIdError."""
    v0a = TopologyVertex(entity_id=_tid("v0"))
    v0b = TopologyVertex(entity_id=_tid("v0"))
    with pytest.raises(DuplicateTopologyIdError):
        CanonicalTopologyModel(vertices=[v0a, v0b])


def test_g_duplicate_edge_id_rejected() -> None:
    """Two edges sharing an entity_id raise DuplicateTopologyIdError."""
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    ea = _edge("e0", "v0", "v1")
    eb = _edge("e0", "v0", "v1")
    with pytest.raises(DuplicateTopologyIdError):
        CanonicalTopologyModel(vertices=[v0, v1], edges=[ea, eb])


def test_g_duplicate_face_id_rejected() -> None:
    """Two faces sharing an entity_id raise DuplicateTopologyIdError."""
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    e0 = _edge("e0", "v0", "v1")
    w0 = TopologyWire(entity_id=_tid("w0"), edge_ids=(_tid("e0"),))
    fa = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    fb = TopologyFace(entity_id=_tid("f0"), outer_wire_id=_tid("w0"))
    with pytest.raises(DuplicateTopologyIdError):
        CanonicalTopologyModel(
            vertices=[v0, v1], edges=[e0], wires=[w0], faces=[fa, fb]
        )


def test_g_cross_kind_id_collision_allowed() -> None:
    """The same string value may appear as both a vertex ID and an edge ID."""
    v = TopologyVertex(entity_id=_tid("1"))
    u = TopologyVertex(entity_id=_tid("2"))
    e = TopologyEdge(
        entity_id=_tid("1"),
        start_vertex_id=_tid("1"),
        end_vertex_id=_tid("2"),
    )
    m = CanonicalTopologyModel(vertices=[v, u], edges=[e])
    assert len(m.vertices) == 2
    assert len(m.edges) == 1


def test_g_traversal_order_preserved() -> None:
    """Vertices are stored in the order supplied."""
    ids = ["v3", "v1", "v2"]
    vertices = [TopologyVertex(entity_id=_tid(i)) for i in ids]
    m = CanonicalTopologyModel(vertices=vertices)
    assert [v.entity_id.value for v in m.vertices] == ids


def test_g_model_is_frozen() -> None:
    """CanonicalTopologyModel is immutable."""
    m = CanonicalTopologyModel()
    with pytest.raises((AttributeError, TypeError)):
        m.vertices = ()  # type: ignore[misc]


def test_g_model_deterministic_equality() -> None:
    """Two models with identical entities are equal."""
    v = TopologyVertex(entity_id=_tid("v0"))
    m1 = CanonicalTopologyModel(vertices=[v])
    m2 = CanonicalTopologyModel(vertices=[v])
    assert m1 == m2


def test_g_model_entity_counts_correct() -> None:
    """Entity counts reflect supplied collections."""
    m = _make_full_model()
    assert len(m.vertices) == 4
    assert len(m.edges) == 4


def test_g_model_no_source_by_default() -> None:
    """source is None when not supplied."""
    m = CanonicalTopologyModel()
    assert m.source is None


def test_g_model_source_stored() -> None:
    """source is stored when supplied."""
    doc = _source_doc()
    m = CanonicalTopologyModel(source=doc)
    assert m.source == doc


# ---------------------------------------------------------------------------
# Section H: Adjacency helpers
# ---------------------------------------------------------------------------


def test_h_edges_for_vertex_start() -> None:
    """edges_for_vertex returns edges where the vertex is the start."""
    m = _make_full_model()
    result = m.edges_for_vertex(_tid("v0"))
    edge_ids = {e.entity_id.value for e in result}
    assert "e0" in edge_ids
    assert "e3" in edge_ids


def test_h_edges_for_vertex_end() -> None:
    """edges_for_vertex includes edges where the vertex is the end."""
    m = _make_full_model()
    result = m.edges_for_vertex(_tid("v1"))
    edge_ids = {e.entity_id.value for e in result}
    assert "e0" in edge_ids
    assert "e1" in edge_ids


def test_h_edges_for_missing_vertex_returns_empty() -> None:
    """edges_for_vertex returns empty tuple for a non-existent vertex_id."""
    m = _make_full_model()
    assert m.edges_for_vertex(_tid("NONEXISTENT")) == ()


def test_h_wires_for_edge() -> None:
    """wires_for_edge returns wires that reference the given edge."""
    m = _make_full_model()
    result = m.wires_for_edge(_tid("e0"))
    assert len(result) == 1
    assert result[0].entity_id == _tid("w0")


def test_h_wires_for_missing_edge_returns_empty() -> None:
    """wires_for_edge returns empty for a non-existent edge_id."""
    m = _make_full_model()
    assert m.wires_for_edge(_tid("NONEXISTENT")) == ()


def test_h_faces_for_wire() -> None:
    """faces_for_wire returns faces whose outer wire is the given id."""
    m = _make_full_model()
    result = m.faces_for_wire(_tid("w0"))
    assert len(result) == 1
    assert result[0].entity_id == _tid("f0")


def test_h_shells_for_face() -> None:
    """shells_for_face returns shells that reference the given face."""
    m = _make_full_model()
    result = m.shells_for_face(_tid("f0"))
    assert len(result) == 1
    assert result[0].entity_id == _tid("s0")


def test_h_solids_for_shell() -> None:
    """solids_for_shell returns solids whose outer shell is the given id."""
    m = _make_full_model()
    result = m.solids_for_shell(_tid("s0"))
    assert len(result) == 1
    assert result[0].entity_id == _tid("sol0")


def test_h_full_adjacency_chain() -> None:
    """Full adjacency chain: vertex→edge→wire→face→shell→solid traversable."""
    m = _make_full_model()
    edges = m.edges_for_vertex(_tid("v0"))
    assert len(edges) >= 1
    wires = m.wires_for_edge(edges[0].entity_id)
    assert len(wires) >= 1
    faces = m.faces_for_wire(wires[0].entity_id)
    assert len(faces) >= 1
    shells = m.shells_for_face(faces[0].entity_id)
    assert len(shells) >= 1
    solids = m.solids_for_shell(shells[0].entity_id)
    assert len(solids) >= 1


# ---------------------------------------------------------------------------
# Section I: Provenance binding
# ---------------------------------------------------------------------------


def test_i_vertex_source_identity_preserved() -> None:
    """Vertex source_identity is stored verbatim."""
    si = _source_ent("v#1")
    v = TopologyVertex(entity_id=_tid("v0"), source_identity=si)
    assert v.source_identity == si


def test_i_edge_source_identity_preserved() -> None:
    """Edge source_identity is stored verbatim."""
    si = _source_ent("e#1")
    e = TopologyEdge(
        entity_id=_tid("e0"),
        start_vertex_id=_tid("v0"),
        end_vertex_id=_tid("v1"),
        source_identity=si,
    )
    assert e.source_identity == si


def test_i_face_source_identity_preserved() -> None:
    """Face source_identity is stored verbatim."""
    si = _source_ent("f#1")
    f = TopologyFace(
        entity_id=_tid("f0"), outer_wire_id=_tid("w0"), source_identity=si
    )
    assert f.source_identity == si


def test_i_shell_source_identity_preserved() -> None:
    """Shell source_identity is stored verbatim."""
    si = _source_ent("s#1")
    s = TopologyShell(
        entity_id=_tid("s0"), face_ids=(_tid("f0"),), source_identity=si
    )
    assert s.source_identity == si


def test_i_no_source_identity_by_default() -> None:
    """source_identity is None when not supplied."""
    v = TopologyVertex(entity_id=_tid("v0"))
    assert v.source_identity is None


def test_i_source_document_in_model() -> None:
    """CanonicalTopologyModel preserves the source document identity."""
    doc = _source_doc("step-doc-001")
    m = CanonicalTopologyModel(source=doc)
    assert m.source is not None
    assert m.source.source_id == "step-doc-001"


def test_i_source_entity_key_explicit() -> None:
    """Source entity key is accessible and unmodified on vertex."""
    doc = _source_doc()
    si = SourceEntityIdentity(
        source_document=doc, source_entity_key="#face_42"
    )
    v = TopologyVertex(entity_id=_tid("v0"), source_identity=si)
    assert v.source_identity is not None
    assert v.source_identity.source_entity_key == "#face_42"


def test_i_entity_id_does_not_encode_local_path() -> None:
    """TopologyEntityId value contains no filesystem path separator."""
    tid = _tid("step_vertex_42")
    assert "/" not in tid.value
    assert "\\" not in tid.value


# ---------------------------------------------------------------------------
# Section K: Security / robustness contracts
# ---------------------------------------------------------------------------


def test_k_entity_id_empty_rejected() -> None:
    """Empty entity ID raises ValueError."""
    with pytest.raises(ValueError):
        TopologyEntityId("")


def test_k_entity_id_whitespace_only_rejected() -> None:
    """Whitespace-only entity ID raises ValueError."""
    with pytest.raises(ValueError):
        TopologyEntityId("   ")


def test_k_entity_id_stripped() -> None:
    """Whitespace is stripped from entity ID value."""
    tid = TopologyEntityId("  v1  ")
    assert tid.value == "v1"


def test_k_entity_id_deterministic_not_random() -> None:
    """Two TopologyEntityId instances with the same value are identical."""
    t1 = TopologyEntityId("x")
    t2 = TopologyEntityId("x")
    assert t1 == t2
    assert hash(t1) == hash(t2)


def test_k_entity_id_hash_stable() -> None:
    """Hash of a TopologyEntityId is stable across calls."""
    tid = TopologyEntityId("stable")
    assert hash(tid) == hash(tid)


def test_k_topology_orientation_no_unknown_member() -> None:
    """TopologyOrientation has exactly FORWARD and REVERSED members."""
    members = {m.value for m in TopologyOrientation}
    assert members == {"forward", "reversed"}


def test_k_orientation_invalid_enum_value_rejected() -> None:
    """Creating an invalid TopologyOrientation member raises ValueError."""
    with pytest.raises(ValueError):
        TopologyOrientation("unknown_orientation")


def test_k_topology_validation_error_is_cad_error() -> None:
    """TopologyValidationError is a subclass of OriglyphCadError."""
    from origlyph.cad.exceptions import OriglyphCadError

    assert issubclass(TopologyValidationError, OriglyphCadError)


def test_k_dangling_ref_error_is_topology_validation_error() -> None:
    """DanglingTopologyReferenceError is a subclass of TopologyValidationError."""
    assert issubclass(DanglingTopologyReferenceError, TopologyValidationError)


def test_k_duplicate_id_error_is_topology_validation_error() -> None:
    """DuplicateTopologyIdError is a subclass of TopologyValidationError."""
    assert issubclass(DuplicateTopologyIdError, TopologyValidationError)
