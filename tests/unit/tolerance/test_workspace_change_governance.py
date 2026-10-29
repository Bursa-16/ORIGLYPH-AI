"""Unit tests for change disposition and approval readiness workspace surface (Stage
20F)."""

from __future__ import annotations

import json

import pytest

from origlyph.tolerance.approval_readiness import (
    AuditApprovalReadinessStatus,
    evaluate_audit_approval_readiness,
)
from origlyph.tolerance.audit import (
    ToleranceDecisionAuditPackage,
)
from origlyph.tolerance.change_disposition import (
    AuditChangeDisposition,
    determine_audit_change_disposition,
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


def _make_ctrl_with_change_impact() -> ToleranceWorkspaceController:
    """Return a controller with a full chain through change impact cached."""
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
    ctrl.run_decision_report()
    ctrl.run_audit_package()
    # Load an identical package as comparison → IDENTICAL comparison
    pkg = ctrl.last_audit_package
    assert pkg is not None
    import tempfile
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            f,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    return ctrl


def _make_ctrl_with_audit_package() -> ToleranceWorkspaceController:
    """Return a controller with an audit package but no comparison/impact."""
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
    ctrl.run_decision_report()
    ctrl.run_audit_package()
    return ctrl


def _make_ctrl_no_audit_package() -> ToleranceWorkspaceController:
    """Return a controller without an audit package."""
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
    ctrl.run_decision_report()
    return ctrl


def _write_package_json(
    package: ToleranceDecisionAuditPackage, path: object
) -> None:
    data = json.dumps(
        package.as_dict(),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    path.write_text(data, encoding="utf-8")  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_change_disposition_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.last_change_disposition is None


def test_initial_approval_readiness_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.last_approval_readiness is None


def test_session_initial_change_disposition_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.last_change_disposition is None


def test_session_initial_approval_readiness_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.last_approval_readiness is None


def test_session_change_disposition_status_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.change_disposition_status_text == "NOT DETERMINED"


def test_session_approval_readiness_status_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.approval_readiness_status_text == "NOT EVALUATED"


def test_session_change_disposition_reasons_rows_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.change_disposition_reasons_rows() == []


def test_session_approval_readiness_reasons_rows_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.approval_readiness_reasons_rows() == []


# ---------------------------------------------------------------------------
# Fail-closed: missing prerequisites
# ---------------------------------------------------------------------------


def test_run_change_disposition_fails_without_change_impact() -> None:
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Evaluate Change Impact first"
    ):
        ctrl.run_change_disposition()


def test_run_approval_readiness_fails_without_change_disposition() -> None:
    ctrl = _make_ctrl_with_change_impact()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Determine Change Disposition first"
    ):
        ctrl.run_approval_readiness()


def test_session_run_change_disposition_fails_without_impact() -> None:
    ctrl = _make_ctrl_with_audit_package()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Evaluate Change Impact first"
    ):
        session.run_change_disposition()


def test_session_run_approval_readiness_fails_without_disposition() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Determine Change Disposition first"
    ):
        session.run_approval_readiness()


# ---------------------------------------------------------------------------
# Exact Stage 15R delegation
# ---------------------------------------------------------------------------


def test_run_change_disposition_delegates_to_stage15r() -> None:
    ctrl = _make_ctrl_with_change_impact()
    impact = ctrl.last_change_impact
    assert impact is not None
    expected = determine_audit_change_disposition(impact)
    result = ctrl.run_change_disposition()
    assert result == expected


def test_run_change_disposition_caches_result() -> None:
    ctrl = _make_ctrl_with_change_impact()
    result = ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is result


def test_session_run_change_disposition_delegates() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    impact = ctrl.last_change_impact
    assert impact is not None
    expected = determine_audit_change_disposition(impact)
    result = session.run_change_disposition()
    assert result == expected


