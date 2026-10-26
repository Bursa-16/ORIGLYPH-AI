"""Stage 17E-2: Workspace allocation validation controller + session tests.

Covers:
A. Delegation — Stage 15 validator invoked; no duplicated math
B. Valid plan — correct conversion, exact result, deterministic
C. Absent plan — fail closed
D. Binding — unknown/orphan/duplicate contributor handling
E. Invalidation — cached result clears on authoritative plan/contributor changes
F. Isolation — decision / sensitivity / budget results not affected
G. Persistence — save/load keeps plan; validation not persisted
H. Identity — validate alone does not rotate project_id
"""

from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.tolerance import (
    AllocationValidationResult,
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
    """Controller with two contributors (a=0.2 tol, b=0.3 tol), v1 schema."""
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


def _plan(budget: float = 1.0) -> WorkspaceAllocationPlan:
    return WorkspaceAllocationPlan(
        allowed_budget=budget,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
        ),
    )


# ---------------------------------------------------------------------------
# A. DELEGATION — Stage 15 validator actually invoked; no duplicated math
# ---------------------------------------------------------------------------


def test_validate_allocation_returns_allocation_validation_result() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    result = ctrl.validate_allocation()
    assert isinstance(result, AllocationValidationResult)


def test_validate_allocation_result_fields_match_stage15_semantics() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan(budget=1.0))
    result = ctrl.validate_allocation()
    # 0.4 + 0.6 = 1.0 == budget → FULLY_ALLOCATED
    assert result.allowed_budget == 1.0
    assert result.allocated_total == pytest.approx(1.0)
    assert result.remaining_unallocated == pytest.approx(0.0, abs=1e-12)
    assert result.utilization_fraction == pytest.approx(1.0)
    assert result.is_complete is True
    assert result.status.value == "fully_allocated"


def test_validate_allocation_under_allocated() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=2.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
        ),
    ))
    result = ctrl.validate_allocation()
    assert result.status.value == "under_allocated"
    assert result.allocated_total == pytest.approx(1.0)


def test_validate_allocation_over_allocated() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
        ),
    ))
    result = ctrl.validate_allocation()
    assert result.status.value == "over_allocated"


def test_validate_allocation_contributor_results_present() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    result = ctrl.validate_allocation()
    ids = [cr.contributor_id for cr in result.contributor_results]
    assert "a" in ids
    assert "b" in ids


def test_validate_allocation_current_span_from_stack() -> None:
    """current_span in result reflects tolerance*2 (upper-lower deviation)."""
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    result = ctrl.validate_allocation()
    cr_a = next(cr for cr in result.contributor_results if cr.contributor_id == "a")
    # tolerance=0.2 → lower_deviation=-0.2, upper_deviation=0.2 → span=0.4
    assert cr_a.current_span == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# B. VALID PLAN — deterministic repeated validation
# ---------------------------------------------------------------------------


def test_validate_allocation_deterministic() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    r1 = ctrl.validate_allocation()
    r2 = ctrl.validate_allocation()
    assert r1 == r2


def test_last_allocation_validation_cached_after_run() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    assert ctrl.last_allocation_validation is None
    result = ctrl.validate_allocation()
    assert ctrl.last_allocation_validation is result


# ---------------------------------------------------------------------------
# C. ABSENT PLAN — fail closed
# ---------------------------------------------------------------------------


def test_validate_allocation_no_plan_raises() -> None:
    ctrl = _ctrl_ab()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allocation_plan"):
        ctrl.validate_allocation()


def test_validate_allocation_no_contributors_raises() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="x", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0, entries=()
    ))
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor"):
        ctrl.validate_allocation()


# ---------------------------------------------------------------------------
# D. BINDING
# ---------------------------------------------------------------------------


def test_validate_allocation_unknown_contributor_raises() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.5),
            WorkspaceAllocationEntry(contributor_id="UNKNOWN", allocated_span=0.5),
        ),
    ))
    with pytest.raises(InvalidToleranceWorkspaceError, match="unknown contributor"):
        ctrl.validate_allocation()


