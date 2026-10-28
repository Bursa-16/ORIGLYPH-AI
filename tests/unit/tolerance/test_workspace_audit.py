"""Unit tests for audit integrity and audit package workspace surface (Stage 20D)."""

from __future__ import annotations

import pytest

from origlyph.tolerance.audit import (
    AUDIT_PACKAGE_SCHEMA_VERSION,
    ReplayabilityStatus,
    ToleranceDecisionAuditPackage,
    build_decision_audit_package,
)
from origlyph.tolerance.integrity import (
    AuditIntegrityResult,
    AuditIntegrityStatus,
    validate_decision_report_integrity,
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


def _make_ctrl_with_report() -> ToleranceWorkspaceController:
    """Return a controller with full decision → evidence → report chain cached."""
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


def _make_ctrl_no_report() -> ToleranceWorkspaceController:
    """Return a controller with decision cached but no report."""
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
    return ctrl


def _make_ctrl_no_decision() -> ToleranceWorkspaceController:
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
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    ctrl.run_analysis()
    return ctrl


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_audit_integrity_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    assert ctrl.last_audit_integrity is None


def test_initial_audit_package_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    assert ctrl.last_audit_package is None


def test_session_initial_audit_integrity_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.last_audit_integrity is None


def test_session_initial_audit_package_is_none() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.last_audit_package is None


def test_session_audit_integrity_status_text_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.audit_integrity_status_text == "NOT GENERATED"


def test_session_audit_package_status_text_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.audit_package_status_text == "NOT GENERATED"


def test_session_audit_package_id_text_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.audit_package_id_text == ""


def test_session_audit_violations_rows_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.audit_integrity_violations_rows() == []


def test_session_audit_manifest_rows_initial() -> None:
    ctrl = _make_ctrl_no_decision()
    session = WorkspaceSession(ctrl)
    assert session.audit_manifest_rows() == []


# ---------------------------------------------------------------------------
# Fail-closed: missing prerequisites
# ---------------------------------------------------------------------------


def test_run_audit_integrity_fails_without_report() -> None:
    ctrl = _make_ctrl_no_report()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Generate Decision Report first"
    ):
        ctrl.run_audit_integrity()


def test_run_audit_package_fails_without_report() -> None:
    ctrl = _make_ctrl_no_report()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Generate Decision Report first"
    ):
        ctrl.run_audit_package()


def test_session_run_audit_integrity_fails_without_report() -> None:
    ctrl = _make_ctrl_no_report()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Generate Decision Report first"
    ):
        session.run_audit_integrity()


def test_session_generate_audit_package_fails_without_report() -> None:
    ctrl = _make_ctrl_no_report()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Generate Decision Report first"
    ):
        session.generate_audit_package()


# ---------------------------------------------------------------------------
# Successful delegation to Stage 15N (integrity)
# ---------------------------------------------------------------------------


def test_run_audit_integrity_returns_result() -> None:
    ctrl = _make_ctrl_with_report()
    integrity = ctrl.run_audit_integrity()
    assert isinstance(integrity, AuditIntegrityResult)


def test_run_audit_integrity_delegates_to_stage15n() -> None:
    ctrl = _make_ctrl_with_report()
    report = ctrl.last_decision_report
    assert report is not None
    expected = validate_decision_report_integrity(report)
    integrity = ctrl.run_audit_integrity()
    assert integrity.status == expected.status
    assert len(integrity.violations) == len(expected.violations)


def test_audit_integrity_cached_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    integrity = ctrl.run_audit_integrity()
    assert ctrl.last_audit_integrity is integrity


def test_session_run_audit_integrity_caches_result() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    integrity = session.run_audit_integrity()
    assert ctrl.last_audit_integrity is integrity


# ---------------------------------------------------------------------------
# Successful delegation to Stage 15O (audit package)
# ---------------------------------------------------------------------------


def test_run_audit_package_returns_package() -> None:
    ctrl = _make_ctrl_with_report()
    package = ctrl.run_audit_package()
    assert isinstance(package, ToleranceDecisionAuditPackage)


def test_run_audit_package_delegates_to_stage15o() -> None:
    ctrl = _make_ctrl_with_report()
    report = ctrl.last_decision_report
    assert report is not None
    expected = build_decision_audit_package(report)
    package = ctrl.run_audit_package()
    assert package.audit_schema_version == expected.audit_schema_version
    assert package.package_id == expected.package_id
    assert package.replayability_status == expected.replayability_status
    assert package.replay_manifest.decision_id == expected.replay_manifest.decision_id


