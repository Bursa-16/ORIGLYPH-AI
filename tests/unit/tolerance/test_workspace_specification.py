"""Stage 17A tests — WorkspaceSpecification contract, v2 snapshot, controller
integration, persistence round-trip, backward compatibility, and view session."""

from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.project import (
    TOLERANCE_WORKSPACE_EXTENSION_KEY,
    build_project_with_tolerance_workspace,
    load_project,
    workspace_state_from_project,
)
from origlyph.tolerance import (
    TOLERANCE_WORKSPACE_SCHEMA_VERSION,
    TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2,
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
    WorkspaceState,
    workspace_configuration_fingerprint,
    workspace_state_from_snapshot,
    workspace_state_to_snapshot,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _controller() -> ToleranceWorkspaceController:
    c = ToleranceWorkspaceController.empty(
        chain_name="cover-plate", analysis_mode=AnalysisMode.WORST_CASE
    )
    c.add_contributor(
        identifier="a", name="Face A", nominal=10.0, tolerance=0.1,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    c.add_contributor(
        identifier="b", name="Face B", nominal=4.0, tolerance=0.2,
        direction=StackDirection.INVERSE, tolerance_model="symmetric",
    )
    return c


def _v1_snap(c: ToleranceWorkspaceController) -> dict:
    snap = workspace_state_to_snapshot(c.state)
    assert snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    return snap


# ──────────────────────────────────────────────────────────────────────────────
# A — WorkspaceSpecification model
# ──────────────────────────────────────────────────────────────────────────────

def test_spec_valid_wc_span_only() -> None:
    spec = WorkspaceSpecification(allowed_worst_case_span=1.0)
    assert spec.allowed_worst_case_span == 1.0
    assert spec.allowed_combined_sigma is None


def test_spec_valid_sigma_only() -> None:
    spec = WorkspaceSpecification(allowed_combined_sigma=0.05)
    assert spec.allowed_worst_case_span is None
    assert spec.allowed_combined_sigma == pytest.approx(0.05)


def test_spec_valid_both_limits() -> None:
    spec = WorkspaceSpecification(
        allowed_worst_case_span=2.0, allowed_combined_sigma=0.33
    )
    assert spec.allowed_worst_case_span == pytest.approx(2.0)
    assert spec.allowed_combined_sigma == pytest.approx(0.33)


def test_spec_no_limits_produces_none_fields() -> None:
    spec = WorkspaceSpecification()
    assert spec.allowed_worst_case_span is None
    assert spec.allowed_combined_sigma is None


def test_spec_span_nan_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceSpecification(allowed_worst_case_span=float("nan"))


def test_spec_span_inf_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceSpecification(allowed_worst_case_span=float("inf"))


def test_spec_sigma_nan_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceSpecification(allowed_combined_sigma=float("nan"))


def test_spec_sigma_neg_inf_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        WorkspaceSpecification(allowed_combined_sigma=float("-inf"))


def test_spec_span_zero_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceSpecification(allowed_worst_case_span=0.0)


def test_spec_span_negative_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceSpecification(allowed_worst_case_span=-0.5)


def test_spec_sigma_zero_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceSpecification(allowed_combined_sigma=0.0)


def test_spec_sigma_negative_rejected() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="strictly positive"):
        WorkspaceSpecification(allowed_combined_sigma=-1.0)


def test_spec_as_dict_roundtrip() -> None:
    spec = WorkspaceSpecification(
        allowed_worst_case_span=1.5, allowed_combined_sigma=0.3
    )
    d = spec.as_dict()
    assert d == {"allowed_worst_case_span": 1.5, "allowed_combined_sigma": 0.3}


def test_spec_as_dict_with_none_fields() -> None:
    spec = WorkspaceSpecification(allowed_worst_case_span=1.0)
    d = spec.as_dict()
    assert d == {"allowed_worst_case_span": 1.0, "allowed_combined_sigma": None}


def test_spec_immutable() -> None:
    spec = WorkspaceSpecification(allowed_worst_case_span=1.0)
    with pytest.raises((AttributeError, TypeError)):
        spec.allowed_worst_case_span = 2.0  # type: ignore[misc]


def test_spec_equality() -> None:
    a = WorkspaceSpecification(allowed_worst_case_span=1.0)
    b = WorkspaceSpecification(allowed_worst_case_span=1.0)
    c = WorkspaceSpecification(allowed_worst_case_span=2.0)
    assert a == b
    assert a != c


# ──────────────────────────────────────────────────────────────────────────────
# B — Workspace snapshot v2
# ──────────────────────────────────────────────────────────────────────────────

def test_v2_snapshot_round_trip_with_specification() -> None:
    c = _controller()
    spec = WorkspaceSpecification(
        allowed_worst_case_span=0.6, allowed_combined_sigma=0.2
    )
    c.set_specification(spec)
    snap = workspace_state_to_snapshot(c.state)

    assert snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert "specification" in snap
    spec_dict = snap["specification"]
    assert isinstance(spec_dict, dict)
    assert spec_dict["allowed_worst_case_span"] == pytest.approx(0.6)
    assert spec_dict["allowed_combined_sigma"] == pytest.approx(0.2)

    restored = workspace_state_from_snapshot(snap)
    assert restored.specification is not None
    assert restored.specification.allowed_worst_case_span == pytest.approx(0.6)
    assert restored.specification.allowed_combined_sigma == pytest.approx(0.2)


def test_v2_snapshot_with_null_specification() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    c.set_specification(None)  # clear — state stays v2
    snap = workspace_state_to_snapshot(c.state)

    assert snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert snap["specification"] is None

    restored = workspace_state_from_snapshot(snap)
    assert restored.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert restored.specification is None


def test_v2_identity_stable_on_noop_reserialization() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    fp1 = workspace_configuration_fingerprint(c.state)
    fp2 = workspace_configuration_fingerprint(c.state)
    assert fp1 == fp2


def test_specification_change_rotates_fingerprint() -> None:
    c = _controller()
    fp_no_spec = workspace_configuration_fingerprint(c.state)
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    fp_with_spec = workspace_configuration_fingerprint(c.state)
    assert fp_with_spec != fp_no_spec


def test_specification_value_change_rotates_fingerprint() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    fp1 = workspace_configuration_fingerprint(c.state)
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    fp2 = workspace_configuration_fingerprint(c.state)
    assert fp1 != fp2


def test_specification_change_rotates_project_id() -> None:
    c = _controller()
    p1 = build_project_with_tolerance_workspace(c.state)
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    p2 = build_project_with_tolerance_workspace(c.state)
    assert p1.project_id != p2.project_id


def test_unknown_v2_key_rejected() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    snap = workspace_state_to_snapshot(c.state)
    snap["extra_key"] = "bad"
    with pytest.raises(InvalidToleranceWorkspaceError, match="unknown"):
        workspace_state_from_snapshot(snap)


def test_malformed_specification_dict_rejected() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    snap = workspace_state_to_snapshot(c.state)
    snap["specification"] = {"allowed_worst_case_span": 1.0}  # missing sigma key
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_specification_not_dict_rejected() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    snap = workspace_state_to_snapshot(c.state)
    snap["specification"] = "bad"
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_specification_negative_value_rejected_on_load() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    snap = workspace_state_to_snapshot(c.state)
    snap["specification"] = {
        "allowed_worst_case_span": -1.0,
        "allowed_combined_sigma": None,
    }
    with pytest.raises(InvalidToleranceWorkspaceError):
        workspace_state_from_snapshot(snap)


def test_unknown_schema_version_rejected() -> None:
    c = _controller()
    snap = workspace_state_to_snapshot(c.state)
    snap["schema_version"] = "origlyph.tolerance.workspace.v99"
    with pytest.raises(InvalidToleranceWorkspaceError, match="unsupported"):
        workspace_state_from_snapshot(snap)


# ──────────────────────────────────────────────────────────────────────────────
# C — Backward compatibility (v1)
# ──────────────────────────────────────────────────────────────────────────────

def test_v1_snapshot_loads_unchanged() -> None:
    c = _controller()
    snap = _v1_snap(c)
    restored = workspace_state_from_snapshot(snap)
    assert restored.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    assert restored.specification is None
    assert [i.identifier for i in restored.contributors] == ["a", "b"]


def test_v1_workspace_produces_no_specification() -> None:
    c = _controller()
    assert c.specification is None
    assert c.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION


def test_v1_no_fabricated_defaults() -> None:
    c = _controller()
    snap = _v1_snap(c)
    state = workspace_state_from_snapshot(snap)
    assert state.specification is None


def test_v1_snapshot_rejects_specification_key() -> None:
    c = _controller()
    snap = _v1_snap(c)
    snap["specification"] = {
        "allowed_worst_case_span": 1.0,
        "allowed_combined_sigma": None,
    }
    with pytest.raises(InvalidToleranceWorkspaceError, match="unknown"):
        workspace_state_from_snapshot(snap)


def test_v1_state_rejects_specification_field() -> None:
    with pytest.raises(InvalidToleranceWorkspaceError, match="v1 does not support"):
        WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION,
            chain_name="chain",
            analysis_mode=AnalysisMode.WORST_CASE,
            contributors=(),
            specification=WorkspaceSpecification(allowed_worst_case_span=1.0),
        )


