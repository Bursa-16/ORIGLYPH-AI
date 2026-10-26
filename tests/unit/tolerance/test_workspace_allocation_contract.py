"""Stage 17E-1: Workspace allocation plan contract tests.

Covers:
A. Model validation (WorkspaceAllocationEntry, WorkspaceAllocationPlan)
B. Serialization round-trip and canonical stability (v3 snapshot)
C. Backward compatibility (v1/v2 load with allocation_plan=None)
D. Identity semantics (fingerprint/project_id rotation on plan changes)
E. Contributor binding rules and duplicate detection
F. Controller set_allocation_plan / clear_allocation_plan API
G. Persistence (save/load round-trip preserves plan, project_id stable)
"""

from __future__ import annotations

from typing import Any

import pytest

from origlyph.tolerance import (
    TOLERANCE_WORKSPACE_SCHEMA_VERSION,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceSpecification,
    WorkspaceState,
    workspace_configuration_fingerprint,
    workspace_state_from_snapshot,
    workspace_state_to_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(cid: str = "a", span: float = 0.1) -> WorkspaceAllocationEntry:
    return WorkspaceAllocationEntry(contributor_id=cid, allocated_span=span)


def _plan(
    budget: float = 0.5,
    entries: tuple[WorkspaceAllocationEntry, ...] | None = None,
) -> WorkspaceAllocationPlan:
    if entries is None:
        entries = (_entry("a", 0.2), _entry("b", 0.3))
    return WorkspaceAllocationPlan(allowed_budget=budget, entries=entries)


def _controller_with_contributors() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="test-chain", analysis_mode=AnalysisMode.WORST_CASE
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


# ---------------------------------------------------------------------------
# A. MODEL — WorkspaceAllocationEntry
# ---------------------------------------------------------------------------

def test_entry_valid() -> None:
    e = WorkspaceAllocationEntry(contributor_id="A", allocated_span=0.05)
    assert e.contributor_id == "A"
    assert e.allocated_span == 0.05


def test_entry_zero_span_is_valid() -> None:
    e = WorkspaceAllocationEntry(contributor_id="x", allocated_span=0.0)
    assert e.allocated_span == 0.0


def test_entry_empty_contributor_id_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor_id"):
        WorkspaceAllocationEntry(contributor_id="", allocated_span=0.1)


def test_entry_whitespace_contributor_id_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError):
        WorkspaceAllocationEntry(contributor_id="  ", allocated_span=0.1)


def test_entry_nan_span_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceAllocationEntry(contributor_id="a", allocated_span=float("nan"))


def test_entry_inf_span_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceAllocationEntry(contributor_id="a", allocated_span=float("inf"))


def test_entry_negative_span_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="non-negative"):
        WorkspaceAllocationEntry(contributor_id="a", allocated_span=-0.01)


def test_entry_as_dict() -> None:
    e = WorkspaceAllocationEntry(contributor_id="c1", allocated_span=0.15)
    d = e.as_dict()
    assert d == {"contributor_id": "c1", "allocated_span": 0.15}


# ---------------------------------------------------------------------------
# A. MODEL — WorkspaceAllocationPlan
# ---------------------------------------------------------------------------

def test_plan_valid() -> None:
    p = _plan()
    assert p.allowed_budget == 0.5
    assert len(p.entries) == 2


def test_plan_empty_entries_is_valid() -> None:
    p = WorkspaceAllocationPlan(allowed_budget=1.0, entries=())
    assert p.entries == ()


def test_plan_zero_budget_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceAllocationPlan(allowed_budget=0.0, entries=())


def test_plan_negative_budget_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceAllocationPlan(allowed_budget=-1.0, entries=())


def test_plan_nan_budget_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceAllocationPlan(allowed_budget=float("nan"), entries=())


def test_plan_inf_budget_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceAllocationPlan(allowed_budget=float("inf"), entries=())


def test_plan_duplicate_contributor_ids_raises() -> None:
    entries = (_entry("dup", 0.1), _entry("dup", 0.2))
    with pytest.raises(InvalidToleranceWorkspaceError, match="duplicate"):
        WorkspaceAllocationPlan(allowed_budget=1.0, entries=entries)


def test_plan_entries_not_tuple_raises() -> None:
    with pytest.raises((InvalidToleranceWorkspaceError, TypeError)):
        WorkspaceAllocationPlan(allowed_budget=1.0, entries=[_entry()])  # type: ignore[arg-type]


def test_plan_as_dict() -> None:
    p = WorkspaceAllocationPlan(
        allowed_budget=0.8,
        entries=(_entry("x", 0.3), _entry("y", 0.5)),
    )
    d: dict[str, Any] = p.as_dict()  # type: ignore[assignment]
    assert d["allowed_budget"] == 0.8
    assert len(d["entries"]) == 2
    assert d["entries"][0] == {"contributor_id": "x", "allocated_span": 0.3}


# ---------------------------------------------------------------------------
# B. SERIALIZATION — v3 round-trip and canonical stability
# ---------------------------------------------------------------------------

