"""Unit tests for decision report workspace surface (Stage 20C)."""

from __future__ import annotations

import pytest

from origlyph.tolerance.report import (
    ToleranceDecisionReport,
    build_decision_report,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctrl_with_evidence() -> ToleranceWorkspaceController:
    """Return a controller with decision + evidence cached."""
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
    return ctrl


def _make_ctrl_with_decision() -> ToleranceWorkspaceController:
    """Return a controller with decision cached but no evidence."""
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
    return ctrl


def _make_ctrl_no_decision() -> ToleranceWorkspaceController:
    """Return a controller without a decision result."""
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
    return ctrl


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_report_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    assert ctrl.last_decision_report is None


def test_session_initial_report_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.last_decision_report is None


def test_session_report_status_text_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.report_status_text == "NOT GENERATED"


def test_session_report_summary_text_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.report_summary_text == ""


def test_session_report_contributors_rows_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.report_contributors_rows() == []


def test_session_report_evidence_refs_rows_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.report_evidence_refs_rows() == []


# ---------------------------------------------------------------------------
# Fail-closed: missing prerequisites
# ---------------------------------------------------------------------------


def test_run_decision_report_fails_without_decision() -> None:
    ctrl = _make_ctrl_no_decision()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Run Decision first"):
        ctrl.run_decision_report()


def test_run_decision_report_fails_without_evidence() -> None:
    ctrl = _make_ctrl_with_decision()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Generate Evidence first"):
        ctrl.run_decision_report()


def test_session_generate_report_fails_without_decision() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError, match="Run Decision first"):
        session.generate_decision_report()


def test_session_generate_report_fails_without_evidence() -> None:
    ctrl = _make_ctrl_with_decision()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError, match="Generate Evidence first"):
        session.generate_decision_report()


# ---------------------------------------------------------------------------
# Successful delegation to Stage 15M
# ---------------------------------------------------------------------------


def test_run_decision_report_returns_report() -> None:
    ctrl = _make_ctrl_with_evidence()
    report = ctrl.run_decision_report()
    assert isinstance(report, ToleranceDecisionReport)


def test_run_decision_report_delegates_to_stage15m() -> None:
    ctrl = _make_ctrl_with_evidence()
    decision = ctrl.last_decision
    evidence = ctrl.last_evidence
    explanation = ctrl.last_explanation
    assert decision is not None
    assert evidence is not None
    assert explanation is not None
    expected = build_decision_report(decision, evidence, explanation)
    report = ctrl.run_decision_report()
    assert report.schema_version == expected.schema_version
    assert report.final_status == expected.final_status
    assert report.is_complete == expected.is_complete
    assert report.summary_code == expected.summary_code
    assert report.summary_text == expected.summary_text


def test_report_cached_after_generation() -> None:
    ctrl = _make_ctrl_with_evidence()
    report = ctrl.run_decision_report()
    assert ctrl.last_decision_report is report


def test_session_generate_report_caches_result() -> None:
    ctrl = _make_ctrl_with_evidence()
    session = WorkspaceSession(ctrl)
    report = session.generate_decision_report()
    assert ctrl.last_decision_report is report


# ---------------------------------------------------------------------------
# Result mapping
# ---------------------------------------------------------------------------


def test_report_maps_final_status() -> None:
    ctrl = _make_ctrl_with_evidence()
    report = ctrl.run_decision_report()
    decision = ctrl.last_decision
    assert decision is not None
    assert report.final_status == decision.overall_status


def test_session_report_status_text_after_generation() -> None:
    ctrl = _make_ctrl_with_evidence()
    session = WorkspaceSession(ctrl)
    session.generate_decision_report()
    assert session.report_status_text != "NOT GENERATED"
    assert session.report_status_text != ""


def test_session_report_summary_text_after_generation() -> None:
    ctrl = _make_ctrl_with_evidence()
    session = WorkspaceSession(ctrl)
    session.generate_decision_report()
    assert session.report_summary_text != ""


def test_session_report_contributors_rows_after_generation() -> None:
    ctrl = _make_ctrl_with_evidence()
    session = WorkspaceSession(ctrl)
    session.generate_decision_report()
    rows = session.report_contributors_rows()
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert "name" in row
        assert "type" in row
        assert "value" in row
        assert "sigma" in row


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_report_generation_is_deterministic() -> None:
    ctrl = _make_ctrl_with_evidence()
    report1 = ctrl.run_decision_report()
    report2 = ctrl.run_decision_report()
    assert report1.final_status == report2.final_status
    assert report1.summary_code == report2.summary_code
    assert report1.summary_text == report2.summary_text
    assert report1.is_complete == report2.is_complete


# ---------------------------------------------------------------------------
# Feature isolation — report must NOT mutate other state
# ---------------------------------------------------------------------------


def test_report_does_not_change_decision() -> None:
    ctrl = _make_ctrl_with_evidence()
    original_decision = ctrl.last_decision
    ctrl.run_decision_report()
    assert ctrl.last_decision is original_decision