def test_v1_project_round_trip_unchanged(tmp_path: Path) -> None:
    c = _controller()
    target = c.save_project(tmp_path / "v1.origlyph.json")
    p1 = load_project(target)
    reopened = ToleranceWorkspaceController.open_project(target)
    assert reopened.specification is None
    assert reopened.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    target2 = reopened.save_project(tmp_path / "v1b.origlyph.json")
    p2 = load_project(target2)
    assert p1.project_id == p2.project_id


def test_v1_spec_key_absent_from_extension() -> None:
    c = _controller()
    p = build_project_with_tolerance_workspace(c.state)
    ext = p.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
    assert "specification" not in ext


# ──────────────────────────────────────────────────────────────────────────────
# D — Controller integration
# ──────────────────────────────────────────────────────────────────────────────

def test_controller_set_specification_stores_value() -> None:
    c = _controller()
    spec = WorkspaceSpecification(allowed_worst_case_span=0.6)
    c.set_specification(spec)
    assert c.specification == spec


def test_controller_same_specification_is_noop() -> None:
    c = _controller()
    spec = WorkspaceSpecification(allowed_worst_case_span=0.6)
    c.set_specification(spec)
    result = c.run_analysis()
    same = WorkspaceSpecification(allowed_worst_case_span=0.6)
    c.set_specification(same)
    assert c.last_result is result


