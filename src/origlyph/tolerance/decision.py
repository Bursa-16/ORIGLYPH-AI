"""Deterministic tolerance decision layer (Stage 15K).

This module orchestrates the existing tolerance-analysis engines into a
single coherent, traceable engineering decision.  It does **not**
reimplement any of the existing math; it delegates to the authoritative
engines and combines their outputs under deterministic decision rules.

Stage 15K answers questions such as:

- Is the stack compliant with the specified tolerance requirement?
- Does worst-case analysis pass?
- Does statistical analysis pass?
- Is the allocation plan respected?
- Which contributors are controlling the result?
- Is the result robust or marginal?
- Are worst-case and statistical conclusions consistent?
- Does covariance materially affect the statistical conclusion?
- What is the deterministic overall engineering decision?
- What deterministic reasons explain that decision?

This layer is **not** an AI recommendation engine.  It is:

- deterministic
- explainable
- traceable
- fail-closed
- formula-driven
- reproducible

It does **not** implement health scores, confidence scores, or any
probabilistic text generation.  Every observation is a typed enum with
structured numeric evidence.

Authoritative engines reused
----------------------------
- ``worst_case`` (Stage 15C-R)
- ``statistical`` (Stage 15D)
- ``worst_case_sensitivity`` (Stage 15F)
- ``statistical_sensitivity`` (Stage 15F)
- ``worst_case_budget`` (Stage 15G)
- ``statistical_budget`` (Stage 15G)
- ``validate_allocation`` (Stage 15H)
- ``reconcile_allocation`` (Stage 15I)
- ``reconcile_statistical_allocation`` (Stage 15J)

Equality policy
---------------
Reuses the deterministic engineering equality tolerance of ``1e-12``
established by Stage 15G / 15H / 15I / 15J.  No new or contradictory
epsilon is introduced.
"""

from __future__ import annotations

from collections.abc import Sequence

from .allocation import validate_allocation
from .exceptions import InvalidToleranceDecisionError
from .models import (
    AllocationPlan,
    Correlation,
    DecisionAllocationMissingContributorObservation,
    DecisionCovariancePairObservation,
    DecisionReconciliationObservation,
    DecisionStatisticalContributionObservation,
    DecisionStatisticalReconciliationObservation,
    DecisionWorstCaseContributionObservation,
    StatisticalAllocationPlan,
    StatisticalStack,
    ToleranceDecisionCovarianceEffect,
    ToleranceDecisionDimension,
    ToleranceDecisionEvaluationState,
    ToleranceDecisionEvidence,
    ToleranceDecisionReason,
    ToleranceDecisionReasonCode,
    ToleranceDecisionResult,
    ToleranceDecisionSensitivity,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    ToleranceStack,
)
from .reconciliation import reconcile_allocation
from .sensitivity import statistical_sensitivity, worst_case_sensitivity
from .statistical import statistical
from .statistical_reconciliation import reconcile_statistical_allocation
from .worst_case import worst_case

__all__ = [
    "evaluate_tolerance_decision",
]


# Reuse the established equality policy.
_EQUALITY_TOLERANCE = 1e-12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_dimension(
    actual: float,
    allowed: float,
) -> tuple[
    ToleranceDecisionEvaluationState, float, bool
]:
    """Classify a single dimension against an allowed value.

    Returns
    -------
    state:
        PASS / AT_BOUNDARY / FAIL based on the established equality
        policy.
    margin:
        ``allowed - actual`` (positive when passing).
    at_boundary:
        ``True`` if the result is at the equality boundary
        (technically passes but requires review).
    """
    margin = allowed - actual
    if abs(margin) <= _EQUALITY_TOLERANCE:
        return (
            ToleranceDecisionEvaluationState.AT_BOUNDARY,
            margin,
            True,
        )
    if margin > 0.0:
        return ToleranceDecisionEvaluationState.PASS, margin, False
    return ToleranceDecisionEvaluationState.FAIL, margin, False


