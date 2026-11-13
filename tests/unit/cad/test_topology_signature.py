"""Unit tests for origlyph.cad.topology_signature (Stage 22H)."""
from __future__ import annotations

import math
from typing import Optional

import pytest

from origlyph.cad.topology_signature import (
    QUANTIZE_PRECISION,
    FaceSurfaceType,
    TopologyFaceSignature,
    _quantize,
    _safe_finite,
    build_face_signature,
    compute_persistent_face_id,
    compute_vertex_fingerprint,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_UNIT_SQUARE = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (1.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
]
_UNIT_SQUARE_TRANSLATED = [
    (5.0, 3.0, -2.0),
    (6.0, 3.0, -2.0),
    (6.0, 4.0, -2.0),
    (5.0, 4.0, -2.0),
]
_UNIT_SQUARE_SHUFFLED = [
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (1.0, 1.0, 0.0),
    (0.0, 0.0, 0.0),
]
_LARGE_SQUARE = [
    (0.0, 0.0, 0.0),
    (100.0, 0.0, 0.0),
    (100.0, 100.0, 0.0),
    (0.0, 100.0, 0.0),
]


def _make_sig(
    pts: list[tuple[float, float, float]] = _UNIT_SQUARE,
    stype: FaceSurfaceType = FaceSurfaceType.PLANE,
    sparams: tuple[float, ...] = (0.0, 0.0, 1.0, 0.0),
    area: Optional[float] = 1.0,
    source_id: Optional[str] = None,
    normal: Optional[tuple[float, float, float]] = (0.0, 0.0, 1.0),
    adj: int = 4,
    edges: int = 4,
) -> TopologyFaceSignature:
    return build_face_signature(
        vertex_points=pts,
        surface_type=stype,
        surface_params=sparams,
        source_entity_id=source_id,
        area=area,
        normal=normal,
        adjacent_face_count=adj,
        edge_count=edges,
    )


# ---------------------------------------------------------------------------
# QUANTIZE_PRECISION constant
# ---------------------------------------------------------------------------


def test_quantize_precision_value() -> None:
    assert QUANTIZE_PRECISION == 1e-6


def test_quantize_rounds_to_precision() -> None:
    x = 1.0000004
    q = _quantize(x)
    assert abs(q - round(x / 1e-6) * 1e-6) < 1e-14


def test_safe_finite_passthrough() -> None:
    assert _safe_finite(3.14) == 3.14


def test_safe_finite_inf_returns_zero() -> None:
    assert _safe_finite(math.inf) == 0.0


def test_safe_finite_nan_returns_zero() -> None:
    assert _safe_finite(math.nan) == 0.0


# ---------------------------------------------------------------------------
# FaceSurfaceType
# ---------------------------------------------------------------------------


def test_face_surface_type_all_members() -> None:
    expected = {
        "PLANE", "CYLINDER", "CONE", "SPHERE", "TORUS",
        "REVOLUTION", "EXTRUSION", "OFFSET", "BSPLINE", "UNKNOWN",
    }
    assert {m.value for m in FaceSurfaceType} == expected


def test_face_surface_type_str_enum() -> None:
    assert FaceSurfaceType.PLANE == "PLANE"


def test_face_surface_type_unknown_safe() -> None:
    assert FaceSurfaceType.UNKNOWN.value == "UNKNOWN"


# ---------------------------------------------------------------------------
# compute_vertex_fingerprint
# ---------------------------------------------------------------------------


def test_vfp_deterministic() -> None:
    fp1 = compute_vertex_fingerprint(_UNIT_SQUARE)
    fp2 = compute_vertex_fingerprint(_UNIT_SQUARE)
    assert fp1 == fp2


def test_vfp_translation_invariant() -> None:
    """MUST 4: same geometry translated → same fingerprint."""
    fp_orig = compute_vertex_fingerprint(_UNIT_SQUARE)
    fp_trans = compute_vertex_fingerprint(_UNIT_SQUARE_TRANSLATED)
    assert fp_orig == fp_trans


def test_vfp_order_independent() -> None:
    """MUST 28: shuffled point order → same fingerprint."""
    fp_orig = compute_vertex_fingerprint(_UNIT_SQUARE)
    fp_shuffled = compute_vertex_fingerprint(_UNIT_SQUARE_SHUFFLED)
    assert fp_orig == fp_shuffled


def test_vfp_different_geometry_different() -> None:
    different = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)]
    fp_orig = compute_vertex_fingerprint(_UNIT_SQUARE)
    fp_diff = compute_vertex_fingerprint(different)
    assert fp_orig != fp_diff