def test_v3_round_trip_with_plan() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap = workspace_state_to_snapshot(ctrl.state)
    assert snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    state2 = workspace_state_from_snapshot(snap)
    assert state2.allocation_plan is not None
    assert state2.allocation_plan.allowed_budget == 0.5
    assert state2.allocation_plan.entries[0].contributor_id == "a"
    assert state2.allocation_plan.entries[1].contributor_id == "b"


def test_v3_round_trip_null_plan() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    ctrl.clear_allocation_plan()
    snap = workspace_state_to_snapshot(ctrl.state)
    assert snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    assert snap["allocation_plan"] is None
    state2 = workspace_state_from_snapshot(snap)
    assert state2.allocation_plan is None


def test_v3_snapshot_has_all_required_keys() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap = workspace_state_to_snapshot(ctrl.state)
    assert set(snap.keys()) == {
        "schema_version", "chain_name", "analysis_mode",
        "contributors", "specification", "allocation_plan",
    }


def test_v3_canonical_stability_same_inputs() -> None:
    ctrl1 = _controller_with_contributors()
    ctrl1.set_allocation_plan(_plan())
    ctrl2 = _controller_with_contributors()
    ctrl2.set_allocation_plan(_plan())
    snap1 = workspace_state_to_snapshot(ctrl1.state)
    snap2 = workspace_state_to_snapshot(ctrl2.state)
    assert snap1 == snap2


def test_v3_unknown_key_in_snapshot_raises() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap = dict(workspace_state_to_snapshot(ctrl.state))
    snap["unexpected_key"] = "bad"
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v3_unknown_key_in_allocation_plan_raises() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap: dict[str, Any] = dict(workspace_state_to_snapshot(ctrl.state))
    plan_dict: dict[str, Any] = dict(snap["allocation_plan"])
    plan_dict["unexpected"] = 99
    snap["allocation_plan"] = plan_dict
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v3_unknown_key_in_allocation_entry_raises() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap: dict[str, Any] = dict(workspace_state_to_snapshot(ctrl.state))
    plan_dict: dict[str, Any] = dict(snap["allocation_plan"])
    entries: list[dict[str, Any]] = [dict(e) for e in plan_dict["entries"]]
    entries[0]["extra"] = "bad"
    plan_dict["entries"] = entries
    snap["allocation_plan"] = plan_dict
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v3_malformed_allocation_plan_not_dict_raises() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap: dict[str, Any] = dict(workspace_state_to_snapshot(ctrl.state))
    snap["allocation_plan"] = "not-a-dict"
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v3_missing_required_plan_key_raises() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    snap: dict[str, Any] = dict(workspace_state_to_snapshot(ctrl.state))
    plan_dict: dict[str, Any] = dict(snap["allocation_plan"])
    del plan_dict["allowed_budget"]
    snap["allocation_plan"] = plan_dict
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


# ---------------------------------------------------------------------------
# C. BACKWARD COMPATIBILITY
# ---------------------------------------------------------------------------

def test_v1_loads_with_no_allocation_plan() -> None:
    v1 = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION,
        "chain_name": "legacy",
        "analysis_mode": "worst_case",
        "contributors": [],
    }
    state = workspace_state_from_snapshot(v1)
    assert state.allocation_plan is None
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION


def test_v2_loads_with_no_allocation_plan() -> None:
    v2 = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
        "chain_name": "legacy-v2",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
    }
    state = workspace_state_from_snapshot(v2)
    assert state.allocation_plan is None
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2


def test_v1_project_identity_preserved_after_round_trip() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="legacy", analysis_mode=AnalysisMode.WORST_CASE
    )
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    snap = workspace_state_to_snapshot(ctrl.state)
    state2 = workspace_state_from_snapshot(snap)
    fp2 = workspace_configuration_fingerprint(state2)
    assert fp1 == fp2


def test_v1_state_rejects_allocation_plan_on_construction() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION,
            chain_name="x",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            allocation_plan=_plan(entries=(_entry(),)),
        )


def test_v2_state_rejects_allocation_plan_on_construction() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
            chain_name="x",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            allocation_plan=_plan(entries=(_entry(),)),
        )


def test_unknown_schema_version_raises() -> None:
    snap = {
        "schema_version": "origlyph.tolerance.workspace.v999",
        "chain_name": "x",
        "analysis_mode": "worst_case",
        "contributors": [],
    }
    with pytest.raises(InvalidToleranceWorkspaceError, match="unsupported"):
        workspace_state_from_snapshot(snap)


# ---------------------------------------------------------------------------
# D. IDENTITY SEMANTICS
# ---------------------------------------------------------------------------

def test_allowed_budget_change_rotates_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan(budget=0.5))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(_plan(budget=0.6))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


def test_allocated_span_change_rotates_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5,
        entries=(_entry("a", 0.2), _entry("b", 0.3)),
    ))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5,
        entries=(_entry("a", 0.25), _entry("b", 0.25)),
    ))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