def test_session_run_change_disposition_updates_status_text() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    status = session.change_disposition_status_text
    assert status != "NOT DETERMINED"
    assert status == session.last_change_disposition.disposition.value.upper()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Exact Stage 15S delegation
# ---------------------------------------------------------------------------


def test_run_approval_readiness_delegates_to_stage15s() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    disposition = ctrl.last_change_disposition
    assert disposition is not None
    expected = evaluate_audit_approval_readiness(disposition)
    result = ctrl.run_approval_readiness()
    assert result == expected


def test_run_approval_readiness_caches_result() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    result = ctrl.run_approval_readiness()
    assert ctrl.last_approval_readiness is result


def test_session_run_approval_readiness_delegates() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    disposition = ctrl.last_change_disposition
    assert disposition is not None
    expected = evaluate_audit_approval_readiness(disposition)
    result = session.run_approval_readiness()
    assert result == expected


def test_session_run_approval_readiness_updates_status_text() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    session.run_approval_readiness()
    status = session.approval_readiness_status_text
    assert status != "NOT EVALUATED"
    assert status == session.last_approval_readiness.status.value.upper()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Deterministic behavior
# ---------------------------------------------------------------------------


def test_run_change_disposition_is_deterministic() -> None:
    ctrl = _make_ctrl_with_change_impact()
    r1 = ctrl.run_change_disposition()
    r2 = ctrl.run_change_disposition()
    assert r1 == r2


def test_run_approval_readiness_is_deterministic() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    r1 = ctrl.run_approval_readiness()
    r2 = ctrl.run_approval_readiness()
    assert r1 == r2


# ---------------------------------------------------------------------------
# Result mapping: session presentation methods
# ---------------------------------------------------------------------------


def test_change_disposition_reasons_rows_returns_list_of_dicts() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    rows = session.change_disposition_reasons_rows()
    assert isinstance(rows, list)


def test_change_disposition_reasons_rows_keys() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    rows = session.change_disposition_reasons_rows()
    for row in rows:
        assert "disposition" in row
        assert "code" in row
        assert "impact" in row
        assert "impact_reason" in row
        assert "change_code" in row


def test_approval_readiness_reasons_rows_returns_list_of_dicts() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    session.run_approval_readiness()
    rows = session.approval_readiness_reasons_rows()
    assert isinstance(rows, list)


def test_approval_readiness_reasons_rows_keys() -> None:
    ctrl = _make_ctrl_with_change_impact()
    session = WorkspaceSession(ctrl)
    session.run_change_disposition()
    session.run_approval_readiness()
    rows = session.approval_readiness_reasons_rows()
    for row in rows:
        assert "status" in row
        assert "code" in row
        assert "source_disposition" in row
        assert "source_code" in row


def test_identical_comparison_produces_accept_disposition() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    result = ctrl.last_change_disposition
    assert result is not None
    assert result.disposition is AuditChangeDisposition.ACCEPT


def test_accept_disposition_produces_ready_approval() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    result = ctrl.last_approval_readiness
    assert result is not None
    assert result.status is AuditApprovalReadinessStatus.READY


def test_approval_readiness_is_ready_flag() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    result = ctrl.last_approval_readiness
    assert result is not None
    # READY → is_ready=True
    assert result.is_ready == (result.status is AuditApprovalReadinessStatus.READY)


# ---------------------------------------------------------------------------
# Stale clearing on upstream change (change impact replaced)
# ---------------------------------------------------------------------------


