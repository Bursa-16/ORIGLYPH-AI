"""Integration tests for the controlled STEP import (Stage 22E).

Exercises the complete controlled path:
  load_step_topology(path, source)
  → extension dispatch
  → StepKernelAdapter
  → OCP B-Rep traversal
  → CanonicalTopologyModel

All tests that require OCP are skipped when OCP is not installed.
"""
from __future__ import annotations

import gc
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.cad.step_loader import load_step_topology
from origlyph.cad.topology import CanonicalTopologyModel

OCP_PRESENT: bool = importlib.util.find_spec("OCP") is not None

skip_if_no_ocp = pytest.mark.skipif(
    not OCP_PRESENT, reason="OCP/cadquery-ocp-novtk not installed"
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"


def _make_source(
    source_id: str = "controlled-import-001",
    filename: str = "simple_box.step",
) -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename=filename,
        source_revision="stage-22e-v1",
    )


# ---------------------------------------------------------------------------
# H. Real STEP import proof
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_step_import_proof() -> None:
    """STEP fixture → load_step_topology → CanonicalTopologyModel (real kernel)."""
    source = _make_source()
    model = load_step_topology(SIMPLE_BOX_STEP, source)
    assert isinstance(model, CanonicalTopologyModel)


# ---------------------------------------------------------------------------
# I. Canonical topology returned
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_canonical_topology_solid_count() -> None:
    """Box imports as exactly one solid body."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.solids) == 1


@skip_if_no_ocp
def test_canonical_topology_shell_count() -> None:
    """Box has exactly one outer shell."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.shells) == 1


@skip_if_no_ocp
def test_canonical_topology_face_count() -> None:
    """Box has exactly six faces."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.faces) == 6


@skip_if_no_ocp
def test_canonical_topology_wire_count() -> None:
    """Box has exactly six wires (one outer wire per face)."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.wires) == 6


@skip_if_no_ocp
def test_canonical_topology_edge_count() -> None:
    """Box has exactly twelve unique edges."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.edges) == 12


@skip_if_no_ocp
def test_canonical_topology_vertex_count() -> None:
    """Box has exactly eight unique vertices."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert len(model.vertices) == 8


@skip_if_no_ocp
def test_canonical_topology_no_dangling_references() -> None:
    """CanonicalTopologyModel construction succeeds, proving no dangling refs."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
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
    for shell in model.shells:
        for fid in shell.face_ids:
            assert fid in face_ids
    for solid in model.solids:
        assert solid.outer_shell_id in shell_ids


# ---------------------------------------------------------------------------
# J. Deterministic repeated import
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_snapshot_identity_deterministic() -> None:
    """Three repeated calls to load_step_topology produce identical snapshots."""
    source = _make_source(source_id="det-import-001")
    snapshots = []
    for _ in range(3):
        model = load_step_topology(SIMPLE_BOX_STEP, source)
        snapshots.append(
            (
                tuple(v.entity_id.value for v in model.vertices),
                tuple(
                    (
                        e.entity_id.value,
                        e.start_vertex_id.value,
                        e.end_vertex_id.value,
                    )
                    for e in model.edges
                ),
            )
        )
    assert snapshots[0] == snapshots[1] == snapshots[2]


# ---------------------------------------------------------------------------
# K. Provenance preserved
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_provenance_source_identity_preserved() -> None:
    """model.source is the SourceDocumentIdentity passed to load_step_topology."""
    source = _make_source(source_id="prov-import-001")
    model = load_step_topology(SIMPLE_BOX_STEP, source)
    assert model.source is source


@skip_if_no_ocp
def test_provenance_format_is_step() -> None:
    """model.source.format is CadFormat.STEP."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    assert model.source is not None
    assert model.source.format is CadFormat.STEP


@skip_if_no_ocp
def test_provenance_original_filename_retained() -> None:
    """model.source.original_filename is preserved from the SourceDocumentIdentity."""
    source = _make_source(filename="simple_box.step")
    model = load_step_topology(SIMPLE_BOX_STEP, source)
    assert model.source is not None
    assert model.source.original_filename == "simple_box.step"