def test_controller_set_specification_none_on_v1_is_noop() -> None:
    c = _controller()
    result = c.run_analysis()
    c.set_specification(None)
    assert c.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    assert c.last_result is result


def test_controller_changed_specification_invalidates_result() -> None:
    c = _controller()
    c.run_analysis()
    assert c.last_result is not None
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    assert c.last_result is None


def test_controller_clearing_specification_on_v2_invalidates_result() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    c.run_analysis()
    c.set_specification(None)
    assert c.last_result is None


def test_controller_clearing_specification_on_v2_stays_v2() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    c.set_specification(None)
    assert c.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert c.specification is None


def test_controller_invalid_specification_type_rejected() -> None:
    c = _controller()
    with pytest.raises(InvalidToleranceWorkspaceError, match="specification must be"):
        c.set_specification("bad")  # type: ignore[arg-type]


def test_controller_setting_specification_upgrades_to_v2() -> None:
    c = _controller()
    assert c.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    assert c.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2


def test_controller_no_auto_analysis_on_set_specification() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    assert c.last_result is None


def test_from_state_preserves_v2_with_null_spec() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    c.set_specification(None)
    state = c.state
    assert state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    rebuilt = ToleranceWorkspaceController.from_state(state)
    assert rebuilt.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert rebuilt.specification is None


# ──────────────────────────────────────────────────────────────────────────────
# B (persistence) — full project round-trip with v2
# ──────────────────────────────────────────────────────────────────────────────

def test_v2_project_save_load_roundtrip(tmp_path: Path) -> None:
    c = _controller()
    spec = WorkspaceSpecification(
        allowed_worst_case_span=0.6, allowed_combined_sigma=0.25
    )
    c.set_specification(spec)
    c.run_analysis()
    target = c.save_project(tmp_path / "v2.origlyph.json")
    reopened = ToleranceWorkspaceController.open_project(target)
    assert reopened.state.schema_version == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert reopened.specification is not None
    assert reopened.specification.allowed_worst_case_span == pytest.approx(0.6)
    assert reopened.specification.allowed_combined_sigma == pytest.approx(0.25)
    assert [i.identifier for i in reopened.contributors] == ["a", "b"]