def _validate_positive_finite(
    value: float | None,
    field_name: str,
) -> float | None:
    """Validate that a value, if provided, is finite and strictly positive."""
    if value is None:
        return None
    fvalue = float(value)
    if fvalue != fvalue or fvalue == float("inf") or fvalue == float("-inf"):
        raise InvalidToleranceDecisionError(
            f"{field_name} must be a finite positive number, got {value!r}"
        )
    if fvalue <= 0.0:
        raise InvalidToleranceDecisionError(
            f"{field_name} must be a finite positive number, got {value!r}"
        )
    return fvalue


def _validate_sigma_multiplier(k: float) -> float:
    """Validate the sigma multiplier."""
    value = float(k)
    if value != value or value == float("inf") or value == float("-inf"):
        raise InvalidToleranceDecisionError(
            f"sigma_multiplier must be a finite number, got {k!r}"
        )
    if value <= 0.0:
        raise InvalidToleranceDecisionError(
            f"sigma_multiplier must be strictly positive, got {k!r}"
        )
    return value


def _wc_controlling(stack: ToleranceStack) -> tuple[str, ...]:
    """Compute deterministic controlling contributors for worst-case.

    Returns an ordered tuple of contributor IDs, most controlling
    first, sorted by ``fraction`` descending.  Ties are broken by
    contributor name ascending to guarantee determinism.
    """
    sens = worst_case_sensitivity(stack)
    impacts = sorted(
        sens.impacts,
        key=lambda imp: (-imp.fraction, imp.name),
    )
    return tuple(imp.name for imp in impacts)


def _stat_controlling(
    stack: StatisticalStack,
    sigma_multiplier: float,
    correlations: tuple[Correlation, ...] | None,
) -> tuple[str, ...]:
    """Compute deterministic controlling contributors for statistical.

    Sorted by ``fraction_of_total_variance`` descending.  Ties broken
    by contributor name ascending.
    """
    sens = statistical_sensitivity(
        stack,
        sigma_multiplier=sigma_multiplier,
        correlations=correlations,
    )
    impacts = sorted(
        sens.contributions,
        key=lambda imp: (-imp.fraction, imp.name),
    )
    return tuple(imp.name for imp in impacts)


def _classify_covariance_effect(
    *,
    correlations: Sequence[Correlation] | None,
    stat_stack: StatisticalStack | None,
    sigma_multiplier: float,
) -> ToleranceDecisionCovarianceEffect:
    """Determine the deterministic effect of correlations on combined sigma.

    Compares the combined sigma computed with the supplied correlations
    to the independent reference.  Both reference calls use the same
    authoritative ``statistical`` engine and the same multiplier.
    """
    if not correlations or stat_stack is None:
        return ToleranceDecisionCovarianceEffect.NOT_REQUESTED
    correlated = statistical(
        stat_stack,
        sigma_multiplier=sigma_multiplier,
        correlations=tuple(correlations),
    )
    independent = statistical(
        stat_stack,
        sigma_multiplier=sigma_multiplier,
        correlations=None,
    )
    diff = correlated.combined_sigma - independent.combined_sigma
    if abs(diff) <= _EQUALITY_TOLERANCE:
        return ToleranceDecisionCovarianceEffect.NEUTRAL
    if diff > 0.0:
        return ToleranceDecisionCovarianceEffect.INCREASES
    return ToleranceDecisionCovarianceEffect.DECREASES


