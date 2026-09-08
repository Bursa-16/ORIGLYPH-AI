"""Stage 15P deterministic audit-package comparison tests."""

from __future__ import annotations

import importlib
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from origlyph.tolerance import (
    REPORT_SCHEMA_VERSION,
    DecisionEvidenceSource,
    DecisionProvenance,
    ReportContributor,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceDecisionReasonCode,
    ToleranceDecisionReport,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
)
from origlyph.tolerance.audit import (
    ReplayabilityStatus,
    ToleranceDecisionAuditPackage,
    build_decision_audit_package,
)
from origlyph.tolerance.comparison import (
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
    AuditPackageComparisonResult,
    InvalidAuditComparisonError,
    compare_decision_audit_packages,
)
from origlyph.tolerance.integrity import (
    AuditIntegrityResult,
    AuditIntegritySeverity,
    AuditIntegrityStatus,
    AuditIntegrityViolation,
    AuditIntegrityViolationCode,
)

_SECTION_ORDER = tuple(ReportSection)


def _report(
    *,
    status: ToleranceDecisionStatus = ToleranceDecisionStatus.PASS,
    summary_code: str = "pass:within_limits",
    evidence_refs: tuple[ReportEvidenceRef, ...] = (),
    triggered_reasons: tuple[ReportReasonRef, ...] = (),
    governing_reason_codes: tuple[ToleranceDecisionReasonCode, ...] = (),
    marginal_reason_codes: tuple[ToleranceDecisionReasonCode, ...] = (),
    contributors: tuple[ReportContributor, ...] = (),
    worst_case_metrics: tuple[ReportMetricValue, ...] = (),
    statistical_metrics: tuple[ReportMetricValue, ...] = (),
    correlation_metrics: tuple[ReportMetricValue, ...] = (),
    allocation_metrics: tuple[ReportMetricValue, ...] = (),
    worst_case_reconciliation_metrics: tuple[ReportMetricValue, ...] = (),
    statistical_reconciliation_metrics: tuple[ReportMetricValue, ...] = (),
    equality_tolerance: float = 1e-9,
    sigma_multiplier: float | None = None,
    provenance: DecisionProvenance | None = None,
) -> ToleranceDecisionReport:
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=status,
        is_complete=True,
        summary_code=summary_code,
        summary_text="Deterministic comparison fixture.",
        governing_reason_codes=governing_reason_codes,
        marginal_reason_codes=marginal_reason_codes,
        supporting_reason_codes=(),
        triggered_reasons=triggered_reasons,
        contributors=contributors,
        worst_case_metrics=worst_case_metrics,
        statistical_metrics=statistical_metrics,
        correlation_metrics=correlation_metrics,
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=allocation_metrics,
        worst_case_reconciliation_metrics=worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=statistical_reconciliation_metrics,
        evidence_refs=evidence_refs,
        equality_tolerance=equality_tolerance,
        sigma_multiplier=sigma_multiplier,
        section_order=_SECTION_ORDER,
        provenance=provenance,
    )


def _package(
    report: ToleranceDecisionReport | None = None,
    integrity_result: AuditIntegrityResult | None = None,
    *,
    provenance: DecisionProvenance | None = None,
) -> ToleranceDecisionAuditPackage:
    return build_decision_audit_package(
        report or _report(), integrity_result, provenance=provenance
    )


def _evidence(
    evidence_id: str = "worst_case:within_limit:requirement:limit:000",
    *,
    source: DecisionEvidenceSource = DecisionEvidenceSource.WORST_CASE,
    reason_code: str = "",
) -> ReportEvidenceRef:
    return ReportEvidenceRef(
        evidence_id=evidence_id,
        source=source.value,
        evidence_code="within_limit",
        reason_code=reason_code,
    )


def _fail_report(evidence_id: str = "worst_case:exceeded:requirement:limit:000"):
    reason_code = ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    return _report(
        status=ToleranceDecisionStatus.FAIL,
        summary_code="fail:wc_span_exceeds_limit",
        governing_reason_codes=(reason_code,),
        triggered_reasons=(
            ReportReasonRef(
                reason_code=reason_code,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope=reason_code,
                detail="requirement exceeded",
                evidence_ids=(evidence_id,),
            ),
        ),
        evidence_refs=(
            ReportEvidenceRef(
                evidence_id=evidence_id,
                source=DecisionEvidenceSource.WORST_CASE.value,
                evidence_code="wc_span_exceeds_limit",
                reason_code=reason_code.value,
            ),
        ),
    )


