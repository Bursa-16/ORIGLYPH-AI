"""Stage 15Q deterministic audit-change impact tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import origlyph.tolerance.change_impact as change_impact_module
from origlyph.tolerance import (
    AuditChangeImpact,
    AuditChangeImpactAssessment,
    AuditChangeImpactReason,
    AuditChangeImpactResult,
    InvalidAuditChangeImpactError,
    assess_audit_change_impact,
)
from origlyph.tolerance.comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
    AuditPackageComparisonResult,
)
from origlyph.tolerance.models import ToleranceDecisionStatus


def _change(
    code: AuditChangeCode,
    *,
    category: AuditChangeCategory = AuditChangeCategory.INPUT,
    baseline: object = "old",
    candidate: object = "new",
    significance: AuditChangeSignificance = (
        AuditChangeSignificance.ENGINEERING_RELEVANT
    ),
) -> AuditChange:
    return AuditChange(
        code=code,
        category=category,
        scope="fixture",
        subject_id="subject",
        field_path="field",
        baseline_value=baseline,  # type: ignore[arg-type]
        candidate_value=candidate,  # type: ignore[arg-type]
        significance=significance,
        detail="deterministic fixture change",
    )


def _comparison(
    *changes: AuditChange,
    status: AuditComparisonStatus = AuditComparisonStatus.CHANGED,
) -> AuditPackageComparisonResult:
    return AuditPackageComparisonResult(
        status=status,
        baseline_package_id="baseline",
        candidate_package_id="candidate",
        changes=changes,
    )


def _impact(change: AuditChange) -> AuditChangeImpactResult:
    return assess_audit_change_impact(_comparison(change))


def test_public_api_is_available() -> None:
    assert callable(assess_audit_change_impact)
    assert AuditChangeImpact.NO_IMPACT.value == "no_impact"
    assert AuditChangeImpactReason.DECISION_STATUS_TRANSITION.value


def test_identical_maps_to_no_impact() -> None:
    result = assess_audit_change_impact(
        _comparison(status=AuditComparisonStatus.IDENTICAL)
    )
    assert result.overall_impact is AuditChangeImpact.NO_IMPACT
    assert result.assessed_changes == ()


def test_identical_result_has_no_transition_or_flags() -> None:
    result = assess_audit_change_impact(
        _comparison(status=AuditComparisonStatus.IDENTICAL)
    )
    assert not result.decision_changed
    assert result.previous_decision_status is None
    assert result.current_decision_status is None
    assert not result.engineering_evidence_changed
    assert not result.compliance_relevant_changed


def test_evidence_source_change_is_traceability_only() -> None:
    result = _impact(
        _change(
            AuditChangeCode.EVIDENCE_SOURCE_CHANGED,
            category=AuditChangeCategory.EVIDENCE,
        )
    )
    assert result.overall_impact is AuditChangeImpact.TRACEABILITY_ONLY


def test_input_metric_change_is_engineering_evidence() -> None:
    result = _impact(_change(AuditChangeCode.INPUT_METRIC_CHANGED))
    assert result.overall_impact is AuditChangeImpact.ENGINEERING_EVIDENCE
    assert result.engineering_evidence_changed


def test_evidence_mutation_is_engineering_evidence() -> None:
    result = _impact(
        _change(
            AuditChangeCode.EVIDENCE_CODE_CHANGED,
            category=AuditChangeCategory.EVIDENCE,
        )
    )
    assert result.overall_impact is AuditChangeImpact.ENGINEERING_EVIDENCE


def test_contributor_span_change_is_engineering_evidence() -> None:
    result = _impact(
        _change(
            AuditChangeCode.CONTRIBUTOR_SPAN_CHANGED,
            category=AuditChangeCategory.CONTRIBUTOR,
        )
    )
    assert result.overall_impact is AuditChangeImpact.ENGINEERING_EVIDENCE


def test_equality_policy_change_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.EQUALITY_TOLERANCE_CHANGED,
            category=AuditChangeCategory.POLICY,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT
    assert result.compliance_relevant_changed


def test_requirement_reason_change_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.GOVERNING_REASON_SET_CHANGED,
            category=AuditChangeCategory.EXPLANATION,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT


def test_governing_evidence_change_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.GOVERNING_EVIDENCE_CHANGED,
            category=AuditChangeCategory.EXPLANATION,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT


def test_decision_transitions_are_decision_changing() -> None:
    transitions = (
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.MARGINAL),
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.FAIL),
        (ToleranceDecisionStatus.FAIL, ToleranceDecisionStatus.PASS),
        (ToleranceDecisionStatus.INCOMPLETE, ToleranceDecisionStatus.PASS),
        (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.INCOMPLETE),
    )
    for previous, current in transitions:
        result = _impact(
            _change(
                AuditChangeCode.DECISION_STATUS_CHANGED,
                category=AuditChangeCategory.DECISION,
                baseline=previous.value,
                candidate=current.value,
            )
        )
        assert result.overall_impact is AuditChangeImpact.DECISION_CHANGING
        assert result.decision_changed
        assert result.previous_decision_status is previous
        assert result.current_decision_status is current


def test_unchanged_decision_is_not_invented() -> None:
    for unchanged in (ToleranceDecisionStatus.PASS, ToleranceDecisionStatus.FAIL):
        result = _impact(_change(AuditChangeCode.INPUT_METRIC_CHANGED))
        assert not result.decision_changed
        assert result.previous_decision_status is None
        assert result.current_decision_status is None
        assert unchanged in ToleranceDecisionStatus


def test_decision_change_precedes_engineering_evidence() -> None:
    decision = _change(
        AuditChangeCode.DECISION_STATUS_CHANGED,
        category=AuditChangeCategory.DECISION,
        baseline="pass",
        candidate="fail",
    )
    result = assess_audit_change_impact(
        _comparison(_change(AuditChangeCode.INPUT_METRIC_CHANGED), decision)
    )
    assert result.overall_impact is AuditChangeImpact.DECISION_CHANGING


def test_replayability_loss_is_replay_blocking() -> None:
    result = _impact(
        _change(
            AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
            category=AuditChangeCategory.REPLAYABILITY,
            baseline="replayable",
            candidate="not_replayable",
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.REPLAY_BLOCKING
    assert result.replayability_changed


def test_replayability_restoration_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
            category=AuditChangeCategory.REPLAYABILITY,
            baseline="not_replayable",
            candidate="replayable",
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT


def test_integrity_degradation_is_replay_blocking() -> None:
    result = _impact(
        _change(
            AuditChangeCode.INTEGRITY_STATUS_CHANGED,
            category=AuditChangeCategory.INTEGRITY,
            baseline="valid",
            candidate="invalid",
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.REPLAY_BLOCKING
    assert result.integrity_relevant_changed


def test_integrity_restoration_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.INTEGRITY_STATUS_CHANGED,
            category=AuditChangeCategory.INTEGRITY,
            baseline="invalid",
            candidate="valid",
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT


def test_integrity_violation_added_is_replay_blocking() -> None:
    result = _impact(
        _change(
            AuditChangeCode.INTEGRITY_VIOLATION_ADDED,
            category=AuditChangeCategory.INTEGRITY,
            baseline=None,
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.REPLAY_BLOCKING


def test_integrity_violation_removed_is_compliance_relevant() -> None:
    result = _impact(
        _change(
            AuditChangeCode.INTEGRITY_VIOLATION_REMOVED,
            category=AuditChangeCategory.INTEGRITY,
            candidate=None,
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.COMPLIANCE_RELEVANT


def test_incompatible_comparison_is_replay_blocking() -> None:
    change = _change(
        AuditChangeCode.AUDIT_SCHEMA_CHANGED,
        category=AuditChangeCategory.SCHEMA,
        significance=AuditChangeSignificance.INCOMPATIBLE,
    )
    result = assess_audit_change_impact(
        _comparison(change, status=AuditComparisonStatus.INCOMPATIBLE)
    )
    assert result.overall_impact is AuditChangeImpact.REPLAY_BLOCKING


def test_replay_blocking_has_highest_precedence() -> None:
    decision = _change(
        AuditChangeCode.DECISION_STATUS_CHANGED,
        category=AuditChangeCategory.DECISION,
        baseline="pass",
        candidate="fail",
    )
    replay = _change(
        AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        category=AuditChangeCategory.REPLAYABILITY,
        baseline="replayable",
        candidate="incomplete",
        significance=AuditChangeSignificance.STRUCTURAL,
    )
    result = assess_audit_change_impact(_comparison(decision, replay))
    assert result.overall_impact is AuditChangeImpact.REPLAY_BLOCKING
    assert result.decision_changed


def test_compliance_relevant_engineering_policies() -> None:
    policies = (
        (AuditChangeCode.ALLOCATION_CHANGED, AuditChangeCategory.ALLOCATION),
        (AuditChangeCode.RECONCILIATION_CHANGED, AuditChangeCategory.RECONCILIATION),
        (AuditChangeCode.CORRELATION_RHO_CHANGED, AuditChangeCategory.CORRELATION),
    )
    for code, category in policies:
        assert _impact(_change(code, category=category)).overall_impact is (
            AuditChangeImpact.COMPLIANCE_RELEVANT
        )


def test_fingerprint_change_is_traceability_only_by_itself() -> None:
    result = _impact(
        _change(
            AuditChangeCode.PACKAGE_ID_CHANGED,
            category=AuditChangeCategory.FINGERPRINT,
            significance=AuditChangeSignificance.STRUCTURAL,
        )
    )
    assert result.overall_impact is AuditChangeImpact.TRACEABILITY_ONLY


def test_stage_15p_order_is_preserved() -> None:
    first = _change(AuditChangeCode.INPUT_METRIC_CHANGED)
    second = _change(
        AuditChangeCode.PACKAGE_ID_CHANGED,
        category=AuditChangeCategory.FINGERPRINT,
        significance=AuditChangeSignificance.STRUCTURAL,
    )
    result = assess_audit_change_impact(_comparison(first, second))
    assert tuple(item.change for item in result.assessed_changes) == (first, second)


def test_repeated_execution_is_identical_and_json_is_stable() -> None:
    comparison = _comparison(_change(AuditChangeCode.INPUT_METRIC_CHANGED))
    first = assess_audit_change_impact(comparison)
    second = assess_audit_change_impact(comparison)
    assert first == second
    assert first.to_json() == second.to_json()


def test_input_comparison_is_not_mutated() -> None:
    comparison = _comparison(_change(AuditChangeCode.INPUT_METRIC_CHANGED))
    before = comparison.to_json()
    assess_audit_change_impact(comparison)
    assert comparison.to_json() == before


def test_models_are_frozen() -> None:
    change = _change(AuditChangeCode.INPUT_METRIC_CHANGED)
    assessment = AuditChangeImpactAssessment(
        change,
        AuditChangeImpact.ENGINEERING_EVIDENCE,
        AuditChangeImpactReason.ENGINEERING_EVIDENCE_CHANGED,
    )
    with pytest.raises(FrozenInstanceError):
        assessment.impact = AuditChangeImpact.NO_IMPACT  # type: ignore[misc]


def test_invalid_input_type_is_rejected() -> None:
    with pytest.raises(InvalidAuditChangeImpactError):
        assess_audit_change_impact(object())  # type: ignore[arg-type]


def test_identical_with_changes_is_rejected() -> None:
    malformed = _comparison(
        _change(AuditChangeCode.INPUT_METRIC_CHANGED),
        status=AuditComparisonStatus.IDENTICAL,
    )
    with pytest.raises(InvalidAuditChangeImpactError):
        assess_audit_change_impact(malformed)


def test_changed_without_changes_is_rejected() -> None:
    with pytest.raises(InvalidAuditChangeImpactError):
        assess_audit_change_impact(_comparison())


def test_same_state_decision_transition_is_rejected() -> None:
    change = _change(
        AuditChangeCode.DECISION_STATUS_CHANGED,
        category=AuditChangeCategory.DECISION,
        baseline="pass",
        candidate="pass",
    )
    with pytest.raises(InvalidAuditChangeImpactError):
        assess_audit_change_impact(_comparison(change))


def test_malformed_structural_transition_is_rejected() -> None:
    change = _change(
        AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        category=AuditChangeCategory.REPLAYABILITY,
        baseline="unknown",
        candidate="replayable",
        significance=AuditChangeSignificance.STRUCTURAL,
    )
    with pytest.raises(InvalidAuditChangeImpactError):
        assess_audit_change_impact(_comparison(change))


def test_every_stage_15p_change_code_has_an_explicit_policy() -> None:
    mapped = (
        change_impact_module._TRACEABILITY_CODES
        | change_impact_module._ENGINEERING_EVIDENCE_CODES
        | change_impact_module._COMPLIANCE_CODES
        | change_impact_module._STRUCTURAL_BLOCKING_CODES
        | {
            AuditChangeCode.DECISION_STATUS_CHANGED,
            AuditChangeCode.INTEGRITY_STATUS_CHANGED,
            AuditChangeCode.INTEGRITY_VIOLATION_ADDED,
            AuditChangeCode.INTEGRITY_VIOLATION_CHANGED,
            AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
        }
    )
    assert mapped == set(AuditChangeCode)


def test_no_comparison_or_engine_recomputation_dependencies() -> None:
    source = inspect.getsource(change_impact_module)
    prohibited_calls = (
        "compare_decision_audit_packages(",
        "worst_case(",
        "statistical(",
        "evaluate_tolerance_decision(",
        "build_decision_audit_package(",
    )
    assert not any(call in source for call in prohibited_calls)
