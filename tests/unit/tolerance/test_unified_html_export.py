"""Unit tests for deterministic unified engineering report HTML export (Stage 21E)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.unified_html_export import (
    UnifiedEngineeringHtmlExportError,
    render_unified_engineering_report_html,
    write_unified_engineering_report_html,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceSpecification,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_complete_chain() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.5,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    ctrl.run_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            fp=f,
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-REF-001",
            decision_reference="DEC-REF-001",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


def _kwargs(ctrl: ToleranceWorkspaceController) -> dict:
    return {
        "decision_report": ctrl.last_decision_report,
        "audit_package": ctrl.last_audit_package,
        "comparison": ctrl.last_audit_comparison,
        "change_impact": ctrl.last_change_impact,
        "disposition": ctrl.last_change_disposition,
        "approval_readiness": ctrl.last_approval_readiness,
        "acceptance_handoff": ctrl.last_acceptance_handoff,
        "acceptance_record": ctrl.last_acceptance_record,
        "acceptance_verification": ctrl.last_acceptance_verification,
        "acceptance_closure": ctrl.last_acceptance_closure,
    }


# ---------------------------------------------------------------------------
# Type validation — renderer rejects invalid types
# ---------------------------------------------------------------------------


def test_reject_none_decision_report() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["decision_report"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_audit_package() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["audit_package"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_comparison() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["comparison"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_change_impact() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["change_impact"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_disposition() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["disposition"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_approval_readiness() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["approval_readiness"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_acceptance_handoff() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["acceptance_handoff"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_acceptance_record() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["acceptance_record"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_acceptance_verification() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["acceptance_verification"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_none_acceptance_closure() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["acceptance_closure"] = None
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_wrong_type_decision_report() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["decision_report"] = "not-a-report"
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_wrong_type_audit_package() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["audit_package"] = object()
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


def test_reject_wrong_type_comparison() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    kw["comparison"] = object()
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        render_unified_engineering_report_html(**kw)


# ---------------------------------------------------------------------------
# Basic rendering — completeness and HTML structure
# ---------------------------------------------------------------------------


def test_render_returns_string() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert isinstance(result, str)


def test_render_non_empty() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert len(result) > 100


def test_render_contains_doctype() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<!DOCTYPE html>" in result


def test_render_contains_html_tag() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<html" in result
    assert "</html>" in result


def test_render_contains_head_and_body() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<head>" in result
    assert "<body>" in result


def test_render_contains_title() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<title>" in result
    assert "Origlyph" in result


def test_render_contains_charset_meta() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "charset" in result.lower()
    assert "utf-8" in result.lower()


def test_render_contains_inline_style() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<style>" in result


def test_render_valid_utf8() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    result.encode("utf-8")  # must not raise


# ---------------------------------------------------------------------------
# Section presence
# ---------------------------------------------------------------------------


def test_contains_executive_summary_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Executive Engineering Summary" in result


def test_contains_decision_report_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Decision Report" in result


def test_contains_audit_package_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Audit Package" in result


def test_contains_audit_comparison_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Audit Comparison" in result


def test_contains_change_impact_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Change Impact" in result


def test_contains_change_disposition_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Change Disposition" in result


def test_contains_approval_readiness_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Approval Readiness" in result


def test_contains_acceptance_handoff_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Acceptance Handoff" in result


def test_contains_acceptance_record_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Acceptance Record" in result


def test_contains_acceptance_verification_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Acceptance Verification" in result


def test_contains_acceptance_closure_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Acceptance Closure" in result


def test_contains_traceability_heading() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Traceability" in result


def test_contains_engineering_report_notice() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "Engineering Report Notice" in result or "does not independently" in result


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_deterministic_same_call() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    r1 = render_unified_engineering_report_html(**kw)
    r2 = render_unified_engineering_report_html(**kw)
    assert r1 == r2


def test_render_byte_identical_repeat() -> None:
    ctrl = _make_complete_chain()
    kw = _kwargs(ctrl)
    b1 = render_unified_engineering_report_html(**kw).encode("utf-8")
    b2 = render_unified_engineering_report_html(**kw).encode("utf-8")
    assert b1 == b2


def test_render_no_timestamp_in_output() -> None:
    import re
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    # No date strings like 2025-01-01 or 2026-11-10
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", result)


def test_render_no_uuid_in_output() -> None:
    import re
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    # No random UUID4 patterns (8-4-4-4-12 hex format in a generated position)
    # Note: SHA-256 fingerprints are legitimate and may appear
    # UUIDs have the format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    uuid_re = re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    )
    assert not uuid_re.search(result)


# ---------------------------------------------------------------------------
# Identifier fidelity
# ---------------------------------------------------------------------------


def test_package_id_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    pkg = ctrl.last_audit_package
    assert pkg is not None
    assert pkg.package_id in result


def test_handoff_id_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    handoff = ctrl.last_acceptance_handoff
    assert handoff is not None
    assert handoff.handoff_id in result


def test_acceptance_record_id_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    record = ctrl.last_acceptance_record
    assert record is not None
    assert record.acceptance_record_id in result


def test_authority_reference_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "AUTH-REF-001" in result


def test_decision_reference_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "DEC-REF-001" in result


def test_closure_id_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    closure = ctrl.last_acceptance_closure
    assert closure is not None
    assert closure.closure_id in result


def test_decision_status_present_in_output() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    report = ctrl.last_decision_report
    assert report is not None
    assert report.final_status.value.upper() in result.upper()


# ---------------------------------------------------------------------------
# HTML escaping / injection protection
# ---------------------------------------------------------------------------


def _make_injection_chain() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.5,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    ctrl.run_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            fp=f,
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference='<script>alert(1)</script>',
            decision_reference='</table><img src=x onerror=alert(1)>',
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


def test_html_escaping_lt_gt_amp() -> None:
    ctrl = _make_injection_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    # Active markup must not appear; escaped text is acceptable
    assert "<script>" not in result
    # <img and <table from injection must be escaped, not active tags
    assert "<img " not in result


def test_html_escaping_authority_reference() -> None:
    ctrl = _make_injection_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;" in result


def test_html_escaping_decision_reference() -> None:
    ctrl = _make_injection_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "</table><img" not in result


def test_no_active_script_tags() -> None:
    ctrl = _make_injection_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    # <script> from inline CSS is not expected; no <script src=...> either
    import re
    assert not re.search(r"<script\b", result, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Self-contained / no external resources
# ---------------------------------------------------------------------------


def test_no_external_stylesheet() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<link" not in result.lower()


def test_no_cdn_reference() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    cdns = ("cdnjs.cloudflare.com", "unpkg.com", "jsdelivr.net", "fonts.googleapis")
    for cdn in cdns:
        assert cdn not in result


def test_no_http_in_src_or_href() -> None:
    import re
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert not re.search(r'(src|href)=["\']https?://', result)


def test_no_file_protocol_reference() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "file://" not in result


def test_no_js_import_statement() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "<script" not in result.lower()


# ---------------------------------------------------------------------------
# Semantic safety
# ---------------------------------------------------------------------------


def test_no_certified_label() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    lower = result.lower()
    if "certified" in lower:
        # Only acceptable in a limitation/negative context
        idx = lower.index("certified")
        ctx = lower[max(0, idx - 50): idx + 50]
        assert "not" in ctx


def test_no_digitally_signed_label() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    lower = result.lower()
    assert "digitally signed" not in lower


def test_no_authenticated_approver_label() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    lower = result.lower()
    assert "authenticated approver" not in lower


def test_no_regulatory_approved_label() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    lower = result.lower()
    assert "regulatory approved" not in lower


def test_unified_notice_present() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert "does not independently" in result or "already generated" in result


def test_unified_notice_no_grant_approval() -> None:
    ctrl = _make_complete_chain()
    result = render_unified_engineering_report_html(**_kwargs(ctrl))
    lower = result.lower()
    assert "grant approval" in lower or "authorize product release" in lower


# ---------------------------------------------------------------------------
# Source artifact state unchanged after render
# ---------------------------------------------------------------------------


def test_decision_report_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    report_before = ctrl.last_decision_report
    render_unified_engineering_report_html(**_kwargs(ctrl))
    assert ctrl.last_decision_report is report_before


def test_audit_package_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    pkg_before = ctrl.last_audit_package
    render_unified_engineering_report_html(**_kwargs(ctrl))
    assert ctrl.last_audit_package is pkg_before


def test_acceptance_closure_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    closure_before = ctrl.last_acceptance_closure
    render_unified_engineering_report_html(**_kwargs(ctrl))
    assert ctrl.last_acceptance_closure is closure_before


# ---------------------------------------------------------------------------
# Writer API
# ---------------------------------------------------------------------------


def test_write_creates_file(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out)
    assert out.exists()


def test_write_returns_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    result = write_unified_engineering_report_html(**_kwargs(ctrl), path=out)
    assert isinstance(result, Path)
    assert result == out


def test_write_non_empty(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out)
    assert len(out.read_text(encoding="utf-8")) > 0


def test_write_matches_render(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out)
    written = out.read_text(encoding="utf-8")
    rendered = render_unified_engineering_report_html(**_kwargs(ctrl))
    assert written.replace("\r\n", "\n") == rendered.replace("\r\n", "\n")


def test_write_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=str(out))
    assert out.exists()


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "nested" / "deep" / "report.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out)
    assert out.exists()


def test_repeated_write_byte_identical(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out1 = tmp_path / "a.html"
    out2 = tmp_path / "b.html"
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out1)
    write_unified_engineering_report_html(**_kwargs(ctrl), path=out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_write_invalid_path_raises(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        write_unified_engineering_report_html(
            **_kwargs(ctrl),
            path=blocker / "nested" / "report.html",
        )


def test_write_raises_on_none_path() -> None:
    ctrl = _make_complete_chain()
    with pytest.raises((UnifiedEngineeringHtmlExportError, TypeError, AttributeError)):
        write_unified_engineering_report_html(**_kwargs(ctrl), path=None)  # type: ignore[arg-type]