def test_disposition_cleared_on_new_change_impact(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    # Re-run change impact → disposition must be cleared
    ctrl.run_change_impact()
    assert ctrl.last_change_disposition is None


def test_readiness_cleared_on_new_change_impact(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    assert ctrl.last_approval_readiness is not None
    ctrl.run_change_impact()
    assert ctrl.last_approval_readiness is None


def test_readiness_cleared_on_new_change_disposition(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    assert ctrl.last_approval_readiness is not None
    ctrl.run_change_disposition()
    assert ctrl.last_approval_readiness is None


def test_disposition_cleared_on_new_audit_comparison(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.run_audit_comparison()
    assert ctrl.last_change_disposition is None


def test_disposition_cleared_on_new_audit_package(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.run_audit_package()
    assert ctrl.last_change_disposition is None


def test_disposition_cleared_on_load_comparison_package(tmp_path) -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    assert ctrl.last_change_disposition is None


def test_disposition_cleared_on_set_chain_name() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.set_chain_name("New name")
    assert ctrl.last_change_disposition is None


def test_disposition_cleared_on_set_analysis_mode() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.last_change_disposition is None


def test_readiness_cleared_on_set_chain_name() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    assert ctrl.last_approval_readiness is not None
    ctrl.set_chain_name("New name 2")
    assert ctrl.last_approval_readiness is None


def test_disposition_cleared_on_run_analysis() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.run_analysis()
    assert ctrl.last_change_disposition is None


def test_disposition_cleared_on_evaluate_decision() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    ctrl.evaluate_decision()
    assert ctrl.last_change_disposition is None


# ---------------------------------------------------------------------------
# Feature isolation
# ---------------------------------------------------------------------------


def test_change_disposition_does_not_affect_analysis() -> None:
    ctrl = _make_ctrl_with_change_impact()
    analysis_before = ctrl.last_result
    ctrl.run_change_disposition()
    assert ctrl.last_result is analysis_before


def test_change_disposition_does_not_affect_decision() -> None:
    ctrl = _make_ctrl_with_change_impact()
    decision_before = ctrl.last_decision
    ctrl.run_change_disposition()
    assert ctrl.last_decision is decision_before


def test_approval_readiness_does_not_affect_change_impact() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    impact_before = ctrl.last_change_impact
    ctrl.run_approval_readiness()
    assert ctrl.last_change_impact is impact_before


def test_approval_readiness_does_not_affect_change_disposition() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    disposition_before = ctrl.last_change_disposition
    ctrl.run_approval_readiness()
    assert ctrl.last_change_disposition is disposition_before


def test_change_disposition_does_not_affect_audit_package() -> None:
    ctrl = _make_ctrl_with_change_impact()
    pkg_before = ctrl.last_audit_package
    ctrl.run_change_disposition()
    assert ctrl.last_audit_package is pkg_before


def test_approval_readiness_does_not_affect_audit_package() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    pkg_before = ctrl.last_audit_package
    ctrl.run_approval_readiness()
    assert ctrl.last_audit_package is pkg_before


# ---------------------------------------------------------------------------
# No hidden generation or manual recomputation
# ---------------------------------------------------------------------------


def test_change_disposition_does_not_rerun_impact() -> None:
    """run_change_disposition() must not mutate _last_change_impact."""
    ctrl = _make_ctrl_with_change_impact()
    impact_before = ctrl.last_change_impact
    ctrl.run_change_disposition()
    assert ctrl.last_change_impact is impact_before


def test_approval_readiness_does_not_rerun_disposition() -> None:
    """run_approval_readiness() must not mutate _last_change_disposition."""
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    disposition_before = ctrl.last_change_disposition
    ctrl.run_approval_readiness()
    assert ctrl.last_change_disposition is disposition_before


# ---------------------------------------------------------------------------
# from_state clears governance fields
# ---------------------------------------------------------------------------


def test_from_state_clears_change_disposition() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    assert ctrl.last_change_disposition is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.last_change_disposition is None


def test_from_state_clears_approval_readiness() -> None:
    ctrl = _make_ctrl_with_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    assert ctrl.last_approval_readiness is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.last_approval_readiness is None


# ---------------------------------------------------------------------------
# project_id unchanged
# ---------------------------------------------------------------------------


def test_project_id_unchanged_by_governance_run() -> None:
    ctrl = _make_ctrl_with_change_impact()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    assert ctrl.configuration_fingerprint() == fp_before
