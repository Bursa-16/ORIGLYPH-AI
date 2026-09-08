"""Deterministic audit-integrity validation (Stage 15N).

This module validates the internal structural consistency of a Stage 15M
:class:`~origlyph.tolerance.report.ToleranceDecisionReport` envelope.

Stage 15N sits ABOVE the Stage 15M report envelope:

    authoritative tolerance engines
            |
    Stage 15K decision layer
            |
    Stage 15L evidence / explainability layer
            |
    Stage 15M report envelope
            |
    Stage 15N audit-integrity validation   (this module)

Stage 15N checks integrity only.  It does NOT recompute any engineering
calculation, does NOT call any authoritative engine, and does NOT modify
any upstream object.  It inspects the report envelope for structural
contradictions, broken references, non-finite payload values, and
deterministic-identity drift.

An integrity VALID result means the decision package is structurally
consistent; it does NOT mean the engineering decision is PASS.  Optional
provenance metadata does not alter deterministic decision identity.

AI does not override deterministic tolerance calculations.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .exceptions import OriglyphToleranceError
from .models import ToleranceDecisionReasonCode, ToleranceDecisionStatus
from .report import (
    REPORT_SCHEMA_VERSION,
    ToleranceDecisionReport,
    decision_report_from_dict,
)

__all__ = [
    "AuditIntegrityStatus",
    "AuditIntegritySeverity",
    "AuditIntegrityViolationCode",
    "AuditIntegrityViolation",
    "AuditIntegrityResult",
    "InvalidAuditIntegrityError",
    "validate_decision_report_integrity",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class InvalidAuditIntegrityError(OriglyphToleranceError):
    """Raised when the integrity validator is invoked with an unsupported type.

    This is an invocation error, not an inspectable integrity failure.
    """


# ---------------------------------------------------------------------------
# Status / severity / violation models
# ---------------------------------------------------------------------------


class AuditIntegrityStatus(Enum):
    """Top-level integrity verdict.

    Members
    -------
    VALID:
        No integrity violations were found.
    INCOMPLETE:
        Validation could not be fully performed (for example, an unsupported
        schema version).  Any emitted violations are still reported.
    INVALID:
        One or more integrity violations were found.
    """

    VALID = "valid"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


class AuditIntegritySeverity(Enum):
    """Severity of a single integrity violation.

    All current violations are ERROR.  WARNING is reserved for future use.
    """

    ERROR = "error"
    WARNING = "warning"


class AuditIntegrityViolationCode(Enum):
    """Stable, serialization-safe integrity violation codes.

    The string values are the authoritative identity.
    """

    STATUS_MISMATCH = "status_mismatch"
    COMPLETENESS_MISMATCH = "completeness_mismatch"
    MISSING_REASON_LINK = "missing_reason_link"
    ORPHAN_REASON_LINK = "orphan_reason_link"
    MISSING_GOVERNING_EVIDENCE = "missing_governing_evidence"
    MISSING_MARGINAL_EVIDENCE = "missing_marginal_evidence"
    DUPLICATE_EVIDENCE_ID = "duplicate_evidence_id"
    BROKEN_EVIDENCE_REFERENCE = "broken_evidence_reference"
    UNSUPPORTED_EVIDENCE_SOURCE = "unsupported_evidence_source"
    UNKNOWN_SUBJECT_REFERENCE = "unknown_subject_reference"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    DECISION_ID_MISMATCH = "decision_id_mismatch"
    ROUND_TRIP_MISMATCH = "round_trip_mismatch"
    NON_FINITE_VALUE = "non_finite_value"
    INVALID_REPORT_TYPE = "invalid_report_type"


@dataclass(frozen=True)
class AuditIntegrityViolation:
    """One immutable, deterministic integrity violation."""

    code: AuditIntegrityViolationCode
    severity: AuditIntegritySeverity
    scope: str
    subject: str
    detail: str


@dataclass(frozen=True)
class AuditIntegrityResult:
    """Immutable, deterministic integrity-validation result."""

    status: AuditIntegrityStatus
    violations: tuple[AuditIntegrityViolation, ...]

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization."""
        return {
            "status": self.status.value,
            "violations": [
                {
                    "code": v.code.value,
                    "severity": v.severity.value,
                    "scope": v.scope,
                    "subject": v.subject,
                    "detail": v.detail,
                }
                for v in self.violations
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _violation_sort_key(v: AuditIntegrityViolation) -> tuple[str, str, str, str]:
    """Deterministic violation ordering key."""
    return (v.severity.value, v.code.value, v.scope, v.subject)


def _add_violation(
    violations: list[AuditIntegrityViolation],
    code: AuditIntegrityViolationCode,
    scope: str,
    subject: str,
    detail: str,
    severity: AuditIntegritySeverity = AuditIntegritySeverity.ERROR,
) -> None:
    """Append a deterministic violation."""
    violations.append(
        AuditIntegrityViolation(
            code=code,
            severity=severity,
            scope=scope,
            subject=subject,
            detail=detail,
        )
    )


def _check_status_consistency(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check final_status vs summary_code prefix and reason-code consistency."""
    prefix_map = {
        ToleranceDecisionStatus.PASS: "pass:",
        ToleranceDecisionStatus.FAIL: "fail:",
        ToleranceDecisionStatus.MARGINAL: "marginal:",
        ToleranceDecisionStatus.INCOMPLETE: "incomplete:",
    }
    expected_prefix = prefix_map.get(report.final_status)
    if expected_prefix is not None and not report.summary_code.startswith(
        expected_prefix
    ):
        _add_violation(
            violations,
            AuditIntegrityViolationCode.STATUS_MISMATCH,
            "report.summary_code",
            report.summary_code,
            f"summary_code {report.summary_code!r} does not match "
            f"final_status {report.final_status.value!r}",
        )

    if report.final_status is ToleranceDecisionStatus.PASS:
        if report.governing_reason_codes:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.STATUS_MISMATCH,
                "report.governing_reason_codes",
                str(tuple(c.value for c in report.governing_reason_codes)),
                "PASS status must not have governing reasons",
            )
        if report.marginal_reason_codes:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.STATUS_MISMATCH,
                "report.marginal_reason_codes",
                str(tuple(c.value for c in report.marginal_reason_codes)),
                "PASS status must not have marginal reasons",
            )
    elif report.final_status is ToleranceDecisionStatus.FAIL:
        if not report.governing_reason_codes:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.MISSING_GOVERNING_EVIDENCE,
                "report.governing_reason_codes",
                "",
                "FAIL status must have governing reasons",
            )
    elif report.final_status is ToleranceDecisionStatus.MARGINAL:
        if not report.marginal_reason_codes:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.MISSING_MARGINAL_EVIDENCE,
                "report.marginal_reason_codes",
                "",
                "MARGINAL status must have marginal reasons",
            )


def _check_completeness_consistency(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check is_complete vs final_status consistency."""
    if (
        not report.is_complete
        and report.final_status is not ToleranceDecisionStatus.INCOMPLETE
    ):
        _add_violation(
            violations,
            AuditIntegrityViolationCode.COMPLETENESS_MISMATCH,
            "report.is_complete",
            str(report.is_complete),
            f"is_complete=False but final_status is "
            f"{report.final_status.value!r}, expected incomplete",
        )


def _check_reason_linkage(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check reason-to-evidence linkage and evidence-reference integrity."""
    evidence_id_set = {ref.evidence_id for ref in report.evidence_refs}
    triggered_codes = {ref.reason_code for ref in report.triggered_reasons}

    for reason_ref in report.triggered_reasons:
        for eid in reason_ref.evidence_ids:
            if eid not in evidence_id_set:
                _add_violation(
                    violations,
                    AuditIntegrityViolationCode.BROKEN_EVIDENCE_REFERENCE,
                    "report.triggered_reasons",
                    eid,
                    f"reason {reason_ref.reason_code.value} references "
                    f"unknown evidence {eid!r}",
                )

        if reason_ref.reason_code in report.governing_reason_codes:
            if not reason_ref.evidence_ids:
                _add_violation(
                    violations,
                    AuditIntegrityViolationCode.MISSING_GOVERNING_EVIDENCE,
                    "report.triggered_reasons",
                    reason_ref.reason_code.value,
                    f"governing reason {reason_ref.reason_code.value} "
                    f"has no evidence",
                )
        elif reason_ref.reason_code in report.marginal_reason_codes:
            if not reason_ref.evidence_ids:
                _add_violation(
                    violations,
                    AuditIntegrityViolationCode.MISSING_MARGINAL_EVIDENCE,
                    "report.triggered_reasons",
                    reason_ref.reason_code.value,
                    f"marginal reason {reason_ref.reason_code.value} "
                    f"has no evidence",
                )
        elif not reason_ref.evidence_ids:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.MISSING_REASON_LINK,
                "report.triggered_reasons",
                reason_ref.reason_code.value,
                f"triggered reason {reason_ref.reason_code.value} has "
                f"no evidence link",
            )


    _check_orphan_reason_links(report, triggered_codes, violations)


def _check_orphan_reason_links(
    report: ToleranceDecisionReport,
    triggered_codes: set[ToleranceDecisionReasonCode],
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check evidence-to-reason links and reason partition membership."""
    for ref in report.evidence_refs:
        if ref.reason_code and ref.reason_code not in {
            c.value for c in triggered_codes
        }:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.ORPHAN_REASON_LINK,
                "report.evidence_refs",
                ref.evidence_id,
                f"evidence {ref.evidence_id!r} references reason "
                f"{ref.reason_code!r} not present in triggered reasons",
            )

    all_partitioned = (
        set(report.governing_reason_codes)
        | set(report.marginal_reason_codes)
        | set(report.supporting_reason_codes)
    )
    for code in triggered_codes:
        if code not in all_partitioned:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.ORPHAN_REASON_LINK,
                "report.triggered_reasons",
                code.value,
                f"triggered reason {code.value} is not partitioned into "
                f"governing/marginal/supporting reason codes",
            )


def _check_evidence_uniqueness_and_sources(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check evidence-ID uniqueness and source validity."""
    from .evidence import DecisionEvidenceSource

    valid_sources = {src.value for src in DecisionEvidenceSource}
    seen_ids: set[str] = set()

    for ref in report.evidence_refs:
        if ref.evidence_id in seen_ids:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.DUPLICATE_EVIDENCE_ID,
                "report.evidence_refs",
                ref.evidence_id,
                f"duplicate evidence_id {ref.evidence_id!r}",
            )
        else:
            seen_ids.add(ref.evidence_id)

        if ref.source not in valid_sources:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.UNSUPPORTED_EVIDENCE_SOURCE,
                "report.evidence_refs",
                ref.evidence_id,
                f"unsupported evidence source {ref.source!r}",
            )


#: Structural subject tokens that appear in canonical evidence IDs but are
#: not contributor references (requirement, allocation, covariance or
#: criteria level subjects).
_STRUCTURAL_SUBJECTS: frozenset[str] = frozenset(
    {
        "worst_case_requirement",
        "statistical_requirement",
        "worst_case_allocation",
        "statistical_allocation",
        "covariance",
        "criteria",
        "combined_sigma",
        "-",
        "",
    }
)


def _check_subject_references(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check contributor references embedded in evidence IDs.

    Canonical evidence IDs use the shape
    ``source:evidence_code:scope:subject_id:index``.  When the report
    carries a contributor table, every subject token that is not a
    known structural subject must resolve to a contributor name.
    Covariance pair subjects use the ``A|B`` orientation.
    """
    known_contributors = {contributor.name for contributor in report.contributors}
    if not known_contributors:
        return

    for ref in report.evidence_refs:
        parts = ref.evidence_id.split(":")
        if len(parts) < 5:
            continue
        subject = parts[3]
        if subject in _STRUCTURAL_SUBJECTS:
            continue
        for name in subject.split("|"):
            if name and name not in known_contributors:
                _add_violation(
                    violations,
                    AuditIntegrityViolationCode.UNKNOWN_SUBJECT_REFERENCE,
                    "report.evidence_refs",
                    ref.evidence_id,
                    f"evidence {ref.evidence_id!r} references unknown "
                    f"contributor {name!r}",
                )


def _check_decision_id(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Recompute the deterministic decision identity and compare."""
    try:
        payload = report.as_dict()
        expected = json.dumps(
            payload, sort_keys=True, allow_nan=False, ensure_ascii=True
        )
        actual = report.decision_id()
        if actual != expected:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.DECISION_ID_MISMATCH,
                "report.decision_id",
                actual,
                "decision_id does not match canonical identity",
            )
    except Exception as exc:
        _add_violation(
            violations,
            AuditIntegrityViolationCode.DECISION_ID_MISMATCH,
            "report.decision_id",
            "",
            f"decision_id verification failed: {exc}",
        )


def _strip_sections_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the payload with section metrics removed.

    Stage 15M's ``decision_report_from_dict`` rebuilds all metric sections as
    empty tuples.  The round-trip check therefore compares the preserved
    structural surface only.
    """
    result = dict(payload)
    sections = result.get("sections")
    if isinstance(sections, dict):
        stripped_sections: dict[str, Any] = {}
        for key, section in sections.items():
            if isinstance(section, dict):
                s = dict(section)
                s.pop("metrics", None)
                stripped_sections[key] = s
            else:
                stripped_sections[key] = section
        result["sections"] = stripped_sections
    return result


def _check_round_trip(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Check as_dict -> from_dict -> as_dict preserves the payload."""
    try:
        original = _strip_sections_metrics(report.as_dict())
        rebuilt = decision_report_from_dict(report.as_dict())
        round_tripped = _strip_sections_metrics(rebuilt.as_dict())
        if original != round_tripped:
            _add_violation(
                violations,
                AuditIntegrityViolationCode.ROUND_TRIP_MISMATCH,
                "report.as_dict",
                "",
                "round-trip as_dict -> from_dict -> as_dict does not "
                "preserve payload",
            )
    except Exception as exc:
        _add_violation(
            violations,
            AuditIntegrityViolationCode.ROUND_TRIP_MISMATCH,
            "report.as_dict",
            "",
            f"round-trip verification failed: {exc}",
        )


def _check_non_finite(
    report: ToleranceDecisionReport,
    violations: list[AuditIntegrityViolation],
) -> None:
    """Recursively detect non-finite values in the deterministic payload."""

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                _add_violation(
                    violations,
                    AuditIntegrityViolationCode.NON_FINITE_VALUE,
                    path,
                    str(value),
                    f"non-finite value at {path}",
                )
            return
        if isinstance(value, dict):
            for k, v in value.items():
                _walk(v, f"{path}.{k}")
            return
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                _walk(v, f"{path}[{i}]")
            return

    try:
        _walk(report.as_dict(), "report")
    except Exception as exc:
        _add_violation(
            violations,
            AuditIntegrityViolationCode.NON_FINITE_VALUE,
            "report",
            "",
            f"non-finite check failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_decision_report_integrity(
    report: ToleranceDecisionReport,
) -> AuditIntegrityResult:
    """Validate the internal consistency of a tolerance decision report.

    Parameters
    ----------
    report:
        The Stage 15M report envelope to validate.

    Returns
    -------
    AuditIntegrityResult
        A deterministic result with a status and an ordered tuple of
        violations.  A result with no violations has status VALID.

    Raises
    ------
    InvalidAuditIntegrityError
        If *report* is not a
        :class:`~origlyph.tolerance.report.ToleranceDecisionReport`.

    Notes
    -----
    This function does NOT recompute any authoritative engineering
    calculation.  It inspects the report envelope for structural
    contradictions, broken references, non-finite payload values, and
    deterministic-identity drift.

    An integrity VALID result means the decision package is structurally
    consistent; it does NOT mean the engineering decision is PASS.
    """
    if not isinstance(report, ToleranceDecisionReport):
        raise InvalidAuditIntegrityError(
            f"validate_decision_report_integrity requires a "
            f"ToleranceDecisionReport, got {type(report).__name__}"
        )

    violations: list[AuditIntegrityViolation] = []

    # Schema version must be supported before any other check.
    if report.schema_version != REPORT_SCHEMA_VERSION:
        _add_violation(
            violations,
            AuditIntegrityViolationCode.UNSUPPORTED_SCHEMA_VERSION,
            "report.schema_version",
            report.schema_version,
            f"unsupported schema version {report.schema_version!r}; "
            f"expected {REPORT_SCHEMA_VERSION!r}",
        )
        violations.sort(key=_violation_sort_key)
        return AuditIntegrityResult(
            status=AuditIntegrityStatus.INCOMPLETE,
            violations=tuple(violations),
        )

    _check_status_consistency(report, violations)
    _check_completeness_consistency(report, violations)
    _check_reason_linkage(report, violations)
    _check_evidence_uniqueness_and_sources(report, violations)
    _check_subject_references(report, violations)
    _check_decision_id(report, violations)
    _check_round_trip(report, violations)
    _check_non_finite(report, violations)

    violations.sort(key=_violation_sort_key)

    status = (
        AuditIntegrityStatus.INVALID
        if violations
        else AuditIntegrityStatus.VALID
    )
    return AuditIntegrityResult(
        status=status,
        violations=tuple(violations),
    )
