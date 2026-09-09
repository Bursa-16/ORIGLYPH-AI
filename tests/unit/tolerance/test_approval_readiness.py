"""Stage 15S deterministic audit approval-readiness gate tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import origlyph.tolerance.approval_readiness as readiness_module
from origlyph.tolerance import (
    AuditApprovalReadinessReason,
    AuditApprovalReadinessReasonCode,
    AuditApprovalReadinessResult,
    AuditApprovalReadinessStatus,
    InvalidAuditApprovalReadinessError,
    evaluate_audit_approval_readiness,
)
from origlyph.tolerance.change_disposition import (
    AuditChangeDisposition,
    AuditChangeDispositionReason,
    AuditChangeDispositionReasonCode,
    AuditChangeDispositionResult,
)
from origlyph.tolerance.change_impact import (
    AuditChangeImpact,
    AuditChangeImpactReason,
)
from origlyph.tolerance.comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
)
from origlyph.tolerance.models import ToleranceDecisionStatus

_SOURCE_IMPACT = {
    AuditChangeDisposition.ACCEPT: AuditChangeImpact.NO_IMPACT,
    AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY: (
        AuditChangeImpact.TRACEABILITY_ONLY
    ),
    AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED: (
        AuditChangeImpact.ENGINEERING_EVIDENCE
    ),
    AuditChangeDisposition.REVALIDATION_REQUIRED: (
        AuditChangeImpact.COMPLIANCE_RELEVANT
    ),
    AuditChangeDisposition.REPLAY_REQUIRED: AuditChangeImpact.COMPLIANCE_RELEVANT,
    AuditChangeDisposition.BLOCKED: AuditChangeImpact.REPLAY_BLOCKING,
}

_SOURCE_REASON = {
    AuditChangeImpact.NO_IMPACT: AuditChangeImpactReason.NO_DETERMINISTIC_CHANGE,
    AuditChangeImpact.TRACEABILITY_ONLY: (
        AuditChangeImpactReason.IDENTITY_OR_TRACEABILITY_CHANGED
    ),
    AuditChangeImpact.ENGINEERING_EVIDENCE: (
        AuditChangeImpactReason.ENGINEERING_EVIDENCE_CHANGED
    ),
    AuditChangeImpact.COMPLIANCE_RELEVANT: (
        AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED
    ),
    AuditChangeImpact.DECISION_CHANGING: (
        AuditChangeImpactReason.DECISION_STATUS_TRANSITION
    ),
    AuditChangeImpact.REPLAY_BLOCKING: (
        AuditChangeImpactReason.STRUCTURALLY_INCOMPATIBLE
    ),
}

_REASON_CODE = {
    AuditChangeDisposition.ACCEPT: (
        AuditChangeDispositionReasonCode.NO_ACTION_REQUIRED
    ),
    AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY: (
        AuditChangeDispositionReasonCode.TRACEABILITY_RETENTION_REQUIRED
    ),
    AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED: (
        AuditChangeDispositionReasonCode.ENGINEERING_EVIDENCE_REVIEW_REQUIRED
    ),
    AuditChangeDisposition.REVALIDATION_REQUIRED: (
        AuditChangeDispositionReasonCode.COMPLIANCE_REVALIDATION_REQUIRED
    ),
    AuditChangeDisposition.REPLAY_REQUIRED: (
        AuditChangeDispositionReasonCode.REPLAYABILITY_REESTABLISHED
    ),
    AuditChangeDisposition.BLOCKED: (
        AuditChangeDispositionReasonCode.TRUSTWORTHY_DISPOSITION_BLOCKED
    ),
}


def _change(
    code: AuditChangeCode = AuditChangeCode.INPUT_METRIC_CHANGED,
) -> AuditChange:
    return AuditChange(
        code=code,
        category=AuditChangeCategory.STRUCTURAL,
        scope="fixture",
        subject_id="subject",
        field_path="field",
        baseline_value="old",
        candidate_value="new",
        significance=AuditChangeSignificance.ENGINEERING_RELEVANT,
        detail="deterministic fixture",
    )


def _reason(
    disposition: AuditChangeDisposition,
    *,
    source_impact: AuditChangeImpact | None = None,
    code: AuditChangeDispositionReasonCode | None = None,
) -> AuditChangeDispositionReason:
    impact = source_impact or _SOURCE_IMPACT[disposition]
    return AuditChangeDispositionReason(
        code=code or _REASON_CODE[disposition],
        disposition=disposition,
        source_impact=impact,
        source_impact_reason=_SOURCE_REASON[impact],
        change=None if disposition is AuditChangeDisposition.ACCEPT else _change(),
    )


def _result(
    disposition: AuditChangeDisposition,
    *reasons: AuditChangeDispositionReason,
    source_impact: AuditChangeImpact | None = None,
    comparison_status: AuditComparisonStatus = AuditComparisonStatus.CHANGED,
    decision_changed: bool = False,
    previous: ToleranceDecisionStatus | None = None,
    current: ToleranceDecisionStatus | None = None,
) -> AuditChangeDispositionResult:
    impact = source_impact or _SOURCE_IMPACT[disposition]
    if disposition is AuditChangeDisposition.ACCEPT:
        comparison_status = AuditComparisonStatus.IDENTICAL
    return AuditChangeDispositionResult(
        comparison_status=comparison_status,
        source_impact=impact,
        disposition=disposition,
        decision_changed=decision_changed,
        previous_decision_status=previous,
        current_decision_status=current,
        reasons=reasons or (_reason(disposition, source_impact=impact),),
    )


def test_public_api_is_available() -> None:
    assert callable(evaluate_audit_approval_readiness)
    assert AuditApprovalReadinessStatus.READY.value == "ready"
    assert AuditApprovalReadinessReasonCode.REVALIDATION_PENDING.value


def test_accept_is_ready() -> None:
    result = evaluate_audit_approval_readiness(_result(AuditChangeDisposition.ACCEPT))
    assert result.status is AuditApprovalReadinessStatus.READY
    assert result.is_ready


def test_accept_with_traceability_is_ready() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY)
    )
    assert result.status is AuditApprovalReadinessStatus.READY
    assert (
        result.reasons[0].code
        is AuditApprovalReadinessReasonCode.TRACEABILITY_PRESERVED
    )


def test_engineering_review_is_action_required() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    )
    assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED
    assert not result.is_ready


def test_revalidation_is_action_required() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.REVALIDATION_REQUIRED)
    )
    assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED
    assert (
        result.reasons[0].code is AuditApprovalReadinessReasonCode.REVALIDATION_PENDING
    )


def test_replay_is_action_required() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.REPLAY_REQUIRED)
    )
    assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED
    assert result.reasons[0].code is AuditApprovalReadinessReasonCode.REPLAY_PENDING


def test_blocked_disposition_is_blocked() -> None:
    result = evaluate_audit_approval_readiness(_result(AuditChangeDisposition.BLOCKED))
    assert result.status is AuditApprovalReadinessStatus.BLOCKED
    assert not result.is_ready


def test_incompatible_comparison_is_blocked() -> None:
    result = evaluate_audit_approval_readiness(
        _result(
            AuditChangeDisposition.BLOCKED,
            comparison_status=AuditComparisonStatus.INCOMPATIBLE,
        )
    )
    assert result.status is AuditApprovalReadinessStatus.BLOCKED


def test_integrity_block_remains_visible() -> None:
    source = AuditChangeDispositionReason(
        code=AuditChangeDispositionReasonCode.TRUSTWORTHY_DISPOSITION_BLOCKED,
        disposition=AuditChangeDisposition.BLOCKED,
        source_impact=AuditChangeImpact.REPLAY_BLOCKING,
        source_impact_reason=AuditChangeImpactReason.INTEGRITY_NOT_TRUSTWORTHY,
        change=_change(AuditChangeCode.INTEGRITY_STATUS_CHANGED),
    )
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.BLOCKED, source)
    )
    assert result.reasons[0].source_reason is source
    assert result.status is AuditApprovalReadinessStatus.BLOCKED


def test_replayability_loss_remains_blocked() -> None:
    source = AuditChangeDispositionReason(
        code=AuditChangeDispositionReasonCode.TRUSTWORTHY_DISPOSITION_BLOCKED,
        disposition=AuditChangeDisposition.BLOCKED,
        source_impact=AuditChangeImpact.REPLAY_BLOCKING,
        source_impact_reason=AuditChangeImpactReason.REPLAYABILITY_LOST,
        change=_change(AuditChangeCode.REPLAYABILITY_STATUS_CHANGED),
    )
    assert (
        evaluate_audit_approval_readiness(
            _result(AuditChangeDisposition.BLOCKED, source)
        ).status
        is AuditApprovalReadinessStatus.BLOCKED
    )


def test_all_decision_transitions_require_action() -> None:
    transitions = (
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.FAIL),
        (ToleranceDecisionStatus.FAIL, ToleranceDecisionStatus.PASS),
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.INCOMPLETE),
        (ToleranceDecisionStatus.INCOMPLETE, ToleranceDecisionStatus.PASS),
    )
    for previous, current in transitions:
        result = evaluate_audit_approval_readiness(
            _result(
                AuditChangeDisposition.REVALIDATION_REQUIRED,
                _reason(
                    AuditChangeDisposition.REVALIDATION_REQUIRED,
                    source_impact=AuditChangeImpact.DECISION_CHANGING,
                    code=AuditChangeDispositionReasonCode.DECISION_REVALIDATION_REQUIRED,
                ),
                source_impact=AuditChangeImpact.DECISION_CHANGING,
                decision_changed=True,
                previous=previous,
                current=current,
            )
        )
        assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED
        assert result.previous_decision_status is previous
        assert result.current_decision_status is current


def test_unchanged_decision_with_evidence_review_is_not_ready() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    )
    assert not result.decision_changed
    assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED


def test_blocked_has_highest_precedence() -> None:
    review = _reason(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    blocked = _reason(AuditChangeDisposition.BLOCKED)
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.BLOCKED, review, blocked)
    )
    assert result.status is AuditApprovalReadinessStatus.BLOCKED


def test_action_required_precedes_ready() -> None:
    ready = _reason(AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY)
    action = _reason(AuditChangeDisposition.REVALIDATION_REQUIRED)
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.REVALIDATION_REQUIRED, ready, action)
    )
    assert result.status is AuditApprovalReadinessStatus.ACTION_REQUIRED


def test_stage_15r_reason_order_is_preserved() -> None:
    first = _reason(AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY)
    second = _reason(AuditChangeDisposition.REVALIDATION_REQUIRED)
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.REVALIDATION_REQUIRED, first, second)
    )
    assert tuple(reason.source_reason for reason in result.reasons) == (first, second)


def test_repeated_execution_is_identical() -> None:
    disposition = _result(AuditChangeDisposition.REVALIDATION_REQUIRED)
    assert evaluate_audit_approval_readiness(
        disposition
    ) == evaluate_audit_approval_readiness(disposition)


def test_serialization_is_deterministic() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY)
    )
    assert result.to_json() == result.to_json()
    assert result.as_dict()["status"] == "ready"


def test_input_disposition_is_not_mutated() -> None:
    disposition = _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    before = disposition.to_json()
    evaluate_audit_approval_readiness(disposition)
    assert disposition.to_json() == before


def test_models_are_frozen() -> None:
    result = evaluate_audit_approval_readiness(_result(AuditChangeDisposition.ACCEPT))
    with pytest.raises(FrozenInstanceError):
        result.is_ready = False  # type: ignore[misc]


def test_invalid_input_type_is_rejected() -> None:
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(object())  # type: ignore[arg-type]


def test_empty_reason_collection_is_rejected() -> None:
    malformed = AuditChangeDispositionResult(
        comparison_status=AuditComparisonStatus.CHANGED,
        source_impact=AuditChangeImpact.ENGINEERING_EVIDENCE,
        disposition=AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED,
        decision_changed=False,
        previous_decision_status=None,
        current_decision_status=None,
        reasons=(),
    )
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_non_tuple_reason_collection_is_rejected() -> None:
    malformed = _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    object.__setattr__(malformed, "reasons", list(malformed.reasons))
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_duplicate_reasons_are_rejected() -> None:
    reason = _reason(AuditChangeDisposition.REVALIDATION_REQUIRED)
    malformed = _result(AuditChangeDisposition.REVALIDATION_REQUIRED, reason, reason)
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_mismatched_reason_code_is_rejected() -> None:
    reason = _reason(
        AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED,
        code=AuditChangeDispositionReasonCode.COMPLIANCE_REVALIDATION_REQUIRED,
    )
    malformed = _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED, reason)
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_mismatched_source_impact_is_rejected() -> None:
    malformed = _result(
        AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY,
        source_impact=AuditChangeImpact.ENGINEERING_EVIDENCE,
    )
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_incompatible_nonblocked_disposition_is_rejected() -> None:
    malformed = _result(
        AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED,
        comparison_status=AuditComparisonStatus.INCOMPATIBLE,
    )
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_changed_accept_disposition_is_rejected() -> None:
    malformed = _result(AuditChangeDisposition.ACCEPT)
    object.__setattr__(malformed, "comparison_status", AuditComparisonStatus.CHANGED)
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_unflagged_decision_reason_is_rejected() -> None:
    reason = _reason(
        AuditChangeDisposition.REVALIDATION_REQUIRED,
        source_impact=AuditChangeImpact.DECISION_CHANGING,
        code=AuditChangeDispositionReasonCode.DECISION_REVALIDATION_REQUIRED,
    )
    malformed = _result(
        AuditChangeDisposition.REVALIDATION_REQUIRED,
        reason,
        source_impact=AuditChangeImpact.DECISION_CHANGING,
    )
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_same_state_decision_transition_is_rejected() -> None:
    reason = _reason(
        AuditChangeDisposition.REVALIDATION_REQUIRED,
        source_impact=AuditChangeImpact.DECISION_CHANGING,
        code=AuditChangeDispositionReasonCode.DECISION_REVALIDATION_REQUIRED,
    )
    malformed = _result(
        AuditChangeDisposition.REVALIDATION_REQUIRED,
        reason,
        source_impact=AuditChangeImpact.DECISION_CHANGING,
        decision_changed=True,
        previous=ToleranceDecisionStatus.PASS,
        current=ToleranceDecisionStatus.PASS,
    )
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_unknown_disposition_value_is_rejected() -> None:
    malformed = _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    object.__setattr__(malformed, "disposition", object())
    with pytest.raises(InvalidAuditApprovalReadinessError):
        evaluate_audit_approval_readiness(malformed)


def test_every_disposition_has_an_explicit_readiness_status() -> None:
    assert set(readiness_module._DISPOSITION_STATUS) == set(AuditChangeDisposition)
    assert set(readiness_module._DISPOSITION_REASON) == set(AuditChangeDisposition)


def test_readiness_result_contains_no_approval_record() -> None:
    fields = AuditApprovalReadinessResult.__dataclass_fields__
    prohibited = {
        "approved" + "_by",
        "reviewed" + "_by",
        "authorized" + "_by",
        "signature",
        "approval" + "_timestamp",
        "actor" + "_id",
    }
    assert prohibited.isdisjoint(fields)


def test_ready_status_is_not_an_approval_boolean() -> None:
    fields = AuditApprovalReadinessResult.__dataclass_fields__
    assert "is_ready" in fields
    assert "is_approved" not in fields
    assert "approved" not in fields


def test_no_upstream_layer_or_engine_invocations() -> None:
    source = inspect.getsource(readiness_module)
    prohibited_calls = (
        "compare_decision_audit_packages(",
        "assess_audit_change_impact(",
        "determine_audit_change_disposition(",
        "worst_case(",
        "statistical(",
        "evaluate_tolerance_decision(",
    )
    assert not any(call in source for call in prohibited_calls)


def test_readiness_reason_retains_structured_stage_15r_source() -> None:
    result = evaluate_audit_approval_readiness(
        _result(AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED)
    )
    reason = result.reasons[0]
    assert isinstance(reason, AuditApprovalReadinessReason)
    assert reason.source_reason.change is not None
    assert reason.source_reason.source_impact is AuditChangeImpact.ENGINEERING_EVIDENCE
