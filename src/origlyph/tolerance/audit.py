"""Deterministic audit package and replay manifest (Stage 15O).

This module packages an existing Stage 15M decision report and Stage 15N
integrity result.  It performs structural verification only and never calls
authoritative tolerance engines.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .integrity import (
    AuditIntegrityResult,
    AuditIntegritySeverity,
    AuditIntegrityStatus,
    AuditIntegrityViolation,
    AuditIntegrityViolationCode,
    validate_decision_report_integrity,
)
from .report import (
    REPORT_SCHEMA_VERSION,
    DecisionProvenance,
    ReportMetricValue,
    ReportSection,
    ToleranceDecisionReport,
    decision_report_from_dict,
)

__all__ = [
    "AUDIT_PACKAGE_SCHEMA_VERSION",
    "ReplayabilityStatus",
    "DecisionReplayManifest",
    "ToleranceDecisionAuditPackage",
    "InvalidDecisionAuditPackageError",
    "build_decision_audit_package",
    "audit_package_from_dict",
    "verify_decision_audit_package",
]


AUDIT_PACKAGE_SCHEMA_VERSION = "origlyph.tolerance.audit_package.v1"

_REQUIRE_COMPLETE_POLICY = "not_recorded_by_report_schema_v1"
_POLICY_IDENTIFIERS = (
    "canonical_json_sort_keys_allow_nan_false.v1",
    "sha256.v1",
    "stage15n_integrity_valid_required_for_replay.v1",
    _REQUIRE_COMPLETE_POLICY,
)
_REPORT_METRIC_SECTIONS = (
    ReportSection.WORST_CASE,
    ReportSection.STATISTICAL,
    ReportSection.CORRELATION,
    ReportSection.SENSITIVITY,
    ReportSection.BUDGET,
    ReportSection.ALLOCATION,
    ReportSection.WORST_CASE_RECONCILIATION,
    ReportSection.STATISTICAL_RECONCILIATION,
)


class InvalidDecisionAuditPackageError(ValueError):
    """Raised when an audit package contract is malformed or unsupported."""


class ReplayabilityStatus(Enum):
    """Structural replay-readiness state, independent of engineering status."""

    REPLAYABLE = "replayable"
    NOT_REPLAYABLE = "not_replayable"
    INCOMPLETE = "incomplete"


def _canonical_json(payload: object, *, context: str) -> str:
    """Serialize deterministic content or fail closed."""
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object, *, context: str) -> str:
    canonical = _canonical_json(payload, context=context)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _provenance_as_dict(
    provenance: DecisionProvenance | None,
) -> dict[str, object] | None:
    if provenance is None:
        return None
    return {
        "generated_by": provenance.generated_by,
        "generation_timestamp": provenance.generation_timestamp,
        "audit_id": provenance.audit_id,
        "metadata": provenance.metadata,
    }


def _canonical_input_payload(report: ToleranceDecisionReport) -> dict[str, object]:
    """Return the deterministic input surface available in report schema v1.

    Raw stacks and the Stage 15K ``require_complete`` invocation flag are not
    present in Stage 15M.  Their absence is represented explicitly rather than
    inferred from output state.
    """
    return {
        "contributors": [item.as_dict() for item in report.contributors],
        "metric_sections": {
            section.value: report.section(section)["metrics"]
            for section in _REPORT_METRIC_SECTIONS
        },
        "equality_tolerance": float(report.equality_tolerance),
        "sigma_multiplier": (
            float(report.sigma_multiplier)
            if report.sigma_multiplier is not None
            else None
        ),
        "require_complete_policy": _REQUIRE_COMPLETE_POLICY,
    }


def _correlation_assumptions(
    report: ToleranceDecisionReport,
) -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (
                (metric.key, float(metric.value))
                for metric in report.correlation_metrics
            ),
            key=lambda item: item[0],
        )
    )


@dataclass(frozen=True, slots=True)
class DecisionReplayManifest:
    """Immutable structural replay contract for one decision report."""

    report_schema_version: str
    audit_schema_version: str
    decision_id: str
    package_id: str
    equality_tolerance: float
    sigma_multiplier: float | None
    require_complete_policy: str
    correlation_assumptions: tuple[tuple[str, float], ...]
    input_fingerprint: str
    report_fingerprint: str
    integrity_fingerprint: str
    integrity_status: AuditIntegrityStatus
    policy_identifiers: tuple[str, ...]
    is_complete: bool

    # Manifest contract validation is intentionally centralized and fail closed.
    def __post_init__(self) -> None:  # noqa: C901
        string_fields = (
            self.report_schema_version,
            self.audit_schema_version,
            self.decision_id,
            self.package_id,
            self.require_complete_policy,
            self.input_fingerprint,
            self.report_fingerprint,
            self.integrity_fingerprint,
        )
        if not all(isinstance(value, str) for value in string_fields):
            raise InvalidDecisionAuditPackageError(
                "manifest identity and policy fields must be strings"
            )
        if not isinstance(self.integrity_status, AuditIntegrityStatus):
            raise InvalidDecisionAuditPackageError(
                "manifest integrity_status must be AuditIntegrityStatus"
            )
        if not isinstance(self.policy_identifiers, tuple) or not all(
            isinstance(value, str) for value in self.policy_identifiers
        ):
            raise InvalidDecisionAuditPackageError(
                "manifest policy_identifiers must be a tuple of strings"
            )
        if not isinstance(self.correlation_assumptions, tuple):
            raise InvalidDecisionAuditPackageError(
                "manifest correlation_assumptions must be a tuple"
            )
        if not isinstance(self.equality_tolerance, (int, float)) or isinstance(
            self.equality_tolerance, bool
        ):
            raise InvalidDecisionAuditPackageError(
                "manifest equality_tolerance must be numeric"
            )
        if self.sigma_multiplier is not None and (
            not isinstance(self.sigma_multiplier, (int, float))
            or isinstance(self.sigma_multiplier, bool)
        ):
            raise InvalidDecisionAuditPackageError(
                "manifest sigma_multiplier must be numeric or None"
            )
        for item in self.correlation_assumptions:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not isinstance(item[1], (int, float))
                or isinstance(item[1], bool)
            ):
                raise InvalidDecisionAuditPackageError(
                    "manifest correlation assumptions are malformed"
                )
        if self.correlation_assumptions != tuple(
            sorted(self.correlation_assumptions, key=lambda item: item[0])
        ):
            raise InvalidDecisionAuditPackageError(
                "manifest correlation assumptions must be canonically ordered"
            )
        if not isinstance(self.is_complete, bool):
            raise InvalidDecisionAuditPackageError(
                "manifest is_complete must be bool"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "report_schema_version": self.report_schema_version,
            "audit_schema_version": self.audit_schema_version,
            "decision_id": self.decision_id,
            "package_id": self.package_id,
            "equality_tolerance": float(self.equality_tolerance),
            "sigma_multiplier": (
                float(self.sigma_multiplier)
                if self.sigma_multiplier is not None
                else None
            ),
            "require_complete_policy": self.require_complete_policy,
            "correlation_assumptions": [
                {"metric_key": key, "coefficient": float(coefficient)}
                for key, coefficient in self.correlation_assumptions
            ],
            "input_fingerprint": self.input_fingerprint,
            "report_fingerprint": self.report_fingerprint,
            "integrity_fingerprint": self.integrity_fingerprint,
            "integrity_status": self.integrity_status.value,
            "policy_identifiers": list(self.policy_identifiers),
            "is_complete": self.is_complete,
        }


@dataclass(frozen=True, slots=True)
class ToleranceDecisionAuditPackage:
    """Immutable Stage 15O audit package."""

    audit_schema_version: str
    package_id: str
    report: ToleranceDecisionReport
    integrity_result: AuditIntegrityResult
    replay_manifest: DecisionReplayManifest
    replayability_status: ReplayabilityStatus
    provenance: DecisionProvenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.audit_schema_version, str) or not isinstance(
            self.package_id, str
        ):
            raise InvalidDecisionAuditPackageError(
                "package schema and identity must be strings"
            )
        if not isinstance(self.report, ToleranceDecisionReport):
            raise InvalidDecisionAuditPackageError(
                "package report must be a ToleranceDecisionReport"
            )
        if not isinstance(self.integrity_result, AuditIntegrityResult):
            raise InvalidDecisionAuditPackageError(
                "package integrity_result must be an AuditIntegrityResult"
            )
        if not isinstance(self.replay_manifest, DecisionReplayManifest):
            raise InvalidDecisionAuditPackageError(
                "package replay_manifest must be a DecisionReplayManifest"
            )
        if not isinstance(self.replayability_status, ReplayabilityStatus):
            raise InvalidDecisionAuditPackageError(
                "package replayability_status must be ReplayabilityStatus"
            )
        if self.provenance is not None and not isinstance(
            self.provenance, DecisionProvenance
        ):
            raise InvalidDecisionAuditPackageError(
                "package provenance must be DecisionProvenance or None"
            )

    @property
    def is_replayable(self) -> bool:
        return self.replayability_status is ReplayabilityStatus.REPLAYABLE

    def as_dict(self) -> dict[str, object]:
        return {
            "audit_schema_version": self.audit_schema_version,
            "package_id": self.package_id,
            "report": self.report.as_dict(),
            "integrity_result": self.integrity_result.as_dict(),
            "replay_manifest": self.replay_manifest.as_dict(),
            "replayability_status": self.replayability_status.value,
            "provenance": _provenance_as_dict(self.provenance),
        }

    def to_json(self) -> str:
        return _canonical_json(self.as_dict(), context="audit package")


def _manifest_identity_payload(manifest: DecisionReplayManifest) -> dict[str, object]:
    payload = manifest.as_dict()
    payload.pop("package_id")
    return payload


def _expected_package_id(
    report: ToleranceDecisionReport,
    integrity_result: AuditIntegrityResult,
    manifest: DecisionReplayManifest,
) -> str:
    return _fingerprint(
        {
            "audit_schema_version": AUDIT_PACKAGE_SCHEMA_VERSION,
            "decision_id": report.decision_id(),
            "report_fingerprint": _fingerprint(
                report.as_dict(), context="report payload"
            ),
            "integrity_fingerprint": _fingerprint(
                integrity_result.as_dict(), context="integrity result"
            ),
            "replay_manifest": _manifest_identity_payload(manifest),
        },
        context="package identity",
    )


def _manifest_is_complete(manifest: DecisionReplayManifest) -> bool:
    if manifest.report_schema_version != REPORT_SCHEMA_VERSION:
        return False
    if manifest.audit_schema_version != AUDIT_PACKAGE_SCHEMA_VERSION:
        return False
    if not manifest.decision_id or not manifest.require_complete_policy:
        return False
    if not math.isfinite(manifest.equality_tolerance):
        return False
    if manifest.sigma_multiplier is not None and not math.isfinite(
        manifest.sigma_multiplier
    ):
        return False
    for key, coefficient in manifest.correlation_assumptions:
        if not key or not math.isfinite(coefficient):
            return False
    fingerprints = (
        manifest.input_fingerprint,
        manifest.report_fingerprint,
        manifest.integrity_fingerprint,
    )
    return all(_is_sha256(value) for value in fingerprints)


def _replayability(
    integrity_status: AuditIntegrityStatus,
    manifest_complete: bool,
) -> ReplayabilityStatus:
    if not manifest_complete or integrity_status is AuditIntegrityStatus.INCOMPLETE:
        return ReplayabilityStatus.INCOMPLETE
    if integrity_status is AuditIntegrityStatus.VALID:
        return ReplayabilityStatus.REPLAYABLE
    return ReplayabilityStatus.NOT_REPLAYABLE


def build_decision_audit_package(
    report: ToleranceDecisionReport,
    integrity_result: AuditIntegrityResult | None = None,
    *,
    provenance: DecisionProvenance | None = None,
) -> ToleranceDecisionAuditPackage:
    """Package existing deterministic artifacts without engineering recomputation."""
    if not isinstance(report, ToleranceDecisionReport):
        raise InvalidDecisionAuditPackageError(
            "report must be a ToleranceDecisionReport"
        )
    if report.schema_version != REPORT_SCHEMA_VERSION:
        raise InvalidDecisionAuditPackageError(
            f"unsupported report schema {report.schema_version!r}"
        )
    if integrity_result is None:
        integrity = validate_decision_report_integrity(report)
    elif isinstance(integrity_result, AuditIntegrityResult):
        integrity = integrity_result
    else:
        raise InvalidDecisionAuditPackageError(
            "integrity_result must be an AuditIntegrityResult or None"
        )
    selected_provenance = provenance if provenance is not None else report.provenance
    if selected_provenance is not None and not isinstance(
        selected_provenance, DecisionProvenance
    ):
        raise InvalidDecisionAuditPackageError(
            "provenance must be a DecisionProvenance or None"
        )
    _canonical_json(report.as_dict(), context="report payload")
    _canonical_json(integrity.as_dict(), context="integrity result")
    _canonical_json(
        _provenance_as_dict(selected_provenance), context="provenance payload"
    )

    manifest = DecisionReplayManifest(
        report_schema_version=report.schema_version,
        audit_schema_version=AUDIT_PACKAGE_SCHEMA_VERSION,
        decision_id=report.decision_id(),
        package_id="",
        equality_tolerance=float(report.equality_tolerance),
        sigma_multiplier=report.sigma_multiplier,
        require_complete_policy=_REQUIRE_COMPLETE_POLICY,
        correlation_assumptions=_correlation_assumptions(report),
        input_fingerprint=_fingerprint(
            _canonical_input_payload(report), context="deterministic input surface"
        ),
        report_fingerprint=_fingerprint(
            report.as_dict(), context="report payload"
        ),
        integrity_fingerprint=_fingerprint(
            integrity.as_dict(), context="integrity result"
        ),
        integrity_status=integrity.status,
        policy_identifiers=_POLICY_IDENTIFIERS,
        is_complete=False,
    )
    manifest = replace(manifest, is_complete=_manifest_is_complete(manifest))
    package_id = _expected_package_id(report, integrity, manifest)
    manifest = replace(manifest, package_id=package_id)
    replayability = _replayability(integrity.status, manifest.is_complete)
    return ToleranceDecisionAuditPackage(
        audit_schema_version=AUDIT_PACKAGE_SCHEMA_VERSION,
        package_id=package_id,
        report=report,
        integrity_result=integrity,
        replay_manifest=manifest,
        replayability_status=replayability,
        provenance=selected_provenance,
    )


def _require_dict(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidDecisionAuditPackageError(f"{field_name} must be a dict")
    return value


def _require_exact_keys(
    payload: dict[str, Any], required: set[str], *, field_name: str
) -> None:
    actual = set(payload)
    if actual != required:
        missing = sorted(required - actual)
        unknown = sorted(actual - required)
        raise InvalidDecisionAuditPackageError(
            f"{field_name} keys invalid; missing={missing}, unknown={unknown}"
        )


def _parse_metric(payload: object) -> ReportMetricValue:
    data = _require_dict(payload, field_name="report metric")
    allowed = {"key", "value", "lower_bound", "upper_bound"}
    if not {"key", "value"}.issubset(data) or not set(data).issubset(allowed):
        raise InvalidDecisionAuditPackageError("report metric fields are malformed")
    try:
        return ReportMetricValue(
            key=data["key"],
            value=data["value"],
            lower_bound=data.get("lower_bound"),
            upper_bound=data.get("upper_bound"),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"invalid report metric: {exc}"
        ) from exc


def _parse_section_metrics(
    sections: dict[str, Any], section: ReportSection
) -> tuple[ReportMetricValue, ...]:
    section_payload = _require_dict(
        sections.get(section.value), field_name=f"report section {section.value}"
    )
    metrics = section_payload.get("metrics")
    if not isinstance(metrics, list):
        raise InvalidDecisionAuditPackageError(
            f"report section {section.value} metrics must be a list"
        )
    return tuple(_parse_metric(metric) for metric in metrics)


def _parse_provenance(payload: object) -> DecisionProvenance | None:
    if payload is None:
        return None
    data = _require_dict(payload, field_name="provenance")
    required = {"generated_by", "generation_timestamp", "audit_id", "metadata"}
    _require_exact_keys(data, required, field_name="provenance")
    metadata = data["metadata"]
    if not isinstance(metadata, dict):
        raise InvalidDecisionAuditPackageError("provenance.metadata must be a dict")
    provenance = DecisionProvenance(
        generated_by=data["generated_by"],
        generation_timestamp=data["generation_timestamp"],
        audit_id=data["audit_id"],
        metadata=metadata,
    )
    _canonical_json(_provenance_as_dict(provenance), context="provenance payload")
    return provenance


def _parse_report(
    payload: object, provenance: DecisionProvenance | None
) -> ToleranceDecisionReport:
    data = _require_dict(payload, field_name="report")
    report_fields = {
        "schema_version",
        "final_status",
        "is_complete",
        "summary_code",
        "summary_text",
        "governing_reason_codes",
        "marginal_reason_codes",
        "supporting_reason_codes",
        "triggered_reasons",
        "contributors",
        "sections",
        "section_order",
        "evidence_refs",
        "equality_tolerance",
        "sigma_multiplier",
    }
    _require_exact_keys(data, report_fields, field_name="report")
    if data.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise InvalidDecisionAuditPackageError(
            f"unsupported report schema {data.get('schema_version')!r}"
        )
    try:
        base = decision_report_from_dict(data)
        sections = _require_dict(data.get("sections"), field_name="report.sections")
        expected_sections = {section.value for section in ReportSection}
        _require_exact_keys(
            sections, expected_sections, field_name="report.sections"
        )
        for section_name, raw_section in sections.items():
            section_data = _require_dict(
                raw_section, field_name=f"report section {section_name}"
            )
            _require_exact_keys(
                section_data,
                {"metrics", "reason_refs", "evidence_refs"},
                field_name=f"report section {section_name}",
            )
        rebuilt = replace(
            base,
            worst_case_metrics=_parse_section_metrics(
                sections, ReportSection.WORST_CASE
            ),
            statistical_metrics=_parse_section_metrics(
                sections, ReportSection.STATISTICAL
            ),
            correlation_metrics=_parse_section_metrics(
                sections, ReportSection.CORRELATION
            ),
            sensitivity_metrics=_parse_section_metrics(
                sections, ReportSection.SENSITIVITY
            ),
            budget_metrics=_parse_section_metrics(sections, ReportSection.BUDGET),
            allocation_metrics=_parse_section_metrics(
                sections, ReportSection.ALLOCATION
            ),
            worst_case_reconciliation_metrics=_parse_section_metrics(
                sections, ReportSection.WORST_CASE_RECONCILIATION
            ),
            statistical_reconciliation_metrics=_parse_section_metrics(
                sections, ReportSection.STATISTICAL_RECONCILIATION
            ),
            provenance=provenance,
        )
        if rebuilt.as_dict() != data:
            raise InvalidDecisionAuditPackageError(
                "report payload does not round-trip without data loss"
            )
        return rebuilt
    except InvalidDecisionAuditPackageError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"invalid report payload: {exc}"
        ) from exc


def _parse_integrity_result(payload: object) -> AuditIntegrityResult:
    data = _require_dict(payload, field_name="integrity_result")
    _require_exact_keys(data, {"status", "violations"}, field_name="integrity_result")
    raw_violations = data["violations"]
    if not isinstance(raw_violations, list):
        raise InvalidDecisionAuditPackageError(
            "integrity_result.violations must be a list"
        )
    try:
        violations = tuple(
            AuditIntegrityViolation(
                code=AuditIntegrityViolationCode(item["code"]),
                severity=AuditIntegritySeverity(item["severity"]),
                scope=item["scope"],
                subject=item["subject"],
                detail=item["detail"],
            )
            for raw in raw_violations
            for item in [_require_dict(raw, field_name="integrity violation")]
            if not _require_exact_keys(
                item,
                {"code", "severity", "scope", "subject", "detail"},
                field_name="integrity violation",
            )
        )
        return AuditIntegrityResult(
            status=AuditIntegrityStatus(data["status"]), violations=violations
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"invalid integrity result payload: {exc}"
        ) from exc


def _parse_manifest(payload: object) -> DecisionReplayManifest:
    data = _require_dict(payload, field_name="replay_manifest")
    required = {
        "report_schema_version",
        "audit_schema_version",
        "decision_id",
        "package_id",
        "equality_tolerance",
        "sigma_multiplier",
        "require_complete_policy",
        "correlation_assumptions",
        "input_fingerprint",
        "report_fingerprint",
        "integrity_fingerprint",
        "integrity_status",
        "policy_identifiers",
        "is_complete",
    }
    _require_exact_keys(data, required, field_name="replay_manifest")
    correlations = data["correlation_assumptions"]
    policies = data["policy_identifiers"]
    if not isinstance(correlations, list) or not isinstance(policies, list):
        raise InvalidDecisionAuditPackageError(
            "manifest correlations and policy identifiers must be lists"
        )
    try:
        correlation_assumptions = tuple(
            (item["metric_key"], float(item["coefficient"]))
            for raw in correlations
            for item in [_require_dict(raw, field_name="correlation assumption")]
            if not _require_exact_keys(
                item,
                {"metric_key", "coefficient"},
                field_name="correlation assumption",
            )
        )
        return DecisionReplayManifest(
            report_schema_version=data["report_schema_version"],
            audit_schema_version=data["audit_schema_version"],
            decision_id=data["decision_id"],
            package_id=data["package_id"],
            equality_tolerance=float(data["equality_tolerance"]),
            sigma_multiplier=(
                float(data["sigma_multiplier"])
                if data["sigma_multiplier"] is not None
                else None
            ),
            require_complete_policy=data["require_complete_policy"],
            correlation_assumptions=correlation_assumptions,
            input_fingerprint=data["input_fingerprint"],
            report_fingerprint=data["report_fingerprint"],
            integrity_fingerprint=data["integrity_fingerprint"],
            integrity_status=AuditIntegrityStatus(data["integrity_status"]),
            policy_identifiers=tuple(policies),
            is_complete=data["is_complete"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"invalid replay manifest payload: {exc}"
        ) from exc


def _verify_fingerprints(package: ToleranceDecisionAuditPackage) -> bool:
    manifest = package.replay_manifest
    return (
        manifest.report_fingerprint
        == _fingerprint(package.report.as_dict(), context="report payload")
        and manifest.input_fingerprint
        == _fingerprint(
            _canonical_input_payload(package.report),
            context="deterministic input surface",
        )
        and manifest.integrity_fingerprint
        == _fingerprint(
            package.integrity_result.as_dict(), context="integrity result"
        )
    )


# Package verification remains centralized so every fail-closed check is visible.
def verify_decision_audit_package(  # noqa: C901
    package: ToleranceDecisionAuditPackage,
) -> ReplayabilityStatus:
    """Verify package structure without rerunning engineering calculations."""
    if not isinstance(package, ToleranceDecisionAuditPackage):
        raise InvalidDecisionAuditPackageError(
            "package must be a ToleranceDecisionAuditPackage"
        )
    manifest = package.replay_manifest
    if (
        package.audit_schema_version != AUDIT_PACKAGE_SCHEMA_VERSION
        or manifest.audit_schema_version != AUDIT_PACKAGE_SCHEMA_VERSION
        or package.report.schema_version != REPORT_SCHEMA_VERSION
        or manifest.report_schema_version != REPORT_SCHEMA_VERSION
    ):
        return ReplayabilityStatus.INCOMPLETE
    if not _manifest_is_complete(manifest) or not manifest.is_complete:
        return ReplayabilityStatus.INCOMPLETE
    try:
        if not _verify_fingerprints(package):
            return ReplayabilityStatus.NOT_REPLAYABLE
        if manifest.decision_id != package.report.decision_id():
            return ReplayabilityStatus.NOT_REPLAYABLE
        if manifest.package_id != package.package_id:
            return ReplayabilityStatus.NOT_REPLAYABLE
        if package.package_id != _expected_package_id(
            package.report, package.integrity_result, manifest
        ):
            return ReplayabilityStatus.NOT_REPLAYABLE
        if manifest.integrity_status is not package.integrity_result.status:
            return ReplayabilityStatus.NOT_REPLAYABLE
        if validate_decision_report_integrity(package.report) != (
            package.integrity_result
        ):
            return ReplayabilityStatus.NOT_REPLAYABLE
        payload = package.as_dict()
        rebuilt = audit_package_from_dict(payload, verify=False)
        if rebuilt.as_dict() != payload:
            return ReplayabilityStatus.NOT_REPLAYABLE
    except InvalidDecisionAuditPackageError:
        return ReplayabilityStatus.NOT_REPLAYABLE
    return _replayability(package.integrity_result.status, manifest.is_complete)


def audit_package_from_dict(
    payload: dict[str, Any], *, verify: bool = True
) -> ToleranceDecisionAuditPackage:
    """Rebuild an audit package from its complete deterministic payload."""
    data = _require_dict(payload, field_name="audit package")
    required = {
        "audit_schema_version",
        "package_id",
        "report",
        "integrity_result",
        "replay_manifest",
        "replayability_status",
        "provenance",
    }
    _require_exact_keys(data, required, field_name="audit package")
    if data["audit_schema_version"] != AUDIT_PACKAGE_SCHEMA_VERSION:
        raise InvalidDecisionAuditPackageError(
            f"unsupported audit schema {data['audit_schema_version']!r}"
        )
    provenance = _parse_provenance(data["provenance"])
    report = _parse_report(data["report"], provenance)
    integrity = _parse_integrity_result(data["integrity_result"])
    manifest = _parse_manifest(data["replay_manifest"])
    try:
        replayability = ReplayabilityStatus(data["replayability_status"])
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionAuditPackageError(
            f"invalid replayability status: {exc}"
        ) from exc
    package = ToleranceDecisionAuditPackage(
        audit_schema_version=data["audit_schema_version"],
        package_id=data["package_id"],
        report=report,
        integrity_result=integrity,
        replay_manifest=manifest,
        replayability_status=replayability,
        provenance=provenance,
    )
    if verify:
        expected = _expected_package_id(report, integrity, manifest)
        if package.package_id != expected or manifest.package_id != expected:
            raise InvalidDecisionAuditPackageError("package_id mismatch")
        if not _verify_fingerprints(package):
            raise InvalidDecisionAuditPackageError("audit fingerprint mismatch")
        expected_replayability = verify_decision_audit_package(package)
        if replayability is not expected_replayability:
            raise InvalidDecisionAuditPackageError(
                "replayability status does not match verified package state"
            )
    return package