def _marginal_report(
    evidence_id: str = "worst_case:boundary:requirement:limit:000",
):
    reason_code = ToleranceDecisionReasonCode.WC_REQUIREMENT_AT_BOUNDARY
    return _report(
        status=ToleranceDecisionStatus.MARGINAL,
        summary_code="marginal:wc_span_at_limit",
        marginal_reason_codes=(reason_code,),
        triggered_reasons=(
            ReportReasonRef(
                reason_code=reason_code,
                severity=ToleranceDecisionSeverity.BOUNDARY,
                scope=reason_code,
                detail="requirement at boundary",
                evidence_ids=(evidence_id,),
            ),
        ),
        evidence_refs=(
            ReportEvidenceRef(
                evidence_id=evidence_id,
                source=DecisionEvidenceSource.WORST_CASE.value,
                evidence_code="wc_span_at_limit",
                reason_code=reason_code.value,
            ),
        ),
    )


def _invalid_integrity() -> AuditIntegrityResult:
    return AuditIntegrityResult(
        status=AuditIntegrityStatus.INVALID,
        violations=(
            AuditIntegrityViolation(
                code=AuditIntegrityViolationCode.STATUS_MISMATCH,
                severity=AuditIntegritySeverity.ERROR,
                scope="report.summary_code",
                subject="fixture",
                detail="fixture violation",
            ),
        ),
    )


def _codes(result: AuditPackageComparisonResult) -> set[AuditChangeCode]:
    return {change.code for change in result.changes}


def _categories(result: AuditPackageComparisonResult) -> set[AuditChangeCategory]:
    return {change.category for change in result.changes}


def test_identical_packages_have_zero_changes() -> None:
    result = compare_decision_audit_packages(_package(), _package())
    assert result.status is AuditComparisonStatus.IDENTICAL
    assert result.changes == ()


def test_provenance_only_difference_is_ignored() -> None:
    report = _report()
    baseline = _package(
        report,
        provenance=DecisionProvenance(
            generated_by="actor-a", generation_timestamp="2026-01-01"
        ),
    )
    candidate = _package(
        report,
        provenance=DecisionProvenance(
            generated_by="actor-b", generation_timestamp="2030-01-01"
        ),
    )
    result = compare_decision_audit_packages(baseline, candidate)
    assert result.status is AuditComparisonStatus.IDENTICAL
    assert not result.provenance_compared


def test_input_change_is_detected() -> None:
    metric = ReportMetricValue("worst_case.allowed_span", 0.5)
    result = compare_decision_audit_packages(
        _package(), _package(_report(worst_case_metrics=(metric,)))
    )
    assert AuditChangeCategory.INPUT in _categories(result)
    assert AuditChangeCode.INPUT_FINGERPRINT_CHANGED in _codes(result)


def test_policy_changes_are_detected() -> None:
    baseline = _package(_report(equality_tolerance=1e-9, sigma_multiplier=3.0))
    candidate = _package(_report(equality_tolerance=1e-8, sigma_multiplier=6.0))
    result = compare_decision_audit_packages(baseline, candidate)
    assert AuditChangeCode.EQUALITY_TOLERANCE_CHANGED in _codes(result)
    assert AuditChangeCode.SIGMA_MULTIPLIER_CHANGED in _codes(result)


def test_decision_status_transition_is_neutral() -> None:
    result = compare_decision_audit_packages(_package(), _package(_fail_report()))
    change = next(
        item
        for item in result.changes
        if item.code is AuditChangeCode.DECISION_STATUS_CHANGED
    )
    assert change.baseline_value == "pass"
    assert change.candidate_value == "fail"
    assert "better" not in change.detail
    assert "worse" not in change.detail


def test_integrity_and_replayability_transitions_are_detected() -> None:
    baseline = _package()
    candidate = _package(integrity_result=_invalid_integrity())
    result = compare_decision_audit_packages(baseline, candidate)
    assert AuditChangeCode.INTEGRITY_STATUS_CHANGED in _codes(result)
    assert AuditChangeCode.INTEGRITY_VIOLATION_ADDED in _codes(result)
    assert AuditChangeCode.REPLAYABILITY_STATUS_CHANGED in _codes(result)


