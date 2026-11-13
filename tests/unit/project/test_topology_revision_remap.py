"""Unit tests for topology_revision_remap and datum_topology_binding v2 (Stage 22H)."""
from __future__ import annotations

import hashlib
from typing import Optional

import pytest

from origlyph.cad.topology import (
    CanonicalTopologyModel,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyShell,
    TopologySolid,
    TopologyVertex,
    TopologyWire,
)
from origlyph.cad.topology_signature import (
    FaceSurfaceType,
    TopologyFaceSignature,
    build_face_signature,
)
from origlyph.geometry import Point3D
from origlyph.project.datum_topology_binding import (
    BINDING_FORMAT_VERSION,
    BINDING_FORMAT_VERSION_V2,
    RESOLUTION_AMBIGUOUS,
    RESOLUTION_REMAPPED_EXACT,
    RESOLUTION_REMAPPED_PROBABLE,
    DatumTopologyRef,
    decode_datum_topology_ref,
    encode_datum_topology_ref,
    is_topology_binding,
)
from origlyph.project.exceptions import InvalidProjectError
from origlyph.project.topology_revision_remap import (
    RevisionMatchClass,
    RevisionRemapResult,
    remap_all_face_bindings,
    remap_face_binding,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FAKE_FP = "a" * 64
_FAKE_FP2 = "b" * 64

_SQUARE_PTS = [
    (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
]
_RECT_PTS = [
    (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.0),
]
_LARGE_PTS = [
    (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
]


def _sig(
    pts: list[tuple[float, float, float]] = _SQUARE_PTS,
    stype: FaceSurfaceType = FaceSurfaceType.PLANE,
    sparams: tuple[float, ...] = (0.0, 0.0, 1.0, 0.0),
    area: Optional[float] = 1.0,
) -> TopologyFaceSignature:
    return build_face_signature(
        vertex_points=pts,
        surface_type=stype,
        surface_params=sparams,
        area=area,
        edge_count=4,
    )


def _face(
    face_id: str,
    sig: Optional[TopologyFaceSignature] = None,
    wire_id: str = "w:0001",
) -> TopologyFace:
    return TopologyFace(
        entity_id=TopologyEntityId(face_id),
        outer_wire_id=TopologyEntityId(wire_id),
        surface_signature=sig,
    )


def _minimal_topology(faces: list[TopologyFace]) -> CanonicalTopologyModel:
    """Minimal valid CanonicalTopologyModel for the given faces."""
    vertices = [
        TopologyVertex(entity_id=TopologyEntityId("v:0001"), point=Point3D(0, 0, 0))
    ]
    edges = [
        TopologyEdge(
            entity_id=TopologyEntityId("e:0001"),
            start_vertex_id=TopologyEntityId("v:0001"),
            end_vertex_id=TopologyEntityId("v:0001"),
        )
    ]
    wire_ids_seen: set[str] = set()
    wires: list[TopologyWire] = []
    for face in faces:
        wid = face.outer_wire_id.value
        if wid not in wire_ids_seen:
            wire_ids_seen.add(wid)
            wires.append(
                TopologyWire(
                    entity_id=TopologyEntityId(wid),
                    edge_ids=(TopologyEntityId("e:0001"),),
                )
            )
    all_fids = tuple(f.entity_id for f in faces)
    shells: list[TopologyShell] = []
    solids: list[TopologySolid] = []
    if faces:
        shells = [
            TopologyShell(entity_id=TopologyEntityId("s:0001"), face_ids=all_fids)
        ]
        solids = [
            TopologySolid(
                entity_id=TopologyEntityId("b:0001"),
                outer_shell_id=TopologyEntityId("s:0001"),
            )
        ]
    return CanonicalTopologyModel(
        source=None,  # type: ignore[arg-type]
        vertices=tuple(vertices),
        edges=tuple(edges),
        wires=tuple(wires),
        faces=tuple(faces),
        shells=tuple(shells),
        solids=tuple(solids),
    )


# ---------------------------------------------------------------------------
# DatumTopologyRef v2 encode / decode
# ---------------------------------------------------------------------------


def test_v1_encode_decode_unchanged() -> None:
    ref = DatumTopologyRef(
        source_fingerprint=_FAKE_FP, entity_kind="face", entity_id="f:0001"
    )
    key = encode_datum_topology_ref(ref)
    assert key.startswith("topology:v1:")
    decoded = decode_datum_topology_ref(key)
    assert decoded.persistent_id is None
    assert decoded.entity_id == "f:0001"
    assert decoded.source_fingerprint == _FAKE_FP


def test_v2_encode_decode_roundtrip() -> None:
    pid = hashlib.sha256(b"face-sig").hexdigest()
    ref = DatumTopologyRef(_FAKE_FP, "face", "f:0001", persistent_id=pid)
    key = encode_datum_topology_ref(ref)
    assert key.startswith("topology:v2:")
    decoded = decode_datum_topology_ref(key)
    assert decoded.persistent_id == pid
    assert decoded.entity_id == "f:0001"
    assert decoded.source_fingerprint == _FAKE_FP


def test_v2_entity_id_with_colon_preserved() -> None:
    """Entity IDs containing colons must survive encode → decode (MUST 20)."""
    pid = hashlib.sha256(b"test").hexdigest()
    ref = DatumTopologyRef(_FAKE_FP, "face", "f:0001", persistent_id=pid)
    key = encode_datum_topology_ref(ref)
    decoded = decode_datum_topology_ref(key)
    assert decoded.entity_id == "f:0001"
    assert decoded.persistent_id == pid


def test_is_topology_binding_v1() -> None:
    key = encode_datum_topology_ref(
        DatumTopologyRef(_FAKE_FP, "face", "f:0001")
    )
    assert is_topology_binding(key)


def test_is_topology_binding_v2() -> None:
    pid = hashlib.sha256(b"x").hexdigest()
    ref = DatumTopologyRef(_FAKE_FP, "face", "f:0001", persistent_id=pid)
    key = encode_datum_topology_ref(ref)
    assert is_topology_binding(key)


def test_is_topology_binding_none_returns_false() -> None:
    assert not is_topology_binding(None)


def test_is_topology_binding_garbage_returns_false() -> None:
    assert not is_topology_binding("not-a-binding")


def test_new_resolution_constants_values() -> None:
    assert RESOLUTION_REMAPPED_EXACT == "REMAPPED_EXACT"
    assert RESOLUTION_REMAPPED_PROBABLE == "REMAPPED_PROBABLE"
    assert RESOLUTION_AMBIGUOUS == "AMBIGUOUS"


def test_binding_format_v2_constant() -> None:
    assert BINDING_FORMAT_VERSION_V2 == "topology:v2"
    assert BINDING_FORMAT_VERSION == "topology:v1"


def test_v2_bad_pid_raises() -> None:
    with pytest.raises((InvalidProjectError, Exception)):
        DatumTopologyRef(_FAKE_FP, "face", "f:0001", persistent_id="not-sha256")


def test_old_v1_fixture_decode() -> None:
    """Pre-22H v1 key must decode unchanged (MUST 32)."""
    old_key = f"topology:v1:{_FAKE_FP}:face:f:0042"
    decoded = decode_datum_topology_ref(old_key)
    assert decoded.entity_id == "f:0042"
    assert decoded.persistent_id is None


def test_malformed_v2_too_short_raises() -> None:
    bad_key = f"topology:v2:{_FAKE_FP}:face:f:0001:tooshort"
    with pytest.raises((InvalidProjectError, Exception)):
        decode_datum_topology_ref(bad_key)


# ---------------------------------------------------------------------------
# RevisionMatchClass
# ---------------------------------------------------------------------------


def test_revision_match_class_members() -> None:
    assert RevisionMatchClass.EXACT == "EXACT"
    assert RevisionMatchClass.PROBABLE == "PROBABLE"
    assert RevisionMatchClass.AMBIGUOUS == "AMBIGUOUS"
    assert RevisionMatchClass.NO_MATCH == "NO_MATCH"


# ---------------------------------------------------------------------------
# remap_face_binding — no signature (pre-22H binding)
# ---------------------------------------------------------------------------


def test_remap_no_signature_returns_no_match() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_face_binding("f:0001", None, topo)
    assert result.match_class == RevisionMatchClass.NO_MATCH
    assert result.confirmation_required is True
    assert result.auto_remapped is False
    assert result.old_persistent_id is None


# ---------------------------------------------------------------------------
# remap_face_binding — EXACT
# ---------------------------------------------------------------------------


def test_remap_same_file_reopen_exact() -> None:
    """MUST 1: reopening same file → EXACT (MUST 15)."""
    old_sig = _sig()
    new_sig = _sig()
    topo = _minimal_topology([_face("f:0001", sig=new_sig)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.EXACT
    assert result.auto_remapped is True
    assert result.confirmation_required is False
    assert result.new_candidate_id == "f:0001"
    assert result.new_persistent_id == new_sig.persistent_id


def test_remap_exact_different_entity_id() -> None:
    """Same geometry, new entity number → EXACT via persistent_id match."""
    old_sig = _sig()
    new_sig = _sig()
    topo = _minimal_topology([_face("f:0099", sig=new_sig)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.EXACT
    assert result.new_candidate_id == "f:0099"


def test_remap_exact_confidence_high() -> None:
    old_sig = _sig()
    new_sig = _sig()
    topo = _minimal_topology([_face("f:0001", sig=new_sig)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.confidence >= 0.9


# ---------------------------------------------------------------------------
# remap_face_binding — surface type mismatch → NO_MATCH
# ---------------------------------------------------------------------------


def test_remap_surface_type_mismatch_no_match() -> None:
    old_sig = _sig(stype=FaceSurfaceType.PLANE)
    new_sig = _sig(stype=FaceSurfaceType.CYLINDER, sparams=(0.0, 0.0, 1.0, 1.0))
    topo = _minimal_topology([_face("f:0001", sig=new_sig)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.NO_MATCH


def test_remap_no_candidate_no_match() -> None:
    old_sig = _sig()
    topo = _minimal_topology([_face("f:0001", sig=None)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.NO_MATCH
    assert result.candidate_count == 0


def test_remap_removed_face_no_match() -> None:
    """Face removed in revision → NO_MATCH."""
    old_sig = _sig()
    different_sig = _sig(pts=_RECT_PTS, area=2.0)
    topo = _minimal_topology([_face("f:0099", sig=different_sig)])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.NO_MATCH


# ---------------------------------------------------------------------------
# remap_face_binding — AMBIGUOUS (face split/merge, duplicate candidates)
# ---------------------------------------------------------------------------


def test_remap_multiple_exact_candidates_ambiguous() -> None:
    """MUST 12: multiple exact candidates → AMBIGUOUS, fail-closed."""
    old_sig = _sig()
    f1 = _face("f:0001", sig=_sig(), wire_id="w:0001")
    f2 = _face("f:0002", sig=_sig(), wire_id="w:0002")
    topo = _minimal_topology([f1, f2])
    result = remap_face_binding("f:0001", old_sig, topo)
    assert result.match_class == RevisionMatchClass.AMBIGUOUS
    assert result.confirmation_required is True
    assert result.auto_remapped is False
    assert result.candidate_count == 2


def test_remap_ambiguous_no_auto_remap() -> None:
    """FACE_SPLIT_AUTO_REMAP=NO (MUST 14)."""
    old_sig = _sig()
    f1 = _face("f:0001", sig=_sig(), wire_id="w:0001")
    f2 = _face("f:0002", sig=_sig(), wire_id="w:0002")
    topo = _minimal_topology([f1, f2])
    result = remap_face_binding("f:old", old_sig, topo)
    assert result.auto_remapped is False


def test_remap_ambiguous_winner_is_none() -> None:
    """AMBIGUOUS result must NOT name a winner."""
    old_sig = _sig()
    f1 = _face("f:0001", sig=_sig(), wire_id="w:0001")
    f2 = _face("f:0002", sig=_sig(), wire_id="w:0002")
    topo = _minimal_topology([f1, f2])
    result = remap_face_binding("f:old", old_sig, topo)
    if result.match_class == RevisionMatchClass.AMBIGUOUS:
        assert result.new_candidate_id is None
        assert result.new_persistent_id is None


# ---------------------------------------------------------------------------
# remap_all_face_bindings
# ---------------------------------------------------------------------------


def test_remap_all_batch_exact() -> None:
    sig_a = _sig()
    sig_b = _sig(pts=_RECT_PTS, sparams=(0.0, 0.0, 1.0, 0.0), area=2.0)
    new_a = _sig()
    new_b = _sig(pts=_RECT_PTS, sparams=(0.0, 0.0, 1.0, 0.0), area=2.0)
    f_a = _face("f:0001", sig=new_a, wire_id="w:0001")
    f_b = _face("f:0002", sig=new_b, wire_id="w:0002")
    topo = _minimal_topology([f_a, f_b])
    result = remap_all_face_bindings(["f:0001", "f:0002"], [sig_a, sig_b], topo)
    assert isinstance(result, RevisionRemapResult)
    assert result.exact_count == 2
    assert result.probable_count == 0
    assert result.ambiguous_count == 0
    assert result.no_match_count == 0


def test_remap_all_batch_mixed() -> None:
    sig_match = _sig()
    sig_lost = _sig(pts=_LARGE_PTS, area=100.0)
    topo = _minimal_topology([_face("f:0001", sig=_sig(), wire_id="w:0001")])
    result = remap_all_face_bindings(["f:0001", "f:old"], [sig_match, sig_lost], topo)
    assert len(result.matches) == 2


def test_remap_all_length_mismatch_raises() -> None:
    topo = _minimal_topology([])
    with pytest.raises((InvalidProjectError, Exception)):
        remap_all_face_bindings(["f:0001"], [], topo)


def test_remap_all_no_signature_in_batch() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_all_face_bindings(["f:0001"], [None], topo)
    assert result.no_match_count == 1
    assert result.matches[0].match_class == RevisionMatchClass.NO_MATCH


def test_remap_all_counts_sum_to_total() -> None:
    sig_a = _sig()
    sig_b = _sig()
    topo = _minimal_topology([_face("f:0001", sig=_sig(), wire_id="w:0001")])
    result = remap_all_face_bindings(["f:0001", "f:0002"], [sig_a, sig_b], topo)
    total = (
        result.exact_count
        + result.probable_count
        + result.ambiguous_count
        + result.no_match_count
    )
    assert total == len(result.matches)


# ---------------------------------------------------------------------------
# FaceRevisionMatch / RevisionRemapResult structural invariants
# ---------------------------------------------------------------------------


def test_face_revision_match_frozen() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_face_binding("f:0001", _sig(), topo)
    with pytest.raises((AttributeError, TypeError)):
        result.match_class = RevisionMatchClass.NO_MATCH  # type: ignore[misc]


def test_revision_remap_result_frozen() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_all_face_bindings(["f:0001"], [_sig()], topo)
    with pytest.raises((AttributeError, TypeError)):
        result.exact_count = 999  # type: ignore[misc]


def test_reasons_non_empty() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_face_binding("f:0001", _sig(), topo)
    assert len(result.reasons) >= 1


def test_confidence_in_range() -> None:
    topo = _minimal_topology([_face("f:0001", sig=_sig())])
    result = remap_face_binding("f:0001", _sig(), topo)
    assert 0.0 <= result.confidence <= 1.0


def test_no_match_confidence_zero() -> None:
    topo = _minimal_topology([_face("f:0001", sig=None)])
    result = remap_face_binding("f:0001", _sig(), topo)
    assert result.confidence == 0.0
