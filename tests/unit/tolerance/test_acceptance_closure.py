from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError, replace

import pytest

import origlyph.tolerance.acceptance_closure as closure_module
from origlyph.tolerance import (
    ACCEPTANCE_CLOSURE_SCHEMA_VERSION,
    ACCEPTANCE_RECORD_SCHEMA_VERSION,
    AuditAcceptanceClosureManifest,
    AuditAcceptanceClosureStatus,
    AuditAcceptanceDecision,
    AuditAcceptanceRecord,
    InvalidAuditAcceptanceClosureError,
    build_acceptance_closure_manifest,
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


def _chain(kind="ready", decision=AuditAcceptanceDecision.APPROVED):
    handoff = _handoff(kind)
    external = AuditAcceptanceRecord(
        schema_version=ACCEPTANCE_RECORD_SCHEMA_VERSION,
        handoff_id=handoff.handoff_id,
        decision=decision,
        authority_reference="authority:governance-board",
        decision_reference="decision:2026-0042",
    )
    record = validate_audit_acceptance_record(handoff, external)
    envelope = build_acceptance_record_verification_envelope(handoff, record)
    return handoff, record, envelope


def _refingerprint_record(record, **changes):
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


def _refingerprint_envelope(envelope, **changes):
    changed = replace(envelope, **changes)
    payload = changed.as_dict()
    payload.pop("envelope_id")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return replace(
        changed,
        envelope_id=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def test_api_schema_and_status_are_stable() -> None:
    assert callable(build_acceptance_closure_manifest)
    assert ACCEPTANCE_CLOSURE_SCHEMA_VERSION == (
        "origlyph.tolerance.audit_acceptance_closure.v1"
    )
    assert AuditAcceptanceClosureStatus.COMPLETE.value == "complete"
    assert len(AuditAcceptanceClosureStatus) == 1


def test_valid_chain_builds_closure_manifest() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    assert isinstance(manifest, AuditAcceptanceClosureManifest)
    assert manifest.status is AuditAcceptanceClosureStatus.COMPLETE
    assert manifest.schema_version == ACCEPTANCE_CLOSURE_SCHEMA_VERSION
    assert len(manifest.closure_id) == 64


def test_closure_references_are_preserved() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    refs = manifest.references
    assert refs.handoff_id == handoff.handoff_id
    assert refs.handoff_schema_version == handoff.schema_version
    assert refs.handoff_status == handoff.status
    assert refs.acceptance_record_id == record.acceptance_record_id
    assert refs.envelope_id == envelope.envelope_id
    assert refs.decision is record.decision
    assert refs.authority_reference == record.authority_reference
    assert refs.decision_reference == record.decision_reference
    assert refs.verification_status == envelope.status


def test_external_decision_is_preserved_exactly() -> None:
    decisions = list(AuditAcceptanceDecision)
    for decision in decisions:
        kind = "ready"
        if decision is not AuditAcceptanceDecision.APPROVED:
            kind = "action" if decision is AuditAcceptanceDecision.REJECTED else "ready"
        handoff, record, envelope = _chain(kind, decision)
        manifest = build_acceptance_closure_manifest(handoff, record, envelope)
        assert manifest.references.decision is decision


def test_as_dict_and_json_are_canonical() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    as_dict = manifest.as_dict()
    assert as_dict["closure_id"] == manifest.closure_id
    references = as_dict["references"]
    assert isinstance(references, dict)
    assert references["handoff_id"] == handoff.handoff_id
    assert manifest.to_json() == json.dumps(
        as_dict,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def test_repeated_builds_are_identical() -> None:
    handoff, record, envelope = _chain()
    first = build_acceptance_closure_manifest(handoff, record, envelope)
    second = build_acceptance_closure_manifest(handoff, record, envelope)
    assert first == second
    assert first.closure_id == second.closure_id
    assert first.as_dict() == second.as_dict()
    assert first.to_json() == second.to_json()


def test_closure_identity_matches_independent_fingerprint() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    identity = {
        "schema_version": ACCEPTANCE_CLOSURE_SCHEMA_VERSION,
        "status": "complete",
        "references": manifest.references.as_dict(),
    }
    canonical = json.dumps(
        identity,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    assert manifest.closure_id == hashlib.sha256(canonical.encode()).hexdigest()


def test_closure_id_changes_with_reference_content() -> None:
    handoff, record, envelope = _chain()
    first = build_acceptance_closure_manifest(handoff, record, envelope)
    changed_record = _refingerprint_record(
        record, decision_reference="decision:changed"
    )
    changed_envelope = _refingerprint_envelope(
        envelope,
        decision_reference="decision:changed",
        acceptance_record_id=changed_record.acceptance_record_id,
    )
    second = build_acceptance_closure_manifest(
        handoff, changed_record, changed_envelope
    )
    assert first.closure_id != second.closure_id


@pytest.mark.parametrize("slot", [0, 1, 2])
def test_wrong_input_types_are_rejected(slot) -> None:
    handoff, record, envelope = _chain()
    args = [handoff, record, envelope]
    args[slot] = "not-an-artifact"
    with pytest.raises(InvalidAuditAcceptanceClosureError):
        build_acceptance_closure_manifest(*args)  # type: ignore[arg-type]


def test_record_handoff_mismatch_is_rejected() -> None:
    ready, _, _ = _chain()
    _, action_record, _ = _chain("action", AuditAcceptanceDecision.REJECTED)
    _, _, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="handoff_id mismatch"):
        build_acceptance_closure_manifest(ready, action_record, envelope)


def test_envelope_record_mismatch_is_rejected() -> None:
    handoff, record, envelope = _chain()
    stale_record = _refingerprint_record(record, decision_reference="decision:stale")
    with pytest.raises(
        InvalidAuditAcceptanceClosureError, match="acceptance_record_id mismatch"
    ):
        build_acceptance_closure_manifest(handoff, stale_record, envelope)


@pytest.mark.parametrize("handoff_id", ["", "a" * 63, "A" * 64, "g" * 64])
def test_malformed_handoff_id_is_rejected(handoff_id) -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="lowercase"):
        build_acceptance_closure_manifest(
            replace(handoff, handoff_id=handoff_id), record, envelope
        )


@pytest.mark.parametrize("record_id", ["", "a" * 63, "A" * 64, "g" * 64])
def test_malformed_acceptance_record_id_is_rejected(record_id) -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="lowercase"):
        build_acceptance_closure_manifest(
            handoff, replace(record, acceptance_record_id=record_id), envelope
        )


@pytest.mark.parametrize("envelope_id", ["", "a" * 63, "A" * 64, "g" * 64])
def test_malformed_envelope_id_is_rejected(envelope_id) -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="lowercase"):
        build_acceptance_closure_manifest(
            handoff, record, replace(envelope, envelope_id=envelope_id)
        )

    with pytest.raises(InvalidAuditAcceptanceClosureError):
        build_acceptance_closure_manifest(
            handoff,
            "not-a-valid-record",  # type: ignore[arg-type]
            envelope,
        )


