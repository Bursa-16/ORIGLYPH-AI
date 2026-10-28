"""Unit tests for decision evidence and explanation workspace surface (Stage 20B)."""

from __future__ import annotations

import pytest

from origlyph.tolerance.evidence import (
    DecisionEvidenceBundle,
    DecisionExplanation,
    build_decision_evidence,
    explain_tolerance_decision,
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


def _make_controller_with_decision() -> ToleranceWorkspaceController:
    """Return a controller that has a valid decision result cached."""
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
    ctrl.set_specification(
        WorkspaceSpecification(allowed_worst_case_span=2.0)
    )
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    return ctrl


def _make_controller_no_decision() -> ToleranceWorkspaceController:
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
    ctrl.set_specification(
        WorkspaceSpecification(allowed_worst_case_span=2.0)
    )
    ctrl.run_analysis()
    return ctrl


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_evidence_is_none() -> None:
    ctrl = _make_controller_no_decision()
    assert ctrl.last_evidence is None


def test_initial_explanation_is_none() -> None:
    ctrl = _make_controller_no_decision()
    assert ctrl.last_explanation is None


def test_session_initial_evidence_is_none() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.last_evidence is None


def test_session_initial_explanation_is_none() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.last_explanation is None


def test_session_evidence_status_text_initial() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.evidence_status_text == "NOT GENERATED"


def test_session_explanation_summary_text_initial() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.explanation_summary_text == ""


def test_session_evidence_items_rows_initial() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.evidence_items_rows() == []


# ---------------------------------------------------------------------------
# Fail-closed: missing decision
# ---------------------------------------------------------------------------


def test_run_decision_evidence_fails_without_decision() -> None:
    ctrl = _make_controller_no_decision()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Run Decision first"):
        ctrl.run_decision_evidence()


def test_session_generate_evidence_fails_without_decision() -> None:
    ctrl = _make_controller_no_decision()
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError, match="Run Decision first"):
        session.generate_evidence()


# ---------------------------------------------------------------------------
# Successful delegation to Stage 15L
# ---------------------------------------------------------------------------


def test_run_decision_evidence_returns_bundle_and_explanation() -> None:
    ctrl = _make_controller_with_decision()
    bundle, explanation = ctrl.run_decision_evidence()
    assert isinstance(bundle, DecisionEvidenceBundle)
    assert isinstance(explanation, DecisionExplanation)


def test_run_decision_evidence_delegates_to_stage15l() -> None:
    ctrl = _make_controller_with_decision()
    decision = ctrl.last_decision
    assert decision is not None
    expected_bundle = build_decision_evidence(decision)
    expected_explanation = explain_tolerance_decision(decision, expected_bundle)
    bundle, explanation = ctrl.run_decision_evidence()
    assert bundle.decision_status == expected_bundle.decision_status
    assert bundle.is_complete == expected_bundle.is_complete
    assert len(bundle.evidence_items) == len(expected_bundle.evidence_items)
    assert explanation.summary == expected_explanation.summary
    assert explanation.summary_code == expected_explanation.summary_code


def test_evidence_cached_after_generation() -> None:
    ctrl = _make_controller_with_decision()
    bundle, explanation = ctrl.run_decision_evidence()
    assert ctrl.last_evidence is bundle
    assert ctrl.last_explanation is explanation


def test_session_generate_evidence_caches_result() -> None:
    ctrl = _make_controller_with_decision()
    session = WorkspaceSession(ctrl)
    bundle, explanation = session.generate_evidence()
    assert ctrl.last_evidence is bundle
    assert ctrl.last_explanation is explanation


# ---------------------------------------------------------------------------
# Correct evidence content mapping
# ---------------------------------------------------------------------------


def test_evidence_bundle_maps_decision_status() -> None:
    ctrl = _make_controller_with_decision()
    bundle, _ = ctrl.run_decision_evidence()
    assert ctrl.last_decision is not None
    assert bundle.decision_status == ctrl.last_decision.overall_status


def test_explanation_maps_summary() -> None:
    ctrl = _make_controller_with_decision()
    _, explanation = ctrl.run_decision_evidence()
    assert explanation.summary != ""
    assert ctrl.last_decision is not None
    assert explanation.final_status == ctrl.last_decision.overall_status


def test_session_evidence_status_text_after_generation() -> None:
    ctrl = _make_controller_with_decision()
    session = WorkspaceSession(ctrl)
    session.generate_evidence()
    decision = ctrl.last_decision
    assert decision is not None
    expected = decision.overall_status.value.upper()
    assert session.evidence_status_text == expected


