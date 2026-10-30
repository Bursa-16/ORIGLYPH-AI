"""Unit tests for Acceptance Verification + Acceptance Closure surface (Stage 20H)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_closure import AuditAcceptanceClosureStatus
from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.acceptance_verification import (
    AuditAcceptanceVerificationStatus,
)
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


def _chain_with_record(
    decision: AuditAcceptanceDecision = AuditAcceptanceDecision.APPROVED,
) -> ToleranceWorkspaceController:
    """Return a controller with record built and cached."""
    ctrl = _make_full_chain()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=decision,
            authority_reference="AUTH-001",
            decision_reference="DEC-001",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    return ctrl


def _chain_with_verification(
    decision: AuditAcceptanceDecision = AuditAcceptanceDecision.APPROVED,
) -> ToleranceWorkspaceController:
    """Return a controller with verification envelope built and cached."""
    ctrl = _chain_with_record(decision)
    ctrl.run_acceptance_verification()
    return ctrl


# ---------------------------------------------------------------------------
# Controller — initial state
# ---------------------------------------------------------------------------


def test_initial_acceptance_verification_is_none() -> None:
    ctrl = _make_full_chain()
    assert ctrl.last_acceptance_verification is None


def test_initial_acceptance_closure_is_none() -> None:
    ctrl = _make_full_chain()
    assert ctrl.last_acceptance_closure is None


# ---------------------------------------------------------------------------
# Controller — run_acceptance_verification guards
# ---------------------------------------------------------------------------


def test_run_acceptance_verification_requires_handoff() -> None:
    ctrl = _make_full_chain()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Handoff"):
        ctrl.run_acceptance_verification()


def test_run_acceptance_verification_requires_record() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Record"):
        ctrl.run_acceptance_verification()


# ---------------------------------------------------------------------------
# Controller — run_acceptance_verification success
# ---------------------------------------------------------------------------


def test_run_acceptance_verification_returns_envelope() -> None:
    ctrl = _chain_with_record()
    envelope = ctrl.run_acceptance_verification()
    assert envelope is not None
    assert envelope.envelope_id
    assert len(envelope.envelope_id) == 64


def test_run_acceptance_verification_status_is_verified_binding() -> None:
    ctrl = _chain_with_record()
    envelope = ctrl.run_acceptance_verification()
    assert envelope.status == AuditAcceptanceVerificationStatus.VERIFIED_BINDING


def test_run_acceptance_verification_stored_on_controller() -> None:
    ctrl = _chain_with_record()
    envelope = ctrl.run_acceptance_verification()
    assert ctrl.last_acceptance_verification is envelope


def test_run_acceptance_verification_clears_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    assert ctrl.last_acceptance_closure is not None
    ctrl.run_acceptance_verification()
    assert ctrl.last_acceptance_closure is None


def test_run_acceptance_verification_deterministic() -> None:
    ctrl = _chain_with_record()
    e1 = ctrl.run_acceptance_verification()
    e2 = ctrl.run_acceptance_verification()
    assert e1.envelope_id == e2.envelope_id


def test_run_acceptance_verification_does_not_change_fingerprint() -> None:
    ctrl = _chain_with_record()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_acceptance_verification()
    fp_after = ctrl.configuration_fingerprint()
    assert fp_before == fp_after


# ---------------------------------------------------------------------------
# Controller — run_acceptance_closure guards
# ---------------------------------------------------------------------------


def test_run_acceptance_closure_requires_handoff() -> None:
    ctrl = _make_full_chain()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Handoff"):
        ctrl.run_acceptance_closure()


def test_run_acceptance_closure_requires_record() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Record"):
        ctrl.run_acceptance_closure()


def test_run_acceptance_closure_requires_verification() -> None:
    ctrl = _chain_with_record()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Verify Acceptance Record"
    ):
        ctrl.run_acceptance_closure()


# ---------------------------------------------------------------------------
# Controller — run_acceptance_closure success
# ---------------------------------------------------------------------------


def test_run_acceptance_closure_returns_manifest() -> None:
    ctrl = _chain_with_verification()
    manifest = ctrl.run_acceptance_closure()
    assert manifest is not None
    assert manifest.closure_id
    assert len(manifest.closure_id) == 64


def test_run_acceptance_closure_status_is_complete() -> None:
    ctrl = _chain_with_verification()
    manifest = ctrl.run_acceptance_closure()
    assert manifest.status == AuditAcceptanceClosureStatus.COMPLETE


def test_run_acceptance_closure_stored_on_controller() -> None:
    ctrl = _chain_with_verification()
    manifest = ctrl.run_acceptance_closure()
    assert ctrl.last_acceptance_closure is manifest


def test_run_acceptance_closure_deterministic() -> None:
    ctrl = _chain_with_verification()
    m1 = ctrl.run_acceptance_closure()
    m2 = ctrl.run_acceptance_closure()
    assert m1.closure_id == m2.closure_id


def test_run_acceptance_closure_does_not_change_fingerprint() -> None:
    ctrl = _chain_with_verification()
    fp_before = ctrl.configuration_fingerprint()
    ctrl.run_acceptance_closure()
    fp_after = ctrl.configuration_fingerprint()
    assert fp_before == fp_after


# ---------------------------------------------------------------------------
# Controller — result mapping
# ---------------------------------------------------------------------------


def test_verification_envelope_references_correct_handoff_id() -> None:
    ctrl = _chain_with_record()
    handoff = ctrl.last_acceptance_handoff
    assert handoff is not None
    envelope = ctrl.run_acceptance_verification()
    assert envelope.handoff_id == handoff.handoff_id


def test_closure_manifest_references_correct_ids() -> None:
    ctrl = _chain_with_verification()
    record = ctrl.last_acceptance_record
    envelope = ctrl.last_acceptance_verification
    assert record is not None
    assert envelope is not None
    manifest = ctrl.run_acceptance_closure()
    assert manifest.references.acceptance_record_id == record.acceptance_record_id
    assert manifest.references.envelope_id == envelope.envelope_id
    assert manifest.references.handoff_id == envelope.handoff_id


def test_closure_manifest_preserves_decision() -> None:
    ctrl = _chain_with_record(AuditAcceptanceDecision.REJECTED)
    ctrl.run_acceptance_verification()
    manifest = ctrl.run_acceptance_closure()
    assert manifest.references.decision == AuditAcceptanceDecision.REJECTED


# ---------------------------------------------------------------------------
# Stale clearing — verification + closure cleared by upstream changes
# ---------------------------------------------------------------------------


def test_set_specification_clears_verification_and_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=3.0))
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


def test_run_approval_readiness_clears_verification_and_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    ctrl.run_approval_readiness()
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


def test_set_acceptance_state_clears_verification_and_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    handoff = ctrl.last_acceptance_handoff
    assert handoff is not None
    new_state = WorkspaceAcceptanceState(
        decision=AuditAcceptanceDecision.REJECTED,
        authority_reference="AUTH-002",
        decision_reference="DEC-002",
        handoff_id=handoff.handoff_id,
    )
    ctrl.set_acceptance_state(new_state)
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


def test_run_acceptance_record_clears_verification_and_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    # Re-running run_acceptance_record must clear both
    ctrl.run_acceptance_record()
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


def test_run_acceptance_handoff_clears_verification_and_closure() -> None:
    ctrl = _chain_with_verification()
    ctrl.run_acceptance_closure()
    ctrl.run_acceptance_handoff()
    assert ctrl.last_acceptance_verification is None
    assert ctrl.last_acceptance_closure is None


# ---------------------------------------------------------------------------
# Save / Open — runtime artifacts cleared, v5 authoritative inputs preserved
# ---------------------------------------------------------------------------


def test_save_open_clears_verification_and_closure(tmp_path: Path) -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    ctrl.run_acceptance_closure()

    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")

    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    assert ctrl2.last_acceptance_handoff is None
    assert ctrl2.last_acceptance_record is None
    assert ctrl2.last_acceptance_verification is None
    assert ctrl2.last_acceptance_closure is None


def test_save_open_preserves_v5_acceptance_state(tmp_path: Path) -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    ctrl.run_acceptance_closure()

    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")

    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    acc = ctrl2.acceptance_state
    assert acc is not None
    assert acc.decision == AuditAcceptanceDecision.APPROVED
    assert acc.authority_reference == "AUTH-001"
    assert acc.decision_reference == "DEC-001"


# ---------------------------------------------------------------------------
# No hidden execution
# ---------------------------------------------------------------------------


def test_no_hidden_handoff_execution_on_open(tmp_path: Path) -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")
    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    assert ctrl2.last_acceptance_handoff is None


def test_no_hidden_verification_execution_on_open(tmp_path: Path) -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    project_path = tmp_path / "project.json"
    session.save_project(project_path, project_name="Test")
    ctrl2 = ToleranceWorkspaceController.open_project(str(project_path))
    assert ctrl2.last_acceptance_verification is None


# ---------------------------------------------------------------------------
# Session integration
# ---------------------------------------------------------------------------


def test_session_initial_verification_is_none() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.last_acceptance_verification is None


def test_session_initial_closure_is_none() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.last_acceptance_closure is None


def test_session_initial_verification_status_text() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.acceptance_verification_status_text == "NOT VERIFIED"


def test_session_initial_closure_status_text() -> None:
    ctrl = _make_full_chain()
    session = WorkspaceSession(ctrl)
    assert session.acceptance_closure_status_text == "NOT BUILT"


def test_session_run_acceptance_verification_returns_envelope() -> None:
    ctrl = _chain_with_record()
    session = WorkspaceSession(ctrl)
    envelope = session.run_acceptance_verification()
    assert envelope is not None
    assert envelope.status == AuditAcceptanceVerificationStatus.VERIFIED_BINDING


def test_session_verification_status_text_after_verify() -> None:
    ctrl = _chain_with_record()
    session = WorkspaceSession(ctrl)
    session.run_acceptance_verification()
    assert session.acceptance_verification_status_text == "VERIFIED_BINDING"


def test_session_verification_detail_text_contains_id() -> None:
    ctrl = _chain_with_record()
    session = WorkspaceSession(ctrl)
    envelope = session.run_acceptance_verification()
    detail = session.acceptance_verification_detail_text
    assert envelope.envelope_id[:16] in detail


def test_session_run_acceptance_closure_returns_manifest() -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    manifest = session.run_acceptance_closure()
    assert manifest is not None
    assert manifest.status == AuditAcceptanceClosureStatus.COMPLETE


def test_session_closure_status_text_after_build() -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    session.run_acceptance_closure()
    assert session.acceptance_closure_status_text == "COMPLETE"


def test_session_closure_detail_text_contains_closure_id() -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    manifest = session.run_acceptance_closure()
    detail = session.acceptance_closure_detail_text
    assert manifest.closure_id[:16] in detail


# ---------------------------------------------------------------------------
# Semantic safety — no forbidden words in status text
# ---------------------------------------------------------------------------

_FORBIDDEN = {"certify", "authenticate", "authorize", "sign", "release"}


def test_verification_status_text_has_no_forbidden_words() -> None:
    ctrl = _chain_with_record()
    session = WorkspaceSession(ctrl)
    session.run_acceptance_verification()
    text = session.acceptance_verification_status_text.lower()
    for word in _FORBIDDEN:
        assert word not in text, f"Forbidden word in verification status: {word!r}"


def test_closure_status_text_has_no_forbidden_words() -> None:
    ctrl = _chain_with_verification()
    session = WorkspaceSession(ctrl)
    session.run_acceptance_closure()
    text = session.acceptance_closure_status_text.lower()
    for word in _FORBIDDEN:
        assert word not in text, f"Forbidden word in closure status: {word!r}"


# ---------------------------------------------------------------------------
# Feature isolation
# ---------------------------------------------------------------------------


def test_verification_does_not_affect_acceptance_record() -> None:
    ctrl = _chain_with_record()
    record_before = ctrl.last_acceptance_record
    ctrl.run_acceptance_verification()
    assert ctrl.last_acceptance_record is record_before


def test_verification_does_not_affect_approval_readiness() -> None:
    ctrl = _chain_with_record()
    readiness_before = ctrl.last_approval_readiness
    ctrl.run_acceptance_verification()
    assert ctrl.last_approval_readiness is readiness_before


def test_closure_does_not_affect_acceptance_record() -> None:
    ctrl = _chain_with_verification()
    record_before = ctrl.last_acceptance_record
    ctrl.run_acceptance_closure()
    assert ctrl.last_acceptance_record is record_before


def test_closure_does_not_mutate_v5_acceptance_state() -> None:
    ctrl = _chain_with_verification()
    state_before = ctrl.acceptance_state
    ctrl.run_acceptance_closure()
    assert ctrl.acceptance_state == state_before


def test_closure_does_not_affect_verification_envelope() -> None:
    ctrl = _chain_with_verification()
    envelope_before = ctrl.last_acceptance_verification
    ctrl.run_acceptance_closure()
    assert ctrl.last_acceptance_verification is envelope_before


# ---------------------------------------------------------------------------
# Error handling — malformed inputs fail closed
# ---------------------------------------------------------------------------


def test_verification_fails_closed_without_valid_record() -> None:
    ctrl = _make_full_chain()
    ctrl.run_acceptance_handoff()
    with pytest.raises(InvalidToleranceWorkspaceError, match="Acceptance Record"):
        ctrl.run_acceptance_verification()


def test_closure_fails_closed_without_verification() -> None:
    ctrl = _chain_with_record()
    with pytest.raises(
        InvalidToleranceWorkspaceError, match="Verify Acceptance Record"
    ):
        ctrl.run_acceptance_closure()
