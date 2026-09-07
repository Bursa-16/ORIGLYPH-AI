"""Stage 15M tests: deterministic decision report envelope."""

from __future__ import annotations

import pytest

from origlyph.tolerance import (
    REPORT_SCHEMA_VERSION,
    DecisionProvenance,
    InvalidDecisionReportError,
    ReportContributor,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceDecisionReasonCode,
    ToleranceDecisionReport,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    build_decision_report,
    build_tolerance_decision_report,
    decision_report_from_dict,
)

_REPORT_SECTION_ORDER = (
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


def _minimal_report() -> ToleranceDecisionReport:
    """Create a minimal valid report."""
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="Pass",
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
        section_order=_REPORT_SECTION_ORDER,
    )


def test_schema_version_exact() -> None:
    assert REPORT_SCHEMA_VERSION == "origlyph.tolerance.decision_report.v1"


def test_schema_version_is_string() -> None:
    assert isinstance(REPORT_SCHEMA_VERSION, str)


def test_report_metric_value_basic() -> None:
    m = ReportMetricValue(key="test.key", value=1.5)
    assert m.key == "test.key"
    assert m.value == 1.5
    assert m.lower_bound is None
    assert m.upper_bound is None


def test_report_metric_value_with_bounds() -> None:
    m = ReportMetricValue(key="test", value=2.0, lower_bound=1.0, upper_bound=3.0)
    assert m.lower_bound == 1.0
    assert m.upper_bound == 3.0


def test_report_metric_value_frozen() -> None:
    m = ReportMetricValue(key="test", value=1.0)
    with pytest.raises(AttributeError):
        m.key = "changed"  # type: ignore


def test_report_metric_value_rejects_nan() -> None:
    with pytest.raises(InvalidDecisionReportError):
        ReportMetricValue(key="test", value=float("nan"))


def test_report_metric_value_rejects_inf() -> None:
    with pytest.raises(InvalidDecisionReportError):
        ReportMetricValue(key="test", value=float("inf"))


def test_report_metric_value_as_dict() -> None:
    m = ReportMetricValue(key="a", value=1.0, lower_bound=0.0, upper_bound=2.0)
    d1 = m.as_dict()
    d2 = m.as_dict()
    assert d1 == d2
    assert "key" in d1
    assert "value" in d1


def test_report_reason_ref_basic() -> None:
    ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        severity=ToleranceDecisionSeverity.FAILURE,
        scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        detail="test detail",
        evidence_ids=("eid1", "eid2"),
    )
    assert ref.reason_code == ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    assert ref.severity == ToleranceDecisionSeverity.FAILURE
    assert ref.evidence_ids == ("eid1", "eid2")


def test_report_reason_ref_frozen() -> None:
    ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        severity=ToleranceDecisionSeverity.FAILURE,
        scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        detail="test",
        evidence_ids=(),
    )
    with pytest.raises(AttributeError):
        ref.detail = "changed"  # type: ignore


def test_report_reason_ref_as_dict() -> None:
    ref = ReportReasonRef(
        reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        severity=ToleranceDecisionSeverity.FAILURE,
        scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
        detail="detail",
        evidence_ids=("e1",),
    )
    d = ref.as_dict()
    assert d["reason_code"] == "wc_requirement_exceeded"
    assert d["severity"] == "failure"
    assert d["evidence_ids"] == ["e1"]


def test_report_evidence_ref_basic() -> None:
    ref = ReportEvidenceRef(
        evidence_id="eid123",
        source="WORST_CASE_ANALYSIS",
        evidence_code="WC_REQUIREMENT_EXCEEDED",
        reason_code="wc_requirement_exceeded",
    )
    assert ref.evidence_id == "eid123"


def test_report_evidence_ref_frozen() -> None:
    ref = ReportEvidenceRef(
        evidence_id="eid",
        source="SRC",
        evidence_code="CODE",
        reason_code="REASON",
    )
    with pytest.raises(AttributeError):
        ref.evidence_id = "changed"  # type: ignore


