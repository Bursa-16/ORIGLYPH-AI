"""Stage 22F tests: STEP source reference bridge and project reopen continuity.

Tests cover:
  cad_source_reference_from_step(
      source, path, *, expected_fingerprint, local_path_hint)
  project_with_step_source(
      project, source, path, *, expected_fingerprint, local_path_hint)

Bridge does not require OCP.  Topology is not persisted.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.project import (
    CadSourceReference,
    InvalidProjectError,
    build_project,
    cad_source_reference_from_step,
    load_project,
    project_with_step_source,
    save_project,
)
from origlyph.project.models import PROJECT_SCHEMA_VERSION

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"

OCP_PRESENT: bool = importlib.util.find_spec("OCP") is not None


def _step_source(
    source_id: str = "bridge-test-001",
    filename: str = "simple_box.step",
) -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename=filename,
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Valid .step extension accepted
# ---------------------------------------------------------------------------


def test_step_extension_accepted() -> None:
    """.step extension builds a CadSourceReference without error."""
    ref = cad_source_reference_from_step(_step_source(), SIMPLE_BOX_STEP)
    assert isinstance(ref, CadSourceReference)


# ---------------------------------------------------------------------------
# 2. Valid .stp extension accepted
# ---------------------------------------------------------------------------


def test_stp_extension_accepted(tmp_path: Path) -> None:
    """.stp extension is accepted and produces a CadSourceReference."""
    stp = tmp_path / "box.stp"
    stp.write_bytes(SIMPLE_BOX_STEP.read_bytes())
    source = _step_source(filename="box.stp")
    ref = cad_source_reference_from_step(source, stp)
    assert isinstance(ref, CadSourceReference)


# ---------------------------------------------------------------------------
# 3. Extension normalization — upper-case .STEP
# ---------------------------------------------------------------------------


def test_step_extension_uppercase(tmp_path: Path) -> None:
    """.STEP (upper-case) is accepted via case-insensitive normalization."""
    f = tmp_path / "BOX.STEP"
    f.write_bytes(SIMPLE_BOX_STEP.read_bytes())
    source = _step_source(filename="BOX.STEP")
    ref = cad_source_reference_from_step(source, f)
    assert isinstance(ref, CadSourceReference)


# ---------------------------------------------------------------------------
# 4. Extension normalization — upper-case .STP
# ---------------------------------------------------------------------------


def test_stp_extension_uppercase(tmp_path: Path) -> None:
    """.STP (upper-case) is accepted via case-insensitive normalization."""
    f = tmp_path / "BOX.STP"
    f.write_bytes(SIMPLE_BOX_STEP.read_bytes())
    source = _step_source(filename="BOX.STP")
    ref = cad_source_reference_from_step(source, f)
    assert isinstance(ref, CadSourceReference)


# ---------------------------------------------------------------------------
# 5. Deterministic SHA-256 fingerprint
# ---------------------------------------------------------------------------


def test_sha256_fingerprint_deterministic() -> None:
    """Fingerprint is a 64-char hex string matching sha256 of file bytes."""
    ref = cad_source_reference_from_step(_step_source(), SIMPLE_BOX_STEP)
    assert len(ref.fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in ref.fingerprint)
    assert ref.fingerprint == _sha256_file(SIMPLE_BOX_STEP)


# ---------------------------------------------------------------------------
# 6. Repeated calls produce same fingerprint
# ---------------------------------------------------------------------------


def test_repeated_calls_same_fingerprint() -> None:
    """Three calls on the same file produce identical fingerprints."""
    fps = [
        cad_source_reference_from_step(
            _step_source(source_id=f"r{i}"), SIMPLE_BOX_STEP
        ).fingerprint
        for i in range(3)
    ]
    assert fps[0] == fps[1] == fps[2]


# ---------------------------------------------------------------------------
# 7. Same bytes, different path → same fingerprint
# ---------------------------------------------------------------------------


def test_same_bytes_different_path_same_fingerprint(tmp_path: Path) -> None:
    """Copying bytes to a different path produces the same fingerprint."""
    copy = tmp_path / "copy.step"
    copy.write_bytes(SIMPLE_BOX_STEP.read_bytes())
    ref_orig = cad_source_reference_from_step(
        _step_source(source_id="orig"), SIMPLE_BOX_STEP
    )
    ref_copy = cad_source_reference_from_step(_step_source(source_id="copy"), copy)
    assert ref_orig.fingerprint == ref_copy.fingerprint


# ---------------------------------------------------------------------------
# 8. Different bytes → different fingerprint
# ---------------------------------------------------------------------------


def test_different_bytes_different_fingerprint(tmp_path: Path) -> None:
    """Different file content produces a different fingerprint."""
    other = tmp_path / "other.step"
    other.write_bytes(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    ref_box = cad_source_reference_from_step(
        _step_source(source_id="box"), SIMPLE_BOX_STEP
    )
    ref_other = cad_source_reference_from_step(
        _step_source(source_id="other"), other
    )
    assert ref_box.fingerprint != ref_other.fingerprint


# ---------------------------------------------------------------------------
# 9. local_path_hint excluded from identity
# ---------------------------------------------------------------------------


def test_local_path_hint_excluded_from_identity() -> None:
    """local_path_hint does not affect fingerprint or format/unit fields."""
    ref_no_hint = cad_source_reference_from_step(
        _step_source(), SIMPLE_BOX_STEP, local_path_hint=None
    )
    ref_with_hint = cad_source_reference_from_step(
        _step_source(), SIMPLE_BOX_STEP, local_path_hint="/mnt/cad/box.step"
    )
    assert ref_no_hint.fingerprint == ref_with_hint.fingerprint
    assert ref_no_hint.identity_dict() == ref_with_hint.identity_dict()
    assert ref_with_hint.local_path_hint == "/mnt/cad/box.step"


# ---------------------------------------------------------------------------
# 10. Correct caller-supplied fingerprint passes
# ---------------------------------------------------------------------------


def test_correct_caller_fingerprint_passes() -> None:
    """When expected_fingerprint matches the file, no error is raised."""
    correct_fp = _sha256_file(SIMPLE_BOX_STEP)
    ref = cad_source_reference_from_step(
        _step_source(), SIMPLE_BOX_STEP, expected_fingerprint=correct_fp
    )
    assert ref.fingerprint == correct_fp


# ---------------------------------------------------------------------------
# 11. Fingerprint mismatch raises
# ---------------------------------------------------------------------------


def test_fingerprint_mismatch_raises() -> None:
    """When expected_fingerprint does not match file content, raise."""
    wrong_fp = hashlib.sha256(b"wrong").hexdigest()
    with pytest.raises(InvalidProjectError, match="mismatch"):
        cad_source_reference_from_step(
            _step_source(), SIMPLE_BOX_STEP, expected_fingerprint=wrong_fp
        )


# ---------------------------------------------------------------------------
# 12. Invalid fingerprint format raises
# ---------------------------------------------------------------------------


def test_invalid_fingerprint_format_raises() -> None:
    """Non-sha256-hex expected_fingerprint raises with format error."""
    with pytest.raises(InvalidProjectError, match="64-character"):
        cad_source_reference_from_step(
            _step_source(), SIMPLE_BOX_STEP, expected_fingerprint="not-a-sha256"
        )


# ---------------------------------------------------------------------------
# 13. Unsupported extension raises
# ---------------------------------------------------------------------------


def test_unsupported_extension_raises() -> None:
    """.stl extension raises InvalidProjectError (fail closed)."""
    source = SourceDocumentIdentity(
        source_id="stl-attempt",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="part.stl",
    )
    with pytest.raises(InvalidProjectError):
        cad_source_reference_from_step(source, Path("part.stl"))


# ---------------------------------------------------------------------------
# 14. Non-STEP CadFormat raises
# ---------------------------------------------------------------------------


def test_non_step_cad_format_raises(tmp_path: Path) -> None:
    """source.format != CadFormat.STEP raises InvalidProjectError."""
    f = tmp_path / "part.step"
    f.write_bytes(b"")
    source = SourceDocumentIdentity(
        source_id="stl-source",
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="part.step",
    )
    with pytest.raises(InvalidProjectError, match="CadFormat.STEP"):
        cad_source_reference_from_step(source, f)


# ---------------------------------------------------------------------------
# 15. Missing file raises
# ---------------------------------------------------------------------------


def test_missing_file_raises() -> None:
    """Non-existent file raises InvalidProjectError with 'not found'."""
    with pytest.raises(InvalidProjectError, match="not found"):
        cad_source_reference_from_step(
            _step_source(), FIXTURE_DIR / "does_not_exist.step"
        )


# ---------------------------------------------------------------------------
# 16. Insertion into project
# ---------------------------------------------------------------------------


def test_step_source_inserts_into_project() -> None:
    """project_with_step_source returns a new project with the STEP source."""
    base = build_project()
    result = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    assert len(result.cad_sources) == 1
    assert result.cad_sources[0].format == "step"
    assert result.cad_sources[0].source_id == "bridge-test-001"


# ---------------------------------------------------------------------------
# 17. Duplicate same fingerprint — idempotent
# ---------------------------------------------------------------------------


def test_duplicate_same_fingerprint_idempotent() -> None:
    """Adding the same STEP source twice returns the project unchanged."""
    base = build_project()
    once = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    twice = project_with_step_source(once, _step_source(), SIMPLE_BOX_STEP)
    assert twice.project_id == once.project_id
    assert len(twice.cad_sources) == 1


# ---------------------------------------------------------------------------
# 18. Duplicate different fingerprint raises
# ---------------------------------------------------------------------------


def test_duplicate_different_fingerprint_raises(tmp_path: Path) -> None:
    """Same source_id but different file content raises InvalidProjectError."""
    other = tmp_path / "other.step"
    other.write_bytes(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    base = build_project()
    once = project_with_step_source(
        base, _step_source(source_id="shared-id"), SIMPLE_BOX_STEP
    )
    with pytest.raises(InvalidProjectError, match="different fingerprint"):
        project_with_step_source(once, _step_source(source_id="shared-id"), other)


# ---------------------------------------------------------------------------
# 19. Existing project state preserved
# ---------------------------------------------------------------------------


def test_existing_project_state_preserved() -> None:
    """project_with_step_source preserves metadata and existing cad_sources."""
    from origlyph.project import ProjectMetadata

    meta = ProjectMetadata(name="TestPart", revision="rev1")
    base = build_project(metadata=meta)
    result = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    assert result.metadata.name == "TestPart"
    assert result.metadata.revision == "rev1"
    assert result.datum_state is None
    assert result.tolerance_state is None
    assert result.schema_version == PROJECT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 20. Project_id deterministic
# ---------------------------------------------------------------------------


def test_project_id_deterministic() -> None:
    """Same source + same file bytes → same project_id on two calls."""
    base = build_project()
    p1 = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    p2 = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    assert p1.project_id == p2.project_id


# ---------------------------------------------------------------------------
# 21. Authoritative source change changes project_id
# ---------------------------------------------------------------------------


def test_authoritative_source_change_changes_project_id(tmp_path: Path) -> None:
    """Different file bytes → different fingerprint → different project_id."""
    other = tmp_path / "other.step"
    other.write_bytes(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    base = build_project()
    p_box = project_with_step_source(
        base, _step_source(source_id="part"), SIMPLE_BOX_STEP
    )
    p_other = project_with_step_source(
        base, _step_source(source_id="part"), other
    )
    assert p_box.project_id != p_other.project_id


# ---------------------------------------------------------------------------
# 22. Save/load round-trip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path) -> None:
    """save_project + load_project preserves the STEP source reference."""
    project_file = tmp_path / "test.origlyph"
    base = build_project()
    p = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    save_project(p, project_file)
    loaded = load_project(project_file)
    assert loaded.project_id == p.project_id
    assert len(loaded.cad_sources) == 1
    assert loaded.cad_sources[0].source_id == p.cad_sources[0].source_id
    assert loaded.cad_sources[0].fingerprint == p.cad_sources[0].fingerprint


# ---------------------------------------------------------------------------
# 23. Project_id stable after reopen
# ---------------------------------------------------------------------------


def test_project_id_stable_after_reopen(tmp_path: Path) -> None:
    """project_id is identical before save and after load."""
    project_file = tmp_path / "reopen.origlyph"
    base = build_project()
    p = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    original_id = p.project_id
    save_project(p, project_file)
    loaded = load_project(project_file)
    assert loaded.project_id == original_id


# ---------------------------------------------------------------------------
# 24. Schema remains v1
# ---------------------------------------------------------------------------


def test_schema_remains_v1(tmp_path: Path) -> None:
    """schema_version is origlyph.project.v1 after STEP source insertion."""
    base = build_project()
    p = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    assert p.schema_version == "origlyph.project.v1"
    project_file = tmp_path / "schema.origlyph"
    save_project(p, project_file)
    raw = json.loads(project_file.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "origlyph.project.v1"


# ---------------------------------------------------------------------------
# 25. CanonicalTopologyModel absent from JSON
# ---------------------------------------------------------------------------


def test_topology_absent_from_json(tmp_path: Path) -> None:
    """Serialized project JSON contains no topology or OCP references."""
    project_file = tmp_path / "topo.origlyph"
    base = build_project()
    p = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    save_project(p, project_file)
    text = project_file.read_text(encoding="utf-8")
    for banned in (
        "CanonicalTopologyModel",
        "TopologyVertex",
        "TopologyEdge",
        "TopologyFace",
        "TopologyShell",
        "TopologySolid",
        "TopologyWire",
        "OCP",
        "kernel",
    ):
        assert banned not in text, f"banned token {banned!r} found in project JSON"


# ---------------------------------------------------------------------------
# 26. OCP objects absent from project state
# ---------------------------------------------------------------------------


def test_ocp_absent_from_project_state() -> None:
    """No OCP module objects appear in cad_sources after STEP source bridge."""
    base = build_project()
    p = project_with_step_source(base, _step_source(), SIMPLE_BOX_STEP)
    for ref in p.cad_sources:
        module = getattr(type(ref), "__module__", "") or ""
        assert not module.startswith("OCP")


# ---------------------------------------------------------------------------
# 27. Bridge does not require OCP
# ---------------------------------------------------------------------------


def test_bridge_does_not_require_ocp() -> None:
    """cad_source_reference_from_step executes without an OCP/kernel import."""
    import origlyph.project.cad_source_bridge as bridge_mod

    source_mods = [m for m in dir(bridge_mod) if m.startswith("OCP")]
    assert source_mods == [], f"unexpected OCP symbols in bridge: {source_mods}"
    ref = cad_source_reference_from_step(_step_source(), SIMPLE_BOX_STEP)
    assert isinstance(ref, CadSourceReference)


# ---------------------------------------------------------------------------
# Serialization proof (Section 31 of the spec)
# ---------------------------------------------------------------------------


def test_serialization_proof(tmp_path: Path) -> None:
    """Representative project serializes with all required/absent fields."""
    project_file = tmp_path / "proof.origlyph"
    base = build_project()
    p = project_with_step_source(
        base,
        _step_source(source_id="proof-001"),
        SIMPLE_BOX_STEP,
        local_path_hint="simple_box.step",
    )
    save_project(p, project_file)
    raw = json.loads(project_file.read_text(encoding="utf-8"))

    assert raw["schema_version"] == "origlyph.project.v1"
    assert len(raw["cad_sources"]) == 1
    src = raw["cad_sources"][0]
    assert src["source_id"] == "proof-001"
    assert src["format"] == "step"
    assert len(src["fingerprint"]) == 64
    assert all(c in "0123456789abcdef" for c in src["fingerprint"])
    assert "CanonicalTopologyModel" not in json.dumps(raw)
    assert "OCP" not in json.dumps(raw)