def test_evidence_added_and_removed_are_detected() -> None:
    empty = _package()
    with_evidence = _package(_report(evidence_refs=(_evidence(),)))
    added = compare_decision_audit_packages(empty, with_evidence)
    removed = compare_decision_audit_packages(with_evidence, empty)
    assert AuditChangeCode.EVIDENCE_ADDED in _codes(added)
    assert AuditChangeCode.EVIDENCE_REMOVED in _codes(removed)


def test_evidence_code_and_source_changes_are_detected() -> None:
    original = _evidence()
    changed = replace(
        original,
        source=DecisionEvidenceSource.STATISTICAL.value,
        evidence_code="different_code",
    )
    result = compare_decision_audit_packages(
        _package(_report(evidence_refs=(original,))),
        _package(_report(evidence_refs=(changed,))),
    )
    assert AuditChangeCode.EVIDENCE_CODE_CHANGED in _codes(result)
    assert AuditChangeCode.EVIDENCE_SOURCE_CHANGED in _codes(result)


def test_reason_link_change_is_detected() -> None:
    original = _evidence()
    changed = replace(
        original,
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED.value,
    )
    result = compare_decision_audit_packages(
        _package(_report(evidence_refs=(original,))),
        _package(_report(evidence_refs=(changed,))),
    )
    assert AuditChangeCode.REASON_LINK_CHANGED in _codes(result)


def test_governing_evidence_and_summary_changes_are_detected() -> None:
    baseline = _package(_fail_report("worst_case:exceeded:req:a:000"))
    candidate = _package(_fail_report("worst_case:exceeded:req:b:000"))
    result = compare_decision_audit_packages(baseline, candidate)
    assert AuditChangeCode.GOVERNING_EVIDENCE_CHANGED in _codes(result)
    changed_summary = _package(
        replace(_fail_report(), summary_code="fail:alternate_code")
    )
    summary_result = compare_decision_audit_packages(
        _package(_fail_report()), changed_summary
    )
    assert AuditChangeCode.SUMMARY_CODE_CHANGED in _codes(summary_result)


def test_marginal_evidence_change_is_detected() -> None:
    result = compare_decision_audit_packages(
        _package(_marginal_report("worst_case:boundary:req:a:000")),
        _package(_marginal_report("worst_case:boundary:req:b:000")),
    )
    assert AuditChangeCode.MARGINAL_EVIDENCE_CHANGED in _codes(result)


def test_contributor_add_remove_and_order_are_detected() -> None:
    contributor_a = ReportContributor("A", "worst_case", 0.3, is_worst_case=True)
    contributor_b = ReportContributor("B", "worst_case", 0.2, is_worst_case=True)
    empty = _package()
    one = _package(_report(contributors=(contributor_a,)))
    assert AuditChangeCode.CONTRIBUTOR_ADDED in _codes(
        compare_decision_audit_packages(empty, one)
    )
    assert AuditChangeCode.CONTRIBUTOR_REMOVED in _codes(
        compare_decision_audit_packages(one, empty)
    )
    order = compare_decision_audit_packages(
        _package(_report(contributors=(contributor_a, contributor_b))),
        _package(_report(contributors=(contributor_b, contributor_a))),
    )
    assert AuditChangeCode.CONTRIBUTOR_ORDER_CHANGED in _codes(order)


def test_contributor_span_and_sigma_changes_are_detected() -> None:
    baseline = ReportContributor(
        "A", "combined", 0.3, contribution_sigma=0.05, is_worst_case=True
    )
    candidate = replace(baseline, contribution_value=0.4, contribution_sigma=0.07)
    result = compare_decision_audit_packages(
        _package(_report(contributors=(baseline,))),
        _package(_report(contributors=(candidate,))),
    )
    assert AuditChangeCode.CONTRIBUTOR_SPAN_CHANGED in _codes(result)
    assert AuditChangeCode.CONTRIBUTOR_SIGMA_CHANGED in _codes(result)


