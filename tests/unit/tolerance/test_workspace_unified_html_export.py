"""Workspace integration tests for unified engineering report HTML export (Stage 21E).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.unified_html_export import (
    UnifiedEngineeringHtmlExportError,
    render_unified_engineering_report_html,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceSpecification,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
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
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


def _make_partial_chain(stop_before: str) -> ToleranceWorkspaceController:  # noqa: C901
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
    if stop_before == "report":
        return ctrl
    ctrl.run_decision_report()
    if stop_before == "audit_package":
        return ctrl
    ctrl.run_audit_package()
    if stop_before == "comparison":
        return ctrl
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
    if stop_before == "change_impact":
        return ctrl
    ctrl.run_change_impact()
    if stop_before == "disposition":
        return ctrl
    ctrl.run_change_disposition()
    if stop_before == "approval_readiness":
        return ctrl
    ctrl.run_approval_readiness()
    if stop_before == "handoff":
        return ctrl
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=handoff.handoff_id,
        )
    )
    if stop_before == "record":
        return ctrl
    ctrl.run_acceptance_record()
    if stop_before == "verification":
        return ctrl
    ctrl.run_acceptance_verification()
    if stop_before == "closure":
        return ctrl
    ctrl.run_acceptance_closure()
    return ctrl


# ---------------------------------------------------------------------------
# Controller — missing artifacts fail closed for ALL ten
# ---------------------------------------------------------------------------


def test_missing_decision_report_raises() -> None:
    ctrl = _make_partial_chain("report")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_audit_package_raises() -> None:
    ctrl = _make_partial_chain("audit_package")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_comparison_raises() -> None:
    ctrl = _make_partial_chain("comparison")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_change_impact_raises() -> None:
    ctrl = _make_partial_chain("change_impact")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_disposition_raises() -> None:
    ctrl = _make_partial_chain("disposition")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_approval_readiness_raises() -> None:
    ctrl = _make_partial_chain("approval_readiness")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_handoff_raises() -> None:
    ctrl = _make_partial_chain("handoff")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_record_raises() -> None:
    ctrl = _make_partial_chain("record")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_verification_raises() -> None:
    ctrl = _make_partial_chain("verification")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_missing_closure_raises() -> None:
    ctrl = _make_partial_chain("closure")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report("report.html")


def test_error_message_mentions_missing_report() -> None:
    ctrl = _make_partial_chain("report")
    with pytest.raises(InvalidToleranceWorkspaceError, match="last_decision_report"):
        ctrl.export_unified_html_report("report.html")


def test_error_message_mentions_missing_audit_package() -> None:
    ctrl = _make_partial_chain("audit_package")
    with pytest.raises(InvalidToleranceWorkspaceError, match="last_audit_package"):
        ctrl.export_unified_html_report("report.html")


def test_error_message_mentions_missing_comparison() -> None:
    ctrl = _make_partial_chain("comparison")
    with pytest.raises(InvalidToleranceWorkspaceError, match="last_audit_comparison"):
        ctrl.export_unified_html_report("report.html")


# ---------------------------------------------------------------------------
# No hidden generation
# ---------------------------------------------------------------------------


def test_no_hidden_report_generation(tmp_path: Path) -> None:
    ctrl = _make_partial_chain("report")
    assert ctrl.last_decision_report is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_decision_report is None


def test_no_hidden_audit_package_generation(tmp_path: Path) -> None:
    ctrl = _make_partial_chain("audit_package")
    assert ctrl.last_audit_package is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_audit_package is None


def test_no_hidden_comparison_generation(tmp_path: Path) -> None:
    ctrl = _make_partial_chain("comparison")
    assert ctrl.last_audit_comparison is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_audit_comparison is None


def test_no_hidden_acceptance_generation(tmp_path: Path) -> None:
    ctrl = _make_partial_chain("record")
    assert ctrl.last_acceptance_record is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_record is None


def test_no_hidden_closure_generation(tmp_path: Path) -> None:
    ctrl = _make_partial_chain("closure")
    assert ctrl.last_acceptance_closure is None
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_closure is None


# ---------------------------------------------------------------------------
# Successful export
# ---------------------------------------------------------------------------


def test_export_creates_file(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    ctrl.export_unified_html_report(out)
    assert out.exists()


def test_export_returns_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    result = ctrl.export_unified_html_report(out)
    assert isinstance(result, Path)
    assert result == out


def test_export_non_empty(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    ctrl.export_unified_html_report(out)
    assert len(out.read_text(encoding="utf-8")) > 0


def test_export_contains_doctype(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    ctrl.export_unified_html_report(out)
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_export_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    ctrl.export_unified_html_report(str(out))
    assert out.exists()


def test_export_creates_parent_dirs(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "nested" / "deep" / "report.html"
    ctrl.export_unified_html_report(out)
    assert out.exists()


# ---------------------------------------------------------------------------
# Output matches direct renderer
# ---------------------------------------------------------------------------


def test_output_matches_direct_render(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "report.html"
    ctrl.export_unified_html_report(out)
    written = out.read_text(encoding="utf-8")
    rendered = render_unified_engineering_report_html(
        decision_report=ctrl.last_decision_report,  # type: ignore[arg-type]
        audit_package=ctrl.last_audit_package,  # type: ignore[arg-type]
        comparison=ctrl.last_audit_comparison,  # type: ignore[arg-type]
        change_impact=ctrl.last_change_impact,  # type: ignore[arg-type]
        disposition=ctrl.last_change_disposition,  # type: ignore[arg-type]
        approval_readiness=ctrl.last_approval_readiness,  # type: ignore[arg-type]
        acceptance_handoff=ctrl.last_acceptance_handoff,  # type: ignore[arg-type]
        acceptance_record=ctrl.last_acceptance_record,  # type: ignore[arg-type]
        acceptance_verification=ctrl.last_acceptance_verification,  # type: ignore[arg-type]
        acceptance_closure=ctrl.last_acceptance_closure,  # type: ignore[arg-type]
    )
    assert written.replace("\r\n", "\n") == rendered.replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_export_identical(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out1 = tmp_path / "a.html"
    out2 = tmp_path / "b.html"
    ctrl.export_unified_html_report(out1)
    ctrl.export_unified_html_report(out2)
    assert out1.read_bytes() == out2.read_bytes()


# ---------------------------------------------------------------------------
# Project identity unchanged
# ---------------------------------------------------------------------------


def test_project_id_unchanged(tmp_path: Path) -> None:
    from origlyph.tolerance.workspace_controller import (
        workspace_configuration_fingerprint,
    )
    ctrl = _make_complete_chain()
    fp_before = workspace_configuration_fingerprint(ctrl._state)
    ctrl.export_unified_html_report(tmp_path / "report.html")
    fp_after = workspace_configuration_fingerprint(ctrl._state)
    assert fp_before == fp_after


# ---------------------------------------------------------------------------
# Authoritative acceptance state unchanged
# ---------------------------------------------------------------------------


def test_acceptance_state_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    state_before = ctrl.acceptance_state
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.acceptance_state is state_before


# ---------------------------------------------------------------------------
# Engineering state unchanged
# ---------------------------------------------------------------------------


def test_analysis_result_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    result_before = ctrl.last_result
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_result is result_before


def test_decision_report_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    report_before = ctrl.last_decision_report
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_decision_report is report_before


def test_audit_package_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    pkg_before = ctrl.last_audit_package
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_audit_package is pkg_before


def test_decision_result_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    decision_before = ctrl.last_decision
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_decision is decision_before


# ---------------------------------------------------------------------------
# Governance state unchanged
# ---------------------------------------------------------------------------


def test_comparison_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_audit_comparison
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_audit_comparison is before


def test_change_impact_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_change_impact
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_change_impact is before


def test_disposition_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_change_disposition
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_change_disposition is before


def test_approval_readiness_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_approval_readiness
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_approval_readiness is before


def test_acceptance_handoff_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_acceptance_handoff
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_handoff is before


def test_acceptance_record_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_acceptance_record
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_record is before


def test_acceptance_verification_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_acceptance_verification
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_verification is before


def test_acceptance_closure_unchanged(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_acceptance_closure
    ctrl.export_unified_html_report(tmp_path / "report.html")
    assert ctrl.last_acceptance_closure is before


# ---------------------------------------------------------------------------
# WorkspaceSession integration
# ---------------------------------------------------------------------------


def test_session_unified_html_available_false_without_chain() -> None:
    ctrl = _make_partial_chain("comparison")
    session = WorkspaceSession(ctrl)
    assert session.unified_html_available is False


def test_session_unified_html_available_false_without_report() -> None:
    ctrl = _make_partial_chain("report")
    session = WorkspaceSession(ctrl)
    assert session.unified_html_available is False


def test_session_unified_html_available_true_with_all_artifacts() -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    assert session.unified_html_available is True


def test_session_export_creates_file(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "report.html"
    session.export_unified_html_report(out)
    assert out.exists()


def test_session_export_returns_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "report.html"
    result = session.export_unified_html_report(out)
    assert isinstance(result, Path)


def test_session_missing_chain_raises() -> None:
    ctrl = _make_partial_chain("comparison")
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.export_unified_html_report("report.html")


def test_session_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    session.export_unified_html_report(str(tmp_path / "report.html"))
    assert (tmp_path / "report.html").exists()


def test_session_available_reflects_state_change() -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    assert session.unified_html_available is True
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert session.unified_html_available is False


# ---------------------------------------------------------------------------
# Writer failure propagation
# ---------------------------------------------------------------------------


def test_ctrl_writer_failure_propagates(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        ctrl.export_unified_html_report(blocker / "nested" / "report.html")


def test_session_writer_failure_propagates(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    session = WorkspaceSession(ctrl)
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(UnifiedEngineeringHtmlExportError):
        session.export_unified_html_report(blocker / "nested" / "report.html")
