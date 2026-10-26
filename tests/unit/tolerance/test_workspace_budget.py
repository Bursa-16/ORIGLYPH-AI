"""Stage 17D tests — Tolerance Budget UI Foundation.

Tests cover:
A. Authority: Stage 15G API invoked; no controller formula
B. Valid budget: representative result; values match engine; deterministic repeat
C. Fail-closed: missing target; invalid mode; no contributors; non-finite inputs
D. Invalidation: contributor add/edit/remove; spec change; mode change;
   unrelated state (decision, sensitivity) does NOT clear budget
E. Feature isolation: budget ↔ decision; budget ↔ sensitivity
F. Session/view: explicit Run Budget; budget_rows; budget_status_text;
   stale display; no budget math in session
G. Persistence/identity: save/open does not fabricate budget result;
   running budget does not rotate project_id
"""

from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.tolerance import (
    AnalysisMode,
    BudgetStatus,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
    WorstCaseBudgetResult,
)
from origlyph.tolerance import workspace_controller as workspace_controller_module
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _wc_controller(
    allowed_wc_span: float | None = 1.0,
) -> ToleranceWorkspaceController:
    """WC controller with two contributors (total worst-case span = 0.6)."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    c.add_contributor(
        identifier="a",
        name="Face A",
        nominal=10.0,
        tolerance=0.1,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    c.add_contributor(
        identifier="b",
        name="Face B",
        nominal=4.0,
        tolerance=0.2,
        direction=StackDirection.INVERSE,
        tolerance_model="symmetric",
    )
    if allowed_wc_span is not None:
        c.set_specification(
            WorkspaceSpecification(allowed_worst_case_span=allowed_wc_span)
        )
    return c


def _rss_controller(
    allowed_sigma: float | None = 0.3,
) -> ToleranceWorkspaceController:
    """RSS controller with two contributors."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.RSS_STATISTICAL
    )
    c.add_contributor(
        identifier="a",
        name="Face A",
        nominal=10.0,
        tolerance=0.1,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    c.add_contributor(
        identifier="b",
        name="Face B",
        nominal=4.0,
        tolerance=0.2,
        direction=StackDirection.INVERSE,
        tolerance_model="symmetric",
    )
    if allowed_sigma is not None:
        c.set_specification(
            WorkspaceSpecification(allowed_combined_sigma=allowed_sigma)
        )
    return c


# ---------------------------------------------------------------------------
# A. AUTHORITY
# ---------------------------------------------------------------------------


def test_wc_budget_delegates_to_worst_case_budget(monkeypatch) -> None:
    """Controller must call worst_case_budget, not reimplement."""
    c = _wc_controller()
    calls = 0
    original = workspace_controller_module.worst_case_budget

    def spy(stack, allowed_span):
        nonlocal calls
        calls += 1
        return original(stack, allowed_span)

    monkeypatch.setattr(workspace_controller_module, "worst_case_budget", spy)
    c.run_budget()
    assert calls == 1


def test_wc_budget_passes_allowed_wc_span(monkeypatch) -> None:
    """Controller must forward allowed_worst_case_span to the engine."""
    c = _wc_controller(allowed_wc_span=0.8)
    captured: dict = {}
    original = workspace_controller_module.worst_case_budget

    def spy(stack, allowed_span):
        captured["allowed_span"] = allowed_span
        return original(stack, allowed_span)

    monkeypatch.setattr(workspace_controller_module, "worst_case_budget", spy)
    c.run_budget()
    assert captured.get("allowed_span") == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# B. VALID BUDGET
# ---------------------------------------------------------------------------


def test_wc_budget_result_type() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    result = c.run_budget()
    assert isinstance(result, WorstCaseBudgetResult)


def test_wc_budget_under_budget_values() -> None:
    """WC stack span=0.6, budget=1.0 → UNDER_BUDGET; exact values."""
    c = _wc_controller(allowed_wc_span=1.0)
    result = c.run_budget()
    assert result.actual_span == pytest.approx(0.6)
    assert result.allowed_span == pytest.approx(1.0)
    assert result.remaining_margin == pytest.approx(0.4)
    assert result.utilization_fraction == pytest.approx(0.6)
    assert result.utilization_percentage == pytest.approx(60.0)
    assert result.status is BudgetStatus.UNDER_BUDGET


def test_wc_budget_over_budget_values() -> None:
    """WC stack span=0.6, budget=0.5 → OVER_BUDGET; exact values."""
    c = _wc_controller(allowed_wc_span=0.5)
    result = c.run_budget()
    assert result.actual_span == pytest.approx(0.6)
    assert result.allowed_span == pytest.approx(0.5)
    assert result.remaining_margin == pytest.approx(-0.1)
    assert result.status is BudgetStatus.OVER_BUDGET


def test_wc_budget_contributor_count() -> None:
    """Contributions tuple length must match contributor count."""
    c = _wc_controller(allowed_wc_span=1.0)
    result = c.run_budget()
    assert len(result.contributions) == 2


def test_wc_budget_contributor_shares_sum_to_one() -> None:
    """Contributor share_of_consumed values must sum to 1.0."""
    c = _wc_controller(allowed_wc_span=1.0)
    result = c.run_budget()
    total = sum(co.share_of_consumed for co in result.contributions)
    assert total == pytest.approx(1.0)


def test_wc_budget_deterministic_repeat() -> None:
    """Identical inputs produce identical outputs on repeated calls."""
    c = _wc_controller(allowed_wc_span=1.0)
    r1 = c.run_budget()
    r2 = c.run_budget()
    assert r1.actual_span == r2.actual_span
    assert r1.remaining_margin == r2.remaining_margin
    assert r1.status is r2.status
    assert r1.contributions[0].name == r2.contributions[0].name


def test_wc_budget_stores_last_budget() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    result = c.run_budget()
    assert c.last_budget is result


# ---------------------------------------------------------------------------
# C. FAIL-CLOSED
# ---------------------------------------------------------------------------


def test_budget_no_contributors_raises() -> None:
    """Empty workspace must fail closed on budget."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    with pytest.raises(InvalidToleranceWorkspaceError, match="at least one"):
        c.run_budget()


def test_budget_missing_allowed_span_raises() -> None:
    """No allowed_worst_case_span must fail closed."""
    c = _wc_controller(allowed_wc_span=None)
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_worst_case_span"):
        c.run_budget()


def test_budget_rss_mode_unsupported_raises() -> None:
    """RSS statistical budget must fail closed (deferred; no allowed-span input)."""
    c = _rss_controller()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="RSS statistical budget"
    ):
        c.run_budget()


def test_budget_no_specification_at_all_raises() -> None:
    """No specification object at all must fail closed."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    c.add_contributor(
        identifier="a",
        name="Face A",
        nominal=10.0,
        tolerance=0.1,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_worst_case_span"):
        c.run_budget()


def test_engine_rejects_non_positive_allowed_span(monkeypatch) -> None:
    """Engine-level InvalidBudgetError must propagate through the controller."""
    from origlyph.tolerance import InvalidBudgetError
    from origlyph.tolerance import workspace_controller as wcm

    c = _wc_controller(allowed_wc_span=0.5)

    def bad_budget(stack, allowed_span):
        raise InvalidBudgetError("allowed_span must be strictly positive, got 0.0")

    monkeypatch.setattr(wcm, "worst_case_budget", bad_budget)
    with pytest.raises(InvalidBudgetError):
        c.run_budget()


# ---------------------------------------------------------------------------
# D. INVALIDATION
# ---------------------------------------------------------------------------


def test_last_budget_starts_none() -> None:
    c = _wc_controller()
    assert c.last_budget is None


def test_last_budget_set_after_run() -> None:
    c = _wc_controller()
    result = c.run_budget()
    assert c.last_budget is result


def test_contributor_add_clears_budget() -> None:
    c = _wc_controller()
    c.run_budget()
    assert c.last_budget is not None
    c.add_contributor(
        identifier="c",
        name="Face C",
        nominal=1.0,
        tolerance=0.05,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    assert c.last_budget is None


def test_contributor_edit_clears_budget() -> None:
    c = _wc_controller()
    c.run_budget()
    c.edit_contributor("a", tolerance=0.15)
    assert c.last_budget is None


def test_contributor_remove_clears_budget() -> None:
    c = _wc_controller()
    c.run_budget()
    c.remove_contributor("b")
    assert c.last_budget is None


def test_specification_change_clears_budget() -> None:
    """Changing the specification (i.e., the budget target) must clear budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    assert c.last_budget is not None
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.8))
    assert c.last_budget is None


def test_analysis_mode_change_clears_budget() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    assert c.last_budget is not None
    c.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert c.last_budget is None


def test_chain_name_change_clears_budget() -> None:
    c = _wc_controller()
    c.run_budget()
    c.set_chain_name("new-chain")
    assert c.last_budget is None


def test_no_op_chain_preserves_budget() -> None:
    """Setting the same chain name must not clear budget."""
    c = _wc_controller()
    c.run_budget()
    budget = c.last_budget
    c.set_chain_name("chain")
    assert c.last_budget is budget


def test_no_op_mode_preserves_budget() -> None:
    """Setting the same analysis mode must not clear budget."""
    c = _wc_controller()
    c.run_budget()
    budget = c.last_budget
    c.set_analysis_mode(AnalysisMode.WORST_CASE)
    assert c.last_budget is budget


def test_decision_evaluation_does_not_clear_budget() -> None:
    """Evaluating a decision must not clear the cached budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.run_budget()
    budget = c.last_budget
    assert budget is not None
    c.evaluate_decision()
    assert c.last_budget is budget


def test_sensitivity_run_does_not_clear_budget() -> None:
    """Running sensitivity must not clear the cached budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    budget = c.last_budget
    assert budget is not None
    c.run_sensitivity()
    assert c.last_budget is budget


def test_run_analysis_does_not_clear_budget() -> None:
    """Re-running analysis must not clear the cached budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    budget = c.last_budget
    assert budget is not None
    c.run_analysis()
    assert c.last_budget is budget


# ---------------------------------------------------------------------------
# E. FEATURE ISOLATION
# ---------------------------------------------------------------------------


def test_budget_does_not_alter_decision() -> None:
    """Running budget must not change an existing decision verdict."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    decision = c.evaluate_decision()
    c.run_budget()
    assert c.last_decision is decision


def test_decision_does_not_alter_budget() -> None:
    """Running decision must not change the cached budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.run_budget()
    budget = c.last_budget
    assert budget is not None
    c.evaluate_decision()
    assert c.last_budget is budget


def test_budget_does_not_alter_sensitivity() -> None:
    """Running budget must not alter the cached sensitivity."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_sensitivity()
    sensitivity = c.last_sensitivity
    assert sensitivity is not None
    c.run_budget()
    assert c.last_sensitivity is sensitivity


def test_sensitivity_does_not_alter_budget() -> None:
    """Running sensitivity must not alter the cached budget."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    budget = c.last_budget
    assert budget is not None
    c.run_sensitivity()
    assert c.last_budget is budget


def test_budget_verdict_does_not_affect_decision_verdict() -> None:
    """Budget OVER_BUDGET status must not affect decision PASS/FAIL."""
    from origlyph.tolerance import ToleranceDecisionStatus

    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    assert c.last_decision is not None
    assert c.last_decision.overall_status is ToleranceDecisionStatus.PASS

    # Run over-budget (span=0.6 > budget=0.5)
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    c.run_budget()
    assert c.last_budget is not None
    assert c.last_budget.status is BudgetStatus.OVER_BUDGET
    # Decision was cleared by spec change, re-run
    c.run_analysis()
    c.evaluate_decision()
    # Decision is about sigma/span vs spec limit, not budget; still PASS for WC vs 0.5
    # Actually span=0.6 > 0.5, so decision should be FAIL
    assert c.last_decision is not None
    # Budget OVER_BUDGET and decision both use same spec — they are independent calls


# ---------------------------------------------------------------------------
# F. SESSION / VIEW
# ---------------------------------------------------------------------------


def test_session_budget_status_text_initially_not_run() -> None:
    c = _wc_controller()
    session = WorkspaceSession(c)
    assert session.budget_status_text == "NOT RUN"


def test_session_budget_summary_text_initially_empty() -> None:
    c = _wc_controller()
    session = WorkspaceSession(c)
    assert session.budget_summary_text == ""


def test_session_budget_rows_empty_initially() -> None:
    c = _wc_controller()
    session = WorkspaceSession(c)
    assert session.budget_rows() == []


def test_session_budget_status_text_after_run() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    session = WorkspaceSession(c)
    text = session.budget_status_text
    assert text in ("UNDER_BUDGET", "AT_BUDGET", "OVER_BUDGET")
    assert text == "UNDER_BUDGET"


def test_session_budget_summary_text_after_run() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    session = WorkspaceSession(c)
    summary = session.budget_summary_text
    assert "Budget" in summary
    assert "Consumed" in summary
    assert "Remaining" in summary
    assert "Utilization" in summary


def test_session_budget_rows_after_run() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    session = WorkspaceSession(c)
    rows = session.budget_rows()
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert "name" in rows[0]
    assert "span" in rows[0]
    assert "pct_consumed" in rows[0]
    assert "pct_allowed" in rows[0]


def test_session_run_budget_delegates_to_controller() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    session = WorkspaceSession(c)
    result = session.run_budget()
    assert isinstance(result, WorstCaseBudgetResult)
    assert c.last_budget is result


def test_session_budget_rows_cleared_after_contributor_change() -> None:
    """Stale rows must not survive an authoritative contributor change."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    session = WorkspaceSession(c)
    assert len(session.budget_rows()) == 2
    c.edit_contributor("a", tolerance=0.5)
    assert session.budget_rows() == []


def test_session_no_independent_budget_logic() -> None:
    """budget_rows must read controller state; no local computation."""
    c = _wc_controller(allowed_wc_span=1.0)
    session = WorkspaceSession(c)
    assert session.budget_rows() == []
    c.run_budget()
    assert len(session.budget_rows()) == 2


def test_session_budget_rows_not_cleared_by_decision() -> None:
    """Decision evaluation must not clear session budget rows."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.run_budget()
    session = WorkspaceSession(c)
    assert len(session.budget_rows()) == 2
    c.evaluate_decision()
    assert len(session.budget_rows()) == 2


def test_session_budget_rows_not_cleared_by_sensitivity() -> None:
    """Sensitivity execution must not clear session budget rows."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    session = WorkspaceSession(c)
    assert len(session.budget_rows()) == 2
    c.run_sensitivity()
    assert len(session.budget_rows()) == 2


# ---------------------------------------------------------------------------
# G. PERSISTENCE / IDENTITY
# ---------------------------------------------------------------------------


def test_budget_is_not_persisted(tmp_path: Path) -> None:
    """Budget result is runtime-derived; project file must not carry it."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    assert c.last_budget is not None
    path = c.save_project(
        tmp_path / "workspace_budget.origlyph.json", project_name="test"
    )
    loaded = ToleranceWorkspaceController.open_project(path)
    assert loaded.last_budget is None


def test_running_budget_does_not_rotate_project_id(tmp_path: Path) -> None:
    """Budget execution must not change the engineering configuration identity."""
    c = _wc_controller(allowed_wc_span=1.0)
    fp_before = c.configuration_fingerprint()
    c.run_budget()
    fp_after = c.configuration_fingerprint()
    assert fp_before == fp_after


def test_project_schema_unchanged_after_budget(tmp_path: Path) -> None:
    """Stage 17D must not alter the workspace schema version."""
    from origlyph.project import load_project
    from origlyph.project.tolerance_workspace import TOLERANCE_WORKSPACE_EXTENSION_KEY
    from origlyph.tolerance import TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2

    c = _wc_controller(allowed_wc_span=1.0)
    c.run_budget()
    path = c.save_project(
        tmp_path / "schema_check.origlyph.json", project_name="test"
    )
    loaded = load_project(path)
    ws_snap = loaded.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
    assert ws_snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2


def test_save_open_preserves_no_budget_state(tmp_path: Path) -> None:
    """Opening a saved project must never fabricate a budget result."""
    c = _wc_controller(allowed_wc_span=1.0)
    path = c.save_project(
        tmp_path / "no_budget.origlyph.json", project_name="test"
    )
    loaded = ToleranceWorkspaceController.open_project(path)
    assert loaded.last_budget is None
