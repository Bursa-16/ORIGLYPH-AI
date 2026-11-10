"""Unit tests for the deterministic decision report HTML export (Stage 21B)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from origlyph.tolerance.html_export import (
    DecisionReportHtmlExportError,
    render_decision_report_html,
    write_decision_report_html,
)
from origlyph.tolerance.models import (
    ToleranceDecisionReasonCode,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
)
from origlyph.tolerance.report import (
    REPORT_SCHEMA_VERSION,
    ReportContributor,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceDecisionReport,
)

# ---------------------------------------------------------------------------
# Section order constant (mirrors private constant in report module)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_report(
    status: ToleranceDecisionStatus = ToleranceDecisionStatus.PASS,
) -> ToleranceDecisionReport:
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=status,
        is_complete=True,
        summary_code="PASS",
        summary_text="All criteria met.",
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


def _report_with_contributors() -> ToleranceDecisionReport:
    contributors = (
        ReportContributor(
            name="Part A",
            contribution_type="worst_case",
            contribution_value=0.3,
            is_worst_case=True,
        ),
        ReportContributor(
            name="Part B",
            contribution_type="statistical",
            contribution_value=0.05,
            contribution_sigma=0.025,
            is_statistical=True,
        ),
    )
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="Pass with contributors.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=contributors,
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


def _report_with_metrics() -> ToleranceDecisionReport:
    wc_metrics = (
        ReportMetricValue(key="worst_case.Part_A", value=0.3),
        ReportMetricValue(
            key="worst_case.Part_B", value=0.2, lower_bound=0.0, upper_bound=0.5
        ),
    )
    stat_metrics = (
        ReportMetricValue(key="statistical.Part_A", value=0.15),
    )
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="Pass with metrics.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(),
        worst_case_metrics=wc_metrics,
        statistical_metrics=stat_metrics,
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


def _report_with_reasons() -> ToleranceDecisionReport:
    governing = (ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,)
    marginal = (ToleranceDecisionReasonCode.WC_REQUIREMENT_AT_BOUNDARY,)
    supporting = (ToleranceDecisionReasonCode.NO_REQUIREMENT_PROVIDED,)
    triggered = (
        ReportReasonRef(
            reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
            severity=ToleranceDecisionSeverity.FAILURE,
            scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
            detail="Actual span 1.5 exceeds limit 1.0",
            evidence_ids=("ev001",),
        ),
    )
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.FAIL,
        is_complete=True,
        summary_code="FAIL",
        summary_text="Worst-case span exceeds limit.",
        governing_reason_codes=governing,
        marginal_reason_codes=marginal,
        supporting_reason_codes=supporting,
        triggered_reasons=triggered,
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


def _report_with_evidence_refs() -> ToleranceDecisionReport:
    refs = (
        ReportEvidenceRef(
            evidence_id="ev-001",
            source="WORST_CASE_ANALYSIS",
            evidence_code="WC_REQUIREMENT_EXCEEDED",
            reason_code="wc_requirement_exceeded",
        ),
        ReportEvidenceRef(
            evidence_id="ev-002",
            source="STATISTICAL_ANALYSIS",
            evidence_code="STAT_RESULT",
            reason_code="stat_requirement_at_boundary",
        ),
    )
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.MARGINAL,
        is_complete=True,
        summary_code="MARGINAL",
        summary_text="At boundary.",
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
        evidence_refs=refs,
        equality_tolerance=1e-9,
        section_order=_SECTION_ORDER,
    )


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


def test_render_rejects_non_report() -> None:
    with pytest.raises(DecisionReportHtmlExportError):
        render_decision_report_html("not a report")  # type: ignore


def test_render_rejects_none() -> None:
    with pytest.raises(DecisionReportHtmlExportError):
        render_decision_report_html(None)  # type: ignore


def test_write_rejects_non_report(tmp_path: Path) -> None:
    with pytest.raises(DecisionReportHtmlExportError):
        write_decision_report_html(42, tmp_path / "out.html")  # type: ignore


# ---------------------------------------------------------------------------
# Basic output contract
# ---------------------------------------------------------------------------


def test_render_returns_str() -> None:
    result = render_decision_report_html(_minimal_report())
    assert isinstance(result, str)


def test_render_non_empty() -> None:
    result = render_decision_report_html(_minimal_report())
    assert len(result) > 0


def test_render_utf8_compatible() -> None:
    result = render_decision_report_html(_minimal_report())
    result.encode("utf-8")  # must not raise


def test_render_doctype() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<!DOCTYPE html>" in result


def test_render_html_tag() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<html" in result
    assert "</html>" in result


def test_render_head_tag() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<head>" in result
    assert "</head>" in result


def test_render_body_tag() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<body>" in result
    assert "</body>" in result


def test_render_charset_meta() -> None:
    result = render_decision_report_html(_minimal_report())
    assert 'charset="UTF-8"' in result


def test_render_title() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<title>" in result
    assert "Origlyph" in result


def test_render_inline_style() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<style>" in result
    assert "</style>" in result


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_deterministic_repeat() -> None:
    report = _minimal_report()
    html1 = render_decision_report_html(report)
    html2 = render_decision_report_html(report)
    assert html1 == html2


def test_render_byte_identical_repeat() -> None:
    report = _minimal_report()
    b1 = render_decision_report_html(report).encode("utf-8")
    b2 = render_decision_report_html(report).encode("utf-8")
    assert b1 == b2


def test_render_deterministic_with_contributors() -> None:
    report = _report_with_contributors()
    assert render_decision_report_html(report) == render_decision_report_html(report)


def test_render_deterministic_with_metrics() -> None:
    report = _report_with_metrics()
    assert render_decision_report_html(report) == render_decision_report_html(report)


def test_render_deterministic_with_reasons() -> None:
    report = _report_with_reasons()
    assert render_decision_report_html(report) == render_decision_report_html(report)


# ---------------------------------------------------------------------------
# No non-deterministic content
# ---------------------------------------------------------------------------


def test_render_no_timestamp() -> None:
    result = render_decision_report_html(_minimal_report())
    # No ISO-8601 timestamp pattern
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", result)


def test_render_no_uuid_pattern() -> None:
    result = render_decision_report_html(_minimal_report())
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        result,
        re.IGNORECASE,
    )


def test_render_no_generated_at_field() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "generated_at" not in result.lower()
    assert "generation_timestamp" not in result.lower()


# ---------------------------------------------------------------------------
# No external resources
# ---------------------------------------------------------------------------


def test_render_no_external_css() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<link" not in result


def test_render_no_cdn_reference() -> None:
    result = render_decision_report_html(_minimal_report())
    result_lower = result.lower()
    assert "cdn." not in result_lower
    assert "cdnjs" not in result_lower
    assert "jsdelivr" not in result_lower
    assert "unpkg" not in result_lower


def test_render_no_script_tag() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "<script" not in result.lower()


def test_render_no_http_reference() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "http://" not in result
    assert "https://" not in result


def test_render_no_absolute_local_path() -> None:
    result = render_decision_report_html(_minimal_report())
    # No Windows-style or Unix absolute path
    assert not re.search(r"[A-Za-z]:\\", result)
    assert not re.search(r"href=\"/", result)


# ---------------------------------------------------------------------------
# Decision status rendering
# ---------------------------------------------------------------------------


def test_render_pass_status() -> None:
    report = _minimal_report(ToleranceDecisionStatus.PASS)
    result = render_decision_report_html(report)
    assert "PASS" in result


def test_render_fail_status() -> None:
    report = _minimal_report(ToleranceDecisionStatus.FAIL)
    result = render_decision_report_html(report)
    assert "FAIL" in result


def test_render_marginal_status() -> None:
    report = _minimal_report(ToleranceDecisionStatus.MARGINAL)
    result = render_decision_report_html(report)
    assert "MARGINAL" in result


def test_render_incomplete_status() -> None:
    report = _minimal_report(ToleranceDecisionStatus.INCOMPLETE)
    result = render_decision_report_html(report)
    assert "INCOMPLETE" in result


def test_render_summary_text() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "All criteria met." in result


def test_render_schema_version() -> None:
    result = render_decision_report_html(_minimal_report())
    assert REPORT_SCHEMA_VERSION in result


# ---------------------------------------------------------------------------
# Contributor rendering
# ---------------------------------------------------------------------------


def test_render_contributor_names() -> None:
    result = render_decision_report_html(_report_with_contributors())
    assert "Part A" in result
    assert "Part B" in result


def test_render_contributor_type() -> None:
    result = render_decision_report_html(_report_with_contributors())
    assert "worst_case" in result
    assert "statistical" in result


def test_render_contributor_value() -> None:
    result = render_decision_report_html(_report_with_contributors())
    assert "0.3" in result


def test_render_no_contributor_section_when_empty() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Contributors" not in result


# ---------------------------------------------------------------------------
# Metrics rendering
# ---------------------------------------------------------------------------


def test_render_worst_case_metrics_section() -> None:
    result = render_decision_report_html(_report_with_metrics())
    assert "Worst-Case Metrics" in result
    assert "worst_case.Part_A" in result


def test_render_statistical_metrics_section() -> None:
    result = render_decision_report_html(_report_with_metrics())
    assert "Statistical Metrics" in result
    assert "statistical.Part_A" in result


def test_render_metrics_with_bounds() -> None:
    result = render_decision_report_html(_report_with_metrics())
    assert "worst_case.Part_B" in result
    # Lower and upper bounds rendered
    assert "0" in result


def test_render_no_metrics_sections_when_empty() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Worst-Case Metrics" not in result
    assert "Statistical Metrics" not in result
    assert "Correlation Metrics" not in result


# ---------------------------------------------------------------------------
# Reason codes rendering
# ---------------------------------------------------------------------------


def test_render_governing_reason_code() -> None:
    result = render_decision_report_html(_report_with_reasons())
    assert "GOVERNING" in result
    assert "wc_requirement_exceeded" in result


def test_render_marginal_reason_code() -> None:
    result = render_decision_report_html(_report_with_reasons())
    assert "MARGINAL" in result
    assert "wc_requirement_at_boundary" in result


def test_render_supporting_reason_code() -> None:
    result = render_decision_report_html(_report_with_reasons())
    assert "SUPPORTING" in result
    assert "no_requirement_provided" in result


def test_render_triggered_reasons_section() -> None:
    result = render_decision_report_html(_report_with_reasons())
    assert "Triggered Reasons" in result
    assert "Actual span 1.5 exceeds limit 1.0" in result


def test_render_no_reason_section_when_empty() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Reason Codes" not in result
    assert "Triggered Reasons" not in result


# ---------------------------------------------------------------------------
# Evidence references rendering
# ---------------------------------------------------------------------------


def test_render_evidence_refs_section() -> None:
    result = render_decision_report_html(_report_with_evidence_refs())
    assert "Evidence References" in result
    assert "ev-001" in result
    assert "ev-002" in result


def test_render_evidence_source() -> None:
    result = render_decision_report_html(_report_with_evidence_refs())
    assert "WORST_CASE_ANALYSIS" in result


def test_render_no_evidence_section_when_empty() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Evidence References" not in result


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def test_render_escapes_lt_gt_in_contributor_name() -> None:
    contributors = (
        ReportContributor(
            name="Part <A>",
            contribution_type="worst_case",
            contribution_value=0.1,
            is_worst_case=True,
        ),
    )
    report = ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="pass",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=contributors,
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
    result = render_decision_report_html(report)
    assert "Part <A>" not in result
    assert "&lt;A&gt;" in result


def test_render_escapes_ampersand_in_summary_text() -> None:
    report = ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="A & B pass",
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
    result = render_decision_report_html(report)
    assert "A & B pass" not in result
    assert "A &amp; B pass" in result


def test_render_escapes_quotes_in_evidence_id() -> None:
    refs = (
        ReportEvidenceRef(
            evidence_id='ev"001',
            source="SOURCE",
            evidence_code="CODE",
            reason_code="reason",
        ),
    )
    report = ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="pass",
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
        evidence_refs=refs,
        equality_tolerance=1e-9,
        section_order=_SECTION_ORDER,
    )
    result = render_decision_report_html(report)
    assert 'ev"001' not in result
    assert "ev&quot;001" in result


def test_render_escapes_reason_detail() -> None:
    triggered = (
        ReportReasonRef(
            reason_code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
            severity=ToleranceDecisionSeverity.FAILURE,
            scope=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
            detail="span > limit",
            evidence_ids=(),
        ),
    )
    report = ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.FAIL,
        is_complete=True,
        summary_code="FAIL",
        summary_text="fail",
        governing_reason_codes=(ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=triggered,
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
    result = render_decision_report_html(report)
    assert "span > limit" not in result
    assert "span &gt; limit" in result


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def test_write_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = write_decision_report_html(_minimal_report(), out)
    assert result == out
    assert out.exists()


def test_write_returns_path(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    returned = write_decision_report_html(_minimal_report(), out)
    assert isinstance(returned, Path)


def test_write_content_matches_render(tmp_path: Path) -> None:
    report = _minimal_report()
    out = tmp_path / "report.html"
    write_decision_report_html(report, out)
    on_disk = out.read_text(encoding="utf-8")
    expected = render_decision_report_html(report)
    assert on_disk == expected


def test_write_utf8_encoding(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    write_decision_report_html(_minimal_report(), out)
    raw = out.read_bytes()
    raw.decode("utf-8")  # must not raise


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "deep" / "report.html"
    write_decision_report_html(_minimal_report(), out)
    assert out.exists()


def test_write_accepts_str_path(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    write_decision_report_html(_minimal_report(), str(out))
    assert out.exists()


def test_write_byte_identical_repeat(tmp_path: Path) -> None:
    report = _minimal_report()
    out1 = tmp_path / "r1.html"
    out2 = tmp_path / "r2.html"
    write_decision_report_html(report, out1)
    write_decision_report_html(report, out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_write_invalid_path_raises() -> None:
    with pytest.raises(DecisionReportHtmlExportError):
        # Use a path that cannot be created (empty string → invalid)
        write_decision_report_html(_minimal_report(), "")


# ---------------------------------------------------------------------------
# Sigma multiplier rendering
# ---------------------------------------------------------------------------


def test_render_sigma_multiplier_shown_when_set() -> None:
    report = ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=ToleranceDecisionStatus.PASS,
        is_complete=True,
        summary_code="PASS",
        summary_text="pass",
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
        sigma_multiplier=3.0,
        section_order=_SECTION_ORDER,
    )
    result = render_decision_report_html(report)
    assert "Sigma multiplier" in result
    assert "3.0" in result


def test_render_sigma_multiplier_absent_when_none() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Sigma multiplier" not in result


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def test_render_contains_footer() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "Origlyph AI" in result


def test_render_footer_disclaimer() -> None:
    result = render_decision_report_html(_minimal_report())
    assert "not a new engineering calculation" in result