@pytest.mark.parametrize(
    ("section_field", "metric_key", "expected_code"),
    [
        ("allocation_metrics", "allocation.A", AuditChangeCode.ALLOCATION_CHANGED),
        (
            "allocation_metrics",
            "stat_allocation.A",
            AuditChangeCode.STATISTICAL_ALLOCATION_CHANGED,
        ),
        (
            "worst_case_reconciliation_metrics",
            "reconciliation.margin",
            AuditChangeCode.RECONCILIATION_MARGIN_CHANGED,
        ),
        (
            "statistical_reconciliation_metrics",
            "reconciliation.status",
            AuditChangeCode.RECONCILIATION_CHANGED,
        ),
    ],
)
def test_allocation_and_reconciliation_changes(
    section_field: str,
    metric_key: str,
    expected_code: AuditChangeCode,
) -> None:
    baseline_metric = (ReportMetricValue(metric_key, 1.0),)
    candidate_metric = (ReportMetricValue(metric_key, 2.0),)
    if section_field == "allocation_metrics":
        baseline_report = _report(allocation_metrics=baseline_metric)
        candidate_report = _report(allocation_metrics=candidate_metric)
    elif section_field == "worst_case_reconciliation_metrics":
        baseline_report = _report(
            worst_case_reconciliation_metrics=baseline_metric
        )
        candidate_report = _report(
            worst_case_reconciliation_metrics=candidate_metric
        )
    else:
        baseline_report = _report(
            statistical_reconciliation_metrics=baseline_metric
        )
        candidate_report = _report(
            statistical_reconciliation_metrics=candidate_metric
        )
    result = compare_decision_audit_packages(
        _package(baseline_report), _package(candidate_report)
    )
    assert expected_code in _codes(result)


def test_correlation_added_removed_and_rho_changed() -> None:
    correlation = ReportMetricValue("correlation.A.B", 0.5, -1.0, 1.0)
    changed = ReportMetricValue("correlation.A.B", -0.2, -1.0, 1.0)
    empty = _package()
    present = _package(_report(correlation_metrics=(correlation,)))
    assert AuditChangeCode.CORRELATION_PAIR_ADDED in _codes(
        compare_decision_audit_packages(empty, present)
    )
    assert AuditChangeCode.CORRELATION_PAIR_REMOVED in _codes(
        compare_decision_audit_packages(present, empty)
    )
    rho = compare_decision_audit_packages(
        present, _package(_report(correlation_metrics=(changed,)))
    )
    assert AuditChangeCode.CORRELATION_RHO_CHANGED in _codes(rho)


def test_all_identity_fingerprint_changes_are_reported() -> None:
    baseline = _package()
    candidate = _package(_report(worst_case_metrics=(ReportMetricValue("x", 1.0),)))
    codes = _codes(compare_decision_audit_packages(baseline, candidate))
    assert AuditChangeCode.DECISION_ID_CHANGED in codes
    assert AuditChangeCode.PACKAGE_ID_CHANGED in codes
    assert AuditChangeCode.INPUT_FINGERPRINT_CHANGED in codes
    assert AuditChangeCode.REPORT_FINGERPRINT_CHANGED in codes


def test_integrity_fingerprint_change_is_reported() -> None:
    result = compare_decision_audit_packages(
        _package(), _package(integrity_result=_invalid_integrity())
    )
    assert AuditChangeCode.INTEGRITY_FINGERPRINT_CHANGED in _codes(result)


def test_integrity_violation_change_is_detected() -> None:
    baseline_integrity = _invalid_integrity()
    candidate_violation = replace(
        baseline_integrity.violations[0],
        code=AuditIntegrityViolationCode.COMPLETENESS_MISMATCH,
    )
    candidate_integrity = replace(
        baseline_integrity, violations=(candidate_violation,)
    )
    result = compare_decision_audit_packages(
        _package(integrity_result=baseline_integrity),
        _package(integrity_result=candidate_integrity),
    )
    assert AuditChangeCode.INTEGRITY_VIOLATION_CHANGED in _codes(result)


def test_unexplained_fingerprint_drift_is_incompatible() -> None:
    baseline = _package()
    manifest = replace(
        baseline.replay_manifest, report_fingerprint="0" * 64
    )
    candidate = replace(baseline, replay_manifest=manifest)
    result = compare_decision_audit_packages(baseline, candidate)
    assert result.status is AuditComparisonStatus.INCOMPATIBLE
    assert AuditChangeCode.UNEXPLAINED_FINGERPRINT_DRIFT in _codes(result)


def test_unsupported_audit_schema_is_incompatible() -> None:
    package = _package()
    candidate = replace(package, audit_schema_version="unsupported")
    result = compare_decision_audit_packages(package, candidate)
    assert result.status is AuditComparisonStatus.INCOMPATIBLE


