"""Datum-to-topology binding persistence (Stage 22G).

Encodes a stable reference to a canonical topology entity into the existing
DatumRoleAssignment.bound_reference_key field without schema change.  No OCP
objects, no CanonicalTopologyModel, and no topology entity structures are ever
serialized to the project JSON.

Binding format version:  topology:v1
Encoding:                topology:v1:{source_fingerprint}:{entity_kind}:{entity_id}

The source_fingerprint anchors the binding to an exact CAD artifact (SHA-256
of file bytes).  Bindings are deterministic for the same artifact and topology
snapshot.  They are not guaranteed to survive CAD source revision changes.

Stage 22G scope: "face" entity kind only.
"""

from __future__ import annotations

from dataclasses import dataclass

from origlyph.cad.topology import CanonicalTopologyModel

from .exceptions import InvalidProjectError
from .models import (
    _VALID_ROLES,  # private but intra-package; established pattern
    DatumRoleAssignment,
    OriglyphProject,
    _is_sha,  # private but intra-package; established pattern
)

__all__ = [
    "BINDING_FORMAT_VERSION",
    "BINDING_FORMAT_VERSION_V2",
    "SUPPORTED_DATUM_ENTITY_KINDS",
    "RESOLUTION_RESOLVED",
    "RESOLUTION_UNRESOLVED_SOURCE_REVISION",
    "RESOLUTION_UNRESOLVED_MISSING_ENTITY",
    "RESOLUTION_UNBOUND",
    "RESOLUTION_REMAPPED_EXACT",
    "RESOLUTION_REMAPPED_PROBABLE",
    "RESOLUTION_AMBIGUOUS",
    "DatumTopologyRef",
    "DatumTopologyResolution",
    "datum_role_assignment_with_topology",
    "decode_datum_topology_ref",
    "encode_datum_topology_ref",
    "is_topology_binding",
    "resolve_datum_topology_bindings",
]

BINDING_FORMAT_VERSION: str = "topology:v1"
BINDING_FORMAT_VERSION_V2: str = "topology:v2"
SUPPORTED_DATUM_ENTITY_KINDS: frozenset[str] = frozenset({"face"})

RESOLUTION_RESOLVED: str = "RESOLVED"
RESOLUTION_UNRESOLVED_SOURCE_REVISION: str = "UNRESOLVED_SOURCE_REVISION"
RESOLUTION_UNRESOLVED_MISSING_ENTITY: str = "UNRESOLVED_MISSING_ENTITY"
RESOLUTION_UNBOUND: str = "UNBOUND"
RESOLUTION_REMAPPED_EXACT: str = "REMAPPED_EXACT"
RESOLUTION_REMAPPED_PROBABLE: str = "REMAPPED_PROBABLE"
RESOLUTION_AMBIGUOUS: str = "AMBIGUOUS"

_BINDING_PREFIX: str = "topology:v1:"
_BINDING_PREFIX_V2: str = "topology:v2:"


@dataclass(frozen=True, slots=True)
class DatumTopologyRef:
    """Authoritative topology entity reference for datum binding.

    Attributes
    ----------
    source_fingerprint:
        SHA-256 (64-char lowercase hex) of the CAD file bytes.  Anchors the
        binding to an exact, unmodified CAD artifact.
    entity_kind:
        Canonical entity type.  Stage 22G supports ``"face"`` only.
    entity_id:
        ``TopologyEntityId.value`` of the referenced topology entity.
    persistent_id:
        Stage 22H persistent face identity SHA-256 (64-char lowercase hex),
        or ``None`` for Stage 22G-era bindings without embedded signatures.
        Encoded in v2 format only; v1 bindings always decode to ``None``.
    """

    source_fingerprint: str
    entity_kind: str
    entity_id: str
    persistent_id: str | None = None

    def __post_init__(self) -> None:
        if not _is_sha(self.source_fingerprint):
            raise InvalidProjectError(
                "DatumTopologyRef.source_fingerprint must be a 64-character "
                "lowercase sha256 hex string"
            )
        if self.entity_kind not in SUPPORTED_DATUM_ENTITY_KINDS:
            raise InvalidProjectError(
                f"DatumTopologyRef.entity_kind must be one of "
                f"{sorted(SUPPORTED_DATUM_ENTITY_KINDS)}; "
                f"got {self.entity_kind!r}"
            )
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise InvalidProjectError(
                "DatumTopologyRef.entity_id must be a non-empty string"
            )
        if self.persistent_id is not None and not _is_sha(self.persistent_id):
            raise InvalidProjectError(
                "DatumTopologyRef.persistent_id must be a 64-character "
                "lowercase sha256 hex string when present"
            )


