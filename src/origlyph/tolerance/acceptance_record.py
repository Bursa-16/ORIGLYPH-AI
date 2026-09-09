"""Deterministic intake of externally supplied governed acceptance records.

Stage 15U validates and preserves an external decision.  It does not choose a
decision, verify a human identity, or invoke any Stage 15P--15T builder.
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

__all__ = [
    "ACCEPTANCE_RECORD_SCHEMA_VERSION",
    "VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION",
    "AuditAcceptanceDecision",
    "AuditAcceptanceRecord",
    "InvalidAuditAcceptanceRecordError",
    "ValidatedAuditAcceptanceRecord",
    "validate_audit_acceptance_record",
]


ACCEPTANCE_RECORD_SCHEMA_VERSION = "origlyph.tolerance.audit_acceptance_record.v1"
VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION = (
    "origlyph.tolerance.validated_audit_acceptance_record.v1"
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InvalidAuditAcceptanceRecordError(ValueError):
    """Raised when an external record cannot be safely bound to a handoff."""


class AuditAcceptanceDecision(Enum):
    """Decision explicitly supplied by an external governed authority."""

    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED_FOR_ACTION = "returned_for_action"


@dataclass(frozen=True, slots=True)
class AuditAcceptanceRecord:
    """Immutable external record supplied to the Stage 15U trust boundary."""

    schema_version: str
    handoff_id: str
    decision: AuditAcceptanceDecision
    authority_reference: str
    decision_reference: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "handoff_id": self.handoff_id,
            "decision": self.decision.value,
            "authority_reference": self.authority_reference,
            "decision_reference": self.decision_reference,
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="acceptance record")


@dataclass(frozen=True, slots=True)
class ValidatedAuditAcceptanceRecord:
    """Immutable proof of deterministic record intake and handoff binding."""

    schema_version: str
    acceptance_record_id: str
    acceptance_record_schema_version: str
    handoff_id: str
    handoff_status: AuditAcceptanceHandoffStatus
    decision: AuditAcceptanceDecision
    authority_reference: str
    decision_reference: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "acceptance_record_id": self.acceptance_record_id,
            "acceptance_record_schema_version": (
                self.acceptance_record_schema_version
            ),
            "handoff_id": self.handoff_id,
            "handoff_status": self.handoff_status.value,
            "decision": self.decision.value,
            "authority_reference": self.authority_reference,
            "decision_reference": self.decision_reference,
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="validated acceptance record")


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
        raise InvalidAuditAcceptanceRecordError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object, *, context: str) -> str:
    canonical = _canonical_json(payload, context=context)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_handoff(value: object) -> AuditAcceptanceHandoffPackage:
    if type(value) is not AuditAcceptanceHandoffPackage:
        raise InvalidAuditAcceptanceRecordError(
            "handoff_package must be an AuditAcceptanceHandoffPackage"
        )
    handoff = value
    if handoff.schema_version != ACCEPTANCE_HANDOFF_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceRecordError("unsupported handoff schema version")
    if not isinstance(handoff.status, AuditAcceptanceHandoffStatus):
        raise InvalidAuditAcceptanceRecordError("handoff status is invalid")
    if not isinstance(handoff.handoff_id, str) or not _SHA256_PATTERN.fullmatch(
        handoff.handoff_id
    ):
        raise InvalidAuditAcceptanceRecordError(
            "handoff_id must be a lowercase SHA-256 fingerprint"
        )
    try:
        payload = handoff.as_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceRecordError(
            f"handoff package is malformed: {exc}"
        ) from exc
    expected_keys = {
        "schema_version",
        "handoff_id",
        "baseline_package_id",
        "candidate_package_id",
        "status",
        "comparison_result",
        "impact_result",
        "disposition_result",
        "readiness_result",
    }
    if set(payload) != expected_keys:
        raise InvalidAuditAcceptanceRecordError(
            "handoff package does not have canonical fields"
        )
    identity_payload = dict(payload)
    recorded_id = identity_payload.pop("handoff_id")
    if recorded_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceRecordError("handoff identity is inconsistent")
    expected_id = _fingerprint(identity_payload, context="handoff identity")
    if expected_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceRecordError("handoff fingerprint is invalid")
    return handoff


def _require_canonical_reference(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise InvalidAuditAcceptanceRecordError(
            f"{field} must be a non-empty canonical string"
        )
    return value


def _validate_record(value: object) -> AuditAcceptanceRecord:
    if type(value) is not AuditAcceptanceRecord:
        raise InvalidAuditAcceptanceRecordError(
            "acceptance_record must be an AuditAcceptanceRecord"
        )
    record = value
    if record.schema_version != ACCEPTANCE_RECORD_SCHEMA_VERSION:
        raise InvalidAuditAcceptanceRecordError(
            "unsupported acceptance record schema version"
        )
    if not isinstance(record.handoff_id, str) or not _SHA256_PATTERN.fullmatch(
        record.handoff_id
    ):
        raise InvalidAuditAcceptanceRecordError(
            "acceptance record handoff_id must be a lowercase SHA-256 fingerprint"
        )
    if not isinstance(record.decision, AuditAcceptanceDecision):
        raise InvalidAuditAcceptanceRecordError("acceptance decision is invalid")
    _require_canonical_reference(
        record.authority_reference,
        field="authority_reference",
    )
    _require_canonical_reference(
        record.decision_reference,
        field="decision_reference",
    )
    _canonical_json(record.as_dict(), context="acceptance record")
    return record


def _validate_decision_consistency(
    status: AuditAcceptanceHandoffStatus,
    decision: AuditAcceptanceDecision,
) -> None:
    if (
        status
        in {
            AuditAcceptanceHandoffStatus.ACTION_REQUIRED,
            AuditAcceptanceHandoffStatus.BLOCKED,
        }
        and decision is AuditAcceptanceDecision.APPROVED
    ):
        raise InvalidAuditAcceptanceRecordError(
            f"approved decision conflicts with {status.value} handoff"
        )


def _identity_payload(
    handoff: AuditAcceptanceHandoffPackage,
    record: AuditAcceptanceRecord,
) -> dict[str, object]:
    return {
        "schema_version": VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION,
        "acceptance_record_schema_version": record.schema_version,
        "handoff_id": handoff.handoff_id,
        "handoff_status": handoff.status.value,
        "decision": record.decision.value,
        "authority_reference": record.authority_reference,
        "decision_reference": record.decision_reference,
    }


def validate_audit_acceptance_record(
    handoff_package: AuditAcceptanceHandoffPackage,
    acceptance_record: AuditAcceptanceRecord,
) -> ValidatedAuditAcceptanceRecord:
    """Validate and preserve one externally supplied acceptance record."""
    handoff = _validate_handoff(handoff_package)
    record = _validate_record(acceptance_record)
    if record.handoff_id != handoff.handoff_id:
        raise InvalidAuditAcceptanceRecordError(
            "acceptance record is not bound to the supplied handoff"
        )
    _validate_decision_consistency(handoff.status, record.decision)
    payload = _identity_payload(handoff, record)
    acceptance_record_id = _fingerprint(
        payload,
        context="validated acceptance record identity",
    )
    return ValidatedAuditAcceptanceRecord(
        schema_version=VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION,
        acceptance_record_id=acceptance_record_id,
        acceptance_record_schema_version=record.schema_version,
        handoff_id=handoff.handoff_id,
        handoff_status=handoff.status,
        decision=record.decision,
        authority_reference=record.authority_reference,
        decision_reference=record.decision_reference,
    )
