"""Tests for Stage 19D: Statistical Allocation Plan + Reconciliation Workspace.

Covers controller v4 schema management, statistical plan persistence, session
presentation layer, and stale-result clearing for Stage 15J reconciliation.
"""

from __future__ import annotations

import pytest

from origlyph.tolerance.models import (
    StatisticalAllocationReconciliationResult,
)
from origlyph.tolerance.workspace_controller import (
    TOLERANCE_WORKSPACE_SCHEMA_VERSION,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceState,
    WorkspaceStatisticalAllocationEntry,
    WorkspaceStatisticalAllocationPlan,
    workspace_state_from_snapshot,
    workspace_state_to_snapshot,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctrl_with_stat_plan() -> ToleranceWorkspaceController:
    """Two contributors + a statistical allocation plan (k=1)."""
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="stat_recon_test",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal="10.0",
        tolerance="0.10",
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
    plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=1.0,
        entries=(
            WorkspaceStatisticalAllocationEntry(
                contributor_id="A", allocated_sigma=0.12
            ),
            WorkspaceStatisticalAllocationEntry(
                contributor_id="B", allocated_sigma=0.18
            ),
        ),
        allowed_combined_sigma=None,
    )
    ctrl.set_statistical_allocation_plan(plan)
    return ctrl


def _ctrl_without_stat_plan() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="no_stat_plan",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
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
# WorkspaceStatisticalAllocationEntry validation
# ---------------------------------------------------------------------------


def test_entry_valid_zero_sigma() -> None:
    e = WorkspaceStatisticalAllocationEntry(
        contributor_id="A", allocated_sigma=0.0
    )
    assert e.allocated_sigma == 0.0


def test_entry_negative_sigma_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="non-negative"):
        WorkspaceStatisticalAllocationEntry(
            contributor_id="A", allocated_sigma=-0.01
        )


def test_entry_blank_contributor_id_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError):
        WorkspaceStatisticalAllocationEntry(
            contributor_id="  ", allocated_sigma=0.05
        )


def test_entry_as_dict_round_trips() -> None:
    e = WorkspaceStatisticalAllocationEntry(
        contributor_id="X", allocated_sigma=0.07
    )
    d = e.as_dict()
    assert d == {"contributor_id": "X", "allocated_sigma": 0.07}


# ---------------------------------------------------------------------------
# WorkspaceStatisticalAllocationPlan validation
# ---------------------------------------------------------------------------


def test_plan_zero_multiplier_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceStatisticalAllocationPlan(
            sigma_multiplier=0.0,
            entries=(),
        )


def test_plan_negative_multiplier_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceStatisticalAllocationPlan(
            sigma_multiplier=-1.0,
            entries=(),
        )


def test_plan_duplicate_contributor_raises() -> None:
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="duplicate contributor_id"
    ):
        WorkspaceStatisticalAllocationPlan(
            sigma_multiplier=1.0,
            entries=(
                WorkspaceStatisticalAllocationEntry("A", 0.1),
                WorkspaceStatisticalAllocationEntry("A", 0.2),
            ),
        )


def test_plan_negative_allowed_combined_sigma_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceStatisticalAllocationPlan(
            sigma_multiplier=1.0,
            entries=(),
            allowed_combined_sigma=-0.1,
        )


def test_plan_as_dict_round_trips() -> None:
    plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=2.0,
        entries=(
            WorkspaceStatisticalAllocationEntry("A", 0.05),
        ),
        allowed_combined_sigma=0.10,
    )
    d = plan.as_dict()
    assert d["sigma_multiplier"] == 2.0
    assert d["allowed_combined_sigma"] == 0.10
    assert isinstance(d["entries"], list)
    assert len(d["entries"]) == 1


# ---------------------------------------------------------------------------
# Schema version management
# ---------------------------------------------------------------------------


def test_set_stat_plan_upgrades_to_v4() -> None:
    ctrl = _ctrl_with_stat_plan()
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


def test_clear_stat_plan_stays_v4() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.clear_statistical_allocation_plan()
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


def test_set_allocation_plan_on_v4_stays_v4() -> None:
    ctrl = _ctrl_with_stat_plan()
    plan = WorkspaceAllocationPlan(
        allowed_budget=0.5,
        entries=(
            WorkspaceAllocationEntry("A", 0.20),
            WorkspaceAllocationEntry("B", 0.30),
        ),
    )
    ctrl.set_allocation_plan(plan)
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


