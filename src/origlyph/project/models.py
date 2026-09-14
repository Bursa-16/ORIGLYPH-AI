"""Deterministic project models v1 (Stage 16B)."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from .exceptions import InvalidProjectError

__all__ = ["PROJECT_SCHEMA_VERSION", "ProjectMetadata", "CadSourceReference"]
__all__ += ["DatumRoleAssignment", "DatumState", "ToleranceState"]
__all__ += ["OriglyphProject", "build_project"]

PROJECT_SCHEMA_VERSION = "origlyph.project.v1"
_VALID_ROLES = ("PRIMARY", "SECONDARY", "TERTIARY")


def _canonical_json(payload: object, *, context: str) -> str:
    try:
        return json.dumps(payload, sort_keys=True, allow_nan=False,
                          ensure_ascii=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise InvalidProjectError(
            f"{context} is not finite canonical JSON: {exc}") from exc


def _fingerprint(payload: object, *, context: str) -> str:
    return hashlib.sha256(
        _canonical_json(payload, context=context).encode("utf-8")).hexdigest()


def _req_str(v: object, *, name: str) -> str:
    if not isinstance(v, str) or not v:
        raise InvalidProjectError(f"{name} must be a non-empty str")
    return v


def _req_num(v: object, *, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise InvalidProjectError(f"{name} must be numeric")
    if not math.isfinite(v):
        raise InvalidProjectError(f"{name} must be finite")
    return float(v)


def _is_sha(v: object) -> bool:
    return (isinstance(v, str) and len(v) == 64
            and all(c in "0123456789abcdef" for c in v))


def _freeze_map(v: object) -> dict[str, Any]:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise InvalidProjectError("mapping field must be a dict")
    out = copy.deepcopy(v)
    _canonical_json(out, context="mapping field")
    return out

@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    """Descriptive metadata only; excluded from project_id."""

    name: str | None = None
    description: str | None = None
    revision: str | None = None
    local_path_hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for fname in ("name", "description", "revision", "local_path_hint"):
            val = getattr(self, fname)
            if val is not None and not isinstance(val, str):
                raise InvalidProjectError(f"metadata.{fname} must be str or None")
        object.__setattr__(self, "extra", _freeze_map(self.extra))

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "description": self.description,
                "revision": self.revision,
                "local_path_hint": self.local_path_hint,
                "extra": copy.deepcopy(self.extra)}

@dataclass(frozen=True, slots=True)
class CadSourceReference:
    """Logical CAD source ref; local_path_hint excluded from identity."""

    source_id: str
    format: str
    length_unit: str
    fingerprint: str
    local_path_hint: str | None = None

    def __post_init__(self) -> None:
        _req_str(self.source_id, name="cad source source_id")
        _req_str(self.format, name="cad source format")
        _req_str(self.length_unit, name="cad source length_unit")
        if not _is_sha(self.fingerprint):
            raise InvalidProjectError("cad source fingerprint must be sha256 hex")
        if self.local_path_hint is not None and not isinstance(
                self.local_path_hint, str):
            raise InvalidProjectError("cad local_path_hint must be str or None")

    def identity_dict(self) -> dict[str, object]:
        return {"source_id": self.source_id, "format": self.format,
                "length_unit": self.length_unit,
                "fingerprint": self.fingerprint}

    def as_dict(self) -> dict[str, object]:
        return {"source_id": self.source_id, "format": self.format,
                "length_unit": self.length_unit,
                "fingerprint": self.fingerprint,
                "local_path_hint": self.local_path_hint}


@dataclass(frozen=True, slots=True)
class DatumRoleAssignment:
    """One explicit datum role assignment (no inference)."""

    role: str
    candidate_key: str
    bound_reference_key: str | None = None

    def __post_init__(self) -> None:
        if self.role not in _VALID_ROLES:
            raise InvalidProjectError(f"datum role must be one of {_VALID_ROLES}")
        _req_str(self.candidate_key, name="datum candidate_key")
        if self.bound_reference_key is not None:
            _req_str(self.bound_reference_key, name="datum bound_reference_key")

    def as_dict(self) -> dict[str, object]:
        return {"role": self.role, "candidate_key": self.candidate_key,
                "bound_reference_key": self.bound_reference_key}


@dataclass(frozen=True, slots=True)
class DatumState:
    """Explicit datum snapshot with deterministic role ordering."""

    frame_name: str
    assignments: tuple[DatumRoleAssignment, ...] = ()

    def __post_init__(self) -> None:
        _req_str(self.frame_name, name="datum frame_name")
        if not isinstance(self.assignments, tuple):
            raise InvalidProjectError("datum assignments must be a tuple")
        for item in self.assignments:
            if not isinstance(item, DatumRoleAssignment):
                raise InvalidProjectError("datum assignments must be items")
        roles = [a.role for a in self.assignments]
        if len(set(roles)) != len(roles):
            raise InvalidProjectError("datum roles must be distinct")
        object.__setattr__(self, "assignments",
                           tuple(sorted(self.assignments, key=lambda a: a.role)))

    def as_dict(self) -> dict[str, object]:
        return {"frame_name": self.frame_name,
                "assignments": [a.as_dict() for a in self.assignments]}


@dataclass(frozen=True, slots=True)
class ToleranceState:
    """Project-level tolerance refs; no engine recomputation."""

    chain_name: str
    configuration_fingerprint: str
    result_identities: tuple[str, ...] = ()
    summary_values: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _req_str(self.chain_name, name="tolerance chain_name")
        if not _is_sha(self.configuration_fingerprint):
            raise InvalidProjectError("tolerance config fingerprint must be sha256")
        if not isinstance(self.result_identities, tuple):
            raise InvalidProjectError("tolerance result_identities must be a tuple")
        for item in self.result_identities:
            if not _is_sha(item):
                raise InvalidProjectError("tolerance result ids must be sha256 hex")
        if not isinstance(self.summary_values, dict):
            raise InvalidProjectError("tolerance summary_values must be a dict")
        frozen: dict[str, float] = {}
        for key in sorted(self.summary_values):
            if not isinstance(key, str) or not key:
                raise InvalidProjectError("tolerance summary key must be str")
            frozen[key] = _req_num(self.summary_values[key],
                                   name="tolerance summary value")
        object.__setattr__(self, "summary_values", frozen)
        object.__setattr__(self, "result_identities",
                           tuple(sorted(self.result_identities)))

    def as_dict(self) -> dict[str, object]:
        return {"chain_name": self.chain_name,
                "configuration_fingerprint": self.configuration_fingerprint,
                "result_identities": list(self.result_identities),
                "summary_values": dict(self.summary_values)}


@dataclass(frozen=True, slots=True)
class OriglyphProject:
    """Immutable deterministic project snapshot (schema v1)."""

    schema_version: str
    project_id: str
    metadata: ProjectMetadata
    cad_sources: tuple[CadSourceReference, ...] = ()
    datum_state: DatumState | None = None
    tolerance_state: ToleranceState | None = None
    artifact_refs: dict[str, str] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:  # noqa: C901
        if self.schema_version != PROJECT_SCHEMA_VERSION:
            raise InvalidProjectError(
                f"unsupported project schema {self.schema_version!r}")
        if not _is_sha(self.project_id):
            raise InvalidProjectError("project_id must be sha256 hex")
        if not isinstance(self.metadata, ProjectMetadata):
            raise InvalidProjectError("metadata must be ProjectMetadata")
        if not isinstance(self.cad_sources, tuple):
            raise InvalidProjectError("cad_sources must be a tuple")
        for item in self.cad_sources:
            if not isinstance(item, CadSourceReference):
                raise InvalidProjectError("cad_sources must be CadSourceReference")
        object.__setattr__(self, "cad_sources",
                           tuple(sorted(self.cad_sources,
                                        key=lambda c: c.source_id)))
        if self.datum_state is not None and not isinstance(
                self.datum_state, DatumState):
            raise InvalidProjectError("datum_state must be DatumState or None")
        if self.tolerance_state is not None and not isinstance(
                self.tolerance_state, ToleranceState):
            raise InvalidProjectError("tolerance_state must be ToleranceState or None")
        if not isinstance(self.artifact_refs, dict):
            raise InvalidProjectError("artifact_refs must be a dict")
        frozen_refs: dict[str, str] = {}
        for key in sorted(self.artifact_refs):
            if not isinstance(key, str) or not key:
                raise InvalidProjectError("artifact_ref key must be non-empty str")
            if not _is_sha(self.artifact_refs[key]):
                raise InvalidProjectError("artifact_ref value must be sha256 hex")
            frozen_refs[key] = self.artifact_refs[key]
        object.__setattr__(self, "artifact_refs", frozen_refs)
        object.__setattr__(self, "extensions", _freeze_map(self.extensions))
        expected = _expected_id(self.cad_sources, self.datum_state,
                                self.tolerance_state, frozen_refs,
                                self.extensions)
        if self.project_id != expected:
            raise InvalidProjectError("project_id does not match project content")

    def as_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version,
                "project_id": self.project_id,
                "metadata": self.metadata.as_dict(),
                "cad_sources": [c.as_dict() for c in self.cad_sources],
                "datum_state": self.datum_state.as_dict()
                if self.datum_state is not None else None,
                "tolerance_state": self.tolerance_state.as_dict()
                if self.tolerance_state is not None else None,
                "artifact_refs": dict(self.artifact_refs),
                "extensions": copy.deepcopy(self.extensions)}

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="origlyph project")


def _identity_payload(cads: tuple[CadSourceReference, ...],
                      datum: DatumState | None,
                      tol: ToleranceState | None,
                      refs: dict[str, str],
                      ext: dict[str, Any]) -> dict[str, object]:
    return {"schema_version": PROJECT_SCHEMA_VERSION,
            "cad_sources": [c.identity_dict()
                            for c in sorted(cads, key=lambda c: c.source_id)],
            "datum_state": datum.as_dict() if datum is not None else None,
            "tolerance_state": tol.as_dict() if tol is not None else None,
            "artifact_refs": dict(sorted(refs.items())),
            "extensions": copy.deepcopy(ext)}


def _expected_id(cads: tuple[CadSourceReference, ...],
                 datum: DatumState | None,
                 tol: ToleranceState | None,
                 refs: dict[str, str],
                 ext: dict[str, Any]) -> str:
    return _fingerprint(_identity_payload(cads, datum, tol, refs, ext),
                        context="project identity")


def build_project(*, metadata: ProjectMetadata | None = None,
                  cad_sources: tuple[CadSourceReference, ...] = (),
                  datum_state: DatumState | None = None,
                  tolerance_state: ToleranceState | None = None,
                  artifact_refs: dict[str, str] | None = None,
                  extensions: dict[str, Any] | None = None) -> OriglyphProject:
    """Construct a snapshot with derived deterministic identity."""
    if not isinstance(cad_sources, tuple):
        raise InvalidProjectError("cad_sources must be a tuple")
    refs = dict(artifact_refs) if artifact_refs is not None else {}
    ext = copy.deepcopy(extensions) if extensions is not None else {}
    _canonical_json(ext, context="project extensions")
    ordered = tuple(sorted(cad_sources, key=lambda c: c.source_id))
    pid = _expected_id(ordered, datum_state, tolerance_state,
                       dict(sorted(refs.items())), ext)
    return OriglyphProject(schema_version=PROJECT_SCHEMA_VERSION,
                           project_id=pid,
                           metadata=metadata or ProjectMetadata(),
                           cad_sources=cad_sources,
                           datum_state=datum_state,
                           tolerance_state=tolerance_state,
                           artifact_refs=refs, extensions=ext)

