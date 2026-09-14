"""Stage 16B project-model tests: serialization round-trips."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import cast

import pytest

from origlyph.project import (
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    OriglyphProject,
    ProjectMetadata,
    ToleranceState,
    build_project,
    project_from_dict,
    project_from_json,
    project_to_canonical_json,
    project_to_json,
)
from origlyph.project.exceptions import (
    InvalidProjectError,
    ProjectIntegrityError,
    UnsupportedProjectSchemaError,
)
from origlyph.project.models import PROJECT_SCHEMA_VERSION
from origlyph.project.persistence import load_project, save_project

_FP = hashlib.sha256(b"part").hexdigest()
_FP2 = hashlib.sha256(b"other").hexdigest()


def _full() -> OriglyphProject:
    return build_project(
        metadata=ProjectMetadata(name="demo", revision="r1"),
        cad_sources=(CadSourceReference(
            source_id="part.stl", format="stl", length_unit="mm",
            fingerprint=_FP, local_path_hint="D:/tmp/part.stl"),),
        datum_state=DatumState(frame_name="frame", assignments=(
            DatumRoleAssignment(role="TERTIARY", candidate_key="c"),
            DatumRoleAssignment(role="PRIMARY", candidate_key="a"),
            DatumRoleAssignment(role="SECONDARY", candidate_key="b",
                                bound_reference_key="ref-b"),
        )),
        tolerance_state=ToleranceState(
            chain_name="chain", configuration_fingerprint=_FP,
            result_identities=(_FP2,), summary_values={"span": 0.5}),
        artifact_refs={"audit": _FP2},
        extensions={"note": "v1-slot"})


def test_dict_round_trip() -> None:
    project = _full()
    assert project_from_dict(project.as_dict()) == project


def test_json_round_trip() -> None:
    project = _full()
    text = project_to_json(project)
    assert project_from_json(text) == project
    assert project_from_json(project.to_json()).project_id == (
        project.project_id)


def test_canonical_json_deterministic() -> None:
    project = _full()
    first = project_to_canonical_json(project)
    payload = json.loads(first)
    second = json.dumps(payload, sort_keys=True, allow_nan=False,
                        ensure_ascii=True, separators=(",", ":"))
    assert first == second


def test_save_load_round_trip(tmp_path: object) -> None:
    from pathlib import Path
    path = Path(str(tmp_path)) / "demo.origlyph.json"
    project = _full()
    save_project(project, path)
    first = path.read_text(encoding="utf-8")
    save_project(project, path)
    assert path.read_text(encoding="utf-8") == first
    assert load_project(path) == project


def test_input_not_mutated() -> None:
    project = _full()
    before = copy.deepcopy(project.as_dict())
    _ = project.as_dict()
    _ = project_to_json(project)
    _ = project_from_dict(project.as_dict())
    assert project.as_dict() == before


def test_malformed_json_rejected() -> None:
    with pytest.raises(InvalidProjectError):
        project_from_json("{not json")


def test_unknown_schema_rejected() -> None:
    project = _full()
    payload = project.as_dict()
    payload["schema_version"] = "origlyph.project.v99"
    with pytest.raises(UnsupportedProjectSchemaError):
        project_from_dict(payload)


def test_missing_field_rejected() -> None:
    payload = _full().as_dict()
    del payload["cad_sources"]
    with pytest.raises(InvalidProjectError):
        project_from_dict(payload)


def test_bad_type_rejected() -> None:
    payload = _full().as_dict()
    payload["cad_sources"] = "nope"
    with pytest.raises(InvalidProjectError):
        project_from_dict(payload)


def test_nonfinite_rejected() -> None:
    payload = _full().as_dict()
    tol_payload = cast(dict[str, object], payload["tolerance_state"])
    tol_payload["summary_values"] = {"span": float("inf")}
    with pytest.raises((InvalidProjectError, ProjectIntegrityError)):
        project_from_dict(payload)


def test_id_tamper_rejected() -> None:
    payload = _full().as_dict()
    payload["project_id"] = "0" * 64
    with pytest.raises(ProjectIntegrityError):
        project_from_dict(payload)


def test_stale_content_rejected() -> None:
    payload = _full().as_dict()
    datum_payload = cast(dict[str, object], payload["datum_state"])
    datum_payload["frame_name"] = "changed"
    with pytest.raises(ProjectIntegrityError):
        project_from_dict(payload)


def test_extra_key_rejected() -> None:
    payload = _full().as_dict()
    payload["surprise"] = 1
    with pytest.raises(InvalidProjectError):
        project_from_dict(payload)


def test_roles_preserved_explicit() -> None:
    project = project_from_dict(_full().as_dict())
    assert project.datum_state is not None
    assert [a.role for a in project.datum_state.assignments] == [
        "PRIMARY", "SECONDARY", "TERTIARY"]
    assert project.datum_state.assignments[1].bound_reference_key == "ref-b"


def test_refs_preserved() -> None:
    project = project_from_dict(_full().as_dict())
    assert project.cad_sources[0].source_id == "part.stl"
    assert project.cad_sources[0].local_path_hint == "D:/tmp/part.stl"
    assert project.tolerance_state is not None
    assert project.tolerance_state.chain_name == "chain"
    assert project.artifact_refs == {"audit": _FP2}
    assert project.metadata.name == "demo"


def test_schema_constant() -> None:
    assert PROJECT_SCHEMA_VERSION == "origlyph.project.v1"