def test_add_entry_rotates_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("a", 0.5),)
    ))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("a", 0.2), _entry("b", 0.3))
    ))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


def test_remove_entry_rotates_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("a", 0.2), _entry("b", 0.3))
    ))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("a", 0.5),)
    ))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


def test_contributor_id_change_in_plan_rotates_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("a", 0.5),)
    ))
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(WorkspaceAllocationPlan(
        allowed_budget=0.5, entries=(_entry("c", 0.5),)
    ))
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 != fp2


def test_no_op_plan_round_trip_preserves_fingerprint(tmp_path) -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    fp_before = workspace_configuration_fingerprint(ctrl.state)
    path = ctrl.save_project(tmp_path / "ws.origlyph.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    fp_after = workspace_configuration_fingerprint(ctrl2.state)
    assert fp_before == fp_after


def test_derived_result_does_not_rotate_fingerprint() -> None:
    ctrl = _controller_with_contributors()
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.run_analysis()
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 == fp2


# ---------------------------------------------------------------------------
# E. CONTRIBUTOR BINDING
# ---------------------------------------------------------------------------

def test_duplicate_contributor_id_in_plan_raises() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="duplicate"):
        WorkspaceAllocationPlan(
            allowed_budget=1.0,
            entries=(_entry("dup", 0.1), _entry("dup", 0.2)),
        )


def test_plan_with_unknown_contributor_id_does_not_raise_at_construction() -> None:
    # Cross-workspace validation is Stage 17E-2; construction accepts unknown ids.
    p = WorkspaceAllocationPlan(
        allowed_budget=1.0,
        entries=(_entry("unknown-id", 0.5),),
    )
    assert p.entries[0].contributor_id == "unknown-id"


def test_entry_order_preserved() -> None:
    entries = (_entry("z", 0.1), _entry("a", 0.2), _entry("m", 0.3))
    p = WorkspaceAllocationPlan(allowed_budget=1.0, entries=entries)
    assert [e.contributor_id for e in p.entries] == ["z", "a", "m"]


def test_set_allocation_plan_noop_when_same() -> None:
    ctrl = _controller_with_contributors()
    plan = _plan()
    ctrl.set_allocation_plan(plan)
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(plan)
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 == fp2


# ---------------------------------------------------------------------------
# F. CONTROLLER API
# ---------------------------------------------------------------------------

def test_set_allocation_plan_upgrades_schema_from_v1_to_v3() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE
    )
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    ctrl.set_allocation_plan(_plan(entries=(_entry(),)))
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3


def test_set_allocation_plan_upgrades_schema_from_v2_to_v3() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE,
        specification=WorkspaceSpecification(allowed_worst_case_span=1.0),
    )
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    ctrl.set_allocation_plan(_plan(entries=(_entry(),)))
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3


def test_clear_allocation_plan_keeps_v3_schema() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_allocation_plan(_plan(entries=(_entry(),)))
    ctrl.clear_allocation_plan()
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    assert ctrl.allocation_plan is None


def test_allocation_plan_property_returns_current_plan() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE
    )
    assert ctrl.allocation_plan is None
    plan = _plan(entries=(_entry(),))
    ctrl.set_allocation_plan(plan)
    assert ctrl.allocation_plan == plan


def test_set_allocation_plan_none_on_v1_is_noop() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE
    )
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.set_allocation_plan(None)
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 == fp2
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION


def test_set_invalid_type_raises() -> None:
    ctrl = ToleranceWorkspaceController.empty(
        chain_name="c", analysis_mode=AnalysisMode.WORST_CASE
    )
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.set_allocation_plan("not-a-plan")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# G. PERSISTENCE / IDENTITY
# ---------------------------------------------------------------------------

def test_save_and_load_v3_round_trip_preserves_plan(tmp_path) -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    path = ctrl.save_project(tmp_path / "v3.origlyph.json", project_name="test")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    assert ctrl2.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    assert ctrl2.allocation_plan is not None
    assert ctrl2.allocation_plan.allowed_budget == 0.5
    assert ctrl2.allocation_plan.entries[0].contributor_id == "a"


def test_load_v1_project_has_no_plan(tmp_path) -> None:
    ctrl = _controller_with_contributors()
    path = ctrl.save_project(tmp_path / "v1.origlyph.json", project_name="legacy")
    ctrl2 = ToleranceWorkspaceController.open_project(path)
    assert ctrl2.allocation_plan is None


def test_running_budget_does_not_change_fingerprint_with_plan() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.set_allocation_plan(_plan())
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    ctrl.run_budget()
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 == fp2


def test_running_analysis_does_not_change_fingerprint_or_plan() -> None:
    ctrl = _controller_with_contributors()
    ctrl.set_allocation_plan(_plan())
    fp1 = workspace_configuration_fingerprint(ctrl.state)
    plan_before = ctrl.allocation_plan
    ctrl.run_analysis()
    fp2 = workspace_configuration_fingerprint(ctrl.state)
    assert fp1 == fp2
    assert ctrl.allocation_plan == plan_before