def test_clear_allocation_plan_on_v4_stays_v4() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.clear_allocation_plan()
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


def test_set_specification_on_v4_stays_v4() -> None:
    from origlyph.tolerance.workspace_controller import WorkspaceSpecification

    ctrl = _ctrl_with_stat_plan()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


def test_workspace_state_v1_rejects_stat_plan() -> None:
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="statistical_allocation_plan"
    ):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION,
            chain_name="test",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            statistical_allocation_plan=WorkspaceStatisticalAllocationPlan(
                sigma_multiplier=1.0, entries=()
            ),
        )


def test_workspace_state_v3_rejects_stat_plan() -> None:
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="statistical_allocation_plan"
    ):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
            chain_name="test",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            statistical_allocation_plan=WorkspaceStatisticalAllocationPlan(
                sigma_multiplier=1.0, entries=()
            ),
        )


# ---------------------------------------------------------------------------
# Snapshot round-trip (v4 persistence)
# ---------------------------------------------------------------------------


def test_v4_snapshot_round_trip() -> None:
    ctrl = _ctrl_with_stat_plan()
    snapshot = workspace_state_to_snapshot(ctrl.state)
    assert snapshot["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    assert "statistical_allocation_plan" in snapshot
    reloaded = workspace_state_from_snapshot(snapshot)
    assert reloaded.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    assert reloaded.statistical_allocation_plan is not None
    assert reloaded.statistical_allocation_plan.sigma_multiplier == pytest.approx(1.0)
    assert len(reloaded.statistical_allocation_plan.entries) == 2


def test_v4_snapshot_null_stat_plan() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.clear_statistical_allocation_plan()
    snapshot = workspace_state_to_snapshot(ctrl.state)
    assert snapshot["statistical_allocation_plan"] is None
    reloaded = workspace_state_from_snapshot(snapshot)
    assert reloaded.statistical_allocation_plan is None


def test_v4_snapshot_with_allowed_combined_sigma() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="sigma_budget_test",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    ctrl.add_contributor(
        identifier="C",
        name="Part C",
        nominal="1.0",
        tolerance="0.05",
        direction="forward",
        tolerance_model="symmetric",
    )
    plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=2.0,
        entries=(
            WorkspaceStatisticalAllocationEntry("C", 0.06),
        ),
        allowed_combined_sigma=0.15,
    )
    ctrl.set_statistical_allocation_plan(plan)
    snapshot = workspace_state_to_snapshot(ctrl.state)
    reloaded = workspace_state_from_snapshot(snapshot)
    assert reloaded.statistical_allocation_plan is not None
    assert reloaded.statistical_allocation_plan.allowed_combined_sigma == pytest.approx(
        0.15
    )
    assert reloaded.statistical_allocation_plan.sigma_multiplier == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Controller: run_statistical_reconciliation
# ---------------------------------------------------------------------------


def test_controller_last_stat_reconciliation_initially_none() -> None:
    ctrl = _ctrl_with_stat_plan()
    assert ctrl.last_statistical_reconciliation is None


def test_controller_run_stat_reconciliation_returns_result() -> None:
    ctrl = _ctrl_with_stat_plan()
    result = ctrl.run_statistical_reconciliation()
    assert isinstance(result, StatisticalAllocationReconciliationResult)


def test_controller_last_stat_reconciliation_cached() -> None:
    ctrl = _ctrl_with_stat_plan()
    result = ctrl.run_statistical_reconciliation()
    assert ctrl.last_statistical_reconciliation is result


def test_controller_run_stat_reconciliation_no_plan_raises() -> None:
    ctrl = _ctrl_without_stat_plan()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="statistical_allocation_plan"
    ):
        ctrl.run_statistical_reconciliation()


def test_controller_run_stat_reconciliation_no_contributors_raises() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="empty",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    ctrl.set_statistical_allocation_plan(
        WorkspaceStatisticalAllocationPlan(sigma_multiplier=1.0, entries=())
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor"):
        ctrl.run_statistical_reconciliation()


def test_controller_run_stat_reconciliation_unknown_contributor_raises() -> None:
    ctrl = _ctrl_without_stat_plan()
    plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=1.0,
        entries=(
            WorkspaceStatisticalAllocationEntry("UNKNOWN", 0.05),
        ),
    )
    ctrl.set_statistical_allocation_plan(plan)
    with pytest.raises(InvalidToleranceWorkspaceError, match="UNKNOWN"):
        ctrl.run_statistical_reconciliation()


