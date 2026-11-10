"""Tests for governance state restoration (Stage 21G).

Covers ToleranceWorkspaceController.restore_governance_state and
WorkspaceSession.restore_governance_state delegation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.audit import InvalidDecisionAuditPackageError
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceSpecification,
)
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctrl_minimal() -> ToleranceWorkspaceController:
    """Controller with one contributor and worst-case specification — no chain run."""
    ctrl = ToleranceWorkspaceController(
        chain_name="Restore chain",
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
    return ctrl


def _run_core_chain(ctrl: ToleranceWorkspaceController) -> None:
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    ctrl.run_audit_integrity()
    ctrl.run_audit_package()


def _write_audit_package(ctrl: ToleranceWorkspaceController) -> str:
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as fh:
        json.dump(
            pkg.as_dict(),
            fp=fh,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return fh.name


def _make_ctrl_with_comparison(
    *, with_acceptance: bool = True
) -> tuple[ToleranceWorkspaceController, str]:
    """Controller with full chain including comparison."""
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)
    ctrl.load_comparison_audit_package(cpath)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    if with_acceptance:
        ctrl.set_acceptance_state(
            WorkspaceAcceptanceState(
                decision=AuditAcceptanceDecision.APPROVED,
                authority_reference="AUTH-001",
                decision_reference="DEC-001",
                handoff_id=handoff.handoff_id,
            )
        )
        ctrl.run_acceptance_record()
        ctrl.run_acceptance_verification()
        ctrl.run_acceptance_closure()
    return ctrl, cpath


# ---------------------------------------------------------------------------
# 1. Runtime state initially absent after project open
# ---------------------------------------------------------------------------


def test_runtime_absent_after_open(tmp_path: Path) -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    save_path = tmp_path / "proj.json"
    ctrl.save_project(save_path)

    loaded = ToleranceWorkspaceController.open_project(save_path)
    assert loaded.last_decision_report is None
    assert loaded.last_audit_package is None
    assert loaded.last_acceptance_closure is None


def test_all_runtime_absent_after_open(tmp_path: Path) -> None:
    ctrl, _ = _make_ctrl_with_comparison()
    save_path = tmp_path / "proj.json"
    ctrl.save_project(save_path)

    loaded = ToleranceWorkspaceController.open_project(save_path)
    for attr in (
        "last_decision",
        "last_evidence",
        "last_decision_report",
        "last_audit_package",
        "last_audit_comparison",
        "last_change_impact",
        "last_change_disposition",
        "last_approval_readiness",
        "last_acceptance_handoff",
        "last_acceptance_record",
        "last_acceptance_verification",
        "last_acceptance_closure",
    ):
        assert getattr(loaded, attr) is None, f"{attr} should be None after open"


# ---------------------------------------------------------------------------
# 2. Core chain restored (no comparison)
# ---------------------------------------------------------------------------


def test_restore_core_chain_artifacts_present() -> None:
    ctrl = _make_ctrl_minimal()
    ctrl.restore_governance_state()

    assert ctrl.last_result is not None
    assert ctrl.last_decision is not None
    assert ctrl.last_evidence is not None
    assert ctrl.last_decision_report is not None
    assert ctrl.last_audit_integrity is not None
    assert ctrl.last_audit_package is not None


def test_restore_core_chain_comparison_absent() -> None:
    ctrl = _make_ctrl_minimal()
    ctrl.restore_governance_state()

    assert ctrl.comparison_audit_package is None
    assert ctrl.last_audit_comparison is None
    assert ctrl.last_change_impact is None
    assert ctrl.last_change_disposition is None
    assert ctrl.last_approval_readiness is None
    assert ctrl.last_acceptance_handoff is None
    assert ctrl.last_acceptance_record is None
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


# ---------------------------------------------------------------------------
# 3. Full chain restored with comparison
# ---------------------------------------------------------------------------


def test_restore_full_chain_with_comparison() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)

    ctrl2 = _make_ctrl_minimal()
    ctrl2.restore_governance_state(comparison_path=cpath)

    assert ctrl2.last_audit_comparison is not None
    assert ctrl2.last_change_impact is not None
    assert ctrl2.last_change_disposition is not None
    assert ctrl2.last_approval_readiness is not None
    assert ctrl2.last_acceptance_handoff is not None
    assert ctrl2.last_acceptance_record is None
    assert ctrl2.last_acceptance_verification is None
    assert ctrl2.last_acceptance_closure is None


def test_restore_full_chain_with_acceptance_closure() -> None:
    ctrl, cpath = _make_ctrl_with_comparison()
    acc_state = ctrl.state.acceptance_state
    assert acc_state is not None

    ctrl2 = _make_ctrl_minimal()
    ctrl2.set_acceptance_state(acc_state)
    ctrl2.restore_governance_state(comparison_path=cpath)

    assert ctrl2.last_acceptance_handoff is not None
    assert ctrl2.last_acceptance_record is not None
    assert ctrl2.last_acceptance_verification is not None
    assert ctrl2.last_acceptance_closure is not None


# ---------------------------------------------------------------------------
# 4. Restore after project reopen
# ---------------------------------------------------------------------------


def test_restore_after_project_reopen_core(tmp_path: Path) -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    save_path = tmp_path / "proj.json"
    ctrl.save_project(save_path)

    loaded = ToleranceWorkspaceController.open_project(save_path)
    assert loaded.last_decision_report is None

    loaded.restore_governance_state()
    assert loaded.last_decision_report is not None
    assert loaded.last_audit_package is not None


def test_restore_after_project_reopen_full(tmp_path: Path) -> None:
    ctrl, cpath = _make_ctrl_with_comparison()
    save_path = tmp_path / "proj.json"
    ctrl.save_project(save_path)
    acc_state = ctrl.state.acceptance_state

    loaded = ToleranceWorkspaceController.open_project(save_path)
    loaded.restore_governance_state(comparison_path=cpath)

    assert loaded.last_acceptance_closure is not None
    assert loaded.state.acceptance_state == acc_state


# ---------------------------------------------------------------------------
# 5. Determinism — repeat restore produces same artifacts
# ---------------------------------------------------------------------------


def test_restore_determinism_core() -> None:
    ctrl = _make_ctrl_minimal()
    ctrl.restore_governance_state()
    pid1 = ctrl.last_audit_package.package_id  # type: ignore[union-attr]
    did1 = ctrl.last_decision_report.decision_id()  # type: ignore[union-attr]

    ctrl.restore_governance_state()
    pid2 = ctrl.last_audit_package.package_id  # type: ignore[union-attr]
    did2 = ctrl.last_decision_report.decision_id()  # type: ignore[union-attr]

    assert pid1 == pid2
    assert did1 == did2


def test_restore_determinism_handoff_id() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)

    ctrl2 = _make_ctrl_minimal()
    ctrl2.restore_governance_state(comparison_path=cpath)
    hid1 = ctrl2.last_acceptance_handoff.handoff_id  # type: ignore[union-attr]

    ctrl2.restore_governance_state(comparison_path=cpath)
    hid2 = ctrl2.last_acceptance_handoff.handoff_id  # type: ignore[union-attr]

    assert hid1 == hid2


# ---------------------------------------------------------------------------
# 6. Project identity unchanged after restore
# ---------------------------------------------------------------------------


def test_project_fingerprint_unchanged_core() -> None:
    ctrl = _make_ctrl_minimal()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.restore_governance_state()
    assert ctrl.configuration_fingerprint() == fp_before


def test_project_fingerprint_unchanged_full() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)

    ctrl2 = _make_ctrl_minimal()
    fp_before = ctrl2.configuration_fingerprint()
    ctrl2.restore_governance_state(comparison_path=cpath)
    assert ctrl2.configuration_fingerprint() == fp_before


def test_workspace_state_unchanged_after_restore() -> None:
    ctrl = _make_ctrl_minimal()
    state_before = ctrl.state
    ctrl.restore_governance_state()
    assert ctrl.state is state_before


# ---------------------------------------------------------------------------
# 7. Authoritative acceptance inputs unchanged after restore
# ---------------------------------------------------------------------------


def test_acceptance_state_preserved_during_restore() -> None:
    ctrl, cpath = _make_ctrl_with_comparison()
    acc = ctrl.state.acceptance_state
    assert acc is not None

    ctrl.restore_governance_state(comparison_path=cpath)
    assert ctrl.state.acceptance_state == acc


def test_acceptance_state_none_preserved_during_restore() -> None:
    ctrl = _make_ctrl_minimal()
    assert ctrl.state.acceptance_state is None
    ctrl.restore_governance_state()
    assert ctrl.state.acceptance_state is None


# ---------------------------------------------------------------------------
# 8. Missing prerequisites
# ---------------------------------------------------------------------------


def test_restore_raises_no_contributors() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="Empty chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor"):
        ctrl.restore_governance_state()


def test_restore_raises_no_specification() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="No spec",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A", name="A", nominal=0.0, tolerance=0.1,
        direction="forward", tolerance_model="symmetric",
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="specification"):
        ctrl.restore_governance_state()


def test_restore_raises_comparison_file_missing() -> None:
    ctrl = _make_ctrl_minimal()
    with pytest.raises(InvalidToleranceWorkspaceError, match="not found"):
        ctrl.restore_governance_state(comparison_path="/nonexistent/path/pkg.json")


def test_restore_raises_comparison_file_missing_pathlib() -> None:
    ctrl = _make_ctrl_minimal()
    with pytest.raises(InvalidToleranceWorkspaceError, match="not found"):
        ctrl.restore_governance_state(comparison_path=Path("/nonexistent/pkg.json"))


# ---------------------------------------------------------------------------
# 9. Comparison absent → partial restore (stops after audit package)
# ---------------------------------------------------------------------------


def test_restore_no_comparison_stops_at_audit_package() -> None:
    ctrl = _make_ctrl_minimal()
    ctrl.restore_governance_state()

    assert ctrl.last_audit_package is not None
    assert ctrl.comparison_audit_package is None
    assert ctrl.last_audit_comparison is None


def test_restore_no_comparison_clears_stale_comparison_state() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)
    ctrl.load_comparison_audit_package(cpath)
    ctrl.run_audit_comparison()
    assert ctrl.last_audit_comparison is not None

    ctrl.restore_governance_state()
    assert ctrl.comparison_audit_package is None
    assert ctrl.last_audit_comparison is None


# ---------------------------------------------------------------------------
# 10. Stale state cleared correctly
# ---------------------------------------------------------------------------


def test_clear_stale_state_before_restore() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    old_pid = ctrl.last_audit_package.package_id  # type: ignore[union-attr]

    ctrl.restore_governance_state()
    new_pid = ctrl.last_audit_package.package_id  # type: ignore[union-attr]
    assert new_pid == old_pid


def test_clear_called_on_restore_start(monkeypatch: pytest.MonkeyPatch) -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)

    cleared: list[str] = []
    original_clear = ctrl._clear_all_governance_runtime_state  # type: ignore[attr-defined]

    def recording_clear() -> None:
        cleared.append("called")
        original_clear()

    monkeypatch.setattr(ctrl, "_clear_all_governance_runtime_state", recording_clear)
    ctrl.restore_governance_state()
    assert len(cleared) == 1


def test_failed_restore_leaves_cleared_state(monkeypatch: pytest.MonkeyPatch) -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)

    def fail_analysis() -> None:
        raise RuntimeError("simulated analysis failure")

    monkeypatch.setattr(ctrl, "run_analysis", fail_analysis)
    with pytest.raises(RuntimeError, match="simulated"):
        ctrl.restore_governance_state()

    assert ctrl.last_result is None
    assert ctrl.last_decision_report is None
    assert ctrl.last_audit_package is None


# ---------------------------------------------------------------------------
# 11. Malformed / wrong-schema comparison file
# ---------------------------------------------------------------------------


def test_restore_malformed_comparison_raises(tmp_path: Path) -> None:
    cpath = tmp_path / "bad.json"
    cpath.write_text('{"not": "an audit package"}', encoding="utf-8")
    ctrl = _make_ctrl_minimal()
    with pytest.raises(InvalidDecisionAuditPackageError):
        ctrl.restore_governance_state(comparison_path=cpath)


def test_restore_non_json_comparison_raises(tmp_path: Path) -> None:
    cpath = tmp_path / "bad.json"
    cpath.write_text("this is not json at all!!!", encoding="utf-8")
    ctrl = _make_ctrl_minimal()
    with pytest.raises(ValueError):
        ctrl.restore_governance_state(comparison_path=cpath)


def test_restore_json_array_comparison_raises(tmp_path: Path) -> None:
    cpath = tmp_path / "array.json"
    cpath.write_text("[1, 2, 3]", encoding="utf-8")
    ctrl = _make_ctrl_minimal()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.restore_governance_state(comparison_path=cpath)


# ---------------------------------------------------------------------------
# 12. Comparison path excluded from project identity
# ---------------------------------------------------------------------------


def test_comparison_path_does_not_change_fingerprint() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)
    fp_before = ctrl.configuration_fingerprint()

    ctrl2 = _make_ctrl_minimal()
    ctrl2.restore_governance_state(comparison_path=cpath)
    assert ctrl2.configuration_fingerprint() == fp_before


# ---------------------------------------------------------------------------
# 13. No acceptance_state → restore stops after handoff (no record/verification/closure)
# ---------------------------------------------------------------------------


def test_restore_with_comparison_no_acceptance_state_stops_at_handoff() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)

    ctrl2 = _make_ctrl_minimal()
    ctrl2.restore_governance_state(comparison_path=cpath)

    assert ctrl2.last_acceptance_handoff is not None
    assert ctrl2.last_acceptance_record is None
    assert ctrl2.last_acceptance_verification is None
    assert ctrl2.last_acceptance_closure is None


# ---------------------------------------------------------------------------
# 14. Session delegation
# ---------------------------------------------------------------------------


def test_session_restore_delegates_to_controller() -> None:
    ctrl = _make_ctrl_minimal()
    session = WorkspaceSession(ctrl)
    session.restore_governance_state()

    assert ctrl.last_audit_package is not None
    assert ctrl.last_decision_report is not None


def test_session_restore_with_comparison() -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    cpath = _write_audit_package(ctrl)

    ctrl2 = _make_ctrl_minimal()
    session = WorkspaceSession(ctrl2)
    session.restore_governance_state(comparison_path=cpath)

    assert ctrl2.last_acceptance_handoff is not None


def test_session_restore_raises_propagates() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="Empty",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    session = WorkspaceSession(ctrl)
    with pytest.raises(InvalidToleranceWorkspaceError, match="contributor"):
        session.restore_governance_state()


# ---------------------------------------------------------------------------
# 15. No auto-save on restore
# ---------------------------------------------------------------------------


def test_restore_does_not_mutate_project_file(tmp_path: Path) -> None:
    ctrl = _make_ctrl_minimal()
    _run_core_chain(ctrl)
    save_path = tmp_path / "proj.json"
    ctrl.save_project(save_path)
    mtime_before = save_path.stat().st_mtime

    loaded = ToleranceWorkspaceController.open_project(save_path)
    loaded.restore_governance_state()

    assert save_path.stat().st_mtime == mtime_before


# ---------------------------------------------------------------------------
# 16. Statistical analysis mode restore
# ---------------------------------------------------------------------------


def test_restore_rss_statistical_mode() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="Stat chain",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.5,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_combined_sigma=3.0))
    ctrl.restore_governance_state()

    assert ctrl.last_result is not None
    assert ctrl.last_decision_report is not None
    assert ctrl.last_audit_package is not None


# ---------------------------------------------------------------------------
# 17. Multiple contributors
# ---------------------------------------------------------------------------


def test_restore_multiple_contributors() -> None:
    ctrl = ToleranceWorkspaceController(
        chain_name="Multi chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    for i in range(3):
        ctrl.add_contributor(
            identifier=f"C{i}",
            name=f"Part {i}",
            nominal=0.0,
            tolerance=0.1,
            direction="forward",
            tolerance_model="symmetric",
        )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    ctrl.restore_governance_state()

    assert ctrl.last_audit_package is not None


# ---------------------------------------------------------------------------
# 18. Acceptance state invariant assertion fires on mutation
# ---------------------------------------------------------------------------


def test_acceptance_invariant_state_reference_stable() -> None:
    ctrl, cpath = _make_ctrl_with_comparison()
    acc_before = ctrl.state.acceptance_state
    state_before = ctrl.state

    ctrl.restore_governance_state(comparison_path=cpath)

    assert ctrl.state.acceptance_state is acc_before
    assert ctrl.state is state_before
