"""Stage 15R deterministic audit-change disposition tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import origlyph.tolerance.change_disposition as disposition_module
from origlyph.tolerance import (
    AuditChangeDisposition,
    AuditChangeDispositionReason,
    AuditChangeDispositionReasonCode,
    AuditChangeDispositionResult,
    InvalidAuditChangeDispositionError,
    determine_audit_change_disposition,
)
from origlyph.tolerance.change_impact import (
    AuditChangeImpact,
    AuditChangeImpactAssessment,
    AuditChangeImpactReason,
    AuditChangeImpactResult,
)
from origlyph.tolerance.comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
)
from origlyph.tolerance.models import ToleranceDecisionStatus

_DEFAULT_REASON = {
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

_DEFAULT_CHANGE = {
    AuditChangeImpact.TRACEABILITY_ONLY: AuditChangeCode.PACKAGE_ID_CHANGED,
    AuditChangeImpact.ENGINEERING_EVIDENCE: AuditChangeCode.INPUT_METRIC_CHANGED,
    AuditChangeImpact.COMPLIANCE_RELEVANT: (AuditChangeCode.EQUALITY_TOLERANCE_CHANGED),
    AuditChangeImpact.DECISION_CHANGING: AuditChangeCode.DECISION_STATUS_CHANGED,
    AuditChangeImpact.REPLAY_BLOCKING: AuditChangeCode.PACKAGE_VERIFICATION_FAILED,
}


def _change(
    code: AuditChangeCode,
    *,
    baseline: object = "old",
    candidate: object = "new",
) -> AuditChange:
    return AuditChange(
        code=code,
        category=AuditChangeCategory.STRUCTURAL,
        scope="fixture",
        subject_id="subject",
        field_path="field",
        baseline_value=baseline,  # type: ignore[arg-type]
        candidate_value=candidate,  # type: ignore[arg-type]
        significance=AuditChangeSignificance.ENGINEERING_RELEVANT,
        detail="deterministic fixture",
    )


def _assessment(
    impact: AuditChangeImpact,
    *,
    code: AuditChangeCode | None = None,
    reason: AuditChangeImpactReason | None = None,
    baseline: object = "old",
    candidate: object = "new",
) -> AuditChangeImpactAssessment:
    return AuditChangeImpactAssessment(
        change=_change(
            code or _DEFAULT_CHANGE[impact],
            baseline=baseline,
            candidate=candidate,
        ),
        impact=impact,
        reason=reason or _DEFAULT_REASON[impact],
    )


def _result(
    impact: AuditChangeImpact,
    *assessments: AuditChangeImpactAssessment,
    comparison_status: AuditComparisonStatus = AuditComparisonStatus.CHANGED,
    decision_changed: bool = False,
    previous: ToleranceDecisionStatus | None = None,
    current: ToleranceDecisionStatus | None = None,
) -> AuditChangeImpactResult:
    if impact is AuditChangeImpact.NO_IMPACT:
        comparison_status = AuditComparisonStatus.IDENTICAL
        items: tuple[AuditChangeImpactAssessment, ...] = ()
    else:
        items = assessments or (_assessment(impact),)
    return AuditChangeImpactResult(
        comparison_status=comparison_status,
        overall_impact=impact,
        decision_changed=decision_changed,
        previous_decision_status=previous,
        current_decision_status=current,
        assessed_changes=items,
    )


def test_public_api_is_available() -> None:
    assert callable(determine_audit_change_disposition)
    assert AuditChangeDisposition.ACCEPT.value == "accept"
    assert AuditChangeDispositionReasonCode.NO_ACTION_REQUIRED.value


def test_no_impact_is_accepted() -> None:
    result = determine_audit_change_disposition(_result(AuditChangeImpact.NO_IMPACT))
    assert result.disposition is AuditChangeDisposition.ACCEPT
    assert result.reasons[0].change is None


def test_traceability_only_is_accepted_with_traceability() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.TRACEABILITY_ONLY)
    )
    assert result.disposition is AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY


def test_engineering_evidence_requires_review() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.ENGINEERING_EVIDENCE)
    )
    assert result.disposition is AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED


def test_compliance_change_requires_revalidation() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.COMPLIANCE_RELEVANT)
    )
    assert result.disposition is AuditChangeDisposition.REVALIDATION_REQUIRED


def test_decision_change_requires_revalidation() -> None:
    result = determine_audit_change_disposition(
        _result(
            AuditChangeImpact.DECISION_CHANGING,
            decision_changed=True,
            previous=ToleranceDecisionStatus.PASS,
            current=ToleranceDecisionStatus.FAIL,
        )
    )
    assert result.disposition is AuditChangeDisposition.REVALIDATION_REQUIRED
    assert result.decision_changed


def test_replay_blocking_impact_is_blocked() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.REPLAY_BLOCKING)
    )
    assert result.disposition is AuditChangeDisposition.BLOCKED


def test_incompatible_comparison_impact_is_blocked() -> None:
    result = determine_audit_change_disposition(
        _result(
            AuditChangeImpact.REPLAY_BLOCKING,
            comparison_status=AuditComparisonStatus.INCOMPATIBLE,
        )
    )
    assert result.disposition is AuditChangeDisposition.BLOCKED


def test_integrity_degradation_is_blocked() -> None:
    assessment = _assessment(
        AuditChangeImpact.REPLAY_BLOCKING,
        code=AuditChangeCode.INTEGRITY_STATUS_CHANGED,
        reason=AuditChangeImpactReason.INTEGRITY_NOT_TRUSTWORTHY,
        baseline="valid",
        candidate="invalid",
    )
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.REPLAY_BLOCKING, assessment)
    )
    assert result.disposition is AuditChangeDisposition.BLOCKED


def test_replayability_loss_is_blocked() -> None:
    assessment = _assessment(
        AuditChangeImpact.REPLAY_BLOCKING,
        code=AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        reason=AuditChangeImpactReason.REPLAYABILITY_LOST,
        baseline="replayable",
        candidate="not_replayable",
    )
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.REPLAY_BLOCKING, assessment)
    )
    assert result.disposition is AuditChangeDisposition.BLOCKED


def test_reestablished_replayability_requires_replay() -> None:
    assessment = _assessment(
        AuditChangeImpact.COMPLIANCE_RELEVANT,
        code=AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        baseline="not_replayable",
        candidate="replayable",
    )
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.COMPLIANCE_RELEVANT, assessment)
    )
    assert result.disposition is AuditChangeDisposition.REPLAY_REQUIRED
    assert result.reasons[0].code is (
        AuditChangeDispositionReasonCode.REPLAYABILITY_REESTABLISHED
    )


def test_unchanged_pass_with_evidence_change_requires_review() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.ENGINEERING_EVIDENCE)
    )
    assert not result.decision_changed
    assert result.disposition is AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED


def test_unchanged_fail_with_evidence_change_requires_review() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.ENGINEERING_EVIDENCE)
    )
    assert result.previous_decision_status is None
    assert result.disposition is AuditChangeDisposition.ENGINEERING_REVIEW_REQUIRED


def test_all_supported_decision_transitions_require_revalidation() -> None:
    transitions = (
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.FAIL),
        (ToleranceDecisionStatus.FAIL, ToleranceDecisionStatus.PASS),
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.INCOMPLETE),
        (ToleranceDecisionStatus.INCOMPLETE, ToleranceDecisionStatus.PASS),
    )
    for previous, current in transitions:
        result = determine_audit_change_disposition(
            _result(
                AuditChangeImpact.DECISION_CHANGING,
                decision_changed=True,
                previous=previous,
                current=current,
            )
        )
        assert result.disposition is AuditChangeDisposition.REVALIDATION_REQUIRED
        assert result.previous_decision_status is previous
        assert result.current_decision_status is current


def test_blocked_has_highest_precedence() -> None:
    result = determine_audit_change_disposition(
        _result(
            AuditChangeImpact.REPLAY_BLOCKING,
            _assessment(AuditChangeImpact.ENGINEERING_EVIDENCE),
            _assessment(AuditChangeImpact.REPLAY_BLOCKING),
        )
    )
    assert result.disposition is AuditChangeDisposition.BLOCKED


def test_replay_required_precedes_revalidation() -> None:
    replay = _assessment(
        AuditChangeImpact.COMPLIANCE_RELEVANT,
        code=AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        baseline="not_replayable",
        candidate="replayable",
    )
    compliance = _assessment(AuditChangeImpact.COMPLIANCE_RELEVANT)
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.COMPLIANCE_RELEVANT, compliance, replay)
    )
    assert result.disposition is AuditChangeDisposition.REPLAY_REQUIRED


def test_stage_15q_reason_order_is_preserved() -> None:
    first = _assessment(AuditChangeImpact.ENGINEERING_EVIDENCE)
    second = _assessment(AuditChangeImpact.TRACEABILITY_ONLY)
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.ENGINEERING_EVIDENCE, first, second)
    )
    assert tuple(reason.change for reason in result.reasons) == (
        first.change,
        second.change,
    )


def test_repeated_execution_is_identical() -> None:
    impact = _result(AuditChangeImpact.COMPLIANCE_RELEVANT)
    assert determine_audit_change_disposition(
        impact
    ) == determine_audit_change_disposition(impact)


def test_serialization_is_deterministic() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.TRACEABILITY_ONLY)
    )
    assert result.to_json() == result.to_json()
    assert result.as_dict()["disposition"] == "accept_with_traceability"


def test_input_result_is_not_mutated() -> None:
    impact = _result(AuditChangeImpact.ENGINEERING_EVIDENCE)
    before = impact.to_json()
    determine_audit_change_disposition(impact)
    assert impact.to_json() == before


def test_models_are_frozen() -> None:
    result = determine_audit_change_disposition(_result(AuditChangeImpact.NO_IMPACT))
    with pytest.raises(FrozenInstanceError):
        result.disposition = AuditChangeDisposition.BLOCKED  # type: ignore[misc]


def test_invalid_input_type_is_rejected() -> None:
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(object())  # type: ignore[arg-type]


def test_unknown_impact_value_is_rejected() -> None:
    malformed = AuditChangeImpactResult(
        comparison_status=AuditComparisonStatus.CHANGED,
        overall_impact=object(),  # type: ignore[arg-type]
        decision_changed=False,
        previous_decision_status=None,
        current_decision_status=None,
        assessed_changes=(_assessment(AuditChangeImpact.ENGINEERING_EVIDENCE),),
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_identical_with_assessments_is_rejected() -> None:
    malformed = AuditChangeImpactResult(
        comparison_status=AuditComparisonStatus.IDENTICAL,
        overall_impact=AuditChangeImpact.NO_IMPACT,
        decision_changed=False,
        previous_decision_status=None,
        current_decision_status=None,
        assessed_changes=(_assessment(AuditChangeImpact.TRACEABILITY_ONLY),),
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_changed_without_assessments_is_rejected() -> None:
    malformed = AuditChangeImpactResult(
        comparison_status=AuditComparisonStatus.CHANGED,
        overall_impact=AuditChangeImpact.ENGINEERING_EVIDENCE,
        decision_changed=False,
        previous_decision_status=None,
        current_decision_status=None,
        assessed_changes=(),
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_per_change_no_impact_is_rejected() -> None:
    assessment = AuditChangeImpactAssessment(
        _change(AuditChangeCode.PACKAGE_ID_CHANGED),
        AuditChangeImpact.NO_IMPACT,
        AuditChangeImpactReason.NO_DETERMINISTIC_CHANGE,
    )
    malformed = _result(AuditChangeImpact.TRACEABILITY_ONLY, assessment)
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_unrepresented_overall_impact_is_rejected() -> None:
    malformed = _result(
        AuditChangeImpact.COMPLIANCE_RELEVANT,
        _assessment(AuditChangeImpact.ENGINEERING_EVIDENCE),
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_malformed_decision_transition_is_rejected() -> None:
    malformed = _result(
        AuditChangeImpact.DECISION_CHANGING,
        decision_changed=True,
        previous=ToleranceDecisionStatus.PASS,
        current=ToleranceDecisionStatus.PASS,
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_inconsistent_impact_reason_is_rejected() -> None:
    malformed = _result(
        AuditChangeImpact.ENGINEERING_EVIDENCE,
        _assessment(
            AuditChangeImpact.ENGINEERING_EVIDENCE,
            reason=AuditChangeImpactReason.COMPLIANCE_SEMANTICS_CHANGED,
        ),
    )
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_duplicate_assessments_are_rejected() -> None:
    assessment = _assessment(AuditChangeImpact.ENGINEERING_EVIDENCE)
    malformed = _result(AuditChangeImpact.ENGINEERING_EVIDENCE, assessment, assessment)
    with pytest.raises(InvalidAuditChangeDispositionError):
        determine_audit_change_disposition(malformed)


def test_every_impact_has_an_explicit_disposition() -> None:
    assert set(disposition_module._IMPACT_DISPOSITION) == set(AuditChangeImpact)


def test_no_human_authority_is_fabricated() -> None:
    fields = AuditChangeDispositionResult.__dataclass_fields__
    prohibited = {
        "approved" + "_by",
        "reviewed" + "_by",
        "authorized" + "_by",
        "signature",
        "user" + "_id",
        "actor" + "_id",
    }
    assert prohibited.isdisjoint(fields)


def test_no_upstream_or_impact_recomputation_calls() -> None:
    source = inspect.getsource(disposition_module)
    prohibited_calls = (
        "compare_decision_audit_packages(",
        "assess_audit_change_impact(",
        "worst_case(",
        "statistical(",
        "evaluate_tolerance_decision(",
        "build_decision_audit_package(",
    )
    assert not any(call in source for call in prohibited_calls)


def test_reason_retains_structured_source_traceability() -> None:
    result = determine_audit_change_disposition(
        _result(AuditChangeImpact.ENGINEERING_EVIDENCE)
    )
    reason = result.reasons[0]
    assert isinstance(reason, AuditChangeDispositionReason)
    assert reason.change is not None
    assert reason.source_impact is AuditChangeImpact.ENGINEERING_EVIDENCE
