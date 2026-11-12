"""Unit tests for the experimental STEP kernel adapter (Stage 22D spike).

Covers: kernel detection, fail-closed error handling, valid conversion,
deterministic snapshot IDs, vertex geometry binding, provenance, kernel
object isolation, and production registration guard.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from origlyph.cad.exceptions import CadImportError, OriglyphCadError
from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.cad.step_kernel_adapter import (
    StepKernelAdapter,
    StepKernelUnavailableError,
)
from origlyph.cad.topology import CanonicalTopologyModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OCP_PRESENT: bool = importlib.util.find_spec("OCP") is not None

skip_if_no_ocp = pytest.mark.skipif(
    not OCP_PRESENT,
    reason="OCP/cadquery-ocp-novtk not installed",
)

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"


def _make_source(source_id: str = "test-001") -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="simple_box.step",
    )


def _convert_box() -> CanonicalTopologyModel:
    adapter = StepKernelAdapter(SIMPLE_BOX_STEP)
    return adapter.to_canonical_topology(_make_source())


# ---------------------------------------------------------------------------
# Kernel availability detection
# ---------------------------------------------------------------------------


def test_ocp_available_flag():
    """importlib.util.find_spec correctly detects OCP presence."""
    spec = importlib.util.find_spec("OCP")
    assert (spec is not None) == OCP_PRESENT


def test_unavailable_kernel_raises():
    """StepKernelAdapter raises StepKernelUnavailableError when OCP absent."""
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        adapter = StepKernelAdapter(SIMPLE_BOX_STEP)
        with pytest.raises(StepKernelUnavailableError):
            adapter.to_canonical_topology(_make_source())


def test_unavailable_error_is_origlyph_error():
    """StepKernelUnavailableError is an OriglyphCadError subclass."""
    assert issubclass(StepKernelUnavailableError, OriglyphCadError)


# ---------------------------------------------------------------------------
# Fail-closed: missing / malformed / empty STEP
# ---------------------------------------------------------------------------


def test_missing_file_fail_closed():
    """Adapter raises CadImportError for a non-existent file."""
    adapter = StepKernelAdapter(FIXTURE_DIR / "does_not_exist.step")
    with pytest.raises(CadImportError, match="not found"):
        adapter.to_canonical_topology(_make_source())


@skip_if_no_ocp
def test_malformed_step_fail_closed(tmp_path: Path):
    """Adapter raises CadImportError for a file with invalid STEP content."""
    bad = tmp_path / "bad.step"
    bad.write_text(
        "THIS IS NOT A VALID STEP FILE CONTENT xyz 123 !@#",
        encoding="ascii",
    )
    adapter = StepKernelAdapter(bad)
    with pytest.raises(CadImportError):
        adapter.to_canonical_topology(_make_source())


@skip_if_no_ocp
def test_empty_step_fail_closed(tmp_path: Path):
    """Adapter raises CadImportError for an empty file."""
    empty = tmp_path / "empty.step"
    empty.write_text("", encoding="ascii")
    adapter = StepKernelAdapter(empty)
    with pytest.raises(CadImportError):
        adapter.to_canonical_topology(_make_source())


@skip_if_no_ocp
def test_no_body_fail_closed(tmp_path: Path):
    """Adapter raises CadImportError for a valid STEP with no solid body."""
    # Minimal valid STEP header with no geometry data
    no_geom = tmp_path / "no_body.step"
    no_geom.write_text(
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('Empty'),'2;1');\n"
        "FILE_NAME('empty','2026-01-01T00:00:00',(''),(''),'','','');\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n"
        "ENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n",
        encoding="ascii",
    )
    adapter = StepKernelAdapter(no_geom)
    with pytest.raises(CadImportError):
        adapter.to_canonical_topology(_make_source())


# ---------------------------------------------------------------------------
# Valid conversion — box topology counts
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_valid_step_converts():
    """Adapter successfully converts the simple box STEP fixture."""
    model = _convert_box()
    assert isinstance(model, CanonicalTopologyModel)


@skip_if_no_ocp
def test_body_count():
    assert len(_convert_box().solids) == 1


@skip_if_no_ocp
def test_shell_count():
    assert len(_convert_box().shells) == 1


@skip_if_no_ocp
def test_face_count():
    assert len(_convert_box().faces) == 6


@skip_if_no_ocp
def test_wire_count():
    assert len(_convert_box().wires) == 6


@skip_if_no_ocp
def test_edge_count():
    # 12 unique edges on a box (deduplicated)
    assert len(_convert_box().edges) == 12


@skip_if_no_ocp
def test_vertex_count():
    # 8 unique vertices on a box (deduplicated)
    assert len(_convert_box().vertices) == 8


# ---------------------------------------------------------------------------
# Reference validation (CanonicalTopologyModel validates on construction)
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_no_dangling_references():
    """CanonicalTopologyModel construction succeeds, proving no dangling refs."""
    model = _convert_box()
    # If construction succeeded, all refs were valid (CanonicalTopologyModel validates)
    vertex_ids = {v.entity_id for v in model.vertices}
    edge_ids = {e.entity_id for e in model.edges}
    wire_ids = {w.entity_id for w in model.wires}
    face_ids = {f.entity_id for f in model.faces}
    shell_ids = {sh.entity_id for sh in model.shells}

    for edge in model.edges:
        assert edge.start_vertex_id in vertex_ids
        assert edge.end_vertex_id in vertex_ids

    for wire in model.wires:
        for eid in wire.edge_ids:
            assert eid in edge_ids

    for face in model.faces:
        assert face.outer_wire_id in wire_ids
        for wid in face.inner_wire_ids:
            assert wid in wire_ids

    for shell in model.shells:
        for fid in shell.face_ids:
            assert fid in face_ids

    for solid in model.solids:
        assert solid.outer_shell_id in shell_ids


@skip_if_no_ocp
def test_no_duplicate_ids():
    """All canonical IDs within each entity kind are unique."""
    model = _convert_box()
    for label, entities in (
        ("vertex", model.vertices),
        ("edge", model.edges),
        ("wire", model.wires),
        ("face", model.faces),
        ("shell", model.shells),
        ("solid", model.solids),
    ):
        ids = [e.entity_id for e in entities]
        assert len(ids) == len(set(ids)), f"duplicate {label} IDs: {ids}"


# ---------------------------------------------------------------------------
# Deterministic snapshot identity (3 repeated imports)
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_snapshot_identity_deterministic():
    """Three repeated imports of the same file produce identical snapshots."""
    source = _make_source("det-test-001")
    snapshots = []
    for _ in range(3):
        m = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(source)
        snapshots.append(
            (
                tuple(v.entity_id.value for v in m.vertices),
                tuple(
                    (e.entity_id.value, e.start_vertex_id.value, e.end_vertex_id.value)
                    for e in m.edges
                ),
                tuple(
                    (round(pt.x, 8), round(pt.y, 8), round(pt.z, 8))
                    for v in m.vertices
                    if (pt := v.point) is not None
                ),
            )
        )
    assert snapshots[0] == snapshots[1] == snapshots[2]


# ---------------------------------------------------------------------------
# Vertex geometry binding
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_all_vertices_have_point():
    """Every vertex in the box model has a finite Point3D binding."""
    model = _convert_box()
    for v in model.vertices:
        assert v.point is not None, f"{v.entity_id.value} has no point"
        assert math.isfinite(v.point.x)
        assert math.isfinite(v.point.y)
        assert math.isfinite(v.point.z)


@skip_if_no_ocp
def test_vertex_coordinates_span_box():
    """Vertex coordinates cover the expected 10×20×30 mm box extent."""
    model = _convert_box()
    xs = {round(v.point.x, 6) for v in model.vertices if v.point is not None}
    ys = {round(v.point.y, 6) for v in model.vertices if v.point is not None}
    zs = {round(v.point.z, 6) for v in model.vertices if v.point is not None}
    assert xs == {0.0, 10.0}
    assert ys == {0.0, 20.0}
    assert zs == {0.0, 30.0}


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_model_carries_source_identity():
    """The returned model's source field equals the SourceDocumentIdentity passed in."""
    source = _make_source("prov-test-001")
    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(source)
    assert model.source is source


