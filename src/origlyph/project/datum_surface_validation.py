"""Surface-type and geometric datum validation for Origlyph projects (Stage 22H).

Surface-type validation is a CAD geometry-layer check.

Validation does not approve an engineering datum strategy.

Validation results are derived state and are not persisted in origlyph.project.v1.

Unknown or unresolved surface geometry fails closed.

Stage 22H does not introduce automatic datum selection.

Validation flow
---------------
DatumTopologyRef
  → resolve_datum_topology_bindings (binding layer)
  → identify TopologyFace in CanonicalTopologyModel
  → inspect face.surface_signature
  → classify surface type against rule table

Surface-type rule table (Stage 22H v1)
---------------------------------------
PLANE  : VALID  — planar faces are accepted for PRIMARY, SECONDARY, TERTIARY.
UNKNOWN: SURFACE_TYPE_UNVALIDATABLE — kernel could not classify; fail closed.
Other  : INVALID_SURFACE_TYPE — not silently accepted.  Future work required
         to validate CYLINDER/CONE/TORUS/etc. with pairwise geometric checks.

No pairwise geometry (parallelism, perpendicularity, coaxiality) is computed
in this stage — no authoritative tolerance constants for those checks exist
in the repository at the time of Stage 22H.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from origlyph.cad.topology import CanonicalTopologyModel
from origlyph.cad.topology_signature import FaceSurfaceType

from .datum_topology_binding import (
    RESOLUTION_UNBOUND,
    RESOLUTION_UNRESOLVED_MISSING_ENTITY,
    RESOLUTION_UNRESOLVED_SOURCE_REVISION,
    DatumTopologyResolution,
    resolve_datum_topology_bindings,
)
from .exceptions import InvalidProjectError
from .models import OriglyphProject, _is_sha

__all__ = [
    "SUPPORTED_VALIDATION_ENTITY_KINDS",
    "DatumSurfaceValidationStatus",
    "DatumSurfaceValidationResult",
    "validate_datum_surface",
    "validate_datum_role_surface",
]

# ---------------------------------------------------------------------------
# Supported entity kinds for Stage 22H v1
# ---------------------------------------------------------------------------

SUPPORTED_VALIDATION_ENTITY_KINDS: frozenset[str] = frozenset({"face"})

# ---------------------------------------------------------------------------
# Surface-type rule table
# ---------------------------------------------------------------------------

#: Surface types classified as VALID for datum face roles in Stage 22H v1.
_VALID_SURFACE_TYPES: frozenset[str] = frozenset({FaceSurfaceType.PLANE.value})

#: Surface types that cannot be validated (kernel could not classify).
_UNVALIDATABLE_SURFACE_TYPES: frozenset[str] = frozenset(
    {FaceSurfaceType.UNKNOWN.value}
)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class DatumSurfaceValidationStatus(str, Enum):
    """Outcome of a datum surface-type validation check (Stage 22H).

    ``VALID``
        Surface type confirmed valid for the datum role in this stage.
    ``INVALID_SURFACE_TYPE``
        Surface type known but not accepted for datum role in Stage 22H v1.
    ``UNRESOLVED_SURFACE_TYPE``
        Face has no surface signature; surface type cannot be determined.
    ``SURFACE_TYPE_UNVALIDATABLE``
        Surface type is ``UNKNOWN``; kernel could not classify.
    ``UNSUPPORTED_ENTITY_KIND``
        Binding's entity_kind is not in
        :data:`SUPPORTED_VALIDATION_ENTITY_KINDS`.  Forward-compatibility
        guard for future entity kinds (EDGE, VERTEX, …).
    ``MISSING_ENTITY``
        Bound entity not found in the topology.
    ``SOURCE_MISMATCH``
        Binding source fingerprint does not match the topology fingerprint.
        Validation must not proceed (fail closed).
    ``UNBOUND``
        Assignment has no topology binding.
    """

    VALID = "VALID"
    INVALID_SURFACE_TYPE = "INVALID_SURFACE_TYPE"
    UNRESOLVED_SURFACE_TYPE = "UNRESOLVED_SURFACE_TYPE"
    SURFACE_TYPE_UNVALIDATABLE = "SURFACE_TYPE_UNVALIDATABLE"
    UNSUPPORTED_ENTITY_KIND = "UNSUPPORTED_ENTITY_KIND"
    MISSING_ENTITY = "MISSING_ENTITY"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    UNBOUND = "UNBOUND"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DatumSurfaceValidationResult:
    """Deterministic result of one datum role surface-type validation.

    Attributes
    ----------
    status:
        :class:`DatumSurfaceValidationStatus` classification.
    role:
        Datum role string (PRIMARY / SECONDARY / TERTIARY).
    entity_kind:
        ``DatumTopologyRef.entity_kind`` from the resolved binding, or
        ``None`` when no binding exists or resolution failed before decode.
    entity_id:
        ``resolved_entity_id`` confirmed present in the topology, or
        ``None`` when unavailable.
    surface_type:
        :attr:`~origlyph.cad.topology_signature.TopologyFaceSignature.surface_type`
        string of the resolved face, or ``None`` when unavailable.
    reason_code:
        Short machine-readable reason string.  ``reason_code`` is
        **authoritative** for programmatic logic.
    diagnostic:
        Optional human-readable diagnostic string.  NOT authoritative;
        may change between releases.
    """

    status: DatumSurfaceValidationStatus
    role: str
    entity_kind: Optional[str]
    entity_id: Optional[str]
    surface_type: Optional[str]
    reason_code: str
    diagnostic: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_resolved_face(
    role: str,
    entity_kind: str,
    entity_id: str,
    topology: CanonicalTopologyModel,
) -> DatumSurfaceValidationResult:
    """Validate the surface type of a resolved face entity."""
    if entity_kind not in SUPPORTED_VALIDATION_ENTITY_KINDS:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.UNSUPPORTED_ENTITY_KIND,
            role=role,
            entity_kind=entity_kind,
            entity_id=entity_id,
            surface_type=None,
            reason_code="ENTITY_KIND_NOT_VALIDATABLE",
            diagnostic=(
                f"Entity kind {entity_kind!r} is not in "
                f"{sorted(SUPPORTED_VALIDATION_ENTITY_KINDS)}."
            ),
        )

    face = None
    for f in topology.faces:
        if f.entity_id.value == entity_id:
            face = f
            break

    if face is None:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.MISSING_ENTITY,
            role=role,
            entity_kind=entity_kind,
            entity_id=entity_id,
            surface_type=None,
            reason_code="FACE_LOOKUP_FAILED",
            diagnostic="Resolved entity ID not found during face lookup.",
        )

    sig = face.surface_signature
    if sig is None:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.UNRESOLVED_SURFACE_TYPE,
            role=role,
            entity_kind=entity_kind,
            entity_id=entity_id,
            surface_type=None,
            reason_code="SURFACE_SIGNATURE_ABSENT",
            diagnostic="Face has no surface signature.",
        )

    stype = sig.surface_type
    if stype in _UNVALIDATABLE_SURFACE_TYPES:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.SURFACE_TYPE_UNVALIDATABLE,
            role=role,
            entity_kind=entity_kind,
            entity_id=entity_id,
            surface_type=stype,
            reason_code="SURFACE_TYPE_UNKNOWN",
            diagnostic="Surface type is UNKNOWN; validation is not possible.",
        )

    if stype in _VALID_SURFACE_TYPES:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.VALID,
            role=role,
            entity_kind=entity_kind,
            entity_id=entity_id,
            surface_type=stype,
            reason_code="SURFACE_TYPE_VALID",
        )

    return DatumSurfaceValidationResult(
        status=DatumSurfaceValidationStatus.INVALID_SURFACE_TYPE,
        role=role,
        entity_kind=entity_kind,
        entity_id=entity_id,
        surface_type=stype,
        reason_code="SURFACE_TYPE_NOT_SUPPORTED_FOR_DATUM_ROLE",
        diagnostic=f"Surface type {stype!r} not accepted in Stage 22H v1.",
    )


def _validate_one_resolution(
    resolution: DatumTopologyResolution,
    topology: CanonicalTopologyModel,
) -> DatumSurfaceValidationResult:
    """Map one binding resolution to a surface validation result."""
    role = resolution.assignment.role
    ref = resolution.ref

    if resolution.status == RESOLUTION_UNBOUND:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.UNBOUND,
            role=role,
            entity_kind=None,
            entity_id=None,
            surface_type=None,
            reason_code="UNBOUND_ASSIGNMENT",
            diagnostic="Datum role has no topology binding.",
        )

    if resolution.status == RESOLUTION_UNRESOLVED_SOURCE_REVISION:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.SOURCE_MISMATCH,
            role=role,
            entity_kind=ref.entity_kind if ref is not None else None,
            entity_id=None,
            surface_type=None,
            reason_code="SOURCE_FINGERPRINT_MISMATCH",
            diagnostic=(
                "Binding source fingerprint does not match topology; "
                "validation cannot proceed."
            ),
        )

    if resolution.status == RESOLUTION_UNRESOLVED_MISSING_ENTITY:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.MISSING_ENTITY,
            role=role,
            entity_kind=ref.entity_kind if ref is not None else None,
            entity_id=ref.entity_id if ref is not None else None,
            surface_type=None,
            reason_code="BOUND_ENTITY_NOT_FOUND",
            diagnostic="Bound entity not present in topology.",
        )

    # RESOLVED: ref and resolved_entity_id are guaranteed non-None by contract
    if ref is None or resolution.resolved_entity_id is None:
        return DatumSurfaceValidationResult(
            status=DatumSurfaceValidationStatus.MISSING_ENTITY,
            role=role,
            entity_kind=None,
            entity_id=None,
            surface_type=None,
            reason_code="INTERNAL_RESOLUTION_INCONSISTENCY",
        )

    return _validate_resolved_face(
        role=role,
        entity_kind=ref.entity_kind,
        entity_id=resolution.resolved_entity_id,
        topology=topology,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_datum_surface(
    project: OriglyphProject,
    topology: CanonicalTopologyModel,
    topology_fingerprint: str,
) -> tuple[DatumSurfaceValidationResult, ...]:
    """Validate surface types for all datum role assignments in *project*.

    Returns one :class:`DatumSurfaceValidationResult` per assignment in
    ``project.datum_state``.  Returns an empty tuple when ``datum_state``
    is ``None``.

    Validation is derived state: it does **not** modify the project,
    does **not** persist results, and does **not** change ``project_id``.

    Parameters
    ----------
    project:
        Project whose ``datum_state`` bindings are validated.
    topology:
        A runtime :class:`~origlyph.cad.topology.CanonicalTopologyModel`
        rehydrated from the STEP source; never serialized.
    topology_fingerprint:
        SHA-256 (64-char lowercase hex) of the STEP file used to build
        *topology*.  Must match the fingerprint stored in bindings for
        resolution (and thus validation) to succeed.

    Raises
    ------
    InvalidProjectError
        When arguments are the wrong types or ``topology_fingerprint`` is
        not a valid SHA-256 hex string.
    """
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    if not isinstance(topology, CanonicalTopologyModel):
        raise InvalidProjectError("topology must be a CanonicalTopologyModel")
    if not _is_sha(topology_fingerprint):
        raise InvalidProjectError(
            "topology_fingerprint must be a 64-character "
            "lowercase sha256 hex string"
        )
    if project.datum_state is None:
        return ()

    resolutions = resolve_datum_topology_bindings(
        project, topology, topology_fingerprint
    )
    return tuple(
        _validate_one_resolution(res, topology) for res in resolutions
    )


def validate_datum_role_surface(
    project: OriglyphProject,
    topology: CanonicalTopologyModel,
    topology_fingerprint: str,
    role: str,
) -> DatumSurfaceValidationResult:
    """Validate surface type for a single datum role in *project*.

    Parameters
    ----------
    project:
        Project whose datum binding for *role* is validated.
    topology:
        Runtime :class:`~origlyph.cad.topology.CanonicalTopologyModel`.
    topology_fingerprint:
        SHA-256 hex of the STEP file used to build *topology*.
    role:
        Datum role to validate (``"PRIMARY"``, ``"SECONDARY"``, or
        ``"TERTIARY"``).

    Returns
    -------
    DatumSurfaceValidationResult
        Result for the requested role.

    Raises
    ------
    InvalidProjectError
        When ``datum_state`` is ``None`` or *role* is not found.
    """
    if project.datum_state is None:
        raise InvalidProjectError("project has no datum_state")

    all_results = validate_datum_surface(project, topology, topology_fingerprint)
    for result in all_results:
        if result.role == role:
            return result
    raise InvalidProjectError(
        f"datum role {role!r} not found in project.datum_state"
    )
