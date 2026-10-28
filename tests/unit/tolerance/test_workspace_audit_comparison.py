"""Unit tests for audit comparison and change impact workspace surface (Stage 20E)."""

from __future__ import annotations

import json

import pytest

from origlyph.tolerance.audit import (
    InvalidDecisionAuditPackageError,
    ToleranceDecisionAuditPackage,
    build_decision_audit_package,
)
from origlyph.tolerance.change_impact import (
    assess_audit_change_impact,
)
from origlyph.tolerance.comparison import (
    AuditComparisonStatus,
    compare_decision_audit_packages,
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


def _make_ctrl_with_audit_package() -> ToleranceWorkspaceController:
    """Return a controller with a full audit package cached."""
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
    """Return a controller without an audit package (but with decision + report)."""
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


def test_initial_comparison_package_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.comparison_audit_package is None


def test_initial_audit_comparison_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.last_audit_comparison is None


def test_initial_change_impact_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.last_change_impact is None


def test_session_initial_comparison_package_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.comparison_audit_package is None


def test_session_initial_audit_comparison_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.last_audit_comparison is None


def test_session_initial_change_impact_is_none() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.last_change_impact is None


def test_session_reference_package_id_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.reference_package_id_text == "NOT GENERATED"


def test_session_comparison_package_id_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.comparison_package_id_text == "NOT LOADED"


def test_session_audit_comparison_status_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.audit_comparison_status_text == "NOT COMPARED"


def test_session_change_impact_status_text_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.change_impact_status_text == "NOT EVALUATED"


def test_session_audit_comparison_changes_rows_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.audit_comparison_changes_rows() == []


def test_session_change_impact_rows_initial() -> None:
    ctrl = _make_ctrl_no_audit_package()
    session = WorkspaceSession(ctrl)
    assert session.change_impact_rows() == []


# ---------------------------------------------------------------------------
# Fail-closed: missing prerequisites
# ---------------------------------------------------------------------------


def test_run_audit_comparison_fails_without_audit_package(tmp_path) -> None:
    ctrl = _make_ctrl_no_audit_package()
    # Load a valid comparison package
    assert ctrl.last_decision_report is not None
    pkg = build_decision_audit_package(ctrl.last_decision_report)
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Generate Audit Package first"
    ):
        ctrl.run_audit_comparison()


def test_run_audit_comparison_fails_without_comparison_package() -> None:
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Load Comparison Package first"
    ):
        ctrl.run_audit_comparison()


def test_run_change_impact_fails_without_comparison() -> None:
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Run Audit Comparison first"
    ):
        ctrl.run_change_impact()


def test_session_run_audit_comparison_fails_without_package() -> None:
    ctrl = _make_ctrl_with_audit_package()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Load Comparison Package first"
    ):
        session.run_audit_comparison()


def test_session_run_change_impact_fails_without_comparison() -> None:
    ctrl = _make_ctrl_with_audit_package()
    session = WorkspaceSession(ctrl)
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Run Audit Comparison first"
    ):
        session.run_change_impact()


# ---------------------------------------------------------------------------
# Malformed comparison package rejected
# ---------------------------------------------------------------------------


