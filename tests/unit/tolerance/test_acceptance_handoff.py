"""Stage 15T deterministic governed-acceptance handoff tests."""

from __future__ import annotations

import inspect
import json
import math
from dataclasses import FrozenInstanceError, replace

import pytest

import origlyph.tolerance.acceptance_handoff as handoff_module
from origlyph.tolerance import (
    ACCEPTANCE_HANDOFF_SCHEMA_VERSION,
    AuditAcceptanceHandoffPackage,
    AuditAcceptanceHandoffStatus,
    InvalidAuditAcceptanceHandoffError,
    build_audit_acceptance_handoff,
)
from origlyph.tolerance.approval_readiness import (
    AuditApprovalReadinessStatus,
    evaluate_audit_approval_readiness,
)
from origlyph.tolerance.change_disposition import (
    AuditChangeDisposition,
    determine_audit_change_disposition,
)
from origlyph.tolerance.change_impact import (
    assess_audit_change_impact,
)
from origlyph.tolerance.comparison import (
    AuditChange,
    AuditChangeCategory,
    AuditChangeCode,
    AuditChangeSignificance,
    AuditComparisonStatus,
    AuditPackageComparisonResult,
)


def _change(
    code: AuditChangeCode,
    *,
    category: AuditChangeCategory,
    baseline: object = "old",
    candidate: object = "new",
    significance: AuditChangeSignificance = (
        AuditChangeSignificance.ENGINEERING_RELEVANT
    ),
) -> AuditChange:
    return AuditChange(
        code=code,
        category=category,
        scope="fixture",
        subject_id="subject",
        field_path="field",
        baseline_value=baseline,  # type: ignore[arg-type]
        candidate_value=candidate,  # type: ignore[arg-type]
        significance=significance,
        detail="deterministic fixture",
    )


def _comparison(kind: str = "identical") -> AuditPackageComparisonResult:
    status = AuditComparisonStatus.CHANGED
    if kind == "identical":
        status = AuditComparisonStatus.IDENTICAL
        changes: tuple[AuditChange, ...] = ()
    elif kind == "traceability":
        changes = (
            _change(
                AuditChangeCode.PACKAGE_ID_CHANGED,
                category=AuditChangeCategory.FINGERPRINT,
                significance=AuditChangeSignificance.STRUCTURAL,
            ),
        )
    elif kind == "engineering":
        changes = (
            _change(
                AuditChangeCode.INPUT_METRIC_CHANGED,
                category=AuditChangeCategory.INPUT,
            ),
        )
    elif kind == "compliance":
        changes = (
            _change(
                AuditChangeCode.EQUALITY_TOLERANCE_CHANGED,
                category=AuditChangeCategory.POLICY,
            ),
        )
    elif kind == "decision":
        changes = (
            _change(
                AuditChangeCode.DECISION_STATUS_CHANGED,
                category=AuditChangeCategory.DECISION,
                baseline="pass",
                candidate="fail",
            ),
        )
    elif kind == "replay":
        changes = (
            _change(
                AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
                category=AuditChangeCategory.REPLAYABILITY,
                baseline="not_replayable",
                candidate="replayable",
                significance=AuditChangeSignificance.STRUCTURAL,
            ),
        )
    elif kind == "blocked":
        status = AuditComparisonStatus.INCOMPATIBLE
        changes = (
            _change(
                AuditChangeCode.AUDIT_SCHEMA_CHANGED,
                category=AuditChangeCategory.SCHEMA,
                significance=AuditChangeSignificance.INCOMPATIBLE,
            ),
        )
    else:
        raise AssertionError(f"unknown fixture kind {kind!r}")
    return AuditPackageComparisonResult(
        status=status,
        baseline_package_id="baseline-package",
        candidate_package_id="candidate-package",
        changes=changes,
    )


def _chain(kind: str = "identical"):
    comparison = _comparison(kind)
    impact = assess_audit_change_impact(comparison)
    disposition = determine_audit_change_disposition(impact)
    readiness = evaluate_audit_approval_readiness(disposition)
    return comparison, impact, disposition, readiness


