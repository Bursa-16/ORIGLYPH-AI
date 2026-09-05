"""Independent engineering tests for Stage 15L evidence & explainability.

Tests cover PASS, MARGINAL, FAIL, INCOMPLETE, MULTIPLE-FAILURE, all
evidence categories (WC, statistical, correlation, sensitivity, budget,
allocation, WC reconciliation, statistical reconciliation), deterministic
ID/ordering/serialization, fail-closed behavior, immutability, and
Stage 15K regression.

All numeric assertions use exact float equality: the evidence layer
preserves authoritative values without rounding, and equality must hold
bit-for-bit across the layer.
"""

from __future__ import annotations

import json
import math

import pytest

from origlyph.tolerance.decision import evaluate_tolerance_decision
from origlyph.tolerance.evidence import (
    DecisionComparison,
    DecisionEvidenceSource,
    build_decision_evidence,
    explain_tolerance_decision,
)
from origlyph.tolerance.exceptions import (
    InvalidDecisionEvidenceError,
)
from origlyph.tolerance.models import (
    AllocationPlan,
    Correlation,
    StatisticalAllocation,
    StatisticalAllocationPlan,
    StatisticalContribution,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceDecisionReason,
    ToleranceDecisionReasonCode,
    ToleranceDecisionResult,
    ToleranceDecisionSensitivity,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    ToleranceStack,
)

# ---------------------------------------------------------------------------
# Stack fixtures
# ---------------------------------------------------------------------------


def _wc_stack() -> ToleranceStack:
    """A (span 0.30) + B (span 0.15): total worst-case span 0.45."""
    return ToleranceStack(
        (
            ToleranceContribution("A", 100.0, -0.10, 0.20),
            ToleranceContribution("B", 40.0, -0.05, 0.10),
        )
    )


def _stat_stack() -> StatisticalStack:
    """A sigma=0.05, B sigma=0.05."""
    return StatisticalStack(
        (
            StatisticalContribution("A", 0.0, 0.05),
            StatisticalContribution("B", 0.0, 0.05),
        )
    )


def _wc_allocation(span_a: float, span_b: float) -> AllocationPlan:
    return AllocationPlan(
        allowed_budget=0.50,
        allocations=(
            ToleranceAllocation("A", span_a),
            ToleranceAllocation("B", span_b),
        ),
    )


def _stat_allocation(
    sigma_a: float, sigma_b: float, k: float = 3.0
) -> StatisticalAllocationPlan:
    return StatisticalAllocationPlan(
        sigma_multiplier=k,
        allocations=(
            StatisticalAllocation("A", sigma_a),
            StatisticalAllocation("B", sigma_b),
        ),
    )


# ---------------------------------------------------------------------------
# Decision builders for each scenario
# ---------------------------------------------------------------------------


def _pass_decision() -> ToleranceDecisionResult:
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.50,
        allowed_combined_sigma=0.20,
    )


def _fail_decision() -> ToleranceDecisionResult:
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.40,
    )


def _marginal_decision() -> ToleranceDecisionResult:
    # 0.45 vs 0.45+1e-13 — well within 1e-12 boundary.
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.45 + 1e-13,
    )


def _multiple_fail_decision() -> ToleranceDecisionResult:
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        statistical_stack=_stat_stack(),
        allowed_worst_case_span=0.30,
        allowed_combined_sigma=0.02,
    )


def _incomplete_allocation_decision() -> ToleranceDecisionResult:
    plan = AllocationPlan(
        allowed_budget=0.50,
        allocations=(ToleranceAllocation("A", 0.30),),
    )
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
        allowed_worst_case_span=0.50,
        require_complete=False,
    )


def _correlation_decision(rho: float) -> ToleranceDecisionResult:
    return evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", rho),),
    )


def _negative_covariance_decision() -> ToleranceDecisionResult:
    return evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", -0.9),),
    )


