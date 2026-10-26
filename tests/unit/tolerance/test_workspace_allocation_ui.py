"""Stage 17E-3: Allocation Plan Editor + Validate Allocation UI tests.

Covers:
A. Plan editing — sync_allocation_plan produces exact v3 plan
B. Invalid input — fail-closed on blank/invalid/non-finite values
C. Validation action — explicit only, no auto-validation
D. Result display — session accessor correctness
E. Stale clearing — plan changes remove cached validation result
F. Persistence — save/load round-trip keeps plan, clears result
G. Identity — plan edits rotate fingerprint, validate alone does not
H. Isolation — decision/sensitivity/budget unchanged by validate
I. Binding — contributor IDs preserved, reorder safe, no silent rebind
"""

from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.tolerance import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceSpecification,
    workspace_configuration_fingerprint,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctrl_ab() -> ToleranceWorkspaceController:
    """Controller with two contributors (a=0.2 tol, b=0.3 tol)."""
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="test", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.add_contributor(
        identifier="a", name="Part A", nominal=10.0, tolerance=0.2,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    ctrl.add_contributor(
        identifier="b", name="Part B", nominal=5.0, tolerance=0.3,
        direction=StackDirection.INVERSE, tolerance_model="symmetric",
    )
    return ctrl


def _session_ab() -> WorkspaceSession:
    return WorkspaceSession(_ctrl_ab())


def _set_plan(session: WorkspaceSession, budget: str = "1.0") -> None:
    """Set budget + spans and apply the allocation plan."""
    session.allocation_budget = budget
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    session.sync_allocation_plan()


# ---------------------------------------------------------------------------
# A. PLAN EDITING
# ---------------------------------------------------------------------------


def test_sync_allocation_plan_creates_v3_plan() -> None:
    session = _session_ab()
    _set_plan(session)
    plan = session.controller.allocation_plan
    assert plan is not None
    assert plan.allowed_budget == pytest.approx(1.0)
    ids = {e.contributor_id for e in plan.entries}
    assert ids == {"a", "b"}


def test_sync_allocation_plan_exact_spans() -> None:
    session = _session_ab()
    _set_plan(session)
    plan = session.controller.allocation_plan
    assert plan is not None
    entry_a = next(e for e in plan.entries if e.contributor_id == "a")
    entry_b = next(e for e in plan.entries if e.contributor_id == "b")
    assert entry_a.allocated_span == pytest.approx(0.4)
    assert entry_b.allocated_span == pytest.approx(0.6)


def test_sync_allocation_plan_contributor_ids_not_positional() -> None:
    """Binding is by contributor_id, not by entry position."""
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("b", "0.6")
    session.set_pending_span("a", "0.4")
    session.sync_allocation_plan()
    plan = session.controller.allocation_plan
    assert plan is not None
    entry_a = next(e for e in plan.entries if e.contributor_id == "a")
    assert entry_a.allocated_span == pytest.approx(0.4)


def test_sync_allocation_plan_zero_span_allowed() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "0.0")
    session.set_pending_span("b", "1.0")
    session.sync_allocation_plan()
    plan = session.controller.allocation_plan
    assert plan is not None
    entry_a = next(e for e in plan.entries if e.contributor_id == "a")
    assert entry_a.allocated_span == pytest.approx(0.0)


def test_load_allocation_plan_fields_on_init() -> None:
    """WorkspaceSession.__init__ loads existing plan into transient fields."""
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=2.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.8),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=1.2),
        ),
    ))
    session = WorkspaceSession(ctrl)
    assert session.allocation_budget == "2.0"
    assert session.pending_span("a") == "0.8"
    assert session.pending_span("b") == "1.2"


def test_allocation_editor_rows_shows_all_contributors() -> None:
    session = _session_ab()
    rows = session.allocation_editor_rows()
    assert len(rows) == 2
    ids = {r["contributor_id"] for r in rows}
    assert ids == {"a", "b"}


def test_allocation_editor_rows_current_span_is_tolerance_times_2() -> None:
    session = _session_ab()
    rows = session.allocation_editor_rows()
    row_a = next(r for r in rows if r["contributor_id"] == "a")
    assert row_a["current_span"] == pytest.approx(0.4)


def test_allocation_editor_rows_shows_contributor_names() -> None:
    session = _session_ab()
    rows = session.allocation_editor_rows()
    names = {r["contributor_name"] for r in rows}
    assert "Part A" in names
    assert "Part B" in names


def test_allocation_editor_rows_shows_pending_spans() -> None:
    session = _session_ab()
    session.set_pending_span("a", "0.4")
    rows = session.allocation_editor_rows()
    row_a = next(r for r in rows if r["contributor_id"] == "a")
    assert row_a["allocated_span_str"] == "0.4"