def test_unsupported_report_schema_is_incompatible() -> None:
    package = _package()
    candidate = replace(package, report=replace(package.report, schema_version="bad"))
    result = compare_decision_audit_packages(package, candidate)
    assert result.status is AuditComparisonStatus.INCOMPATIBLE
    assert AuditChangeCode.REPORT_SCHEMA_CHANGED in _codes(result)


def test_tampered_package_is_not_compared_as_valid() -> None:
    package = _package()
    tampered = replace(package, package_id="0" * 64)
    result = compare_decision_audit_packages(package, tampered)
    assert result.status is AuditComparisonStatus.INCOMPATIBLE
    assert AuditChangeCode.PACKAGE_VERIFICATION_FAILED in _codes(result)


def test_deterministic_order_and_serialization() -> None:
    baseline = _package()
    candidate = _package(
        _report(
            equality_tolerance=1e-8,
            worst_case_metrics=(ReportMetricValue("z", 2.0),),
            contributors=(ReportContributor("Z", "worst_case", 0.2),),
        )
    )
    first = compare_decision_audit_packages(baseline, candidate)
    second = compare_decision_audit_packages(baseline, candidate)
    assert first == second
    assert first.as_dict() == second.as_dict()
    assert first.to_json() == second.to_json()


def test_models_are_frozen() -> None:
    result = compare_decision_audit_packages(_package(), _package())
    with pytest.raises(FrozenInstanceError):
        result.status = AuditComparisonStatus.CHANGED  # type: ignore[misc]
    assert AuditChangeSignificance.ENGINEERING_RELEVANT.value == (
        "engineering_relevant"
    )


def test_wrong_inputs_raise() -> None:
    package = _package()
    with pytest.raises(InvalidAuditComparisonError):
        compare_decision_audit_packages("bad", package)  # type: ignore[arg-type]
    with pytest.raises(InvalidAuditComparisonError):
        compare_decision_audit_packages(package, "bad")  # type: ignore[arg-type]


def test_comparison_does_not_mutate_packages() -> None:
    baseline = _package()
    candidate = _package(_report(equality_tolerance=1e-8))
    left_before = deepcopy(baseline.as_dict())
    right_before = deepcopy(candidate.as_dict())
    compare_decision_audit_packages(baseline, candidate)
    assert baseline.as_dict() == left_before
    assert candidate.as_dict() == right_before


def test_no_engineering_recomputation(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _package()
    candidate = _package(_report(equality_tolerance=1e-8))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("authoritative engineering engine was called")

    targets = (
        ("origlyph.tolerance.worst_case", "worst_case"),
        ("origlyph.tolerance.statistical", "statistical"),
        ("origlyph.tolerance.sensitivity", "worst_case_sensitivity"),
        ("origlyph.tolerance.sensitivity", "statistical_sensitivity"),
        ("origlyph.tolerance.budget", "worst_case_budget"),
        ("origlyph.tolerance.budget", "statistical_budget"),
        ("origlyph.tolerance.allocation", "validate_allocation"),
        ("origlyph.tolerance.reconciliation", "reconcile_allocation"),
        (
            "origlyph.tolerance.statistical_reconciliation",
            "reconcile_statistical_allocation",
        ),
        ("origlyph.tolerance.decision", "evaluate_tolerance_decision"),
    )
    for module_name, function_name in targets:
        monkeypatch.setattr(
            importlib.import_module(module_name), function_name, forbidden
        )

    result = compare_decision_audit_packages(baseline, candidate)
    assert result.status is AuditComparisonStatus.CHANGED


def test_public_api_exports_stage_15p_symbols() -> None:
    import origlyph.tolerance as tolerance

    expected = {
        "AuditComparisonStatus",
        "AuditChangeCategory",
        "AuditChangeCode",
        "AuditChangeSignificance",
        "AuditChange",
        "AuditPackageComparisonResult",
        "InvalidAuditComparisonError",
        "compare_decision_audit_packages",
    }
    assert expected.issubset(tolerance.__all__)
    assert all(hasattr(tolerance, name) for name in expected)


def test_replayability_is_separate_from_engineering_status() -> None:
    package = _package(_fail_report())
    assert package.report.final_status is ToleranceDecisionStatus.FAIL
    assert package.replayability_status is ReplayabilityStatus.REPLAYABLE
    assert isinstance(package, ToleranceDecisionAuditPackage)
