"""Deterministic decision evidence and explainability layer (Stage 15L).

This module answers one question: *why* did the Stage 15K decision layer
produce a given deterministic tolerance decision?  It builds a typed,
ordered, deterministic and serializable evidence bundle from an
already-authoritative
:class:`~origlyph.tolerance.models.ToleranceDecisionResult` without
rerunning any engineering calculation.

Stage 15L sits ABOVE the Stage 15K decision layer:

    authoritative tolerance engines
            |
    Stage 15K decision layer
            |
    Stage 15L evidence / explainability layer   (this module)

Evidence explains results; it does not replace them.  This module never
recomputes worst-case spans, statistical sigma, covariance propagation,
budget compliance, allocation validation or reconciliation, and it never
re-derives decision status logic.  All numeric values are passed through
from the Stage 15K result without rounding.

The layer is deterministic: repeated evaluation of an identical decision
result produces identical evidence identifiers, identical ordering and
identical serialization.  No timestamps, UUIDs, random values or object
addresses participate in any identity.

If authoritative source information required to support a triggered
reason is missing, building evidence fails closed with
:class:`~origlyph.tolerance.exceptions.InvalidDecisionEvidenceError`
rather than fabricating evidence.

AI does not override deterministic tolerance calculations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .exceptions import InvalidDecisionEvidenceError
from .models import (
    ToleranceDecisionDimension,
    ToleranceDecisionEvaluationState,
    ToleranceDecisionReason,
    ToleranceDecisionReasonCode,
    ToleranceDecisionResult,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
)

__all__ = [
    "DecisionComparison",
    "DecisionEvidenceBundle",
    "DecisionEvidenceCode",
    "DecisionEvidenceItem",
    "DecisionEvidenceSource",
    "DecisionExplanation",
    "DecisionMetric",
    "ReasonEvidenceLink",
    "build_decision_evidence",
    "explain_tolerance_decision",
]


# ---------------------------------------------------------------------------
# Stable typed source / comparison models
# ---------------------------------------------------------------------------


class DecisionEvidenceSource(Enum):
    """Stable, serialization-safe source of a decision-evidence item.

    The string values are the authoritative identity; they are stable
    across releases and independent of Python class names.
    """

    WORST_CASE = "worst_case"
    STATISTICAL = "statistical"
    CORRELATED_STATISTICAL = "correlated_statistical"
    SENSITIVITY = "sensitivity"
    BUDGET = "budget"
    ALLOCATION = "allocation"
    WORST_CASE_RECONCILIATION = "worst_case_reconciliation"
    STATISTICAL_RECONCILIATION = "statistical_reconciliation"
    DECISION = "decision"
    STRUCTURAL = "structural"


class DecisionComparison(Enum):
    """Deterministic comparison state of observed vs reference value."""

    LESS_THAN = "less_than"
    AT_BOUNDARY = "at_boundary"
    GREATER_THAN = "greater_than"
    NOT_APPLICABLE = "not_applicable"


class DecisionEvidenceCode(Enum):
    """Stable technical evidence codes.

    Each member identifies one technical observation.  The string values
    are the serialization identity.  Codes never encode prose, format
    names, vendor names or free-form identifiers.
    """

    WC_SPAN_WITHIN_LIMIT = "wc_span_within_limit"
    WC_SPAN_AT_LIMIT = "wc_span_at_limit"
    WC_SPAN_EXCEEDS_LIMIT = "wc_span_exceeds_limit"
    WC_STACK_NOT_PROVIDED = "wc_stack_not_provided"
    STAT_SIGMA_WITHIN_LIMIT = "stat_sigma_within_limit"
    STAT_SIGMA_AT_LIMIT = "stat_sigma_at_limit"
    STAT_SIGMA_EXCEEDS_LIMIT = "stat_sigma_exceeds_limit"
    STAT_STACK_NOT_PROVIDED = "stat_stack_not_provided"
    WC_ALLOCATION_WITHIN_PLAN = "wc_allocation_within_plan"
    WC_ALLOCATION_AT_PLAN_LIMIT = "wc_allocation_at_plan_limit"
    WC_ALLOCATION_EXCEEDS_PLAN = "wc_allocation_exceeds_plan"
    STAT_ALLOCATION_WITHIN_PLAN = "stat_allocation_within_plan"
    STAT_ALLOCATION_AT_PLAN_LIMIT = "stat_allocation_at_plan_limit"
    STAT_ALLOCATION_EXCEEDS_PLAN = "stat_allocation_exceeds_plan"
    ALLOCATION_MISSING_CONTRIBUTORS = "allocation_missing_contributors"
    WC_RECONCILIATION_CONTRIBUTOR_WITHIN = "wc_reconciliation_contributor_within"
    WC_RECONCILIATION_CONTRIBUTOR_AT = "wc_reconciliation_contributor_at"
    WC_RECONCILIATION_CONTRIBUTOR_EXCEEDED = "wc_reconciliation_contributor_exceeded"
    STAT_RECONCILIATION_CONTRIBUTOR_WITHIN = "stat_reconciliation_contributor_within"
    STAT_RECONCILIATION_CONTRIBUTOR_AT = "stat_reconciliation_contributor_at"
    STAT_RECONCILIATION_CONTRIBUTOR_EXCEEDED = (
        "stat_reconciliation_contributor_exceeded"
    )
    COVARIANCE_PAIR_CONTRIBUTION = "covariance_pair_contribution"
    COVARIANCE_INCREASES_VARIANCE = "covariance_increases_variance"
    COVARIANCE_REDUCES_VARIANCE = "covariance_reduces_variance"
    COVARIANCE_EFFECTIVELY_NEUTRAL = "covariance_effectively_neutral"
    SENSITIVITY_WC_CONTRIBUTOR = "sensitivity_wc_contributor"
    SENSITIVITY_STAT_CONTRIBUTOR = "sensitivity_stat_contributor"
    WC_STAT_DISAGREEMENT = "wc_stat_disagreement"
    NO_CRITERIA_REQUESTED = "no_criteria_requested"


#: Deterministic evidence-source priority used for stable ordering
#: (lower sorts first).  Fixed, documented, never derived from data.
_SOURCE_ORDER: tuple[DecisionEvidenceSource, ...] = (
    DecisionEvidenceSource.WORST_CASE,
    DecisionEvidenceSource.STATISTICAL,
    DecisionEvidenceSource.CORRELATED_STATISTICAL,
    DecisionEvidenceSource.SENSITIVITY,
    DecisionEvidenceSource.BUDGET,
    DecisionEvidenceSource.ALLOCATION,
    DecisionEvidenceSource.WORST_CASE_RECONCILIATION,
    DecisionEvidenceSource.STATISTICAL_RECONCILIATION,
    DecisionEvidenceSource.DECISION,
    DecisionEvidenceSource.STRUCTURAL,
)

#: Deterministic evidence-severity priority used for stable ordering
#: (lower sorts first): hard failures, then boundary, then informational.
_SEVERITY_ORDER: tuple[ToleranceDecisionSeverity, ...] = (
    ToleranceDecisionSeverity.FAILURE,
    ToleranceDecisionSeverity.BOUNDARY,
    ToleranceDecisionSeverity.INFO,
)


# ---------------------------------------------------------------------------
# Metric / evidence-item models
# ---------------------------------------------------------------------------


def _check_finite_numeric(value: object, label: str) -> float:
    """Validate that ``value`` is a finite, non-bool number.

    Raises ``ValueError`` for bools, non-numerics, NaN and infinities.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be finite, got {value!r}")
    return numeric


