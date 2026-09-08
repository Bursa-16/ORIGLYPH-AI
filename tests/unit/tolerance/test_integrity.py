"""Stage 15N tests: deterministic audit-integrity validation.

Tests cover VALID, STATUS_MISMATCH, COMPLETENESS_MISMATCH,
MISSING_REASON_LINK, ORPHAN_REASON_LINK, MISSING_GOVERNING_EVIDENCE,
MISSING_MARGINAL_EVIDENCE, DUPLICATE_EVIDENCE_ID, BROKEN_EVIDENCE_REFERENCE,
UNSUPPORTED_EVIDENCE_SOURCE, UNKNOWN_SUBJECT_REFERENCE,
UNSUPPORTED_SCHEMA_VERSION, DECISION_ID_MISMATCH, ROUND_TRIP_MISMATCH,
NON_FINITE_VALUE, EXPLANATION_UNKNOWN_EVIDENCE, GOVERNING_REASON_NOT_IN_DECISION,
provenance-independence, deterministic ordering, as_dict determinism,
no-engineering-recomputation, input immutability, and Stage 15K/15L/15M
regressions.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from origlyph.tolerance import (
    REPORT_SCHEMA_VERSION,
    DecisionEvidenceSource,
    ReportContributor,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceDecisionReasonCode,
    ToleranceDecisionReport,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    decision_report_from_dict,
)
from origlyph.tolerance.decision import evaluate_tolerance_decision
from origlyph.tolerance.evidence import (
    build_decision_evidence,
    explain_tolerance_decision,
)
from origlyph.tolerance.integrity import (
    AuditIntegrityResult,
    AuditIntegrityStatus,
    AuditIntegrityViolationCode,
    InvalidAuditIntegrityError,
    validate_decision_report_integrity,
)
from origlyph.tolerance.models import (
    AllocationPlan,
    Correlation,
    StatisticalContribution,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceStack,
)
from origlyph.tolerance.report import build_decision_report

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SECTION_ORDER = (
    ReportSection.DECISION,
    ReportSection.WORST_CASE,
    ReportSection.STATISTICAL,
    ReportSection.CORRELATION,
    ReportSection.SENSITIVITY,
    ReportSection.BUDGET,
    ReportSection.ALLOCATION,
    ReportSection.WORST_CASE_RECONCILIATION,
    ReportSection.STATISTICAL_RECONCILIATION,
    ReportSection.EVIDENCE,
)


def _minimal_pass_report() -> ToleranceDecisionReport:
    """Create a minimal valid PASS report."""
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="pass:within_limits",
        summary_text="All within limits.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=1e-9,
        section_order=_SECTION_ORDER,
    )


def _wc_stack() -> ToleranceStack:
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )


def _stat_stack() -> StatisticalStack:
    return StatisticalStack(
        (
            StatisticalContribution("A", 0.0, 0.05),
            StatisticalContribution("B", 0.0, 0.05),
        )
    )


def _pass_decision():
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )


def _fail_decision():
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.40,
    )


def _marginal_decision():
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.45 + 1e-13,
    )


def _incomplete_decision():
    plan = AllocationPlan(
        allowed_budget=0.50,
        allocations=(ToleranceAllocation("A", 0.30),),
    )
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
        allowed_worst_case_span=0.50,
        require_complete=False,
    )


def _corr_decision():
    return evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", -0.9),),
    )


def _no_req_decision():
    return evaluate_tolerance_decision(worst_case_stack=_wc_stack())


# ---------------------------------------------------------------------------
# A. VALID REPORT
# ---------------------------------------------------------------------------


def test_valid_minimal_pass_report() -> None:
    """A minimal valid PASS report produces VALID with zero violations."""
    report = _minimal_pass_report()
    result = validate_decision_report_integrity(report)
    assert result.status is AuditIntegrityStatus.VALID
    assert result.violations == ()


def test_valid_full_pass_report() -> None:
    """A full PASS report built via build_decision_report is VALID."""
    dec = _pass_decision()
    bundle = build_decision_evidence(dec)
    expl = explain_tolerance_decision(dec, bundle)
    report = build_decision_report(dec, bundle, expl)
    result = validate_decision_report_integrity(report)
    assert result.status is AuditIntegrityStatus.VALID
    assert result.violations == ()


# ---------------------------------------------------------------------------
# B. STATUS MISMATCH
# ---------------------------------------------------------------------------


def test_status_mismatch_summary_code() -> None:
    """PASS status with fail: summary_code is a STATUS_MISMATCH."""
    report = _minimal_pass_report()
    # Tamper with summary_code to mismatch status
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code="fail:wc_span_exceeds_limit",
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=report.evidence_refs,
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.STATUS_MISMATCH in codes


def test_status_mismatch_pass_with_governing_reasons() -> None:
    """PASS status with governing reasons is a STATUS_MISMATCH."""
    report = _minimal_pass_report()
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=(
            ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        ),
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=report.evidence_refs,
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.STATUS_MISMATCH in codes


# ---------------------------------------------------------------------------
# C. COMPLETENESS MISMATCH
# ---------------------------------------------------------------------------


def test_completeness_mismatch() -> None:
    """is_complete=False with PASS status is a COMPLETENESS_MISMATCH."""
    report = _minimal_pass_report()
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=False,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=report.evidence_refs,
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.COMPLETENESS_MISMATCH in codes


# ---------------------------------------------------------------------------
# D. MISSING REASON LINK
# ---------------------------------------------------------------------------


def test_missing_reason_link_governing() -> None:
    """Governing reason with no evidence is MISSING_GOVERNING_EVIDENCE."""
    report = _minimal_pass_report()
    # Create a FAIL report with a governing reason but no evidence
    reason_ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        severity=ToleranceDecisionSeverity.FAILURE,
        scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        detail="test",
        evidence_ids=(),  # No evidence!
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.FAIL,
        is_complete=True,
        summary_code="fail:wc_span_exceeds_limit",
        summary_text="WC span exceeds limit.",
        governing_reason_codes=(
            ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        ),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(reason_ref,),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.MISSING_GOVERNING_EVIDENCE in codes
# ---------------------------------------------------------------------------
# E. ORPHAN REASON LINK
# ---------------------------------------------------------------------------


def test_orphan_reason_link_evidence_ref() -> None:
    """Evidence ref with unknown reason_code is ORPHAN_REASON_LINK."""
    report = _minimal_pass_report()
    evidence_ref = ReportEvidenceRef(
        evidence_id="ev1",
        source=DecisionEvidenceSource.WORST_CASE.value,
        evidence_code="wc_span_within_limit",
        reason_code="wc_requirement_exceeded",  # Not in triggered reasons!
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=(evidence_ref,),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.ORPHAN_REASON_LINK in codes


def test_orphan_triggered_reason_not_partitioned() -> None:
    """Triggered reason not in governing/marginal/supporting is orphan."""
    report = _minimal_pass_report()
    reason_ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
        severity=ToleranceDecisionSeverity.INFO,
        scope=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
        detail="test",
        evidence_ids=(),
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.INCOMPLETE,
        is_complete=True,
        summary_code="incomplete:no_stack_provided",
        summary_text="No stack provided.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),  # Not partitioned!
        triggered_reasons=(reason_ref,),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.ORPHAN_REASON_LINK in codes


# ---------------------------------------------------------------------------
# F. MISSING GOVERNING EVIDENCE
# ---------------------------------------------------------------------------


def test_missing_governing_evidence_fail_no_reasons() -> None:
    """FAIL status with no governing reasons is MISSING_GOVERNING_EVIDENCE."""
    report = _minimal_pass_report()
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.FAIL,
        is_complete=True,
        summary_code="fail:wc_span_exceeds_limit",
        summary_text="WC span exceeds limit.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.MISSING_GOVERNING_EVIDENCE in codes


# ---------------------------------------------------------------------------
# G. MISSING MARGINAL EVIDENCE
# ---------------------------------------------------------------------------


def test_missing_marginal_evidence() -> None:
    """MARGINAL status with no marginal reasons is MISSING_MARGINAL_EVIDENCE."""
    report = _minimal_pass_report()
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.MARGINAL,
        is_complete=True,
        summary_code="marginal:wc_span_at_limit",
        summary_text="WC span at limit.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.MISSING_MARGINAL_EVIDENCE in codes


# ---------------------------------------------------------------------------
# H. DUPLICATE EVIDENCE ID
# ---------------------------------------------------------------------------


def test_duplicate_evidence_id() -> None:
    """Duplicate evidence IDs are DUPLICATE_EVIDENCE_ID."""
    report = _minimal_pass_report()
    ev1 = ReportEvidenceRef(
        evidence_id="ev1",
        source=DecisionEvidenceSource.WORST_CASE.value,
        evidence_code="wc_span_within_limit",
        reason_code="",
    )
    ev2 = ReportEvidenceRef(
        evidence_id="ev1",  # Duplicate!
        source=DecisionEvidenceSource.STATISTICAL.value,
        evidence_code="stat_sigma_within_limit",
        reason_code="",
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=(ev1, ev2),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.DUPLICATE_EVIDENCE_ID in codes


# ---------------------------------------------------------------------------
# I. BROKEN EVIDENCE REFERENCE
# ---------------------------------------------------------------------------


def test_broken_evidence_reference() -> None:
    """Reason referencing an unknown evidence ID is BROKEN_EVIDENCE_REFERENCE."""
    report = _minimal_pass_report()
    reason_ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        severity=ToleranceDecisionSeverity.FAILURE,
        scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        detail="test",
        evidence_ids=("ghost_evidence",),  # Does not exist!
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.FAIL,
        is_complete=True,
        summary_code="fail:wc_span_exceeds_limit",
        summary_text="WC span exceeds limit.",
        governing_reason_codes=(
            ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        ),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(reason_ref,),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.BROKEN_EVIDENCE_REFERENCE in codes


# ---------------------------------------------------------------------------
# J. UNKNOWN CONTRIBUTOR REFERENCE
# ---------------------------------------------------------------------------


def test_unknown_contributor_reference() -> None:
    """Evidence ref subject referencing unknown contributor is flagged."""
    report = _minimal_pass_report()
    # Contributors table carries A and B.
    contributor_a = ReportContributor(
        name="A",
        contribution_type="worst_case",
        contribution_value=0.30,
        is_worst_case=True,
    )
    contributor_b = ReportContributor(
        name="B",
        contribution_type="worst_case",
        contribution_value=0.15,
        is_worst_case=True,
    )
    # Covariance evidence whose subject references Z|Q (unknown).
    ev = ReportEvidenceRef(
        evidence_id="correlated_statistical:covariance_pair_contribution:"
        "covariance:Z|Q:003",
        source=DecisionEvidenceSource.CORRELATED_STATISTICAL.value,
        evidence_code="covariance_pair_contribution",
        reason_code="",
    )
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.INCOMPLETE,
        is_complete=False,
        summary_code="incomplete:covariance_pair_contribution",
        summary_text="Covariance pair contribution.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(contributor_a, contributor_b),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(ev,),
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.UNKNOWN_SUBJECT_REFERENCE in codes


# ---------------------------------------------------------------------------
# K. UNSUPPORTED SCHEMA
# ---------------------------------------------------------------------------


def test_unsupported_schema_version() -> None:
    """Unsupported schema version produces INCOMPLETE status."""
    report = _minimal_pass_report()
    tampered = ToleranceDecisionReport(
        schema_version="origlyph.tolerance.decision_report.v999",
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=report.evidence_refs,
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INCOMPLETE
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.UNSUPPORTED_SCHEMA_VERSION in codes


# ---------------------------------------------------------------------------
# L. DECISION ID MISMATCH
# ---------------------------------------------------------------------------


def test_decision_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A report whose decision_id disagrees with canonical is flagged."""
    report = _minimal_pass_report()
    # Build a report whose decision_id() is overridden to a wrong value.
    tampered = ToleranceDecisionReport(
        schema_version=report.schema_version,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=report.is_complete,
        summary_code=report.summary_code,
        summary_text=report.summary_text,
        governing_reason_codes=report.governing_reason_codes,
        marginal_reason_codes=report.marginal_reason_codes,
        supporting_reason_codes=report.supporting_reason_codes,
        triggered_reasons=report.triggered_reasons,
        contributors=report.contributors,
        worst_case_metrics=report.worst_case_metrics,
        statistical_metrics=report.statistical_metrics,
        correlation_metrics=report.correlation_metrics,
        sensitivity_metrics=report.sensitivity_metrics,
        budget_metrics=report.budget_metrics,
        allocation_metrics=report.allocation_metrics,
        worst_case_reconciliation_metrics=report.worst_case_reconciliation_metrics,
        statistical_reconciliation_metrics=report.statistical_reconciliation_metrics,
        evidence_refs=report.evidence_refs,
        equality_tolerance=report.equality_tolerance,
        section_order=report.section_order,
    )

    # Monkeypatch decision_id to return a wrong value.
    def wrong_id(self: ToleranceDecisionReport) -> str:
        return "tampered-decision-id"

    monkeypatch.setattr(ToleranceDecisionReport, "decision_id", wrong_id)
    result = validate_decision_report_integrity(tampered)

    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.DECISION_ID_MISMATCH in codes


