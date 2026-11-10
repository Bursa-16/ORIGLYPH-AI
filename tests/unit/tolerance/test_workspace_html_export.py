"""Workspace integration tests for HTML export (Stage 21B)."""

from __future__ import annotations

from pathlib import Path

import pytest  # noqa: F401

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


def _make_ctrl_with_report() -> ToleranceWorkspaceController:
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
    return ctrl


def _make_ctrl_without_report() -> ToleranceWorkspaceController:
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
    # run_decision_report() NOT called
    return ctrl


# ---------------------------------------------------------------------------
# Controller — export_html_report
# ---------------------------------------------------------------------------


def test_ctrl_export_html_creates_file(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "report.html"
    result = ctrl.export_html_report(out)
    assert result == out
    assert out.exists()


def test_ctrl_export_html_returns_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "report.html"
    returned = ctrl.export_html_report(out)
    assert isinstance(returned, Path)


def test_ctrl_export_html_content_non_empty(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "report.html"
    ctrl.export_html_report(out)
    content = out.read_text(encoding="utf-8")
    assert len(content) > 0


def test_ctrl_export_html_contains_doctype(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "report.html"
    ctrl.export_html_report(out)
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_ctrl_export_html_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "report.html"
    ctrl.export_html_report(str(out))
    assert out.exists()


def test_ctrl_export_html_missing_report_raises() -> None:
    ctrl = _make_ctrl_without_report()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_html_report("report.html")


def test_ctrl_export_html_no_report_error_message() -> None:
    ctrl = _make_ctrl_without_report()
    with pytest.raises(InvalidToleranceWorkspaceError, match="run_decision_report"):
        ctrl.export_html_report("report.html")


def test_ctrl_export_html_does_not_mutate_report(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    report_before = ctrl.last_decision_report
    ctrl.export_html_report(tmp_path / "r.html")
    assert ctrl.last_decision_report is report_before


def test_ctrl_export_html_deterministic(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out1 = tmp_path / "r1.html"
    out2 = tmp_path / "r2.html"
    ctrl.export_html_report(out1)
    ctrl.export_html_report(out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_ctrl_export_html_creates_parent_dirs(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    out = tmp_path / "nested" / "deep" / "report.html"
    ctrl.export_html_report(out)
    assert out.exists()


def test_ctrl_export_html_after_state_reset_raises() -> None:
    ctrl = _make_ctrl_with_report()
    # Add another contributor to reset downstream caches
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_html_report("report.html")


# ---------------------------------------------------------------------------
# WorkspaceSession — html_report_available + export_html_report
# ---------------------------------------------------------------------------


def test_session_html_report_available_false_without_report() -> None:
    ctrl = _make_ctrl_without_report()
    session = WorkspaceSession(ctrl)
    assert session.html_report_available is False


def test_session_html_report_available_true_with_report() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    assert session.html_report_available is True


def test_session_export_html_creates_file(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "report.html"
    session.export_html_report(out)
    assert out.exists()


def test_session_export_html_returns_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    out = tmp_path / "report.html"
    returned = session.export_html_report(out)
    assert isinstance(returned, Path)


def test_session_export_html_missing_report_raises() -> None:
    ctrl = _make_ctrl_without_report()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.export_html_report("report.html")


def test_session_export_html_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    session.export_html_report(str(tmp_path / "report.html"))
    assert (tmp_path / "report.html").exists()


def test_session_html_report_available_reflects_state_change() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    assert session.html_report_available is True
    # Mutation invalidates the report cache
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert session.html_report_available is False
