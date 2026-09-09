"""Deterministic governed-acceptance handoff package (Stage 15T).

The builder packages authoritative Stage 15P--15S outputs without invoking
those stages, replaying calculations, fabricating approval, or mutating input.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from .approval_readiness import (
    AuditApprovalReadinessReason,
    AuditApprovalReadinessResult,
    AuditApprovalReadinessStatus,
)
from .change_disposition import (
    AuditChangeDisposition,
    AuditChangeDispositionReason,
    AuditChangeDispositionResult,
)
from .change_impact import AuditChangeImpactAssessment, AuditChangeImpactResult
from .comparison import AuditPackageComparisonResult

__all__ = [
    "ACCEPTANCE_HANDOFF_SCHEMA_VERSION",
    "AuditAcceptanceHandoffPackage",
    "AuditAcceptanceHandoffStatus",
    "InvalidAuditAcceptanceHandoffError",
    "build_audit_acceptance_handoff",
]


ACCEPTANCE_HANDOFF_SCHEMA_VERSION = "origlyph.tolerance.audit_acceptance_handoff.v1"


class InvalidAuditAcceptanceHandoffError(ValueError):
    """Raised when the authoritative handoff chain is malformed."""


class AuditAcceptanceHandoffStatus(Enum):
    """Governed-acceptance handoff state, not an approval decision."""

    READY_FOR_GOVERNED_ACCEPTANCE = "ready_for_governed_acceptance"
    ACTION_REQUIRED = "action_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AuditAcceptanceHandoffPackage:
    """Immutable deterministic package of Stage 15P--15S outputs."""

    schema_version: str
    handoff_id: str
    baseline_package_id: str
    candidate_package_id: str
    status: AuditAcceptanceHandoffStatus
    comparison_result: AuditPackageComparisonResult
    impact_result: AuditChangeImpactResult
    disposition_result: AuditChangeDispositionResult
    readiness_result: AuditApprovalReadinessResult

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "handoff_id": self.handoff_id,
            "baseline_package_id": self.baseline_package_id,
            "candidate_package_id": self.candidate_package_id,
            "status": self.status.value,
            "comparison_result": self.comparison_result.as_dict(),
            "impact_result": self.impact_result.as_dict(),
            "disposition_result": self.disposition_result.as_dict(),
            "readiness_result": self.readiness_result.as_dict(),
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="handoff package")


_READINESS_STATUS = {
    AuditApprovalReadinessStatus.READY: (
        AuditAcceptanceHandoffStatus.READY_FOR_GOVERNED_ACCEPTANCE
    ),
    AuditApprovalReadinessStatus.ACTION_REQUIRED: (
        AuditAcceptanceHandoffStatus.ACTION_REQUIRED
    ),
    AuditApprovalReadinessStatus.BLOCKED: AuditAcceptanceHandoffStatus.BLOCKED,
}

_DISPOSITION_READINESS = {
    AuditChangeDisposition.ACCEPT: AuditApprovalReadinessStatus.READY,
    AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY: (
        AuditApprovalReadinessStatus.READY
    ),
    AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED: (
        AuditApprovalReadinessStatus.ACTION_REQUIRED
    ),
    AuditChangeDisposition.REVALIDATION_REQUIRED: (
        AuditApprovalReadinessStatus.ACTION_REQUIRED
    ),
    AuditChangeDisposition.REPLAY_REQUIRED: (
        AuditApprovalReadinessStatus.ACTION_REQUIRED
    ),
    AuditChangeDisposition.BLOCKED: AuditApprovalReadinessStatus.BLOCKED,
}

_READINESS_PRECEDENCE = (
    AuditApprovalReadinessStatus.BLOCKED,
    AuditApprovalReadinessStatus.ACTION_REQUIRED,
    AuditApprovalReadinessStatus.READY,
)


def _canonical_json(payload: object, *, context: str) -> str:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidAuditAcceptanceHandoffError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object) -> str:
    canonical = _canonical_json(payload, context="handoff identity")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_types(
    comparison_result: object,
    impact_result: object,
    disposition_result: object,
    readiness_result: object,
) -> tuple[
    AuditPackageComparisonResult,
    AuditChangeImpactResult,
    AuditChangeDispositionResult,
    AuditApprovalReadinessResult,
]:
    if not isinstance(comparison_result, AuditPackageComparisonResult):
        raise InvalidAuditAcceptanceHandoffError(
            "comparison_result must be an AuditPackageComparisonResult"
        )
    if not isinstance(impact_result, AuditChangeImpactResult):
        raise InvalidAuditAcceptanceHandoffError(
            "impact_result must be an AuditChangeImpactResult"
        )
    if not isinstance(disposition_result, AuditChangeDispositionResult):
        raise InvalidAuditAcceptanceHandoffError(
            "disposition_result must be an AuditChangeDispositionResult"
        )
    if not isinstance(readiness_result, AuditApprovalReadinessResult):
        raise InvalidAuditAcceptanceHandoffError(
            "readiness_result must be an AuditApprovalReadinessResult"
        )
    return comparison_result, impact_result, disposition_result, readiness_result


def _validate_package_ids(comparison: AuditPackageComparisonResult) -> None:
    for field, value in (
        ("baseline_package_id", comparison.baseline_package_id),
        ("candidate_package_id", comparison.candidate_package_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise InvalidAuditAcceptanceHandoffError(
                f"comparison {field} must be a non-empty string"
            )


def _validate_comparison_to_impact(
    comparison: AuditPackageComparisonResult,
    impact: AuditChangeImpactResult,
) -> None:
    if impact.comparison_status is not comparison.status:
        raise InvalidAuditAcceptanceHandoffError(
            "impact comparison status does not match Stage 15P"
        )
    if not isinstance(impact.assessed_changes, tuple):
        raise InvalidAuditAcceptanceHandoffError(
            "impact assessed_changes must be a tuple"
        )
    assessments = impact.assessed_changes
    if not all(isinstance(item, AuditChangeImpactAssessment) for item in assessments):
        raise InvalidAuditAcceptanceHandoffError(
            "impact result contains an invalid assessment"
        )
    if tuple(item.change for item in assessments) != comparison.changes:
        raise InvalidAuditAcceptanceHandoffError(
            "impact assessments do not preserve Stage 15P changes and order"
        )


def _validate_impact_to_disposition(
    impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
) -> None:
    fields = (
        ("comparison_status", disposition.comparison_status, impact.comparison_status),
        ("source_impact", disposition.source_impact, impact.overall_impact),
        ("decision_changed", disposition.decision_changed, impact.decision_changed),
        (
            "previous_decision_status",
            disposition.previous_decision_status,
            impact.previous_decision_status,
        ),
        (
            "current_decision_status",
            disposition.current_decision_status,
            impact.current_decision_status,
        ),
    )
    for field, actual, expected in fields:
        if actual != expected:
            raise InvalidAuditAcceptanceHandoffError(
                f"disposition {field} does not match Stage 15Q"
            )
    if not isinstance(disposition.reasons, tuple) or not disposition.reasons:
        raise InvalidAuditAcceptanceHandoffError(
            "disposition reasons must be a non-empty tuple"
        )
    if not all(
        isinstance(reason, AuditChangeDispositionReason)
        for reason in disposition.reasons
    ):
        raise InvalidAuditAcceptanceHandoffError(
            "disposition result contains an invalid reason"
        )
    if impact.assessed_changes:
        expected = tuple(
            (item.change, item.impact, item.reason) for item in impact.assessed_changes
        )
        actual = tuple(
            (reason.change, reason.source_impact, reason.source_impact_reason)
            for reason in disposition.reasons
        )
        if actual != expected:
            raise InvalidAuditAcceptanceHandoffError(
                "disposition reasons do not preserve Stage 15Q assessments"
            )
    elif len(disposition.reasons) != 1 or disposition.reasons[0].change is not None:
        raise InvalidAuditAcceptanceHandoffError(
            "no-impact disposition must have one change-free reason"
        )


def _validate_readiness_reasons(
    disposition: AuditChangeDispositionResult,
    readiness: AuditApprovalReadinessResult,
) -> None:
    if not isinstance(readiness.reasons, tuple) or not readiness.reasons:
        raise InvalidAuditAcceptanceHandoffError(
            "readiness reasons must be a non-empty tuple"
        )
    if not all(
        isinstance(reason, AuditApprovalReadinessReason) for reason in readiness.reasons
    ):
        raise InvalidAuditAcceptanceHandoffError(
            "readiness result contains an invalid reason"
        )
    if tuple(reason.source_reason for reason in readiness.reasons) != (
        disposition.reasons
    ):
        raise InvalidAuditAcceptanceHandoffError(
            "readiness reasons do not preserve Stage 15R reasons and order"
        )
    for index, reason in enumerate(readiness.reasons):
        expected = _DISPOSITION_READINESS.get(reason.source_reason.disposition)
        if expected is None or reason.status is not expected:
            raise InvalidAuditAcceptanceHandoffError(
                f"readiness reason {index} conflicts with its Stage 15R source"
            )
    expected_status = next(
        status
        for status in _READINESS_PRECEDENCE
        if any(reason.status is status for reason in readiness.reasons)
    )
    if readiness.status is not expected_status:
        raise InvalidAuditAcceptanceHandoffError(
            "readiness status conflicts with its ordered reason set"
        )


def _validate_disposition_to_readiness(
    disposition: AuditChangeDispositionResult,
    readiness: AuditApprovalReadinessResult,
) -> None:
    fields = (
        (
            "comparison_status",
            readiness.comparison_status,
            disposition.comparison_status,
        ),
        ("source_impact", readiness.source_impact, disposition.source_impact),
        (
            "source_disposition",
            readiness.source_disposition,
            disposition.disposition,
        ),
        ("decision_changed", readiness.decision_changed, disposition.decision_changed),
        (
            "previous_decision_status",
            readiness.previous_decision_status,
            disposition.previous_decision_status,
        ),
        (
            "current_decision_status",
            readiness.current_decision_status,
            disposition.current_decision_status,
        ),
    )
    for field, actual, expected in fields:
        if actual != expected:
            raise InvalidAuditAcceptanceHandoffError(
                f"readiness {field} does not match Stage 15R"
            )
    if not isinstance(readiness.status, AuditApprovalReadinessStatus):
        raise InvalidAuditAcceptanceHandoffError("readiness status is invalid")
    if not isinstance(readiness.is_ready, bool):
        raise InvalidAuditAcceptanceHandoffError("readiness is_ready must be boolean")
    if readiness.is_ready is not (
        readiness.status is AuditApprovalReadinessStatus.READY
    ):
        raise InvalidAuditAcceptanceHandoffError(
            "readiness boolean disagrees with readiness status"
        )
    _validate_readiness_reasons(disposition, readiness)


def _identity_payload(
    comparison: AuditPackageComparisonResult,
    impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
    readiness: AuditApprovalReadinessResult,
    status: AuditAcceptanceHandoffStatus,
) -> dict[str, object]:
    return {
        "schema_version": ACCEPTANCE_HANDOFF_SCHEMA_VERSION,
        "baseline_package_id": comparison.baseline_package_id,
        "candidate_package_id": comparison.candidate_package_id,
        "status": status.value,
        "comparison_result": comparison.as_dict(),
        "impact_result": impact.as_dict(),
        "disposition_result": disposition.as_dict(),
        "readiness_result": readiness.as_dict(),
    }


def build_audit_acceptance_handoff(
    comparison_result: AuditPackageComparisonResult,
    impact_result: AuditChangeImpactResult,
    disposition_result: AuditChangeDispositionResult,
    readiness_result: AuditApprovalReadinessResult,
) -> AuditAcceptanceHandoffPackage:
    """Package a consistent Stage 15P--15S chain for governed acceptance."""
    comparison, impact, disposition, readiness = _validate_types(
        comparison_result,
        impact_result,
        disposition_result,
        readiness_result,
    )
    _validate_package_ids(comparison)
    _validate_comparison_to_impact(comparison, impact)
    _validate_impact_to_disposition(impact, disposition)
    _validate_disposition_to_readiness(disposition, readiness)
    status = _READINESS_STATUS.get(readiness.status)
    if status is None:
        raise InvalidAuditAcceptanceHandoffError(
            f"unmapped readiness status {readiness.status.value!r}"
        )
    payload = _identity_payload(
        comparison,
        impact,
        disposition,
        readiness,
        status,
    )
    handoff_id = _fingerprint(payload)
    return AuditAcceptanceHandoffPackage(
        schema_version=ACCEPTANCE_HANDOFF_SCHEMA_VERSION,
        handoff_id=handoff_id,
        baseline_package_id=comparison.baseline_package_id,
        candidate_package_id=comparison.candidate_package_id,
        status=status,
        comparison_result=comparison,
        impact_result=impact,
        disposition_result=disposition,
        readiness_result=readiness,
    )