# ---------------------------------------------------------------------------
# L. Units preserved / normalized per contract
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_step_unit_contract_mm() -> None:
    """OCC delivers coordinates in millimeters; box extents match 10x20x30 mm."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    xs = {round(v.point.x, 6) for v in model.vertices if v.point is not None}
    ys = {round(v.point.y, 6) for v in model.vertices if v.point is not None}
    zs = {round(v.point.z, 6) for v in model.vertices if v.point is not None}
    assert xs == {0.0, 10.0}, f"unexpected X extents: {xs}"
    assert ys == {0.0, 20.0}, f"unexpected Y extents: {ys}"
    assert zs == {0.0, 30.0}, f"unexpected Z extents: {zs}"


@skip_if_no_ocp
def test_step_unit_system_declared_mm() -> None:
    """Source unit system declares mm length unit."""
    source = _make_source()
    model = load_step_topology(SIMPLE_BOX_STEP, source)
    assert model.source is not None
    assert model.source.unit_system.length_unit == "mm"


# ---------------------------------------------------------------------------
# M. No kernel-object leakage
# ---------------------------------------------------------------------------


def _is_ocp_object(obj: Any) -> bool:
    t = type(obj)
    module = getattr(t, "__module__", "") or ""
    return module.startswith("OCP")


@skip_if_no_ocp
def test_no_ocp_objects_in_vertices() -> None:
    """No OCP objects are stored in topology vertices."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    for v in model.vertices:
        assert not _is_ocp_object(v)
        if v.point is not None:
            assert not _is_ocp_object(v.point)
            assert not _is_ocp_object(v.point.x)


@skip_if_no_ocp
def test_no_ocp_objects_in_edges() -> None:
    """No OCP objects are stored in topology edges."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    for e in model.edges:
        assert not _is_ocp_object(e)
        assert not _is_ocp_object(e.entity_id)


@skip_if_no_ocp
def test_model_survives_gc() -> None:
    """CanonicalTopologyModel is fully usable after GC of OCP handles."""
    model = load_step_topology(SIMPLE_BOX_STEP, _make_source())
    gc.collect()
    assert len(model.solids) == 1
    shell_ids = {sh.entity_id for sh in model.shells}
    assert all(s.outer_shell_id in shell_ids for s in model.solids)


# ---------------------------------------------------------------------------
# .stp extension via load_step_topology
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_stp_extension_import(tmp_path: Path) -> None:
    """.stp file imports correctly through load_step_topology."""
    stp_file = tmp_path / "simple_box.stp"
    stp_file.write_bytes(SIMPLE_BOX_STEP.read_bytes())
    source = SourceDocumentIdentity(
        source_id="stp-import-001",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="simple_box.stp",
    )
    model = load_step_topology(stp_file, source)
    assert isinstance(model, CanonicalTopologyModel)
    assert len(model.solids) == 1


# ---------------------------------------------------------------------------
# E. Malformed STEP — fail closed
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_malformed_step_fail_closed(tmp_path: Path) -> None:
    """load_step_topology raises CadImportError for malformed STEP content."""
    from origlyph.cad.exceptions import CadImportError

    bad = tmp_path / "bad.step"
    bad.write_text(
        "THIS IS NOT A VALID STEP FILE CONTENT xyz 123 !@#", encoding="ascii"
    )
    source = SourceDocumentIdentity(
        source_id="malformed-step-001",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="bad.step",
    )
    with pytest.raises(CadImportError):
        load_step_topology(bad, source)


@skip_if_no_ocp
def test_empty_step_fail_closed(tmp_path: Path) -> None:
    """load_step_topology raises CadImportError for an empty file."""
    from origlyph.cad.exceptions import CadImportError

    empty = tmp_path / "empty.step"
    empty.write_text("", encoding="ascii")
    source = SourceDocumentIdentity(
        source_id="empty-step-001",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="empty.step",
    )
    with pytest.raises(CadImportError):
        load_step_topology(empty, source)
