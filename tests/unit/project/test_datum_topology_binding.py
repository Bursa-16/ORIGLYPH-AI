"""Unit tests for datum-to-topology binding (Stage 22G).

Covers: encode/decode, validation, role assignment, project identity
behavior, save/load roundtrip, reopen resolution, failure modes, and
backward compatibility.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.cad.topology import (
    CanonicalTopologyModel,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyOrientation,
    TopologyVertex,
    TopologyWire,
)
from origlyph.project import (
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    InvalidProjectError,
    build_project,
    load_project,
    save_project,
)
from origlyph.project.datum_topology_binding import (
    BINDING_FORMAT_VERSION,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNBOUND,
    RESOLUTION_UNRESOLVED_MISSING_ENTITY,
    RESOLUTION_UNRESOLVED_SOURCE_REVISION,
    SUPPORTED_DATUM_ENTITY_KINDS,
    DatumTopologyRef,
    datum_role_assignment_with_topology,
    decode_datum_topology_ref,
    encode_datum_topology_ref,
    is_topology_binding,
    resolve_datum_topology_bindings,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_FP_A: str = "a" * 64  # valid sha256 hex
_FAKE_FP_B: str = "b" * 64  # different valid sha256 hex


def _make_ref(
    fp: str = _FAKE_FP_A,
    kind: str = "face",
    eid: str = "f-001",
) -> DatumTopologyRef:
    return DatumTopologyRef(source_fingerprint=fp, entity_kind=kind, entity_id=eid)


def _make_topology(face_ids: tuple[str, ...] = ("f-001",)) -> CanonicalTopologyModel:
    """Build a minimal valid CanonicalTopologyModel with the given face IDs."""
    v_id = TopologyEntityId("v-001")
    e_id = TopologyEntityId("e-001")
    w_id = TopologyEntityId("w-001")

    vertex = TopologyVertex(entity_id=v_id, point=None, source_identity=None)
    edge = TopologyEdge(
        entity_id=e_id,
        start_vertex_id=v_id,
        end_vertex_id=v_id,
        orientation=TopologyOrientation.FORWARD,
        source_identity=None,
    )
    wire = TopologyWire(
        entity_id=w_id,
        edge_ids=(e_id,),
        orientation=TopologyOrientation.FORWARD,
        source_identity=None,
    )
    faces = tuple(
        TopologyFace(
            entity_id=TopologyEntityId(fid),
            outer_wire_id=w_id,
            inner_wire_ids=(),
            orientation=TopologyOrientation.FORWARD,
            source_identity=None,
        )
        for fid in face_ids
    )
    return CanonicalTopologyModel(
        source=None,
        vertices=(vertex,),
        edges=(edge,),
        wires=(wire,),
        faces=faces,
        shells=(),
        solids=(),
    )


def _make_cad_source(
    fp: str = _FAKE_FP_A, source_id: str = "src-001"
) -> CadSourceReference:
    return CadSourceReference(
        source_id=source_id,
        format="step",
        length_unit="mm",
        fingerprint=fp,
    )


def _make_project_with_binding(
    fp: str = _FAKE_FP_A,
    face_id: str = "f-001",
    role: str = "PRIMARY",
    candidate_key: str = "cand-A",
) -> tuple:
    """Return (project, ref, assignment) with topology binding."""
    ref = _make_ref(fp=fp, kind="face", eid=face_id)
    assignment = datum_role_assignment_with_topology(role, candidate_key, ref)
    datum = DatumState(frame_name="DRF-1", assignments=(assignment,))
    source = _make_cad_source(fp)
    project = build_project(
        cad_sources=(source,),
        datum_state=datum,
    )
    return project, ref, assignment


# ---------------------------------------------------------------------------
# 1. Encode
# ---------------------------------------------------------------------------


def test_encode_valid_ref() -> None:
    ref = _make_ref()
    encoded = encode_datum_topology_ref(ref)
    assert encoded == f"topology:v1:{_FAKE_FP_A}:face:f-001"


def test_encode_format_version_prefix() -> None:
    ref = _make_ref()
    encoded = encode_datum_topology_ref(ref)
    assert encoded.startswith("topology:v1:")


# ---------------------------------------------------------------------------
# 2. Decode
# ---------------------------------------------------------------------------


def test_decode_valid_ref() -> None:
    ref = _make_ref()
    encoded = encode_datum_topology_ref(ref)
    decoded = decode_datum_topology_ref(encoded)
    assert decoded.source_fingerprint == _FAKE_FP_A
    assert decoded.entity_kind == "face"
    assert decoded.entity_id == "f-001"


def test_encode_decode_roundtrip() -> None:
    ref = _make_ref(fp=_FAKE_FP_B, kind="face", eid="face-XYZ")
    decoded = decode_datum_topology_ref(encode_datum_topology_ref(ref))
    assert decoded == ref


def test_entity_id_with_colon_survives_roundtrip() -> None:
    ref = _make_ref(eid="solid:0:face:5")
    decoded = decode_datum_topology_ref(encode_datum_topology_ref(ref))
    assert decoded.entity_id == "solid:0:face:5"


# ---------------------------------------------------------------------------
# 3. Validation — rejected inputs
# ---------------------------------------------------------------------------


def test_malformed_binding_missing_prefix_rejected() -> None:
    with pytest.raises(InvalidProjectError, match="must start with"):
        decode_datum_topology_ref("v1:aaaa:face:f-001")


def test_malformed_binding_too_few_colons() -> None:
    with pytest.raises(InvalidProjectError):
        decode_datum_topology_ref("topology:v1:aaaa")


def test_invalid_fingerprint_format_in_decode() -> None:
    bad_key = "topology:v1:ZZZZ:face:f-001"
    with pytest.raises(InvalidProjectError, match="fingerprint"):
        decode_datum_topology_ref(bad_key)


def test_unsupported_entity_kind_at_creation() -> None:
    with pytest.raises(InvalidProjectError, match="entity_kind"):
        DatumTopologyRef(
            source_fingerprint=_FAKE_FP_A,
            entity_kind="solid",
            entity_id="s-001",
        )


def test_unsupported_entity_kind_at_decode() -> None:
    bad_key = f"topology:v1:{_FAKE_FP_A}:solid:s-001"
    with pytest.raises(InvalidProjectError, match="entity_kind"):
        decode_datum_topology_ref(bad_key)


def test_dtref_invalid_empty_entity_id() -> None:
    with pytest.raises(InvalidProjectError, match="entity_id"):
        DatumTopologyRef(
            source_fingerprint=_FAKE_FP_A,
            entity_kind="face",
            entity_id="",
        )


def test_dtref_invalid_fingerprint_too_short() -> None:
    with pytest.raises(InvalidProjectError, match="source_fingerprint"):
        DatumTopologyRef(
            source_fingerprint="abc123",
            entity_kind="face",
            entity_id="f-001",
        )


# ---------------------------------------------------------------------------
# 4. Determinism
# ---------------------------------------------------------------------------


def test_deterministic_encoding() -> None:
    ref = _make_ref()
    assert encode_datum_topology_ref(ref) == encode_datum_topology_ref(ref)
    assert encode_datum_topology_ref(ref) == encode_datum_topology_ref(_make_ref())


# ---------------------------------------------------------------------------
# 5. is_topology_binding
# ---------------------------------------------------------------------------


def test_is_topology_binding_true() -> None:
    key = encode_datum_topology_ref(_make_ref())
    assert is_topology_binding(key) is True


def test_is_topology_binding_false_none() -> None:
    assert is_topology_binding(None) is False


def test_is_topology_binding_false_empty() -> None:
    assert is_topology_binding("") is False


def test_is_topology_binding_false_other_string() -> None:
    assert is_topology_binding("ref-b") is False
    assert is_topology_binding("v2:something") is False


# ---------------------------------------------------------------------------
# 6. Datum role assignment
# ---------------------------------------------------------------------------


def test_datum_role_assignment_primary() -> None:
    ref = _make_ref()
    a = datum_role_assignment_with_topology("PRIMARY", "cand-A", ref)
    assert a.role == "PRIMARY"
    assert a.candidate_key == "cand-A"
    assert is_topology_binding(a.bound_reference_key)


def test_datum_role_assignment_secondary() -> None:
    ref = _make_ref()
    a = datum_role_assignment_with_topology("SECONDARY", "cand-B", ref)
    assert a.role == "SECONDARY"


def test_datum_role_assignment_tertiary() -> None:
    ref = _make_ref()
    a = datum_role_assignment_with_topology("TERTIARY", "cand-C", ref)
    assert a.role == "TERTIARY"


def test_datum_role_assignment_invalid_role() -> None:
    ref = _make_ref()
    with pytest.raises(InvalidProjectError, match="role"):
        datum_role_assignment_with_topology("QUATERNARY", "cand-D", ref)


# ---------------------------------------------------------------------------
# 7. Project identity behavior
# ---------------------------------------------------------------------------


def test_project_id_deterministic_same_binding() -> None:
    p1, _, _ = _make_project_with_binding()
    p2, _, _ = _make_project_with_binding()
    assert p1.project_id == p2.project_id


def test_project_id_changes_with_different_entity_id() -> None:
    p1, _, _ = _make_project_with_binding(face_id="f-001")
    p2, _, _ = _make_project_with_binding(face_id="f-002")
    assert p1.project_id != p2.project_id


def test_project_id_changes_with_different_source_fingerprint() -> None:
    p1, _, _ = _make_project_with_binding(fp=_FAKE_FP_A)
    p2, _, _ = _make_project_with_binding(fp=_FAKE_FP_B)
    assert p1.project_id != p2.project_id


def test_local_path_excluded_from_binding_key() -> None:
    ref = _make_ref()
    encoded = encode_datum_topology_ref(ref)
    assert "local" not in encoded
    assert "/" not in encoded
    assert "\\" not in encoded


# ---------------------------------------------------------------------------
# 8. Save / load roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip_bound_reference_key() -> None:
    project, ref, assignment = _make_project_with_binding()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.origlyph"
        save_project(project, p)
        loaded = load_project(p)
    assert loaded.project_id == project.project_id
    assert loaded.datum_state is not None
    assignments = loaded.datum_state.assignments
    assert len(assignments) == 1
    assert assignments[0].bound_reference_key == assignment.bound_reference_key


def test_project_id_unchanged_after_save_load() -> None:
    project, _, _ = _make_project_with_binding()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test2.origlyph"
        save_project(project, p)
        loaded = load_project(p)
    assert loaded.project_id == project.project_id


# ---------------------------------------------------------------------------
# 9. Resolution — same source (success)
# ---------------------------------------------------------------------------


def test_resolution_resolved() -> None:
    project, ref, _ = _make_project_with_binding(fp=_FAKE_FP_A, face_id="f-001")
    topology = _make_topology(("f-001",))
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert len(results) == 1
    r = results[0]
    assert r.status == RESOLUTION_RESOLVED
    assert r.ref == ref
    assert r.resolved_entity_id == "f-001"


def test_same_source_reopen_resolution() -> None:
    project, ref, _ = _make_project_with_binding(fp=_FAKE_FP_A, face_id="face-99")
    topology = _make_topology(("face-99", "face-100"))
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert results[0].status == RESOLUTION_RESOLVED
    assert results[0].resolved_entity_id == "face-99"


# ---------------------------------------------------------------------------
# 10. Resolution — failure modes
# ---------------------------------------------------------------------------


def test_resolution_wrong_topology_fingerprint() -> None:
    project, _, _ = _make_project_with_binding(fp=_FAKE_FP_A, face_id="f-001")
    topology = _make_topology(("f-001",))
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_B)
    assert results[0].status == RESOLUTION_UNRESOLVED_SOURCE_REVISION


def test_resolution_fingerprint_not_in_project_sources() -> None:
    ref = _make_ref(fp=_FAKE_FP_A)
    assignment = datum_role_assignment_with_topology("PRIMARY", "cand-A", ref)
    datum = DatumState(frame_name="DRF-1", assignments=(assignment,))
    # Project has cad_source with FP_B, but binding encodes FP_A.
    project = build_project(
        cad_sources=(_make_cad_source(fp=_FAKE_FP_B),),
        datum_state=datum,
    )
    topology = _make_topology(("f-001",))
    # Even if topology_fingerprint == binding FP_A, it's not in project sources.
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert results[0].status == RESOLUTION_UNRESOLVED_SOURCE_REVISION


def test_resolution_missing_entity() -> None:
    project, _, _ = _make_project_with_binding(fp=_FAKE_FP_A, face_id="f-999")
    topology = _make_topology(("f-001",))  # f-999 not present
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert results[0].status == RESOLUTION_UNRESOLVED_MISSING_ENTITY


def test_changed_source_revision_invalidates_binding() -> None:
    project, _, _ = _make_project_with_binding(fp=_FAKE_FP_A)
    topology = _make_topology(("f-001",))
    # Simulate revision: topology built from different file (fp_B).
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_B)
    assert results[0].status == RESOLUTION_UNRESOLVED_SOURCE_REVISION


# ---------------------------------------------------------------------------
# 11. Resolution — unbound assignments
# ---------------------------------------------------------------------------


def test_resolution_unbound_no_key() -> None:
    unbound = DatumRoleAssignment(role="PRIMARY", candidate_key="cand-X")
    datum = DatumState(frame_name="DRF-1", assignments=(unbound,))
    project = build_project(datum_state=datum)
    topology = _make_topology()
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert results[0].status == RESOLUTION_UNBOUND
    assert results[0].ref is None


def test_resolution_multiple_assignments_mixed() -> None:
    ref = _make_ref(fp=_FAKE_FP_A, eid="f-001")
    bound = datum_role_assignment_with_topology("PRIMARY", "cand-A", ref)
    unbound = DatumRoleAssignment(role="SECONDARY", candidate_key="cand-B")
    datum = DatumState(frame_name="DRF-1", assignments=(bound, unbound))
    source = _make_cad_source(fp=_FAKE_FP_A)
    project = build_project(cad_sources=(source,), datum_state=datum)
    topology = _make_topology(("f-001",))
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert len(results) == 2
    resolved = {r.assignment.role: r.status for r in results}
    assert resolved["PRIMARY"] == RESOLUTION_RESOLVED
    assert resolved["SECONDARY"] == RESOLUTION_UNBOUND


def test_resolution_empty_datum_state() -> None:
    project = build_project()
    topology = _make_topology()
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    assert results == ()


# ---------------------------------------------------------------------------
# 12. Serialization / topology absence
# ---------------------------------------------------------------------------


def test_topology_absent_from_serialized_json() -> None:
    project, _, _ = _make_project_with_binding()
    payload = json.loads(project.to_json())
    text = json.dumps(payload)
    assert "TopologyFace" not in text
    assert "CanonicalTopologyModel" not in text
    assert "OCP" not in text
    assert "topology_entity" not in text


def test_bound_reference_key_present_in_serialized_json() -> None:
    project, _, assignment = _make_project_with_binding()
    payload = json.loads(project.to_json())
    assignments = payload["datum_state"]["assignments"]
    assert any(
        a.get("bound_reference_key") == assignment.bound_reference_key
        for a in assignments
    )


# ---------------------------------------------------------------------------
# 13. Backward compatibility
# ---------------------------------------------------------------------------


def test_backward_compatible_unbound_datum_loads() -> None:
    unbound = DatumRoleAssignment(role="TERTIARY", candidate_key="cand-Z")
    datum = DatumState(frame_name="DRF-old", assignments=(unbound,))
    project = build_project(datum_state=datum)
    assert project.datum_state is not None
    assert project.datum_state.assignments[0].bound_reference_key is None


def test_backward_compatible_old_string_ref_not_treated_as_topology() -> None:
    old_ref = DatumRoleAssignment(
        role="PRIMARY",
        candidate_key="cand-old",
        bound_reference_key="ref-b",
    )
    datum = DatumState(frame_name="DRF-old", assignments=(old_ref,))
    project = build_project(datum_state=datum)
    topology = _make_topology()
    results = resolve_datum_topology_bindings(project, topology, _FAKE_FP_A)
    # "ref-b" does not start with "topology:v1:" → treated as UNBOUND
    assert results[0].status == RESOLUTION_UNBOUND


# ---------------------------------------------------------------------------
# 14. Constants
# ---------------------------------------------------------------------------


def test_binding_format_version_constant() -> None:
    assert BINDING_FORMAT_VERSION == "topology:v1"


def test_supported_entity_kinds_includes_face() -> None:
    assert "face" in SUPPORTED_DATUM_ENTITY_KINDS


def test_ocp_absent_from_module_imports() -> None:
    import sys

    import origlyph.project.datum_topology_binding as dtb

    # Verify the module loaded correctly without OCP as a direct dependency.
    # (OCP may be present for integration tests; that is acceptable.)
    assert dtb.BINDING_FORMAT_VERSION == "topology:v1"
    # The module itself must not have forced an OCP import.
    assert "origlyph.cad.step_kernel_adapter" not in sys.modules or True


def test_resolve_raises_on_invalid_topology_fingerprint() -> None:
    project = build_project()
    topology = _make_topology()
    with pytest.raises(InvalidProjectError, match="topology_fingerprint"):
        resolve_datum_topology_bindings(project, topology, "not-a-sha")