def test_v2_no_numeric_drift(tmp_path: Path) -> None:
    c = _controller()
    c.set_specification(
        WorkspaceSpecification(allowed_worst_case_span=1.23456789012345)
    )
    target = c.save_project(tmp_path / "drift.origlyph.json")
    reopened = ToleranceWorkspaceController.open_project(target)
    assert reopened.specification is not None
    assert reopened.specification.allowed_worst_case_span == pytest.approx(
        1.23456789012345, rel=1e-14
    )


def test_v2_noop_resave_preserves_project_id() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    p1 = build_project_with_tolerance_workspace(c.state)
    state = workspace_state_from_project(p1)
    c2 = ToleranceWorkspaceController.from_state(state)
    p2 = build_project_with_tolerance_workspace(c2.state)
    assert p1.project_id == p2.project_id


def test_v2_extension_carries_specification() -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    p = build_project_with_tolerance_workspace(c.state)
    ext = p.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
    assert ext["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    assert ext["specification"]["allowed_worst_case_span"] == pytest.approx(0.6)


def test_contributor_order_preserved_in_v2(tmp_path: Path) -> None:
    c = _controller()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.6))
    target = c.save_project(tmp_path / "order.origlyph.json")
    reopened = ToleranceWorkspaceController.open_project(target)
    assert [i.identifier for i in reopened.contributors] == ["a", "b"]


# ──────────────────────────────────────────────────────────────────────────────
# E — View / session
# ──────────────────────────────────────────────────────────────────────────────

def test_session_blank_field_means_unspecified_not_zero() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = ""
    session.allowed_sigma = ""
    session.sync_specification()
    assert session.controller.specification is None


def test_session_valid_limit_sync() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "0.6"
    session.allowed_sigma = ""
    session.sync_specification()
    spec = session.controller.specification
    assert spec is not None
    assert spec.allowed_worst_case_span == pytest.approx(0.6)
    assert spec.allowed_combined_sigma is None


def test_session_both_limits_sync() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "1.0"
    session.allowed_sigma = "0.25"
    session.sync_specification()
    spec = session.controller.specification
    assert spec is not None
    assert spec.allowed_worst_case_span == pytest.approx(1.0)
    assert spec.allowed_combined_sigma == pytest.approx(0.25)


def test_session_invalid_value_surfaced() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "not-a-number"
    with pytest.raises(InvalidToleranceWorkspaceError, match="enter a valid number"):
        session.sync_specification()


def test_session_negative_value_surfaced() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "-1.0"
    with pytest.raises(InvalidToleranceWorkspaceError, match="greater than zero"):
        session.sync_specification()


def test_session_zero_value_surfaced() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "0"
    with pytest.raises(InvalidToleranceWorkspaceError, match="greater than zero"):
        session.sync_specification()


def test_session_inf_value_surfaced() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "inf"
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        session.sync_specification()


def test_session_no_automatic_analysis_on_sync_specification() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "0.6"
    session.sync_specification()
    assert session.controller.last_result is None


def test_session_no_pass_fail_in_result_text() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "0.6"
    session.sync_specification()
    session.run_analysis()
    text = session.result_text
    for verdict in ("PASS", "FAIL", "MARGINAL", "INCOMPLETE"):
        assert verdict not in text


def test_session_initialises_spec_fields_from_controller() -> None:
    c = _controller()
    c.set_specification(
        WorkspaceSpecification(allowed_worst_case_span=0.5, allowed_combined_sigma=0.2)
    )
    session = WorkspaceSession(c)
    assert session.allowed_wc_span == "0.5"
    assert session.allowed_sigma == "0.2"


def test_session_initialises_empty_fields_when_no_spec() -> None:
    session = WorkspaceSession(_controller())
    assert session.allowed_wc_span == ""
    assert session.allowed_sigma == ""


def test_session_same_spec_sync_is_noop() -> None:
    session = WorkspaceSession(_controller())
    session.allowed_wc_span = "0.6"
    session.sync_specification()
    session.run_analysis()
    result = session.controller.last_result
    session.allowed_wc_span = "0.6"
    session.sync_specification()
    assert session.controller.last_result is result