def test_audit_package_cached_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    package = ctrl.run_audit_package()
    assert ctrl.last_audit_package is package


def test_session_generate_audit_package_caches_result() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    package = session.generate_audit_package()
    assert ctrl.last_audit_package is package


def test_run_audit_package_uses_cached_integrity() -> None:
    """Package uses pre-generated integrity result when available."""
    ctrl = _make_ctrl_with_report()
    integrity = ctrl.run_audit_integrity()
    package = ctrl.run_audit_package()
    assert package.integrity_result == integrity


# ---------------------------------------------------------------------------
# Result mapping
# ---------------------------------------------------------------------------


def test_audit_package_schema_version() -> None:
    ctrl = _make_ctrl_with_report()
    package = ctrl.run_audit_package()
    assert package.audit_schema_version == AUDIT_PACKAGE_SCHEMA_VERSION


def test_audit_integrity_status_is_valid_or_invalid() -> None:
    ctrl = _make_ctrl_with_report()
    integrity = ctrl.run_audit_integrity()
    assert integrity.status in (
        AuditIntegrityStatus.VALID,
        AuditIntegrityStatus.INVALID,
        AuditIntegrityStatus.INCOMPLETE,
    )


def test_audit_package_replayability_reflects_integrity() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_integrity()
    package = ctrl.run_audit_package()
    assert isinstance(package.replayability_status, ReplayabilityStatus)


def test_session_audit_integrity_status_text_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    session.run_audit_integrity()
    assert session.audit_integrity_status_text != "NOT GENERATED"
    assert session.audit_integrity_status_text != ""


def test_session_audit_package_status_text_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    session.generate_audit_package()
    assert session.audit_package_status_text != "NOT GENERATED"
    assert session.audit_package_status_text != ""


def test_session_audit_package_id_text_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    session.generate_audit_package()
    assert session.audit_package_id_text != ""


def test_session_audit_manifest_rows_after_generation() -> None:
    ctrl = _make_ctrl_with_report()
    session = WorkspaceSession(ctrl)
    session.generate_audit_package()
    rows = session.audit_manifest_rows()
    assert len(rows) >= 1
    for row in rows:
        assert "field" in row
        assert "value" in row


# ---------------------------------------------------------------------------
# Replay manifest fields
# ---------------------------------------------------------------------------


def test_audit_package_has_replay_manifest() -> None:
    ctrl = _make_ctrl_with_report()
    package = ctrl.run_audit_package()
    manifest = package.replay_manifest
    assert manifest.audit_schema_version == AUDIT_PACKAGE_SCHEMA_VERSION
    assert len(manifest.report_fingerprint) == 64
    assert len(manifest.input_fingerprint) == 64
    assert len(manifest.integrity_fingerprint) == 64


def test_audit_package_package_id_is_sha256() -> None:
    ctrl = _make_ctrl_with_report()
    package = ctrl.run_audit_package()
    assert len(package.package_id) == 64
    assert all(c in "0123456789abcdef" for c in package.package_id)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_audit_integrity_generation_is_deterministic() -> None:
    ctrl = _make_ctrl_with_report()
    i1 = ctrl.run_audit_integrity()
    i2 = ctrl.run_audit_integrity()
    assert i1.status == i2.status
    assert len(i1.violations) == len(i2.violations)


def test_repeated_audit_package_generation_is_deterministic() -> None:
    ctrl = _make_ctrl_with_report()
    p1 = ctrl.run_audit_package()
    p2 = ctrl.run_audit_package()
    assert p1.package_id == p2.package_id
    assert p1.replayability_status == p2.replayability_status
    assert p1.replay_manifest.decision_id == p2.replay_manifest.decision_id


# ---------------------------------------------------------------------------
# Prerequisite objects unchanged after audit generation
# ---------------------------------------------------------------------------


def test_audit_does_not_change_decision_report() -> None:
    ctrl = _make_ctrl_with_report()
    original_report = ctrl.last_decision_report
    ctrl.run_audit_package()
    assert ctrl.last_decision_report is original_report


def test_audit_does_not_change_decision() -> None:
    ctrl = _make_ctrl_with_report()
    original_decision = ctrl.last_decision
    ctrl.run_audit_package()
    assert ctrl.last_decision is original_decision


def test_audit_does_not_change_evidence() -> None:
    ctrl = _make_ctrl_with_report()
    original_evidence = ctrl.last_evidence
    ctrl.run_audit_package()
    assert ctrl.last_evidence is original_evidence


