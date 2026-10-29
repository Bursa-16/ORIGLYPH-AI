"""Unit tests for Governed Acceptance + Acceptance Record surface (Stage 20G.3)."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
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


def _make_full_chain() -> ToleranceWorkspaceController:
    """Return a controller with the full governance chain through approval readiness."""
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
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            fp=f,
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    return ctrl


def _make_partial_chain() -> ToleranceWorkspaceController:
    """Return a controller with audit package but no comparison/impact chain."""
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


def _acceptance_state(
    ctrl: ToleranceWorkspaceController,
    decision: AuditAcceptanceDecision = AuditAcceptanceDecision.APPROVED,
    authority: str = "AUTH-001",
    reference: str = "DEC-001",
) -> WorkspaceAcceptanceState:
    handoff = ctrl.run_acceptance_handoff()
    return WorkspaceAcceptanceState(
        decision=decision,
        authority_reference=authority,
        decision_reference=reference,
        handoff_id=handoff.handoff_id,
    )


# ---------------------------------------------------------------------------
# Controller — initial state
# ---------------------------------------------------------------------------


def test_initial_acceptance_handoff_is_none() -> None:
    ctrl = _make_partial_chain()
    assert ctrl.last_acceptance_handoff is None


def test_initial_acceptance_record_is_none() -> None:
    ctrl = _make_partial_chain()
    assert ctrl.last_acceptance_record is None


# ---------------------------------------------------------------------------
# Controller — run_acceptance_handoff guards
# ---------------------------------------------------------------------------


def test_run_acceptance_handoff_requires_comparison() -> None:
    ctrl = _make_partial_chain()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Audit Comparison"):
        ctrl.run_acceptance_handoff()


def test_run_acceptance_handoff_requires_change_impact(
    tmp_path: Path,
) -> None:
    ctrl = _make_partial_chain()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    p = tmp_path / "pkg.json"
    p.write_text(
        json.dumps(pkg.as_dict(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    ctrl.load_comparison_audit_package(str(p))
    ctrl.run_audit_comparison()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Change Impact"):
        ctrl.run_acceptance_handoff()


def test_run_acceptance_handoff_requires_change_disposition(
    tmp_path: Path,
) -> None:
    ctrl = _make_partial_chain()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    p = tmp_path / "pkg.json"
    p.write_text(
        json.dumps(pkg.as_dict(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    ctrl.load_comparison_audit_package(str(p))
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Change Disposition"):
        ctrl.run_acceptance_handoff()


def test_run_acceptance_handoff_requires_approval_readiness(
    tmp_path: Path,
) -> None:
    ctrl = _make_partial_chain()
    pkg = ctrl.last_audit_package
    assert pkg is not None
    p = tmp_path / "pkg.json"
    p.write_text(
        json.dumps(pkg.as_dict(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    ctrl.load_comparison_audit_package(str(p))
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Approval Readiness"):
        ctrl.run_acceptance_handoff()


# ---------------------------------------------------------------------------
# Controller — run_acceptance_handoff success
# ---------------------------------------------------------------------------


def test_run_acceptance_handoff_returns_package() -> None:
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    assert handoff is not None
    assert handoff.handoff_id


def test_run_acceptance_handoff_stored_on_controller() -> None:
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    assert ctrl.last_acceptance_handoff is handoff


def test_run_acceptance_handoff_clears_acceptance_record() -> None:
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    state = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.APPROVED,
        authority_reference="AUTH-001",
        decision_reference="DEC-001",
        handoff_id=handoff.handoff_id,
    )
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    assert ctrl.last_acceptance_record is not None
    # Re-running handoff must clear the record
    ctrl.run_acceptance_handoff()
    assert ctrl.last_acceptance_record is None


def test_run_acceptance_handoff_deterministic() -> None:
    ctrl = _make_full_chain()
    h1 = ctrl.run_acceptance_handoff()
    h2 = ctrl.run_acceptance_handoff()
    assert h1.handoff_id == h2.handoff_id


# ---------------------------------------------------------------------------
# Controller — run_acceptance_record guards
# ---------------------------------------------------------------------------


def test_run_acceptance_record_requires_handoff() -> None:
    ctrl = _make_full_chain()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Handoff"):
        ctrl.run_acceptance_record()


def test_run_acceptance_record_requires_acceptance_state() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    with pytest.raises(InvalidToleranceWorkspaceError, match="acceptance inputs"):
        ctrl.run_acceptance_record()


def test_run_acceptance_record_detects_handoff_id_mismatch() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    fake_id = hashlib.sha256(b"wrong").hexdigest()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=fake_id,
        )
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="handoff_id"):
        ctrl.run_acceptance_record()


# ---------------------------------------------------------------------------
# Controller — run_acceptance_record success
# ---------------------------------------------------------------------------


def test_run_acceptance_record_approved() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    record = ctrl.run_acceptance_record()
    assert record.decision == AuditAcceptanceDecision.APPROVED
    assert record.authority_reference == "AUTH-001"
    assert record.decision_reference == "DEC-001"


def test_run_acceptance_record_rejected() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl, decision=AuditAcceptanceDecision.REJECTED)
    ctrl.set_acceptance_state(state)
    record = ctrl.run_acceptance_record()
    assert record.decision == AuditAcceptanceDecision.REJECTED


def test_run_acceptance_record_returned_for_action() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(
        ctrl, decision=AuditAcceptanceDecision.RETURNED_FOR_ACTION
    )
    ctrl.set_acceptance_state(state)
    record = ctrl.run_acceptance_record()
    assert record.decision == AuditAcceptanceDecision.RETURNED_FOR_ACTION


def test_run_acceptance_record_stored_on_controller() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    record = ctrl.run_acceptance_record()
    assert ctrl.last_acceptance_record is record


# ---------------------------------------------------------------------------
# Controller — stale clearing
# ---------------------------------------------------------------------------


def test_set_specification_clears_acceptance_handoff_and_record() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=3.0))
    assert ctrl.last_acceptance_handoff is None
    assert ctrl.last_acceptance_record is None


def test_run_analysis_clears_acceptance_handoff() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    ctrl.run_analysis()
    assert ctrl.last_acceptance_handoff is None


def test_run_approval_readiness_clears_acceptance_record() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    ctrl.run_approval_readiness()
    assert ctrl.last_acceptance_handoff is None
    assert ctrl.last_acceptance_record is None


def test_set_acceptance_state_clears_record_only() -> None:
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    state = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.APPROVED,
        authority_reference="AUTH-001",
        decision_reference="DEC-001",
        handoff_id=handoff.handoff_id,
    )
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    # Set a new acceptance state; handoff must be preserved, record cleared
    new_state = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.REJECTED,
        authority_reference="AUTH-002",
        decision_reference="DEC-002",
        handoff_id=handoff.handoff_id,
    )
    ctrl.set_acceptance_state(new_state)
    assert ctrl.last_acceptance_handoff is not None
    assert ctrl.last_acceptance_record is None


# ---------------------------------------------------------------------------
# Session — initial state
# ---------------------------------------------------------------------------


def test_session_initial_acceptance_handoff_is_none() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.last_acceptance_handoff is None


def test_session_initial_acceptance_record_is_none() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.last_acceptance_record is None


def test_session_initial_acceptance_handoff_status_text() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.acceptance_handoff_status_text == "NOT PREPARED"


def test_session_initial_acceptance_record_status_text() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.acceptance_record_status_text == "NOT BUILT"


# ---------------------------------------------------------------------------
# Session — prepare_acceptance_handoff
# ---------------------------------------------------------------------------


def test_session_prepare_acceptance_handoff_returns_package() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    handoff = session.prepare_acceptance_handoff()
    assert handoff is not None
    assert handoff.handoff_id


def test_session_acceptance_handoff_status_text_after_prepare() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    text = session.acceptance_handoff_status_text
    assert text not in ("NOT PREPARED", "")


def test_session_acceptance_handoff_detail_text_contains_id() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    handoff = session.prepare_acceptance_handoff()
    detail = session.acceptance_handoff_detail_text
    assert handoff.handoff_id[:16] in detail


# ---------------------------------------------------------------------------
# Session — sync_acceptance_state
# ---------------------------------------------------------------------------


def test_session_sync_acceptance_state_requires_handoff() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Handoff"):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_requires_decision() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = ""
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    with pytest.raises(InvalidToleranceWorkspaceError, match="decision"):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_rejects_invalid_decision() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "maybe"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Invalid acceptance decision"
    ):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_requires_authority() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = ""
    session.acceptance_decision_reference = "DEC-001"
    with pytest.raises(InvalidToleranceWorkspaceError, match="Authority"):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_rejects_whitespace_authority() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "  AUTH "
    session.acceptance_decision_reference = "DEC-001"
    with pytest.raises(InvalidToleranceWorkspaceError, match="whitespace"):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_requires_reference() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = ""
    with pytest.raises(InvalidToleranceWorkspaceError, match="Decision reference"):
        session.sync_acceptance_state()


def test_session_sync_acceptance_state_success() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    acc = ctrl.acceptance_state
    assert acc is not None
    assert acc.decision == AuditAcceptanceDecision.APPROVED
    assert acc.authority_reference == "AUTH-001"
    assert acc.decision_reference == "DEC-001"


# ---------------------------------------------------------------------------
# Session — build_acceptance_record
# ---------------------------------------------------------------------------


def test_session_build_acceptance_record_after_sync() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    record = session.build_acceptance_record()
    assert record.decision == AuditAcceptanceDecision.APPROVED


def test_session_acceptance_record_status_text_after_build() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    session.build_acceptance_record()
    assert session.acceptance_record_status_text == "APPROVED"


def test_session_acceptance_record_detail_text_contains_decision() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "rejected"
    session.acceptance_authority_reference = "AUTH-002"
    session.acceptance_decision_reference = "DEC-002"
    session.sync_acceptance_state()
    session.build_acceptance_record()
    detail = session.acceptance_record_detail_text
    assert "rejected" in detail
    assert "AUTH-002" in detail
    assert "DEC-002" in detail


# ---------------------------------------------------------------------------
# Session — clear_acceptance_state
# ---------------------------------------------------------------------------


def test_session_clear_acceptance_state_resets_fields() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    session.clear_acceptance_state()
    assert session.acceptance_decision == ""
    assert session.acceptance_authority_reference == ""
    assert session.acceptance_decision_reference == ""
    assert ctrl.acceptance_state is None


# ---------------------------------------------------------------------------
# Session — load_acceptance_fields round-trip
# ---------------------------------------------------------------------------


def test_load_acceptance_fields_from_controller_state() -> None:
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.REJECTED,
            authority_reference="AUTH-LOAD",
            decision_reference="DEC-LOAD",
            handoff_id=handoff.handoff_id,
        )
    )
    session = WorkspaceSession(ctrl)
    # Fields must already be loaded by __init__
    assert session.acceptance_decision == "rejected"
    assert session.acceptance_authority_reference == "AUTH-LOAD"
    assert session.acceptance_decision_reference == "DEC-LOAD"


def test_load_acceptance_fields_no_state() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.acceptance_decision == ""
    assert session.acceptance_authority_reference == ""
    assert session.acceptance_decision_reference == ""


# ---------------------------------------------------------------------------
# Save / Open round-trip — acceptance inputs preserved
# ---------------------------------------------------------------------------


def test_save_open_preserves_acceptance_state(tmp_path: Path) -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-SAVE"
    session.acceptance_decision_reference = "DEC-SAVE"
    session.sync_acceptance_state()

    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")

    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    acc = ctrl2.acceptance_state
    assert acc is not None
    assert acc.decision == AuditAcceptanceDecision.APPROVED
    assert acc.authority_reference == "AUTH-SAVE"
    assert acc.decision_reference == "DEC-SAVE"
    assert len(acc.handoff_id) == 64


def test_save_open_runtime_handoff_cleared(tmp_path: Path) -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    session.build_acceptance_record()

    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")

    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    assert ctrl2.last_acceptance_handoff is None
    assert ctrl2.last_acceptance_record is None


def test_save_open_acceptance_fields_reloaded_by_session(tmp_path: Path) -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "returned_for_action"
    session.acceptance_authority_reference = "AUTH-RTN"
    session.acceptance_decision_reference = "DEC-RTN"
    session.sync_acceptance_state()

    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")

    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    session2 = WorkspaceSession(ctrl2)
    assert session2.acceptance_decision == "returned_for_action"
    assert session2.acceptance_authority_reference == "AUTH-RTN"
    assert session2.acceptance_decision_reference == "DEC-RTN"


# ---------------------------------------------------------------------------
# Identity — acceptance state changes rotate project_id
# ---------------------------------------------------------------------------


def test_acceptance_state_changes_configuration_fingerprint() -> None:
    ctrl = _make_full_chain()
    fp_before = ctrl.configuration_fingerprint()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    fp_after = ctrl.configuration_fingerprint()
    assert fp_before != fp_after


def test_clearing_acceptance_state_changes_configuration_fingerprint() -> None:
    ctrl = _make_full_chain()
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    fp_with = ctrl.configuration_fingerprint()
    ctrl.clear_acceptance_state()
    fp_without = ctrl.configuration_fingerprint()
    assert fp_with != fp_without


# ---------------------------------------------------------------------------
# Semantic safety — no approve/certify/authenticate wording in status text
# ---------------------------------------------------------------------------

_FORBIDDEN_WORDS = {"certify", "authenticate", "authorize", "sign", "release"}


def test_acceptance_handoff_status_text_has_no_forbidden_words() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    text = session.acceptance_handoff_status_text.lower()
    for word in _FORBIDDEN_WORDS:
        assert word not in text, f"Forbidden word in handoff status text: {word!r}"


def test_acceptance_record_status_text_has_no_forbidden_words() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    session.prepare_acceptance_handoff()
    session.acceptance_decision = "approved"
    session.acceptance_authority_reference = "AUTH-001"
    session.acceptance_decision_reference = "DEC-001"
    session.sync_acceptance_state()
    session.build_acceptance_record()
    text = session.acceptance_record_status_text.lower()
    for word in _FORBIDDEN_WORDS:
        assert word not in text, f"Forbidden word in record status text: {word!r}"


# ---------------------------------------------------------------------------
# Feature isolation — acceptance does not break prior governance chain
# ---------------------------------------------------------------------------


def test_acceptance_does_not_affect_change_disposition_result() -> None:
    ctrl = _make_full_chain()
    disp_before = ctrl.last_change_disposition
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    assert ctrl.last_change_disposition is disp_before


def test_acceptance_does_not_affect_approval_readiness_result() -> None:
    ctrl = _make_full_chain()
    readiness_before = ctrl.last_approval_readiness
    state = _acceptance_state(ctrl)
    ctrl.set_acceptance_state(state)
    ctrl.run_acceptance_record()
    assert ctrl.last_approval_readiness is readiness_before