# ---------------------------------------------------------------------------
# Controller: stale-result clearing
# ---------------------------------------------------------------------------


def test_stat_reconciliation_cleared_on_contributor_add() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.run_statistical_reconciliation()
    assert ctrl.last_statistical_reconciliation is not None
    ctrl.add_contributor(
        identifier="C",
        name="Part C",
        nominal="2.0",
        tolerance="0.05",
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.last_statistical_reconciliation is None


def test_stat_reconciliation_cleared_on_contributor_remove() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.run_statistical_reconciliation()
    assert ctrl.last_statistical_reconciliation is not None
    ctrl.remove_contributor("A")
    assert ctrl.last_statistical_reconciliation is None


def test_stat_reconciliation_cleared_on_stat_plan_change() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.run_statistical_reconciliation()
    assert ctrl.last_statistical_reconciliation is not None
    new_plan = WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=2.0,
        entries=(
            WorkspaceStatisticalAllocationEntry("A", 0.12),
            WorkspaceStatisticalAllocationEntry("B", 0.18),
        ),
    )
    ctrl.set_statistical_allocation_plan(new_plan)
    assert ctrl.last_statistical_reconciliation is None


def test_stat_reconciliation_cleared_on_stat_plan_clear() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.run_statistical_reconciliation()
    assert ctrl.last_statistical_reconciliation is not None
    ctrl.clear_statistical_allocation_plan()
    assert ctrl.last_statistical_reconciliation is None


def test_stat_reconciliation_cleared_on_from_state() -> None:
    ctrl = _ctrl_with_stat_plan()
    ctrl.run_statistical_reconciliation()
    reloaded = ToleranceWorkspaceController.from_state(ctrl.state)
    assert reloaded.last_statistical_reconciliation is None


# ---------------------------------------------------------------------------
# WorkspaceSession: presentation layer
# ---------------------------------------------------------------------------


def test_session_stat_reconciliation_status_text_no_result() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.statistical_reconciliation_status_text == "NOT RUN"


def test_session_stat_reconciliation_summary_no_result() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.statistical_reconciliation_summary_text == ""


def test_session_stat_reconciliation_rows_empty_when_no_result() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.statistical_reconciliation_rows() == []


def test_session_run_stat_reconciliation_returns_result() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    result = session.run_statistical_reconciliation()
    assert isinstance(result, StatisticalAllocationReconciliationResult)


def test_session_stat_reconciliation_status_text_after_run() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    session.run_statistical_reconciliation()
    text = session.statistical_reconciliation_status_text
    assert text != "NOT RUN"
    assert text  # non-empty string


def test_session_stat_reconciliation_summary_after_run() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    session.run_statistical_reconciliation()
    text = session.statistical_reconciliation_summary_text
    assert "Alloc" in text
    assert "Actual" in text
    assert "Margin" in text


def test_session_stat_reconciliation_rows_after_run() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    session.run_statistical_reconciliation()
    rows = session.statistical_reconciliation_rows()
    assert len(rows) == 2
    assert rows[0]["contributor_id"] == "A"
    assert rows[1]["contributor_id"] == "B"
    for row in rows:
        assert "allocated_sigma" in row
        assert "actual_sigma" in row
        assert "margin" in row
        assert "utilization_pct" in row
        assert "status" in row


def test_session_last_stat_reconciliation_delegates_to_controller() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.last_statistical_reconciliation is None
    session.run_statistical_reconciliation()
    assert session.last_statistical_reconciliation is not None
    assert (
        session.last_statistical_reconciliation
        is ctrl.last_statistical_reconciliation
    )


# ---------------------------------------------------------------------------
# Session: load_statistical_allocation_plan_fields
# ---------------------------------------------------------------------------


def test_session_load_stat_plan_fields_populated() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.stat_sigma_multiplier != ""
    assert session.pending_sigma("A") != ""
    assert session.pending_sigma("B") != ""


def test_session_load_stat_plan_fields_empty_when_no_plan() -> None:
    ctrl = _ctrl_without_stat_plan()
    session = WorkspaceSession(ctrl)
    assert session.stat_sigma_multiplier == ""
    assert session.pending_sigma("X") == ""


def test_session_statistical_allocation_editor_rows() -> None:
    ctrl = _ctrl_with_stat_plan()
    session = WorkspaceSession(ctrl)
    rows = session.statistical_allocation_editor_rows()
    assert len(rows) == 2
    for row in rows:
        assert "contributor_id" in row
        assert "current_sigma" in row
        assert "allocated_sigma_str" in row