def test_audit_does_not_change_analysis_result() -> None:
    ctrl = _make_ctrl_with_report()
    original_result = ctrl.last_result
    ctrl.run_audit_package()
    assert ctrl.last_result is original_result


# ---------------------------------------------------------------------------
# Feature isolation
# ---------------------------------------------------------------------------


def test_audit_does_not_clear_sensitivity() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    ctrl.run_audit_package()
    assert ctrl.last_sensitivity is sensitivity_before


def test_audit_does_not_clear_budget() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    ctrl.run_audit_package()
    assert ctrl.last_budget is budget_before


def test_audit_does_not_change_project_id() -> None:
    ctrl = _make_ctrl_with_report()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_audit_package()
    assert ctrl.configuration_fingerprint() == fp_before


def test_audit_does_not_clear_reconciliation() -> None:
    from origlyph.tolerance.workspace_controller import (
        WorkspaceAllocationEntry,
        WorkspaceAllocationPlan,
    )

    ctrl = _make_ctrl_with_report()
    plan = WorkspaceAllocationPlan(
        allowed_budget=2.0,
        entries=(WorkspaceAllocationEntry(contributor_id="A", allocated_span=1.0),),
    )
    ctrl.set_allocation_plan(plan)
    ctrl.run_reconciliation()
    recon_before = ctrl.last_reconciliation
    ctrl.run_audit_package()
    assert ctrl.last_reconciliation is recon_before


# ---------------------------------------------------------------------------
# Stale clearing
# ---------------------------------------------------------------------------


def test_audit_cleared_on_new_report() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.run_decision_report()
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_new_evidence() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.run_decision_evidence()
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_new_decision() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.evaluate_decision()
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_run_analysis() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.run_analysis()
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_contributor_change() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.add_contributor(
        identifier="B",
        name="Part B",
        nominal=0.0,
        tolerance=0.2,
        direction="forward",
        tolerance_model="symmetric",
    )
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_specification_change() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.5))
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_mode_change() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_audit_cleared_on_chain_name_change() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.set_chain_name("renamed chain")
    assert ctrl.last_audit_package is None
    assert ctrl.last_audit_integrity is None


def test_integrity_cleared_on_new_audit_integrity() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_integrity()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    ctrl.run_audit_integrity()
    assert ctrl.last_audit_package is None


# ---------------------------------------------------------------------------
# Persistence boundary — save/load clears runtime audit state
# ---------------------------------------------------------------------------


def test_from_state_clears_audit() -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.last_audit_integrity is None
    assert restored.last_audit_package is None


def test_save_load_clears_runtime_audit(tmp_path) -> None:
    ctrl = _make_ctrl_with_report()
    ctrl.run_audit_package()
    assert ctrl.last_audit_package is not None
    project_file = ctrl.save_project(tmp_path / "test.json")
    loaded = ToleranceWorkspaceController.open_project(project_file)
    assert loaded.last_audit_integrity is None
    assert loaded.last_audit_package is None


def test_project_id_unchanged_after_audit(tmp_path) -> None:
    ctrl = _make_ctrl_with_report()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_audit_package()
    assert ctrl.configuration_fingerprint() == fp_before


# ---------------------------------------------------------------------------
# No hidden prerequisite generation
# ---------------------------------------------------------------------------


def test_run_audit_package_does_not_auto_generate_report() -> None:
    ctrl = _make_ctrl_no_report()
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.run_audit_package()
    assert ctrl.last_decision_report is None


def test_run_audit_integrity_does_not_auto_generate_report() -> None:
    ctrl = _make_ctrl_no_report()
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.run_audit_integrity()
    assert ctrl.last_decision_report is None


# ---------------------------------------------------------------------------
# No duplicated fingerprint calculation
# ---------------------------------------------------------------------------


def test_audit_package_fingerprints_match_backend() -> None:
    """Package IDs from workspace and direct backend call are identical."""
    ctrl = _make_ctrl_with_report()
    report = ctrl.last_decision_report
    assert report is not None
    expected_package = build_decision_audit_package(report)
    workspace_package = ctrl.run_audit_package()
    assert workspace_package.package_id == expected_package.package_id
    manifest = workspace_package.replay_manifest
    expected_manifest = expected_package.replay_manifest
    assert manifest.report_fingerprint == expected_manifest.report_fingerprint
    assert manifest.input_fingerprint == expected_manifest.input_fingerprint
    assert manifest.integrity_fingerprint == expected_manifest.integrity_fingerprint