def _handoff(kind: str = "identical") -> AuditAcceptanceHandoffPackage:
    return build_audit_acceptance_handoff(*_chain(kind))


def test_public_api_is_available() -> None:
    assert callable(build_audit_acceptance_handoff)
    assert AuditAcceptanceHandoffStatus.BLOCKED.value == "blocked"


def test_schema_version_is_stable() -> None:
    assert ACCEPTANCE_HANDOFF_SCHEMA_VERSION == (
        "origlyph.tolerance.audit_acceptance_handoff.v1"
    )


def test_ready_handoff() -> None:
    package = _handoff("identical")
    assert package.status is (
        AuditAcceptanceHandoffStatus.READY_FOR_GOVERNED_ACCEPTANCE
    )


def test_action_required_handoff() -> None:
    package = _handoff("engineering")
    assert package.status is AuditAcceptanceHandoffStatus.ACTION_REQUIRED


def test_blocked_handoff() -> None:
    package = _handoff("blocked")
    assert package.status is AuditAcceptanceHandoffStatus.BLOCKED


def test_traceability_ready_handoff() -> None:
    package = _handoff("traceability")
    assert package.status is (
        AuditAcceptanceHandoffStatus.READY_FOR_GOVERNED_ACCEPTANCE
    )
    assert package.disposition_result.disposition is (
        AuditChangeDisposition.ACCEPT_WITH_TRACEABILITY
    )


def test_compliance_handoff_requires_action() -> None:
    assert _handoff("compliance").status is (
        AuditAcceptanceHandoffStatus.ACTION_REQUIRED
    )


def test_decision_handoff_requires_action() -> None:
    package = _handoff("decision")
    assert package.status is AuditAcceptanceHandoffStatus.ACTION_REQUIRED
    assert package.readiness_result.decision_changed


def test_replay_pending_handoff_requires_action() -> None:
    package = _handoff("replay")
    assert package.status is AuditAcceptanceHandoffStatus.ACTION_REQUIRED
    assert (
        package.disposition_result.disposition is AuditChangeDisposition.REPLAY_REQUIRED
    )


def test_deterministic_handoff_identity() -> None:
    first = _handoff("engineering")
    second = _handoff("engineering")
    assert first.handoff_id == second.handoff_id
    assert len(first.handoff_id) == 64


def test_handoff_identity_changes_with_package_trace() -> None:
    comparison, impact, disposition, readiness = _chain("engineering")
    changed = replace(comparison, candidate_package_id="other-candidate")
    package = build_audit_acceptance_handoff(changed, impact, disposition, readiness)
    assert package.handoff_id != _handoff("engineering").handoff_id


