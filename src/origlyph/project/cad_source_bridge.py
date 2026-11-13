"""STEP source reference bridge for the Origlyph project model (Stage 22F).

Converts a Stage 22E SourceDocumentIdentity into a CadSourceReference that
can be persisted in an OriglyphProject.  Only source identity metadata and
the SHA-256 content fingerprint are recorded.  CanonicalTopologyModel is
never serialized.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from origlyph.cad.identity import CadFormat, SourceDocumentIdentity

from .exceptions import InvalidProjectError
from .models import CadSourceReference, OriglyphProject, _is_sha, build_project

__all__ = [
    "cad_source_reference_from_step",
    "project_with_step_source",
]

_STEP_SUFFIXES: frozenset[str] = frozenset({".step", ".stp"})


def cad_source_reference_from_step(
    source: SourceDocumentIdentity,
    path: Path | str,
    *,
    expected_fingerprint: str | None = None,
    local_path_hint: str | None = None,
) -> CadSourceReference:
    """Create a CadSourceReference from a Stage 22E STEP SourceDocumentIdentity.

    Computes an authoritative SHA-256 content fingerprint from the file bytes.
    If *expected_fingerprint* is supplied the computed value must match exactly;
    a mismatch raises InvalidProjectError.

    Does not require OCP.  Does not parse STEP topology.
    """
    if not isinstance(source, SourceDocumentIdentity):
        raise InvalidProjectError("source must be a SourceDocumentIdentity")
    if source.format is not CadFormat.STEP:
        raise InvalidProjectError(
            f"source.format must be CadFormat.STEP; got {source.format!r}"
        )

    p = Path(path)
    if p.suffix.lower() not in _STEP_SUFFIXES:
        raise InvalidProjectError(
            f"unsupported STEP file extension {p.suffix!r}; "
            "accepted: .step, .stp (case-insensitive)"
        )
    if not p.exists():
        raise InvalidProjectError(f"STEP file not found: {p}")
    if not p.is_file():
        raise InvalidProjectError(f"STEP path is not a regular file: {p}")

    try:
        file_bytes = p.read_bytes()
    except OSError as exc:
        raise InvalidProjectError(
            f"STEP file cannot be read: {exc}"
        ) from exc

    computed_fp = hashlib.sha256(file_bytes).hexdigest()

    if expected_fingerprint is not None:
        if not _is_sha(expected_fingerprint):
            raise InvalidProjectError(
                "expected_fingerprint must be a 64-character lowercase "
                "sha256 hex string"
            )
        if expected_fingerprint != computed_fp:
            raise InvalidProjectError(
                f"fingerprint mismatch: "
                f"expected {expected_fingerprint}, computed {computed_fp}"
            )

    return CadSourceReference(
        source_id=source.source_id,
        format=source.format.value,
        length_unit=source.unit_system.length_unit,
        fingerprint=computed_fp,
        local_path_hint=local_path_hint,
    )


def project_with_step_source(
    project: OriglyphProject,
    source: SourceDocumentIdentity,
    path: Path | str,
    *,
    expected_fingerprint: str | None = None,
    local_path_hint: str | None = None,
) -> OriglyphProject:
    """Return a new OriglyphProject with the STEP source reference appended.

    All existing state (metadata, datum, tolerance, workspace, other CAD
    sources) is preserved.  project_id changes because cad_sources participates
    in authoritative identity.

    Duplicate policy:
    - same source_id + same fingerprint already present -> return project unchanged
    - same source_id + different fingerprint -> InvalidProjectError
    """
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")

    cad_ref = cad_source_reference_from_step(
        source,
        path,
        expected_fingerprint=expected_fingerprint,
        local_path_hint=local_path_hint,
    )

    for existing in project.cad_sources:
        if existing.source_id == cad_ref.source_id:
            if existing.fingerprint == cad_ref.fingerprint:
                return project
            raise InvalidProjectError(
                f"cad source {cad_ref.source_id!r} already exists "
                "with a different fingerprint"
            )

    new_sources = project.cad_sources + (cad_ref,)
    return build_project(
        metadata=project.metadata,
        cad_sources=new_sources,
        datum_state=project.datum_state,
        tolerance_state=project.tolerance_state,
        artifact_refs=dict(project.artifact_refs),
        extensions=dict(project.extensions),
    )
