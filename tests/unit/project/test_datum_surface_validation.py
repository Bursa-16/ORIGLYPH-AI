"""Unit tests for datum surface-type validation (Stage 22H).

Covers all specified test scenarios including:
- planar face validity for PRIMARY / SECONDARY / TERTIARY
- missing surface signature (fail closed)
- UNKNOWN surface type (fail closed)
- unsupported surface type
- unsupported entity kind (mocked)
- missing entity
- source mismatch (fail closed)
- determinism
- no project_id change
- no serialization of results / topology
- binding format unchanged
- backward-compatible unbound datum
- same-source reopen gives same result
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from origlyph.cad.topology import (
    CanonicalTopologyModel,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyVertex,
    TopologyWire,
)
from origlyph.cad.topology_signature import (
    FaceSurfaceType,
    TopologyFaceSignature,
    build_face_signature,
)
from origlyph.project import (
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    InvalidProjectError,
    OriglyphProject,
    build_project,
    load_project,
    save_project,
)
from origlyph.project.datum_surface_validation import (
    SUPPORTED_VALIDATION_ENTITY_KINDS,
    DatumSurfaceValidationStatus,
    validate_datum_role_surface,
    validate_datum_surface,
)
from origlyph.project.datum_topology_binding import (
    DatumTopologyRef,
    datum_role_assignment_with_topology,
    encode_datum_topology_ref,
    is_topology_binding,
)

# ---------------------------------------------------------------------------
# Shared SHA fixtures
# ---------------------------------------------------------------------------

_SHA_A: str = "a" * 64
_SHA_B: str = "b" * 64
_SHA_C: str = "c" * 64


# ---------------------------------------------------------------------------
# Topology helpers
# ---------------------------------------------------------------------------


def _make_sig(
    surface_type: str = FaceSurfaceType.PLANE.value,
    surface_params: tuple[float, ...] = (0.0, 0.0, 1.0, 0.0),
    entity_id: str = "face-001",
) -> TopologyFaceSignature:
    return build_face_signature(
        vertex_points=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        surface_type=surface_type,
        surface_params=surface_params,
        source_entity_id=entity_id,
    )


_DEFAULT_SIG: TopologyFaceSignature = _make_sig()


def _make_topology(
    face_id: str = "face-001",
    signature: TopologyFaceSignature | None = _DEFAULT_SIG,
) -> CanonicalTopologyModel:
    """Build a minimal topology with one face."""
    v = TopologyVertex(entity_id=TopologyEntityId("v-001"), point=None)
    e = TopologyEdge(
        entity_id=TopologyEntityId("e-001"),
        start_vertex_id=TopologyEntityId("v-001"),
        end_vertex_id=TopologyEntityId("v-001"),
    )
    w = TopologyWire(
        entity_id=TopologyEntityId("w-001"),
        edge_ids=(TopologyEntityId("e-001"),),
    )
    face = TopologyFace(
        entity_id=TopologyEntityId(face_id),
        outer_wire_id=TopologyEntityId("w-001"),
        surface_signature=signature,
    )
    return CanonicalTopologyModel(
        vertices=(v,),
        edges=(e,),
        wires=(w,),
        faces=(face,),
    )


def _make_cad_ref(fp: str = _SHA_A, source_id: str = "s1") -> CadSourceReference:
    return CadSourceReference(
        source_id=source_id, format="step", length_unit="mm", fingerprint=fp
    )


def _make_project_with_role(
    role: str = "PRIMARY",
    fp: str = _SHA_A,
    face_id: str = "face-001",
) -> tuple[OriglyphProject, DatumTopologyRef, DatumRoleAssignment]:
    ref = DatumTopologyRef(
        source_fingerprint=fp, entity_kind="face", entity_id=face_id
    )
    assignment = datum_role_assignment_with_topology(role, f"cand-{role}", ref)
    datum = DatumState(frame_name="DRF-1", assignments=(assignment,))
    project = build_project(
        cad_sources=(_make_cad_ref(fp),),
        datum_state=datum,
    )
    return project, ref, assignment


# ---------------------------------------------------------------------------
# 1. Planar PRIMARY valid
# ---------------------------------------------------------------------------


def test_planar_primary_valid() -> None:
    """PLANE face bound to PRIMARY role → VALID."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig(FaceSurfaceType.PLANE.value))
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.VALID
    assert result.role == "PRIMARY"
    assert result.surface_type == "PLANE"
    assert result.reason_code == "SURFACE_TYPE_VALID"