def test_as_dict_and_json_are_canonical() -> None:
    package = _handoff("traceability")
    assert package.to_json() == package.to_json()
    assert package.as_dict()["handoff_id"] == package.handoff_id
    assert package.to_json() == json.dumps(
        package.as_dict(),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def test_repeated_output_is_equal() -> None:
    assert _handoff("compliance") == _handoff("compliance")


def test_all_upstream_results_are_preserved() -> None:
    chain = _chain("engineering")
    package = build_audit_acceptance_handoff(*chain)
    assert (
        package.comparison_result,
        package.impact_result,
        package.disposition_result,
        package.readiness_result,
    ) == chain


def test_audit_package_ids_are_preserved() -> None:
    package = _handoff("identical")
    assert package.baseline_package_id == "baseline-package"
    assert package.candidate_package_id == "candidate-package"


def test_change_order_is_preserved() -> None:
    first = _change(
        AuditChangeCode.INPUT_METRIC_CHANGED,
        category=AuditChangeCategory.INPUT,
    )
    second = _change(
        AuditChangeCode.PACKAGE_ID_CHANGED,
        category=AuditChangeCategory.FINGERPRINT,
        significance=AuditChangeSignificance.STRUCTURAL,
    )
    comparison = replace(_comparison("engineering"), changes=(first, second))
    impact = assess_audit_change_impact(comparison)
    disposition = determine_audit_change_disposition(impact)
    readiness = evaluate_audit_approval_readiness(disposition)
    package = build_audit_acceptance_handoff(comparison, impact, disposition, readiness)
    assert package.comparison_result.changes == (first, second)


def test_models_are_immutable() -> None:
    package = _handoff("identical")
    with pytest.raises(FrozenInstanceError):
        package.status = AuditAcceptanceHandoffStatus.BLOCKED  # type: ignore[misc]


@pytest.mark.parametrize("bad_index", range(4))
def test_wrong_input_types_are_rejected(bad_index: int) -> None:
    chain: list[object] = list(_chain("engineering"))
    chain[bad_index] = object()
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(*chain)  # type: ignore[arg-type]


def test_comparison_to_impact_mismatch_is_rejected() -> None:
    comparison, impact, disposition, readiness = _chain("engineering")
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(
            _comparison("traceability"), impact, disposition, readiness
        )


def test_impact_to_disposition_mismatch_is_rejected() -> None:
    comparison, impact, _, _ = _chain("engineering")
    _, _, disposition, readiness = _chain("compliance")
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(comparison, impact, disposition, readiness)


def test_disposition_to_readiness_mismatch_is_rejected() -> None:
    comparison, impact, disposition, _ = _chain("engineering")
    *_, readiness = _chain("compliance")
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(comparison, impact, disposition, readiness)


def test_blocked_chain_cannot_become_ready() -> None:
    comparison, impact, disposition, readiness = _chain("blocked")
    malformed = replace(
        readiness,
        status=AuditApprovalReadinessStatus.READY,
        is_ready=True,
    )
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(comparison, impact, disposition, malformed)


def test_incompatible_chain_cannot_become_ready() -> None:
    comparison, impact, disposition, readiness = _chain("blocked")
    malformed = replace(readiness, comparison_status=AuditComparisonStatus.CHANGED)
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(comparison, impact, disposition, malformed)


def test_empty_package_identifier_is_rejected() -> None:
    comparison, impact, disposition, readiness = _chain("engineering")
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(
            replace(comparison, candidate_package_id=""),
            impact,
            disposition,
            readiness,
        )


def test_non_finite_content_is_rejected() -> None:
    comparison, _, _, _ = _chain("engineering")
    bad_change = replace(comparison.changes[0], baseline_value=math.nan)
    comparison = replace(comparison, changes=(bad_change,))
    impact = assess_audit_change_impact(comparison)
    disposition = determine_audit_change_disposition(impact)
    readiness = evaluate_audit_approval_readiness(disposition)
    with pytest.raises(InvalidAuditAcceptanceHandoffError):
        build_audit_acceptance_handoff(comparison, impact, disposition, readiness)


def test_inputs_are_not_mutated() -> None:
    chain = _chain("engineering")
    before = tuple(item.to_json() for item in chain)
    build_audit_acceptance_handoff(*chain)
    assert tuple(item.to_json() for item in chain) == before


def test_every_readiness_state_has_an_explicit_handoff_status() -> None:
    assert set(handoff_module._READINESS_STATUS) == set(AuditApprovalReadinessStatus)


def test_no_approval_record_fields() -> None:
    fields = AuditAcceptanceHandoffPackage.__dataclass_fields__
    prohibited = {
        "approved" + "_by",
        "reviewed" + "_by",
        "authorized" + "_by",
        "signature",
        "approval" + "_timestamp",
        "actor" + "_id",
    }
    assert prohibited.isdisjoint(fields)


def test_no_clock_random_or_environment_identity_sources() -> None:
    source = inspect.getsource(handoff_module)
    prohibited = ("datetime", "time.time", "uuid", "random", "getenv", "cwd")
    assert not any(item in source for item in prohibited)


def test_no_upstream_or_engine_invocations() -> None:
    source = inspect.getsource(handoff_module)
    prohibited_calls = (
        "compare_decision_audit_packages(",
        "assess_audit_change_impact(",
        "determine_audit_change_disposition(",
        "evaluate_audit_approval_readiness(",
        "worst_case(",
        "statistical(",
        "evaluate_tolerance_decision(",
    )
    assert not any(call in source for call in prohibited_calls)