def test_load_comparison_package_rejects_non_json(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json!!", encoding="utf-8")
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises((json.JSONDecodeError, ValueError)):
        ctrl.load_comparison_audit_package(bad)


def test_load_comparison_package_rejects_wrong_schema(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"audit_schema_version": "bad.version"}', encoding="utf-8")
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises((InvalidDecisionAuditPackageError, Exception)):
        ctrl.load_comparison_audit_package(bad)


def test_load_comparison_package_rejects_json_array(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.load_comparison_audit_package(bad)


def test_load_comparison_package_rejects_empty_object(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises((InvalidDecisionAuditPackageError, Exception)):
        ctrl.load_comparison_audit_package(bad)


# ---------------------------------------------------------------------------
# Exact Stage 15O deserialization
# ---------------------------------------------------------------------------


def test_load_comparison_package_exact_deserialization(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    loaded = ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    assert isinstance(loaded, ToleranceDecisionAuditPackage)
    assert loaded.package_id == pkg.package_id
    assert loaded.replayability_status == pkg.replayability_status


def test_load_comparison_package_caches_result(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    loaded = ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    assert ctrl.comparison_audit_package is loaded


# ---------------------------------------------------------------------------
# Exact Stage 15P comparison delegation
# ---------------------------------------------------------------------------


def test_run_audit_comparison_delegates_to_stage15p(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    comparison = ctrl.run_audit_comparison()
    # Same package → IDENTICAL
    candidate = ctrl.comparison_audit_package
    assert candidate is not None
    expected = compare_decision_audit_packages(pkg, candidate)
    assert comparison.status == expected.status
    assert comparison.baseline_package_id == expected.baseline_package_id
    assert comparison.candidate_package_id == expected.candidate_package_id
    assert len(comparison.changes) == len(expected.changes)


def test_run_audit_comparison_identical_for_same_package(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    comparison = ctrl.run_audit_comparison()
    assert comparison.status == AuditComparisonStatus.IDENTICAL
    assert comparison.changes == ()


def test_audit_comparison_cached_after_generation(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    comparison = ctrl.run_audit_comparison()
    assert ctrl.last_audit_comparison is comparison


def test_session_run_audit_comparison_caches_result(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    comparison = session.run_audit_comparison()
    assert ctrl.last_audit_comparison is comparison


# ---------------------------------------------------------------------------
# Exact Stage 15Q change-impact delegation
# ---------------------------------------------------------------------------


def test_run_change_impact_delegates_to_stage15q(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    comparison = ctrl.run_audit_comparison()
    impact = ctrl.run_change_impact()
    expected = assess_audit_change_impact(comparison)
    assert impact.overall_impact == expected.overall_impact
    assert impact.decision_changed == expected.decision_changed
    assert impact.comparison_status == expected.comparison_status


def test_change_impact_cached_after_generation(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    impact = ctrl.run_change_impact()
    assert ctrl.last_change_impact is impact


def test_session_run_change_impact_caches_result(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    session.run_audit_comparison()
    impact = session.run_change_impact()
    assert ctrl.last_change_impact is impact


# ---------------------------------------------------------------------------
# Deterministic repeated generation
# ---------------------------------------------------------------------------


def test_repeated_comparison_is_deterministic(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    c1 = ctrl.run_audit_comparison()
    c2 = ctrl.run_audit_comparison()
    assert c1.status == c2.status
    assert c1.baseline_package_id == c2.baseline_package_id
    assert c1.candidate_package_id == c2.candidate_package_id


def test_repeated_change_impact_is_deterministic(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    i1 = ctrl.run_change_impact()
    i2 = ctrl.run_change_impact()
    assert i1.overall_impact == i2.overall_impact
    assert i1.decision_changed == i2.decision_changed


# ---------------------------------------------------------------------------
# Result mapping
# ---------------------------------------------------------------------------


def test_session_audit_comparison_status_text_after_generation(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    session.run_audit_comparison()
    assert session.audit_comparison_status_text != "NOT COMPARED"
    assert session.audit_comparison_status_text != ""


def test_session_change_impact_status_text_after_generation(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    session.run_audit_comparison()
    session.run_change_impact()
    assert session.change_impact_status_text != "NOT EVALUATED"
    assert session.change_impact_status_text != ""


def test_session_reference_package_id_text_after_audit_package() -> None:
    ctrl = _make_ctrl_with_audit_package()
    session = WorkspaceSession(ctrl)
    text = session.reference_package_id_text
    assert text != "NOT GENERATED"
    assert text != ""


def test_session_comparison_package_id_text_after_load(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    assert session.comparison_package_id_text != "NOT LOADED"
    assert session.comparison_package_id_text != ""


def test_session_audit_comparison_changes_rows_after_comparison(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    session.run_audit_comparison()
    # Same package → IDENTICAL → empty rows
    rows = session.audit_comparison_changes_rows()
    assert isinstance(rows, list)


def test_session_change_impact_rows_after_generation(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    session = WorkspaceSession(ctrl)
    session.run_audit_comparison()
    session.run_change_impact()
    rows = session.change_impact_rows()
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Stale clearing on current-package change
# ---------------------------------------------------------------------------


def test_comparison_cleared_on_new_audit_package(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.last_audit_comparison is not None
    ctrl.run_audit_package()
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_new_report(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_decision_report()
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_evaluate_decision(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.evaluate_decision()
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_run_analysis(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_analysis()
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_contributor_change(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.add_contributor(
        identifier="B", name="Part B", nominal=0.0, tolerance=0.2,
        direction="forward", tolerance_model="symmetric",
    )
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_specification_change(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.5))
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_mode_change(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


def test_comparison_cleared_on_chain_name_change(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.set_chain_name("renamed chain")
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


# ---------------------------------------------------------------------------
# Stale clearing on comparison-package change
# ---------------------------------------------------------------------------


def test_comparison_cleared_on_comparison_package_reload(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.last_audit_comparison is not None
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None


# ---------------------------------------------------------------------------
# Stale clearing on comparison result change
# ---------------------------------------------------------------------------


def test_change_impact_cleared_on_new_comparison(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.last_change_impact is not None
    ctrl.run_audit_comparison()
    assert ctrl.last_change_impact is None


# ---------------------------------------------------------------------------
# Stale clearing on project load
# ---------------------------------------------------------------------------


def test_from_state_clears_comparison() -> None:
    ctrl = _make_ctrl_with_audit_package()
    assert ctrl.last_audit_package is not None
    restored = ToleranceWorkspaceController.from_state(ctrl.state)
    assert restored.comparison_audit_package is None
    assert restored.last_audit_comparison is None
    assert restored.last_change_impact is None


def test_save_load_clears_runtime_comparison(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    project_file = ctrl.save_project(tmp_path / "test.json")
    loaded = ToleranceWorkspaceController.open_project(project_file)
    assert loaded.comparison_audit_package is None
    assert loaded.last_audit_comparison is None
    assert loaded.last_change_impact is None


# ---------------------------------------------------------------------------
# Feature isolation
# ---------------------------------------------------------------------------


def test_comparison_does_not_change_audit_package(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    original_pkg = ctrl.last_audit_package
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    assert ctrl.last_audit_package is original_pkg


def test_comparison_does_not_change_decision_report(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    original_report = ctrl.last_decision_report
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    assert ctrl.last_decision_report is original_report


def test_comparison_does_not_change_decision(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    original_decision = ctrl.last_decision
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    assert ctrl.last_decision is original_decision


def test_comparison_does_not_change_project_id(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    fp_before = ctrl.configuration_fingerprint()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.configuration_fingerprint() == fp_before


def test_comparison_does_not_clear_sensitivity(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    ctrl.run_sensitivity()
    sensitivity_before = ctrl.last_sensitivity
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.last_sensitivity is sensitivity_before


def test_comparison_does_not_clear_budget(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    ctrl.run_budget()
    budget_before = ctrl.last_budget
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    assert ctrl.last_budget is budget_before


# ---------------------------------------------------------------------------
# No hidden package generation
# ---------------------------------------------------------------------------


def test_run_comparison_does_not_auto_generate_audit_package(tmp_path) -> None:
    ctrl = _make_ctrl_no_audit_package()
    assert ctrl.last_decision_report is not None
    pkg = build_decision_audit_package(ctrl.last_decision_report)
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.run_audit_comparison()
    assert ctrl.last_audit_package is None


def test_run_change_impact_does_not_auto_generate_comparison() -> None:
    ctrl = _make_ctrl_with_audit_package()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.run_change_impact()
    assert ctrl.last_audit_comparison is None


# ---------------------------------------------------------------------------
# No independent hash comparison
# ---------------------------------------------------------------------------


def test_comparison_uses_stage15p_not_manual_hash(tmp_path) -> None:
    """Package IDs from workspace comparison and direct backend call are identical."""
    ctrl = _make_ctrl_with_audit_package()
    current_pkg = ctrl.last_audit_package
    assert current_pkg is not None
    _write_package_json(current_pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    comparison = ctrl.run_audit_comparison()
    candidate = ctrl.comparison_audit_package
    assert candidate is not None
    expected = compare_decision_audit_packages(current_pkg, candidate)
    assert comparison.status == expected.status
    assert comparison.baseline_package_id == expected.baseline_package_id
    assert comparison.candidate_package_id == expected.candidate_package_id


# ---------------------------------------------------------------------------
# No independent impact calculation
# ---------------------------------------------------------------------------


def test_change_impact_uses_stage15q_not_manual_classification(tmp_path) -> None:
    """Change impact from workspace matches direct backend call."""
    ctrl = _make_ctrl_with_audit_package()
    current_pkg = ctrl.last_audit_package
    assert current_pkg is not None
    _write_package_json(current_pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    ctrl.run_audit_comparison()
    impact = ctrl.run_change_impact()
    last_comparison = ctrl.last_audit_comparison
    assert last_comparison is not None
    expected = assess_audit_change_impact(last_comparison)
    assert impact.overall_impact == expected.overall_impact
    assert impact.decision_changed == expected.decision_changed
    assert len(impact.assessed_changes) == len(expected.assessed_changes)


# ---------------------------------------------------------------------------
# project_id unchanged
# ---------------------------------------------------------------------------


def test_load_comparison_package_does_not_change_project_id(tmp_path) -> None:
    ctrl = _make_ctrl_with_audit_package()
    fp_before = ctrl.configuration_fingerprint()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    _write_package_json(pkg, tmp_path / "pkg.json")
    ctrl.load_comparison_audit_package(tmp_path / "pkg.json")
    assert ctrl.configuration_fingerprint() == fp_before