def encode_datum_topology_ref(ref: DatumTopologyRef) -> str:
    """Return the bound_reference_key wire-format string for *ref*.

    v1 format (no persistent_id):
        ``topology:v1:{source_fingerprint}:{entity_kind}:{entity_id}``

    v2 format (with persistent_id):
        ``topology:v2:{source_fingerprint}:{entity_kind}:{entity_id}:{pid64}``

    ``entity_id`` may contain colons; :func:`decode_datum_topology_ref` handles
    both formats unambiguously via version-prefix detection.
    """
    if ref.persistent_id is not None:
        return (
            f"{BINDING_FORMAT_VERSION_V2}"
            f":{ref.source_fingerprint}"
            f":{ref.entity_kind}"
            f":{ref.entity_id}"
            f":{ref.persistent_id}"
        )
    return (
        f"{BINDING_FORMAT_VERSION}"
        f":{ref.source_fingerprint}"
        f":{ref.entity_kind}"
        f":{ref.entity_id}"
    )


def decode_datum_topology_ref(key: str) -> DatumTopologyRef:  # noqa: C901
    """Decode a bound_reference_key string into a :class:`DatumTopologyRef`.

    Handles both v1 (``topology:v1:…``) and v2 (``topology:v2:…``) formats.

    v2 parsing: ``key.split(":", 4)`` → 5 parts; ``parts[4]`` contains
    ``{entity_id}:{pid64}`` where ``pid64`` is exactly 64 lowercase hex chars.
    The split point is determined by the fixed 65-char tail ``":" + pid64``.

    Raises :class:`InvalidProjectError` on any malformed or unsupported input.
    """
    if not isinstance(key, str):
        raise InvalidProjectError("datum topology key must be a string")
    is_v2 = key.startswith(_BINDING_PREFIX_V2)
    if not is_v2 and not key.startswith(_BINDING_PREFIX):
        raise InvalidProjectError(
            f"datum topology key must start with {_BINDING_PREFIX!r} or "
            f"{_BINDING_PREFIX_V2!r}; got {key!r}"
        )
    # Split at most 4 times → ["topology", "v1/v2", fingerprint, kind, rest]
    parts = key.split(":", 4)
    if len(parts) != 5:
        raise InvalidProjectError(
            f"malformed datum topology key; expected 5 colon-delimited "
            f"fields, got {len(parts)}: {key!r}"
        )
    _fmt, _ver, fingerprint, kind, rest = parts
    if not _is_sha(fingerprint):
        raise InvalidProjectError(
            f"datum topology key contains invalid fingerprint: {fingerprint!r}"
        )
    if kind not in SUPPORTED_DATUM_ENTITY_KINDS:
        raise InvalidProjectError(
            f"datum topology key entity_kind {kind!r} is not in supported set "
            f"{sorted(SUPPORTED_DATUM_ENTITY_KINDS)}"
        )

    if is_v2:
        # rest = "{entity_id}:{pid64}" where pid64 is exactly 64 hex chars
        # The tail is always ":" + 64 chars = 65 chars
        if len(rest) < 65 or rest[-65] != ":":
            raise InvalidProjectError(
                f"malformed v2 datum topology key; rest field must end with "
                f"':<64-hex-pid>'; got rest={rest!r}"
            )
        entity_id = rest[:-65]
        pid64 = rest[-64:]
        if not _is_sha(pid64):
            raise InvalidProjectError(
                f"malformed v2 datum topology key; persistent_id is not a "
                f"64-char lowercase sha256 hex: {pid64!r}"
            )
        if not entity_id:
            raise InvalidProjectError(
                "datum topology v2 key entity_id must be non-empty"
            )
        return DatumTopologyRef(
            source_fingerprint=fingerprint,
            entity_kind=kind,
            entity_id=entity_id,
            persistent_id=pid64,
        )

    # v1
    entity_id = rest
    if not entity_id:
        raise InvalidProjectError(
            "datum topology key entity_id must be non-empty"
        )
    return DatumTopologyRef(
        source_fingerprint=fingerprint,
        entity_kind=kind,
        entity_id=entity_id,
    )


def is_topology_binding(key: str | None) -> bool:
    """Return ``True`` when *key* is a v1 or v2 topology binding key."""
    return isinstance(key, str) and (
        key.startswith(_BINDING_PREFIX) or key.startswith(_BINDING_PREFIX_V2)
    )