def test_validate_allocation_orphaned_entry_fails_after_remove() -> None:
    """After removing contributor 'b', a plan referencing 'b' is rejected."""
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.remove_contributor("b")
    ctrl.set_allocation_plan(_plan())  # plan still references 'b'
    with pytest.raises(InvalidToleranceWorkspaceError, match="unknown contributor"):
        ctrl.validate_allocation()


def test_validate_allocation_contributor_reorder_safe() -> None:
    """Entry order in plan does not affect correctness; binding is by ID."""
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
        ),
    ))
    result = ctrl.validate_allocation()
    assert isinstance(result, AllocationValidationResult)
    assert result.allocated_total == pytest.approx(1.0)


def test_validate_allocation_missing_contributor_in_plan_raises() -> None:
    """Plan covers only 'a', not 'b' — Stage 15 raises completeness error."""
    from origlyph.tolerance.exceptions import InvalidAllocationError

    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(WorkspaceAllocationEntry(contributor_id="a", allocated_span=1.0),),
    ))
    with pytest.raises(InvalidAllocationError, match="missing"):
        ctrl.validate_allocation()


# ---------------------------------------------------------------------------
# E. INVALIDATION
# ---------------------------------------------------------------------------


def test_set_plan_clears_prior_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    assert ctrl.last_allocation_validation is not None
    ctrl.set_allocation_plan(_plan(budget=2.0))
    assert ctrl.last_allocation_validation is None


def test_clear_plan_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl.clear_allocation_plan()
    assert ctrl.last_allocation_validation is None


def test_allocated_span_change_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.5),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.5),
        ),
    ))
    assert ctrl.last_allocation_validation is None


def test_allowed_budget_change_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan(budget=1.0))
    ctrl.validate_allocation()
    ctrl.set_allocation_plan(_plan(budget=1.5))
    assert ctrl.last_allocation_validation is None


def test_entry_membership_change_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.add_contributor(
        identifier="c", name="Part C", nominal=1.0, tolerance=0.1,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.5,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
            WorkspaceAllocationEntry(contributor_id="c", allocated_span=0.5),
        ),
    ))
    ctrl.validate_allocation()
    # Remove one entry from plan
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(
            WorkspaceAllocationEntry(contributor_id="a", allocated_span=0.4),
            WorkspaceAllocationEntry(contributor_id="b", allocated_span=0.6),
        ),
    ))
    assert ctrl.last_allocation_validation is None


def test_contributor_tolerance_change_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl.edit_contributor("a", tolerance=0.25)
    assert ctrl.last_allocation_validation is None