@dataclass(frozen=True)
class DecisionMetric:
    """One named, finite numeric traceability value attached to evidence.

    Keys are stable snake_case identifiers; values are passed through
    from authoritative results without rounding.  NaN, infinities and
    booleans are rejected.
    """

    key: str
    value: float

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("metric key must be a non-empty string")
        _check_finite_numeric(self.value, f"metric {self.key!r} value")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization."""
        return {"key": self.key, "value": float(self.value)}


@dataclass(frozen=True)
class DecisionEvidenceItem:
    """One immutable, deterministic piece of decision evidence.

    ``observed_value`` and ``reference_value`` are ``None`` for
    structural evidence (for example a missing allocation contributor)
    and carry exact authoritative values for numeric evidence.  Numeric
    values are never rounded by this layer; presentation rounding
    belongs to future report layers.
    """

    evidence_id: str
    evidence_code: str
    source: DecisionEvidenceSource
    scope: str | None
    subject_id: str | None
    reason_code: ToleranceDecisionReasonCode | None
    observed_value: float | None
    reference_value: float | None
    comparison: DecisionComparison
    severity: ToleranceDecisionSeverity
    detail: str
    metrics: tuple[DecisionMetric, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id:
            raise ValueError("evidence_id must be a non-empty string")
        if not isinstance(self.evidence_code, str) or not self.evidence_code:
            raise ValueError("evidence_code must be a non-empty string")
        if self.observed_value is not None:
            _check_finite_numeric(self.observed_value, "observed_value")
        if self.reference_value is not None:
            _check_finite_numeric(self.reference_value, "reference_value")
        keys = tuple(m.key for m in self.metrics)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate metric key in evidence item")
        if keys != tuple(sorted(keys)):
            raise ValueError("metrics must be sorted by key")

    def metric(self, key: str) -> float | None:
        """Return the metric value for ``key``, or ``None`` if absent."""
        for item_metric in self.metrics:
            if item_metric.key == key:
                return item_metric.value
        return None

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization (enums as stable strings)."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_code": self.evidence_code,
            "source": self.source.value,
            "scope": self.scope,
            "subject_id": self.subject_id,
            "reason_code": (
                self.reason_code.value if self.reason_code is not None else None
            ),
            "observed_value": self.observed_value,
            "reference_value": self.reference_value,
            "comparison": self.comparison.value,
            "severity": self.severity.value,
            "detail": self.detail,
            "metrics": [item_metric.as_dict() for item_metric in self.metrics],
        }


# ---------------------------------------------------------------------------
# Evidence bundle model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasonEvidenceLink:
    """Deterministic linkage from one triggered reason to its evidence."""

    reason_code: ToleranceDecisionReasonCode
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class DecisionEvidenceBundle:
    """Typed, ordered, immutable decision-evidence container.

    ``evidence_items`` is deterministically ordered (severity priority,
    then evidence-source priority, scope, subject, code, then stable
    build index).  The bundle never mutates the decision result it
    explains and never fabricates evidence.
    """

    decision_status: ToleranceDecisionStatus
    is_complete: bool
    evidence_items: tuple[DecisionEvidenceItem, ...]
    reason_to_evidence: tuple[ReasonEvidenceLink, ...]
    governing_evidence_ids: tuple[str, ...]
    marginal_evidence_ids: tuple[str, ...]

    def evidence_ids_for_reason(
        self, reason_code: ToleranceDecisionReasonCode
    ) -> tuple[str, ...]:
        """Return deterministic evidence IDs linked to ``reason_code``."""
        for link in self.reason_to_evidence:
            if link.reason_code is reason_code:
                return link.evidence_ids
        return ()

    @property
    def governing_evidence(self) -> tuple[DecisionEvidenceItem, ...]:
        """All hard-failure / incomplete-structural evidence items."""
        by_id = {item.evidence_id: item for item in self.evidence_items}
        return tuple(
            by_id[evidence_id]
            for evidence_id in self.governing_evidence_ids
            if evidence_id in by_id
        )

    @property
    def marginal_evidence(self) -> tuple[DecisionEvidenceItem, ...]:
        """All boundary (marginal) evidence items."""
        by_id = {item.evidence_id: item for item in self.evidence_items}
        return tuple(
            by_id[evidence_id]
            for evidence_id in self.marginal_evidence_ids
            if evidence_id in by_id
        )

    @property
    def supporting_evidence(self) -> tuple[DecisionEvidenceItem, ...]:
        """All informational (supporting) evidence items."""
        governing = set(self.governing_evidence_ids)
        marginal = set(self.marginal_evidence_ids)
        return tuple(
            item
            for item in self.evidence_items
            if item.evidence_id not in governing
            and item.evidence_id not in marginal
        )

    @property
    def primary_governing_evidence(self) -> DecisionEvidenceItem | None:
        """First governing evidence item in deterministic order."""
        governing = self.governing_evidence
        return governing[0] if governing else None

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization."""
        return {
            "decision_status": self.decision_status.value,
            "is_complete": self.is_complete,
            "evidence_items": [item.as_dict() for item in self.evidence_items],
            "reason_to_evidence": [
                {
                    "reason_code": link.reason_code.value,
                    "evidence_ids": list(link.evidence_ids),
                }
                for link in self.reason_to_evidence
            ],
            "governing_evidence_ids": list(self.governing_evidence_ids),
            "marginal_evidence_ids": list(self.marginal_evidence_ids),
        }


