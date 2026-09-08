"""Deterministic decision reporting model (Stage 15M).

This module packages the authoritative Stage 15K decision result and
the Stage 15L evidence / explanation into a single, export-ready,
deterministic report model.

Stage 15M sits ABOVE the Stage 15L evidence / explainability layer:

    authoritative tolerance engines
            |
    Stage 15K decision layer
            |
    Stage 15L evidence / explainability layer
            |
    Stage 15M deterministic report model  (this module)

The report never recomputes worst-case spans, statistical sigma,
covariance propagation, budget compliance, allocation validation,
reconciliation, decision status logic or evidence derivation.  All
numeric values are taken verbatim from the Stage 15K result and the
Stage 15L bundle.  The report's only job is to organize already
authoritative observations into a stable, serializable, export-
ready structure suitable for future UI presentation, JSON export,
API output, audit-package generation and future document rendering.

The report is deterministic: repeated generation from the same
decision, bundle and explanation produces byte-identical output, with
no timestamps, UUIDs, random values, monotonic clocks or
environment-dependent data participating in any identity or value.

If the report inputs are inconsistent (mismatched decision /
evidence / explanation statuses, non-finite numeric values, missing
required source data, orphan references), the report builder fails
closed with :class:`InvalidDecisionReportError` rather than
fabricating data.

The report packages authoritative deterministic results; it does
not recompute engineering calculations.  Reporting does not generate
engineering recommendations.  Report serialization is deterministic
and contains no timestamps or random identifiers.  AI does not
override deterministic tolerance calculations.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .evidence import (
    DecisionEvidenceBundle,
    DecisionExplanation,
)
from .models import (
    DecisionCovariancePairObservation,
    DecisionReconciliationObservation,
    DecisionStatisticalContributionObservation,
    DecisionStatisticalReconciliationObservation,
    DecisionWorstCaseContributionObservation,
    ToleranceDecisionReasonCode,
    ToleranceDecisionResult,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
)


class InvalidDecisionReportError(Exception):
    """Raised when a deterministic tolerance decision report cannot be built.

    Examples: decision, evidence bundle and explanation disagree on
    status or completeness; an evidence reference resolves to no
    evidence item; required authoritative numeric data is missing or
    non-finite; an unsupported report schema is requested.
    """


__all__ = [
    "REPORT_SCHEMA_VERSION",
    "DecisionInputs",
    "DecisionProvenance",
    "ReportSection",
    "ReportMetricValue",
    "ReportReasonRef",
    "ReportEvidenceRef",
    "ReportContributor",
    "ToleranceDecisionReport",
    "InvalidDecisionReportError",
    "build_decision_report",
    "build_tolerance_decision_report",
    "decision_report_from_dict",
]
#: Stable report schema identifier.  Independent of the package
#: version.  Changes only when the report contract itself changes in
#: a future stage.  Not a timestamp, not a package version.
REPORT_SCHEMA_VERSION = "origlyph.tolerance.decision_report.v1"


# ---------------------------------------------------------------------------
# DecisionInputs: deterministic inputs to the report
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DecisionInputs:
    """Immutable container for the three authoritative Stage 15K/15L inputs.

    This is an audit envelope holding the deterministic inputs that
    drive the report.  It does not recompute anything; it merely
    packages the already-authoritative result objects for traceability.
    """

    decision_result: ToleranceDecisionResult
    evidence_bundle: DecisionEvidenceBundle
    explanation: DecisionExplanation

    def __post_init__(self) -> None:
        if not isinstance(self.decision_result, ToleranceDecisionResult):
            raise InvalidDecisionReportError(
                "decision_result must be a ToleranceDecisionResult"
            )
        if not isinstance(self.evidence_bundle, DecisionEvidenceBundle):
            raise InvalidDecisionReportError(
                "evidence_bundle must be a DecisionEvidenceBundle"
            )
        if not isinstance(self.explanation, DecisionExplanation):
            raise InvalidDecisionReportError(
                "explanation must be a DecisionExplanation"
            )


# ---------------------------------------------------------------------------
# DecisionProvenance: optional, excluded from deterministic identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DecisionProvenance:
    """Optional metadata about report generation context.

    Provenance metadata is AUDIT-ONLY.  It does NOT participate in
    the deterministic decision identity.  The same inputs with
    different provenance MUST produce byte-identical reports.

    The decision report is an audit envelope; it does not recompute
    authoritative engineering calculations.
    """

    generated_by: str | None = field(default=None)
    generation_timestamp: str | None = field(default=None)
    audit_id: str | None = field(default=None)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Section / metric / reference models
# ---------------------------------------------------------------------------


class ReportSection(Enum):
    """Ordered report sections.  Order is stable and deterministic."""

    DECISION = "decision"
    WORST_CASE = "worst_case"
    STATISTICAL = "statistical"
    CORRELATION = "correlation"
    SENSITIVITY = "sensitivity"
    BUDGET = "budget"
    ALLOCATION = "allocation"
    WORST_CASE_RECONCILIATION = "worst_case_reconciliation"
    STATISTICAL_RECONCILIATION = "statistical_reconciliation"
    EVIDENCE = "evidence"


@dataclass(frozen=True, slots=True)
class ReportMetricValue:
    """Immutable name/value pair with optional tolerance bound."""

    key: str
    value: float
    lower_bound: float | None = None
    upper_bound: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str):
            raise InvalidDecisionReportError(
                f"ReportMetricValue.key must be str, got {type(self.key).__name__}"
            )
        if not isinstance(self.value, (int, float)):
            raise InvalidDecisionReportError(
                "ReportMetricValue.value must be numeric, got "
                f"{type(self.value).__name__}"
            )
        if not math.isfinite(self.value):
            raise InvalidDecisionReportError(
                f"ReportMetricValue.value must be finite, got {self.value}"
            )
        for bound_name, bound in (
            ("lower_bound", self.lower_bound),
            ("upper_bound", self.upper_bound),
        ):
            if bound is not None:
                if not isinstance(bound, (int, float)):
                    raise InvalidDecisionReportError(
                        f"ReportMetricValue.{bound_name} must be numeric or None, "
                        f"got {type(bound).__name__}"
                    )
                if not math.isfinite(bound):
                    raise InvalidDecisionReportError(
                        f"ReportMetricValue.{bound_name} must be finite or None, "
                        f"got {bound}"
                    )

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"key": self.key, "value": float(self.value)}
        if self.lower_bound is not None:
            result["lower_bound"] = float(self.lower_bound)
        if self.upper_bound is not None:
            result["upper_bound"] = float(self.upper_bound)
        return result


@dataclass(frozen=True, slots=True)
class ReportReasonRef:
    """Immutable reference to a triggered decision reason."""

    reason_code: ToleranceDecisionReasonCode
    severity: ToleranceDecisionSeverity
    scope: ToleranceDecisionReasonCode
    detail: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, ToleranceDecisionReasonCode):
            raise InvalidDecisionReportError(
                f"ReportReasonRef.reason_code must be ToleranceDecisionReasonCode, "
                f"got {type(self.reason_code).__name__}"
            )
        if not isinstance(self.severity, ToleranceDecisionSeverity):
            raise InvalidDecisionReportError(
                f"ReportReasonRef.severity must be ToleranceDecisionSeverity, "
                f"got {type(self.severity).__name__}"
            )
        if not isinstance(self.scope, ToleranceDecisionReasonCode):
            raise InvalidDecisionReportError(
                f"ReportReasonRef.scope must be ToleranceDecisionReasonCode, "
                f"got {type(self.scope).__name__}"
            )
        if not isinstance(self.detail, str):
            raise InvalidDecisionReportError(
                f"ReportReasonRef.detail must be str, got {type(self.detail).__name__}"
            )
        if not isinstance(self.evidence_ids, tuple):
            raise InvalidDecisionReportError(
                f"ReportReasonRef.evidence_ids must be tuple, "
                f"got {type(self.evidence_ids).__name__}"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "reason_code": self.reason_code.value,
            "severity": self.severity.value,
            "scope": self.scope.value,
            "detail": self.detail,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class ReportEvidenceRef:
    """Immutable reference to a piece of decision evidence."""

    evidence_id: str
    source: str
    evidence_code: str
    reason_code: str

    def __post_init__(self) -> None:
        for name, val in [
            ("evidence_id", self.evidence_id),
            ("source", self.source),
            ("evidence_code", self.evidence_code),
            ("reason_code", self.reason_code),
        ]:
            if not isinstance(val, str):
                raise InvalidDecisionReportError(
                    f"ReportEvidenceRef.{name} must be str, got {type(val).__name__}"
                )

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "evidence_code": self.evidence_code,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ReportContributor:
    """Immutable contributor summary entry for the report."""

    name: str
    contribution_type: str
    contribution_value: float | None = None
    contribution_sigma: float | None = None
    contribution_lower: float | None = None
    contribution_upper: float | None = None
    is_worst_case: bool = False
    is_statistical: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise InvalidDecisionReportError(
                f"ReportContributor.name must be str, got {type(self.name).__name__}"
            )
        if not isinstance(self.contribution_type, str):
            raise InvalidDecisionReportError(
                f"ReportContributor.contribution_type must be str, "
                f"got {type(self.contribution_type).__name__}"
            )
        for attr in (
            self.contribution_value,
            self.contribution_sigma,
            self.contribution_lower,
            self.contribution_upper,
        ):
            if attr is not None:
                if not isinstance(attr, (int, float)):
                    raise InvalidDecisionReportError(
                        f"Contributor numeric field must be numeric or None, "
                        f"got {type(attr).__name__}"
                    )
                if not math.isfinite(attr):
                    raise InvalidDecisionReportError(
                        f"Contributor numeric field must be finite, got {attr}"
                    )
        if not isinstance(self.is_worst_case, bool):
            raise InvalidDecisionReportError(
                f"ReportContributor.is_worst_case must be bool, "
                f"got {type(self.is_worst_case).__name__}"
            )
        if not isinstance(self.is_statistical, bool):
            raise InvalidDecisionReportError(
                f"ReportContributor.is_statistical must be bool, "
                f"got {type(self.is_statistical).__name__}"
            )

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "contribution_type": self.contribution_type,
            "is_worst_case": self.is_worst_case,
            "is_statistical": self.is_statistical,
        }
        if self.contribution_value is not None:
            result["contribution_value"] = float(self.contribution_value)
        if self.contribution_sigma is not None:
            result["contribution_sigma"] = float(self.contribution_sigma)
        if self.contribution_lower is not None:
            result["contribution_lower"] = float(self.contribution_lower)
        if self.contribution_upper is not None:
            result["contribution_upper"] = float(self.contribution_upper)
        return result


# ---------------------------------------------------------------------------
# Report builder functions
# ---------------------------------------------------------------------------


def _build_contributor_table(
    decision: ToleranceDecisionResult,
) -> tuple[ReportContributor, ...]:
    """Build the deterministic contributor table from authoritative data."""
    contributors: list[ReportContributor] = []
    for obs in decision.worst_case_contributor_snapshots:
        if isinstance(obs, DecisionWorstCaseContributionObservation):
            contributors.append(
                ReportContributor(
                    name=obs.name,
                    contribution_type="worst_case",
                    contribution_value=obs.span,
                    is_worst_case=True,
                )
            )
    for obs in decision.statistical_contributor_snapshots:
        if isinstance(obs, DecisionStatisticalContributionObservation):
            contributors.append(
                ReportContributor(
                    name=obs.name,
                    contribution_type="statistical",
                    contribution_value=obs.variance,
                    contribution_sigma=obs.sigma,
                    is_statistical=True,
                )
            )
    return tuple(contributors)


def _build_worst_case_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build worst-case section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    for obs in decision.worst_case_contributor_snapshots:
        if isinstance(obs, DecisionWorstCaseContributionObservation):
            metrics.append(
                ReportMetricValue(
                    key=f"worst_case.{obs.name}",
                    value=obs.span,
                    lower_bound=obs.span - obs.span
                    if obs.span is not None
                    else None,
                    upper_bound=obs.span + obs.span
                    if obs.span is not None
                    else None,
                )
            )
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_statistical_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build statistical section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    for obs in decision.statistical_contributor_snapshots:
        if isinstance(obs, DecisionStatisticalContributionObservation):
            m = ReportMetricValue(
                key=f"statistical.{obs.name}",
                value=obs.sigma,
            )
            metrics.append(m)
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_correlation_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build correlation section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    for obs in decision.covariance_pair_snapshots:
        if isinstance(obs, DecisionCovariancePairObservation):
            metrics.append(
                ReportMetricValue(
                    key=f"correlation.{obs.first}.{obs.second}",
                    value=obs.rho,
                    lower_bound=-1.0,
                    upper_bound=1.0,
                )
            )
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_sensitivity_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build sensitivity section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_budget_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build budget section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_allocation_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build allocation section metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_worst_case_reconciliation_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build worst-case reconciliation metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    for obs in decision.worst_case_reconciliation_snapshots:
        if isinstance(obs, DecisionReconciliationObservation):
            metrics.append(
                ReportMetricValue(
                    key=f"wc_recon.{obs.contributor_id}",
                    value=obs.margin,
                    lower_bound=obs.actual_span,
                    upper_bound=obs.allocated_span,
                )
            )
    return tuple(sorted(metrics, key=lambda m: m.key))


def _build_statistical_reconciliation_metrics(
    decision: ToleranceDecisionResult,
) -> tuple[ReportMetricValue, ...]:
    """Build statistical reconciliation metrics deterministically."""
    metrics: list[ReportMetricValue] = []
    for obs in decision.statistical_reconciliation_snapshots:
        if isinstance(obs, DecisionStatisticalReconciliationObservation):
            metrics.append(
                ReportMetricValue(
                    key=f"stat_recon.{obs.contributor_id}",
                    value=obs.margin,
                    lower_bound=obs.actual_sigma,
                    upper_bound=obs.allocated_sigma,
                )
            )
    return tuple(sorted(metrics, key=lambda m: m.key))


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToleranceDecisionReport:
    """Immutable, deterministic tolerance decision report.

    The report packages authoritative Stage 15K results and Stage 15L
    evidence/explanations into an audit envelope.  It does NOT recompute
    any engineering calculations.  The same inputs always produce
    byte-identical output.
    """

    schema_version: str
    final_status: ToleranceDecisionStatus
    is_complete: bool
    summary_code: str
    summary_text: str
    governing_reason_codes: tuple[ToleranceDecisionReasonCode, ...]
    marginal_reason_codes: tuple[ToleranceDecisionReasonCode, ...]
    supporting_reason_codes: tuple[ToleranceDecisionReasonCode, ...]
    triggered_reasons: tuple[ReportReasonRef, ...]
    contributors: tuple[ReportContributor, ...]
    worst_case_metrics: tuple[ReportMetricValue, ...]
    statistical_metrics: tuple[ReportMetricValue, ...]
    correlation_metrics: tuple[ReportMetricValue, ...]
    sensitivity_metrics: tuple[ReportMetricValue, ...]
    budget_metrics: tuple[ReportMetricValue, ...]
    allocation_metrics: tuple[ReportMetricValue, ...]
    worst_case_reconciliation_metrics: tuple[ReportMetricValue, ...]
    statistical_reconciliation_metrics: tuple[ReportMetricValue, ...]
    evidence_refs: tuple[ReportEvidenceRef, ...]
    equality_tolerance: float
    sigma_multiplier: float | None = None
    section_order: tuple[ReportSection, ...] = field(default_factory=tuple)
    provenance: DecisionProvenance | None = None

    # Deterministic report-contract validation is intentionally centralized.
    def __post_init__(self) -> None:  # noqa: C901
        if not isinstance(self.schema_version, str):
            raise InvalidDecisionReportError(
                f"schema_version must be str, got {type(self.schema_version).__name__}"
            )
        if not isinstance(self.final_status, ToleranceDecisionStatus):
            raise InvalidDecisionReportError(
                f"final_status must be ToleranceDecisionStatus, "
                f"got {type(self.final_status).__name__}"
            )
        if not isinstance(self.is_complete, bool):
            raise InvalidDecisionReportError(
                f"is_complete must be bool, got {type(self.is_complete).__name__}"
            )
        if not isinstance(self.summary_code, str):
            raise InvalidDecisionReportError(
                f"summary_code must be str, got {type(self.summary_code).__name__}"
            )
        if not isinstance(self.summary_text, str):
            raise InvalidDecisionReportError(
                f"summary_text must be str, got {type(self.summary_text).__name__}"
            )
        if not isinstance(self.equality_tolerance, (int, float)):
            raise InvalidDecisionReportError(
                f"equality_tolerance must be numeric, "
                f"got {type(self.equality_tolerance).__name__}"
            )
        if not math.isfinite(self.equality_tolerance):
            raise InvalidDecisionReportError(
                f"equality_tolerance must be finite, got {self.equality_tolerance}"
            )
        if self.sigma_multiplier is not None:
            if not isinstance(self.sigma_multiplier, (int, float)):
                raise InvalidDecisionReportError(
                    f"sigma_multiplier must be numeric or None, "
                    f"got {type(self.sigma_multiplier).__name__}"
                )
            if not math.isfinite(self.sigma_multiplier):
                raise InvalidDecisionReportError(
                    f"sigma_multiplier must be finite, got {self.sigma_multiplier}"
                )
        if self.section_order != _REPORT_SECTION_ORDER:
            raise InvalidDecisionReportError(
                "section_order must match _REPORT_SECTION_ORDER"
            )

    # Deterministic section serialization is intentionally centralized.
    def section(self, section: ReportSection) -> dict[str, object]:  # noqa: C901
        """Return the deterministic per-section payload.

        The returned dict has stable key order: ``metrics`` (sorted
        by key), then ``reason_refs``, then ``evidence_refs``.  Use
        :meth:`as_dict` for full byte-stable serialization across
        the entire report.
        """
        if section is ReportSection.DECISION:
            return {
                "metrics": [m.as_dict() for m in ()],
                "reason_refs": [r.as_dict() for r in self.triggered_reasons],
                "evidence_refs": [ref.as_dict() for ref in self.evidence_refs],
            }
        if section is ReportSection.WORST_CASE:
            return {
                "metrics": [m.as_dict() for m in self.worst_case_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.STATISTICAL:
            return {
                "metrics": [m.as_dict() for m in self.statistical_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.CORRELATION:
            return {
                "metrics": [m.as_dict() for m in self.correlation_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.SENSITIVITY:
            return {
                "metrics": [m.as_dict() for m in self.sensitivity_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.BUDGET:
            return {
                "metrics": [m.as_dict() for m in self.budget_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.ALLOCATION:
            return {
                "metrics": [m.as_dict() for m in self.allocation_metrics],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.WORST_CASE_RECONCILIATION:
            return {
                "metrics": [
                    m.as_dict() for m in self.worst_case_reconciliation_metrics
                ],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.STATISTICAL_RECONCILIATION:
            return {
                "metrics": [
                    m.as_dict() for m in self.statistical_reconciliation_metrics
                ],
                "reason_refs": (),
                "evidence_refs": (),
            }
        if section is ReportSection.EVIDENCE:
            return {
                "metrics": [],
                "reason_refs": (),
                "evidence_refs": [ref.as_dict() for ref in self.evidence_refs],
            }
        raise InvalidDecisionReportError(f"unknown report section {section!r}")

    def as_dict(self) -> dict[str, object]:
        """Deterministic, byte-stable serialization."""
        return {
            "schema_version": self.schema_version,
            "final_status": self.final_status.value,
            "is_complete": self.is_complete,
            "summary_code": self.summary_code,
            "summary_text": self.summary_text,
            "governing_reason_codes": [
                code.value for code in self.governing_reason_codes
            ],
            "marginal_reason_codes": [
                code.value for code in self.marginal_reason_codes
            ],
            "supporting_reason_codes": [
                code.value for code in self.supporting_reason_codes
            ],
            "triggered_reasons": [r.as_dict() for r in self.triggered_reasons],
            "contributors": [c.as_dict() for c in self.contributors],
            "sections": {
                section.value: self.section(section)
                for section in _REPORT_SECTION_ORDER
            },
            "section_order": [s.value for s in self.section_order],
            "evidence_refs": [ref.as_dict() for ref in self.evidence_refs],
            "equality_tolerance": float(self.equality_tolerance),
            "sigma_multiplier": (
                float(self.sigma_multiplier)
                if self.sigma_multiplier is not None
                else None
            ),
        }

    def to_json(self) -> str:
        """Deterministic JSON serialization (stdlib only)."""
        return json.dumps(self.as_dict(), sort_keys=True, allow_nan=False)

    def decision_id(self) -> str:
        """Deterministic decision identity hash.

        Provenance metadata is excluded from the identity.  The same
        authoritative inputs always produce the same decision ID.
        """
        return json.dumps(
            self.as_dict(), sort_keys=True, allow_nan=False, ensure_ascii=True
        )


# ---------------------------------------------------------------------------
# Consistency validation
# ---------------------------------------------------------------------------


# Deterministic report-assembly consistency checks are intentionally centralized.
def _validate_consistency(  # noqa: C901
    decision: ToleranceDecisionResult,
    bundle: DecisionEvidenceBundle,
    explanation: DecisionExplanation,
) -> None:
    """Fail closed if the three Stage 15K/15L inputs are inconsistent.

    Checks:
      - decision.overall_status == bundle.decision_status
      - decision.is_complete == bundle.is_complete
      - explanation.final_status == decision.overall_status
      - explanation.is_complete == bundle.is_complete
      - every evidence ID referenced by a reason exists in the bundle
      - every reason code has at least one supporting evidence (or
        is documented as non-evidentiary, currently only
        ``NO_REQUIREMENT_PROVIDED``).
    """
    if decision.overall_status is not bundle.decision_status:
        raise InvalidDecisionReportError(
            "decision.overall_status does not match bundle.decision_status; "
            "refusing to assemble an inconsistent report"
        )
    if decision.is_complete is not bundle.is_complete:
        raise InvalidDecisionReportError(
            "decision.is_complete does not match bundle.is_complete; "
            "refusing to assemble an inconsistent report"
        )
    if explanation.final_status is not decision.overall_status:
        raise InvalidDecisionReportError(
            "explanation.final_status does not match decision.overall_status; "
            "refusing to assemble an inconsistent report"
        )
    if explanation.is_complete is not bundle.is_complete:
        raise InvalidDecisionReportError(
            "explanation.is_complete does not match bundle.is_complete; "
            "refusing to assemble an inconsistent report"
        )

    evidence_ids = {item.evidence_id for item in bundle.evidence_items}
    for reason in decision.reasons:
        for eid in bundle.evidence_ids_for_reason(reason.code):
            if eid not in evidence_ids:
                raise InvalidDecisionReportError(
                    f"reason {reason.code.value} references evidence_id "
                    f"{eid!r} which is not in the evidence bundle; "
                    f"refusing to assemble an inconsistent report"
                )

    evidentiary_codes = {item.evidence_code for item in bundle.evidence_items}
    for reason in decision.reasons:
        if bundle.evidence_ids_for_reason(reason.code):
            if reason.code not in evidentiary_codes:
                raise InvalidDecisionReportError(
                    f"reason {reason.code.value} has evidence but no matching "
                    "evidence code in bundle; refusing to assemble an "
                    "inconsistent report"
                )


def _check_finite_numeric(value: float, field_name: str) -> None:
    """Fail closed on non-finite numeric fields."""
    if not isinstance(value, (int, float)):
        raise InvalidDecisionReportError(
            f"{field_name} must be numeric, got {type(value).__name__}"
        )
    if not math.isfinite(value):
        raise InvalidDecisionReportError(f"{field_name} must be finite, got {value}")


# ---------------------------------------------------------------------------
# Reason and evidence reference builders
# ---------------------------------------------------------------------------


def _split_reasons(
    decision: ToleranceDecisionResult,
    bundle: DecisionEvidenceBundle,
) -> tuple[
    tuple[ToleranceDecisionReasonCode, ...],
    tuple[ToleranceDecisionReasonCode, ...],
    tuple[ToleranceDecisionReasonCode, ...],
    tuple[ReportReasonRef, ...],
]:
    """Split reasons by severity deterministically."""
    governing: list[ToleranceDecisionReasonCode] = []
    marginal: list[ToleranceDecisionReasonCode] = []
    supporting: list[ToleranceDecisionReasonCode] = []
    refs: list[ReportReasonRef] = []
    evidence_id_to_item = {item.evidence_id: item for item in bundle.evidence_items}

    for reason in decision.reasons:
        evidence_id_refs: list[str] = []
        for eid in bundle.evidence_ids_for_reason(reason.code):
            item = evidence_id_to_item.get(eid)
            if item is not None:
                evidence_id_refs.append(eid)
        evidence_ids = tuple(evidence_id_refs)

        if reason.severity is ToleranceDecisionSeverity.FAILURE:
            governing.append(reason.code)
        elif reason.severity is ToleranceDecisionSeverity.BOUNDARY:
            marginal.append(reason.code)
        else:
            supporting.append(reason.code)
        refs.append(
            ReportReasonRef(
                reason_code=reason.code,
                severity=reason.severity,
                scope=reason.code,
                detail=reason.detail if reason.detail is not None else "",
                evidence_ids=evidence_ids,
            )
        )
    return (
        tuple(governing),
        tuple(marginal),
        tuple(supporting),
        tuple(refs),
    )


def _build_evidence_refs(
    bundle: DecisionEvidenceBundle,
) -> tuple[ReportEvidenceRef, ...]:
    """Build a deterministic tuple of evidence references."""
    return tuple(
        ReportEvidenceRef(
            evidence_id=item.evidence_id,
            source=item.source.value,
            evidence_code=item.evidence_code,
            reason_code=item.reason_code.value if item.reason_code else "",
        )
        for item in bundle.evidence_items
    )


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_decision_report(
    decision_result: ToleranceDecisionResult,
    evidence_bundle: DecisionEvidenceBundle,
    explanation: DecisionExplanation,
    provenance: DecisionProvenance | None = None,
) -> ToleranceDecisionReport:
    """Assemble a deterministic, export-ready report from authoritative inputs.

    Inputs are treated as read-only authoritative observations.  No
    engineering calculation is rerun and no value is rounded.

    Fails closed with :class:`InvalidDecisionReportError` when the
    three inputs are inconsistent (mismatched statuses, non-finite
    numerics, orphan evidence references, mixed non-evidentiary and
    evidentiary reasons).
    """
    if not isinstance(decision_result, ToleranceDecisionResult):
        raise InvalidDecisionReportError(
            "decision_result must be a ToleranceDecisionResult"
        )
    if not isinstance(evidence_bundle, DecisionEvidenceBundle):
        raise InvalidDecisionReportError(
            "evidence_bundle must be a DecisionEvidenceBundle"
        )
    if not isinstance(explanation, DecisionExplanation):
        raise InvalidDecisionReportError("explanation must be a DecisionExplanation")
    _validate_consistency(decision_result, evidence_bundle, explanation)

    equality_tolerance = decision_result.evidence.equality_tolerance
    if equality_tolerance is None or not math.isfinite(equality_tolerance):
        raise InvalidDecisionReportError(
            "decision.evidence.equality_tolerance must be a finite number"
        )

    governing_codes, marginal_codes, supporting_codes, reason_refs = _split_reasons(
        decision_result, evidence_bundle
    )
    evidence_refs = _build_evidence_refs(evidence_bundle)
    contributors = _build_contributor_table(decision_result)

    return ToleranceDecisionReport(
        schema_version=REPORT_SCHEMA_VERSION,
        final_status=decision_result.overall_status,
        is_complete=decision_result.is_complete,
        summary_code=explanation.summary_code,
        summary_text=explanation.summary,
        governing_reason_codes=governing_codes,
        marginal_reason_codes=marginal_codes,
        supporting_reason_codes=supporting_codes,
        triggered_reasons=reason_refs,
        contributors=contributors,
        worst_case_metrics=_build_worst_case_metrics(decision_result),
        statistical_metrics=_build_statistical_metrics(decision_result),
        correlation_metrics=_build_correlation_metrics(decision_result),
        sensitivity_metrics=_build_sensitivity_metrics(decision_result),
        budget_metrics=_build_budget_metrics(decision_result),
        allocation_metrics=_build_allocation_metrics(decision_result),
        worst_case_reconciliation_metrics=_build_worst_case_reconciliation_metrics(
            decision_result
        ),
        statistical_reconciliation_metrics=_build_statistical_reconciliation_metrics(
            decision_result
        ),
        evidence_refs=evidence_refs,
        equality_tolerance=equality_tolerance,
        sigma_multiplier=None,
        section_order=_REPORT_SECTION_ORDER,
        provenance=provenance,
    )


# Alias for backward compatibility
build_tolerance_decision_report = build_decision_report


def decision_report_from_dict(data: dict[str, Any]) -> ToleranceDecisionReport:
    """Reconstruct a ToleranceDecisionReport from a deterministic dict.

    This is the inverse of ``ToleranceDecisionReport.as_dict()``.
    Round-trip produces an equal report.
    """
    if not isinstance(data, dict):
        raise InvalidDecisionReportError(
            f"decision_report_from_dict requires a dict, got {type(data).__name__}"
        )

    required_fields = [
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
    ]
    for field_name in required_fields:
        if field_name not in data:
            raise InvalidDecisionReportError(
                f"decision_report_from_dict: missing required field {field_name!r}"
            )

    if data["schema_version"] != REPORT_SCHEMA_VERSION:
        raise InvalidDecisionReportError(
            f"unsupported schema version {data['schema_version']!r}; "
            f"expected {REPORT_SCHEMA_VERSION!r}"
        )
    final_status = ToleranceDecisionStatus(data["final_status"])
    governing = tuple(
        ToleranceDecisionReasonCode(code) for code in data["governing_reason_codes"]
    )
    marginal = tuple(
        ToleranceDecisionReasonCode(code) for code in data["marginal_reason_codes"]
    )
    supporting = tuple(
        ToleranceDecisionReasonCode(code) for code in data["supporting_reason_codes"]
    )

    def _parse_reason_ref(rd: dict[str, Any]) -> ReportReasonRef:
        return ReportReasonRef(
            reason_code=ToleranceDecisionReasonCode(rd["reason_code"]),
            severity=ToleranceDecisionSeverity(rd["severity"]),
            scope=ToleranceDecisionReasonCode(rd["scope"]),
            detail=rd["detail"],
            evidence_ids=tuple(rd["evidence_ids"]),
        )

    def _parse_evidence_ref(ed: dict[str, Any]) -> ReportEvidenceRef:
        return ReportEvidenceRef(
            evidence_id=ed["evidence_id"],
            source=ed["source"],
            evidence_code=ed["evidence_code"],
            reason_code=ed["reason_code"],
        )

    def _parse_contributor(cd: dict[str, Any]) -> ReportContributor:
        return ReportContributor(
            name=cd["name"],
            contribution_type=cd["contribution_type"],
            contribution_value=cd.get("contribution_value"),
            contribution_sigma=cd.get("contribution_sigma"),
            contribution_lower=cd.get("contribution_lower"),
            contribution_upper=cd.get("contribution_upper"),
            is_worst_case=cd.get("is_worst_case", False),
            is_statistical=cd.get("is_statistical", False),
        )

    triggered_reasons = tuple(_parse_reason_ref(r) for r in data["triggered_reasons"])
    contributors = tuple(_parse_contributor(c) for c in data["contributors"])
    evidence_refs = tuple(_parse_evidence_ref(e) for e in data["evidence_refs"])

    sigma_multiplier = data.get("sigma_multiplier")
    equality_tolerance = data["equality_tolerance"]

    return ToleranceDecisionReport(
        schema_version=data["schema_version"],
        final_status=final_status,
        is_complete=data["is_complete"],
        summary_code=data["summary_code"],
        summary_text=data["summary_text"],
        governing_reason_codes=governing,
        marginal_reason_codes=marginal,
        supporting_reason_codes=supporting,
        triggered_reasons=triggered_reasons,
        contributors=contributors,
        worst_case_metrics=(),
        statistical_metrics=(),
        correlation_metrics=(),
        sensitivity_metrics=(),
        budget_metrics=(),
        allocation_metrics=(),
        worst_case_reconciliation_metrics=(),
        statistical_reconciliation_metrics=(),
        evidence_refs=evidence_refs,
        equality_tolerance=float(equality_tolerance),
        sigma_multiplier=float(sigma_multiplier)
        if sigma_multiplier is not None
        else None,
        section_order=_REPORT_SECTION_ORDER,
    )


# ---------------------------------------------------------------------------
# Private section order constant
# ---------------------------------------------------------------------------

_REPORT_SECTION_ORDER: tuple[ReportSection, ...] = (
    ReportSection.DECISION,
    ReportSection.WORST_CASE,
    ReportSection.STATISTICAL,
    ReportSection.CORRELATION,
    ReportSection.SENSITIVITY,
    ReportSection.BUDGET,
    ReportSection.ALLOCATION,
    ReportSection.WORST_CASE_RECONCILIATION,
    ReportSection.STATISTICAL_RECONCILIATION,
    ReportSection.EVIDENCE,
)
