"""Deterministic verification envelope for governed acceptance records.

Stage 15V packages structural verification evidence for authoritative Stage
15T and Stage 15U artifacts.  It invokes neither stage and makes no claim about
human identity, legal authority, signatures, or non-repudiation.
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

__all__ = [
    "ACCEPTANCE_VERIFICATION_SCHEMA_VERSION",
    "AuditAcceptanceVerificationEnvelope",
    "AuditAcceptanceVerificationFact",
    "AuditAcceptanceVerificationStatus",
    "InvalidAuditAcceptanceVerificationError",
    "build_acceptance_record_verification_envelope",
]


ACCEPTANCE_VERIFICATION_SCHEMA_VERSION = (
    "origlyph.tolerance.audit_acceptance_verification.v1"
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InvalidAuditAcceptanceVerificationError(ValueError):
    """Raised when authoritative acceptance artifacts cannot be verified."""


class AuditAcceptanceVerificationStatus(Enum):
    """Structural verification state, never an approval or authority state."""

    VERIFIED_BINDING = "verified_binding"


class AuditAcceptanceVerificationFact(Enum):
    """Deterministic facts established by the verification envelope."""

    HANDOFF_FINGERPRINT_MATCH = "handoff_fingerprint_match"
    ACCEPTANCE_RECORD_FINGERPRINT_MATCH = "acceptance_record_fingerprint_match"
    HANDOFF_BINDING_MATCH = "handoff_binding_match"
    REFERENCE_CONTENT_PRESERVED = "reference_content_preserved"


_VERIFICATION_FACTS = (
    AuditAcceptanceVerificationFact.HANDOFF_FINGERPRINT_MATCH,
    AuditAcceptanceVerificationFact.ACCEPTANCE_RECORD_FINGERPRINT_MATCH,
    AuditAcceptanceVerificationFact.HANDOFF_BINDING_MATCH,
    AuditAcceptanceVerificationFact.REFERENCE_CONTENT_PRESERVED,
)


@dataclass(frozen=True, slots=True)
class AuditAcceptanceVerificationEnvelope:
    """Immutable evidence of deterministic Stage 15T/15U structural binding."""

    schema_version: str
    envelope_id: str
    status: AuditAcceptanceVerificationStatus
    handoff_id: str
    acceptance_record_id: str
    decision: AuditAcceptanceDecision
    authority_reference: str
    decision_reference: str
    verification_facts: tuple[AuditAcceptanceVerificationFact, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "status": self.status.value,
            "handoff_id": self.handoff_id,
            "acceptance_record_id": self.acceptance_record_id,
            "decision": self.decision.value,
            "authority_reference": self.authority_reference,
            "decision_reference": self.decision_reference,
            "verification_facts": [fact.value for fact in self.verification_facts],
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="verification envelope")


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
        raise InvalidAuditAcceptanceVerificationError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object, *, context: str) -> str:
    canonical = _canonical_json(payload, context=context)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise InvalidAuditAcceptanceVerificationError(
            f"{field} must be a lowercase SHA-256 fingerprint"
        )
    return value


def _require_reference(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise InvalidAuditAcceptanceVerificationError(
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
        raise InvalidAuditAcceptanceVerificationError(
            f"{context} does not have canonical fields"
        )
    identity_payload = dict(payload)
    recorded_identity = identity_payload.pop(identity_field)
    if recorded_identity != expected_identity:
        raise InvalidAuditAcceptanceVerificationError(
            f"{context} identity is inconsistent"
        )
    if _fingerprint(identity_payload, context=f"{context} identity") != (
        expected_identity
    ):
        raise InvalidAuditAcceptanceVerificationError(
            f"{context} fingerprint is invalid"
        )


def _validate_handoff(value: object) -> AuditAcceptanceHandoffPackage:
    if type(value) is not AuditAcceptanceHandoffPackage:
        raise InvalidAuditAcceptanceVerificationError(
            "handoff_package must be an AuditAcceptanceHandoffPackage"
        )
    handoff = value
    if handoff.schema_version != ACCEPTANCE_HANDOFF_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceVerificationError(
            "unsupported handoff schema version"
        )
    _require_sha256(handoff.handoff_id, field="handoff_id")
    if not isinstance(handoff.status, AuditAcceptanceHandoffStatus):
        raise InvalidAuditAcceptanceVerificationError("handoff status is invalid")
    try:
        payload = handoff.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceVerificationError(
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
        raise InvalidAuditAcceptanceVerificationError(
            "validated_acceptance_record must be a ValidatedAuditAcceptanceRecord"
        )
    record = value
    if record.schema_version != VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceVerificationError(
            "unsupported validated acceptance record schema version"
        )
    if record.acceptance_record_schema_version != ACCEPTANCE_RECORD_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceVerificationError(
            "unsupported external acceptance record schema version"
        )
    _require_sha256(record.acceptance_record_id, field="acceptance_record_id")
    _require_sha256(record.handoff_id, field="acceptance record handoff_id")
    if not isinstance(record.handoff_status, AuditAcceptanceHandoffStatus):
        raise InvalidAuditAcceptanceVerificationError(
            "acceptance record handoff status is invalid"
        )
    if not isinstance(record.decision, AuditAcceptanceDecision):
        raise InvalidAuditAcceptanceVerificationError(
            "acceptance record decision is invalid"
        )
    _require_reference(record.authority_reference, field="authority_reference")
    _require_reference(record.decision_reference, field="decision_reference")
    try:
        payload = record.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceVerificationError(
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
    return record


def _validate_binding(
    handoff: AuditAcceptanceHandoffPackage,
    record: ValidatedAuditAcceptanceRecord,
) -> None:
    if record.handoff_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceVerificationError(
            "validated acceptance record is not bound to the supplied handoff"
        )
    if record.handoff_status is not handoff.status:
        raise InvalidAuditAcceptanceVerificationError(
            "validated acceptance record handoff status is inconsistent"
        )
    if (
        handoff.status
        in {
            AuditAcceptanceHandoffStatus.ACTION_REQUIRED,
            AuditAcceptanceHandoffStatus.BLOCKED,
        }
        and record.decision is AuditAcceptanceDecision.APPROVED
    ):
        raise InvalidAuditAcceptanceVerificationError(
            "approved decision is impossible for the supplied handoff status"
        )


def _identity_payload(
    handoff: AuditAcceptanceHandoffPackage,
    record: ValidatedAuditAcceptanceRecord,
) -> dict[str, object]:
    return {
        "schema_version": ACCEPTANCE_VERIFICATION_SCHEMA_VERSION,
        "status": AuditAcceptanceVerificationStatus.VERIFIED_BINDING.value,
        "handoff_id": handoff.handoff_id,
        "acceptance_record_id": record.acceptance_record_id,
        "decision": record.decision.value,
        "authority_reference": record.authority_reference,
        "decision_reference": record.decision_reference,
        "verification_facts": [fact.value for fact in _VERIFICATION_FACTS],
    }


def build_acceptance_record_verification_envelope(
    handoff_package: AuditAcceptanceHandoffPackage,
    validated_acceptance_record: ValidatedAuditAcceptanceRecord,
) -> AuditAcceptanceVerificationEnvelope:
    """Package deterministic structural verification facts for Stage 15T/15U."""
    handoff = _validate_handoff(handoff_package)
    record = _validate_record(validated_acceptance_record)
    _validate_binding(handoff, record)
    payload = _identity_payload(handoff, record)
    envelope_id = _fingerprint(payload, context="verification envelope identity")
    return AuditAcceptanceVerificationEnvelope(
        schema_version=ACCEPTANCE_VERIFICATION_SCHEMA_VERSION,
        envelope_id=envelope_id,
        status=AuditAcceptanceVerificationStatus.VERIFIED_BINDING,
        handoff_id=handoff.handoff_id,
        acceptance_record_id=record.acceptance_record_id,
        decision=record.decision,
        authority_reference=record.authority_reference,
        decision_reference=record.decision_reference,
        verification_facts=_VERIFICATION_FACTS,
    )