def test_add_contributor_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl.add_contributor(
        identifier="c", name="Part C", nominal=1.0, tolerance=0.1,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    assert ctrl.last_allocation_validation is None


def test_remove_contributor_clears_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl.remove_contributor("b")
    assert ctrl.last_allocation_validation is None


# ---------------------------------------------------------------------------
# F. ISOLATION
# ---------------------------------------------------------------------------


def test_validate_allocation_does_not_clear_decision() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.set_allocation_plan(_plan())
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    decision_before = ctrl.last_decision
    ctrl.validate_allocation()
    assert ctrl.last_decision is decision_before


def test_validate_allocation_does_not_clear_sensitivity() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    ctrl.validate_allocation()
    assert ctrl.last_sensitivity is sensitivity_before


def test_validate_allocation_does_not_clear_budget() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.set_allocation_plan(_plan())
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    ctrl.validate_allocation()
    assert ctrl.last_budget is budget_before


def test_run_analysis_does_not_clear_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    validation_before = ctrl.last_allocation_validation
    ctrl.run_analysis()
    assert ctrl.last_allocation_validation is validation_before


def test_run_budget_does_not_clear_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    validation_before = ctrl.last_allocation_validation
    ctrl.run_budget()
    assert ctrl.last_allocation_validation is validation_before


def test_evaluate_decision_does_not_clear_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.set_allocation_plan(_plan())
    ctrl.run_analysis()
    ctrl.validate_allocation()
    validation_before = ctrl.last_allocation_validation
    ctrl.evaluate_decision()
    assert ctrl.last_allocation_validation is validation_before


def test_run_sensitivity_does_not_clear_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    validation_before = ctrl.last_allocation_validation
    ctrl.run_sensitivity()
    assert ctrl.last_allocation_validation is validation_before


def test_set_specification_does_not_clear_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    validation_before = ctrl.last_allocation_validation
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    assert ctrl.last_allocation_validation is validation_before


# ---------------------------------------------------------------------------
# G. PERSISTENCE
# ---------------------------------------------------------------------------


def test_save_load_keeps_plan_clears_validation(tmp_path: Path) -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    path = ctrl.save_project(tmp_path / "v3.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    assert ctrl2.allocation_plan is not None
    assert ctrl2.allocation_plan.allowed_budget == 1.0
    assert ctrl2.last_allocation_validation is None


def test_from_state_clears_allocation_validation() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    ctrl2 = ToleranceWorkspaceController.from_state(ctrl.state)
    assert ctrl2.last_allocation_validation is None


def test_from_snapshot_clears_allocation_validation() -> None:
    from origlyph.tolerance import (
        workspace_state_from_snapshot,
        workspace_state_to_snapshot,
    )

    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    ctrl.validate_allocation()
    snap = workspace_state_to_snapshot(ctrl.state)
    state2 = workspace_state_from_snapshot(snap)
    ctrl2 = ToleranceWorkspaceController.from_state(state2)
    assert ctrl2.last_allocation_validation is None


# ---------------------------------------------------------------------------
# H. IDENTITY
# ---------------------------------------------------------------------------


def test_validate_allocation_alone_does_not_rotate_fingerprint() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    fp_before = workspace_configuration_fingerprint(ctrl.state)
    ctrl.validate_allocation()
    fp_after = workspace_configuration_fingerprint(ctrl.state)
    assert fp_before == fp_after


def test_plan_change_rotates_fingerprint() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan(budget=1.0))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(_plan(budget=2.0))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# Session integration
# ---------------------------------------------------------------------------


def test_session_validate_allocation_delegates() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    session = WorkspaceSession(ctrl)
    result = session.validate_allocation()
    assert isinstance(result, AllocationValidationResult)


def test_session_last_allocation_validation_mirrors_controller() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    session = WorkspaceSession(ctrl)
    assert session.last_allocation_validation is None
    session.validate_allocation()
    assert session.last_allocation_validation is ctrl.last_allocation_validation


def test_session_allocation_validation_status_text_not_validated() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    assert session.allocation_validation_status_text == "NOT VALIDATED"


def test_session_allocation_validation_status_text_after_run() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    session = WorkspaceSession(ctrl)
    session.validate_allocation()
    assert session.allocation_validation_status_text != "NOT VALIDATED"
    assert "allocated" in session.allocation_validation_status_text.lower()


def test_session_allocation_validation_summary_text_empty_when_not_run() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    assert session.allocation_validation_summary_text == ""


def test_session_allocation_validation_summary_text_after_run() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    session = WorkspaceSession(ctrl)
    session.validate_allocation()
    summary = session.allocation_validation_summary_text
    assert "Budget" in summary
    assert "Allocated" in summary
    assert "Utilization" in summary


def test_session_allocation_validation_rows_empty_when_not_run() -> None:
    ctrl = _ctrl_ab()
    session = WorkspaceSession(ctrl)
    assert session.allocation_validation_rows() == []


def test_session_allocation_validation_rows_after_run() -> None:
    ctrl = _ctrl_ab()
    ctrl.set_allocation_plan(_plan())
    session = WorkspaceSession(ctrl)
    session.validate_allocation()
    rows = session.allocation_validation_rows()
    assert len(rows) == 2
    ids = [r["contributor_id"] for r in rows]
    assert "a" in ids
    assert "b" in ids
    row_a = next(r for r in rows if r["contributor_id"] == "a")
    assert row_a["allocated_span"] == pytest.approx(0.4)
    assert "current_span" in row_a
    assert "delta_from_current" in row_a
    assert "fraction_pct" in row_a
