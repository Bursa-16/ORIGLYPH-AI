"""Deterministic disposition of Stage 15Q audit-change impacts (Stage 15R).

This module consumes an existing impact result.  It does not compare packages,
reassess impact, perform approval, replay calculations, or call engineering
engines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from .audit import ReplayabilityStatus
from .change_impact import (
    AuditChangeImpact,
    AuditChangeImpactAssessment,
    AuditChangeImpactReason,
    AuditChangeImpactResult,
)
from .comparison import AuditChange, AuditChangeCode, AuditComparisonStatus
from .models import ToleranceDecisionStatus

__all__ = [
    "AuditChangeDisposition",
    "AuditChangeDispositionReason",
    "AuditChangeDispositionReasonCode",
    "AuditChangeDispositionResult",
    "InvalidAuditChangeDispositionError",
    "determine_audit_change_disposition",
]


class InvalidAuditChangeDispositionError(ValueError):
    """Raised when an impact result cannot be safely dispositioned."""


class AuditChangeDisposition(Enum):
    """Governance action required by an authoritative Stage 15Q impact."""

    ACCEPT = "accept"
    ACCEPT_WITH_TRACEABILITY = "accept_with_traceability"
    ENGINEERING_REVIEW_REQUIRED = "engineering_review_required"
    REVALIDATION_REQUIRED = "revalidation_required"
    REPLAY_REQUIRED = "replay_required"
    BLOCKED = "blocked"


class AuditChangeDispositionReasonCode(Enum):
    """Stable machine-readable rationale for a disposition."""

    NO_ACTION_REQUIRED = "no_action_required"
    TRACEABILITY_RETENTION_REQUIRED = "traceability_retention_required"
    ENGINEERING_EVIDENCE_REVIEW_REQUIRED = "engineering_evidence_review_required"
    COMPLIANCE_REVALIDATION_REQUIRED = "compliance_revalidation_required"
    DECISION_REVALIDATION_REQUIRED = "decision_revalidation_required"
    REPLAYABILITY_REESTABLISHED = "replayability_reestablished"
    TRUSTWORTHY_DISPOSITION_BLOCKED = "trustworthy_disposition_blocked"


@dataclass(frozen=True, slots=True)
class AuditChangeDispositionReason:
    """One structured reason, retaining its Stage 15Q source assessment."""

    code: AuditChangeDispositionReasonCode
    disposition: AuditChangeDisposition
    source_impact: AuditChangeImpact
    source_impact_reason: AuditChangeImpactReason
    change: AuditChange | None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "disposition": self.disposition.value,
            "source_impact": self.source_impact.value,
            "source_impact_reason": self.source_impact_reason.value,
            "change": self.change.as_dict() if self.change is not None else None,
        }


@dataclass(frozen=True, slots=True)
class AuditChangeDispositionResult:
    """Immutable deterministic disposition for one Stage 15Q result."""

    comparison_status: AuditComparisonStatus
    source_impact: AuditChangeImpact
    disposition: AuditChangeDisposition
    decision_changed: bool
    previous_decision_status: ToleranceDecisionStatus | None
    current_decision_status: ToleranceDecisionStatus | None
    reasons: tuple[AuditChangeDispositionReason, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "comparison_status": self.comparison_status.value,
            "source_impact": self.source_impact.value,
            "disposition": self.disposition.value,
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


_IMPACT_DISPOSITION = {
    AuditChangeImpact.NO_IMPACT: AuditChangeDisposition.ACCEPT,
    AuditChangeImpact.TRACEABILITY_ONLY: (
        AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY
    ),
    AuditChangeImpact.ENGINEERING_EVIDENCE: (
        AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED
    ),
    AuditChangeImpact.COMPLIANCE_RELEVANT: (
        AuditChangeDisposition.REVALIDATION_REQUIRED
    ),
    AuditChangeImpact.DECISION_CHANGING: (AuditChangeDisposition.REVALIDATION_REQUIRED),
    AuditChangeImpact.REPLAY_BLOCKING: AuditChangeDisposition.BLOCKED,
}

_DISPOSITION_PRECEDENCE = (
    AuditChangeDisposition.BLOCKED,
    AuditChangeDisposition.REPLAY_REQUIRED,
    AuditChangeDisposition.REVALIDATION_REQUIRED,
    AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED,
    AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY,
    AuditChangeDisposition.ACCEPT,
)

_VALID_IMPACT_REASONS = {
    AuditChangeImpact.TRACEABILITY_ONLY: frozenset(
        {AuditChangeImpactReason.IDENTITY_OR_TRACEABILITY_CHANGED}
    ),
    AuditChangeImpact.ENGINEERING_EVIDENCE: frozenset(
        {AuditChangeImpactReason.ENGINEERING_EVIDENCE_CHANGED}
    ),
    AuditChangeImpact.COMPLIANCE_RELEVANT: frozenset(
        {AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED}
    ),
    AuditChangeImpact.DECISION_CHANGING: frozenset(
        {AuditChangeImpactReason.DECISION_STATUS_TRANSITION}
    ),
    AuditChangeImpact.REPLAY_BLOCKING: frozenset(
        {
            AuditChangeImpactReason.INTEGRITY_NOT_TRUSTWORTHY,
            AuditChangeImpactReason.REPLAYABILITY_LOST,
            AuditChangeImpactReason.STRUCTURALLY_INCOMPATIBLE,
        }
    ),
}


def _validate_assessment(assessment: object, index: int) -> AuditChangeImpactAssessment:
    if not isinstance(assessment, AuditChangeImpactAssessment):
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}] must be an AuditChangeImpactAssessment"
        )
    if not isinstance(assessment.change, AuditChange):
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}].change must be an AuditChange"
        )
    if not isinstance(assessment.change.code, AuditChangeCode):
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}].change code is invalid"
        )
    if not isinstance(assessment.impact, AuditChangeImpact):
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}].impact is invalid"
        )
    if not isinstance(assessment.reason, AuditChangeImpactReason):
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}].reason is invalid"
        )
    if assessment.impact is AuditChangeImpact.NO_IMPACT:
        raise InvalidAuditChangeDispositionError(
            "individual change assessments cannot have NO_IMPACT"
        )
    valid_reasons = _VALID_IMPACT_REASONS.get(assessment.impact)
    if valid_reasons is None:
        raise InvalidAuditChangeDispositionError(
            f"unmapped impact {assessment.impact.value!r}"
        )
    if assessment.reason not in valid_reasons:
        raise InvalidAuditChangeDispositionError(
            f"assessed_changes[{index}] has inconsistent impact reason"
        )
    return assessment


def _validate_decision_transition(result: AuditChangeImpactResult) -> None:
    previous = result.previous_decision_status
    current = result.current_decision_status
    transition_assessed = any(
        item.impact is AuditChangeImpact.DECISION_CHANGING
        for item in result.assessed_changes
    )
    if transition_assessed is not result.decision_changed:
        raise InvalidAuditChangeDispositionError(
            "decision transition flag disagrees with assessed impacts"
        )
    if result.decision_changed:
        if not isinstance(previous, ToleranceDecisionStatus) or not isinstance(
            current, ToleranceDecisionStatus
        ):
            raise InvalidAuditChangeDispositionError(
                "decision_changed requires both typed decision states"
            )
        if previous is current:
            raise InvalidAuditChangeDispositionError(
                "decision transition requires distinct decision states"
            )
        if result.overall_impact not in {
            AuditChangeImpact.DECISION_CHANGING,
            AuditChangeImpact.REPLAY_BLOCKING,
        }:
            raise InvalidAuditChangeDispositionError(
                "decision transition is inconsistent with overall impact"
            )
    elif previous is not None or current is not None:
        raise InvalidAuditChangeDispositionError(
            "unchanged decision must not expose transition states"
        )


def _validated_assessments(
    result: AuditChangeImpactResult,
) -> tuple[AuditChangeImpactAssessment, ...]:
    if not isinstance(result.assessed_changes, tuple):
        raise InvalidAuditChangeDispositionError("assessed_changes must be a tuple")
    assessments = tuple(
        _validate_assessment(item, index)
        for index, item in enumerate(result.assessed_changes)
    )
    if len(set(assessments)) != len(assessments):
        raise InvalidAuditChangeDispositionError(
            "impact result contains duplicate assessments"
        )
    return assessments


def _validate_status_invariants(
    result: AuditChangeImpactResult,
    assessments: tuple[AuditChangeImpactAssessment, ...],
) -> None:
    if result.comparison_status is AuditComparisonStatus.IDENTICAL:
        if assessments or result.overall_impact is not AuditChangeImpact.NO_IMPACT:
            raise InvalidAuditChangeDispositionError(
                "IDENTICAL impact result must be empty and have NO_IMPACT"
            )
    elif not assessments or result.overall_impact is AuditChangeImpact.NO_IMPACT:
        raise InvalidAuditChangeDispositionError(
            "changed impact result requires assessed changes and nonzero impact"
        )
    if result.comparison_status is AuditComparisonStatus.INCOMPATIBLE and (
        result.overall_impact is not AuditChangeImpact.REPLAY_BLOCKING
    ):
        raise InvalidAuditChangeDispositionError(
            "INCOMPATIBLE comparison impact must be replay blocking"
        )
    if assessments and not any(
        item.impact is result.overall_impact for item in assessments
    ):
        raise InvalidAuditChangeDispositionError(
            "overall impact is not represented by an assessed change"
        )
    if (
        any(item.impact is AuditChangeImpact.REPLAY_BLOCKING for item in assessments)
        and result.overall_impact is not AuditChangeImpact.REPLAY_BLOCKING
    ):
        raise InvalidAuditChangeDispositionError(
            "replay-blocking assessment is inconsistent with overall impact"
        )


def _validate_result(result: object) -> AuditChangeImpactResult:
    if not isinstance(result, AuditChangeImpactResult):
        raise InvalidAuditChangeDispositionError(
            "impact_result must be an AuditChangeImpactResult"
        )
    if not isinstance(result.comparison_status, AuditComparisonStatus):
        raise InvalidAuditChangeDispositionError("comparison status is invalid")
    if not isinstance(result.overall_impact, AuditChangeImpact):
        raise InvalidAuditChangeDispositionError("overall impact is invalid")
    if result.overall_impact not in _IMPACT_DISPOSITION:
        raise InvalidAuditChangeDispositionError("overall impact is unmapped")
    if not isinstance(result.decision_changed, bool):
        raise InvalidAuditChangeDispositionError("decision_changed must be boolean")
    assessments = _validated_assessments(result)
    _validate_status_invariants(result, assessments)
    _validate_decision_transition(result)
    return result


def _reason_for_assessment(
    assessment: AuditChangeImpactAssessment,
) -> AuditChangeDispositionReason:
    impact = assessment.impact
    if (
        impact is AuditChangeImpact.COMPLIANCE_RELEVANT
        and assessment.change.code is AuditChangeCode.REPLAYABILITY_STATUS_CHANGED
    ):
        if (
            assessment.change.candidate_value != ReplayabilityStatus.REPLAYABLE.value
            or assessment.change.baseline_value
            not in {
                ReplayabilityStatus.NOT_REPLAYABLE.value,
                ReplayabilityStatus.INCOMPLETE.value,
            }
        ):
            raise InvalidAuditChangeDispositionError(
                "non-blocking replayability impact must re-establish replayability"
            )
        disposition = AuditChangeDisposition.REPLAY_REQUIRED
        code = AuditChangeDispositionReasonCode.REPLAYABILITY_REESTABLISHED
    elif impact is AuditChangeImpact.TRACEABILITY_ONLY:
        disposition = AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY
        code = AuditChangeDispositionReasonCode.TRACEABILITY_RETENTION_REQUIRED
    elif impact is AuditChangeImpact.ENGINEERING_EVIDENCE:
        disposition = AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED
        code = AuditChangeDispositionReasonCode.ENGINEERING_EVIDENCE_REVIEW_REQUIRED
    elif impact is AuditChangeImpact.COMPLIANCE_RELEVANT:
        disposition = AuditChangeDisposition.REVALIDATION_REQUIRED
        code = AuditChangeDispositionReasonCode.COMPLIANCE_REVALIDATION_REQUIRED
    elif impact is AuditChangeImpact.DECISION_CHANGING:
        disposition = AuditChangeDisposition.REVALIDATION_REQUIRED
        code = AuditChangeDispositionReasonCode.DECISION_REVALIDATION_REQUIRED
    elif impact is AuditChangeImpact.REPLAY_BLOCKING:
        disposition = AuditChangeDisposition.BLOCKED
        code = AuditChangeDispositionReasonCode.TRUSTWORTHY_DISPOSITION_BLOCKED
    else:
        raise InvalidAuditChangeDispositionError(
            f"unsupported per-change impact {impact.value!r}"
        )
    return AuditChangeDispositionReason(
        code=code,
        disposition=disposition,
        source_impact=impact,
        source_impact_reason=assessment.reason,
        change=assessment.change,
    )


def _highest_disposition(
    reasons: tuple[AuditChangeDispositionReason, ...],
) -> AuditChangeDisposition:
    present = {reason.disposition for reason in reasons}
    for disposition in _DISPOSITION_PRECEDENCE:
        if disposition in present:
            return disposition
    raise InvalidAuditChangeDispositionError("impact result has no disposition reason")


def determine_audit_change_disposition(
    impact_result: AuditChangeImpactResult,
) -> AuditChangeDispositionResult:
    """Determine governance disposition from authoritative Stage 15Q output."""
    result = _validate_result(impact_result)
    if result.overall_impact is AuditChangeImpact.NO_IMPACT:
        disposition = _IMPACT_DISPOSITION[AuditChangeImpact.NO_IMPACT]
        reasons = (
            AuditChangeDispositionReason(
                code=AuditChangeDispositionReasonCode.NO_ACTION_REQUIRED,
                disposition=disposition,
                source_impact=AuditChangeImpact.NO_IMPACT,
                source_impact_reason=(AuditChangeImpactReason.NO_DETERMINISTIC_CHANGE),
                change=None,
            ),
        )
    else:
        reasons = tuple(
            _reason_for_assessment(item) for item in result.assessed_changes
        )
        disposition = _highest_disposition(reasons)

    expected = _IMPACT_DISPOSITION[result.overall_impact]
    if disposition is not expected and not (
        disposition is AuditChangeDisposition.REPLAY_REQUIRED
        and result.overall_impact
        in {
            AuditChangeImpact.COMPLIANCE_RELEVANT,
            AuditChangeImpact.DECISION_CHANGING,
        }
    ):
        raise InvalidAuditChangeDispositionError(
            "reason dispositions conflict with authoritative overall impact"
        )
    return AuditChangeDispositionResult(
        comparison_status=result.comparison_status,
        source_impact=result.overall_impact,
        disposition=disposition,
        decision_changed=result.decision_changed,
        previous_decision_status=result.previous_decision_status,
        current_decision_status=result.current_decision_status,
        reasons=reasons,
    )