def test_set_pending_span_and_pending_span_roundtrip() -> None:
    session = _session_ab()
    session.set_pending_span("a", "0.35")
    assert session.pending_span("a") == "0.35"


def test_pending_span_empty_by_default() -> None:
    session = _session_ab()
    assert session.pending_span("a") == ""
    assert session.pending_span("b") == ""


# ---------------------------------------------------------------------------
# B. INVALID INPUT
# ---------------------------------------------------------------------------


def test_sync_allocation_plan_blank_budget_raises() -> None:
    session = _session_ab()
    session.allocation_budget = ""
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError, match="budget"):
        session.sync_allocation_plan()


def test_sync_allocation_plan_non_numeric_budget_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "abc"
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_non_finite_budget_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "inf"
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_zero_budget_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "0.0"
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_negative_budget_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "-1.0"
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_blank_span_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "0.4")
    # b span not set — blank
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_no_implicit_zero_for_missing_span() -> None:
    """No contributor span defaults to zero; blank is always an error."""
    session = _session_ab()
    session.allocation_budget = "1.0"
    # neither span set
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_non_numeric_span_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "xyz")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_negative_span_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "-0.1")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_non_finite_span_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "nan")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


def test_sync_allocation_plan_inf_span_raises() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("a", "inf")
    session.set_pending_span("b", "0.6")
    with pytest.raises(InvalidToleranceWorkspaceError):
        session.sync_allocation_plan()


# ---------------------------------------------------------------------------
# C. VALIDATION ACTION
# ---------------------------------------------------------------------------


def test_sync_allocation_plan_does_not_trigger_validate() -> None:
    session = _session_ab()
    _set_plan(session)
    assert session.last_allocation_validation is None


def test_validate_allocation_explicit_call_works() -> None:
    session = _session_ab()
    _set_plan(session)
    result = session.validate_allocation()
    assert result is not None
    assert session.last_allocation_validation is result


def test_validate_allocation_not_triggered_by_clear_plan() -> None:
    session = _session_ab()
    _set_plan(session)
    session.clear_allocation_plan()
    assert session.last_allocation_validation is None


# ---------------------------------------------------------------------------
# D. RESULT DISPLAY
# ---------------------------------------------------------------------------


def test_allocation_validation_status_text_default() -> None:
    session = _session_ab()
    assert session.allocation_validation_status_text == "NOT VALIDATED"


def test_allocation_validation_summary_text_empty_default() -> None:
    session = _session_ab()
    assert session.allocation_validation_summary_text == ""


def test_allocation_validation_status_text_after_validate() -> None:
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    assert session.allocation_validation_status_text != "NOT VALIDATED"
    assert "allocated" in session.allocation_validation_status_text.lower()


def test_allocation_validation_summary_text_after_validate() -> None:
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    summary = session.allocation_validation_summary_text
    assert "Budget" in summary
    assert "Allocated" in summary
    assert "Utilization" in summary


def test_allocation_validation_rows_after_validate() -> None:
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    rows = session.allocation_validation_rows()
    assert len(rows) == 2
    ids = {r["contributor_id"] for r in rows}
    assert ids == {"a", "b"}


# ---------------------------------------------------------------------------
# E. STALE CLEARING
# ---------------------------------------------------------------------------


def test_sync_allocation_plan_clears_prior_validation() -> None:
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    assert session.last_allocation_validation is not None
    _set_plan(session, budget="2.0")
    assert session.last_allocation_validation is None


def test_clear_allocation_plan_clears_validation() -> None:
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    session.clear_allocation_plan()
    assert session.last_allocation_validation is None


def test_clear_allocation_plan_resets_budget_field() -> None:
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.clear_allocation_plan()
    assert session.allocation_budget == ""


def test_clear_allocation_plan_resets_span_fields() -> None:
    session = _session_ab()
    session.set_pending_span("a", "0.4")
    session.clear_allocation_plan()
    assert session.pending_span("a") == ""


def test_set_pending_span_does_not_clear_validation() -> None:
    """Editing transient span (not yet applied) does not clear validation."""
    session = _session_ab()
    _set_plan(session)
    session.validate_allocation()
    session.set_pending_span("a", "0.5")
    assert session.last_allocation_validation is not None


# ---------------------------------------------------------------------------
# F. PERSISTENCE
# ---------------------------------------------------------------------------


