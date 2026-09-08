"""Stage 15O deterministic audit-package and replay-manifest tests."""

from __future__ import annotations

import importlib
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from origlyph.tolerance import (
    REPORT_SCHEMA_VERSION,
    DecisionEvidenceSource,
    DecisionProvenance,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceContribution,
    ToleranceDecisionReasonCode,
    ToleranceDecisionReport,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    ToleranceStack,
    build_decision_evidence,
    build_decision_report,
    evaluate_tolerance_decision,
    explain_tolerance_decision,
)
from origlyph.tolerance.audit import (
    AUDIT_PACKAGE_SCHEMA_VERSION,
    DecisionReplayManifest,
    InvalidDecisionAuditPackageError,
    ReplayabilityStatus,
    ToleranceDecisionAuditPackage,
    audit_package_from_dict,
    build_decision_audit_package,
    verify_decision_audit_package,
)
from origlyph.tolerance.integrity import (
    AuditIntegrityResult,
    AuditIntegritySeverity,
    AuditIntegrityStatus,
    AuditIntegrityViolation,
    AuditIntegrityViolationCode,
    validate_decision_report_integrity,
)

_SECTION_ORDER = tuple(ReportSection)


def _minimal_report(
    *,
    status: ToleranceDecisionStatus = ToleranceDecisionStatus.PASS,
    summary_code: str = "pass:within_limits",
    provenance: DecisionProvenance | None = None,
) -> ToleranceDecisionReport:
    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=status,
        is_complete=True,
        summary_code=summary_code,
        summary_text="Deterministic report.",
        governing_reason_codes=(),
        marginal_reason_codes=(),
        supporting_reason_codes=(),
        triggered_reasons=(),
        contributors=(),
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=(),
        equality_tolerance=1e-9,
        section_order=_SECTION_ORDER,
        provenance=provenance,
    )


def _full_report(*, fail: bool = False) -> ToleranceDecisionReport:
    stack = ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )
    decision = evaluate_tolerance_decision(
        worst_case_stack=stack,
        allowed_worst_case_span=0.40 if fail else 0.50,
    )
    evidence = build_decision_evidence(decision)
    explanation = explain_tolerance_decision(decision, evidence)
    return build_decision_report(decision, evidence, explanation)


def _invalid_integrity() -> AuditIntegrityResult:
    violation = AuditIntegrityViolation(
        code=AuditIntegrityViolationCode.STATUS_MISMATCH,
        severity=AuditIntegritySeverity.ERROR,
        scope="report.summary_code",
        subject="test",
        detail="deliberate test violation",
    )
    return AuditIntegrityResult(
        status=AuditIntegrityStatus.INVALID, violations=(violation,)
    )


def test_valid_package_construction() -> None:
    package = build_decision_audit_package(_minimal_report())
    assert isinstance(package, ToleranceDecisionAuditPackage)
    assert package.integrity_result.status is AuditIntegrityStatus.VALID


def test_audit_schema_version_is_stable() -> None:
    assert AUDIT_PACKAGE_SCHEMA_VERSION == "origlyph.tolerance.audit_package.v1"


def test_package_id_is_deterministic() -> None:
    first = build_decision_audit_package(_full_report())
    second = build_decision_audit_package(_full_report())
    assert first.package_id == second.package_id
    assert len(first.package_id) == 64


def test_provenance_does_not_change_deterministic_identity() -> None:
    report = _minimal_report()
    first = build_decision_audit_package(
        report,
        provenance=DecisionProvenance(
            generated_by="actor-a", generation_timestamp="2026-01-01T00:00:00Z"
        ),
    )
    second = build_decision_audit_package(
        report,
        provenance=DecisionProvenance(
            generated_by="actor-b", generation_timestamp="2030-01-01T00:00:00Z"
        ),
    )
    assert first.package_id == second.package_id
    assert first.replay_manifest.input_fingerprint == (
        second.replay_manifest.input_fingerprint
    )
    assert first.replay_manifest.report_fingerprint == (
        second.replay_manifest.report_fingerprint
    )
    assert first.replay_manifest.integrity_fingerprint == (
        second.replay_manifest.integrity_fingerprint
    )


def test_report_change_changes_package_id() -> None:
    report = _minimal_report()
    changed = replace(report, summary_text="Meaningfully changed report.")
    assert build_decision_audit_package(report).package_id != (
        build_decision_audit_package(changed).package_id
    )


def test_integrity_change_changes_package_id() -> None:
    report = _minimal_report()
    valid = build_decision_audit_package(report)
    invalid = build_decision_audit_package(report, _invalid_integrity())
    assert valid.package_id != invalid.package_id


