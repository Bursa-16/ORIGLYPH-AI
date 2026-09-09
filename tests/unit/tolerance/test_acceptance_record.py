"""Stage 15U governed acceptance-record intake tests."""

from __future__ import annotations

import inspect
import json
import math
from dataclasses import FrozenInstanceError, replace

import pytest

import origlyph.tolerance.acceptance_record as record_module
from origlyph.tolerance import (
    ACCEPTANCE_RECORD_SCHEMA_VERSION,
    VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION,
    AuditAcceptanceDecision,
    AuditAcceptanceHandoffStatus,
    AuditAcceptanceRecord,
    InvalidAuditAcceptanceRecordError,
    ValidatedAuditAcceptanceRecord,
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


def _record(handoff, decision=AuditAcceptanceDecision.APPROVED):
    return AuditAcceptanceRecord(
        schema_version=ACCEPTANCE_RECORD_SCHEMA_VERSION,
        handoff_id=handoff.handoff_id,
        decision=decision,
        authority_reference="authority:governance-board",
        decision_reference="decision:2026-0042",
    )


def test_public_api_and_schema_versions_are_stable() -> None:
    assert callable(validate_audit_acceptance_record)
    assert ACCEPTANCE_RECORD_SCHEMA_VERSION == (
        "origlyph.tolerance.audit_acceptance_record.v1"
    )
    assert VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION == (
        "origlyph.tolerance.validated_audit_acceptance_record.v1"
    )


@pytest.mark.parametrize("decision", list(AuditAcceptanceDecision))
def test_ready_handoff_accepts_every_explicit_external_decision(decision) -> None:
    handoff = _handoff()
    result = validate_audit_acceptance_record(handoff, _record(handoff, decision))
    assert result.decision is decision
    assert result.handoff_status is (
        AuditAcceptanceHandoffStatus.READY_FOR_GOVERNED_ACCEPTANCE
    )


@pytest.mark.parametrize("kind", ["action", "blocked"])
@pytest.mark.parametrize(
    "decision",
    [
        AuditAcceptanceDecision.REJECTED,
        AuditAcceptanceDecision.RETURNED_FOR_ACTION,
    ],
)
def test_nonready_handoff_accepts_nonapproval_decisions(kind, decision) -> None:
    handoff = _handoff(kind)
    assert validate_audit_acceptance_record(
        handoff, _record(handoff, decision)
    ).decision is decision


@pytest.mark.parametrize("kind", ["action", "blocked"])
def test_nonready_handoff_rejects_approved_decision(kind) -> None:
    handoff = _handoff(kind)
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="conflicts"):
        validate_audit_acceptance_record(handoff, _record(handoff))


def test_record_is_bound_to_exact_handoff_id() -> None:
    handoff = _handoff()
    result = validate_audit_acceptance_record(handoff, _record(handoff))
    assert result.handoff_id == handoff.handoff_id


def test_mismatched_handoff_id_is_rejected() -> None:
    handoff = _handoff()
    record = replace(_record(handoff), handoff_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="not bound"):
        validate_audit_acceptance_record(handoff, record)


@pytest.mark.parametrize("handoff_id", ["", "abc", "A" * 64, "g" * 64])
def test_empty_or_malformed_record_handoff_id_is_rejected(handoff_id) -> None:
    handoff = _handoff()
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="lowercase SHA-256"):
        validate_audit_acceptance_record(
            handoff,
            replace(_record(handoff), handoff_id=handoff_id),
        )


def test_external_references_are_preserved_as_opaque_values() -> None:
    handoff = _handoff()
    record = replace(
        _record(handoff),
        authority_reference="external-system://authority/7",
        decision_reference="external-system://decision/99",
    )
    result = validate_audit_acceptance_record(handoff, record)
    assert result.authority_reference == record.authority_reference
    assert result.decision_reference == record.decision_reference


@pytest.mark.parametrize("value", ["", " ", " padded"])
def test_empty_or_noncanonical_authority_reference_is_rejected(value) -> None:
    handoff = _handoff()
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="authority_reference"):
        validate_audit_acceptance_record(
            handoff,
            replace(_record(handoff), authority_reference=value),
        )


@pytest.mark.parametrize("value", ["", " ", "padded "])
def test_empty_or_noncanonical_decision_reference_is_rejected(value) -> None:
    handoff = _handoff()
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="decision_reference"):
        validate_audit_acceptance_record(
            handoff,
            replace(_record(handoff), decision_reference=value),
        )


@pytest.mark.parametrize("decision", ["", "approved", object()])
def test_unknown_or_untyped_decision_is_rejected(decision) -> None:
    handoff = _handoff()
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="decision is invalid"):
        validate_audit_acceptance_record(
            handoff,
            replace(_record(handoff), decision=decision),  # type: ignore[arg-type]
        )


def test_unsupported_record_schema_is_rejected() -> None:
    handoff = _handoff()
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="record schema"):
        validate_audit_acceptance_record(
            handoff,
            replace(_record(handoff), schema_version="future"),
        )


