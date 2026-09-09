"""Deterministic impact assessment for Stage 15P audit changes (Stage 15Q).

This module classifies changes already detected by Stage 15P.  It does not
compare audit packages and does not recompute any engineering result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from .audit import ReplayabilityStatus
from .comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
    AuditPackageComparisonResult,
)
from .integrity import AuditIntegrityStatus
from .models import ToleranceDecisionStatus

__all__ = [
    "AuditChangeImpact",
    "AuditChangeImpactAssessment",
    "AuditChangeImpactReason",
    "AuditChangeImpactResult",
    "InvalidAuditChangeImpactError",
    "assess_audit_change_impact",
]


class InvalidAuditChangeImpactError(ValueError):
    """Raised when a Stage 15P comparison result is malformed."""


class AuditChangeImpact(Enum):
    """Deterministic impact levels, from no effect to replay blocking."""

    NO_IMPACT = "no_impact"
    TRACEABILITY_ONLY = "traceability_only"
    ENGINEERING_EVIDENCE = "engineering_evidence"
    COMPLIANCE_RELEVANT = "compliance_relevant"
    DECISION_CHANGING = "decision_changing"
    REPLAY_BLOCKING = "replay_blocking"


class AuditChangeImpactReason(Enum):
    """Stable rationale for an impact classification."""

    NO_DETERMINISTIC_CHANGE = "no_deterministic_change"
    IDENTITY_OR_TRACEABILITY_CHANGED = "identity_or_traceability_changed"
    ENGINEERING_EVIDENCE_CHANGED = "engineering_evidence_changed"
    COMPLIANCE_SEMANTICS_CHANGED = "compliance_semantics_changed"
    DECISION_STATUS_TRANSITION = "decision_status_transition"
    INTEGRITY_NOT_TRUSTWORTHY = "integrity_not_trustworthy"
    REPLAYABILITY_LOST = "replayability_lost"
    STRUCTURALLY_INCOMPATIBLE = "structurally_incompatible"


@dataclass(frozen=True, slots=True)
class AuditChangeImpactAssessment:
    """Impact assigned to one authoritative Stage 15P change."""

    change: AuditChange
    impact: AuditChangeImpact
    reason: AuditChangeImpactReason

    def as_dict(self) -> dict[str, object]:
        return {
            "change": self.change.as_dict(),
            "impact": self.impact.value,
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class AuditChangeImpactResult:
    """Aggregate deterministic impact of a Stage 15P comparison result."""

    comparison_status: AuditComparisonStatus
    overall_impact: AuditChangeImpact
    decision_changed: bool
    previous_decision_status: ToleranceDecisionStatus | None
    current_decision_status: ToleranceDecisionStatus | None
    assessed_changes: tuple[AuditChangeImpactAssessment, ...]

    @property
    def engineering_evidence_changed(self) -> bool:
        return any(
            item.impact is AuditChangeImpact.ENGINEERING_EVIDENCE
            for item in self.assessed_changes
        )

    @property
    def compliance_relevant_changed(self) -> bool:
        return any(
            item.impact is AuditChangeImpact.COMPLIANCE_RELEVANT
            for item in self.assessed_changes
        )

    @property
    def integrity_relevant_changed(self) -> bool:
        return any(
            item.change.category is AuditChangeCategory.INTEGRITY
            or item.change.code
            in {
                AuditChangeCode.PACKAGE_VERIFICATION_FAILED,
                AuditChangeCode.UNEXPLAINED_FINGERPRINT_DRIFT,
            }
            for item in self.assessed_changes
        )

    @property
    def replayability_changed(self) -> bool:
        return any(
            item.change.code is AuditChangeCode.REPLAYABILITY_STATUS_CHANGED
            for item in self.assessed_changes
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "comparison_status": self.comparison_status.value,
            "overall_impact": self.overall_impact.value,
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
            "engineering_evidence_changed": self.engineering_evidence_changed,
            "compliance_relevant_changed": self.compliance_relevant_changed,
            "integrity_relevant_changed": self.integrity_relevant_changed,
            "replayability_changed": self.replayability_changed,
            "assessed_changes": [item.as_dict() for item in self.assessed_changes],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )


_TRACEABILITY_CODES = frozenset(
    {
        AuditChangeCode.EVIDENCE_SOURCE_CHANGED,
        AuditChangeCode.DECISION_ID_CHANGED,
        AuditChangeCode.PACKAGE_ID_CHANGED,
        AuditChangeCode.INPUT_FINGERPRINT_CHANGED,
        AuditChangeCode.REPORT_FINGERPRINT_CHANGED,
        AuditChangeCode.INTEGRITY_FINGERPRINT_CHANGED,
    }
)

_ENGINEERING_EVIDENCE_CODES = frozenset(
    {
        AuditChangeCode.SUPPORTING_REASON_SET_CHANGED,
        AuditChangeCode.EVIDENCE_ADDED,
        AuditChangeCode.EVIDENCE_REMOVED,
        AuditChangeCode.EVIDENCE_CODE_CHANGED,
        AuditChangeCode.CONTRIBUTOR_ADDED,
        AuditChangeCode.CONTRIBUTOR_REMOVED,
        AuditChangeCode.CONTRIBUTOR_ORDER_CHANGED,
        AuditChangeCode.CONTRIBUTOR_SPAN_CHANGED,
        AuditChangeCode.CONTRIBUTOR_SIGMA_CHANGED,
        AuditChangeCode.CONTRIBUTOR_FIELD_CHANGED,
        AuditChangeCode.INPUT_METRIC_ADDED,
        AuditChangeCode.INPUT_METRIC_REMOVED,
        AuditChangeCode.INPUT_METRIC_CHANGED,
    }
)

_COMPLIANCE_CODES = frozenset(
    {
        AuditChangeCode.EQUALITY_TOLERANCE_CHANGED,
        AuditChangeCode.SIGMA_MULTIPLIER_CHANGED,
        AuditChangeCode.COMPLETENESS_POLICY_CHANGED,
        AuditChangeCode.POLICY_IDENTIFIERS_CHANGED,
        AuditChangeCode.REPORT_COMPLETENESS_CHANGED,
        AuditChangeCode.SUMMARY_CODE_CHANGED,
        AuditChangeCode.GOVERNING_REASON_SET_CHANGED,
        AuditChangeCode.MARGINAL_REASON_SET_CHANGED,
        AuditChangeCode.REASON_LINK_CHANGED,
        AuditChangeCode.GOVERNING_EVIDENCE_CHANGED,
        AuditChangeCode.MARGINAL_EVIDENCE_CHANGED,
        AuditChangeCode.CORRELATION_PAIR_ADDED,
        AuditChangeCode.CORRELATION_PAIR_REMOVED,
        AuditChangeCode.CORRELATION_RHO_CHANGED,
        AuditChangeCode.ALLOCATION_CHANGED,
        AuditChangeCode.STATISTICAL_ALLOCATION_CHANGED,
        AuditChangeCode.RECONCILIATION_CHANGED,
        AuditChangeCode.RECONCILIATION_MARGIN_CHANGED,
        AuditChangeCode.INTEGRITY_VIOLATION_REMOVED,
    }
)

_STRUCTURAL_BLOCKING_CODES = frozenset(
    {
        AuditChangeCode.AUDIT_SCHEMA_CHANGED,
        AuditChangeCode.REPORT_SCHEMA_CHANGED,
        AuditChangeCode.PACKAGE_VERIFICATION_FAILED,
        AuditChangeCode.UNEXPLAINED_FINGERPRINT_DRIFT,
    }
)

_IMPACT_PRECEDENCE = (
    AuditChangeImpact.REPLAY_BLOCKING,
    AuditChangeImpact.DECISION_CHANGING,
    AuditChangeImpact.COMPLIANCE_RELEVANT,
    AuditChangeImpact.ENGINEERING_EVIDENCE,
    AuditChangeImpact.TRACEABILITY_ONLY,
    AuditChangeImpact.NO_IMPACT,
)


def _enum_value(enum_type: type[Enum], value: object, field: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise InvalidAuditChangeImpactError(
            f"{field} has unsupported value {value!r}"
        ) from exc


def _validate_change(change: object, index: int) -> AuditChange:
    if not isinstance(change, AuditChange):
        raise InvalidAuditChangeImpactError(f"changes[{index}] must be an AuditChange")
    if not isinstance(change.code, AuditChangeCode):
        raise InvalidAuditChangeImpactError(f"changes[{index}].code is invalid")
    if not isinstance(change.category, AuditChangeCategory):
        raise InvalidAuditChangeImpactError(f"changes[{index}].category is invalid")
    if not isinstance(change.significance, AuditChangeSignificance):
        raise InvalidAuditChangeImpactError(f"changes[{index}].significance is invalid")
    for field in ("scope", "subject_id", "field_path", "detail"):
        if not isinstance(getattr(change, field), str):
            raise InvalidAuditChangeImpactError(
                f"changes[{index}].{field} must be a string"
            )
    return change


def _validate_result(result: object) -> AuditPackageComparisonResult:
    if not isinstance(result, AuditPackageComparisonResult):
        raise InvalidAuditChangeImpactError(
            "comparison_result must be an AuditPackageComparisonResult"
        )
    if not isinstance(result.status, AuditComparisonStatus):
        raise InvalidAuditChangeImpactError("comparison status is invalid")
    if not isinstance(result.changes, tuple):
        raise InvalidAuditChangeImpactError("comparison changes must be a tuple")
    if not isinstance(result.baseline_package_id, str) or not isinstance(
        result.candidate_package_id, str
    ):
        raise InvalidAuditChangeImpactError("package identifiers must be strings")
    if not isinstance(result.provenance_compared, bool):
        raise InvalidAuditChangeImpactError("provenance_compared must be boolean")
    changes = tuple(_validate_change(item, i) for i, item in enumerate(result.changes))
    if len(set(changes)) != len(changes):
        raise InvalidAuditChangeImpactError("comparison contains duplicate changes")
    if result.status is AuditComparisonStatus.IDENTICAL and changes:
        raise InvalidAuditChangeImpactError("IDENTICAL comparison must have no changes")
    if result.status is not AuditComparisonStatus.IDENTICAL and not changes:
        raise InvalidAuditChangeImpactError(
            f"{result.status.value.upper()} comparison must contain changes"
        )
    if result.status is AuditComparisonStatus.INCOMPATIBLE and not any(
        item.code in _STRUCTURAL_BLOCKING_CODES
        or item.significance is AuditChangeSignificance.INCOMPATIBLE
        for item in changes
    ):
        raise InvalidAuditChangeImpactError(
            "INCOMPATIBLE comparison lacks a blocking structural change"
        )
    return result


def _dynamic_impact(
    change: AuditChange,
) -> tuple[AuditChangeImpact, AuditChangeImpactReason] | None:
    if change.code is AuditChangeCode.REPLAYABILITY_STATUS_CHANGED:
        baseline = _enum_value(
            ReplayabilityStatus, change.baseline_value, "baseline replayability"
        )
        candidate = _enum_value(
            ReplayabilityStatus, change.candidate_value, "candidate replayability"
        )
        if baseline is candidate:
            raise InvalidAuditChangeImpactError(
                "replayability change must contain distinct states"
            )
        if candidate is ReplayabilityStatus.REPLAYABLE:
            return (
                AuditChangeImpact.COMPLIANCE_RELEVANT,
                AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED,
            )
        return (
            AuditChangeImpact.REPLAY_BLOCKING,
            AuditChangeImpactReason.REPLAYABILITY_LOST,
        )
    if change.code is AuditChangeCode.INTEGRITY_STATUS_CHANGED:
        baseline = _enum_value(
            AuditIntegrityStatus, change.baseline_value, "baseline integrity status"
        )
        candidate = _enum_value(
            AuditIntegrityStatus, change.candidate_value, "candidate integrity status"
        )
        if baseline is candidate:
            raise InvalidAuditChangeImpactError(
                "integrity change must contain distinct states"
            )
        if candidate is AuditIntegrityStatus.VALID:
            return (
                AuditChangeImpact.COMPLIANCE_RELEVANT,
                AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED,
            )
        return (
            AuditChangeImpact.REPLAY_BLOCKING,
            AuditChangeImpactReason.INTEGRITY_NOT_TRUSTWORTHY,
        )
    if change.code in {
        AuditChangeCode.INTEGRITY_VIOLATION_ADDED,
        AuditChangeCode.INTEGRITY_VIOLATION_CHANGED,
    }:
        return (
            AuditChangeImpact.REPLAY_BLOCKING,
            AuditChangeImpactReason.INTEGRITY_NOT_TRUSTWORTHY,
        )
    return None


def _classify_change(
    change: AuditChange,
) -> tuple[AuditChangeImpact, AuditChangeImpactReason]:
    dynamic = _dynamic_impact(change)
    if dynamic is not None:
        return dynamic
    if (
        change.code in _STRUCTURAL_BLOCKING_CODES
        or change.significance is AuditChangeSignificance.INCOMPATIBLE
    ):
        return (
            AuditChangeImpact.REPLAY_BLOCKING,
            AuditChangeImpactReason.STRUCTURALLY_INCOMPATIBLE,
        )
    if change.code is AuditChangeCode.DECISION_STATUS_CHANGED:
        return (
            AuditChangeImpact.DECISION_CHANGING,
            AuditChangeImpactReason.DECISION_STATUS_TRANSITION,
        )
    if change.code in _COMPLIANCE_CODES:
        return (
            AuditChangeImpact.COMPLIANCE_RELEVANT,
            AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED,
        )
    if change.code in _ENGINEERING_EVIDENCE_CODES:
        return (
            AuditChangeImpact.ENGINEERING_EVIDENCE,
            AuditChangeImpactReason.ENGINEERING_EVIDENCE_CHANGED,
        )
    if change.code in _TRACEABILITY_CODES:
        return (
            AuditChangeImpact.TRACEABILITY_ONLY,
            AuditChangeImpactReason.IDENTITY_OR_TRACEABILITY_CHANGED,
        )
    raise InvalidAuditChangeImpactError(
        f"no Stage 15Q impact policy for change code {change.code.value!r}"
    )


def _decision_transition(
    changes: tuple[AuditChange, ...],
) -> tuple[ToleranceDecisionStatus | None, ToleranceDecisionStatus | None]:
    transitions = [
        item for item in changes if item.code is AuditChangeCode.DECISION_STATUS_CHANGED
    ]
    if len(transitions) > 1:
        raise InvalidAuditChangeImpactError(
            "comparison contains multiple decision status transitions"
        )
    if not transitions:
        return None, None
    transition = transitions[0]
    previous = _enum_value(
        ToleranceDecisionStatus,
        transition.baseline_value,
        "previous decision status",
    )
    current = _enum_value(
        ToleranceDecisionStatus,
        transition.candidate_value,
        "current decision status",
    )
    if previous is current:
        raise InvalidAuditChangeImpactError(
            "decision status change must contain distinct states"
        )
    return previous, current  # type: ignore[return-value]


def _overall_impact(
    assessments: tuple[AuditChangeImpactAssessment, ...],
) -> AuditChangeImpact:
    present = {item.impact for item in assessments}
    for impact in _IMPACT_PRECEDENCE:
        if impact in present:
            return impact
    return AuditChangeImpact.NO_IMPACT


def assess_audit_change_impact(
    comparison_result: AuditPackageComparisonResult,
) -> AuditChangeImpactResult:
    """Assess only the impact of changes already detected by Stage 15P."""
    result = _validate_result(comparison_result)
    if result.status is AuditComparisonStatus.IDENTICAL:
        return AuditChangeImpactResult(
            comparison_status=result.status,
            overall_impact=AuditChangeImpact.NO_IMPACT,
            decision_changed=False,
            previous_decision_status=None,
            current_decision_status=None,
            assessed_changes=(),
        )

    assessments = tuple(
        AuditChangeImpactAssessment(change, *_classify_change(change))
        for change in result.changes
    )
    previous, current = _decision_transition(result.changes)
    overall = _overall_impact(assessments)
    if result.status is AuditComparisonStatus.INCOMPATIBLE and overall is not (
        AuditChangeImpact.REPLAY_BLOCKING
    ):
        raise InvalidAuditChangeImpactError(
            "INCOMPATIBLE comparison must assess as replay blocking"
        )
    return AuditChangeImpactResult(
        comparison_status=result.status,
        overall_impact=overall,
        decision_changed=previous is not None,
        previous_decision_status=previous,
        current_decision_status=current,
        assessed_changes=assessments,
    )