def _build_dimension(
    name: str,
    state: ToleranceDecisionEvaluationState,
    actual: float | None,
    allowed: float | None,
    margin: float | None,
) -> ToleranceDecisionDimension:
    return ToleranceDecisionDimension(
        name=name,
        state=state,
        actual=actual,
        allowed=allowed,
        margin=margin,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_tolerance_decision(  # noqa: C901
    *,
    worst_case_stack: ToleranceStack | None = None,
    statistical_stack: StatisticalStack | None = None,
    allowed_worst_case_span: float | None = None,
    allowed_combined_sigma: float | None = None,
    sigma_multiplier: float = 3.0,
    correlations: tuple[Correlation, ...] | None = None,
    worst_case_allocation: AllocationPlan | None = None,
    statistical_allocation: StatisticalAllocationPlan | None = None,
    require_complete: bool = True,
) -> ToleranceDecisionResult:
    """Deterministically orchestrate tolerance engines into one decision.

    The decision layer combines worst-case, statistical, sensitivity,
    and (optional) reconciliation dimensions into a single
    ``ToleranceDecisionResult`` with explicit dimension states,
    controlling contributors, covariance effect, and a structured
    reason list.

    The function is fail-closed: mandatory inputs that are absent
    produce an ``INCOMPLETE`` decision rather than a fabricated
    ``PASS``.  Optional dimensions report ``NOT_REQUESTED``.

    Returns
    -------
    ToleranceDecisionResult
        Structured, deterministic decision result.

    Raises
    ------
    InvalidToleranceDecisionError
        If the input configuration cannot be evaluated.
    """
    if worst_case_stack is None and statistical_stack is None:
        raise InvalidToleranceDecisionError(
            "at least one of worst_case_stack or statistical_stack must "
            "be provided"
        )

    k = _validate_sigma_multiplier(sigma_multiplier)
    allowed_wc = _validate_positive_finite(
        allowed_worst_case_span, "allowed_worst_case_span"
    )
    allowed_stat = _validate_positive_finite(
        allowed_combined_sigma, "allowed_combined_sigma"
    )

    dimensions: list[ToleranceDecisionDimension] = []
    reasons: list[ToleranceDecisionReason] = []
    any_failure = False
    any_boundary = False
    any_incomplete = False

    # Worst-case requirement dimension
    wc_actual_span: float | None = None
    wc_margin_value: float | None = None
    wc_passed: bool | None = None
    if worst_case_stack is not None and allowed_wc is not None:
        wc_result = worst_case(worst_case_stack)
        wc_actual_span = wc_result.total_span
        state, margin, at_boundary = _classify_dimension(
            wc_actual_span, allowed_wc
        )
        dimensions.append(
            _build_dimension(
                "worst_case_requirement", state, wc_actual_span,
                allowed_wc, margin,
            )
        )
        wc_margin_value = margin
        if state is ToleranceDecisionEvaluationState.FAIL:
            any_failure = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope=None,
                    detail=(
                        f"actual={wc_actual_span:.12g} "
                        f"allowed={allowed_wc:.12g}"
                    ),
                )
            )
        elif state is ToleranceDecisionEvaluationState.AT_BOUNDARY:
            any_boundary = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_REQUIREMENT_AT_BOUNDARY,
                    severity=ToleranceDecisionSeverity.BOUNDARY,
                    scope=None,
                    detail=(
                        f"actual={wc_actual_span:.12g} "
                        f"allowed={allowed_wc:.12g}"
                    ),
                )
            )
        wc_passed = (
            state is ToleranceDecisionEvaluationState.PASS or at_boundary
        )
    elif allowed_wc is not None and worst_case_stack is None:
        any_incomplete = True
        dimensions.append(
            _build_dimension(
                "worst_case_requirement",
                ToleranceDecisionEvaluationState.INCOMPLETE,
                None, allowed_wc, None,
            )
        )
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope="worst_case_requirement",
                detail=(
                    "allowed_worst_case_span supplied but "
                    "worst_case_stack is None"
                ),
            )
        )

    # Statistical requirement dimension
    stat_actual_sigma: float | None = None
    stat_independent_sigma: float | None = None
    stat_margin_value: float | None = None
    stat_passed: bool | None = None
    if statistical_stack is not None:
        # Always compute the actual combined sigma for evidence, even if no
        # allowed budget is supplied.  This supports downstream analysis of
        # covariance effect and the independent reference.
        stat_result = statistical(
            statistical_stack,
            sigma_multiplier=k,
            correlations=correlations,
        )
        stat_actual_sigma = stat_result.combined_sigma
        if allowed_stat is not None:
            state, margin, at_boundary = _classify_dimension(
                stat_actual_sigma, allowed_stat
            )
            dimensions.append(
                _build_dimension(
                    "statistical_requirement", state, stat_actual_sigma,
                    allowed_stat, margin,
                )
            )
            stat_margin_value = margin
            if state is ToleranceDecisionEvaluationState.FAIL:
                any_failure = True
                reasons.append(
                    ToleranceDecisionReason(
                        code=(
                            ToleranceDecisionReasonCode
                            .STAT_REQUIREMENT_EXCEEDED
                        ),
                        severity=ToleranceDecisionSeverity.FAILURE,
                        scope=None,
                        detail=(
                            f"actual={stat_actual_sigma:.12g} "
                            f"allowed={allowed_stat:.12g}"
                        ),
                    )
                )
            elif state is ToleranceDecisionEvaluationState.AT_BOUNDARY:
                any_boundary = True
                reasons.append(
                    ToleranceDecisionReason(
                        code=(
                            ToleranceDecisionReasonCode
                            .STAT_REQUIREMENT_AT_BOUNDARY
                        ),
                        severity=ToleranceDecisionSeverity.BOUNDARY,
                        scope=None,
                        detail=(
                            f"actual={stat_actual_sigma:.12g} "
                            f"allowed={allowed_stat:.12g}"
                        ),
                    )
                )
            stat_passed = (
                state is ToleranceDecisionEvaluationState.PASS or at_boundary
            )
        if correlations:
            independent = statistical(
                statistical_stack,
                sigma_multiplier=k,
                correlations=None,
            )
            stat_independent_sigma = independent.combined_sigma
    elif allowed_stat is not None and statistical_stack is None:
        any_incomplete = True
        dimensions.append(
            _build_dimension(
                "statistical_requirement",
                ToleranceDecisionEvaluationState.INCOMPLETE,
                None, allowed_stat, None,
            )
        )
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope="statistical_requirement",
                detail=(
                    "allowed_combined_sigma supplied but "
                    "statistical_stack is None"
                ),
            )
        )

    # Worst-case allocation reconciliation
    wc_recon_passed: bool | None = None
    if worst_case_stack is not None and worst_case_allocation is not None:
        validation = validate_allocation(
            worst_case_stack, worst_case_allocation,
            require_complete=require_complete,
        )
        recon = reconcile_allocation(
            worst_case_stack, worst_case_allocation,
            require_complete=require_complete,
        )
        state, margin, at_boundary = _classify_dimension(
            recon.actual_total_span, recon.allocated_total
        )
        dimensions.append(
            _build_dimension(
                "worst_case_allocation", state, recon.actual_total_span,
                recon.allocated_total, margin,
            )
        )
        if state is ToleranceDecisionEvaluationState.FAIL:
            any_failure = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_ALLOCATION_EXCEEDED,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="worst_case_allocation",
                    detail=(
                        f"actual={recon.actual_total_span:.12g} "
                        f"allocated={recon.allocated_total:.12g}"
                    ),
                )
            )
        elif state is ToleranceDecisionEvaluationState.AT_BOUNDARY:
            any_boundary = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_ALLOCATION_AT_BOUNDARY,
                    severity=ToleranceDecisionSeverity.BOUNDARY,
                    scope="worst_case_allocation",
                    detail=(
                        f"actual={recon.actual_total_span:.12g} "
                        f"allocated={recon.allocated_total:.12g}"
                    ),
                )
            )
        wc_recon_passed = (
            state is ToleranceDecisionEvaluationState.PASS or at_boundary
        )
        if not validation.is_complete:
            any_incomplete = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.INCOMPLETE_ALLOCATION,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="worst_case_allocation",
                    detail=(
                        "missing contributors: "
                        f"{list(validation.missing_contributors)}"
                    ),
                )
            )
    elif worst_case_allocation is not None and worst_case_stack is None:
        any_incomplete = True
        dimensions.append(
            _build_dimension(
                "worst_case_allocation",
                ToleranceDecisionEvaluationState.INCOMPLETE,
                None, None, None,
            )
        )
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope="worst_case_allocation",
                detail=(
                    "worst_case_allocation supplied but "
                    "worst_case_stack is None"
                ),
            )
        )

    # Statistical allocation reconciliation
    stat_recon_passed: bool | None = None
    if statistical_stack is not None and statistical_allocation is not None:
        recon = reconcile_statistical_allocation(
            statistical_stack,
            statistical_allocation,
            correlations=correlations,
            require_complete=require_complete,
        )
        state, margin, at_boundary = _classify_dimension(
            recon.actual_combined_sigma, recon.allocated_combined_sigma
        )
        dimensions.append(
            _build_dimension(
                "statistical_allocation",
                state, recon.actual_combined_sigma,
                recon.allocated_combined_sigma, margin,
            )
        )
        if state is ToleranceDecisionEvaluationState.FAIL:
            any_failure = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.STAT_ALLOCATION_EXCEEDED,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="statistical_allocation",
                    detail=(
                        f"actual={recon.actual_combined_sigma:.12g} "
                        f"allocated={recon.allocated_combined_sigma:.12g}"
                    ),
                )
            )
        elif state is ToleranceDecisionEvaluationState.AT_BOUNDARY:
            any_boundary = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.STAT_ALLOCATION_AT_BOUNDARY,
                    severity=ToleranceDecisionSeverity.BOUNDARY,
                    scope="statistical_allocation",
                    detail=(
                        f"actual={recon.actual_combined_sigma:.12g} "
                        f"allocated={recon.allocated_combined_sigma:.12g}"
                    ),
                )
            )
        stat_recon_passed = (
            state is ToleranceDecisionEvaluationState.PASS or at_boundary
        )
        if not recon.is_complete:
            any_incomplete = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.INCOMPLETE_ALLOCATION,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="statistical_allocation",
                    detail=(
                        "missing contributors: "
                        f"{list(recon.missing_contributors)}"
                    ),
                )
            )
    elif statistical_allocation is not None and statistical_stack is None:
        any_incomplete = True
        dimensions.append(
            _build_dimension(
                "statistical_allocation",
                ToleranceDecisionEvaluationState.INCOMPLETE,
                None, None, None,
            )
        )
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.NO_STACK_PROVIDED,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope="statistical_allocation",
                detail=(
                    "statistical_allocation supplied but "
                    "statistical_stack is None"
                ),
            )
        )

    # Controlling contributors (always run when a stack is provided)
    wc_controlling_list: tuple[str, ...] = ()
    stat_controlling_list: tuple[str, ...] = ()
    if worst_case_stack is not None:
        wc_controlling_list = _wc_controlling(worst_case_stack)
    if statistical_stack is not None:
        stat_controlling_list = _stat_controlling(
            statistical_stack, k, correlations
        )

    # Covariance effect (informational)
    cov_effect = _classify_covariance_effect(
        correlations=correlations,
        stat_stack=statistical_stack,
        sigma_multiplier=k,
    )
    if cov_effect is ToleranceDecisionCovarianceEffect.INCREASES:
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.CORRELATION_INCREASES_SIGMA,
                severity=ToleranceDecisionSeverity.INFO,
                scope="statistical",
                detail="correlated sigma > independent sigma",
            )
        )
    elif cov_effect is ToleranceDecisionCovarianceEffect.DECREASES:
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.CORRELATION_DECREASES_SIGMA,
                severity=ToleranceDecisionSeverity.INFO,
                scope="statistical",
                detail="correlated sigma < independent sigma",
            )
        )
    elif cov_effect is ToleranceDecisionCovarianceEffect.NEUTRAL:
        reasons.append(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.CORRELATION_EFFECTIVELY_NEUTRAL,
                severity=ToleranceDecisionSeverity.INFO,
                scope="statistical",
                detail=(
                    "correlated sigma within equality tolerance of "
                    "independent"
                ),
            )
        )

    # WC / Statistical consistency (informational)
    if (
        worst_case_stack is not None
        and statistical_stack is not None
        and allowed_wc is not None
        and allowed_stat is not None
    ):
        wc_passes = wc_passed is True
        stat_passes = stat_passed is True
        if wc_passes and not stat_passes:
            any_failure = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_STAT_INCONSISTENT,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="consistency",
                    detail="worst-case passes, statistical fails",
                )
            )
        elif stat_passes and not wc_passes:
            any_failure = True
            reasons.append(
                ToleranceDecisionReason(
                    code=ToleranceDecisionReasonCode.WC_STAT_INCONSISTENT,
                    severity=ToleranceDecisionSeverity.FAILURE,
                    scope="consistency",
                    detail="worst-case fails, statistical passes",
                )
            )

    # Determine overall status
    if any_incomplete and not any_failure:
        overall = ToleranceDecisionStatus.INCOMPLETE
    elif any_failure:
        overall = ToleranceDecisionStatus.FAIL
    elif any_boundary:
        overall = ToleranceDecisionStatus.MARGINAL
    elif not dimensions:
        overall = ToleranceDecisionStatus.INCOMPLETE
    else:
        overall = ToleranceDecisionStatus.PASS

    sensitivity = ToleranceDecisionSensitivity(
        worst_case_controlling=wc_controlling_list,
        statistical_controlling=stat_controlling_list,
    )

    wc_utilization: float | None = None
    if wc_actual_span is not None and allowed_wc is not None and allowed_wc > 0.0:
        wc_utilization = wc_actual_span / allowed_wc

    stat_utilization: float | None = None
    if (
        stat_actual_sigma is not None
        and allowed_stat is not None
        and allowed_stat > 0.0
    ):
        stat_utilization = stat_actual_sigma / allowed_stat

    evidence = ToleranceDecisionEvidence(
        worst_case_actual_span=wc_actual_span,
        worst_case_allowed_span=allowed_wc,
        worst_case_margin=wc_margin_value,
        worst_case_utilization_fraction=wc_utilization,
        statistical_actual_combined_sigma=stat_actual_sigma,
        statistical_allowed_combined_sigma=allowed_stat,
        statistical_independent_combined_sigma=stat_independent_sigma,
        statistical_margin=stat_margin_value,
        statistical_utilization_fraction=stat_utilization,
        equality_tolerance=_EQUALITY_TOLERANCE,
    )

    # ============================================================
    # Stage 15L source snapshots (split A: WC + statistical + covariance)
    # ============================================================

    worst_case_contributor_snapshots: tuple[
        DecisionWorstCaseContributionObservation, ...
    ] = ()
    if worst_case_stack is not None:
        _wc_sensitivity = worst_case_sensitivity(worst_case_stack)
        worst_case_contributor_snapshots = tuple(
            DecisionWorstCaseContributionObservation(
                name=impact.name,
                span=impact.span,
                fraction=impact.fraction,
                percentage=impact.percentage,
                rank=rank,
            )
            for rank, impact in enumerate(_wc_sensitivity.impacts, start=1)
        )

    statistical_contributor_snapshots: tuple[
        DecisionStatisticalContributionObservation, ...
    ] = ()
    covariance_pair_snapshots: tuple[
        DecisionCovariancePairObservation, ...
    ] = ()
    if statistical_stack is not None:
        _stat_sensitivity = statistical_sensitivity(
            statistical_stack,
            sigma_multiplier=k,
            correlations=correlations,
        )
        statistical_contributor_snapshots = tuple(
            DecisionStatisticalContributionObservation(
                name=impact.name,
                sigma=impact.sigma,
                variance=impact.variance,
                fraction=impact.fraction,
                percentage=impact.percentage,
                rank=rank,
            )
            for rank, impact in enumerate(_stat_sensitivity.contributions, start=1)
        )
        covariance_pair_snapshots = tuple(
            DecisionCovariancePairObservation(
                first=pair.first,
                second=pair.second,
                rho=pair.rho,
                covariance_term=pair.covariance_term,
                fraction=pair.fraction,
                percentage=pair.percentage,
                rank=rank,
            )
            for rank, pair in enumerate(_stat_sensitivity.covariance_pairs, start=1)
        )

    worst_case_reconciliation_snapshots: tuple[
        DecisionReconciliationObservation, ...
    ] = ()
    allocation_missing_contributor_snapshots: tuple[
        DecisionAllocationMissingContributorObservation, ...
    ] = ()

    if worst_case_stack is not None and worst_case_allocation is not None:
        _wc_recon_snapshot = reconcile_allocation(
            worst_case_stack, worst_case_allocation,
            require_complete=require_complete,
        )
        _wc_validation_snapshot = validate_allocation(
            worst_case_stack, worst_case_allocation,
            require_complete=require_complete,
        )
        _ranked_wc_snapshot = sorted(
            _wc_recon_snapshot.contributor_compliances,
            key=lambda c: c.actual_span,
            reverse=True,
        )
        worst_case_reconciliation_snapshots = tuple(
            DecisionReconciliationObservation(
                contributor_id=cc.contributor_id,
                actual_span=cc.actual_span,
                allocated_span=cc.allocated_span,
                margin=cc.margin,
                utilization_fraction=cc.utilization_fraction,
                utilization_percentage=cc.utilization_percentage,
                status=cc.status.name,
                rank=rank,
            )
            for rank, cc in enumerate(_ranked_wc_snapshot, start=1)
        )
        allocation_missing_contributor_snapshots = tuple(
            DecisionAllocationMissingContributorObservation(
                contributor_id=cid, rank=rank,
            )
            for rank, cid in enumerate(
                _wc_validation_snapshot.missing_contributors, start=1,
            )
        )

    statistical_reconciliation_snapshots: tuple[
        DecisionStatisticalReconciliationObservation, ...
    ] = ()
    if statistical_stack is not None and statistical_allocation is not None:
        _stat_recon_snapshot = reconcile_statistical_allocation(
            statistical_stack,
            statistical_allocation,
            correlations=correlations,
            require_complete=require_complete,
        )
        _ranked_stat_snapshot = sorted(
            _stat_recon_snapshot.contributor_compliances,
            key=lambda c: c.actual_sigma,
            reverse=True,
        )
        statistical_reconciliation_snapshots = tuple(
            DecisionStatisticalReconciliationObservation(
                contributor_id=cc.contributor_id,
                actual_sigma=cc.actual_sigma,
                allocated_sigma=cc.allocated_sigma,
                margin=cc.sigma_margin,
                status=cc.status.name,
                rank=rank,
            )
            for rank, cc in enumerate(_ranked_stat_snapshot, start=1)
        )
        if _stat_recon_snapshot.missing_contributors:
            existing = {
                m.contributor_id for m in allocation_missing_contributor_snapshots
            }
            next_rank = len(allocation_missing_contributor_snapshots) + 1
            stat_only = tuple(
                DecisionAllocationMissingContributorObservation(
                    contributor_id=cid, rank=rank,
                )
                for rank, cid in enumerate(
                    _stat_recon_snapshot.missing_contributors, start=next_rank,
                )
                if cid not in existing
            )
            if stat_only:
                allocation_missing_contributor_snapshots = (
                    allocation_missing_contributor_snapshots + stat_only
                )

    return ToleranceDecisionResult(
        overall_status=overall,
        dimensions=tuple(dimensions),
        worst_case_passed=wc_passed,
        statistical_passed=stat_passed,
        worst_case_reconciliation_passed=wc_recon_passed,
        statistical_reconciliation_passed=stat_recon_passed,
        sensitivity=sensitivity,
        covariance_effect=cov_effect,
        evidence=evidence,
        reasons=tuple(reasons),
        is_complete=not any_incomplete,
        worst_case_contributor_snapshots=worst_case_contributor_snapshots,
        statistical_contributor_snapshots=statistical_contributor_snapshots,
        covariance_pair_snapshots=covariance_pair_snapshots,
        worst_case_reconciliation_snapshots=worst_case_reconciliation_snapshots,
        statistical_reconciliation_snapshots=statistical_reconciliation_snapshots,
        allocation_missing_contributor_snapshots=allocation_missing_contributor_snapshots,
    )
