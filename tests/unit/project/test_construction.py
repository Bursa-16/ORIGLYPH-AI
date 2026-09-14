"""Stage 16B project-model tests: construction and identity."""

from __future__ import annotations

import hashlib
import json

import pytest

from origlyph.project import (
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    ProjectMetadata,
    ToleranceState,
    build_project,
)
from origlyph.project.exceptions import InvalidProjectError

_FP = hashlib.sha256(b"part").hexdigest()
_FP2 = hashlib.sha256(b"other").hexdigest()


def _cad(**kwargs: object) -> CadSourceReference:
    base: dict[str, object] = {"source_id": "part.stl", "format": "stl",
                               "length_unit": "mm", "fingerprint": _FP}
    base.update(kwargs)
    return CadSourceReference(**base)  # type: ignore[arg-type]


def _datum() -> DatumState:
    return DatumState(frame_name="frame", assignments=(
        DatumRoleAssignment(role="PRIMARY", candidate_key="a"),
        DatumRoleAssignment(role="SECONDARY", candidate_key="b"),
        DatumRoleAssignment(role="TERTIARY", candidate_key="c"),
    ))


def _tol() -> ToleranceState:
    return ToleranceState(chain_name="chain",
                          configuration_fingerprint=_FP,
                          result_identities=(_FP2,),
                          summary_values={"span": 0.5})


def test_construction_minimal() -> None:
    project = build_project()
    assert project.project_id and len(project.project_id) == 64
    assert project.datum_state is None


def test_invalid_cad_fingerprint() -> None:
    with pytest.raises(InvalidProjectError):
        _cad(fingerprint="nope")


def test_deterministic_id_same_input() -> None:
    first = build_project(cad_sources=(_cad(),), datum_state=_datum(),
                          tolerance_state=_tol())
    second = build_project(cad_sources=(_cad(),), datum_state=_datum(),
                           tolerance_state=_tol())
    assert first.project_id == second.project_id
    assert first == second


def test_content_change_changes_id() -> None:
    first = build_project(cad_sources=(_cad(),))
    second = build_project(cad_sources=(_cad(fingerprint=_FP2),))
    assert first.project_id != second.project_id


def test_metadata_excluded_from_id() -> None:
    first = build_project(cad_sources=(_cad(),),
                          metadata=ProjectMetadata(name="one"))
    second = build_project(cad_sources=(_cad(),),
                           metadata=ProjectMetadata(name="two"))
    assert first.project_id == second.project_id


def test_local_path_excluded_from_id() -> None:
    first = build_project(cad_sources=(_cad(),))
    second = build_project(
        cad_sources=(_cad(local_path_hint="D:/tmp/part.stl"),))
    assert first.project_id == second.project_id
    assert first != second


def test_duplicate_roles_rejected() -> None:
    with pytest.raises(InvalidProjectError):
        DatumState(frame_name="f", assignments=(
            DatumRoleAssignment(role="PRIMARY", candidate_key="a"),
            DatumRoleAssignment(role="PRIMARY", candidate_key="b"),
        ))


def test_bad_role_rejected() -> None:
    with pytest.raises(InvalidProjectError):
        DatumRoleAssignment(role="QUATERNARY", candidate_key="a")


def test_nonfinite_summary_rejected() -> None:
    with pytest.raises(InvalidProjectError):
        ToleranceState(chain_name="c", configuration_fingerprint=_FP,
                       summary_values={"span": float("nan")})


def test_immutable_snapshot() -> None:
    import dataclasses

    project = build_project(cad_sources=(_cad(),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        project.project_id = "x"  # type: ignore[misc]
    _ = json.dumps(project.as_dict())