def test_session_explanation_summary_text_after_generation() -> None:
    ctrl = _make_controller_with_decision()
    session = WorkspaceSession(ctrl)
    session.generate_evidence()
    assert session.explanation_summary_text != ""


def test_session_evidence_items_rows_after_generation() -> None:
    ctrl = _make_controller_with_decision()
    session = WorkspaceSession(ctrl)
    bundle, _ = session.generate_evidence()
    rows = session.evidence_items_rows()
    assert len(rows) == len(bundle.evidence_items)
    for row in rows:
        assert "evidence_code" in row
        assert "source" in row
        assert "scope" in row
        assert "observed_value" in row
        assert "reference_value" in row
        assert "severity" in row
        assert "detail" in row


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_evidence_generation_is_deterministic() -> None:
    ctrl = _make_controller_with_decision()
    bundle1, explanation1 = ctrl.run_decision_evidence()
    bundle2, explanation2 = ctrl.run_decision_evidence()
    assert bundle1.decision_status == bundle2.decision_status
    assert bundle1.is_complete == bundle2.is_complete
    assert len(bundle1.evidence_items) == len(bundle2.evidence_items)
    assert explanation1.summary == explanation2.summary
    assert explanation1.summary_code == explanation2.summary_code


# ---------------------------------------------------------------------------
# Feature isolation — generating evidence must NOT mutate other state
# ---------------------------------------------------------------------------


def test_evidence_does_not_change_decision() -> None:
    ctrl = _make_controller_with_decision()
    original_decision = ctrl.last_decision
    ctrl.run_decision_evidence()
    assert ctrl.last_decision is original_decision


def test_evidence_does_not_trigger_analysis() -> None:
    ctrl = _make_controller_with_decision()
    original_result = ctrl.last_result
    ctrl.run_decision_evidence()
    assert ctrl.last_result is original_result


def test_evidence_does_not_clear_sensitivity() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    ctrl.run_decision_evidence()
    assert ctrl.last_sensitivity is sensitivity_before


def test_evidence_does_not_clear_budget() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    ctrl.run_decision_evidence()
    assert ctrl.last_budget is budget_before


def test_evidence_does_not_change_project_id() -> None:
    ctrl = _make_controller_with_decision()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_decision_evidence()
    assert ctrl.configuration_fingerprint() == fp_before


# ---------------------------------------------------------------------------
# Stale clearing — evidence invalidated when decision becomes stale
# ---------------------------------------------------------------------------


def test_evidence_cleared_on_new_decision() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.evaluate_decision()
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


def test_evidence_cleared_on_run_analysis() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.run_analysis()
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


def test_evidence_cleared_on_contributor_change() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


def test_evidence_cleared_on_mode_change() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


def test_evidence_cleared_on_specification_change() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.5))
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


def test_evidence_cleared_on_chain_name_change() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    ctrl.set_chain_name("renamed chain")
    assert ctrl.last_evidence is None
    assert ctrl.last_explanation is None


# ---------------------------------------------------------------------------
# Persistence boundary — from_state clears evidence
# ---------------------------------------------------------------------------


def test_from_state_clears_evidence() -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.last_evidence is None
    assert restored.last_explanation is None


def test_save_load_clears_runtime_evidence(tmp_path) -> None:
    ctrl = _make_controller_with_decision()
    ctrl.run_decision_evidence()
    assert ctrl.last_evidence is not None
    project_file = ctrl.save_project(tmp_path / "test.json")
    loaded = ToleranceWorkspaceController.open_project(project_file)
    assert loaded.last_evidence is None
    assert loaded.last_explanation is None


# ---------------------------------------------------------------------------
# No fabricated evidence — allocation reconciliation unchanged
# ---------------------------------------------------------------------------


def test_evidence_does_not_clear_reconciliation() -> None:
    from origlyph.tolerance.workspace_controller import (
        WorkspaceAllocationEntry,
        WorkspaceAllocationPlan,
    )

    ctrl = _make_controller_with_decision()
    plan = WorkspaceAllocationPlan(
        allowed_budget=2.0,
        entries=(WorkspaceAllocationEntry(contributor_id="A", allocated_span=1.0),),
    )
    ctrl.set_allocation_plan(plan)
    ctrl.run_reconciliation()
    recon_before = ctrl.last_reconciliation
    ctrl.run_decision_evidence()
    assert ctrl.last_reconciliation is recon_before


def test_evidence_does_not_clear_statistical_reconciliation() -> None:
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
    ctrl.run_decision_evidence()
    assert ctrl.last_statistical_reconciliation is stat_recon_before