def test_unsupported_handoff_schema_is_rejected() -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="handoff schema"):
        build_acceptance_closure_manifest(
            replace(handoff, schema_version="future"), record, envelope
        )


def test_unsupported_record_schema_is_rejected() -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="validated"):
        build_acceptance_closure_manifest(
            handoff, replace(record, schema_version="future"), envelope
        )


def test_unsupported_external_schema_is_rejected() -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="fingerprint"):
        build_acceptance_closure_manifest(
            handoff,
            replace(record, acceptance_record_schema_version="future"),
            envelope,
        )


def test_unsupported_envelope_schema_is_rejected() -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(
        InvalidAuditAcceptanceClosureError, match="verification envelope schema"
    ):
        build_acceptance_closure_manifest(
            handoff, record, replace(envelope, schema_version="future")
        )


def test_unverified_envelope_is_rejected() -> None:
    handoff, record, envelope = _chain()
    forged = replace(envelope, status=None)  # type: ignore[arg-type]
    with pytest.raises(InvalidAuditAcceptanceClosureError):
        build_acceptance_closure_manifest(handoff, record, forged)


def test_forged_handoff_identity_is_rejected() -> None:
    handoff, record, envelope = _chain()
    forged = replace(handoff, handoff_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="fingerprint"):
        build_acceptance_closure_manifest(forged, record, envelope)


def test_changed_record_content_with_stale_identity_is_rejected() -> None:
    handoff, record, envelope = _chain()
    changed = replace(record, decision_reference="decision:changed")
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="fingerprint"):
        build_acceptance_closure_manifest(handoff, changed, envelope)


def test_forged_envelope_identity_is_rejected() -> None:
    handoff, record, envelope = _chain()
    forged = replace(envelope, envelope_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="fingerprint"):
        build_acceptance_closure_manifest(handoff, record, forged)


def test_contradictory_envelope_decision_is_rejected() -> None:
    handoff, record, envelope = _chain()
    if record.decision is AuditAcceptanceDecision.APPROVED:
        other = AuditAcceptanceDecision.REJECTED
    else:
        other = AuditAcceptanceDecision.APPROVED
    forged_envelope = _refingerprint_envelope(envelope, decision=other)
    with pytest.raises(
        InvalidAuditAcceptanceClosureError, match="contradictory decision"
    ):
        build_acceptance_closure_manifest(handoff, record, forged_envelope)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_reference", "authority:other"),
        ("decision_reference", "decision:other"),
    ],
)
def test_contradictory_envelope_references_are_rejected(field, value) -> None:
    handoff, record, envelope = _chain()
    forged_envelope = _refingerprint_envelope(envelope, **{field: value})
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="contradictory"):
        build_acceptance_closure_manifest(handoff, record, forged_envelope)