@skip_if_no_ocp
def test_model_source_format_is_step():
    """Source format is CadFormat.STEP."""
    model = _convert_box()
    assert model.source is not None
    assert model.source.format == CadFormat.STEP


# ---------------------------------------------------------------------------
# Kernel object isolation
# ---------------------------------------------------------------------------


def _is_ocp_object(obj: Any) -> bool:
    """Return True if obj is an OCP type (by module prefix)."""
    t = type(obj)
    module = getattr(t, "__module__", "") or ""
    return module.startswith("OCP")


@skip_if_no_ocp
def test_no_ocp_objects_in_vertices():
    """No OCP objects are stored in topology vertices."""
    model = _convert_box()
    for v in model.vertices:
        assert not _is_ocp_object(v)
        pt = v.point
        if pt is not None:
            assert not _is_ocp_object(pt)
            assert not _is_ocp_object(pt.x)
            assert not _is_ocp_object(pt.y)
            assert not _is_ocp_object(pt.z)


@skip_if_no_ocp
def test_no_ocp_objects_in_edges():
    """No OCP objects are stored in topology edges."""
    model = _convert_box()
    for e in model.edges:
        assert not _is_ocp_object(e)
        assert not _is_ocp_object(e.entity_id)
        assert not _is_ocp_object(e.start_vertex_id)
        assert not _is_ocp_object(e.end_vertex_id)


@skip_if_no_ocp
def test_no_ocp_objects_in_model_source():
    """Model source identity contains no OCP objects."""
    model = _convert_box()
    assert not _is_ocp_object(model.source)


# ---------------------------------------------------------------------------
# No production STEP registration
# ---------------------------------------------------------------------------


def test_step_not_in_production_format_registry():
    """STEP format is NOT registered as a production supported format."""
    import origlyph.cad as cad_pkg

    # StepKernelAdapter must not be in the public cad package API
    assert not hasattr(cad_pkg, "StepKernelAdapter"), (
        "StepKernelAdapter was added to origlyph.cad.__init__ unexpectedly"
    )


def test_step_kernel_adapter_not_in_cad_all():
    """StepKernelAdapter is not in the origlyph.cad __all__ list."""
    import origlyph.cad as cad_pkg
    assert "StepKernelAdapter" not in cad_pkg.__all__
