"""Deterministic Stage 15O audit-package comparison (Stage 15P).

Comparison is structural and read-only.  It does not rerun authoritative
engineering calculations, rank packages, or recommend a preferred result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .audit import (
    AUDIT_PACKAGE_SCHEMA_VERSION,
    ToleranceDecisionAuditPackage,
    verify_decision_audit_package,
)
from .report import REPORT_SCHEMA_VERSION, ReportContributor, ReportEvidenceRef

__all__ = [
    "AuditComparisonStatus",
    "AuditChangeCategory",
    "AuditChangeCode",
    "AuditChangeSignificance",
    "AuditChange",
    "AuditPackageComparisonResult",
    "InvalidAuditComparisonError",
    "compare_decision_audit_packages",
]


class InvalidAuditComparisonError(ValueError):
    """Raised for an invalid comparison invocation."""


class AuditComparisonStatus(Enum):
    """Top-level deterministic comparison verdict."""

    IDENTICAL = "identical"
    CHANGED = "changed"
    INCOMPATIBLE = "incompatible"


class AuditChangeCategory(Enum):
    """Stable domain category for one deterministic change."""

    SCHEMA = "schema"
    INPUT = "input"
    POLICY = "policy"
    DECISION = "decision"
    INTEGRITY = "integrity"
    REPLAYABILITY = "replayability"
    EVIDENCE = "evidence"
    EXPLANATION = "explanation"
    CONTRIBUTOR = "contributor"
    CORRELATION = "correlation"
    ALLOCATION = "allocation"
    RECONCILIATION = "reconciliation"
    FINGERPRINT = "fingerprint"
    REPORT = "report"
    STRUCTURAL = "structural"


class AuditChangeSignificance(Enum):
    """Neutral significance class; never a better/worse ranking."""

    INFO = "info"
    STRUCTURAL = "structural"
    ENGINEERING_RELEVANT = "engineering_relevant"
    INCOMPATIBLE = "incompatible"


class AuditChangeCode(Enum):
    """Stable machine-readable change identities."""

    AUDIT_SCHEMA_CHANGED = "audit_schema_changed"
    REPORT_SCHEMA_CHANGED = "report_schema_changed"
    PACKAGE_VERIFICATION_FAILED = "package_verification_failed"
    INPUT_FINGERPRINT_CHANGED = "input_fingerprint_changed"
    EQUALITY_TOLERANCE_CHANGED = "equality_tolerance_changed"
    SIGMA_MULTIPLIER_CHANGED = "sigma_multiplier_changed"
    COMPLETENESS_POLICY_CHANGED = "completeness_policy_changed"
    POLICY_IDENTIFIERS_CHANGED = "policy_identifiers_changed"
    DECISION_STATUS_CHANGED = "decision_status_changed"
    REPORT_COMPLETENESS_CHANGED = "report_completeness_changed"
    SUMMARY_CODE_CHANGED = "summary_code_changed"
    GOVERNING_REASON_SET_CHANGED = "governing_reason_set_changed"
    MARGINAL_REASON_SET_CHANGED = "marginal_reason_set_changed"
    SUPPORTING_REASON_SET_CHANGED = "supporting_reason_set_changed"
    EVIDENCE_ADDED = "evidence_added"
    EVIDENCE_REMOVED = "evidence_removed"
    EVIDENCE_CODE_CHANGED = "evidence_code_changed"
    EVIDENCE_SOURCE_CHANGED = "evidence_source_changed"
    REASON_LINK_CHANGED = "reason_link_changed"
    GOVERNING_EVIDENCE_CHANGED = "governing_evidence_changed"
    MARGINAL_EVIDENCE_CHANGED = "marginal_evidence_changed"
    INTEGRITY_STATUS_CHANGED = "integrity_status_changed"
    INTEGRITY_VIOLATION_ADDED = "integrity_violation_added"
    INTEGRITY_VIOLATION_REMOVED = "integrity_violation_removed"
    INTEGRITY_VIOLATION_CHANGED = "integrity_violation_changed"
    REPLAYABILITY_STATUS_CHANGED = "replayability_status_changed"
    CONTRIBUTOR_ADDED = "contributor_added"
    CONTRIBUTOR_REMOVED = "contributor_removed"
    CONTRIBUTOR_ORDER_CHANGED = "contributor_order_changed"
    CONTRIBUTOR_SPAN_CHANGED = "contributor_span_changed"
    CONTRIBUTOR_SIGMA_CHANGED = "contributor_sigma_changed"
    CONTRIBUTOR_FIELD_CHANGED = "contributor_field_changed"
    CORRELATION_PAIR_ADDED = "correlation_pair_added"
    CORRELATION_PAIR_REMOVED = "correlation_pair_removed"
    CORRELATION_RHO_CHANGED = "correlation_rho_changed"
    INPUT_METRIC_ADDED = "input_metric_added"
    INPUT_METRIC_REMOVED = "input_metric_removed"
    INPUT_METRIC_CHANGED = "input_metric_changed"
    ALLOCATION_CHANGED = "allocation_changed"
    STATISTICAL_ALLOCATION_CHANGED = "statistical_allocation_changed"
    RECONCILIATION_CHANGED = "reconciliation_changed"
    RECONCILIATION_MARGIN_CHANGED = "reconciliation_margin_changed"
    DECISION_ID_CHANGED = "decision_id_changed"
    PACKAGE_ID_CHANGED = "package_id_changed"
    REPORT_FINGERPRINT_CHANGED = "report_fingerprint_changed"
    INTEGRITY_FINGERPRINT_CHANGED = "integrity_fingerprint_changed"
    UNEXPLAINED_FINGERPRINT_DRIFT = "unexplained_fingerprint_drift"


AuditValue = str | int | float | bool | None | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuditChange:
    """One immutable, neutrally classified deterministic difference."""

    code: AuditChangeCode
    category: AuditChangeCategory
    scope: str
    subject_id: str
    field_path: str
    baseline_value: AuditValue
    candidate_value: AuditValue
    significance: AuditChangeSignificance
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "category": self.category.value,
            "scope": self.scope,
            "subject_id": self.subject_id,
            "field_path": self.field_path,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "significance": self.significance.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class AuditPackageComparisonResult:
    """Immutable deterministic comparison result."""

    status: AuditComparisonStatus
    baseline_package_id: str
    candidate_package_id: str
    changes: tuple[AuditChange, ...]
    provenance_compared: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "baseline_package_id": self.baseline_package_id,
            "candidate_package_id": self.candidate_package_id,
            "provenance_compared": self.provenance_compared,
            "changes": [change.as_dict() for change in self.changes],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )


_CATEGORY_ORDER = tuple(AuditChangeCategory)


def _sort_key(change: AuditChange) -> tuple[int, str, str, str, str]:
    return (
        _CATEGORY_ORDER.index(change.category),
        change.scope,
        change.subject_id,
        change.field_path,
        change.code.value,
    )


def _value(value: object) -> AuditValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _add(
    changes: list[AuditChange],
    code: AuditChangeCode,
    category: AuditChangeCategory,
    scope: str,
    subject_id: str,
    field_path: str,
    baseline_value: object,
    candidate_value: object,
    significance: AuditChangeSignificance,
    detail: str,
) -> None:
    changes.append(
        AuditChange(
            code=code,
            category=category,
            scope=scope,
            subject_id=subject_id,
            field_path=field_path,
            baseline_value=_value(baseline_value),
            candidate_value=_value(candidate_value),
            significance=significance,
            detail=detail,
        )
    )


def _schema_changes(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
) -> list[AuditChange]:
    changes: list[AuditChange] = []
    if baseline.audit_schema_version != candidate.audit_schema_version:
        _add(
            changes,
            AuditChangeCode.AUDIT_SCHEMA_CHANGED,
            AuditChangeCategory.SCHEMA,
            "audit_package",
            "",
            "audit_schema_version",
            baseline.audit_schema_version,
            candidate.audit_schema_version,
            AuditChangeSignificance.INCOMPATIBLE,
            "audit schema versions differ",
        )
    if baseline.report.schema_version != candidate.report.schema_version:
        _add(
            changes,
            AuditChangeCode.REPORT_SCHEMA_CHANGED,
            AuditChangeCategory.SCHEMA,
            "report",
            "",
            "schema_version",
            baseline.report.schema_version,
            candidate.report.schema_version,
            AuditChangeSignificance.INCOMPATIBLE,
            "report schema versions differ",
        )
    return changes


def _verification_changes(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
) -> list[AuditChange]:
    changes: list[AuditChange] = []
    for label, package in (("baseline", baseline), ("candidate", candidate)):
        verified = verify_decision_audit_package(package)
        if verified is not package.replayability_status:
            _add(
                changes,
                AuditChangeCode.PACKAGE_VERIFICATION_FAILED,
                AuditChangeCategory.STRUCTURAL,
                label,
                package.package_id,
                "replayability_status",
                package.replayability_status.value,
                verified.value,
                AuditChangeSignificance.INCOMPATIBLE,
                f"{label} package does not verify as its declared state",
            )
    return changes


def _compare_policies(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = baseline.replay_manifest
    right = candidate.replay_manifest
    fields = (
        (
            "equality_tolerance",
            AuditChangeCode.EQUALITY_TOLERANCE_CHANGED,
            left.equality_tolerance,
            right.equality_tolerance,
        ),
        (
            "sigma_multiplier",
            AuditChangeCode.SIGMA_MULTIPLIER_CHANGED,
            left.sigma_multiplier,
            right.sigma_multiplier,
        ),
        (
            "require_complete_policy",
            AuditChangeCode.COMPLETENESS_POLICY_CHANGED,
            left.require_complete_policy,
            right.require_complete_policy,
        ),
        (
            "policy_identifiers",
            AuditChangeCode.POLICY_IDENTIFIERS_CHANGED,
            left.policy_identifiers,
            right.policy_identifiers,
        ),
    )
    for field_path, code, old, new in fields:
        if old != new:
            _add(
                changes,
                code,
                AuditChangeCategory.POLICY,
                "replay_manifest",
                "",
                field_path,
                old,
                new,
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                f"preserved policy field {field_path} changed",
            )


def _compare_decision(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = baseline.report
    right = candidate.report
    if left.final_status is not right.final_status:
        _add(
            changes,
            AuditChangeCode.DECISION_STATUS_CHANGED,
            AuditChangeCategory.DECISION,
            "report",
            "",
            "final_status",
            left.final_status.value,
            right.final_status.value,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "engineering decision status transitioned",
        )
    if left.is_complete is not right.is_complete:
        _add(
            changes,
            AuditChangeCode.REPORT_COMPLETENESS_CHANGED,
            AuditChangeCategory.DECISION,
            "report",
            "",
            "is_complete",
            left.is_complete,
            right.is_complete,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "report completeness state changed",
        )
    explanation_fields = (
        (
            "summary_code",
            AuditChangeCode.SUMMARY_CODE_CHANGED,
            left.summary_code,
            right.summary_code,
        ),
        (
            "governing_reason_codes",
            AuditChangeCode.GOVERNING_REASON_SET_CHANGED,
            tuple(code.value for code in left.governing_reason_codes),
            tuple(code.value for code in right.governing_reason_codes),
        ),
        (
            "marginal_reason_codes",
            AuditChangeCode.MARGINAL_REASON_SET_CHANGED,
            tuple(code.value for code in left.marginal_reason_codes),
            tuple(code.value for code in right.marginal_reason_codes),
        ),
        (
            "supporting_reason_codes",
            AuditChangeCode.SUPPORTING_REASON_SET_CHANGED,
            tuple(code.value for code in left.supporting_reason_codes),
            tuple(code.value for code in right.supporting_reason_codes),
        ),
    )
    for field_path, code, old, new in explanation_fields:
        if old != new:
            _add(
                changes,
                code,
                AuditChangeCategory.EXPLANATION,
                "report",
                "",
                field_path,
                old,
                new,
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                f"deterministic explanation field {field_path} changed",
            )


def _evidence_map(
    refs: tuple[ReportEvidenceRef, ...],
) -> dict[str, ReportEvidenceRef]:
    return {ref.evidence_id: ref for ref in refs}


def _governing_evidence(package: ToleranceDecisionAuditPackage) -> tuple[str, ...]:
    governing = set(package.report.governing_reason_codes)
    return tuple(
        sorted(
            evidence_id
            for reason in package.report.triggered_reasons
            if reason.reason_code in governing
            for evidence_id in reason.evidence_ids
        )
    )


def _marginal_evidence(package: ToleranceDecisionAuditPackage) -> tuple[str, ...]:
    marginal = set(package.report.marginal_reason_codes)
    return tuple(
        sorted(
            evidence_id
            for reason in package.report.triggered_reasons
            if reason.reason_code in marginal
            for evidence_id in reason.evidence_ids
        )
    )


def _compare_evidence(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = _evidence_map(baseline.report.evidence_refs)
    right = _evidence_map(candidate.report.evidence_refs)
    for evidence_id in sorted(left.keys() - right.keys()):
        _add(
            changes,
            AuditChangeCode.EVIDENCE_REMOVED,
            AuditChangeCategory.EVIDENCE,
            "report.evidence_refs",
            evidence_id,
            "evidence_id",
            evidence_id,
            None,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "evidence reference removed",
        )
    for evidence_id in sorted(right.keys() - left.keys()):
        _add(
            changes,
            AuditChangeCode.EVIDENCE_ADDED,
            AuditChangeCategory.EVIDENCE,
            "report.evidence_refs",
            evidence_id,
            "evidence_id",
            None,
            evidence_id,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "evidence reference added",
        )
    evidence_fields = (
        ("evidence_code", AuditChangeCode.EVIDENCE_CODE_CHANGED),
        ("source", AuditChangeCode.EVIDENCE_SOURCE_CHANGED),
        ("reason_code", AuditChangeCode.REASON_LINK_CHANGED),
    )
    for evidence_id in sorted(left.keys() & right.keys()):
        for field_path, code in evidence_fields:
            old = getattr(left[evidence_id], field_path)
            new = getattr(right[evidence_id], field_path)
            if old != new:
                _add(
                    changes,
                    code,
                    AuditChangeCategory.EVIDENCE,
                    "report.evidence_refs",
                    evidence_id,
                    field_path,
                    old,
                    new,
                    AuditChangeSignificance.ENGINEERING_RELEVANT,
                    f"evidence field {field_path} changed",
                )
    for code, field_path, old, new in (
        (
            AuditChangeCode.GOVERNING_EVIDENCE_CHANGED,
            "governing_evidence_ids",
            _governing_evidence(baseline),
            _governing_evidence(candidate),
        ),
        (
            AuditChangeCode.MARGINAL_EVIDENCE_CHANGED,
            "marginal_evidence_ids",
            _marginal_evidence(baseline),
            _marginal_evidence(candidate),
        ),
    ):
        if old != new:
            _add(
                changes,
                code,
                AuditChangeCategory.EXPLANATION,
                "report.triggered_reasons",
                "",
                field_path,
                old,
                new,
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                f"{field_path} changed",
            )
    left_reasons = {
        reason.reason_code.value: reason for reason in baseline.report.triggered_reasons
    }
    right_reasons = {
        reason.reason_code.value: reason
        for reason in candidate.report.triggered_reasons
    }
    for reason_code in sorted(set(left_reasons) | set(right_reasons)):
        old = (
            left_reasons[reason_code].as_dict()
            if reason_code in left_reasons
            else None
        )
        new = (
            right_reasons[reason_code].as_dict()
            if reason_code in right_reasons
            else None
        )
        if old != new:
            _add(
                changes,
                AuditChangeCode.REASON_LINK_CHANGED,
                AuditChangeCategory.EVIDENCE,
                "report.triggered_reasons",
                reason_code,
                "reason",
                old,
                new,
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                "triggered reason or its evidence linkage changed",
            )


def _violation_identity(violation: Any) -> tuple[str, str, str, str, str]:
    return (
        violation.code.value,
        violation.severity.value,
        violation.scope,
        violation.subject,
        violation.detail,
    )


def _compare_integrity(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = baseline.integrity_result
    right = candidate.integrity_result
    if left.status is not right.status:
        _add(
            changes,
            AuditChangeCode.INTEGRITY_STATUS_CHANGED,
            AuditChangeCategory.INTEGRITY,
            "integrity_result",
            "",
            "status",
            left.status.value,
            right.status.value,
            AuditChangeSignificance.STRUCTURAL,
            "audit integrity status transitioned",
        )
    left_items = {_violation_identity(item) for item in left.violations}
    right_items = {_violation_identity(item) for item in right.violations}
    left_by_subject = {
        (item.scope, item.subject): _violation_identity(item)
        for item in left.violations
    }
    right_by_subject = {
        (item.scope, item.subject): _violation_identity(item)
        for item in right.violations
    }
    for identity in sorted(left_by_subject.keys() & right_by_subject.keys()):
        old = left_by_subject[identity]
        new = right_by_subject[identity]
        if old != new:
            _add(
                changes,
                AuditChangeCode.INTEGRITY_VIOLATION_CHANGED,
                AuditChangeCategory.INTEGRITY,
                identity[0],
                identity[1],
                "violation",
                old,
                new,
                AuditChangeSignificance.STRUCTURAL,
                "integrity violation code or detail changed",
            )
    for identity in sorted(left_items - right_items):
        _add(
            changes,
            AuditChangeCode.INTEGRITY_VIOLATION_REMOVED,
            AuditChangeCategory.INTEGRITY,
            identity[2],
            identity[3],
            "violation",
            identity,
            None,
            AuditChangeSignificance.STRUCTURAL,
            "integrity violation removed",
        )
    for identity in sorted(right_items - left_items):
        _add(
            changes,
            AuditChangeCode.INTEGRITY_VIOLATION_ADDED,
            AuditChangeCategory.INTEGRITY,
            identity[2],
            identity[3],
            "violation",
            None,
            identity,
            AuditChangeSignificance.STRUCTURAL,
            "integrity violation added",
        )


def _contributor_key(item: ReportContributor) -> tuple[str, str]:
    return (item.name, item.contribution_type)


def _compare_contributors(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left_items = baseline.report.contributors
    right_items = candidate.report.contributors
    left = {_contributor_key(item): item for item in left_items}
    right = {_contributor_key(item): item for item in right_items}
    for key in sorted(left.keys() - right.keys()):
        _add(
            changes,
            AuditChangeCode.CONTRIBUTOR_REMOVED,
            AuditChangeCategory.CONTRIBUTOR,
            "report.contributors",
            key[0],
            "contributor",
            key,
            None,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "contributor removed",
        )
    for key in sorted(right.keys() - left.keys()):
        _add(
            changes,
            AuditChangeCode.CONTRIBUTOR_ADDED,
            AuditChangeCategory.CONTRIBUTOR,
            "report.contributors",
            key[0],
            "contributor",
            None,
            key,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "contributor added",
        )
    fields = (
        ("contribution_value", AuditChangeCode.CONTRIBUTOR_SPAN_CHANGED),
        ("contribution_sigma", AuditChangeCode.CONTRIBUTOR_SIGMA_CHANGED),
        ("contribution_lower", AuditChangeCode.CONTRIBUTOR_FIELD_CHANGED),
        ("contribution_upper", AuditChangeCode.CONTRIBUTOR_FIELD_CHANGED),
        ("is_worst_case", AuditChangeCode.CONTRIBUTOR_FIELD_CHANGED),
        ("is_statistical", AuditChangeCode.CONTRIBUTOR_FIELD_CHANGED),
    )
    for key in sorted(left.keys() & right.keys()):
        for field_path, code in fields:
            old = getattr(left[key], field_path)
            new = getattr(right[key], field_path)
            if old != new:
                _add(
                    changes,
                    code,
                    AuditChangeCategory.CONTRIBUTOR,
                    "report.contributors",
                    key[0],
                    field_path,
                    old,
                    new,
                    AuditChangeSignificance.ENGINEERING_RELEVANT,
                    f"contributor field {field_path} changed",
                )
    old_order = tuple("|".join(key) for key in map(_contributor_key, left_items))
    new_order = tuple("|".join(key) for key in map(_contributor_key, right_items))
    if set(old_order) == set(new_order) and old_order != new_order:
        _add(
            changes,
            AuditChangeCode.CONTRIBUTOR_ORDER_CHANGED,
            AuditChangeCategory.CONTRIBUTOR,
            "report.contributors",
            "",
            "order",
            old_order,
            new_order,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "contributor order changed",
        )


def _compare_correlations(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = dict(baseline.replay_manifest.correlation_assumptions)
    right = dict(candidate.replay_manifest.correlation_assumptions)
    for pair in sorted(left.keys() - right.keys()):
        _add(
            changes,
            AuditChangeCode.CORRELATION_PAIR_REMOVED,
            AuditChangeCategory.CORRELATION,
            "replay_manifest.correlation_assumptions",
            pair,
            "coefficient",
            left[pair],
            None,
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "canonical correlation pair removed",
        )
    for pair in sorted(right.keys() - left.keys()):
        _add(
            changes,
            AuditChangeCode.CORRELATION_PAIR_ADDED,
            AuditChangeCategory.CORRELATION,
            "replay_manifest.correlation_assumptions",
            pair,
            "coefficient",
            None,
            right[pair],
            AuditChangeSignificance.ENGINEERING_RELEVANT,
            "canonical correlation pair added",
        )
    for pair in sorted(left.keys() & right.keys()):
        if left[pair] != right[pair]:
            _add(
                changes,
                AuditChangeCode.CORRELATION_RHO_CHANGED,
                AuditChangeCategory.CORRELATION,
                "replay_manifest.correlation_assumptions",
                pair,
                "coefficient",
                left[pair],
                right[pair],
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                "canonical correlation coefficient changed",
            )


def _metric_sections(package: ToleranceDecisionAuditPackage) -> dict[str, Any]:
    return package.report.as_dict()["sections"]  # type: ignore[return-value]


def _metric_map(section: Any) -> dict[str, dict[str, object]]:
    return {item["key"]: item for item in section["metrics"]}


def _metric_classification(
    section_name: str, metric_key: str
) -> tuple[AuditChangeCategory, AuditChangeCode]:
    if section_name == "allocation":
        if "stat" in metric_key:
            return (
                AuditChangeCategory.ALLOCATION,
                AuditChangeCode.STATISTICAL_ALLOCATION_CHANGED,
            )
        return AuditChangeCategory.ALLOCATION, AuditChangeCode.ALLOCATION_CHANGED
    if "reconciliation" in section_name:
        if "margin" in metric_key:
            return (
                AuditChangeCategory.RECONCILIATION,
                AuditChangeCode.RECONCILIATION_MARGIN_CHANGED,
            )
        return (
            AuditChangeCategory.RECONCILIATION,
            AuditChangeCode.RECONCILIATION_CHANGED,
        )
    return AuditChangeCategory.INPUT, AuditChangeCode.INPUT_METRIC_CHANGED


def _compare_metrics(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left_sections = _metric_sections(baseline)
    right_sections = _metric_sections(candidate)
    ignored = {"decision", "evidence", "correlation"}
    for section_name in sorted(set(left_sections) - ignored):
        left = _metric_map(left_sections[section_name])
        right = _metric_map(right_sections[section_name])
        for key in sorted(left.keys() - right.keys()):
            category, _ = _metric_classification(section_name, key)
            _add(
                changes,
                AuditChangeCode.INPUT_METRIC_REMOVED,
                category,
                f"report.sections.{section_name}",
                key,
                "metric",
                left[key],
                None,
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                "preserved metric removed",
            )
        for key in sorted(right.keys() - left.keys()):
            category, _ = _metric_classification(section_name, key)
            _add(
                changes,
                AuditChangeCode.INPUT_METRIC_ADDED,
                category,
                f"report.sections.{section_name}",
                key,
                "metric",
                None,
                right[key],
                AuditChangeSignificance.ENGINEERING_RELEVANT,
                "preserved metric added",
            )
        for key in sorted(left.keys() & right.keys()):
            if left[key] != right[key]:
                category, code = _metric_classification(section_name, key)
                _add(
                    changes,
                    code,
                    category,
                    f"report.sections.{section_name}",
                    key,
                    "metric",
                    left[key],
                    right[key],
                    AuditChangeSignificance.ENGINEERING_RELEVANT,
                    "preserved metric changed",
                )


def _compare_replayability(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    if baseline.replayability_status is not candidate.replayability_status:
        _add(
            changes,
            AuditChangeCode.REPLAYABILITY_STATUS_CHANGED,
            AuditChangeCategory.REPLAYABILITY,
            "audit_package",
            "",
            "replayability_status",
            baseline.replayability_status.value,
            candidate.replayability_status.value,
            AuditChangeSignificance.STRUCTURAL,
            "structural replayability status transitioned",
        )


def _compare_fingerprints(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = baseline.replay_manifest
    right = candidate.replay_manifest
    fields = (
        (
            "decision_id",
            AuditChangeCode.DECISION_ID_CHANGED,
            left.decision_id,
            right.decision_id,
        ),
        (
            "package_id",
            AuditChangeCode.PACKAGE_ID_CHANGED,
            baseline.package_id,
            candidate.package_id,
        ),
        (
            "input_fingerprint",
            AuditChangeCode.INPUT_FINGERPRINT_CHANGED,
            left.input_fingerprint,
            right.input_fingerprint,
        ),
        (
            "report_fingerprint",
            AuditChangeCode.REPORT_FINGERPRINT_CHANGED,
            left.report_fingerprint,
            right.report_fingerprint,
        ),
        (
            "integrity_fingerprint",
            AuditChangeCode.INTEGRITY_FINGERPRINT_CHANGED,
            left.integrity_fingerprint,
            right.integrity_fingerprint,
        ),
    )
    for field_path, code, old, new in fields:
        if old != new:
            category = (
                AuditChangeCategory.INPUT
                if code is AuditChangeCode.INPUT_FINGERPRINT_CHANGED
                else AuditChangeCategory.FINGERPRINT
            )
            _add(
                changes,
                code,
                category,
                "audit_identity",
                "",
                field_path,
                old,
                new,
                AuditChangeSignificance.STRUCTURAL,
                f"deterministic {field_path} changed",
            )


def _add_unexplained_drift(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> None:
    left = baseline.replay_manifest
    right = candidate.replay_manifest
    checks = (
        (
            "report_fingerprint",
            left.report_fingerprint,
            right.report_fingerprint,
            baseline.report.as_dict() == candidate.report.as_dict(),
        ),
        (
            "integrity_fingerprint",
            left.integrity_fingerprint,
            right.integrity_fingerprint,
            baseline.integrity_result == candidate.integrity_result,
        ),
    )
    for field_path, old, new, underlying_equal in checks:
        if old != new and underlying_equal:
            _add(
                changes,
                AuditChangeCode.UNEXPLAINED_FINGERPRINT_DRIFT,
                AuditChangeCategory.STRUCTURAL,
                "audit_identity",
                "",
                field_path,
                old,
                new,
                AuditChangeSignificance.INCOMPATIBLE,
                f"{field_path} drift has no matching deterministic content change",
            )


def _incompatible_result(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
    changes: list[AuditChange],
) -> AuditPackageComparisonResult:
    ordered = tuple(sorted(changes, key=_sort_key))
    return AuditPackageComparisonResult(
        status=AuditComparisonStatus.INCOMPATIBLE,
        baseline_package_id=baseline.package_id,
        candidate_package_id=candidate.package_id,
        changes=ordered,
    )


def compare_decision_audit_packages(
    baseline: ToleranceDecisionAuditPackage,
    candidate: ToleranceDecisionAuditPackage,
) -> AuditPackageComparisonResult:
    """Compare immutable audit packages without engineering recomputation."""
    if not isinstance(baseline, ToleranceDecisionAuditPackage):
        raise InvalidAuditComparisonError(
            "baseline must be a ToleranceDecisionAuditPackage"
        )
    if not isinstance(candidate, ToleranceDecisionAuditPackage):
        raise InvalidAuditComparisonError(
            "candidate must be a ToleranceDecisionAuditPackage"
        )

    schema_changes = _schema_changes(baseline, candidate)
    unsupported = (
        baseline.audit_schema_version != AUDIT_PACKAGE_SCHEMA_VERSION
        or candidate.audit_schema_version != AUDIT_PACKAGE_SCHEMA_VERSION
        or baseline.report.schema_version != REPORT_SCHEMA_VERSION
        or candidate.report.schema_version != REPORT_SCHEMA_VERSION
    )
    if schema_changes or unsupported:
        if unsupported and not schema_changes:
            _add(
                schema_changes,
                AuditChangeCode.AUDIT_SCHEMA_CHANGED,
                AuditChangeCategory.SCHEMA,
                "audit_package",
                "",
                "supported_schema",
                AUDIT_PACKAGE_SCHEMA_VERSION,
                "unsupported",
                AuditChangeSignificance.INCOMPATIBLE,
                "one or both packages use an unsupported schema",
            )
        return _incompatible_result(baseline, candidate, schema_changes)

    verification_changes = _verification_changes(baseline, candidate)
    if verification_changes:
        _compare_fingerprints(baseline, candidate, verification_changes)
        _add_unexplained_drift(baseline, candidate, verification_changes)
        return _incompatible_result(baseline, candidate, verification_changes)

    changes: list[AuditChange] = []
    _compare_policies(baseline, candidate, changes)
    _compare_decision(baseline, candidate, changes)
    _compare_integrity(baseline, candidate, changes)
    _compare_replayability(baseline, candidate, changes)
    _compare_evidence(baseline, candidate, changes)
    _compare_contributors(baseline, candidate, changes)
    _compare_correlations(baseline, candidate, changes)
    _compare_metrics(baseline, candidate, changes)
    _compare_fingerprints(baseline, candidate, changes)
    _add_unexplained_drift(baseline, candidate, changes)
    ordered = tuple(sorted(changes, key=_sort_key))
    status = (
        AuditComparisonStatus.CHANGED
        if ordered
        else AuditComparisonStatus.IDENTICAL
    )
    return AuditPackageComparisonResult(
        status=status,
        baseline_package_id=baseline.package_id,
        candidate_package_id=candidate.package_id,
        changes=ordered,
    )