def test_vfp_empty_set_stable() -> None:
    fp = compute_vertex_fingerprint([])
    assert len(fp) == 64
    assert fp == compute_vertex_fingerprint([])


def test_vfp_returns_sha256_hex() -> None:
    fp = compute_vertex_fingerprint(_UNIT_SQUARE)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_vfp_small_geometry_change_differs() -> None:
    slightly_different = list(_UNIT_SQUARE)
    slightly_different[0] = (0.001, 0.0, 0.0)
    fp_orig = compute_vertex_fingerprint(_UNIT_SQUARE)
    fp_diff = compute_vertex_fingerprint(slightly_different)
    assert fp_orig != fp_diff


def test_vfp_nonfinite_coordinate_no_raise() -> None:
    with_nan = [(math.nan, 0.0, 0.0), (1.0, 0.0, 0.0)]
    fp = compute_vertex_fingerprint(with_nan)
    assert len(fp) == 64


# ---------------------------------------------------------------------------
# compute_persistent_face_id
# ---------------------------------------------------------------------------


def test_pid_deterministic() -> None:
    vfp = compute_vertex_fingerprint(_UNIT_SQUARE)
    pid1 = compute_persistent_face_id(vfp, "PLANE", (0.0, 0.0, 1.0, 0.0))
    pid2 = compute_persistent_face_id(vfp, "PLANE", (0.0, 0.0, 1.0, 0.0))
    assert pid1 == pid2


def test_pid_sha256_hex() -> None:
    vfp = compute_vertex_fingerprint(_UNIT_SQUARE)
    pid = compute_persistent_face_id(vfp, "PLANE", ())
    assert len(pid) == 64
    assert all(c in "0123456789abcdef" for c in pid)


def test_pid_surface_type_affects_id() -> None:
    vfp = compute_vertex_fingerprint(_UNIT_SQUARE)
    pid_plane = compute_persistent_face_id(vfp, "PLANE", ())
    pid_cyl = compute_persistent_face_id(vfp, "CYLINDER", ())
    assert pid_plane != pid_cyl


def test_pid_surface_params_affect_id() -> None:
    vfp = compute_vertex_fingerprint(_UNIT_SQUARE)
    pid_a = compute_persistent_face_id(vfp, "CYLINDER", (0.0, 0.0, 1.0, 5.0))
    pid_b = compute_persistent_face_id(vfp, "CYLINDER", (0.0, 0.0, 1.0, 10.0))
    assert pid_a != pid_b


def test_pid_does_not_encode_object_identity() -> None:
    """MUST 8: persistent ID must not use Python id() or memory addresses."""
    vfp = compute_vertex_fingerprint(_UNIT_SQUARE)
    pid = compute_persistent_face_id(vfp, "PLANE", ())
    pid2 = compute_persistent_face_id(vfp, "PLANE", ())
    assert pid == pid2


# ---------------------------------------------------------------------------
# build_face_signature
# ---------------------------------------------------------------------------


def test_sig_basic_construction() -> None:
    sig = _make_sig()
    assert sig.surface_type == "PLANE"
    assert sig.persistent_id
    assert len(sig.persistent_id) == 64


def test_sig_same_geometry_same_pid() -> None:
    """MUST 1: reopening the same STEP file → same persistent_id."""
    sig1 = _make_sig()
    sig2 = _make_sig()
    assert sig1.persistent_id == sig2.persistent_id


def test_sig_translation_same_pid() -> None:
    """MUST 4: translation-invariant vertex fingerprint → same persistent_id."""
    sig_orig = _make_sig(pts=_UNIT_SQUARE)
    sig_trans = _make_sig(pts=_UNIT_SQUARE_TRANSLATED)
    assert sig_orig.persistent_id == sig_trans.persistent_id