def test_save_load_keeps_allocation_plan(tmp_path: Path) -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    path = session.save_project(tmp_path / "alloc.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    plan = ctrl2.allocation_plan
    assert plan is not None
    assert plan.allowed_budget == pytest.approx(1.0)
    entry_a = next(e for e in plan.entries if e.contributor_id == "a")
    assert entry_a.allocated_span == pytest.approx(0.4)


def test_load_allocation_plan_fields_restored_after_open(tmp_path: Path) -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    path = session.save_project(tmp_path / "alloc.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    session2 = WorkspaceSession(ctrl2)
    assert session2.allocation_budget == "1.0"
    assert session2.pending_span("a") == "0.4"
    assert session2.pending_span("b") == "0.6"


def test_validation_result_absent_after_load(tmp_path: Path) -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    session.validate_allocation()
    path = session.save_project(tmp_path / "alloc.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    session2 = WorkspaceSession(ctrl2)
    assert session2.last_allocation_validation is None


# ---------------------------------------------------------------------------
# G. IDENTITY
# ---------------------------------------------------------------------------


def test_sync_allocation_plan_rotates_fingerprint() -> None:
    session = _session_ab()
    fp1 = workspace_configuration_fingerprint(session.controller.state)
    _set_plan(session)
    fp2 = workspace_configuration_fingerprint(session.controller.state)
    assert fp1 != fp2


def test_validate_allocation_alone_does_not_rotate_fingerprint() -> None:
    session = _session_ab()
    _set_plan(session)
    fp1 = workspace_configuration_fingerprint(session.controller.state)
    session.validate_allocation()
    fp2 = workspace_configuration_fingerprint(session.controller.state)
    assert fp1 == fp2


def test_budget_change_rotates_fingerprint() -> None:
    session = _session_ab()
    _set_plan(session, budget="1.0")
    fp1 = workspace_configuration_fingerprint(session.controller.state)
    _set_plan(session, budget="2.0")
    fp2 = workspace_configuration_fingerprint(session.controller.state)
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# H. ISOLATION
# ---------------------------------------------------------------------------


def test_validate_allocation_does_not_affect_decision() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    decision_before = ctrl.last_decision
    session.validate_allocation()
    assert ctrl.last_decision is decision_before


def test_validate_allocation_does_not_affect_sensitivity() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    session.validate_allocation()
    assert ctrl.last_sensitivity is sensitivity_before


def test_validate_allocation_does_not_affect_budget() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    session.validate_allocation()
    assert ctrl.last_budget is budget_before


def test_sync_allocation_plan_does_not_affect_analysis_result() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    ctrl.run_analysis()
    result_before = ctrl.last_result
    _set_plan(session)
    assert ctrl.last_result is result_before


# ---------------------------------------------------------------------------
# I. BINDING
# ---------------------------------------------------------------------------


def test_contributor_reorder_preserves_id_binding() -> None:
    """Entry position does not determine binding; contributor_id does."""
    session = _session_ab()
    session.allocation_budget = "1.0"
    session.set_pending_span("b", "0.6")
    session.set_pending_span("a", "0.4")
    session.sync_allocation_plan()
    plan = session.controller.allocation_plan
    assert plan is not None
    entry_a = next(e for e in plan.entries if e.contributor_id == "a")
    assert entry_a.allocated_span == pytest.approx(0.4)


def test_contributor_removal_excluded_from_next_sync() -> None:
    """After removing 'b', sync produces a plan without 'b' entry."""
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    _set_plan(session)
    ctrl.remove_contributor("b")
    session.allocation_budget = "0.4"
    session.set_pending_span("a", "0.4")
    session.sync_allocation_plan()
    plan = ctrl.allocation_plan
    assert plan is not None
    ids = {e.contributor_id for e in plan.entries}
    assert "b" not in ids
    assert "a" in ids


def test_pending_span_for_removed_contributor_silently_ignored() -> None:
    """Stale pending span for a removed contributor is not included in sync."""
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    session.set_pending_span("a", "0.4")
    session.set_pending_span("b", "0.6")
    ctrl.remove_contributor("b")
    session.allocation_budget = "0.4"
    session.sync_allocation_plan()
    plan = ctrl.allocation_plan
    assert plan is not None
    ids = {e.contributor_id for e in plan.entries}
    assert ids == {"a"}


def test_allocation_editor_rows_excludes_removed_contributor() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    ctrl.remove_contributor("b")
    rows = session.allocation_editor_rows()
    ids = {r["contributor_id"] for r in rows}
    assert "b" not in ids
    assert "a" in ids


def test_new_contributor_has_no_default_span() -> None:
    """Adding a contributor does not silently create an allocated span."""
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    ctrl.add_contributor(
        identifier="c", name="Part C", nominal=1.0, tolerance=0.05,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    assert session.pending_span("c") == ""