# ---------------------------------------------------------------------------
# Structured explanation model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionExplanation:
    """Deterministic structured explanation of a tolerance decision.

    ``summary`` (when present) is rendered from fixed templates only.
    There is no LLM, no generative wording, no stochastic text and no
    hidden reasoning anywhere in this layer.
    """

    final_status: ToleranceDecisionStatus
    summary_code: str
    governing_reasons: tuple[ToleranceDecisionReasonCode, ...]
    governing_evidence: tuple[DecisionEvidenceItem, ...]
    marginal_evidence: tuple[DecisionEvidenceItem, ...]
    supporting_evidence: tuple[DecisionEvidenceItem, ...]
    is_complete: bool
    summary: str

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization."""
        return {
            "final_status": self.final_status.value,
            "summary_code": self.summary_code,
            "governing_reasons": [code.value for code in self.governing_reasons],
            "governing_evidence": [
                item.as_dict() for item in self.governing_evidence
            ],
            "marginal_evidence": [item.as_dict() for item in self.marginal_evidence],
            "supporting_evidence": [
                item.as_dict() for item in self.supporting_evidence
            ],
            "is_complete": self.is_complete,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Deterministic builder helpers and stable mapping tables
# ---------------------------------------------------------------------------

_MARGIN_METRIC_KEY = "remaining_margin"
_UTILIZATION_METRIC_KEY = "utilization"
_RANK_METRIC_KEY = "rank"
_FRACTION_METRIC_KEY = "fraction"
_PERCENTAGE_METRIC_KEY = "percentage"
_INDEPENDENT_SIGMA_METRIC_KEY = "independent_combined_sigma"
_EQUALITY_TOLERANCE_METRIC_KEY = "equality_tolerance"
_RHO_METRIC_KEY = "rho"

_C = DecisionEvidenceCode
_E = ToleranceDecisionEvaluationState
_R = ToleranceDecisionReasonCode


def _format_number(value: float | None) -> str:
    """Format a number deterministically (Stage 15K ``.12g`` style)."""
    if value is None:
        return "none"
    return format(float(value), ".12g")


def _make_evidence_id(
    source: DecisionEvidenceSource,
    evidence_code: str,
    scope: str | None,
    subject_id: str | None,
    index: int,
) -> str:
    """Deterministic evidence ID: ``source:code:scope:subject:index``.

    ``index`` is the stable build-order index.  No timestamps, random
    values or object addresses participate in the identity.
    """
    scope_part = scope if scope is not None else "-"
    subject_part = subject_id if subject_id is not None else "-"
    return f"{source.value}:{evidence_code}:{scope_part}:{subject_part}:{index:03d}"


def _comparison_for_values(
    observed: float, reference: float, equality_tolerance: float
) -> DecisionComparison:
    """Classify observed vs reference using the authoritative equality policy."""
    difference = observed - reference
    if abs(difference) <= equality_tolerance:
        return DecisionComparison.AT_BOUNDARY
    if difference < 0.0:
        return DecisionComparison.LESS_THAN
    return DecisionComparison.GREATER_THAN


_STATE_SEVERITIES: dict[ToleranceDecisionEvaluationState, ToleranceDecisionSeverity] = {
    _E.FAIL: ToleranceDecisionSeverity.FAILURE,
    _E.AT_BOUNDARY: ToleranceDecisionSeverity.BOUNDARY,
    _E.PASS: ToleranceDecisionSeverity.INFO,
    _E.INCOMPLETE: ToleranceDecisionSeverity.FAILURE,
}

_STATE_COMPARISONS: dict[ToleranceDecisionEvaluationState, DecisionComparison] = {
    _E.FAIL: DecisionComparison.GREATER_THAN,
    _E.AT_BOUNDARY: DecisionComparison.AT_BOUNDARY,
    _E.PASS: DecisionComparison.LESS_THAN,
}

_DIMENSION_SOURCES: dict[str, DecisionEvidenceSource] = {
    "worst_case_requirement": DecisionEvidenceSource.BUDGET,
    "statistical_requirement": DecisionEvidenceSource.BUDGET,
    "worst_case_allocation": DecisionEvidenceSource.ALLOCATION,
    "statistical_allocation": DecisionEvidenceSource.ALLOCATION,
}

_STRUCTURAL_DIMENSION_CODES: dict[str, DecisionEvidenceCode] = {
    "worst_case_requirement": _C.WC_STACK_NOT_PROVIDED,
    "statistical_requirement": _C.STAT_STACK_NOT_PROVIDED,
    "worst_case_allocation": _C.WC_STACK_NOT_PROVIDED,
    "statistical_allocation": _C.STAT_STACK_NOT_PROVIDED,
}

_NUMERIC_DIMENSION_CODES: dict[
    tuple[str, ToleranceDecisionEvaluationState], DecisionEvidenceCode
] = {
    ("worst_case_requirement", _E.FAIL): _C.WC_SPAN_EXCEEDS_LIMIT,
    ("worst_case_requirement", _E.AT_BOUNDARY): _C.WC_SPAN_AT_LIMIT,
    ("worst_case_requirement", _E.PASS): _C.WC_SPAN_WITHIN_LIMIT,
    ("statistical_requirement", _E.FAIL): _C.STAT_SIGMA_EXCEEDS_LIMIT,
    ("statistical_requirement", _E.AT_BOUNDARY): _C.STAT_SIGMA_AT_LIMIT,
    ("statistical_requirement", _E.PASS): _C.STAT_SIGMA_WITHIN_LIMIT,
    ("worst_case_allocation", _E.FAIL): _C.WC_ALLOCATION_EXCEEDS_PLAN,
    ("worst_case_allocation", _E.AT_BOUNDARY): _C.WC_ALLOCATION_AT_PLAN_LIMIT,
    ("worst_case_allocation", _E.PASS): _C.WC_ALLOCATION_WITHIN_PLAN,
    ("statistical_allocation", _E.FAIL): _C.STAT_ALLOCATION_EXCEEDS_PLAN,
    ("statistical_allocation", _E.AT_BOUNDARY): _C.STAT_ALLOCATION_AT_PLAN_LIMIT,
    ("statistical_allocation", _E.PASS): _C.STAT_ALLOCATION_WITHIN_PLAN,
}

_DIMENSION_REASONS: dict[
    tuple[str, ToleranceDecisionEvaluationState], ToleranceDecisionReasonCode | None
] = {
    ("worst_case_requirement", _E.FAIL): _R.WC_REQUIREMENT_EXCEEDED,
    ("worst_case_requirement", _E.AT_BOUNDARY): _R.WC_REQUIREMENT_AT_BOUNDARY,
    ("worst_case_requirement", _E.PASS): None,
    ("statistical_requirement", _E.FAIL): _R.STAT_REQUIREMENT_EXCEEDED,
    ("statistical_requirement", _E.AT_BOUNDARY): _R.STAT_REQUIREMENT_AT_BOUNDARY,
    ("statistical_requirement", _E.PASS): None,
    ("worst_case_allocation", _E.FAIL): _R.WC_ALLOCATION_EXCEEDED,
    ("worst_case_allocation", _E.AT_BOUNDARY): _R.WC_ALLOCATION_AT_BOUNDARY,
    ("worst_case_allocation", _E.PASS): None,
    ("statistical_allocation", _E.FAIL): _R.STAT_ALLOCATION_EXCEEDED,
    ("statistical_allocation", _E.AT_BOUNDARY): _R.STAT_ALLOCATION_AT_BOUNDARY,
    ("statistical_allocation", _E.PASS): None,
}


def _numeric_dimension_metrics(
    result: ToleranceDecisionResult,
    name: str,
) -> list[DecisionMetric]:
    """Collect pass-through numeric metrics for one numeric dimension."""
    metrics: list[DecisionMetric] = []
    if name == "worst_case_requirement":
        utilization = result.evidence.worst_case_utilization_fraction
    elif name == "statistical_requirement":
        utilization = result.evidence.statistical_utilization_fraction
    else:
        utilization = None
    if utilization is not None:
        metrics.append(DecisionMetric(_UTILIZATION_METRIC_KEY, utilization))
    if name == "statistical_requirement":
        independent = result.evidence.statistical_independent_combined_sigma
        if independent is not None:
            metrics.append(
                DecisionMetric(_INDEPENDENT_SIGMA_METRIC_KEY, independent)
            )
    return metrics


def _build_dimension_item(
    result: ToleranceDecisionResult,
    dimension: ToleranceDecisionDimension,
    index: int,
) -> DecisionEvidenceItem:
    """Build the deterministic evidence item for one decision dimension."""
    name = dimension.name
    if name not in _DIMENSION_SOURCES:
        raise InvalidDecisionEvidenceError(
            f"unknown decision dimension {name!r}; cannot build evidence"
        )
    source = _DIMENSION_SOURCES[name]
    scope = name
    metrics: list[DecisionMetric] = []
    if dimension.state is _E.NOT_REQUESTED:
        raise InvalidDecisionEvidenceError(
            f"dimension {name!r} reports NOT_REQUESTED; no evidence exists"
        )
    if dimension.state is _E.INCOMPLETE:
        code = _STRUCTURAL_DIMENSION_CODES[name]
        severity = ToleranceDecisionSeverity.FAILURE
        comparison = DecisionComparison.NOT_APPLICABLE
        reason_code: ToleranceDecisionReasonCode | None = _R.NO_STACK_PROVIDED
        observed: float | None = None
        reference: float | None = dimension.allowed
        detail = f"dimension {name} incomplete: required stack not provided"
    else:
        key = (name, dimension.state)
        if key not in _NUMERIC_DIMENSION_CODES:
            raise InvalidDecisionEvidenceError(
                f"dimension {name!r} has unsupported state {dimension.state!r}"
            )
        if dimension.actual is None or dimension.allowed is None:
            raise InvalidDecisionEvidenceError(
                f"dimension {name!r} state {dimension.state} requires "
                "actual and allowed values"
            )
        code = _NUMERIC_DIMENSION_CODES[key]
        reason_code = _DIMENSION_REASONS[key]
        severity = _STATE_SEVERITIES[dimension.state]
        comparison = _STATE_COMPARISONS[dimension.state]
        observed = dimension.actual
        reference = dimension.allowed
        detail = (
            f"actual={_format_number(observed)} "
            f"allowed={_format_number(reference)}"
        )
        if dimension.margin is not None:
            metrics.append(DecisionMetric(_MARGIN_METRIC_KEY, dimension.margin))
        equality_tolerance = result.evidence.equality_tolerance
        if equality_tolerance is not None:
            metrics.append(
                DecisionMetric(_EQUALITY_TOLERANCE_METRIC_KEY, equality_tolerance)
            )
        metrics.extend(_numeric_dimension_metrics(result, name))
    metrics.sort(key=lambda item_metric: item_metric.key)
    return DecisionEvidenceItem(
        evidence_id=_make_evidence_id(source, code.value, scope, scope, index),
        evidence_code=code.value,
        source=source,
        scope=scope,
        subject_id=scope,
        reason_code=reason_code,
        observed_value=observed,
        reference_value=reference,
        comparison=comparison,
        severity=severity,
        detail=detail,
        metrics=tuple(metrics),
    )


# ---------------------------------------------------------------------------
# Snapshot-derived evidence builders
# ---------------------------------------------------------------------------


def _build_missing_contributor_items(
    result: ToleranceDecisionResult,
    start_index: int,
) -> list[DecisionEvidenceItem]:
    """Build structural evidence for missing allocation contributors.

    Missing-contributor snapshots do not identify which allocation plan
    reported them, so the items are scoped globally (``scope=None``)
    rather than fabricating a scope, and each ``INCOMPLETE_ALLOCATION``
    reason links to the full set.
    """
    items: list[DecisionEvidenceItem] = []
    index = start_index
    for observation in result.allocation_missing_contributor_snapshots:
        items.append(
            DecisionEvidenceItem(
                evidence_id=_make_evidence_id(
                    DecisionEvidenceSource.ALLOCATION,
                    _C.ALLOCATION_MISSING_CONTRIBUTORS.value,
                    None,
                    observation.contributor_id,
                    index,
                ),
                evidence_code=_C.ALLOCATION_MISSING_CONTRIBUTORS.value,
                source=DecisionEvidenceSource.ALLOCATION,
                scope=None,
                subject_id=observation.contributor_id,
                reason_code=_R.INCOMPLETE_ALLOCATION,
                observed_value=None,
                reference_value=None,
                comparison=DecisionComparison.NOT_APPLICABLE,
                severity=ToleranceDecisionSeverity.FAILURE,
                detail=(
                    f"contributor {observation.contributor_id} "
                    "has no allocation"
                ),
                metrics=(DecisionMetric(_RANK_METRIC_KEY, float(observation.rank)),),
            )
        )
        index += 1
    return items


def _contributor_item(
    *,
    source: DecisionEvidenceSource,
    scope: str,
    contributor_id: str,
    status: str,
    rank: int,
    observed: float,
    reference: float,
    margin: float | None,
    utilization: float | None,
    equality_tolerance: float,
    within_code: DecisionEvidenceCode,
    at_code: DecisionEvidenceCode,
    exceeded_code: DecisionEvidenceCode,
    index: int,
) -> DecisionEvidenceItem:
    """Build one per-contributor reconciliation evidence item."""
    comparison = _comparison_for_values(observed, reference, equality_tolerance)
    if comparison is DecisionComparison.GREATER_THAN:
        code = exceeded_code
        severity = ToleranceDecisionSeverity.FAILURE
    elif comparison is DecisionComparison.AT_BOUNDARY:
        code = at_code
        severity = ToleranceDecisionSeverity.BOUNDARY
    else:
        code = within_code
        severity = ToleranceDecisionSeverity.INFO
    metrics = [DecisionMetric(_RANK_METRIC_KEY, float(rank))]
    if margin is not None:
        metrics.append(DecisionMetric(_MARGIN_METRIC_KEY, margin))
    if utilization is not None:
        metrics.append(DecisionMetric(_UTILIZATION_METRIC_KEY, utilization))
    metrics.sort(key=lambda item_metric: item_metric.key)
    return DecisionEvidenceItem(
        evidence_id=_make_evidence_id(source, code.value, scope, contributor_id, index),
        evidence_code=code.value,
        source=source,
        scope=scope,
        subject_id=contributor_id,
        reason_code=None,
        observed_value=observed,
        reference_value=reference,
        comparison=comparison,
        severity=severity,
        detail=(
            f"actual={_format_number(observed)} "
            f"allocated={_format_number(reference)} status={status}"
        ),
        metrics=tuple(metrics),
    )


def _build_wc_reconciliation_items(
    result: ToleranceDecisionResult,
    start_index: int,
) -> list[DecisionEvidenceItem]:
    """Build per-contributor worst-case reconciliation evidence."""
    equality_tolerance = result.evidence.equality_tolerance
    if equality_tolerance is None:
        equality_tolerance = 0.0
    items: list[DecisionEvidenceItem] = []
    index = start_index
    for observation in result.worst_case_reconciliation_snapshots:
        items.append(
            _contributor_item(
                source=DecisionEvidenceSource.WORST_CASE_RECONCILIATION,
                scope="worst_case_allocation",
                contributor_id=observation.contributor_id,
                status=observation.status,
                rank=observation.rank,
                observed=observation.actual_span,
                reference=observation.allocated_span,
                margin=observation.margin,
                utilization=observation.utilization_fraction,
                equality_tolerance=equality_tolerance,
                within_code=_C.WC_RECONCILIATION_CONTRIBUTOR_WITHIN,
                at_code=_C.WC_RECONCILIATION_CONTRIBUTOR_AT,
                exceeded_code=_C.WC_RECONCILIATION_CONTRIBUTOR_EXCEEDED,
                index=index,
            )
        )
        index += 1
    return items


def _build_stat_reconciliation_items(
    result: ToleranceDecisionResult,
    start_index: int,
) -> list[DecisionEvidenceItem]:
    """Build per-contributor statistical reconciliation evidence."""
    equality_tolerance = result.evidence.equality_tolerance
    if equality_tolerance is None:
        equality_tolerance = 0.0
    items: list[DecisionEvidenceItem] = []
    index = start_index
    for observation in result.statistical_reconciliation_snapshots:
        items.append(
            _contributor_item(
                source=DecisionEvidenceSource.STATISTICAL_RECONCILIATION,
                scope="statistical_allocation",
                contributor_id=observation.contributor_id,
                status=observation.status,
                rank=observation.rank,
                observed=observation.actual_sigma,
                reference=observation.allocated_sigma,
                margin=observation.margin,
                utilization=None,
                equality_tolerance=equality_tolerance,
                within_code=_C.STAT_RECONCILIATION_CONTRIBUTOR_WITHIN,
                at_code=_C.STAT_RECONCILIATION_CONTRIBUTOR_AT,
                exceeded_code=_C.STAT_RECONCILIATION_CONTRIBUTOR_EXCEEDED,
                index=index,
            )
        )
        index += 1
    return items


def _build_covariance_pair_items(
    result: ToleranceDecisionResult,
    start_index: int,
) -> list[DecisionEvidenceItem]:
    """Build per-pair covariance evidence (signed; never sign-flipped).

    A pair is never assigned exclusively to one contributor: the subject
    identity is the deterministic ``first|second`` pair, and the signed
    ``covariance_term`` is preserved exactly.
    """
    items: list[DecisionEvidenceItem] = []
    index = start_index
    for observation in result.covariance_pair_snapshots:
        term = observation.covariance_term
        if term > 0.0:
            comparison = DecisionComparison.GREATER_THAN
        elif term < 0.0:
            comparison = DecisionComparison.LESS_THAN
        else:
            comparison = DecisionComparison.AT_BOUNDARY
        subject = f"{observation.first}|{observation.second}"
        pair_metrics: list[DecisionMetric] = []
        if observation.rho is not None:
            pair_metrics.append(DecisionMetric(_RHO_METRIC_KEY, observation.rho))
        if observation.fraction is not None:
            pair_metrics.append(
                DecisionMetric(_FRACTION_METRIC_KEY, observation.fraction)
            )
        if observation.percentage is not None:
            pair_metrics.append(
                DecisionMetric(_PERCENTAGE_METRIC_KEY, observation.percentage)
            )
        pair_metrics.sort(key=lambda item_metric: item_metric.key)
        items.append(
            DecisionEvidenceItem(
                evidence_id=_make_evidence_id(
                    DecisionEvidenceSource.CORRELATED_STATISTICAL,
                    _C.COVARIANCE_PAIR_CONTRIBUTION.value,
                    "covariance",
                    subject,
                    index,
                ),
                evidence_code=_C.COVARIANCE_PAIR_CONTRIBUTION.value,
                source=DecisionEvidenceSource.CORRELATED_STATISTICAL,
                scope="covariance",
                subject_id=subject,
                reason_code=None,
                observed_value=term,
                reference_value=None,
                comparison=comparison,
                severity=ToleranceDecisionSeverity.INFO,
                detail=(
                    f"rho={_format_number(observation.rho)} "
                    f"covariance_term={_format_number(term)}"
                ),
                metrics=tuple(pair_metrics),
            )
        )
        index += 1
    return items


_CORRELATION_COMPARISONS: dict[ToleranceDecisionReasonCode, DecisionComparison] = {
    _R.CORRELATION_INCREASES_SIGMA: DecisionComparison.GREATER_THAN,
    _R.CORRELATION_DECREASES_SIGMA: DecisionComparison.LESS_THAN,
    _R.CORRELATION_EFFECTIVELY_NEUTRAL: DecisionComparison.AT_BOUNDARY,
}

_CORRELATION_EVIDENCE_CODES: dict[ToleranceDecisionReasonCode, DecisionEvidenceCode] = {
    _R.CORRELATION_INCREASES_SIGMA: _C.COVARIANCE_INCREASES_VARIANCE,
    _R.CORRELATION_DECREASES_SIGMA: _C.COVARIANCE_REDUCES_VARIANCE,
    _R.CORRELATION_EFFECTIVELY_NEUTRAL: _C.COVARIANCE_EFFECTIVELY_NEUTRAL,
}


def _build_correlation_reason_item(
    result: ToleranceDecisionResult,
    reason: ToleranceDecisionReason,
    index: int,
) -> DecisionEvidenceItem:
    """Build combined-sigma effect evidence for one correlation reason."""
    code = _CORRELATION_EVIDENCE_CODES.get(reason.code)
    comparison = _CORRELATION_COMPARISONS.get(reason.code)
    if code is None or comparison is None:
        raise InvalidDecisionEvidenceError(
            f"unsupported correlation reason {reason.code!r}"
        )
    actual = result.evidence.statistical_actual_combined_sigma
    independent = result.evidence.statistical_independent_combined_sigma
    if actual is None or independent is None:
        raise InvalidDecisionEvidenceError(
            "correlation reason requires statistical actual and independent "
            "combined sigma; authoritative source data is missing"
        )
    return DecisionEvidenceItem(
        evidence_id=_make_evidence_id(
            DecisionEvidenceSource.CORRELATED_STATISTICAL,
            code.value,
            "covariance",
            "combined_sigma",
            index,
        ),
        evidence_code=code.value,
        source=DecisionEvidenceSource.CORRELATED_STATISTICAL,
        scope="covariance",
        subject_id="combined_sigma",
        reason_code=reason.code,
        observed_value=actual,
        reference_value=independent,
        comparison=comparison,
        severity=reason.severity,
        detail=(
            f"actual={_format_number(actual)} "
            f"independent={_format_number(independent)}"
        ),
        metrics=(),
    )


_VARIANCE_METRIC_KEY = "variance"


def _build_sensitivity_items(
    result: ToleranceDecisionResult,
    start_index: int,
) -> list[DecisionEvidenceItem]:
    """Build controlling-contributor sensitivity evidence.

    Sensitivity explains contribution; it is supporting evidence only
    and never a design recommendation.
    """
    items: list[DecisionEvidenceItem] = []
    index = start_index

    wc_by_name = {obs.name: obs for obs in result.worst_case_contributor_snapshots}
    for name in result.sensitivity.worst_case_controlling:
        observation = wc_by_name.get(name)
        if observation is None:
            raise InvalidDecisionEvidenceError(
                f"controlling contributor {name!r} has no worst-case "
                "sensitivity snapshot; authoritative source data is missing"
            )
        item_metrics: list[DecisionMetric] = [
            DecisionMetric(_RANK_METRIC_KEY, float(observation.rank))
        ]
        if observation.fraction is not None:
            item_metrics.append(
                DecisionMetric(_FRACTION_METRIC_KEY, observation.fraction)
            )
        if observation.percentage is not None:
            item_metrics.append(
                DecisionMetric(_PERCENTAGE_METRIC_KEY, observation.percentage)
            )
        item_metrics.sort(key=lambda item_metric: item_metric.key)
        items.append(
            DecisionEvidenceItem(
                evidence_id=_make_evidence_id(
                    DecisionEvidenceSource.SENSITIVITY,
                    _C.SENSITIVITY_WC_CONTRIBUTOR.value,
                    "sensitivity",
                    name,
                    index,
                ),
                evidence_code=_C.SENSITIVITY_WC_CONTRIBUTOR.value,
                source=DecisionEvidenceSource.SENSITIVITY,
                scope="sensitivity",
                subject_id=name,
                reason_code=None,
                observed_value=observation.span,
                reference_value=None,
                comparison=DecisionComparison.NOT_APPLICABLE,
                severity=ToleranceDecisionSeverity.INFO,
                detail=(
                    f"span={_format_number(observation.span)} "
                    f"rank={observation.rank}"
                ),
                metrics=tuple(item_metrics),
            )
        )
        index += 1

    stat_by_name = {obs.name: obs for obs in result.statistical_contributor_snapshots}
    for name in result.sensitivity.statistical_controlling:
        observation = stat_by_name.get(name)
        if observation is None:
            raise InvalidDecisionEvidenceError(
                f"controlling contributor {name!r} has no statistical "
                "sensitivity snapshot; authoritative source data is missing"
            )
        item_metrics = [DecisionMetric(_RANK_METRIC_KEY, float(observation.rank))]
        if observation.fraction is not None:
            item_metrics.append(
                DecisionMetric(_FRACTION_METRIC_KEY, observation.fraction)
            )
        if observation.percentage is not None:
            item_metrics.append(
                DecisionMetric(_PERCENTAGE_METRIC_KEY, observation.percentage)
            )
        if observation.variance is not None:
            item_metrics.append(
                DecisionMetric(_VARIANCE_METRIC_KEY, observation.variance)
            )
        item_metrics.sort(key=lambda item_metric: item_metric.key)
        items.append(
            DecisionEvidenceItem(
                evidence_id=_make_evidence_id(
                    DecisionEvidenceSource.SENSITIVITY,
                    _C.SENSITIVITY_STAT_CONTRIBUTOR.value,
                    "sensitivity",
                    name,
                    index,
                ),
                evidence_code=_C.SENSITIVITY_STAT_CONTRIBUTOR.value,
                source=DecisionEvidenceSource.SENSITIVITY,
                scope="sensitivity",
                subject_id=name,
                reason_code=None,
                observed_value=observation.sigma,
                reference_value=None,
                comparison=DecisionComparison.NOT_APPLICABLE,
                severity=ToleranceDecisionSeverity.INFO,
                detail=(
                    f"sigma={_format_number(observation.sigma)} "
                    f"rank={observation.rank}"
                ),
                metrics=tuple(item_metrics),
            )
        )
        index += 1
    return items


# ---------------------------------------------------------------------------
# Reason linkage and decision-level evidence
# ---------------------------------------------------------------------------

#: Reason codes documented as non-evidentiary (never emitted by Stage 15K).
_NON_EVIDENTIARY_REASONS: frozenset[ToleranceDecisionReasonCode] = frozenset(
    {_R.NO_REQUIREMENT_PROVIDED}
)

_REASON_EVIDENCE_CODES: dict[ToleranceDecisionReasonCode, DecisionEvidenceCode] = {
    _R.WC_REQUIREMENT_EXCEEDED: _C.WC_SPAN_EXCEEDS_LIMIT,
    _R.WC_REQUIREMENT_AT_BOUNDARY: _C.WC_SPAN_AT_LIMIT,
    _R.STAT_REQUIREMENT_EXCEEDED: _C.STAT_SIGMA_EXCEEDS_LIMIT,
    _R.STAT_REQUIREMENT_AT_BOUNDARY: _C.STAT_SIGMA_AT_LIMIT,
    _R.WC_ALLOCATION_EXCEEDED: _C.WC_ALLOCATION_EXCEEDS_PLAN,
    _R.WC_ALLOCATION_AT_BOUNDARY: _C.WC_ALLOCATION_AT_PLAN_LIMIT,
    _R.STAT_ALLOCATION_EXCEEDED: _C.STAT_ALLOCATION_EXCEEDS_PLAN,
    _R.STAT_ALLOCATION_AT_BOUNDARY: _C.STAT_ALLOCATION_AT_PLAN_LIMIT,
    _R.INCOMPLETE_ALLOCATION: _C.ALLOCATION_MISSING_CONTRIBUTORS,
    _R.WC_STAT_INCONSISTENT: _C.WC_STAT_DISAGREEMENT,
}


_SCOPE_AGNOSTIC_REASONS: frozenset[ToleranceDecisionReasonCode] = frozenset(
    {
        _R.INCOMPLETE_ALLOCATION,
        _R.WC_STAT_INCONSISTENT,
        _R.CORRELATION_INCREASES_SIGMA,
        _R.CORRELATION_DECREASES_SIGMA,
        _R.CORRELATION_EFFECTIVELY_NEUTRAL,
    }
)


def _reason_evidence_code(
    reason: ToleranceDecisionReason,
) -> DecisionEvidenceCode | None:
    """Map one reason to its expected evidence code.

    Returns ``None`` for documented non-evidentiary reasons.  Raises
    ``InvalidDecisionEvidenceError`` for unmappable reasons.
    """
    if reason.code in _NON_EVIDENTIARY_REASONS:
        return None
    if reason.code in _CORRELATION_EVIDENCE_CODES:
        return _CORRELATION_EVIDENCE_CODES[reason.code]
    if reason.code is _R.NO_STACK_PROVIDED:
        scope = reason.scope or ""
        if scope.startswith("worst_case"):
            return _C.WC_STACK_NOT_PROVIDED
        if scope.startswith("statistical"):
            return _C.STAT_STACK_NOT_PROVIDED
        raise InvalidDecisionEvidenceError(
            f"NO_STACK_PROVIDED reason has unmappable scope {reason.scope!r}"
        )
    code = _REASON_EVIDENCE_CODES.get(reason.code)
    if code is None:
        raise InvalidDecisionEvidenceError(
            f"reason {reason.code!r} has no evidence mapping; "
            "refusing to fabricate evidence"
        )
    return code


def _link_reasons(
    result: ToleranceDecisionResult,
    items: tuple[DecisionEvidenceItem, ...],
) -> tuple[ReasonEvidenceLink, ...]:
    """Deterministically link every triggered reason to evidence.

    Fails closed when a triggered reason has no matching evidence item.
    Scope filtering is applied only when both the reason and the
    candidate item are scoped; globally scoped structural evidence
    (missing contributors) stays linkable from scoped reasons.
    """
    links: list[ReasonEvidenceLink] = []
    for reason in result.reasons:
        expected = _reason_evidence_code(reason)
        if expected is None:
            continue
        matching = [
            item
            for item in items
            if item.evidence_code == expected.value
            and (
                reason.code in _SCOPE_AGNOSTIC_REASONS
                or reason.scope is None
                or item.scope is None
                or item.scope == reason.scope
            )
        ]
        if not matching:
            raise InvalidDecisionEvidenceError(
                f"triggered reason {reason.code.value} has no supporting "
                "evidence; refusing to fabricate evidence"
            )
        links.append(
            ReasonEvidenceLink(
                reason_code=reason.code,
                evidence_ids=tuple(item.evidence_id for item in matching),
            )
        )
    return tuple(links)


def _build_wc_stat_disagreement_item(
    reason: ToleranceDecisionReason,
    index: int,
) -> DecisionEvidenceItem:
    """Build the decision-level worst-case/statistical disagreement item."""
    return DecisionEvidenceItem(
        evidence_id=_make_evidence_id(
            DecisionEvidenceSource.DECISION,
            _C.WC_STAT_DISAGREEMENT.value,
            "decision",
            "overall_status",
            index,
        ),
        evidence_code=_C.WC_STAT_DISAGREEMENT.value,
        source=DecisionEvidenceSource.DECISION,
        scope="decision",
        subject_id="overall_status",
        reason_code=_R.WC_STAT_INCONSISTENT,
        observed_value=None,
        reference_value=None,
        comparison=DecisionComparison.NOT_APPLICABLE,
        severity=reason.severity,
        detail=reason.detail or "worst-case and statistical outcomes disagree",
        metrics=(),
    )


def _build_no_criteria_item(index: int) -> DecisionEvidenceItem:
    """Build structural evidence that no evaluation criteria were requested."""
    return DecisionEvidenceItem(
        evidence_id=_make_evidence_id(
            DecisionEvidenceSource.STRUCTURAL,
            _C.NO_CRITERIA_REQUESTED.value,
            "decision",
            "criteria",
            index,
        ),
        evidence_code=_C.NO_CRITERIA_REQUESTED.value,
        source=DecisionEvidenceSource.STRUCTURAL,
        scope="decision",
        subject_id="criteria",
        reason_code=None,
        observed_value=None,
        reference_value=None,
        comparison=DecisionComparison.NOT_APPLICABLE,
        severity=ToleranceDecisionSeverity.INFO,
        detail="no evaluation criteria were requested",
        metrics=(),
    )


# ---------------------------------------------------------------------------
# Public evidence API
# ---------------------------------------------------------------------------


def build_decision_evidence(
    decision_result: ToleranceDecisionResult,
) -> DecisionEvidenceBundle:
    """Build the deterministic evidence bundle for a Stage 15K decision.

    The decision result is treated as read-only authoritative input: no
    engineering calculation is rerun, no value is rounded and nothing is
    mutated.  Raises
    :class:`~origlyph.tolerance.exceptions.InvalidDecisionEvidenceError`
    when authoritative source data required to support a triggered
    reason is missing (fail closed) instead of fabricating evidence.
    """
    if not isinstance(decision_result, ToleranceDecisionResult):
        raise InvalidDecisionEvidenceError(
            "decision_result must be a ToleranceDecisionResult"
        )

    items: list[DecisionEvidenceItem] = []
    index = 0

    for dimension in decision_result.dimensions:
        if dimension.state is _E.NOT_REQUESTED:
            continue
        items.append(_build_dimension_item(decision_result, dimension, index))
        index += 1

    missing_items = _build_missing_contributor_items(decision_result, index)
    items.extend(missing_items)
    index += len(missing_items)

    wc_recon_items = _build_wc_reconciliation_items(decision_result, index)
    items.extend(wc_recon_items)
    index += len(wc_recon_items)

    stat_recon_items = _build_stat_reconciliation_items(decision_result, index)
    items.extend(stat_recon_items)
    index += len(stat_recon_items)

    pair_items = _build_covariance_pair_items(decision_result, index)
    items.extend(pair_items)
    index += len(pair_items)

    sensitivity_items = _build_sensitivity_items(decision_result, index)
    items.extend(sensitivity_items)
    index += len(sensitivity_items)

    # Reason-driven decision-level items, in deterministic reason order.
    for reason in decision_result.reasons:
        if reason.code in _CORRELATION_EVIDENCE_CODES:
            items.append(
                _build_correlation_reason_item(decision_result, reason, index)
            )
            index += 1
        elif reason.code is _R.WC_STAT_INCONSISTENT:
            items.append(
                _build_wc_stat_disagreement_item(reason, index)
            )
            index += 1

    # Structural no-criteria evidence, only when truly nothing was
    # requested or evaluated (fail-closed against hidden criteria).
    if (
        not decision_result.dimensions
        and not decision_result.reasons
        and decision_result.worst_case_passed is None
        and decision_result.statistical_passed is None
        and decision_result.worst_case_reconciliation_passed is None
        and decision_result.statistical_reconciliation_passed is None
    ):
        items.append(_build_no_criteria_item(index))
        index += 1

    # Deterministic ordering: severity priority, source priority, scope,
    # subject, code, then the stable build index as final tiebreaker.
    build_order = list(enumerate(items))
    ordered: list[DecisionEvidenceItem] = [
        entry[1]
        for entry in sorted(
            build_order,
            key=lambda entry: (
                _SEVERITY_ORDER.index(entry[1].severity),
                _SOURCE_ORDER.index(entry[1].source),
                entry[1].scope or "",
                entry[1].subject_id or "",
                entry[1].evidence_code,
                entry[0],
            ),
        )
    ]

    evidence_items = tuple(ordered)
    reason_to_evidence = _link_reasons(decision_result, evidence_items)
    governing_evidence_ids = tuple(
        item.evidence_id
        for item in evidence_items
        if item.severity is ToleranceDecisionSeverity.FAILURE
    )
    marginal_evidence_ids = tuple(
        item.evidence_id
        for item in evidence_items
        if item.severity is ToleranceDecisionSeverity.BOUNDARY
    )
    return DecisionEvidenceBundle(
        decision_status=decision_result.overall_status,
        is_complete=decision_result.is_complete,
        evidence_items=evidence_items,
        reason_to_evidence=reason_to_evidence,
        governing_evidence_ids=governing_evidence_ids,
        marginal_evidence_ids=marginal_evidence_ids,
    )


_WITHIN_LIMIT_CODES: frozenset[str] = frozenset(
    {
        _C.WC_SPAN_WITHIN_LIMIT.value,
        _C.STAT_SIGMA_WITHIN_LIMIT.value,
        _C.WC_ALLOCATION_WITHIN_PLAN.value,
        _C.STAT_ALLOCATION_WITHIN_PLAN.value,
    }
)


def _render_summary(
    status: ToleranceDecisionStatus,
    governing: tuple[DecisionEvidenceItem, ...],
    marginal: tuple[DecisionEvidenceItem, ...],
    supporting: tuple[DecisionEvidenceItem, ...],
) -> tuple[str, str]:
    """Return deterministic ``(summary_code, summary)`` for one bundle."""
    if governing:
        lead_code = governing[0].evidence_code
    elif marginal:
        lead_code = marginal[0].evidence_code
    elif supporting:
        lead_code = supporting[0].evidence_code
    else:
        lead_code = _C.NO_CRITERIA_REQUESTED.value
    summary_code = f"{status.value}:{lead_code}"
    primary = governing[0] if governing else None
    if primary is not None:
        summary = (
            f"Decision {status.value}: governed by {primary.evidence_code} "
            f"(observed {_format_number(primary.observed_value)}, "
            f"reference {_format_number(primary.reference_value)})."
        )
    elif marginal:
        summary = (
            f"Decision {status.value}: at a deterministic boundary, "
            f"led by {marginal[0].evidence_code}."
        )
    elif any(item.evidence_code in _WITHIN_LIMIT_CODES for item in supporting):
        summary = (
            f"Decision {status.value}: all evaluated criteria are within "
            "limits."
        )
    elif supporting:
        summary = (
            f"Decision {status.value}: supporting observations available; "
            "no numeric criterion evaluated."
        )
    else:
        summary = (
            f"Decision {status.value}: no evaluation criteria were "
            "requested."
        )
    return summary_code, summary


def _governing_reason_codes(
    links: tuple[ReasonEvidenceLink, ...],
    governing_id_set: set[str],
) -> tuple[ToleranceDecisionReasonCode, ...]:
    return tuple(
        link.reason_code
        for link in links
        if any(evidence_id in governing_id_set for evidence_id in link.evidence_ids)
    )


def explain_tolerance_decision(
    decision_result: ToleranceDecisionResult,
    evidence_bundle: DecisionEvidenceBundle | None = None,
) -> DecisionExplanation:
    """Explain a Stage 15K tolerance decision deterministically.

    When ``evidence_bundle`` is omitted it is built internally from the
    decision result alone; no engineering calculation is rerun and no
    value is rounded.  The explanation carries structured evidence and a
    fixed-template summary only: no LLM, no generative text and no
    hidden reasoning.
    """
    if not isinstance(decision_result, ToleranceDecisionResult):
        raise InvalidDecisionEvidenceError(
            "decision_result must be a ToleranceDecisionResult"
        )
    if evidence_bundle is None:
        bundle = build_decision_evidence(decision_result)
    else:
        bundle = evidence_bundle
    if not isinstance(bundle, DecisionEvidenceBundle):
        raise InvalidDecisionEvidenceError(
            "evidence_bundle must be a DecisionEvidenceBundle"
        )

    governing = bundle.governing_evidence
    marginal = bundle.marginal_evidence
    supporting = bundle.supporting_evidence
    governing_id_set = set(bundle.governing_evidence_ids)
    governing_reasons = _governing_reason_codes(
        bundle.reason_to_evidence, governing_id_set
    )
    summary_code, summary = _render_summary(
        bundle.decision_status, governing, marginal, supporting
    )

    return DecisionExplanation(
        final_status=bundle.decision_status,
        summary_code=summary_code,
        governing_reasons=governing_reasons,
        governing_evidence=governing,
        marginal_evidence=marginal,
        supporting_evidence=supporting,
        is_complete=bundle.is_complete,
        summary=summary,
    )














