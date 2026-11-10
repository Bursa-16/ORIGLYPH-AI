"""Workspace integration tests for audit HTML export (Stage 21C)."""

from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.tolerance.audit_html_export import render_audit_package_html
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ctrl_with_package() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain", analysis_mode=AnalysisMode.WORST_CASE
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
    return ctrl


def _make_ctrl_without_package() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain", analysis_mode=AnalysisMode.WORST_CASE
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
    # run_audit_package() NOT called
    return ctrl


# ---------------------------------------------------------------------------
# Controller — missing audit package fails closed
# ---------------------------------------------------------------------------


def test_ctrl_missing_package_raises() -> None:
    ctrl = _make_ctrl_without_package()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_audit_html("audit.html")


def test_ctrl_missing_package_error_message() -> None:
    ctrl = _make_ctrl_without_package()
    with pytest.raises(InvalidToleranceWorkspaceError, match="run_audit_package"):
        ctrl.export_audit_html("audit.html")


# ---------------------------------------------------------------------------
# No hidden audit package generation
# ---------------------------------------------------------------------------


def test_no_hidden_run_audit_package(tmp_path: Path) -> None:
    ctrl = _make_ctrl_without_package()
    assert ctrl.last_audit_package is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_audit_package is None


def test_no_hidden_run_audit_integrity(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    integrity_before = ctrl.last_audit_integrity
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_audit_integrity is integrity_before


def test_no_hidden_run_decision_report(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    report_before = ctrl.last_decision_report
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_decision_report is report_before


# ---------------------------------------------------------------------------
# Controller — successful export
# ---------------------------------------------------------------------------


def test_ctrl_export_creates_file(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "audit.html"
    result = ctrl.export_audit_html(out)
    assert result == out
    assert out.exists()


def test_ctrl_export_returns_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "audit.html"
    result = ctrl.export_audit_html(out)
    assert isinstance(result, Path)


def test_ctrl_export_content_non_empty(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "audit.html"
    ctrl.export_audit_html(out)
    assert len(out.read_text(encoding="utf-8")) > 0


def test_ctrl_export_contains_doctype(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "audit.html"
    ctrl.export_audit_html(out)
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_ctrl_export_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "audit.html"
    ctrl.export_audit_html(str(out))
    assert out.exists()


def test_ctrl_export_creates_parent_dirs(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out = tmp_path / "nested" / "deep" / "audit.html"
    ctrl.export_audit_html(out)
    assert out.exists()


# ---------------------------------------------------------------------------
# Output matches direct renderer
# ---------------------------------------------------------------------------


def test_ctrl_output_matches_direct_render(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    out = tmp_path / "audit.html"
    ctrl.export_audit_html(out)
    written = out.read_text(encoding="utf-8")
    rendered = render_audit_package_html(pkg)
    assert written.replace("\r\n", "\n") == rendered.replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_ctrl_repeated_export_identical(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    out1 = tmp_path / "a.html"
    out2 = tmp_path / "b.html"
    ctrl.export_audit_html(out1)
    ctrl.export_audit_html(out2)
    assert out1.read_bytes() == out2.read_bytes()


# ---------------------------------------------------------------------------
# Workspace state unchanged after export
# ---------------------------------------------------------------------------


def test_ctrl_package_unchanged_after_export(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    pkg_before = ctrl.last_audit_package
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_audit_package is pkg_before


def test_ctrl_comparison_package_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    comp_before = ctrl._comparison_audit_package
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._comparison_audit_package is comp_before


def test_acceptance_state_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    acc_before = ctrl._last_acceptance_handoff
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_acceptance_handoff is acc_before


# ---------------------------------------------------------------------------
# After state mutation — package invalidated
# ---------------------------------------------------------------------------


def test_ctrl_export_after_state_reset_raises() -> None:
    ctrl = _make_ctrl_with_package()
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_audit_html("audit.html")


# ---------------------------------------------------------------------------
# Project identity unchanged
# ---------------------------------------------------------------------------


def test_project_id_unchanged(tmp_path: Path) -> None:
    from origlyph.tolerance.workspace_controller import (
        workspace_configuration_fingerprint,
    )
    ctrl = _make_ctrl_with_package()
    fp_before = workspace_configuration_fingerprint(ctrl._state)
    ctrl.export_audit_html(tmp_path / "audit.html")
    fp_after = workspace_configuration_fingerprint(ctrl._state)
    assert fp_before == fp_after


# ---------------------------------------------------------------------------
# Engineering state unchanged
# ---------------------------------------------------------------------------


def test_analysis_result_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    result_before = ctrl.last_result
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_result is result_before


def test_decision_result_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    decision_before = ctrl.last_decision
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_decision is decision_before


# ---------------------------------------------------------------------------
# Governance state unchanged
# ---------------------------------------------------------------------------


def test_last_decision_report_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    report_before = ctrl.last_decision_report
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl.last_decision_report is report_before


def test_acceptance_record_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    rec_before = ctrl._last_acceptance_record
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_acceptance_record is rec_before


def test_acceptance_verification_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    ver_before = ctrl._last_acceptance_verification
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_acceptance_verification is ver_before


def test_acceptance_closure_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    clo_before = ctrl._last_acceptance_closure
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_acceptance_closure is clo_before


# ---------------------------------------------------------------------------
# WorkspaceSession integration
# ---------------------------------------------------------------------------


def test_session_audit_html_available_false_without_package() -> None:
    ctrl = _make_ctrl_without_package()
    session = WorkspaceSession(ctrl)
    assert session.audit_html_available is False


def test_session_audit_html_available_true_with_package() -> None:
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    assert session.audit_html_available is True


def test_session_export_audit_html_creates_file(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "audit.html"
    session.export_audit_html(out)
    assert out.exists()


def test_session_export_audit_html_returns_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "audit.html"
    result = session.export_audit_html(out)
    assert isinstance(result, Path)


def test_session_missing_package_raises() -> None:
    ctrl = _make_ctrl_without_package()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.export_audit_html("audit.html")


def test_session_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    session.export_audit_html(str(tmp_path / "audit.html"))
    assert (tmp_path / "audit.html").exists()


def test_session_audit_html_available_reflects_state_change() -> None:
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    assert session.audit_html_available is True
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert session.audit_html_available is False


# ---------------------------------------------------------------------------
# Writer failure propagation
# ---------------------------------------------------------------------------


def test_ctrl_writer_failure_propagates(tmp_path: Path) -> None:
    from origlyph.tolerance.audit_html_export import AuditPackageHtmlExportError
    ctrl = _make_ctrl_with_package()
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(AuditPackageHtmlExportError):
        ctrl.export_audit_html(blocker / "nested" / "audit.html")


def test_session_writer_failure_propagates(tmp_path: Path) -> None:
    from origlyph.tolerance.audit_html_export import AuditPackageHtmlExportError
    ctrl = _make_ctrl_with_package()
    session = WorkspaceSession(ctrl)
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(AuditPackageHtmlExportError):
        session.export_audit_html(blocker / "nested" / "audit.html")


# ---------------------------------------------------------------------------
# Downstream governance caches unchanged after export
# ---------------------------------------------------------------------------


def test_last_audit_comparison_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    comp_before = ctrl._last_audit_comparison
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_audit_comparison is comp_before


def test_last_change_impact_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    impact_before = ctrl._last_change_impact
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_change_impact is impact_before


def test_last_change_disposition_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    disp_before = ctrl._last_change_disposition
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_change_disposition is disp_before


def test_approval_readiness_unchanged(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_package()
    apr_before = ctrl._last_approval_readiness
    ctrl.export_audit_html(tmp_path / "audit.html")
    assert ctrl._last_approval_readiness is apr_before
