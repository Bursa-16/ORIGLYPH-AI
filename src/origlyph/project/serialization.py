"""Deterministic project serialization v1 (Stage 16B)."""

from __future__ import annotations

import copy
import json
from typing import Any

from .exceptions import (
    InvalidProjectError,
    ProjectIntegrityError,
    UnsupportedProjectSchemaError,
)
from .models import (
    PROJECT_SCHEMA_VERSION,
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    OriglyphProject,
    ProjectMetadata,
    ToleranceState,
    _canonical_json,
)

__all__ = ["project_from_dict", "project_to_json"]
__all__ += ["project_to_canonical_json", "project_from_json"]


def _req_dict(v: object, *, name: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise InvalidProjectError(f"{name} must be a dict")
    return v


def _exact_keys(d: dict[str, Any], req: set[str], *, name: str) -> None:
    if set(d) != req:
        raise InvalidProjectError(
            f"{name} keys invalid; missing={sorted(req - set(d))}, "
            f"unknown={sorted(set(d) - req)}")


def _parse_metadata(v: object) -> ProjectMetadata:
    d = _req_dict(v, name="metadata")
    _exact_keys(d, {"name", "description", "revision", "local_path_hint",
                    "extra"}, name="metadata")
    extra = {} if d["extra"] is None else d["extra"]
    try:
        return ProjectMetadata(name=d["name"], description=d["description"],
                               revision=d["revision"],
                               local_path_hint=d["local_path_hint"],
                               extra=extra)
    except (TypeError, ValueError) as exc:
        raise InvalidProjectError(f"invalid metadata: {exc}") from exc


def _parse_cad(v: object) -> CadSourceReference:
    d = _req_dict(v, name="cad source")
    _exact_keys(d, {"source_id", "format", "length_unit", "fingerprint",
                    "local_path_hint"}, name="cad source")
    try:
        return CadSourceReference(source_id=d["source_id"],
                                  format=d["format"],
                                  length_unit=d["length_unit"],
                                  fingerprint=d["fingerprint"],
                                  local_path_hint=d["local_path_hint"])
    except (TypeError, ValueError) as exc:
        raise InvalidProjectError(f"invalid cad source: {exc}") from exc

def _parse_datum(v: object) -> DatumState | None:
    if v is None:
        return None
    d = _req_dict(v, name="datum_state")
    _exact_keys(d, {"frame_name", "assignments"}, name="datum_state")
    raw = d["assignments"]
    if not isinstance(raw, list):
        raise InvalidProjectError("datum assignments must be a list")
    items = []
    for e in raw:
        ed = _req_dict(e, name="datum assignment")
        _exact_keys(ed, {"role", "candidate_key",
                         "bound_reference_key"}, name="datum assignment")
        try:
            items.append(DatumRoleAssignment(
                role=ed["role"], candidate_key=ed["candidate_key"],
                bound_reference_key=ed["bound_reference_key"]))
        except (TypeError, ValueError) as exc:
            raise InvalidProjectError(
                f"invalid datum assignment: {exc}") from exc
    try:
        return DatumState(frame_name=d["frame_name"],
                          assignments=tuple(items))
    except (TypeError, ValueError) as exc:
        raise InvalidProjectError(f"invalid datum_state: {exc}") from exc


def _parse_tol(v: object) -> ToleranceState | None:
    if v is None:
        return None
    d = _req_dict(v, name="tolerance_state")
    _exact_keys(d, {"chain_name", "configuration_fingerprint",
                    "result_identities", "summary_values"},
                name="tolerance_state")
    if not isinstance(d["result_identities"], list):
        raise InvalidProjectError("tolerance result ids must be a list")
    if not isinstance(d["summary_values"], dict):
        raise InvalidProjectError("tolerance summary must be a dict")
    try:
        return ToleranceState(
            chain_name=d["chain_name"],
            configuration_fingerprint=d["configuration_fingerprint"],
            result_identities=tuple(d["result_identities"]),
            summary_values=dict(d["summary_values"]))
    except (TypeError, ValueError) as exc:
        raise InvalidProjectError(f"invalid tolerance_state: {exc}") from exc


def project_from_dict(payload: object) -> OriglyphProject:
    data = _req_dict(payload, name="project")
    _exact_keys(data, {"schema_version", "project_id", "metadata",
                       "cad_sources", "datum_state", "tolerance_state",
                       "artifact_refs", "extensions"}, name="project")
    if data["schema_version"] != PROJECT_SCHEMA_VERSION:
        raise UnsupportedProjectSchemaError(
            f"unsupported project schema {data['schema_version']!r}")
    raw_sources = data["cad_sources"]
    if not isinstance(raw_sources, list):
        raise InvalidProjectError("cad_sources must be a list")
    sources = tuple(_parse_cad(e) for e in raw_sources)
    refs = dict(_req_dict(data["artifact_refs"], name="artifact_refs"))
    ext = copy.deepcopy(_req_dict(data["extensions"], name="extensions"))
    _canonical_json(ext, context="project extensions")
    stored = data["project_id"]
    if not isinstance(stored, str):
        raise InvalidProjectError("project_id must be a str")
    try:
        return OriglyphProject(
            schema_version=PROJECT_SCHEMA_VERSION, project_id=stored,
            metadata=_parse_metadata(data["metadata"]), cad_sources=sources,
            datum_state=_parse_datum(data["datum_state"]),
            tolerance_state=_parse_tol(data["tolerance_state"]),
            artifact_refs=refs, extensions=ext)
    except UnsupportedProjectSchemaError:
        raise
    except InvalidProjectError as exc:
        raise ProjectIntegrityError(str(exc)) from exc


def project_to_canonical_json(project: OriglyphProject) -> str:
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    return _canonical_json(project.as_dict(), context="origlyph project")


def project_to_json(project: OriglyphProject) -> str:
    return project_to_canonical_json(project)


def project_from_json(text: object) -> OriglyphProject:
    if not isinstance(text, str):
        raise InvalidProjectError("project JSON must be a str")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidProjectError(f"project JSON malformed: {exc}") from exc
    return project_from_dict(payload)

