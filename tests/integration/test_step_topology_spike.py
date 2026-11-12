"""Integration test for the Stage 22D STEP/B-Rep topology spike.

Exercises the complete path:
  STEP file → OCP B-Rep → CanonicalTopologyModel → Stage 22C validation

This test is integration-level because it performs real STEP file I/O via
the OCP kernel.  All tests are skipped when OCP is not installed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from origlyph.cad.identity import (
    CadFormat,
    SourceDocumentIdentity,
    SourceUnitSystem,
)
from origlyph.cad.step_kernel_adapter import StepKernelAdapter
from origlyph.cad.topology import CanonicalTopologyModel
from origlyph.cad.topology_adapter import CadTopologyAdapter

OCP_PRESENT = importlib.util.find_spec("OCP") is not None

skip_if_no_ocp = pytest.mark.skipif(
    not OCP_PRESENT,
    reason="OCP/cadquery-ocp-novtk not installed",
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"


def _make_source() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="integration-box-001",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="simple_box.step",
        source_revision="spike-v1",
    )


@skip_if_no_ocp
def test_adapter_satisfies_protocol():
    """StepKernelAdapter is structurally compatible with CadTopologyAdapter."""
    adapter = StepKernelAdapter(SIMPLE_BOX_STEP)
    assert isinstance(adapter, CadTopologyAdapter)


@skip_if_no_ocp
def test_full_step_to_canonical_topology():
    """Full end-to-end: STEP file → OCP → CanonicalTopologyModel."""
    source = _make_source()
    adapter = StepKernelAdapter(SIMPLE_BOX_STEP)
    model = adapter.to_canonical_topology(source)
    assert isinstance(model, CanonicalTopologyModel)
    # Box topology invariants
    assert len(model.solids) == 1
    assert len(model.shells) == 1
    assert len(model.faces) == 6
    assert len(model.wires) == 6
    assert len(model.edges) == 12
    assert len(model.vertices) == 8


@skip_if_no_ocp
def test_canonical_model_validates_successfully():
    """CanonicalTopologyModel construction (which validates) does not raise."""
    # Construction raises on duplicate IDs or dangling refs; getting here = PASS
    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(_make_source())
    assert model is not None


@skip_if_no_ocp
def test_brep_traversal_hierarchy_is_real():
    """B-Rep hierarchy is correctly captured: solid→shell→face→wire→edge→vertex."""
    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(_make_source())
    solid = model.solids[0]
    shell = next(s for s in model.shells if s.entity_id == solid.outer_shell_id)
    assert len(shell.face_ids) == 6

    all_wire_ids_via_faces = set()
    all_edge_ids_via_wires = set()
    all_vertex_ids_via_edges = set()

    for fid in shell.face_ids:
        face = next(f for f in model.faces if f.entity_id == fid)
        all_wire_ids_via_faces.add(face.outer_wire_id)
        wire = next(w for w in model.wires if w.entity_id == face.outer_wire_id)
        for eid in wire.edge_ids:
            all_edge_ids_via_wires.add(eid)
            edge = next(e for e in model.edges if e.entity_id == eid)
            all_vertex_ids_via_edges.add(edge.start_vertex_id)
            all_vertex_ids_via_edges.add(edge.end_vertex_id)

    assert len(all_wire_ids_via_faces) == 6
    assert len(all_edge_ids_via_wires) == 12
    assert len(all_vertex_ids_via_edges) == 8


@skip_if_no_ocp
def test_adjacency_helpers_work():
    """Stage 22C adjacency helpers return consistent results for STEP topology."""
    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(_make_source())
    # Every edge should be reachable from at least one wire
    for edge in model.edges:
        wires = model.wires_for_edge(edge.entity_id)
        assert len(wires) >= 1, f"edge {edge.entity_id.value} unreachable from wires"
    # Every vertex should be reachable from at least one edge
    for vertex in model.vertices:
        edges = model.edges_for_vertex(vertex.entity_id)
        vid = vertex.entity_id.value
        assert len(edges) >= 1, f"vertex {vid} unreachable from edges"


@skip_if_no_ocp
def test_step_unit_handling_known():
    """OCC delivers vertex coordinates in millimeters (documented known behavior)."""
    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(_make_source())
    xs = {round(v.point.x, 6) for v in model.vertices if v.point is not None}
    ys = {round(v.point.y, 6) for v in model.vertices if v.point is not None}
    zs = {round(v.point.z, 6) for v in model.vertices if v.point is not None}
    # The box was created as 10×20×30 mm; OCC delivers in mm → values match
    assert xs == {0.0, 10.0}, f"unexpected X extents: {xs}"
    assert ys == {0.0, 20.0}, f"unexpected Y extents: {ys}"
    assert zs == {0.0, 30.0}, f"unexpected Z extents: {zs}"


@skip_if_no_ocp
def test_model_survives_without_kernel_handles():
    """CanonicalTopologyModel is fully usable without any live OCP handles."""
    import gc

    model = StepKernelAdapter(SIMPLE_BOX_STEP).to_canonical_topology(_make_source())
    # Force garbage collection to release any lingering OCP objects
    gc.collect()
    # Model should still be fully traversable
    solid_ids = {s.entity_id for s in model.solids}
    shell_ids = {sh.entity_id for sh in model.shells}
    assert all(s.outer_shell_id in shell_ids for s in model.solids)
    assert len(solid_ids) == 1


@skip_if_no_ocp
def test_no_production_step_support():
    """CadFormat.STEP is defined but no production importer is registered."""
    assert CadFormat.STEP == CadFormat.STEP  # enum member exists
    # No production path: StepKernelAdapter is not in public cad API
    import origlyph.cad as cad_pkg
    assert not hasattr(cad_pkg, "StepKernelAdapter")
