"""Stage 15V deterministic acceptance verification-envelope tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError, replace

import pytest

import origlyph.tolerance.acceptance_verification as verification_module
from origlyph.tolerance import (
    ACCEPTANCE_RECORD_SCHEMA_VERSION,
    ACCEPTANCE_VERIFICATION_SCHEMA_VERSION,
    AuditAcceptanceDecision,
    AuditAcceptanceRecord,
    AuditAcceptanceVerificationEnvelope,
    AuditAcceptanceVerificationFact,
    AuditAcceptanceVerificationStatus,
    InvalidAuditAcceptanceVerificationError,
    build_acceptance_record_verification_envelope,
    validate_audit_acceptance_record,
)
from origlyph.tolerance.acceptance_handoff import build_audit_acceptance_handoff
from origlyph.tolerance.approval_readiness import evaluate_audit_approval_readiness
from origlyph.tolerance.change_disposition import determine_audit_change_disposition
from origlyph.tolerance.change_impact import assess_audit_change_impact
from origlyph.tolerance.comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
    AuditPackageComparisonResult,
)


def _handoff(kind: str = "ready"):
    status = AuditComparisonStatus.IDENTICAL
    changes: tuple[AuditChange, ...] = ()
    if kind == "action":
        status = AuditComparisonStatus.CHANGED
        changes = (
            AuditChange(
                code=AuditChangeCode.INPUT_METRIC_CHANGED,
                category=AuditChangeCategory.INPUT,
                scope="fixture",
                subject_id="subject",
                field_path="field",
                baseline_value="old",
                candidate_value="new",
                significance=AuditChangeSignificance.ENGINEERING_RELEVANT,
                detail="deterministic fixture",
            ),
        )
    elif kind == "blocked":
        status = AuditComparisonStatus.INCOMPATIBLE
        changes = (
            AuditChange(
                code=AuditChangeCode.AUDIT_SCHEMA_CHANGED,
                category=AuditChangeCategory.SCHEMA,
                scope="fixture",
                subject_id="subject",
                field_path="field",
                baseline_value="old",
                candidate_value="new",
                significance=AuditChangeSignificance.INCOMPATIBLE,
                detail="deterministic fixture",
            ),
        )
    comparison = AuditPackageComparisonResult(
        status=status,
        baseline_package_id="baseline-package",
        candidate_package_id="candidate-package",
        changes=changes,
    )
    impact = assess_audit_change_impact(comparison)
    disposition = determine_audit_change_disposition(impact)
    readiness = evaluate_audit_approval_readiness(disposition)
    return build_audit_acceptance_handoff(
        comparison,
        impact,
        disposition,
        readiness,
    )


def _validated(kind="ready", decision=AuditAcceptanceDecision.APPROVED):
    handoff = _handoff(kind)
    external = AuditAcceptanceRecord(
        schema_version=ACCEPTANCE_RECORD_SCHEMA_VERSION,
        handoff_id=handoff.handoff_id,
        decision=decision,
        authority_reference="authority:governance-board",
        decision_reference="decision:2026-0042",
    )
    return handoff, validate_audit_acceptance_record(handoff, external)


def _refingerprint(record, **changes):
    changed = replace(record, **changes)
    payload = changed.as_dict()
    payload.pop("acceptance_record_id")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return replace(
        changed,
        acceptance_record_id=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def test_public_api_schema_status_and_facts_are_stable() -> None:
    assert callable(build_acceptance_record_verification_envelope)
    assert ACCEPTANCE_VERIFICATION_SCHEMA_VERSION == (
        "origlyph.tolerance.audit_acceptance_verification.v1"
    )
    assert AuditAcceptanceVerificationStatus.VERIFIED_BINDING.value == (
        "verified_binding"
    )
    assert len(AuditAcceptanceVerificationFact) == 4


@pytest.mark.parametrize("decision", list(AuditAcceptanceDecision))
def test_ready_records_build_verification_envelope(decision) -> None:
    handoff, record = _validated(decision=decision)
    envelope = build_acceptance_record_verification_envelope(handoff, record)
    assert envelope.status is AuditAcceptanceVerificationStatus.VERIFIED_BINDING
    assert envelope.decision is decision


@pytest.mark.parametrize("kind", ["action", "blocked"])
@pytest.mark.parametrize(
    "decision",
    [
        AuditAcceptanceDecision.REJECTED,
        AuditAcceptanceDecision.RETURNED_FOR_ACTION,
    ],
)
def test_nonready_validated_records_build_verification_envelope(
    kind, decision
) -> None:
    handoff, record = _validated(kind, decision)
    assert build_acceptance_record_verification_envelope(
        handoff, record
    ).decision is decision


def test_traceability_fields_are_preserved_exactly() -> None:
    handoff, record = _validated()
    envelope = build_acceptance_record_verification_envelope(handoff, record)
    assert envelope.handoff_id == handoff.handoff_id
    assert envelope.acceptance_record_id == record.acceptance_record_id
    assert envelope.decision is record.decision
    assert envelope.authority_reference == record.authority_reference
    assert envelope.decision_reference == record.decision_reference


def test_verification_facts_have_canonical_order() -> None:
    handoff, record = _validated()
    facts = build_acceptance_record_verification_envelope(
        handoff, record
    ).verification_facts
    assert facts == (
        AuditAcceptanceVerificationFact.HANDOFF_FINGERPRINT_MATCH,
        AuditAcceptanceVerificationFact.ACCEPTANCE_RECORD_FINGERPRINT_MATCH,
        AuditAcceptanceVerificationFact.HANDOFF_BINDING_MATCH,
        AuditAcceptanceVerificationFact.REFERENCE_CONTENT_PRESERVED,
    )


def test_as_dict_and_json_are_canonical() -> None:
    handoff, record = _validated()
    envelope = build_acceptance_record_verification_envelope(handoff, record)
    assert envelope.to_json() == json.dumps(
        envelope.as_dict(),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def test_repeated_envelope_and_identity_are_identical() -> None:
    handoff, record = _validated()
    first = build_acceptance_record_verification_envelope(handoff, record)
    second = build_acceptance_record_verification_envelope(handoff, record)
    assert first == second
    assert first.envelope_id == second.envelope_id
    assert len(first.envelope_id) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_reference", "authority:other"),
        ("decision_reference", "decision:other"),
    ],
)
def test_envelope_identity_changes_with_preserved_reference(field, value) -> None:
    handoff, record = _validated()
    first = build_acceptance_record_verification_envelope(handoff, record)
    changed = _refingerprint(record, **{field: value})
    second = build_acceptance_record_verification_envelope(handoff, changed)
    assert first.envelope_id != second.envelope_id


@pytest.mark.parametrize("bad_index", [0, 1])
def test_wrong_input_types_are_rejected(bad_index) -> None:
    handoff, record = _validated()
    args = [handoff, record]
    args[bad_index] = object()
    with pytest.raises(InvalidAuditAcceptanceVerificationError):
        build_acceptance_record_verification_envelope(*args)  # type: ignore[arg-type]


def test_handoff_mismatch_is_rejected() -> None:
    ready, _ = _validated()
    _, action_record = _validated("action", AuditAcceptanceDecision.REJECTED)
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="not bound"):
        build_acceptance_record_verification_envelope(ready, action_record)


@pytest.mark.parametrize("handoff_id", ["", "a" * 63, "A" * 64, "g" * 64])
def test_malformed_handoff_id_is_rejected(handoff_id) -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="lowercase"):
        build_acceptance_record_verification_envelope(
            replace(handoff, handoff_id=handoff_id), record
        )


@pytest.mark.parametrize("record_id", ["", "a" * 63, "A" * 64, "g" * 64])
def test_malformed_acceptance_record_id_is_rejected(record_id) -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="lowercase"):
        build_acceptance_record_verification_envelope(
            handoff, replace(record, acceptance_record_id=record_id)
        )


def test_unsupported_handoff_schema_is_rejected() -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="handoff schema"):
        build_acceptance_record_verification_envelope(
            replace(handoff, schema_version="future"), record
        )


def test_unsupported_validated_record_schema_is_rejected() -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="validated"):
        build_acceptance_record_verification_envelope(
            handoff, replace(record, schema_version="future")
        )


def test_unsupported_external_record_schema_is_rejected() -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="external"):
        build_acceptance_record_verification_envelope(
            handoff,
            replace(record, acceptance_record_schema_version="future"),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_reference", ""),
        ("authority_reference", " padded"),
        ("decision_reference", ""),
        ("decision_reference", "padded "),
    ],
)
def test_invalid_reference_content_is_rejected(field, value) -> None:
    handoff, record = _validated()
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match=field):
        build_acceptance_record_verification_envelope(
            handoff, replace(record, **{field: value})
        )


def test_changed_record_content_with_stale_identity_is_rejected() -> None:
    handoff, record = _validated()
    changed = replace(record, decision_reference="decision:changed")
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="fingerprint"):
        build_acceptance_record_verification_envelope(handoff, changed)


def test_forged_handoff_identity_is_rejected() -> None:
    handoff, record = _validated()
    forged = replace(handoff, handoff_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="fingerprint"):
        build_acceptance_record_verification_envelope(forged, record)


def test_forged_acceptance_record_identity_is_rejected() -> None:
    handoff, record = _validated()
    forged = replace(record, acceptance_record_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="fingerprint"):
        build_acceptance_record_verification_envelope(handoff, forged)


def test_record_handoff_status_mismatch_is_rejected() -> None:
    handoff, record = _validated()
    changed = _refingerprint(
        record,
        handoff_status=handoff.status.ACTION_REQUIRED,
    )
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="status"):
        build_acceptance_record_verification_envelope(handoff, changed)


def test_impossible_approved_nonready_record_is_rejected() -> None:
    handoff, record = _validated("action", AuditAcceptanceDecision.REJECTED)
    changed = _refingerprint(record, decision=AuditAcceptanceDecision.APPROVED)
    with pytest.raises(InvalidAuditAcceptanceVerificationError, match="impossible"):
        build_acceptance_record_verification_envelope(handoff, changed)


def test_inputs_are_not_mutated() -> None:
    handoff, record = _validated()
    before = (handoff.to_json(), record.to_json())
    build_acceptance_record_verification_envelope(handoff, record)
    assert (handoff.to_json(), record.to_json()) == before


def test_envelope_is_immutable() -> None:
    handoff, record = _validated()
    envelope = build_acceptance_record_verification_envelope(handoff, record)
    assert isinstance(envelope, AuditAcceptanceVerificationEnvelope)
    with pytest.raises(FrozenInstanceError):
        envelope.status = (  # type: ignore[misc]
            AuditAcceptanceVerificationStatus.VERIFIED_BINDING
        )


def test_no_actor_signature_or_authority_claim_fields() -> None:
    fields = AuditAcceptanceVerificationEnvelope.__dataclass_fields__
    prohibited = {
        "timestamp",
        "reviewer",
        "approver",
        "signature",
        "human_identity_verified",
        "legal_authority_verified",
        "authorization_verified",
        "non_repudiation_verified",
    }
    assert prohibited.isdisjoint(fields)


def test_no_clock_random_uuid_or_environment_sources() -> None:
    source = inspect.getsource(verification_module)
    prohibited = ("datetime", "time.time", "uuid", "random", "getenv", "cwd")
    assert not any(item in source for item in prohibited)


def test_no_upstream_stage_or_engine_invocations() -> None:
    source = inspect.getsource(verification_module)
    prohibited_calls = (
        "validate_audit_acceptance_record(",
        "build_audit_acceptance_handoff(",
        "evaluate_audit_approval_readiness(",
        "determine_audit_change_disposition(",
        "assess_audit_change_impact(",
        "compare_decision_audit_packages(",
        "build_decision_audit_package(",
        "validate_decision_report_integrity(",
        "worst_case(",
        "statistical(",
        "sensitivity(",
        "budget(",
        "allocation(",
        "reconciliation(",
        "evaluate_tolerance_decision(",
    )
    assert not any(call in source for call in prohibited_calls)