def test_report_does_not_change_evidence() -> None:
    ctrl = _make_ctrl_with_evidence()
    original_evidence = ctrl.last_evidence
    ctrl.run_decision_report()
    assert ctrl.last_evidence is original_evidence


def test_report_does_not_change_analysis_result() -> None:
    ctrl = _make_ctrl_with_evidence()
    original_result = ctrl.last_result
    ctrl.run_decision_report()
    assert ctrl.last_result is original_result


def test_report_does_not_clear_sensitivity() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    ctrl.run_decision_report()
    assert ctrl.last_sensitivity is sensitivity_before


def test_report_does_not_clear_budget() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    ctrl.run_decision_report()
    assert ctrl.last_budget is budget_before


def test_report_does_not_change_project_id() -> None:
    ctrl = _make_ctrl_with_evidence()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_decision_report()
    assert ctrl.configuration_fingerprint() == fp_before


def test_report_does_not_clear_reconciliation() -> None:
    from origlyph.tolerance.workspace_controller import (
        WorkspaceAllocationEntry,
        WorkspaceAllocationPlan,
    )

    ctrl = _make_ctrl_with_evidence()
    plan = WorkspaceAllocationPlan(
        allowed_budget=2.0,
        entries=(WorkspaceAllocationEntry(contributor_id="A", allocated_span=1.0),),
    )
    ctrl.set_allocation_plan(plan)
    ctrl.run_reconciliation()
    recon_before = ctrl.last_reconciliation
    ctrl.run_decision_report()
    assert ctrl.last_reconciliation is recon_before


def test_report_does_not_clear_statistical_reconciliation() -> None:
    from origlyph.tolerance.workspace_controller import (
        WorkspaceStatisticalAllocationEntry,
        WorkspaceStatisticalAllocationPlan,
    )

    ctrl = ToleranceWorkspaceController(
        chain_name="RSS chain",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.3,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_combined_sigma=1.0))
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()

    plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=1.0,
        entries=(
            WorkspaceStatisticalAllocationEntry(
                contributor_id="A", allocated_sigma=0.5
            ),
        ),
    )
    ctrl.set_statistical_allocation_plan(plan)
    ctrl.run_statistical_reconciliation()
    stat_recon_before = ctrl.last_statistical_reconciliation
    ctrl.run_decision_report()
    assert ctrl.last_statistical_reconciliation is stat_recon_before


# ---------------------------------------------------------------------------
# Stale clearing — report invalidated when evidence/decision becomes stale
# ---------------------------------------------------------------------------


def test_report_cleared_on_new_evidence() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.run_decision_evidence()
    assert ctrl.last_decision_report is None


def test_report_cleared_on_new_decision() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.evaluate_decision()
    assert ctrl.last_decision_report is None


def test_report_cleared_on_run_analysis() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.run_analysis()
    assert ctrl.last_decision_report is None


def test_report_cleared_on_contributor_change() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.last_decision_report is None


def test_report_cleared_on_specification_change() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.5))
    assert ctrl.last_decision_report is None


def test_report_cleared_on_mode_change() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.last_decision_report is None


def test_report_cleared_on_chain_name_change() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    ctrl.set_chain_name("renamed chain")
    assert ctrl.last_decision_report is None


# ---------------------------------------------------------------------------
# Persistence boundary — save/load clears runtime report
# ---------------------------------------------------------------------------


def test_from_state_clears_report() -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.last_decision_report is None


def test_save_load_clears_runtime_report(tmp_path) -> None:
    ctrl = _make_ctrl_with_evidence()
    ctrl.run_decision_report()
    assert ctrl.last_decision_report is not None
    project_file = ctrl.save_project(tmp_path / "test.json")
    loaded = ToleranceWorkspaceController.open_project(project_file)
    assert loaded.last_decision_report is None


def test_project_id_unchanged_after_report(tmp_path) -> None:
    ctrl = _make_ctrl_with_evidence()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_decision_report()
    assert ctrl.configuration_fingerprint() == fp_before


# ---------------------------------------------------------------------------
# No hidden prerequisite generation
# ---------------------------------------------------------------------------


def test_run_decision_report_does_not_auto_generate_evidence() -> None:
    ctrl = _make_ctrl_with_decision()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.run_decision_report()
    assert ctrl.last_evidence is None


def test_session_generate_report_does_not_auto_generate_evidence() -> None:
    ctrl = _make_ctrl_with_decision()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.generate_decision_report()
    assert ctrl.last_evidence is None


# ---------------------------------------------------------------------------
# No export side effects
# ---------------------------------------------------------------------------


def test_report_has_schema_version() -> None:
    ctrl = _make_ctrl_with_evidence()
    report = ctrl.run_decision_report()
    assert report.schema_version == "origlyph.tolerance.decision_report.v1"


def test_report_evidence_refs_present() -> None:
    ctrl = _make_ctrl_with_evidence()
    report = ctrl.run_decision_report()
    assert isinstance(report.evidence_refs, tuple)