def test_report_contributor_basic() -> None:
    c = ReportContributor(
        name="part_a",
        contribution_type="worst_case",
        contribution_value=0.1,
        is_worst_case=True,
    )
    assert c.name == "part_a"
    assert c.contribution_value == 0.1


def test_report_contributor_frozen() -> None:
    c = ReportContributor(
        name="part",
        contribution_type="statistical",
        is_statistical=True,
    )
    with pytest.raises(AttributeError):
        c.name = "changed"  # type: ignore


def test_report_section_has_sections() -> None:
    sections = list(ReportSection)
    assert len(sections) == 10
    assert ReportSection.DECISION in sections
    assert ReportSection.EVIDENCE in sections


def test_decision_provenance_empty() -> None:
    p = DecisionProvenance()
    assert p.generated_by is None
    assert p.generation_timestamp is None
    assert p.audit_id is None
    assert p.metadata == {}


def test_decision_provenance_with_metadata() -> None:
    p = DecisionProvenance(
        generated_by="test-runner",
        audit_id="audit-123",
        metadata={"env": "test"},
    )
    assert p.generated_by == "test-runner"
    assert p.audit_id == "audit-123"
    assert p.metadata["env"] == "test"


def test_decision_provenance_frozen() -> None:
    p = DecisionProvenance()
    with pytest.raises(AttributeError):
        p.generated_by = "changed"  # type: ignore


def test_tolerance_decision_report_basic() -> None:
    report = _minimal_report()
    assert report.schema_version == REPORT_SCHEMA_VERSION
    assert report.final_status == ToleranceDecisionStatus.PASS


def test_tolerance_decision_report_frozen() -> None:
    report = _minimal_report()
    with pytest.raises(AttributeError):
        report.final_status = ToleranceDecisionStatus.FAIL  # type: ignore


def test_tolerance_decision_report_rejects_nan_tolerance() -> None:
    with pytest.raises(InvalidDecisionReportError):
        ToleranceDecisionReport(
            schema_version=REPORT_SCHEMA_VERSION,
            final_status=ToleranceDecisionStatus.PASS,
            is_complete=True,
            summary_code="PASS",
            summary_text="Test",
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
            equality_tolerance=float("nan"),
            section_order=_REPORT_SECTION_ORDER,
        )


def test_tolerance_decision_report_as_dict() -> None:
    report = _minimal_report()
    d1 = report.as_dict()
    d2 = report.as_dict()
    assert d1 == d2


def test_tolerance_decision_report_to_json() -> None:
    report = _minimal_report()
    j1 = report.to_json()
    j2 = report.to_json()
    assert j1 == j2


def test_tolerance_decision_report_decision_id() -> None:
    report = _minimal_report()
    id1 = report.decision_id()
    id2 = report.decision_id()
    assert id1 == id2
    assert isinstance(id1, str)


def test_report_from_dict_round_trip() -> None:
    report = _minimal_report()
    d = report.as_dict()
    rebuilt = decision_report_from_dict(d)
    assert rebuilt.schema_version == report.schema_version
    assert rebuilt.final_status == report.final_status


def test_report_from_dict_rejects_wrong_schema() -> None:
    d = _minimal_report().as_dict()
    d["schema_version"] = "wrong.version"
    with pytest.raises(InvalidDecisionReportError):
        decision_report_from_dict(d)


def test_report_from_dict_rejects_missing_field() -> None:
    d = _minimal_report().as_dict()
    del d["schema_version"]
    with pytest.raises(InvalidDecisionReportError):
        decision_report_from_dict(d)


def test_report_from_dict_rejects_non_dict() -> None:
    with pytest.raises(InvalidDecisionReportError):
        decision_report_from_dict("not a dict")  # type: ignore


def test_no_uuid_in_models() -> None:
    m = ReportMetricValue(key="test", value=1.0)
    assert not hasattr(m, "uuid")
    assert not hasattr(m, "id")
    assert not hasattr(m, "timestamp")


def test_json_determinism() -> None:
    report = _minimal_report()
    json1 = report.to_json()
    json2 = report.to_json()
    assert json1 == json2


def test_build_alias_equivalence() -> None:
    assert build_decision_report is build_tolerance_decision_report