def test_unsupported_handoff_schema_is_rejected() -> None:
    handoff = replace(_handoff(), schema_version="future")
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="handoff schema"):
        validate_audit_acceptance_record(handoff, _record(handoff))


@pytest.mark.parametrize("bad_index", [0, 1])
def test_wrong_input_types_are_rejected(bad_index) -> None:
    handoff = _handoff()
    args = [handoff, _record(handoff)]
    args[bad_index] = object()
    with pytest.raises(InvalidAuditAcceptanceRecordError):
        validate_audit_acceptance_record(*args)  # type: ignore[arg-type]


def test_external_record_serialization_is_canonical() -> None:
    handoff = _handoff()
    record = _record(handoff)
    assert record.to_json() == json.dumps(
        record.as_dict(),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def test_validated_result_serialization_is_canonical() -> None:
    handoff = _handoff()
    result = validate_audit_acceptance_record(handoff, _record(handoff))
    assert result.to_json() == json.dumps(
        result.as_dict(),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def test_repeated_intake_and_fingerprint_are_identical() -> None:
    handoff = _handoff()
    first = validate_audit_acceptance_record(handoff, _record(handoff))
    second = validate_audit_acceptance_record(handoff, _record(handoff))
    assert first == second
    assert first.acceptance_record_id == second.acceptance_record_id
    assert len(first.acceptance_record_id) == 64


def test_fingerprint_changes_with_external_decision_reference() -> None:
    handoff = _handoff()
    first = validate_audit_acceptance_record(handoff, _record(handoff))
    changed = replace(_record(handoff), decision_reference="decision:other")
    second = validate_audit_acceptance_record(handoff, changed)
    assert first.acceptance_record_id != second.acceptance_record_id


def test_inputs_are_not_mutated() -> None:
    handoff = _handoff()
    record = _record(handoff)
    before = (handoff.to_json(), record.to_json())
    validate_audit_acceptance_record(handoff, record)
    assert (handoff.to_json(), record.to_json()) == before


def test_external_record_is_immutable() -> None:
    handoff = _handoff()
    record = _record(handoff)
    with pytest.raises(FrozenInstanceError):
        record.decision = AuditAcceptanceDecision.REJECTED  # type: ignore[misc]


def test_validated_result_is_immutable() -> None:
    handoff = _handoff()
    result = validate_audit_acceptance_record(handoff, _record(handoff))
    assert isinstance(result, ValidatedAuditAcceptanceRecord)
    with pytest.raises(FrozenInstanceError):
        result.decision = AuditAcceptanceDecision.REJECTED  # type: ignore[misc]


@pytest.mark.parametrize("handoff_id", ["", "f" * 63, "F" * 64])
def test_malformed_handoff_package_identity_is_rejected(handoff_id) -> None:
    handoff = replace(_handoff(), handoff_id=handoff_id)
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="lowercase SHA-256"):
        validate_audit_acceptance_record(handoff, _record(handoff))


def test_forged_handoff_fingerprint_is_rejected() -> None:
    source = _handoff()
    forged = replace(source, handoff_id="0" * 64)
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="fingerprint"):
        validate_audit_acceptance_record(forged, _record(forged))


def test_nonfinite_handoff_content_is_rejected() -> None:
    handoff = _handoff("action")
    comparison = handoff.comparison_result
    bad_change = replace(comparison.changes[0], baseline_value=math.nan)
    malformed = replace(
        handoff,
        comparison_result=replace(comparison, changes=(bad_change,)),
    )
    with pytest.raises(InvalidAuditAcceptanceRecordError, match="canonical JSON"):
        validate_audit_acceptance_record(malformed, _record(malformed))


def test_no_approval_or_identity_claim_fields_are_generated() -> None:
    fields = ValidatedAuditAcceptanceRecord.__dataclass_fields__
    prohibited = {
        "timestamp",
        "reviewer",
        "approver",
        "signature",
        "actor_id",
        "identity_verified",
        "authority_verified",
    }
    assert prohibited.isdisjoint(fields)


def test_decision_has_no_default_or_inference_path() -> None:
    field = AuditAcceptanceRecord.__dataclass_fields__["decision"]
    assert field.default is field.default_factory


def test_no_clock_random_uuid_or_environment_sources() -> None:
    source = inspect.getsource(record_module)
    prohibited = ("datetime", "time.time", "uuid", "random", "getenv", "cwd")
    assert not any(item in source for item in prohibited)


def test_no_upstream_stage_or_engine_invocations() -> None:
    source = inspect.getsource(record_module)
    prohibited_calls = (
        "compare_decision_audit_packages(",
        "assess_audit_change_impact(",
        "determine_audit_change_disposition(",
        "evaluate_audit_approval_readiness(",
        "build_audit_acceptance_handoff(",
        "build_decision_audit_package(",
        "validate_decision_report_integrity(",
        "worst_case(",
        "statistical(",
        "sensitivity(",
        "budget(",
        "allocation(",
        "reconciliation(",
        "evaluate_tolerance_decision(",
        "build_decision_evidence(",
    )
    assert not any(call in source for call in prohibited_calls)