def datum_role_assignment_with_topology(
    role: str,
    candidate_key: str,
    ref: DatumTopologyRef,
) -> DatumRoleAssignment:
    """Return a :class:`DatumRoleAssignment` with an encoded topology binding.

    The caller is responsible for ensuring *ref.source_fingerprint* corresponds
    to a :class:`~origlyph.project.models.CadSourceReference` already present
    in the target project before the assignment is committed to that project.
    """
    if role not in _VALID_ROLES:
        raise InvalidProjectError(
            f"datum role must be one of {_VALID_ROLES}; got {role!r}"
        )
    encoded = encode_datum_topology_ref(ref)
    return DatumRoleAssignment(
        role=role,
        candidate_key=candidate_key,
        bound_reference_key=encoded,
    )


@dataclass(frozen=True, slots=True)
class DatumTopologyResolution:
    """Resolution result for one :class:`~origlyph.project.models.DatumRoleAssignment`.

    Attributes
    ----------
    assignment:
        The source assignment.
    status:
        One of the ``RESOLUTION_*`` constants defined in this module.
    ref:
        Decoded :class:`DatumTopologyRef`, or ``None`` when ``status`` is
        ``RESOLUTION_UNBOUND`` or the key is malformed.
    resolved_entity_id:
        The ``TopologyEntityId.value`` confirmed present in the topology model,
        or ``None`` when the binding could not be resolved.
    """

    assignment: DatumRoleAssignment
    status: str
    ref: DatumTopologyRef | None
    resolved_entity_id: str | None


def _resolve_one(
    assignment: DatumRoleAssignment,
    known_fingerprints: frozenset[str],
    topology_fingerprint: str,
    face_ids: frozenset[str],
) -> DatumTopologyResolution:
    """Resolve a single binding assignment (extracted for complexity budget)."""
    key = assignment.bound_reference_key
    if not is_topology_binding(key):
        return DatumTopologyResolution(
            assignment=assignment,
            status=RESOLUTION_UNBOUND,
            ref=None,
            resolved_entity_id=None,
        )

    try:
        ref = decode_datum_topology_ref(key)  # type: ignore[arg-type]
    except InvalidProjectError:
        return DatumTopologyResolution(
            assignment=assignment,
            status=RESOLUTION_UNRESOLVED_MISSING_ENTITY,
            ref=None,
            resolved_entity_id=None,
        )

    # Both checks required: binding fingerprint must equal the topology
    # fingerprint AND must exist in the project's registered sources.
    if ref.source_fingerprint != topology_fingerprint or \
            ref.source_fingerprint not in known_fingerprints:
        return DatumTopologyResolution(
            assignment=assignment,
            status=RESOLUTION_UNRESOLVED_SOURCE_REVISION,
            ref=ref,
            resolved_entity_id=None,
        )

    entity_found = (
        ref.entity_id
        if ref.entity_kind == "face" and ref.entity_id in face_ids
        else None
    )
    status = RESOLUTION_RESOLVED if entity_found is not None \
        else RESOLUTION_UNRESOLVED_MISSING_ENTITY
    return DatumTopologyResolution(
        assignment=assignment,
        status=status,
        ref=ref,
        resolved_entity_id=entity_found,
    )


def resolve_datum_topology_bindings(
    project: OriglyphProject,
    topology: CanonicalTopologyModel,
    topology_fingerprint: str,
) -> tuple[DatumTopologyResolution, ...]:
    """Resolve all datum-to-topology bindings in *project* against *topology*.

    Returns one :class:`DatumTopologyResolution` per assignment in
    ``project.datum_state``.  Returns an empty tuple when ``datum_state`` is
    ``None``.

    ``topology`` is never serialized; it is used only for entity lookup.

    Parameters
    ----------
    project:
        The project whose ``datum_state`` bindings are resolved.
    topology:
        A runtime :class:`~origlyph.cad.topology.CanonicalTopologyModel`
        rehydrated from the STEP source (e.g. via ``load_step_topology``).
    topology_fingerprint:
        SHA-256 (64-char lowercase hex) of the STEP file used to build
        *topology*.  Must match the fingerprint stored in the binding for
        resolution to succeed.

    Raises
    ------
    InvalidProjectError
        When *topology_fingerprint* is not a valid sha256 hex string, or when
        *project* / *topology* are the wrong types.
    """
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    if not isinstance(topology, CanonicalTopologyModel):
        raise InvalidProjectError("topology must be a CanonicalTopologyModel")
    if not _is_sha(topology_fingerprint):
        raise InvalidProjectError(
            "topology_fingerprint must be a 64-character lowercase sha256 "
            "hex string"
        )

    if project.datum_state is None:
        return ()

    known_fingerprints: frozenset[str] = frozenset(
        src.fingerprint for src in project.cad_sources
    )
    face_ids: frozenset[str] = frozenset(f.entity_id.value for f in topology.faces)

    return tuple(
        _resolve_one(a, known_fingerprints, topology_fingerprint, face_ids)
        for a in project.datum_state.assignments
    )