def test_fingerprints_are_stable_sha256_values() -> None:
    first = build_decision_audit_package(_full_report())
    second = build_decision_audit_package(_full_report())
    for name in (
        "input_fingerprint",
        "report_fingerprint",
        "integrity_fingerprint",
    ):
        left = getattr(first.replay_manifest, name)
        right = getattr(second.replay_manifest, name)
        assert left == right
        assert len(left) == 64
        int(left, 16)


def test_manifest_contains_required_contract() -> None:
    package = build_decision_audit_package(_full_report())
    manifest = package.replay_manifest
    assert isinstance(manifest, DecisionReplayManifest)
    assert manifest.report_schema_version == REPORT_SCHEMA_VERSION
    assert manifest.audit_schema_version == AUDIT_PACKAGE_SCHEMA_VERSION
    assert manifest.decision_id == package.report.decision_id()
    assert manifest.package_id == package.package_id
    assert manifest.equality_tolerance == package.report.equality_tolerance
    assert manifest.require_complete_policy == "not_recorded_by_report_schema_v1"
    assert manifest.policy_identifiers
    assert manifest.is_complete


def test_correlation_assumptions_are_canonical() -> None:
    report = replace(
        _minimal_report(),
        correlation_metrics=(
            ReportMetricValue("correlation.B.C", -0.25, -1.0, 1.0),
            ReportMetricValue("correlation.A.B", 0.5, -1.0, 1.0),
        ),
    )
    manifest = build_decision_audit_package(report).replay_manifest
    assert manifest.correlation_assumptions == (
        ("correlation.A.B", 0.5),
        ("correlation.B.C", -0.25),
    )


def test_valid_integrity_is_replayable() -> None:
    package = build_decision_audit_package(_minimal_report())
    assert package.replayability_status is ReplayabilityStatus.REPLAYABLE
    assert package.is_replayable
    assert verify_decision_audit_package(package) is ReplayabilityStatus.REPLAYABLE


def test_engineering_fail_can_be_structurally_replayable() -> None:
    reason_code = ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    evidence_id = "worst_case:wc_span_exceeds_limit:requirement:limit:000"
    report = replace(
        _minimal_report(
            status=ToleranceDecisionStatus.FAIL,
            summary_code="fail:wc_span_exceeds_limit",
        ),
        governing_reason_codes=(reason_code,),
        triggered_reasons=(
            ReportReasonRef(
                reason_code=reason_code,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope=reason_code,
                detail="worst-case requirement exceeded",
                evidence_ids=(evidence_id,),
            ),
        ),
        evidence_refs=(
            ReportEvidenceRef(
                evidence_id=evidence_id,
                source=DecisionEvidenceSource.WORST_CASE.value,
                evidence_code="wc_span_exceeds_limit",
                reason_code=reason_code.value,
            ),
        ),
    )
    package = build_decision_audit_package(report)
    assert package.report.final_status is ToleranceDecisionStatus.FAIL
    assert package.integrity_result.status is AuditIntegrityStatus.VALID
    assert package.is_replayable


def test_invalid_integrity_is_not_replayable() -> None:
    package = build_decision_audit_package(
        _minimal_report(), _invalid_integrity()
    )
    assert package.replayability_status is ReplayabilityStatus.NOT_REPLAYABLE
    assert not package.is_replayable
    assert verify_decision_audit_package(package) is (
        ReplayabilityStatus.NOT_REPLAYABLE
    )


def test_incomplete_manifest_fails_closed() -> None:
    package = build_decision_audit_package(_minimal_report())
    manifest = replace(package.replay_manifest, is_complete=False)
    tampered = replace(package, replay_manifest=manifest)
    assert verify_decision_audit_package(tampered) is ReplayabilityStatus.INCOMPLETE


def test_no_automatic_timestamp_or_random_identifier() -> None:
    package = build_decision_audit_package(_minimal_report())
    assert package.provenance is None
    payload = package.as_dict()
    assert "timestamp" not in payload
    assert "uuid" not in payload


def test_as_dict_and_json_are_deterministic() -> None:
    package = build_decision_audit_package(_full_report())
    assert package.as_dict() == package.as_dict()
    assert package.to_json() == package.to_json()


def test_round_trip_preserves_complete_payload() -> None:
    package = build_decision_audit_package(
        _full_report(), provenance=DecisionProvenance(metadata={"case": "A"})
    )
    rebuilt = audit_package_from_dict(package.as_dict())
    assert rebuilt.as_dict() == package.as_dict()
    assert rebuilt.report.worst_case_metrics == package.report.worst_case_metrics


def test_unsupported_audit_schema_fails_closed() -> None:
    payload = build_decision_audit_package(_minimal_report()).as_dict()
    payload["audit_schema_version"] = "origlyph.tolerance.audit_package.v999"
    with pytest.raises(InvalidDecisionAuditPackageError):
        audit_package_from_dict(payload)


