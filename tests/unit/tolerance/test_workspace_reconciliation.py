"""Tests for Stage 19B: Tolerance Reconciliation Workspace integration.

Covers controller runtime state management and WorkspaceSession presentation
layer for reconciliation (Stage 15I worst-case only).
"""

from __future__ import annotations

import pytest

from origlyph.tolerance.models import (
    AllocationReconciliationResult,
    ReconciliationStatus,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _controller_with_plan() -> ToleranceWorkspaceController:
    """Return a controller with two contributors and a valid allocation plan."""
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="recon_test",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal="10.0",
        tolerance="0.1",
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal="5.0",
        tolerance="0.15",
        direction="forward",
        tolerance_model="symmetric",
    )
    plan = WorkspaceAllocationPlan(
        allowed_budget=0.60,
        entries=(
            WorkspaceAllocationEntry(contributor_id="A", allocated_span=0.25),
            WorkspaceAllocationEntry(contributor_id="B", allocated_span=0.35),
        ),
    )
    ctrl.set_allocation_plan(plan)
    return ctrl


def _controller_without_plan() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="recon_no_plan",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="X",
        name="Part X",
        nominal="1.0",
        tolerance="0.05",
        direction="forward",
        tolerance_model="symmetric",
    )
    return ctrl


# ---------------------------------------------------------------------------
# Controller: initial state
# ---------------------------------------------------------------------------


def test_controller_last_reconciliation_initially_none() -> None:
    ctrl = _controller_with_plan()
    assert ctrl.last_reconciliation is None


def test_controller_run_reconciliation_returns_result() -> None:
    ctrl = _controller_with_plan()
    result = ctrl.run_reconciliation()
    assert isinstance(result, AllocationReconciliationResult)


def test_controller_last_reconciliation_cached_after_run() -> None:
    ctrl = _controller_with_plan()
    result = ctrl.run_reconciliation()
    assert ctrl.last_reconciliation is result


def test_controller_run_reconciliation_no_plan_raises() -> None:
    ctrl = _controller_without_plan()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allocation_plan"):
        ctrl.run_reconciliation()


def test_controller_run_reconciliation_no_contributors_raises() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="empty",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.set_allocation_plan(
        WorkspaceAllocationPlan(allowed_budget=1.0, entries=())
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor"):
        ctrl.run_reconciliation()


# ---------------------------------------------------------------------------
# Controller: stale-result clearing
# ---------------------------------------------------------------------------


def test_controller_reconciliation_cleared_on_contributor_add() -> None:
    ctrl = _controller_with_plan()
    ctrl.run_reconciliation()
    assert ctrl.last_reconciliation is not None
    ctrl.add_contributor(
        identifier="C",
        name="Part C",
        nominal="2.0",
        tolerance="0.05",
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.last_reconciliation is None


def test_controller_reconciliation_cleared_on_contributor_remove() -> None:
    ctrl = _controller_with_plan()
    ctrl.run_reconciliation()
    assert ctrl.last_reconciliation is not None
    ctrl.remove_contributor("A")
    assert ctrl.last_reconciliation is None


def test_controller_reconciliation_cleared_on_plan_change() -> None:
    ctrl = _controller_with_plan()
    ctrl.run_reconciliation()
    assert ctrl.last_reconciliation is not None
    new_plan = WorkspaceAllocationPlan(
        allowed_budget=0.70,
        entries=(
            WorkspaceAllocationEntry(contributor_id="A", allocated_span=0.30),
            WorkspaceAllocationEntry(contributor_id="B", allocated_span=0.40),
        ),
    )
    ctrl.set_allocation_plan(new_plan)
    assert ctrl.last_reconciliation is None


def test_controller_reconciliation_cleared_on_plan_clear() -> None:
    ctrl = _controller_with_plan()
    ctrl.run_reconciliation()
    assert ctrl.last_reconciliation is not None
    ctrl.clear_allocation_plan()
    assert ctrl.last_reconciliation is None


# ---------------------------------------------------------------------------
# Controller: from_state resets runtime cache
# ---------------------------------------------------------------------------


def test_controller_from_state_clears_reconciliation() -> None:
    ctrl = _controller_with_plan()
    ctrl.run_reconciliation()
    reloaded = ToleranceWorkspaceController.from_state(ctrl.state)
    assert reloaded.last_reconciliation is None


# ---------------------------------------------------------------------------
# Controller: result contents
# ---------------------------------------------------------------------------


def test_controller_reconciliation_result_fields() -> None:
    ctrl = _controller_with_plan()
    result = ctrl.run_reconciliation()
    assert result.allowed_budget == pytest.approx(0.60)
    assert result.allocated_total == pytest.approx(0.60)
    # actual spans: A=0.2, B=0.3 → total 0.5
    assert result.actual_total_span == pytest.approx(0.5)
    assert result.total_allocation_margin == pytest.approx(0.10)
    assert len(result.contributor_compliances) == 2


def test_controller_reconciliation_status_within_allocation() -> None:
    ctrl = _controller_with_plan()
    result = ctrl.run_reconciliation()
    # actual (0.5) < allocated (0.6) → ACTUAL_WITHIN_ALLOCATION
    assert result.reconciliation_status is ReconciliationStatus.ACTUAL_WITHIN_ALLOCATION


def test_controller_reconciliation_contributor_compliances_ordered() -> None:
    ctrl = _controller_with_plan()
    result = ctrl.run_reconciliation()
    ids = [cc.contributor_id for cc in result.contributor_compliances]
    assert ids == ["A", "B"]


# ---------------------------------------------------------------------------
# WorkspaceSession: presentation layer
# ---------------------------------------------------------------------------


def test_session_reconciliation_status_text_no_result() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    assert session.reconciliation_status_text == "NOT RUN"


def test_session_reconciliation_summary_text_no_result() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    assert session.reconciliation_summary_text == ""


def test_session_reconciliation_rows_empty_when_no_result() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    assert session.reconciliation_rows() == []


def test_session_run_reconciliation_returns_result() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    result = session.run_reconciliation()
    assert isinstance(result, AllocationReconciliationResult)


def test_session_reconciliation_status_text_after_run() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    session.run_reconciliation()
    assert session.reconciliation_status_text == "ACTUAL_WITHIN_ALLOCATION"


def test_session_reconciliation_summary_text_after_run() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    session.run_reconciliation()
    text = session.reconciliation_summary_text
    assert "Budget" in text
    assert "Allocated" in text
    assert "Actual" in text
    assert "Margin" in text


def test_session_reconciliation_rows_after_run() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    session.run_reconciliation()
    rows = session.reconciliation_rows()
    assert len(rows) == 2
    assert rows[0]["contributor_id"] == "A"
    assert rows[1]["contributor_id"] == "B"
    for row in rows:
        assert "allocated_span" in row
        assert "actual_span" in row
        assert "margin" in row
        assert "utilization_pct" in row
        assert "status" in row


def test_session_last_reconciliation_delegates_to_controller() -> None:
    ctrl = _controller_with_plan()
    session = WorkspaceSession(ctrl)
    assert session.last_reconciliation is None
    session.run_reconciliation()
    assert session.last_reconciliation is not None
    assert session.last_reconciliation is ctrl.last_reconciliation
