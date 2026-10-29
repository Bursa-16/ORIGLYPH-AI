"""Unit tests for workspace schema v5 acceptance persistence (Stage 20G.2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.workspace_controller import (
    TOLERANCE_WORKSPACE_SCHEMA_VERSION,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
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

_SHA = hashlib.sha256(b"handoff").hexdigest()
_SHA2 = hashlib.sha256(b"handoff2").hexdigest()
_SHA3 = hashlib.sha256(b"handoff3").hexdigest()
_fp = workspace_configuration_fingerprint


def _acceptance(
    decision: AuditAcceptanceDecision = AuditAcceptanceDecision.APPROVED,
    authority: str = "AUTH-001",
    reference: str = "DEC-001",
    handoff_id: str = _SHA,
) -> WorkspaceAcceptanceState:
    return WorkspaceAcceptanceState(
        decision=decision,
        authority_reference=authority,
        decision_reference=reference,
        handoff_id=handoff_id,
    )


def _v5_state(acceptance: WorkspaceAcceptanceState | None = None) -> WorkspaceState:
    return WorkspaceState(
        schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
        chain_name="Chain A",
        analysis_mode=AnalysisMode.WORST_CASE,
        contributors=(),
        acceptance_state=acceptance,
    )


def _ctrl_v5() -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name="Chain A", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance())
    return ctrl


# ---------------------------------------------------------------------------
# Schema version constant
# ---------------------------------------------------------------------------


def test_v5_schema_version_constant() -> None:
    assert TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5 == "origlyph.tolerance.workspace.v5"


def test_v5_schema_version_distinct_from_v4() -> None:
    assert (
        TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5 != TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    )


# ---------------------------------------------------------------------------
# WorkspaceAcceptanceState construction
# ---------------------------------------------------------------------------


def test_acceptance_state_stores_decision() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.APPROVED)
    assert acc.decision is AuditAcceptanceDecision.APPROVED


def test_acceptance_state_stores_authority_reference() -> None:
    acc = _acceptance(authority="AUTH-REF-42")
    assert acc.authority_reference == "AUTH-REF-42"


def test_acceptance_state_stores_decision_reference() -> None:
    acc = _acceptance(reference="DEC-REF-99")
    assert acc.decision_reference == "DEC-REF-99"


def test_acceptance_state_stores_handoff_id() -> None:
    acc = _acceptance(handoff_id=_SHA)
    assert acc.handoff_id == _SHA


def test_acceptance_state_rejected_decision() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.REJECTED)
    assert acc.decision is AuditAcceptanceDecision.REJECTED


def test_acceptance_state_returned_for_action_decision() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.RETURNED_FOR_ACTION)
    assert acc.decision is AuditAcceptanceDecision.RETURNED_FOR_ACTION


def test_acceptance_state_is_frozen() -> None:
    acc = _acceptance()
    with pytest.raises((AttributeError, TypeError)):
        acc.decision = AuditAcceptanceDecision.REJECTED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WorkspaceAcceptanceState validation — malformed inputs
# ---------------------------------------------------------------------------


def test_acceptance_state_rejects_non_enum_decision() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="decision"):
        WorkspaceAcceptanceState(
            decision="approved",  # type: ignore[arg-type]
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=_SHA,
        )


def test_acceptance_state_rejects_empty_authority_reference() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="authority_reference"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="",
            decision_reference="DEC-001",
            handoff_id=_SHA,
        )


def test_acceptance_state_rejects_whitespace_authority_reference() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="authority_reference"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="  ",
            decision_reference="DEC-001",
            handoff_id=_SHA,
        )


def test_acceptance_state_rejects_leading_whitespace_authority_reference() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="authority_reference"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference=" AUTH-001",
            decision_reference="DEC-001",
            handoff_id=_SHA,
        )


def test_acceptance_state_rejects_empty_decision_reference() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="decision_reference"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="",
            handoff_id=_SHA,
        )


def test_acceptance_state_rejects_invalid_handoff_id_short() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="handoff_id"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id="abc",
        )


def test_acceptance_state_rejects_uppercase_handoff_id() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="handoff_id"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=_SHA.upper(),
        )


def test_acceptance_state_rejects_non_hex_handoff_id() -> None:
    bad = "g" * 64
    with pytest.raises(InvalidToleranceWorkspaceError, match="handoff_id"):
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=bad,
        )


# ---------------------------------------------------------------------------
# WorkspaceAcceptanceState as_dict
# ---------------------------------------------------------------------------


def test_acceptance_state_as_dict_decision_is_string_value() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.APPROVED)
    d = acc.as_dict()
    assert d["decision"] == "approved"


def test_acceptance_state_as_dict_rejected_is_string_value() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.REJECTED)
    d = acc.as_dict()
    assert d["decision"] == "rejected"


def test_acceptance_state_as_dict_returned_is_string_value() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.RETURNED_FOR_ACTION)
    d = acc.as_dict()
    assert d["decision"] == "returned_for_action"


def test_acceptance_state_as_dict_contains_authority_reference() -> None:
    acc = _acceptance(authority="AUTH-XYZ")
    d = acc.as_dict()
    assert d["authority_reference"] == "AUTH-XYZ"


def test_acceptance_state_as_dict_contains_decision_reference() -> None:
    acc = _acceptance(reference="DEC-XYZ")
    d = acc.as_dict()
    assert d["decision_reference"] == "DEC-XYZ"


def test_acceptance_state_as_dict_contains_handoff_id() -> None:
    acc = _acceptance(handoff_id=_SHA)
    d = acc.as_dict()
    assert d["handoff_id"] == _SHA


def test_acceptance_state_as_dict_exact_keys() -> None:
    d = _acceptance().as_dict()
    assert set(d) == {
        "decision", "authority_reference", "decision_reference", "handoff_id"
    }


# ---------------------------------------------------------------------------
# V1-V4 backward compatibility — acceptance_state must be None
# ---------------------------------------------------------------------------


def test_v1_load_acceptance_none() -> None:
    state = workspace_state_from_snapshot({
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
    })
    assert state.acceptance_state is None


def test_v2_load_acceptance_none() -> None:
    state = workspace_state_from_snapshot({
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
    })
    assert state.acceptance_state is None


def test_v3_load_acceptance_none() -> None:
    state = workspace_state_from_snapshot({
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
    })
    assert state.acceptance_state is None


def test_v4_load_acceptance_none() -> None:
    state = workspace_state_from_snapshot({
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
    })
    assert state.acceptance_state is None


def test_v1_state_rejects_acceptance_state() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="acceptance_state"):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION,
            chain_name="C",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            acceptance_state=_acceptance(),
        )


def test_v4_state_rejects_acceptance_state() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="acceptance_state"):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
            chain_name="C",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            acceptance_state=_acceptance(),
        )


# ---------------------------------------------------------------------------
# V5 WorkspaceState construction
# ---------------------------------------------------------------------------


def test_v5_state_acceptance_none() -> None:
    state = _v5_state(None)
    assert state.acceptance_state is None
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5


def test_v5_state_acceptance_set() -> None:
    acc = _acceptance()
    state = _v5_state(acc)
    assert state.acceptance_state is acc


def test_v5_state_rejects_wrong_type_acceptance() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="acceptance_state"):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
            chain_name="C",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            acceptance_state="not-a-state",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# V5 snapshot round-trip
# ---------------------------------------------------------------------------


def test_v5_round_trip_with_acceptance() -> None:
    acc = _acceptance()
    state = _v5_state(acc)
    snapshot = workspace_state_to_snapshot(state)
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is not None
    assert restored.acceptance_state.decision == AuditAcceptanceDecision.APPROVED
    assert restored.acceptance_state.authority_reference == "AUTH-001"
    assert restored.acceptance_state.decision_reference == "DEC-001"
    assert restored.acceptance_state.handoff_id == _SHA


def test_v5_round_trip_decision_exact() -> None:
    acc = _acceptance(decision=AuditAcceptanceDecision.REJECTED)
    state = _v5_state(acc)
    snapshot = workspace_state_to_snapshot(state)
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is not None
    assert restored.acceptance_state.decision is AuditAcceptanceDecision.REJECTED


def test_v5_round_trip_authority_reference_exact() -> None:
    acc = _acceptance(authority="AUTHORITY-REF-2025")
    state = _v5_state(acc)
    snapshot = workspace_state_to_snapshot(state)
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is not None
    assert restored.acceptance_state.authority_reference == "AUTHORITY-REF-2025"


def test_v5_round_trip_decision_reference_exact() -> None:
    acc = _acceptance(reference="DECISION-2025-001")
    state = _v5_state(acc)
    snapshot = workspace_state_to_snapshot(state)
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is not None
    assert restored.acceptance_state.decision_reference == "DECISION-2025-001"


def test_v5_round_trip_handoff_id_exact() -> None:
    acc = _acceptance(handoff_id=_SHA2)
    state = _v5_state(acc)
    snapshot = workspace_state_to_snapshot(state)
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is not None
    assert restored.acceptance_state.handoff_id == _SHA2


def test_v5_round_trip_null_acceptance() -> None:
    state = _v5_state(None)
    snapshot = workspace_state_to_snapshot(state)
    assert snapshot["acceptance_state"] is None
    restored = workspace_state_from_snapshot(snapshot)
    assert restored.acceptance_state is None


def test_v5_snapshot_keys_include_acceptance_state() -> None:
    state = _v5_state(_acceptance())
    snapshot = workspace_state_to_snapshot(state)
    assert "acceptance_state" in snapshot


def test_v4_snapshot_keys_exclude_acceptance_state() -> None:
    state = WorkspaceState(
        schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
        chain_name="C",
        analysis_mode=AnalysisMode.WORST_CASE,
        contributors=(),
    )
    snapshot = workspace_state_to_snapshot(state)
    assert "acceptance_state" not in snapshot


# ---------------------------------------------------------------------------
# Deserialization validation — fail-closed
# ---------------------------------------------------------------------------


def test_v5_from_snapshot_rejects_unknown_key() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
        "acceptance_state": None,
        "unexpected_key": "value",
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v5_from_snapshot_rejects_invalid_decision() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
        "acceptance_state": {
            "decision": "not_a_real_decision",
            "authority_reference": "AUTH",
            "decision_reference": "DEC",
            "handoff_id": _SHA,
        },
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v5_from_snapshot_rejects_non_dict_acceptance_state() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
        "acceptance_state": "not-a-dict",
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_unknown_schema_fails_closed() -> None:
    snap = {
        "schema_version": "origlyph.tolerance.workspace.v99",
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_v5_acceptance_state_missing_key_rejected() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
        "acceptance_state": {
            "decision": "approved",
            "authority_reference": "AUTH",
            "decision_reference": "DEC",
            # missing: handoff_id
        },
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


# ---------------------------------------------------------------------------
# Deterministic canonical JSON
# ---------------------------------------------------------------------------


def test_canonical_json_deterministic() -> None:
    state = _v5_state(_acceptance())
    snap1 = workspace_state_to_snapshot(state)
    snap2 = workspace_state_to_snapshot(state)
    j1 = json.dumps(snap1, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(snap2, sort_keys=True, separators=(",", ":"))
    assert j1 == j2


def test_canonical_json_same_state_same_fingerprint() -> None:
    acc = _acceptance()
    s1 = _v5_state(acc)
    s2 = _v5_state(acc)
    assert _fp(s1) == _fp(s2)


# ---------------------------------------------------------------------------
# Project identity — fingerprint rotation
# ---------------------------------------------------------------------------


def test_project_id_stable_identical_acceptance_state() -> None:
    acc = _acceptance()
    s1 = _v5_state(acc)
    s2 = _v5_state(acc)
    assert _fp(s1) == _fp(s2)


def test_project_id_rotates_on_decision_change() -> None:
    s1 = _v5_state(_acceptance(decision=AuditAcceptanceDecision.APPROVED))
    s2 = _v5_state(_acceptance(decision=AuditAcceptanceDecision.REJECTED))
    assert _fp(s1) != _fp(s2)


def test_project_id_rotates_on_authority_reference_change() -> None:
    s1 = _v5_state(_acceptance(authority="AUTH-A"))
    s2 = _v5_state(_acceptance(authority="AUTH-B"))
    assert _fp(s1) != _fp(s2)


def test_project_id_rotates_on_decision_reference_change() -> None:
    s1 = _v5_state(_acceptance(reference="DEC-A"))
    s2 = _v5_state(_acceptance(reference="DEC-B"))
    assert _fp(s1) != _fp(s2)


def test_project_id_rotates_when_acceptance_cleared() -> None:
    s1 = _v5_state(_acceptance())
    s2 = _v5_state(None)
    assert _fp(s1) != _fp(s2)


def test_project_id_rotates_on_handoff_id_change() -> None:
    s1 = _v5_state(_acceptance(handoff_id=_SHA))
    s2 = _v5_state(_acceptance(handoff_id=_SHA2))
    assert _fp(s1) != _fp(s2)


# ---------------------------------------------------------------------------
# V4 round-trip unaffected by v5 additions
# ---------------------------------------------------------------------------


def test_v4_round_trip_unaffected() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
    }
    state = workspace_state_from_snapshot(snap)
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    assert state.acceptance_state is None
    restored_snap = workspace_state_to_snapshot(state)
    assert "acceptance_state" not in restored_snap
    assert restored_snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4


# ---------------------------------------------------------------------------
# Controller: set/clear acceptance_state
# ---------------------------------------------------------------------------


def test_controller_initial_acceptance_state_none() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    assert ctrl.acceptance_state is None


def test_controller_set_acceptance_state_upgrades_schema_to_v5() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance())
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5


def test_controller_set_acceptance_state_stores_value() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    acc = _acceptance()
    ctrl.set_acceptance_state(acc)
    assert ctrl.acceptance_state == acc


def test_controller_clear_acceptance_state() -> None:
    ctrl = _ctrl_v5()
    ctrl.clear_acceptance_state()
    assert ctrl.acceptance_state is None
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5


def test_controller_clear_keeps_v5_schema() -> None:
    ctrl = _ctrl_v5()
    ctrl.clear_acceptance_state()
    assert ctrl.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5


def test_controller_set_acceptance_noop_for_same_value() -> None:
    acc = _acceptance()
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(acc)
    fp_before = ctrl.configuration_fingerprint()
    ctrl.set_acceptance_state(acc)
    fp_after = ctrl.configuration_fingerprint()
    assert fp_before == fp_after


def test_controller_set_acceptance_rejects_wrong_type() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="acceptance_state"):
        ctrl.set_acceptance_state("not-a-state")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Stale policy — acceptance_state not cleared by upstream changes
# ---------------------------------------------------------------------------


def test_acceptance_state_not_cleared_by_set_chain_name() -> None:
    ctrl = _ctrl_v5()
    ctrl.set_chain_name("Other chain")
    assert ctrl.acceptance_state is not None


def test_acceptance_state_not_cleared_by_set_analysis_mode() -> None:
    ctrl = _ctrl_v5()
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.acceptance_state is not None


def test_acceptance_state_not_cleared_by_set_specification() -> None:
    ctrl = _ctrl_v5()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    assert ctrl.acceptance_state is not None


def test_acceptance_state_not_cleared_by_add_contributor() -> None:
    ctrl = _ctrl_v5()
    ctrl.add_contributor(
        identifier="X",
        name="Part X",
        nominal=0.0,
        tolerance=0.1,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.acceptance_state is not None


def test_acceptance_state_not_cleared_by_set_allocation_plan() -> None:
    ctrl = _ctrl_v5()
    ctrl.add_contributor(
        identifier="X",
        name="Part X",
        nominal=0.0,
        tolerance=0.1,
        direction="forward",
        tolerance_model="symmetric",
    )
    plan = WorkspaceAllocationPlan(
        allowed_budget=0.5,
        entries=(WorkspaceAllocationEntry(contributor_id="X", allocated_span=0.5),),
    )
    ctrl.set_allocation_plan(plan)
    assert ctrl.acceptance_state is not None


# ---------------------------------------------------------------------------
# Save / open contract
# ---------------------------------------------------------------------------


def test_save_open_round_trip_preserves_acceptance_state(
    tmp_path: Path,
) -> None:
    ctrl = _ctrl_v5()
    acc = ctrl.acceptance_state
    assert acc is not None
    save_path = tmp_path / "project.origlyph.json"
    ctrl.save_project(save_path)
    loaded = ToleranceWorkspaceController.open_project(save_path)
    assert loaded.acceptance_state is not None
    assert loaded.acceptance_state.decision == acc.decision
    assert loaded.acceptance_state.authority_reference == acc.authority_reference
    assert loaded.acceptance_state.decision_reference == acc.decision_reference
    assert loaded.acceptance_state.handoff_id == acc.handoff_id


def test_save_open_round_trip_decision_exact(tmp_path: Path) -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance(decision=AuditAcceptanceDecision.REJECTED))
    ctrl.save_project(tmp_path / "p.origlyph.json")
    loaded = ToleranceWorkspaceController.open_project(tmp_path / "p.origlyph.json")
    assert loaded.acceptance_state is not None
    assert loaded.acceptance_state.decision is AuditAcceptanceDecision.REJECTED


def test_save_open_round_trip_authority_reference_exact(tmp_path: Path) -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance(authority="AUTHORITY-EXACT-REF"))
    ctrl.save_project(tmp_path / "p.origlyph.json")
    loaded = ToleranceWorkspaceController.open_project(tmp_path / "p.origlyph.json")
    assert loaded.acceptance_state is not None
    assert loaded.acceptance_state.authority_reference == "AUTHORITY-EXACT-REF"


def test_save_open_round_trip_decision_reference_exact(tmp_path: Path) -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance(reference="DECISION-EXACT-REF"))
    ctrl.save_project(tmp_path / "p.origlyph.json")
    loaded = ToleranceWorkspaceController.open_project(tmp_path / "p.origlyph.json")
    assert loaded.acceptance_state is not None
    assert loaded.acceptance_state.decision_reference == "DECISION-EXACT-REF"


def test_save_open_round_trip_null_acceptance(tmp_path: Path) -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    ctrl.set_acceptance_state(_acceptance())
    ctrl.clear_acceptance_state()
    ctrl.save_project(tmp_path / "p.origlyph.json")
    loaded = ToleranceWorkspaceController.open_project(tmp_path / "p.origlyph.json")
    assert loaded.acceptance_state is None


# ---------------------------------------------------------------------------
# No fabricated acceptance state
# ---------------------------------------------------------------------------


def test_no_fabricated_acceptance_on_new_controller() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="C", analysis_mode=AnalysisMode.WORST_CASE
    )
    assert ctrl.acceptance_state is None


def test_no_fabricated_acceptance_on_v4_load(tmp_path: Path) -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
        "chain_name": "C",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
    }
    state = workspace_state_from_snapshot(snap)
    ctrl = ToleranceWorkspaceController.from_state(state)
    assert ctrl.acceptance_state is None


# ---------------------------------------------------------------------------
# Derived objects not persisted
# ---------------------------------------------------------------------------


def test_derived_handoff_not_in_snapshot() -> None:
    state = _v5_state(_acceptance())
    snapshot = workspace_state_to_snapshot(state)
    assert "acceptance_handoff" not in snapshot
    assert "handoff_package" not in snapshot


def test_derived_validated_record_not_in_snapshot() -> None:
    state = _v5_state(_acceptance())
    snapshot = workspace_state_to_snapshot(state)
    assert "validated_acceptance_record" not in snapshot
    assert "acceptance_record_id" not in snapshot


# ---------------------------------------------------------------------------
# Legacy schema compatibility
# ---------------------------------------------------------------------------


def test_legacy_v1_schema_still_compatible() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION,
        "chain_name": "LegacyChain",
        "analysis_mode": "worst_case",
        "contributors": [],
    }
    state = workspace_state_from_snapshot(snap)
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    assert state.acceptance_state is None


def test_legacy_v2_schema_still_compatible() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
        "chain_name": "LegacyChain",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
    }
    state = workspace_state_from_snapshot(snap)
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert state.acceptance_state is None


def test_legacy_v3_schema_still_compatible() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3,
        "chain_name": "LegacyChain",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
    }
    state = workspace_state_from_snapshot(snap)
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    assert state.acceptance_state is None


def test_legacy_v4_schema_still_compatible() -> None:
    snap = {
        "schema_version": TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4,
        "chain_name": "LegacyChain",
        "analysis_mode": "worst_case",
        "contributors": [],
        "specification": None,
        "allocation_plan": None,
        "statistical_allocation_plan": None,
    }
    state = workspace_state_from_snapshot(snap)
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    assert state.acceptance_state is None


# ---------------------------------------------------------------------------
# Security boundary — in tests as assertions about what is NOT stored
# ---------------------------------------------------------------------------


def test_authority_reference_is_not_authenticated_identity() -> None:
    # authority_reference is an opaque string; Origlyph does not authenticate it.
    # Test confirms any non-empty canonical string is accepted.
    acc = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.APPROVED,
        authority_reference="ANY-REFERENCE-STRING",
        decision_reference="DEC-001",
        handoff_id=_SHA,
    )
    assert acc.authority_reference == "ANY-REFERENCE-STRING"


def test_decision_reference_is_not_digital_signature() -> None:
    # decision_reference is an opaque string; Origlyph does not verify signatures.
    acc = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.APPROVED,
        authority_reference="AUTH-001",
        decision_reference="ANY-REFERENCE-STRING",
        handoff_id=_SHA,
    )
    assert acc.decision_reference == "ANY-REFERENCE-STRING"