# ---------------------------------------------------------------------------
# M. ROUND-TRIP MISMATCH
# ---------------------------------------------------------------------------


def test_round_trip_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A report that fails round-trip is flagged, not raised."""
    report = _minimal_pass_report()
    # Monkeypatch decision_report_from_dict to return a corrupted report.
    import origlyph.tolerance.integrity as integrity_mod

    original = integrity_mod.decision_report_from_dict

    def corrupted(data: dict[str, object]) -> ToleranceDecisionReport:
        rebuilt = original(data)
        # Corrupt the round-tripped report's summary text.
        return ToleranceDecisionReport(
            schema_version=rebuilt.schema_version,
            final_status=rebuilt.final_status,
            is_complete=rebuilt.is_complete,
            summary_code=rebuilt.summary_code,
            summary_text="CORRUPTED",
            governing_reason_codes=rebuilt.governing_reason_codes,
            marginal_reason_codes=rebuilt.marginal_reason_codes,
            supporting_reason_codes=rebuilt.supporting_reason_codes,
            triggered_reasons=rebuilt.triggered_reasons,
            contributors=rebuilt.contributors,
            worst_case_metrics=rebuilt.worst_case_metrics,
            statistical_metrics=rebuilt.statistical_metrics,
            correlation_metrics=rebuilt.correlation_metrics,
            sensitivity_metrics=rebuilt.sensitivity_metrics,
            budget_metrics=rebuilt.budget_metrics,
            allocation_metrics=rebuilt.allocation_metrics,
            worst_case_reconciliation_metrics=(
                rebuilt.worst_case_reconciliation_metrics
            ),
            statistical_reconciliation_metrics=(
                rebuilt.statistical_reconciliation_metrics
            ),
            evidence_refs=rebuilt.evidence_refs,
            equality_tolerance=rebuilt.equality_tolerance,
            section_order=rebuilt.section_order,
        )

    monkeypatch.setattr(integrity_mod, "decision_report_from_dict", corrupted)
    result = validate_decision_report_integrity(report)

    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.ROUND_TRIP_MISMATCH in codes


# ---------------------------------------------------------------------------
# N. NON-FINITE VALUE
# ---------------------------------------------------------------------------


def test_non_finite_nan() -> None:
    """NaN in the report payload is NON_FINITE_VALUE."""
    report = _minimal_pass_report()
    metric = object.__new__(ReportMetricValue)
    object.__setattr__(metric, "key", "bad.key")
    object.__setattr__(metric, "value", float("nan"))
    object.__setattr__(metric, "lower_bound", None)
    object.__setattr__(metric, "upper_bound", None)
    tampered = replace(report, worst_case_metrics=(metric,))
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.NON_FINITE_VALUE in codes


def test_non_finite_inf() -> None:
    """+inf in the report payload is NON_FINITE_VALUE."""
    report = _minimal_pass_report()
    metric = object.__new__(ReportMetricValue)
    object.__setattr__(metric, "key", "bad.key")
    object.__setattr__(metric, "value", float("inf"))
    object.__setattr__(metric, "lower_bound", None)
    object.__setattr__(metric, "upper_bound", None)
    tampered = replace(report, worst_case_metrics=(metric,))
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.NON_FINITE_VALUE in codes


def test_non_finite_neg_inf() -> None:
    """-inf in the report payload is NON_FINITE_VALUE."""
    report = _minimal_pass_report()
    metric = object.__new__(ReportMetricValue)
    object.__setattr__(metric, "key", "bad.key")
    object.__setattr__(metric, "value", float("-inf"))
    object.__setattr__(metric, "lower_bound", None)
    object.__setattr__(metric, "upper_bound", None)
    tampered = replace(report, worst_case_metrics=(metric,))
    result = validate_decision_report_integrity(tampered)
    assert result.status is AuditIntegrityStatus.INVALID
    codes = [v.code for v in result.violations]
    assert AuditIntegrityViolationCode.NON_FINITE_VALUE in codes


# ---------------------------------------------------------------------------
# O. DETERMINISM, IMMUTABILITY, SERIALIZATION, AND COMPATIBILITY
# ---------------------------------------------------------------------------


def test_repeated_validation_and_serialization_are_stable() -> None:
    report = _minimal_pass_report()
    first = validate_decision_report_integrity(report)
    second = validate_decision_report_integrity(report)
    assert first == second
    assert json.dumps(first.as_dict(), sort_keys=True, allow_nan=False) == json.dumps(
        second.as_dict(), sort_keys=True, allow_nan=False
    )


def test_violation_order_is_deterministic() -> None:
    report = replace(
        _minimal_pass_report(),
        final_status=ToleranceDecisionStatus.FAIL,
        summary_code="pass:within_limits",
        is_complete=False,
    )
    result = validate_decision_report_integrity(report)
    assert result.violations == tuple(
        sorted(
            result.violations,
            key=lambda item: (
                item.severity.value,
                item.code.value,
                item.scope,
                item.subject,
            ),
        )
    )


def test_result_and_violation_are_frozen() -> None:
    result = validate_decision_report_integrity(_minimal_pass_report())
    with pytest.raises(FrozenInstanceError):
        result.status = AuditIntegrityStatus.INVALID  # type: ignore[misc]


def test_validation_does_not_mutate_report() -> None:
    decision = _pass_decision()
    evidence = build_decision_evidence(decision)
    explanation = explain_tolerance_decision(decision, evidence)
    report = build_decision_report(decision, evidence, explanation)
    before = deepcopy(report.as_dict())
    validate_decision_report_integrity(report)
    assert report.as_dict() == before


def test_invalid_input_is_rejected() -> None:
    with pytest.raises(InvalidAuditIntegrityError):
        validate_decision_report_integrity("not a report")  # type: ignore[arg-type]


def test_public_api_exports_integrity_symbols() -> None:
    import origlyph.tolerance as tolerance

    assert tolerance.AuditIntegrityResult is AuditIntegrityResult
    assert tolerance.validate_decision_report_integrity is (
        validate_decision_report_integrity
    )


def test_existing_report_round_trip_remains_compatible() -> None:
    report = _minimal_pass_report()
    rebuilt = decision_report_from_dict(report.as_dict())
    assert validate_decision_report_integrity(rebuilt).status is (
        AuditIntegrityStatus.VALID
    )
