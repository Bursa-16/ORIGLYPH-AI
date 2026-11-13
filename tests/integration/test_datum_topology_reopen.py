"""Integration test: datum-to-topology binding reopen continuity (Stage 22G).

Proves the vertical slice:

  load_step_topology(simple_box.step, source)
  → CanonicalTopologyModel
  → select deterministic face
  → DatumTopologyRef
  → PRIMARY assignment
  → build_project / save_project
  → load_project
  → load_step_topology (same file, same source)
  → resolve_datum_topology_bindings
  → RESOLVED with same entity_id

Also proves that a byte-changed STEP copy produces UNRESOLVED_SOURCE_REVISION.

Skipped when OCP/cadquery-ocp-novtk is not installed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
from pathlib import Path

import pytest

from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.cad.step_loader import load_step_topology
from origlyph.project import (
    CadSourceReference,
    DatumState,
    build_project,
    load_project,
    save_project,
)
from origlyph.project.datum_topology_binding import (
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED_SOURCE_REVISION,
    DatumTopologyRef,
    datum_role_assignment_with_topology,
    decode_datum_topology_ref,
    is_topology_binding,
    resolve_datum_topology_bindings,
)

OCP_PRESENT: bool = importlib.util.find_spec("OCP") is not None

skip_if_no_ocp = pytest.mark.skipif(
    not OCP_PRESENT, reason="OCP/cadquery-ocp-novtk not installed"
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"


def _source(source_id: str = "reopen-test-001") -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="simple_box.step",
        source_revision="stage-22g-v1",
    )


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# A. Same-source reopen: binding resolves
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_same_source_reopen_binding_resolves() -> None:
    """Full vertical slice: bind face, save, reload, re-import, resolve."""
    source = _source()
    fp = _fingerprint(SIMPLE_BOX_STEP)

    # 1. First import — build topology
    topology_a = load_step_topology(SIMPLE_BOX_STEP, source)
    assert len(topology_a.faces) > 0, "simple_box.step must have at least one face"

    # 2. Select the first face deterministically
    first_face = topology_a.faces[0]
    face_entity_id = first_face.entity_id.value

    # 3. Build datum topology binding
    ref = DatumTopologyRef(
        source_fingerprint=fp,
        entity_kind="face",
        entity_id=face_entity_id,
    )
    assignment = datum_role_assignment_with_topology("PRIMARY", "top-face", ref)
    datum = DatumState(frame_name="DRF-reopen", assignments=(assignment,))

    cad_source = CadSourceReference(
        source_id=source.source_id,
        format="step",
        length_unit="mm",
        fingerprint=fp,
    )
    project = build_project(cad_sources=(cad_source,), datum_state=datum)

    # 4. Save and reload project
    with tempfile.TemporaryDirectory() as td:
        proj_file = Path(td) / "reopen.origlyph"
        save_project(project, proj_file)
        loaded_project = load_project(proj_file)

    assert loaded_project.project_id == project.project_id

    # 5. Verify bound_reference_key survived roundtrip
    loaded_assignments = loaded_project.datum_state.assignments  # type: ignore[union-attr]
    assert len(loaded_assignments) == 1
    key = loaded_assignments[0].bound_reference_key
    assert is_topology_binding(key)
    decoded_ref = decode_datum_topology_ref(key)  # type: ignore[arg-type]
    assert decoded_ref.entity_id == face_entity_id

    # 6. Re-import topology from same file
    topology_b = load_step_topology(SIMPLE_BOX_STEP, source)
    assert len(topology_b.faces) == len(topology_a.faces)

    # 7. Resolve binding
    resolutions = resolve_datum_topology_bindings(loaded_project, topology_b, fp)
    assert len(resolutions) == 1
    r = resolutions[0]
    assert r.status == RESOLUTION_RESOLVED, (
        f"Expected RESOLVED, got {r.status!r}. "
        f"Entity {face_entity_id!r} should exist in reloaded topology."
    )
    assert r.resolved_entity_id == face_entity_id


# ---------------------------------------------------------------------------
# B. Same topology is deterministic across two imports
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_same_step_file_deterministic_entity_ids() -> None:
    """Two imports of the same STEP produce the same face entity IDs."""
    source = _source("det-test-001")
    topo_1 = load_step_topology(SIMPLE_BOX_STEP, source)
    topo_2 = load_step_topology(SIMPLE_BOX_STEP, source)
    ids_1 = tuple(f.entity_id.value for f in topo_1.faces)
    ids_2 = tuple(f.entity_id.value for f in topo_2.faces)
    assert ids_1 == ids_2


# ---------------------------------------------------------------------------
# C. Changed source: binding is unresolved
# ---------------------------------------------------------------------------


@skip_if_no_ocp
def test_changed_source_binding_unresolved() -> None:
    """Byte-changed STEP copy → fingerprint mismatch → UNRESOLVED."""
    source = _source("revision-test-001")
    fp_original = _fingerprint(SIMPLE_BOX_STEP)

    topology_original = load_step_topology(SIMPLE_BOX_STEP, source)
    assert len(topology_original.faces) > 0
    first_face_id = topology_original.faces[0].entity_id.value

    ref = DatumTopologyRef(
        source_fingerprint=fp_original,
        entity_kind="face",
        entity_id=first_face_id,
    )
    assignment = datum_role_assignment_with_topology("PRIMARY", "original-face", ref)
    datum = DatumState(frame_name="DRF-rev", assignments=(assignment,))
    cad_source = CadSourceReference(
        source_id=source.source_id,
        format="step",
        length_unit="mm",
        fingerprint=fp_original,
    )
    project = build_project(cad_sources=(cad_source,), datum_state=datum)

    # Create a byte-changed copy (append a space to ASCII part of file).
    with tempfile.TemporaryDirectory() as td:
        changed_step = Path(td) / "changed.step"
        shutil.copy2(SIMPLE_BOX_STEP, changed_step)
        with open(changed_step, "ab") as f:
            f.write(b" ")  # minimal byte change

        fp_changed = _fingerprint(changed_step)
        assert fp_changed != fp_original, (
            "Byte-changed copy must have different fingerprint"
        )

        source_changed = _source("revision-test-001")
        topology_changed = load_step_topology(changed_step, source_changed)

    resolutions = resolve_datum_topology_bindings(project, topology_changed, fp_changed)
    assert len(resolutions) == 1
    assert resolutions[0].status == RESOLUTION_UNRESOLVED_SOURCE_REVISION, (
        "Changed source fingerprint must produce UNRESOLVED_SOURCE_REVISION"
    )