def test_sig_vertex_order_same_pid() -> None:
    """MUST 28: order-independent fingerprint."""
    sig_orig = _make_sig(pts=_UNIT_SQUARE)
    sig_shuffled = _make_sig(pts=_UNIT_SQUARE_SHUFFLED)
    assert sig_orig.persistent_id == sig_shuffled.persistent_id


def test_sig_surface_type_mismatch_different_pid() -> None:
    sig_plane = _make_sig(stype=FaceSurfaceType.PLANE, sparams=())
    sig_cyl = _make_sig(stype=FaceSurfaceType.CYLINDER, sparams=())
    assert sig_plane.persistent_id != sig_cyl.persistent_id


def test_sig_surface_param_mismatch_different_pid() -> None:
    sig_a = _make_sig(sparams=(0.0, 0.0, 1.0, 0.0))
    sig_b = _make_sig(sparams=(0.0, 0.0, 1.0, 5.0))
    assert sig_a.persistent_id != sig_b.persistent_id


def test_sig_centroid_mismatch_different_pid() -> None:
    sig_orig = _make_sig(pts=_UNIT_SQUARE)
    sig_large = _make_sig(pts=_LARGE_SQUARE)
    assert sig_orig.persistent_id != sig_large.persistent_id


def test_sig_unknown_surface_type() -> None:
    sig = _make_sig(stype=FaceSurfaceType.UNKNOWN, sparams=())
    assert sig.surface_type == "UNKNOWN"
    assert sig.surface_params == ()


def test_sig_as_dict_roundtrip() -> None:
    sig = _make_sig()
    d = sig.as_dict()
    assert d["persistent_id"] == sig.persistent_id
    assert d["surface_type"] == sig.surface_type
    assert isinstance(d["surface_params"], list)
    assert isinstance(d["normalized_centroid"], list)
    assert isinstance(d["vertex_fingerprint"], str)


def test_sig_adjacency_signature() -> None:
    sig = _make_sig(adj=6, edges=12)
    assert sig.adjacency_signature == (6, 12)


def test_sig_area_quantized() -> None:
    sig = _make_sig(area=1.000000001)
    assert sig.area == pytest.approx(1.0, abs=1e-5)


def test_sig_normal_normalized() -> None:
    sig = _make_sig(normal=(0.0, 0.0, 5.0))
    assert sig.normal_signature is not None
    assert abs(sig.normal_signature[2] - 1.0) < 1e-5


def test_sig_zero_normal_becomes_none() -> None:
    sig = _make_sig(normal=(0.0, 0.0, 0.0))
    assert sig.normal_signature is None


def test_sig_no_ocp_objects_in_dict() -> None:
    """RAW_OCP_SERIALIZED must be NO (MUST 2)."""
    sig = _make_sig()
    d = sig.as_dict()
    for v in d.values():
        assert v is None or isinstance(v, (str, float, int, list))


def test_sig_frozen_dataclass() -> None:
    sig = _make_sig()
    with pytest.raises((AttributeError, TypeError)):
        sig.persistent_id = "new"  # type: ignore[misc]


def test_sig_centroid_matches_input() -> None:
    sig = _make_sig(pts=_UNIT_SQUARE)
    cx, cy, cz = sig.normalized_centroid
    assert abs(cx - 0.5) < 1e-4
    assert abs(cy - 0.5) < 1e-4
    assert abs(cz) < 1e-4


def test_sig_source_entity_id_stored() -> None:
    sig = _make_sig(source_id="f:0042")
    assert sig.source_entity_id == "f:0042"


def test_sig_string_surface_type_accepted() -> None:
    sig = _make_sig(stype="CYLINDER")  # type: ignore[arg-type]
    assert sig.surface_type == "CYLINDER"


def test_sig_large_geometry_modification_different_pid() -> None:
    sig_small = _make_sig(pts=_UNIT_SQUARE)
    sig_large = _make_sig(pts=_LARGE_SQUARE)
    assert sig_small.persistent_id != sig_large.persistent_id


def test_sig_serialization_stability() -> None:
    """Calling build_face_signature multiple times → identical as_dict output."""
    d1 = _make_sig().as_dict()
    d2 = _make_sig().as_dict()
    assert d1 == d2