def test_unsupported_report_schema_fails_closed() -> None:
    report = replace(_minimal_report(), schema_version="unsupported")
    with pytest.raises(InvalidDecisionAuditPackageError):
        build_decision_audit_package(report)


def test_package_id_tampering_is_detected() -> None:
    package = build_decision_audit_package(_minimal_report())
    tampered = replace(package, package_id="0" * 64)
    assert verify_decision_audit_package(tampered) is (
        ReplayabilityStatus.NOT_REPLAYABLE
    )
    payload = package.as_dict()
    payload["package_id"] = "0" * 64
    with pytest.raises(InvalidDecisionAuditPackageError):
        audit_package_from_dict(payload)


@pytest.mark.parametrize(
    "field_name",
    ["report_fingerprint", "input_fingerprint", "integrity_fingerprint"],
)
def test_fingerprint_tampering_is_detected(field_name: str) -> None:
    package = build_decision_audit_package(_minimal_report())
    manifest = replace(package.replay_manifest, **{field_name: "0" * 64})
    tampered = replace(package, replay_manifest=manifest)
    assert verify_decision_audit_package(tampered) is (
        ReplayabilityStatus.NOT_REPLAYABLE
    )


def test_malformed_or_unknown_fields_fail_closed() -> None:
    payload = build_decision_audit_package(_minimal_report()).as_dict()
    payload["unknown"] = "not allowed"
    with pytest.raises(InvalidDecisionAuditPackageError):
        audit_package_from_dict(payload)


def test_wrong_input_types_fail_closed() -> None:
    with pytest.raises(InvalidDecisionAuditPackageError):
        build_decision_audit_package("report")  # type: ignore[arg-type]
    with pytest.raises(InvalidDecisionAuditPackageError):
        verify_decision_audit_package("package")  # type: ignore[arg-type]


def test_models_are_frozen() -> None:
    package = build_decision_audit_package(_minimal_report())
    with pytest.raises(FrozenInstanceError):
        package.package_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        package.replay_manifest.is_complete = False  # type: ignore[misc]


def test_packaging_does_not_mutate_inputs() -> None:
    report = _full_report()
    integrity = validate_decision_report_integrity(report)
    provenance = DecisionProvenance(metadata={"nested": [1, 2, 3]})
    report_before = deepcopy(report.as_dict())
    integrity_before = deepcopy(integrity.as_dict())
    provenance_before = deepcopy(provenance.metadata)
    build_decision_audit_package(report, integrity, provenance=provenance)
    assert report.as_dict() == report_before
    assert integrity.as_dict() == integrity_before
    assert provenance.metadata == provenance_before


def test_no_engineering_recomputation(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _full_report()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("authoritative engineering engine was called")

    allocation_module = importlib.import_module("origlyph.tolerance.allocation")
    budget_module = importlib.import_module("origlyph.tolerance.budget")
    decision_module = importlib.import_module("origlyph.tolerance.decision")
    reconciliation_module = importlib.import_module(
        "origlyph.tolerance.reconciliation"
    )
    sensitivity_module = importlib.import_module("origlyph.tolerance.sensitivity")
    statistical_module = importlib.import_module("origlyph.tolerance.statistical")
    stat_recon_module = importlib.import_module(
        "origlyph.tolerance.statistical_reconciliation"
    )
    worst_case_module = importlib.import_module("origlyph.tolerance.worst_case")

    targets = (
        (worst_case_module, "worst_case"),
        (statistical_module, "statistical"),
        (sensitivity_module, "worst_case_sensitivity"),
        (sensitivity_module, "statistical_sensitivity"),
        (budget_module, "worst_case_budget"),
        (budget_module, "statistical_budget"),
        (allocation_module, "validate_allocation"),
        (reconciliation_module, "reconcile_allocation"),
        (stat_recon_module, "reconcile_statistical_allocation"),
        (decision_module, "evaluate_tolerance_decision"),
    )
    for module, name in targets:
        monkeypatch.setattr(module, name, forbidden)

    package = build_decision_audit_package(report)
    assert verify_decision_audit_package(package) is ReplayabilityStatus.REPLAYABLE


def test_public_api_exports_stage_15o_symbols() -> None:
    import origlyph.tolerance as tolerance

    expected = {
        "AUDIT_PACKAGE_SCHEMA_VERSION",
        "ReplayabilityStatus",
        "DecisionReplayManifest",
        "ToleranceDecisionAuditPackage",
        "InvalidDecisionAuditPackageError",
        "build_decision_audit_package",
        "audit_package_from_dict",
        "verify_decision_audit_package",
    }
    assert expected.issubset(tolerance.__all__)
    assert all(hasattr(tolerance, name) for name in expected)