def test_invalid_handoff_status_type_is_rejected() -> None:
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="handoff status"):
        build_acceptance_closure_manifest(
            replace(handoff, status=None),  # type: ignore[arg-type]
            record,
            envelope,
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
    handoff, record, envelope = _chain()
    with pytest.raises(InvalidAuditAcceptanceClosureError, match=field):
        build_acceptance_closure_manifest(
            handoff, replace(record, **{field: value}), envelope
        )


def test_record_handoff_status_mismatch_is_rejected() -> None:
    handoff, record, envelope = _chain()
    changed = _refingerprint_record(
        record,
        handoff_status=(
            handoff.status.ACTION_REQUIRED
            if handoff.status is not handoff.status.ACTION_REQUIRED
            else handoff.status.BLOCKED
        ),
    )
    changed_envelope = _refingerprint_envelope(
        envelope, acceptance_record_id=changed.acceptance_record_id
    )
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="status"):
        build_acceptance_closure_manifest(handoff, changed, changed_envelope)


def test_inputs_are_not_mutated() -> None:
    handoff, record, envelope = _chain()
    before = (handoff.to_json(), record.to_json(), envelope.to_json())
    build_acceptance_closure_manifest(handoff, record, envelope)
    assert (handoff.to_json(), record.to_json(), envelope.to_json()) == before


def test_closure_manifest_is_immutable() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    assert isinstance(manifest, AuditAcceptanceClosureManifest)
    with pytest.raises(FrozenInstanceError):
        manifest.status = (  # type: ignore[misc]
            AuditAcceptanceClosureStatus.COMPLETE
        )


def test_closure_reference_is_immutable() -> None:
    handoff, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    with pytest.raises(FrozenInstanceError):
        manifest.references.envelope_id = "0" * 64  # type: ignore[misc]


def test_no_clock_random_uuid_or_environment_sources() -> None:
    source = inspect.getsource(closure_module)
    prohibited = ("datetime", "time.time", "uuid", "random", "getenv", "cwd")
    assert not any(item in source for item in prohibited)


def test_no_upstream_stage_or_engine_invocations() -> None:
    source = inspect.getsource(closure_module)
    prohibited_calls = (
        "build_acceptance_record_verification_envelope(",
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


def test_stage_15t_chain_still_builds_and_closes() -> None:
    handoff = _handoff()
    assert handoff.schema_version
    handoff2, record, envelope = _chain()
    manifest = build_acceptance_closure_manifest(handoff2, record, envelope)
    assert manifest.status is AuditAcceptanceClosureStatus.COMPLETE


def test_stage_15u_acceptance_record_still_validates() -> None:
    handoff = _handoff()
    external = AuditAcceptanceRecord(
        schema_version=ACCEPTANCE_RECORD_SCHEMA_VERSION,
        handoff_id=handoff.handoff_id,
        decision=AuditAcceptanceDecision.REJECTED,
        authority_reference="authority:governance-board",
        decision_reference="decision:2026-0042",
    )
    record = validate_audit_acceptance_record(handoff, external)
    assert record.decision is AuditAcceptanceDecision.REJECTED


def test_stage_15v_envelope_still_builds() -> None:
    handoff, record, envelope = _chain()
    rebuilt = build_acceptance_record_verification_envelope(handoff, record)
    assert rebuilt.envelope_id == envelope.envelope_id


def test_blocked_chain_still_closes() -> None:
    handoff, record, envelope = _chain("blocked", AuditAcceptanceDecision.REJECTED)
    manifest = build_acceptance_closure_manifest(handoff, record, envelope)
    assert manifest.references.decision is AuditAcceptanceDecision.REJECTED
    assert manifest.to_json()


def test_no_actor_signature_or_authority_claim_fields() -> None:
    fields = AuditAcceptanceClosureManifest.__dataclass_fields__
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


def test_forged_record_identity_is_rejected() -> None:
    handoff, record, envelope = _chain()
    forged = replace(record, acceptance_record_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="fingerprint"):
        build_acceptance_closure_manifest(handoff, forged, envelope)


@pytest.mark.parametrize("kind", ["action", "blocked"])
def test_refingerprinted_impossible_approval_is_rejected(kind) -> None:
    handoff, record, envelope = _chain(kind, AuditAcceptanceDecision.REJECTED)
    record = _refingerprint_record(record, decision=AuditAcceptanceDecision.APPROVED)
    envelope = _refingerprint_envelope(
        envelope,
        decision=record.decision,
        acceptance_record_id=record.acceptance_record_id,
    )
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="approved decision"):
        build_acceptance_closure_manifest(handoff, record, envelope)


@pytest.mark.parametrize(
    "variant", ["empty", "missing", "duplicate", "reordered", "list"]
)
def test_noncanonical_verification_facts_are_rejected(variant) -> None:
    handoff, record, envelope = _chain()
    facts = envelope.verification_facts
    variants = {
        "empty": (),
        "missing": facts[:-1],
        "duplicate": facts + facts[:1],
        "reordered": tuple(reversed(facts)),
        "list": list(facts),
    }
    envelope = _refingerprint_envelope(envelope, verification_facts=variants[variant])
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="verification facts"):
        build_acceptance_closure_manifest(handoff, record, envelope)


def test_refingerprinted_unsupported_external_schema_is_rejected() -> None:
    handoff, record, envelope = _chain()
    record = _refingerprint_record(record, acceptance_record_schema_version="future")
    with pytest.raises(InvalidAuditAcceptanceClosureError, match="external"):
        build_acceptance_closure_manifest(handoff, record, envelope)
