"""Deterministic approval-readiness gate for Stage 15R output (Stage 15S).

Readiness is not approval.  This module consumes an existing disposition and
does not perform change detection, impact assessment, disposition, validation,
replay, approval, or engineering recomputation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from .change_disposition import (
    AuditChangeDisposition,
    AuditChangeDispositionReason,
    AuditChangeDispositionReasonCode,
    AuditChangeDispositionResult,
)
from .change_impact import AuditChangeImpact, AuditChangeImpactReason
from .comparison import AuditChange, AuditComparisonStatus
from .models import ToleranceDecisionStatus

__all__ = [
    "AuditApprovalReadinessReason",
    "AuditApprovalReadinessReasonCode",
    "AuditApprovalReadinessResult",
    "AuditApprovalReadinessStatus",
    "InvalidAuditApprovalReadinessError",
    "evaluate_audit_approval_readiness",
]


class InvalidAuditApprovalReadinessError(ValueError):
    """Raised when a disposition result cannot safely pass the gate."""


class AuditApprovalReadinessStatus(Enum):
    """Readiness to enter an external approval process, not approval state."""

    READY = "ready"
    ACTION_REQUIRED = "action_required"
    BLOCKED = "blocked"


class AuditApprovalReadinessReasonCode(Enum):
    """Stable reason codes for approval-readiness classification."""

    NO_FURTHER_ACTION_REQUIRED = "no_further_action_required"
    TRACEABILITY_PRESERVED = "traceability_preserved"
    ENGINEERING_REVIEW_PENDING = "engineering_review_pending"
    REVALIDATION_PENDING = "revalidation_pending"
    REPLAY_PENDING = "replay_pending"
    AUDIT_CONDITION_BLOCKS_READINESS = "audit_condition_blocks_readiness"


@dataclass(frozen=True, slots=True)
class AuditApprovalReadinessReason:
    """One readiness reason retaining its authoritative Stage 15R source."""

    code: AuditApprovalReadinessReasonCode
    status: AuditApprovalReadinessStatus
    source_reason: AuditChangeDispositionReason

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "status": self.status.value,
            "source_reason": self.source_reason.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class AuditApprovalReadinessResult:
    """Immutable approval-readiness gate result."""

    status: AuditApprovalReadinessStatus
    is_ready: bool
    comparison_status: AuditComparisonStatus
    source_impact: AuditChangeImpact
    source_disposition: AuditChangeDisposition
    decision_changed: bool
    previous_decision_status: ToleranceDecisionStatus | None
    current_decision_status: ToleranceDecisionStatus | None
    reasons: tuple[AuditApprovalReadinessReason, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "is_ready": self.is_ready,
            "comparison_status": self.comparison_status.value,
            "source_impact": self.source_impact.value,
            "source_disposition": self.source_disposition.value,
            "decision_changed": self.decision_changed,
            "previous_decision_status": (
                self.previous_decision_status.value
                if self.previous_decision_status is not None
                else None
            ),
            "current_decision_status": (
                self.current_decision_status.value
                if self.current_decision_status is not None
                else None
            ),
            "reasons": [reason.as_dict() for reason in self.reasons],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )


_DISPOSITION_STATUS = {
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

_DISPOSITION_REASON = {
    AuditChangeDisposition.ACCEPT: (
        AuditApprovalReadinessReasonCode.NO_FURTHER_ACTION_REQUIRED
    ),
    AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY: (
        AuditApprovalReadinessReasonCode.TRACEABILITY_PRESERVED
    ),
    AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED: (
        AuditApprovalReadinessReasonCode.ENGINEERING_REVIEW_PENDING
    ),
    AuditChangeDisposition.REVALIDATION_REQUIRED: (
        AuditApprovalReadinessReasonCode.REVALIDATION_PENDING
    ),
    AuditChangeDisposition.REPLAY_REQUIRED: (
        AuditApprovalReadinessReasonCode.REPLAY_PENDING
    ),
    AuditChangeDisposition.BLOCKED: (
        AuditApprovalReadinessReasonCode.AUDIT_CONDITION_BLOCKS_READINESS
    ),
}

_REASON_DISPOSITION = {
    AuditChangeDispositionReasonCode.NO_ACTION_REQUIRED: (
        AuditChangeDisposition.ACCEPT
    ),
    AuditChangeDispositionReasonCode.TRACEABILITY_RETENTION_REQUIRED: (
        AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY
    ),
    AuditChangeDispositionReasonCode.ENGINEERING_EVIDENCE_REVIEW_REQUIRED: (
        AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED
    ),
    AuditChangeDispositionReasonCode.COMPLIANCE_REVALIDATION_REQUIRED: (
        AuditChangeDisposition.REVALIDATION_REQUIRED
    ),
    AuditChangeDispositionReasonCode.DECISION_REVALIDATION_REQUIRED: (
        AuditChangeDisposition.REVALIDATION_REQUIRED
    ),
    AuditChangeDispositionReasonCode.REPLAYABILITY_REESTABLISHED: (
        AuditChangeDisposition.REPLAY_REQUIRED
    ),
    AuditChangeDispositionReasonCode.TRUSTWORTHY_DISPOSITION_BLOCKED: (
        AuditChangeDisposition.BLOCKED
    ),
}

_IMPACT_DISPOSITIONS = {
    AuditChangeImpact.NO_IMPACT: frozenset({AuditChangeDisposition.ACCEPT}),
    AuditChangeImpact.TRACEABILITY_ONLY: frozenset(
        {AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY}
    ),
    AuditChangeImpact.ENGINEERING_EVIDENCE: frozenset(
        {AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED}
    ),
    AuditChangeImpact.COMPLIANCE_RELEVANT: frozenset(
        {
            AuditChangeDisposition.REVALIDATION_REQUIRED,
            AuditChangeDisposition.REPLAY_REQUIRED,
        }
    ),
    AuditChangeImpact.DECISION_CHANGING: frozenset(
        {
            AuditChangeDisposition.REVALIDATION_REQUIRED,
            AuditChangeDisposition.REPLAY_REQUIRED,
        }
    ),
    AuditChangeImpact.REPLAY_BLOCKING: frozenset({AuditChangeDisposition.BLOCKED}),
}

_STATUS_PRECEDENCE = (
    AuditApprovalReadinessStatus.BLOCKED,
    AuditApprovalReadinessStatus.ACTION_REQUIRED,
    AuditApprovalReadinessStatus.READY,
)


def _validate_reason_fields(reason: AuditChangeDispositionReason, index: int) -> None:
    if not isinstance(reason.code, AuditChangeDispositionReasonCode):
        raise InvalidAuditApprovalReadinessError(f"reasons[{index}].code is invalid")
    if not isinstance(reason.disposition, AuditChangeDisposition):
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}].disposition is invalid"
        )
    if not isinstance(reason.source_impact, AuditChangeImpact):
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}].source_impact is invalid"
        )
    if not isinstance(reason.source_impact_reason, AuditChangeImpactReason):
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}].source_impact_reason is invalid"
        )
    if reason.change is not None and not isinstance(reason.change, AuditChange):
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}].change must be an AuditChange or None"
        )


def _validate_source_reason(reason: object, index: int) -> AuditChangeDispositionReason:
    if not isinstance(reason, AuditChangeDispositionReason):
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}] must be an AuditChangeDispositionReason"
        )
    _validate_reason_fields(reason, index)
    expected = _REASON_DISPOSITION.get(reason.code)
    if expected is None or reason.disposition is not expected:
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}] has inconsistent code and disposition"
        )
    allowed = _IMPACT_DISPOSITIONS.get(reason.source_impact)
    if allowed is None or reason.disposition not in allowed:
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}] has inconsistent impact and disposition"
        )
    if reason.disposition is AuditChangeDisposition.ACCEPT:
        if reason.change is not None:
            raise InvalidAuditApprovalReadinessError(
                "ACCEPT no-action reason must not fabricate a change"
            )
    elif reason.change is None:
        raise InvalidAuditApprovalReadinessError(
            f"reasons[{index}] must retain its source change"
        )
    return reason


def _validated_reasons(
    result: AuditChangeDispositionResult,
) -> tuple[AuditChangeDispositionReason, ...]:
    if not isinstance(result.reasons, tuple) or not result.reasons:
        raise InvalidAuditApprovalReadinessError(
            "disposition reasons must be a non-empty tuple"
        )
    reasons = tuple(
        _validate_source_reason(reason, index)
        for index, reason in enumerate(result.reasons)
    )
    if len(set(reasons)) != len(reasons):
        raise InvalidAuditApprovalReadinessError(
            "disposition result contains duplicate reasons"
        )
    if not any(reason.disposition is result.disposition for reason in reasons):
        raise InvalidAuditApprovalReadinessError(
            "source disposition is not represented by its reasons"
        )
    if not any(reason.source_impact is result.source_impact for reason in reasons):
        raise InvalidAuditApprovalReadinessError(
            "source impact is not represented by its reasons"
        )
    return reasons


def _validate_decision_transition(result: AuditChangeDispositionResult) -> None:
    previous = result.previous_decision_status
    current = result.current_decision_status
    transition_represented = any(
        reason.source_impact is AuditChangeImpact.DECISION_CHANGING
        for reason in result.reasons
    )
    if transition_represented is not result.decision_changed:
        raise InvalidAuditApprovalReadinessError(
            "decision transition flag disagrees with disposition reasons"
        )
    if result.decision_changed:
        if not isinstance(previous, ToleranceDecisionStatus) or not isinstance(
            current, ToleranceDecisionStatus
        ):
            raise InvalidAuditApprovalReadinessError(
                "decision_changed requires typed previous and current states"
            )
        if previous is current:
            raise InvalidAuditApprovalReadinessError(
                "decision transition requires distinct states"
            )
        if result.source_impact not in {
            AuditChangeImpact.DECISION_CHANGING,
            AuditChangeImpact.REPLAY_BLOCKING,
        }:
            raise InvalidAuditApprovalReadinessError(
                "decision transition conflicts with source impact"
            )
    elif previous is not None or current is not None:
        raise InvalidAuditApprovalReadinessError(
            "unchanged decision must not expose transition states"
        )


def _validate_comparison_invariants(result: AuditChangeDispositionResult) -> None:
    if result.comparison_status is AuditComparisonStatus.INCOMPATIBLE and (
        result.disposition is not AuditChangeDisposition.BLOCKED
    ):
        raise InvalidAuditApprovalReadinessError(
            "incompatible comparison disposition must be blocked"
        )
    if result.comparison_status is AuditComparisonStatus.IDENTICAL:
        if (
            result.source_impact is not AuditChangeImpact.NO_IMPACT
            or result.disposition is not AuditChangeDisposition.ACCEPT
        ):
            raise InvalidAuditApprovalReadinessError(
                "identical comparison must use the no-impact accept disposition"
            )
    elif (
        result.source_impact is AuditChangeImpact.NO_IMPACT
        or result.disposition is AuditChangeDisposition.ACCEPT
    ):
        raise InvalidAuditApprovalReadinessError(
            "changed comparison cannot use the no-impact accept disposition"
        )


def _validate_result(result: object) -> AuditChangeDispositionResult:
    if not isinstance(result, AuditChangeDispositionResult):
        raise InvalidAuditApprovalReadinessError(
            "disposition_result must be an AuditChangeDispositionResult"
        )
    if not isinstance(result.comparison_status, AuditComparisonStatus):
        raise InvalidAuditApprovalReadinessError("comparison status is invalid")
    if not isinstance(result.source_impact, AuditChangeImpact):
        raise InvalidAuditApprovalReadinessError("source impact is invalid")
    if not isinstance(result.disposition, AuditChangeDisposition):
        raise InvalidAuditApprovalReadinessError("source disposition is invalid")
    if not isinstance(result.decision_changed, bool):
        raise InvalidAuditApprovalReadinessError("decision_changed must be boolean")
    allowed = _IMPACT_DISPOSITIONS.get(result.source_impact)
    if allowed is None or result.disposition not in allowed:
        raise InvalidAuditApprovalReadinessError(
            "source impact and disposition are inconsistent"
        )
    _validate_comparison_invariants(result)
    _validated_reasons(result)
    _validate_decision_transition(result)
    return result


def _reason_status(
    reason: AuditChangeDispositionReason,
) -> AuditApprovalReadinessReason:
    status = _DISPOSITION_STATUS.get(reason.disposition)
    code = _DISPOSITION_REASON.get(reason.disposition)
    if status is None or code is None:
        raise InvalidAuditApprovalReadinessError(
            f"unmapped disposition {reason.disposition.value!r}"
        )
    return AuditApprovalReadinessReason(
        code=code,
        status=status,
        source_reason=reason,
    )


def _overall_status(
    reasons: tuple[AuditApprovalReadinessReason, ...],
) -> AuditApprovalReadinessStatus:
    present = {reason.status for reason in reasons}
    for status in _STATUS_PRECEDENCE:
        if status in present:
            return status
    raise InvalidAuditApprovalReadinessError("readiness result has no reason")


def evaluate_audit_approval_readiness(
    disposition_result: AuditChangeDispositionResult,
) -> AuditApprovalReadinessResult:
    """Evaluate readiness without performing or recording approval."""
    result = _validate_result(disposition_result)
    reasons = tuple(_reason_status(reason) for reason in result.reasons)
    status = _overall_status(reasons)
    expected = _DISPOSITION_STATUS[result.disposition]
    if status is not expected:
        raise InvalidAuditApprovalReadinessError(
            "readiness reasons conflict with source disposition"
        )
    return AuditApprovalReadinessResult(
        status=status,
        is_ready=status is AuditApprovalReadinessStatus.READY,
        comparison_status=result.comparison_status,
        source_impact=result.source_impact,
        source_disposition=result.disposition,
        decision_changed=result.decision_changed,
        previous_decision_status=result.previous_decision_status,
        current_decision_status=result.current_decision_status,
        reasons=reasons,
    )