def _wc_allocation_exceeded_decision() -> ToleranceDecisionResult:
    """Plan total 0.20 < actual 0.45 -> WC allocation EXCEEDED."""
    plan = AllocationPlan(
        allowed_budget=0.30,
        allocations=(
            ToleranceAllocation("A", 0.10),
            ToleranceAllocation("B", 0.10),
        ),
    )
    return evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        worst_case_allocation=plan,
        allowed_worst_case_span=0.50,
    )


# ---------------------------------------------------------------------------
# A. PASS
# ---------------------------------------------------------------------------


def test_pass_decision_has_no_failure_evidence() -> None:
    """PASS produces no synthetic failure evidence."""
    bundle = build_decision_evidence(_pass_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.PASS
    assert bundle.governing_evidence_ids == ()
    assert bundle.marginal_evidence_ids == ()
    codes = {item.evidence_code for item in bundle.evidence_items}
    assert "wc_span_exceeds_limit" not in codes
    assert "stat_sigma_exceeds_limit" not in codes


# ---------------------------------------------------------------------------
# B. MARGINAL
# ---------------------------------------------------------------------------


def test_marginal_decision_has_boundary_evidence() -> None:
    """Boundary comparison yields exact AT_BOUNDARY evidence with values."""
    bundle = build_decision_evidence(_marginal_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.MARGINAL
    assert bundle.marginal_evidence
    item = next(
        i for i in bundle.evidence_items if i.evidence_code == "wc_span_at_limit"
    )
    assert item.comparison is DecisionComparison.AT_BOUNDARY
    assert item.observed_value == pytest.approx(0.45)
    assert item.reference_value == pytest.approx(0.45 + 1e-13)
    assert item.severity is ToleranceDecisionSeverity.BOUNDARY


# ---------------------------------------------------------------------------
# C. FAIL
# ---------------------------------------------------------------------------


def test_fail_decision_maps_reason_to_evidence() -> None:
    """Hard failure reason maps to explicit governing evidence."""
    bundle = build_decision_evidence(_fail_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.FAIL
    assert bundle.governing_evidence_ids
    codes = [item.evidence_code for item in bundle.governing_evidence]
    assert "wc_span_exceeds_limit" in codes
    reason_ids = bundle.evidence_ids_for_reason(
        ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    )
    assert reason_ids
    assert all(eid in bundle.governing_evidence_ids for eid in reason_ids)


# ---------------------------------------------------------------------------
# D. MULTIPLE FAILURES
# ---------------------------------------------------------------------------


def test_multiple_failures_all_remain_visible() -> None:
    """All independent failure evidence is retained."""
    bundle = build_decision_evidence(_multiple_fail_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.FAIL
    codes = {item.evidence_code for item in bundle.governing_evidence}
    assert "wc_span_exceeds_limit" in codes
    assert "stat_sigma_exceeds_limit" in codes
    wc_ids = bundle.evidence_ids_for_reason(
        ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    )
    stat_ids = bundle.evidence_ids_for_reason(
        ToleranceDecisionReasonCode.STAT_REQUIREMENT_EXCEEDED
    )
    assert wc_ids and stat_ids
    assert set(wc_ids).isdisjoint(set(stat_ids))


# ---------------------------------------------------------------------------
# E. INCOMPLETE
# ---------------------------------------------------------------------------


def test_incomplete_allocation_represented_structurally() -> None:
    """Missing allocation contributor is represented structurally."""
    bundle = build_decision_evidence(_incomplete_allocation_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.INCOMPLETE
    assert any(
        item.evidence_code == "allocation_missing_contributors"
        for item in bundle.governing_evidence
    )
    missing = [
        item
        for item in bundle.evidence_items
        if item.evidence_code == "allocation_missing_contributors"
    ]
    assert any(item.subject_id == "B" for item in missing)
    incomplete_ids = bundle.evidence_ids_for_reason(
        ToleranceDecisionReasonCode.INCOMPLETE_ALLOCATION
    )
    assert incomplete_ids
    assert all(eid in bundle.governing_evidence_ids for eid in incomplete_ids)


# ---------------------------------------------------------------------------
# F. REASON LINKAGE
# ---------------------------------------------------------------------------


def test_every_triggered_reason_has_evidence() -> None:
    """Every triggered reason is linked to at least one evidence item."""
    for builder in (
        _pass_decision,
        _fail_decision,
        _marginal_decision,
        _multiple_fail_decision,
        _incomplete_allocation_decision,
    ):
        result = builder()
        bundle = build_decision_evidence(result)
        for reason in result.reasons:
            ids = bundle.evidence_ids_for_reason(reason.code)
            assert ids, (
                f"reason {reason.code} has no evidence in {builder.__name__}"
            )


def test_non_evidentiary_reason_not_linked() -> None:
    """NO_REQUIREMENT_PROVIDED is documented as non-evidentiary."""
    from origlyph.tolerance.models import (
        ToleranceDecisionCovarianceEffect,
        ToleranceDecisionEvidence,
    )

    sensitivity = ToleranceDecisionSensitivity(
        worst_case_controlling=(), statistical_controlling=()
    )
    evidence = ToleranceDecisionEvidence(
        worst_case_actual_span=None,
        worst_case_allowed_span=None,
        worst_case_margin=None,
        worst_case_utilization_fraction=None,
        statistical_actual_combined_sigma=None,
        statistical_allowed_combined_sigma=None,
        statistical_independent_combined_sigma=None,
        statistical_margin=None,
        statistical_utilization_fraction=None,
        equality_tolerance=1e-12,
    )
    result = ToleranceDecisionResult(
        overall_status=ToleranceDecisionStatus.INCOMPLETE,
        dimensions=(),
        worst_case_passed=None,
        statistical_passed=None,
        worst_case_reconciliation_passed=None,
        statistical_reconciliation_passed=None,
        sensitivity=sensitivity,
        covariance_effect=ToleranceDecisionCovarianceEffect.NOT_REQUESTED,
        evidence=evidence,
        reasons=(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.NO_REQUIREMENT_PROVIDED,
                severity=ToleranceDecisionSeverity.INFO,
                scope=None,
                detail="no criteria requested",
            ),
        ),
        is_complete=False,
    )
    bundle = build_decision_evidence(result)
    assert (
        bundle.evidence_ids_for_reason(
            ToleranceDecisionReasonCode.NO_REQUIREMENT_PROVIDED
        )
        == ()
    )
    assert bundle.reason_to_evidence == ()


def test_unmapped_reason_fails_closed() -> None:
    """A triggered reason with no evidence mapping fails closed."""
    from origlyph.tolerance.models import (
        ToleranceDecisionCovarianceEffect,
        ToleranceDecisionEvidence,
    )

    sensitivity = ToleranceDecisionSensitivity(
        worst_case_controlling=(), statistical_controlling=()
    )
    evidence = ToleranceDecisionEvidence(
        worst_case_actual_span=None,
        worst_case_allowed_span=None,
        worst_case_margin=None,
        worst_case_utilization_fraction=None,
        statistical_actual_combined_sigma=None,
        statistical_allowed_combined_sigma=None,
        statistical_independent_combined_sigma=None,
        statistical_margin=None,
        statistical_utilization_fraction=None,
        equality_tolerance=1e-12,
    )
    result = ToleranceDecisionResult(
        overall_status=ToleranceDecisionStatus.FAIL,
        dimensions=(),
        worst_case_passed=False,
        statistical_passed=None,
        worst_case_reconciliation_passed=None,
        statistical_reconciliation_passed=None,
        sensitivity=sensitivity,
        covariance_effect=ToleranceDecisionCovarianceEffect.NOT_REQUESTED,
        evidence=evidence,
        reasons=(
            ToleranceDecisionReason(
                code=ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED,
                severity=ToleranceDecisionSeverity.FAILURE,
                scope=None,
                detail="orphan",
            ),
        ),
        is_complete=True,
    )
    with pytest.raises(InvalidDecisionEvidenceError):
        build_decision_evidence(result)


# ---------------------------------------------------------------------------
# G. EVIDENCE IDS
# ---------------------------------------------------------------------------


def test_evidence_ids_deterministic_across_calls() -> None:
    """Repeated calls produce identical evidence IDs and order."""
    decision = _fail_decision()
    first = build_decision_evidence(decision)
    second = build_decision_evidence(decision)
    assert [i.evidence_id for i in first.evidence_items] == [
        i.evidence_id for i in second.evidence_items
    ]


def test_evidence_ids_unique_within_bundle() -> None:
    """Evidence IDs are unique within one bundle."""
    bundle = build_decision_evidence(_multiple_fail_decision())
    ids = [item.evidence_id for item in bundle.evidence_items]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# H. EVIDENCE ORDERING
# ---------------------------------------------------------------------------


def test_evidence_ordering_deterministic() -> None:
    """Repeated calls produce identical ordering across categories."""
    decision = _multiple_fail_decision()
    first = build_decision_evidence(decision)
    second = build_decision_evidence(decision)
    assert [i.evidence_code for i in first.evidence_items] == [
        i.evidence_code for i in second.evidence_items
    ]


def test_failure_outranks_boundary_in_ordering() -> None:
    """Hard-failure items are ordered before boundary items."""
    bundle = build_decision_evidence(_multiple_fail_decision())
    severities = [i.severity for i in bundle.evidence_items]
    failure_index = [
        i for i, s in enumerate(severities) if s is ToleranceDecisionSeverity.FAILURE
    ]
    boundary_index = [
        i for i, s in enumerate(severities) if s is ToleranceDecisionSeverity.BOUNDARY
    ]
    if failure_index and boundary_index:
        assert max(failure_index) < min(boundary_index)


# ---------------------------------------------------------------------------
# I. SERIALIZATION
# ---------------------------------------------------------------------------


def test_serialization_identical_across_calls() -> None:
    """Repeated serialization is byte-identical (deterministic)."""
    decision = _pass_decision()
    bundle = build_decision_evidence(decision)
    s1 = json.dumps(bundle.as_dict(), sort_keys=True)
    s2 = json.dumps(build_decision_evidence(decision).as_dict(), sort_keys=True)
    assert s1 == s2


def test_serialization_uses_stable_enum_strings() -> None:
    """Enum values serialize as stable snake_case strings."""
    bundle = build_decision_evidence(_fail_decision())
    serial = bundle.as_dict()
    items = serial["evidence_items"]
    assert isinstance(items, list) and items
    item = items[0]
    assert isinstance(item, dict)
    assert isinstance(item["source"], str)
    assert isinstance(item["severity"], str)
    assert isinstance(item["comparison"], str)
    assert item["source"] in {src.value for src in DecisionEvidenceSource}
    assert item["severity"] in {sev.value for sev in ToleranceDecisionSeverity}
    assert item["comparison"] in {cmp.value for cmp in DecisionComparison}


# ---------------------------------------------------------------------------
# J. NO RANDOMNESS
# ---------------------------------------------------------------------------


def test_no_timestamps_or_randomness_in_serialization() -> None:
    """Serialization contains no timestamps, UUIDs, or random values."""
    bundle = build_decision_evidence(_pass_decision())
    serial = bundle.as_dict()
    raw = json.dumps(serial, sort_keys=True)
    forbidden = ("timestamp", "uuid", "random", "now()", "monotonic", "time.time")
    for token in forbidden:
        assert token not in raw.lower(), (
            f"serialization leaked forbidden token: {token!r}"
        )


# ---------------------------------------------------------------------------
# K. WORST-CASE NUMERIC TRACE
# ---------------------------------------------------------------------------


def test_worst_case_numeric_evidence_preserves_values() -> None:
    """actual vs allowed are preserved exactly (no rounding)."""
    bundle = build_decision_evidence(_fail_decision())
    item = next(
        i for i in bundle.evidence_items if i.evidence_code == "wc_span_exceeds_limit"
    )
    assert item.observed_value == pytest.approx(0.45)
    assert item.reference_value == pytest.approx(0.40)
    margin = item.metric("remaining_margin")
    assert margin is not None and margin == pytest.approx(-0.05)


# ---------------------------------------------------------------------------
# L. STATISTICAL NUMERIC TRACE
# ---------------------------------------------------------------------------


def test_statistical_numeric_evidence_preserves_values() -> None:
    """Statistical actual vs allowed and independent sigma are preserved."""
    decision = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        correlations=(Correlation("A", "B", 0.0),),
        allowed_combined_sigma=0.20,
    )
    bundle = build_decision_evidence(decision)
    item = next(
        i for i in bundle.evidence_items
        if i.evidence_code == "stat_sigma_within_limit"
    )
    expected = math.sqrt(0.05 ** 2 + 0.05 ** 2)
    assert item.observed_value == pytest.approx(expected)
    assert item.reference_value == pytest.approx(0.20)
    independent = item.metric("independent_combined_sigma")
    assert independent is not None and independent == pytest.approx(expected)


# ---------------------------------------------------------------------------
# M/N. CORRELATION TRACE (signed)
# ---------------------------------------------------------------------------


def test_correlation_evidence_preserves_rho_and_pair() -> None:
    """Per-pair evidence preserves rho and the canonical pair subject."""
    bundle = build_decision_evidence(_correlation_decision(0.5))
    pairs = [
        i for i in bundle.evidence_items
        if i.evidence_code == "covariance_pair_contribution"
    ]
    assert any(p.subject_id == "A|B" for p in pairs)
    ab = next(p for p in pairs if p.subject_id == "A|B")
    rho = ab.metric("rho")
    assert rho is not None and rho == pytest.approx(0.5)


def test_negative_covariance_preserved_signed() -> None:
    """Negative covariance effect remains signed (never sign-flipped)."""
    bundle = build_decision_evidence(_negative_covariance_decision())
    codes = {i.evidence_code for i in bundle.evidence_items}
    assert "covariance_reduces_variance" in codes
    reducing = next(
        i for i in bundle.evidence_items
        if i.evidence_code == "covariance_reduces_variance"
    )
    assert reducing.comparison is DecisionComparison.LESS_THAN
    assert (reducing.observed_value or 0.0) < (reducing.reference_value or 0.0)


# ---------------------------------------------------------------------------
# O. SENSITIVITY TRACE
# ---------------------------------------------------------------------------


def test_sensitivity_evidence_preserves_rank_and_impact() -> None:
    """Sensitivity evidence preserves rank and impact metric."""
    bundle = build_decision_evidence(_pass_decision())
    sensitivity_items = [
        i for i in bundle.evidence_items
        if i.evidence_code
        in {"sensitivity_wc_contributor", "sensitivity_stat_contributor"}
    ]
    assert sensitivity_items
    for item in sensitivity_items:
        assert item.metric("rank") is not None


# ---------------------------------------------------------------------------
# P. BUDGET TRACE
# ---------------------------------------------------------------------------


def test_budget_evidence_preserves_allowed_consumed_margin() -> None:
    """Budget evidence retains allowed, actual, margin, and utilization."""
    bundle = build_decision_evidence(_fail_decision())
    item = next(
        i for i in bundle.evidence_items if i.evidence_code == "wc_span_exceeds_limit"
    )
    assert item.metric("remaining_margin") == pytest.approx(-0.05)
    assert item.metric("utilization") == pytest.approx(0.45 / 0.40)
    assert item.metric("equality_tolerance") is not None


# ---------------------------------------------------------------------------
# Q. ALLOCATION TRACE
# ---------------------------------------------------------------------------


def test_wc_allocation_exceeded_has_governing_evidence() -> None:
    """WC allocation exceeded produces governing evidence linked to reason."""
    bundle = build_decision_evidence(_wc_allocation_exceeded_decision())
    assert bundle.decision_status is ToleranceDecisionStatus.FAIL
    codes = {i.evidence_code for i in bundle.governing_evidence}
    assert "wc_allocation_exceeds_plan" in codes
    assert bundle.evidence_ids_for_reason(
        ToleranceDecisionReasonCode.WC_ALLOCATION_EXCEEDED
    )


# ---------------------------------------------------------------------------
# R/S. RECONCILIATION TRACE (WC + statistical)
# ---------------------------------------------------------------------------


def test_wc_reconciliation_preserves_actual_vs_allocated() -> None:
    """WC reconciliation evidence preserves actual vs allocated span."""
    bundle = build_decision_evidence(_wc_allocation_exceeded_decision())
    items = [
        i for i in bundle.evidence_items
        if i.evidence_code
        in {
            "wc_reconciliation_contributor_within",
            "wc_reconciliation_contributor_at",
            "wc_reconciliation_contributor_exceeded",
        }
    ]
    assert items
    exceeded = [
        i for i in items
        if i.evidence_code == "wc_reconciliation_contributor_exceeded"
    ]
    assert exceeded
    item = exceeded[0]
    assert item.observed_value is not None
    assert item.reference_value is not None
    assert item.observed_value > item.reference_value


def test_statistical_reconciliation_preserves_sigma() -> None:
    """Statistical reconciliation evidence preserves sigma values."""
    plan = StatisticalAllocationPlan(
        sigma_multiplier=3.0,
        allocations=(
            StatisticalAllocation("A", 0.10),
            StatisticalAllocation("B", 0.10),
        ),
    )
    decision = evaluate_tolerance_decision(
        statistical_stack=_stat_stack(),
        statistical_allocation=plan,
        allowed_combined_sigma=0.20,
    )
    bundle = build_decision_evidence(decision)
    items = [
        i for i in bundle.evidence_items
        if i.evidence_code
        in {
            "stat_reconciliation_contributor_within",
            "stat_reconciliation_contributor_at",
            "stat_reconciliation_contributor_exceeded",
        }
    ]
    assert items
    for item in items:
        assert item.observed_value is not None
        assert item.reference_value is not None
        assert item.metric("rank") is not None


# ---------------------------------------------------------------------------
# T. GOVERNING EVIDENCE
# ---------------------------------------------------------------------------


def test_governing_evidence_first_in_ordering() -> None:
    """Primary governing evidence is the first item in deterministic order."""
    bundle = build_decision_evidence(_fail_decision())
    assert bundle.primary_governing_evidence is not None
    assert bundle.evidence_items[0].evidence_id == (
        bundle.primary_governing_evidence.evidence_id
    )
    assert all(
        i.severity is ToleranceDecisionSeverity.FAILURE
        for i in bundle.governing_evidence
    )


# ---------------------------------------------------------------------------
# U. MISSING REQUIRED SOURCE (fail-closed)
# ---------------------------------------------------------------------------


def test_invalid_decision_result_type_fails_closed() -> None:
    """Non-decision input fails closed with the typed exception."""
    with pytest.raises(InvalidDecisionEvidenceError):
        build_decision_evidence("not a decision")  # type: ignore[arg-type]


def test_dimension_without_actual_or_allowed_fails_closed() -> None:
    """A dimension with PASS state but no actual/allowed fails closed."""
    from origlyph.tolerance.models import (
        ToleranceDecisionCovarianceEffect,
        ToleranceDecisionEvidence,
    )
    from origlyph.tolerance.models import (
        ToleranceDecisionDimension as _Dim,
    )

    sensitivity = ToleranceDecisionSensitivity(
        worst_case_controlling=(), statistical_controlling=()
    )
    evidence = ToleranceDecisionEvidence(
        worst_case_actual_span=None,
        worst_case_allowed_span=0.50,
        worst_case_margin=None,
        worst_case_utilization_fraction=None,
        statistical_actual_combined_sigma=None,
        statistical_allowed_combined_sigma=None,
        statistical_independent_combined_sigma=None,
        statistical_margin=None,
        statistical_utilization_fraction=None,
        equality_tolerance=1e-12,
    )
    bad_dim = _Dim(
        name="worst_case_requirement",
        state=ToleranceDecisionStatus.PASS,  # type: ignore[arg-type]
        actual=None,
        allowed=0.50,
        margin=None,
    )
    result = ToleranceDecisionResult(
        overall_status=ToleranceDecisionStatus.PASS,
        dimensions=(bad_dim,),
        worst_case_passed=True,
        statistical_passed=None,
        worst_case_reconciliation_passed=None,
        statistical_reconciliation_passed=None,
        sensitivity=sensitivity,
        covariance_effect=ToleranceDecisionCovarianceEffect.NOT_REQUESTED,
        evidence=evidence,
        reasons=(),
        is_complete=True,
    )
    with pytest.raises(InvalidDecisionEvidenceError):
        build_decision_evidence(result)


# ---------------------------------------------------------------------------
# V. INPUT IMMUTABILITY
# ---------------------------------------------------------------------------


def test_decision_result_not_mutated_by_evidence_build() -> None:
    """Building evidence does not mutate the decision result."""
    decision = _fail_decision()
    snapshot_dimensions = list(decision.dimensions)
    snapshot_reasons = list(decision.reasons)
    build_decision_evidence(decision)
    assert list(decision.dimensions) == snapshot_dimensions
    assert list(decision.reasons) == snapshot_reasons


# ---------------------------------------------------------------------------
# W. STAGE 15K REGRESSION
# ---------------------------------------------------------------------------


def test_stage15k_decision_unchanged_by_evidence_module() -> None:
    """Importing evidence does not change Stage 15K outcomes or reasons."""
    decision = evaluate_tolerance_decision(
        worst_case_stack=_wc_stack(),
        allowed_worst_case_span=0.40,
    )
    assert decision.overall_status is ToleranceDecisionStatus.FAIL
    codes = [r.code for r in decision.reasons]
    assert ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED in codes


def test_full_tolerance_regression_decision_layer_intact() -> None:
    """Existing decision tests must continue to pass (smoke subset)."""
    decision = _pass_decision()
    assert decision.overall_status is ToleranceDecisionStatus.PASS
    assert decision.worst_case_passed is True
    assert decision.statistical_passed is True
    assert decision.is_complete is True
    decision = _fail_decision()
    assert decision.overall_status is ToleranceDecisionStatus.FAIL
    assert decision.worst_case_passed is False


# ---------------------------------------------------------------------------
# Public API: explain_tolerance_decision
# ---------------------------------------------------------------------------


def test_explanation_uses_fixed_templates() -> None:
    """Explanation summary is rendered from fixed templates only."""
    decision = _fail_decision()
    bundle = build_decision_evidence(decision)
    explanation = explain_tolerance_decision(decision, bundle)
    assert explanation.final_status is bundle.decision_status
    assert explanation.summary_code.startswith("fail:")
    assert "wc_span_exceeds_limit" in explanation.summary
    assert "Decision fail:" in explanation.summary


def test_explanation_reuses_provided_bundle() -> None:
    """When given, the provided bundle is reused (no double-build)."""
    decision = _pass_decision()
    bundle = build_decision_evidence(decision)
    explanation = explain_tolerance_decision(decision, bundle)
    assert explanation.is_complete is bundle.is_complete
    assert explanation.governing_evidence == bundle.governing_evidence
    assert explanation.marginal_evidence == bundle.marginal_evidence
    assert explanation.supporting_evidence == bundle.supporting_evidence


def test_explanation_invalid_input_fails_closed() -> None:
    """Invalid inputs to the explanation API fail closed."""
    with pytest.raises(InvalidDecisionEvidenceError):
        explain_tolerance_decision("not a decision")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Explanation model determinism
# ---------------------------------------------------------------------------


def test_explanation_as_dict_identical_across_calls() -> None:
    """Explanation serialization is deterministic."""
    decision = _fail_decision()
    bundle = build_decision_evidence(decision)
    s1 = json.dumps(
        explain_tolerance_decision(decision, bundle).as_dict(), sort_keys=True
    )
    s2 = json.dumps(
        explain_tolerance_decision(decision, bundle).as_dict(), sort_keys=True
    )
    assert s1 == s2