# ---------------------------------------------------------------------------
# 2. Planar SECONDARY valid
# ---------------------------------------------------------------------------


def test_planar_secondary_valid() -> None:
    """PLANE face bound to SECONDARY role → VALID."""
    project, _, _ = _make_project_with_role("SECONDARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig(FaceSurfaceType.PLANE.value))
    result = validate_datum_role_surface(project, topo, _SHA_A, "SECONDARY")
    assert result.status == DatumSurfaceValidationStatus.VALID
    assert result.role == "SECONDARY"


# ---------------------------------------------------------------------------
# 3. Planar TERTIARY valid
# ---------------------------------------------------------------------------


def test_planar_tertiary_valid() -> None:
    """PLANE face bound to TERTIARY role → VALID."""
    project, _, _ = _make_project_with_role("TERTIARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig(FaceSurfaceType.PLANE.value))
    result = validate_datum_role_surface(project, topo, _SHA_A, "TERTIARY")
    assert result.status == DatumSurfaceValidationStatus.VALID
    assert result.role == "TERTIARY"


# ---------------------------------------------------------------------------
# 4. Missing surface signature → UNRESOLVED_SURFACE_TYPE
# ---------------------------------------------------------------------------


def test_missing_surface_signature() -> None:
    """Face with surface_signature=None → UNRESOLVED_SURFACE_TYPE (fail closed)."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", signature=None)
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.UNRESOLVED_SURFACE_TYPE
    assert result.surface_type is None
    assert result.reason_code == "SURFACE_SIGNATURE_ABSENT"


# ---------------------------------------------------------------------------
# 5. UNKNOWN surface type → SURFACE_TYPE_UNVALIDATABLE
# ---------------------------------------------------------------------------


def test_unknown_surface_type() -> None:
    """Face with UNKNOWN surface type → SURFACE_TYPE_UNVALIDATABLE (fail closed)."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    sig = _make_sig(FaceSurfaceType.UNKNOWN.value, ())
    topo = _make_topology("face-001", sig)
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.SURFACE_TYPE_UNVALIDATABLE
    assert result.surface_type == "UNKNOWN"
    assert result.reason_code == "SURFACE_TYPE_UNKNOWN"


# ---------------------------------------------------------------------------
# 6. Unsupported surface type (CYLINDER) → INVALID_SURFACE_TYPE
# ---------------------------------------------------------------------------


def test_unsupported_surface_type_cylinder() -> None:
    """CYLINDER face → INVALID_SURFACE_TYPE for Stage 22H v1."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    sig = _make_sig(FaceSurfaceType.CYLINDER.value, (0.0, 0.0, 1.0, 5.0))
    topo = _make_topology("face-001", sig)
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.INVALID_SURFACE_TYPE
    assert result.surface_type == "CYLINDER"
    assert "SURFACE_TYPE_NOT_SUPPORTED" in result.reason_code


# ---------------------------------------------------------------------------
# 7. Unsupported entity kind → UNSUPPORTED_ENTITY_KIND (mocked)
# ---------------------------------------------------------------------------


def test_unsupported_entity_kind() -> None:
    """UNSUPPORTED_ENTITY_KIND returned when entity kind not in supported set."""
    import origlyph.project.datum_surface_validation as dsv

    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    with patch.object(dsv, "SUPPORTED_VALIDATION_ENTITY_KINDS", frozenset()):
        result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.UNSUPPORTED_ENTITY_KIND
    assert result.reason_code == "ENTITY_KIND_NOT_VALIDATABLE"


# ---------------------------------------------------------------------------
# 8. Missing entity → MISSING_ENTITY
# ---------------------------------------------------------------------------


def test_missing_entity() -> None:
    """Bound face ID absent from topology → MISSING_ENTITY (fail closed)."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-999")
    topo = _make_topology("face-001", _make_sig())  # face-999 not present
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.MISSING_ENTITY


# ---------------------------------------------------------------------------
# 9. Source mismatch → SOURCE_MISMATCH (fail closed)
# ---------------------------------------------------------------------------


def test_source_mismatch() -> None:
    """Wrong topology fingerprint → SOURCE_MISMATCH; validation does not proceed."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    # Pass SHA_B but binding was made with SHA_A
    result = validate_datum_role_surface(project, topo, _SHA_B, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.SOURCE_MISMATCH
    assert result.reason_code == "SOURCE_FINGERPRINT_MISMATCH"
    assert result.surface_type is None


# ---------------------------------------------------------------------------
# 10. Deterministic repeated validation
# ---------------------------------------------------------------------------


def test_deterministic_repeated_validation() -> None:
    """Same inputs always produce identical result objects."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    r1 = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    r2 = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert r1 == r2


# ---------------------------------------------------------------------------
# 11. Same binding → same result
# ---------------------------------------------------------------------------


def test_same_binding_same_result() -> None:
    """Two projects constructed from identical inputs give identical results."""
    p1, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    p2, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    r1 = validate_datum_role_surface(p1, topo, _SHA_A, "PRIMARY")
    r2 = validate_datum_role_surface(p2, topo, _SHA_A, "PRIMARY")
    assert r1 == r2


# ---------------------------------------------------------------------------
# 12. Validation does not change project_id
# ---------------------------------------------------------------------------


def test_validation_does_not_change_project_id() -> None:
    """project_id is unchanged before and after validation."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    pid_before = project.project_id  # type: ignore[union-attr]
    topo = _make_topology("face-001", _make_sig())
    validate_datum_surface(project, topo, _SHA_A)  # type: ignore[arg-type]
    assert project.project_id == pid_before  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 13. Validation result is not serialized to project JSON
# ---------------------------------------------------------------------------


def test_validation_result_not_in_project_json() -> None:
    """DatumSurfaceValidationResult is NOT present in the project JSON."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    validate_datum_surface(project, topo, _SHA_A)  # type: ignore[arg-type]
    payload = json.loads(project.to_json())  # type: ignore[union-attr]
    text = json.dumps(payload)
    assert "DatumSurfaceValidationResult" not in text
    assert "SURFACE_TYPE_VALID" not in text
    assert "validation_status" not in text


# ---------------------------------------------------------------------------
# 14. Topology not serialized
# ---------------------------------------------------------------------------


def test_topology_not_serialized() -> None:
    """CanonicalTopologyModel is NOT present in the project JSON."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    text = project.to_json()  # type: ignore[union-attr]
    assert "CanonicalTopologyModel" not in text
    assert "TopologyFace" not in text
    assert "surface_signature" not in text


# ---------------------------------------------------------------------------
# 15. OCP not serialized
# ---------------------------------------------------------------------------


def test_ocp_not_serialized() -> None:
    """OCP objects are NOT present in the project JSON."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    text = project.to_json()  # type: ignore[union-attr]
    assert "OCP" not in text
    assert "OCCT" not in text


# ---------------------------------------------------------------------------
# 16. Binding format unchanged by validation
# ---------------------------------------------------------------------------


def test_binding_format_unchanged_by_validation() -> None:
    """bound_reference_key encoding is not altered by validation."""
    project, ref, assignment = _make_project_with_role(
        "PRIMARY", _SHA_A, "face-001"
    )
    topo = _make_topology("face-001", _make_sig())
    validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")  # type: ignore[arg-type]
    # The original encoded key is deterministic and unchanged
    expected_key = encode_datum_topology_ref(ref)  # type: ignore[arg-type]
    assert is_topology_binding(assignment.bound_reference_key)  # type: ignore[union-attr]
    assert assignment.bound_reference_key == expected_key  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 17. Role preserved in result
# ---------------------------------------------------------------------------


def test_role_preserved_in_result() -> None:
    """result.role matches the datum role that was validated."""
    project, _, _ = _make_project_with_role("SECONDARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    result = validate_datum_role_surface(project, topo, _SHA_A, "SECONDARY")
    assert result.role == "SECONDARY"


# ---------------------------------------------------------------------------
# 18. entity_id preserved in result
# ---------------------------------------------------------------------------


def test_entity_id_preserved_in_result() -> None:
    """result.entity_id matches the entity ID looked up in topology."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-007")
    sig = _make_sig(entity_id="face-007")
    topo = _make_topology("face-007", sig)
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.entity_id == "face-007"


# ---------------------------------------------------------------------------
# 19. Face lookup by entity_id
# ---------------------------------------------------------------------------


def test_face_lookup_by_entity_id() -> None:
    """Validation locates the correct face among multiple faces."""
    v = TopologyVertex(entity_id=TopologyEntityId("v1"), point=None)
    e = TopologyEdge(
        entity_id=TopologyEntityId("e1"),
        start_vertex_id=TopologyEntityId("v1"),
        end_vertex_id=TopologyEntityId("v1"),
    )
    w = TopologyWire(
        entity_id=TopologyEntityId("w1"),
        edge_ids=(TopologyEntityId("e1"),),
    )
    # Two faces: one CYLINDER, one PLANE — binding targets PLANE face
    face_cyl = TopologyFace(
        entity_id=TopologyEntityId("face-cyl"),
        outer_wire_id=TopologyEntityId("w1"),
        surface_signature=_make_sig(FaceSurfaceType.CYLINDER.value, ()),
    )
    face_plane = TopologyFace(
        entity_id=TopologyEntityId("face-plane"),
        outer_wire_id=TopologyEntityId("w1"),
        surface_signature=_make_sig(FaceSurfaceType.PLANE.value),
    )
    topo = CanonicalTopologyModel(
        vertices=(v,), edges=(e,), wires=(w,), faces=(face_cyl, face_plane)
    )

    ref = DatumTopologyRef(
        source_fingerprint=_SHA_A, entity_kind="face", entity_id="face-plane"
    )
    assignment = datum_role_assignment_with_topology("PRIMARY", "cand-A", ref)
    datum = DatumState(frame_name="DRF-1", assignments=(assignment,))
    project = build_project(
        cad_sources=(_make_cad_ref(_SHA_A),), datum_state=datum
    )

    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.VALID
    assert result.entity_id == "face-plane"
    assert result.surface_type == "PLANE"


# ---------------------------------------------------------------------------
# 20. Backward compatible: unbound datum → UNBOUND
# ---------------------------------------------------------------------------


def test_backward_compatible_unbound_datum() -> None:
    """Unbound datum role (no topology binding) returns UNBOUND status."""
    unbound = DatumRoleAssignment(role="PRIMARY", candidate_key="cand-X")
    datum = DatumState(frame_name="DRF-1", assignments=(unbound,))
    project = build_project(datum_state=datum)
    topo = _make_topology("face-001", _make_sig())
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.UNBOUND
    assert result.entity_kind is None
    assert result.surface_type is None


# ---------------------------------------------------------------------------
# 21. No hidden tolerance defaults in module
# ---------------------------------------------------------------------------


def test_no_hidden_tolerance_in_module() -> None:
    """Module does not introduce hidden numeric tolerance constants."""
    import origlyph.project.datum_surface_validation as dsv

    # Only the two frozensets (valid + unvalidatable surface types) exist
    # as rule-table constants.  No float epsilon constants.
    for name in dir(dsv):
        if name.startswith("_") and not name.startswith("__"):
            val = getattr(dsv, name)
            assert not isinstance(val, float), (
                f"Found hidden float constant {name}={val!r} in "
                f"datum_surface_validation module"
            )


# ---------------------------------------------------------------------------
# 22. Same-source reopen: same validation result
# ---------------------------------------------------------------------------


def test_same_source_reopen_same_validation_result() -> None:
    """Save → reload project → validate → same result as before save."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())

    result_before = validate_datum_role_surface(
        project, topo, _SHA_A, "PRIMARY"  # type: ignore[arg-type]
    )

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.origlyph"
        save_project(project, p)  # type: ignore[arg-type]
        reloaded = load_project(p)

    result_after = validate_datum_role_surface(reloaded, topo, _SHA_A, "PRIMARY")

    assert result_before == result_after
    assert result_after.status == DatumSurfaceValidationStatus.VALID


# ---------------------------------------------------------------------------
# 23. validate_datum_surface returns tuple of all roles
# ---------------------------------------------------------------------------


def test_validate_datum_surface_all_roles() -> None:
    """validate_datum_surface returns one result per assignment."""
    ref_p = DatumTopologyRef(
        source_fingerprint=_SHA_A, entity_kind="face", entity_id="fp"
    )
    ref_s = DatumTopologyRef(
        source_fingerprint=_SHA_A, entity_kind="face", entity_id="fs"
    )
    datum = DatumState(
        frame_name="DRF-1",
        assignments=(
            datum_role_assignment_with_topology("PRIMARY", "cand-P", ref_p),
            datum_role_assignment_with_topology("SECONDARY", "cand-S", ref_s),
        ),
    )
    project = build_project(
        cad_sources=(_make_cad_ref(_SHA_A),), datum_state=datum
    )

    v = TopologyVertex(entity_id=TopologyEntityId("v1"), point=None)
    e = TopologyEdge(
        entity_id=TopologyEntityId("e1"),
        start_vertex_id=TopologyEntityId("v1"),
        end_vertex_id=TopologyEntityId("v1"),
    )
    w = TopologyWire(
        entity_id=TopologyEntityId("w1"), edge_ids=(TopologyEntityId("e1"),)
    )
    face_p = TopologyFace(
        entity_id=TopologyEntityId("fp"),
        outer_wire_id=TopologyEntityId("w1"),
        surface_signature=_make_sig(),
    )
    face_s = TopologyFace(
        entity_id=TopologyEntityId("fs"),
        outer_wire_id=TopologyEntityId("w1"),
        surface_signature=_make_sig(entity_id="fs"),
    )
    topo = CanonicalTopologyModel(
        vertices=(v,), edges=(e,), wires=(w,), faces=(face_p, face_s)
    )

    results = validate_datum_surface(project, topo, _SHA_A)
    assert len(results) == 2
    by_role = {r.role: r.status for r in results}
    assert by_role["PRIMARY"] == DatumSurfaceValidationStatus.VALID
    assert by_role["SECONDARY"] == DatumSurfaceValidationStatus.VALID


# ---------------------------------------------------------------------------
# 24. SUPPORTED_VALIDATION_ENTITY_KINDS constant
# ---------------------------------------------------------------------------


def test_supported_validation_entity_kinds() -> None:
    """SUPPORTED_VALIDATION_ENTITY_KINDS contains 'face' and only 'face'."""
    assert "face" in SUPPORTED_VALIDATION_ENTITY_KINDS
    assert SUPPORTED_VALIDATION_ENTITY_KINDS == frozenset({"face"})


# ---------------------------------------------------------------------------
# 25. No datum_state → empty tuple
# ---------------------------------------------------------------------------


def test_no_datum_state_returns_empty_tuple() -> None:
    """Projects without datum_state return an empty validation tuple."""
    project = build_project()
    topo = _make_topology()
    results = validate_datum_surface(project, topo, _SHA_A)
    assert results == ()


# ---------------------------------------------------------------------------
# 26. Invalid topology fingerprint raises
# ---------------------------------------------------------------------------


def test_invalid_topology_fingerprint_raises() -> None:
    """Non-sha256 topology_fingerprint raises InvalidProjectError."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    topo = _make_topology("face-001", _make_sig())
    with pytest.raises(InvalidProjectError, match="topology_fingerprint"):
        validate_datum_surface(project, topo, "not-a-sha")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 27. All surface types in INVALID set return INVALID_SURFACE_TYPE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stype",
    [
        FaceSurfaceType.CYLINDER.value,
        FaceSurfaceType.CONE.value,
        FaceSurfaceType.SPHERE.value,
        FaceSurfaceType.TORUS.value,
        FaceSurfaceType.BSPLINE.value,
    ],
)
def test_non_plane_surface_types_invalid(stype: str) -> None:
    """Non-PLANE, non-UNKNOWN surface types return INVALID_SURFACE_TYPE."""
    project, _, _ = _make_project_with_role("PRIMARY", _SHA_A, "face-001")
    sig = _make_sig(stype, ())
    topo = _make_topology("face-001", sig)
    result = validate_datum_role_surface(project, topo, _SHA_A, "PRIMARY")
    assert result.status == DatumSurfaceValidationStatus.INVALID_SURFACE_TYPE
    assert result.surface_type == stype
