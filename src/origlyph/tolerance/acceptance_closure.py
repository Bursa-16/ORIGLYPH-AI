"""Deterministic closure manifest for governed acceptance records (Stage 15W).

Stage 15W closes the deterministic governed-acceptance artifact chain.
It does not create, infer, authenticate, or legally validate an approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum

from .acceptance_handoff import (
    ACCEPTANCE_HANDOFF_SCHEMA_VERSION,
    AuditAcceptanceHandoffPackage,
    AuditAcceptanceHandoffStatus,
)
from .acceptance_record import (
    ACCEPTANCE_RECORD_SCHEMA_VERSION,
    VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION,
    AuditAcceptanceDecision,
    ValidatedAuditAcceptanceRecord,
)
from .acceptance_verification import (
    ACCEPTANCE_VERIFICATION_SCHEMA_VERSION,
    AuditAcceptanceVerificationEnvelope,
    AuditAcceptanceVerificationFact,
    AuditAcceptanceVerificationStatus,
)

__all__ = [
    "ACCEPTANCE_CLOSURE_SCHEMA_VERSION",
    "AuditAcceptanceClosureManifest",
    "AuditAcceptanceClosureReference",
    "AuditAcceptanceClosureStatus",
    "InvalidAuditAcceptanceClosureError",
    "build_acceptance_closure_manifest",
]


ACCEPTANCE_CLOSURE_SCHEMA_VERSION = "origlyph.tolerance.audit_acceptance_closure.v1"

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InvalidAuditAcceptanceClosureError(ValueError):
    """Raised when the deterministic closure manifest cannot be constructed."""


class AuditAcceptanceClosureStatus(Enum):
    """Deterministic closure state of the governed acceptance chain."""

    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class AuditAcceptanceClosureReference:
    """Immutable references to the upstream Stage 15T-15V artifacts."""

    handoff_id: str
    handoff_schema_version: str
    handoff_status: AuditAcceptanceHandoffStatus
    acceptance_record_id: str
    decision: AuditAcceptanceDecision
    authority_reference: str
    decision_reference: str
    envelope_id: str
    verification_status: AuditAcceptanceVerificationStatus

    def as_dict(self) -> dict[str, object]:
        return {
            "handoff_id": self.handoff_id,
            "handoff_schema_version": self.handoff_schema_version,
            "handoff_status": self.handoff_status.value,
            "acceptance_record_id": self.acceptance_record_id,
            "decision": self.decision.value,
            "authority_reference": self.authority_reference,
            "decision_reference": self.decision_reference,
            "envelope_id": self.envelope_id,
            "verification_status": self.verification_status.value,
        }


@dataclass(frozen=True, slots=True)
class AuditAcceptanceClosureManifest:
    """Immutable closure manifest packaging consistent acceptance chain references."""

    schema_version: str
    closure_id: str
    status: AuditAcceptanceClosureStatus
    references: AuditAcceptanceClosureReference

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "closure_id": self.closure_id,
            "status": self.status.value,
            "references": self.references.as_dict(),
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="closure manifest")


def _canonical_json(payload: object, *, context: str) -> str:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceClosureError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object, *, context: str) -> str:
    canonical = _canonical_json(payload, context=context)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise InvalidAuditAcceptanceClosureError(
            f"{field} must be a lowercase SHA-256 fingerprint"
        )
    return value


def _require_reference(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise InvalidAuditAcceptanceClosureError(
            f"{field} must be a non-empty canonical string"
        )
    return value


def _validate_serialized_identity(
    payload: dict[str, object],
    *,
    identity_field: str,
    expected_identity: str,
    expected_keys: set[str],
    context: str,
) -> None:
    if set(payload) != expected_keys:
        raise InvalidAuditAcceptanceClosureError(
            f"{context} does not have canonical fields"
        )
    identity_payload = dict(payload)
    recorded_identity = identity_payload.pop(identity_field)
    if recorded_identity != expected_identity:
        raise InvalidAuditAcceptanceClosureError(f"{context} identity is inconsistent")
    if _fingerprint(identity_payload, context=f"{context} identity") != (
        expected_identity
    ):
        raise InvalidAuditAcceptanceClosureError(f"{context} fingerprint is invalid")


def _validate_handoff(value: object) -> AuditAcceptanceHandoffPackage:
    if type(value) is not AuditAcceptanceHandoffPackage:
        raise InvalidAuditAcceptanceClosureError(
            "handoff_package must be an AuditAcceptanceHandoffPackage"
        )
    handoff = value
    if handoff.schema_version != ACCEPTANCE_HANDOFF_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceClosureError("unsupported handoff schema version")
    _require_sha256(handoff.handoff_id, field="handoff_id")
    if not isinstance(handoff.status, AuditAcceptanceHandoffStatus):
        raise InvalidAuditAcceptanceClosureError("handoff status is invalid")
    try:
        payload = handoff.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceClosureError(
            f"handoff package is malformed: {exc}"
        ) from exc
    _validate_serialized_identity(
        payload,
        identity_field="handoff_id",
        expected_identity=handoff.handoff_id,
        expected_keys={
            "schema_version",
            "handoff_id",
            "baseline_package_id",
            "candidate_package_id",
            "status",
            "comparison_result",
            "impact_result",
            "disposition_result",
            "readiness_result",
        },
        context="handoff package",
    )
    return handoff


def _validate_record(value: object) -> ValidatedAuditAcceptanceRecord:
    if type(value) is not ValidatedAuditAcceptanceRecord:
        raise InvalidAuditAcceptanceClosureError(
            "validated_acceptance_record must be a ValidatedAuditAcceptanceRecord"
        )
    record = value
    if record.schema_version != VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceClosureError(
            "unsupported validated acceptance record schema version"
        )
    _require_sha256(record.acceptance_record_id, field="acceptance_record_id")
    _require_sha256(record.handoff_id, field="handoff_id")
    if not isinstance(record.handoff_status, AuditAcceptanceHandoffStatus):
        raise InvalidAuditAcceptanceClosureError("record handoff status is invalid")
    if not isinstance(record.decision, AuditAcceptanceDecision):
        raise InvalidAuditAcceptanceClosureError("acceptance decision is invalid")
    _require_reference(record.authority_reference, field="authority_reference")
    _require_reference(record.decision_reference, field="decision_reference")
    try:
        payload = record.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceClosureError(
            f"validated acceptance record is malformed: {exc}"
        ) from exc
    _validate_serialized_identity(
        payload,
        identity_field="acceptance_record_id",
        expected_identity=record.acceptance_record_id,
        expected_keys={
            "schema_version",
            "acceptance_record_id",
            "acceptance_record_schema_version",
            "handoff_id",
            "handoff_status",
            "decision",
            "authority_reference",
            "decision_reference",
        },
        context="validated acceptance record",
    )
    if record.acceptance_record_schema_version != ACCEPTANCE_RECORD_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceClosureError(
            "unsupported external acceptance record schema version"
        )
    return record


def _validate_envelope(value: object) -> AuditAcceptanceVerificationEnvelope:
    if type(value) is not AuditAcceptanceVerificationEnvelope:
        raise InvalidAuditAcceptanceClosureError(
            "verification_envelope must be an AuditAcceptanceVerificationEnvelope"
        )
    envelope = value
    if envelope.schema_version != ACCEPTANCE_VERIFICATION_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceClosureError(
            "unsupported verification envelope schema version"
        )
    _require_sha256(envelope.envelope_id, field="envelope_id")
    _require_sha256(envelope.handoff_id, field="handoff_id")
    _require_sha256(envelope.acceptance_record_id, field="acceptance_record_id")
    if not isinstance(envelope.status, AuditAcceptanceVerificationStatus):
        raise InvalidAuditAcceptanceClosureError("verification status is invalid")
    if envelope.status != AuditAcceptanceVerificationStatus.VERIFIED_BINDING:
        raise InvalidAuditAcceptanceClosureError(
            "unverified verification envelope status"
        )
    _require_reference(envelope.authority_reference, field="authority_reference")
    _require_reference(envelope.decision_reference, field="decision_reference")
    try:
        payload = envelope.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceClosureError(
            f"verification envelope is malformed: {exc}"
        ) from exc
    _validate_serialized_identity(
        payload,
        identity_field="envelope_id",
        expected_identity=envelope.envelope_id,
        expected_keys={
            "schema_version",
            "envelope_id",
            "status",
            "handoff_id",
            "acceptance_record_id",
            "decision",
            "authority_reference",
            "decision_reference",
            "verification_facts",
        },
        context="verification envelope",
    )
    if not isinstance(envelope.decision, AuditAcceptanceDecision):
        raise InvalidAuditAcceptanceClosureError(
            "verification envelope decision is invalid"
        )
    if not isinstance(
        envelope.verification_facts, tuple
    ) or envelope.verification_facts != (
        AuditAcceptanceVerificationFact.HANDOFF_FINGERPRINT_MATCH,
        AuditAcceptanceVerificationFact.ACCEPTANCE_RECORD_FINGERPRINT_MATCH,
        AuditAcceptanceVerificationFact.HANDOFF_BINDING_MATCH,
        AuditAcceptanceVerificationFact.REFERENCE_CONTENT_PRESERVED,
    ):
        raise InvalidAuditAcceptanceClosureError("verification facts are malformed")
    return envelope


def build_acceptance_closure_manifest(
    handoff_package: AuditAcceptanceHandoffPackage,
    validated_acceptance_record: ValidatedAuditAcceptanceRecord,
    verification_envelope: AuditAcceptanceVerificationEnvelope,
) -> AuditAcceptanceClosureManifest:
    """Build the deterministic closure manifest for the governed acceptance chain."""
    handoff = _validate_handoff(handoff_package)
    record = _validate_record(validated_acceptance_record)
    envelope = _validate_envelope(verification_envelope)

    # Chain consistency checks
    if record.handoff_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceClosureError(
            "validated acceptance record handoff_id mismatch"
        )
    if envelope.handoff_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceClosureError(
            "verification envelope handoff_id mismatch"
        )
    if envelope.acceptance_record_id != record.acceptance_record_id:
        raise InvalidAuditAcceptanceClosureError(
            "verification envelope acceptance_record_id mismatch"
        )

    if record.decision != envelope.decision:
        raise InvalidAuditAcceptanceClosureError(
            "contradictory decision between record and envelope"
        )
    if record.authority_reference != envelope.authority_reference:
        raise InvalidAuditAcceptanceClosureError(
            "contradictory authority reference between record and envelope"
        )
    if record.decision_reference != envelope.decision_reference:
        raise InvalidAuditAcceptanceClosureError(
            "contradictory decision reference between record and envelope"
        )
    if record.handoff_status != handoff.status:
        raise InvalidAuditAcceptanceClosureError(
            "validated record handoff status does not match handoff package status"
        )
    if (
        handoff.status
        in {
            AuditAcceptanceHandoffStatus.ACTION_REQUIRED,
            AuditAcceptanceHandoffStatus.BLOCKED,
        }
        and record.decision is AuditAcceptanceDecision.APPROVED
    ):
        raise InvalidAuditAcceptanceClosureError(
            "approved decision conflicts with handoff status"
        )

    references = AuditAcceptanceClosureReference(
        handoff_id=handoff.handoff_id,
        handoff_schema_version=handoff.schema_version,
        handoff_status=handoff.status,
        acceptance_record_id=record.acceptance_record_id,
        decision=record.decision,
        authority_reference=record.authority_reference,
        decision_reference=record.decision_reference,
        envelope_id=envelope.envelope_id,
        verification_status=envelope.status,
    )

    identity_payload = {
        "schema_version": ACCEPTANCE_CLOSURE_SCHEMA_VERSION,
        "status": AuditAcceptanceClosureStatus.COMPLETE.value,
        "references": references.as_dict(),
    }
    closure_id = _fingerprint(identity_payload, context="closure manifest identity")

    return AuditAcceptanceClosureManifest(
        schema_version=ACCEPTANCE_CLOSURE_SCHEMA_VERSION,
        closure_id=closure_id,
        status=AuditAcceptanceClosureStatus.COMPLETE,
        references=references,
    )
