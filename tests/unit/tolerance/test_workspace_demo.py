"""Headless tests for the customer demo dataset.

These tests verify the full analysis chain from
examples/tolerance_workspace_demo.py without launching a display.
All assertions are against deterministic engine outputs.
"""

from __future__ import annotations

import pytest

from origlyph.tolerance import (
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceSpecification,
    WorstCaseSensitivityResult,
)

# ---------------------------------------------------------------------------
# Shared demo controller fixture
# ---------------------------------------------------------------------------


def _demo_controller() -> ToleranceWorkspaceController:
    controller = ToleranceWorkspaceController.empty(
        chain_name="bracket-mounting-assembly",
        analysis_mode="worst_case",
    )
    controller.add_contributor(
        identifier="bracket_depth",
        name="Bracket depth",
        nominal=25.0,
        tolerance=0.10,
        direction="forward",
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="pin_length",
        name="Pin length",
        nominal=5.0,
        tolerance=0.08,
        direction="forward",
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="shim_thickness",
        name="Shim thickness",
        nominal=2.5,
        tolerance=0.05,
        direction="inverse",
        tolerance_model="symmetric",
    )
    controller.set_specification(
        WorkspaceSpecification(
            allowed_worst_case_span=0.40,
            allowed_combined_sigma=0.15,
        )
    )
    controller.set_allocation_plan(
        WorkspaceAllocationPlan(
            allowed_budget=0.30,
            entries=(
                WorkspaceAllocationEntry(
                    contributor_id="bracket_depth", allocated_span=0.12
                ),
                WorkspaceAllocationEntry(
                    contributor_id="pin_length", allocated_span=0.10
                ),
                WorkspaceAllocationEntry(
                    contributor_id="shim_thickness", allocated_span=0.08
                ),
            ),
        )
    )
    return controller


# ---------------------------------------------------------------------------
# Section A — Controller setup
# ---------------------------------------------------------------------------


def test_demo_chain_has_three_contributors() -> None:
    c = _demo_controller()
    assert len(c.contributors) == 3


def test_demo_contributor_identifiers() -> None:
    c = _demo_controller()
    ids = [ct.identifier for ct in c.contributors]
    assert "bracket_depth" in ids
    assert "pin_length" in ids
    assert "shim_thickness" in ids


def test_demo_specification_is_set() -> None:
    c = _demo_controller()
    spec = c.specification
    assert spec is not None
    assert spec.allowed_worst_case_span == pytest.approx(0.40)
    assert spec.allowed_combined_sigma == pytest.approx(0.15)


def test_demo_allocation_plan_is_set() -> None:
    c = _demo_controller()
    plan = c.allocation_plan
    assert plan is not None
    assert plan.allowed_budget == pytest.approx(0.30)
    assert len(plan.entries) == 3


# ---------------------------------------------------------------------------
# Section B — Worst-case analysis
# ---------------------------------------------------------------------------


def test_demo_worst_case_total_span() -> None:
    c = _demo_controller()
    result = c.run_analysis()
    total_span = result.summary_values["total_span"]
    # 2*0.10 + 2*0.08 + 2*0.05 = 0.20 + 0.16 + 0.10 = 0.46
    assert total_span == pytest.approx(0.46, rel=1e-9)


def test_demo_worst_case_fails_specification() -> None:
    c = _demo_controller()
    c.run_analysis()
    decision = c.evaluate_decision()
    assert decision.worst_case_passed is False


# ---------------------------------------------------------------------------
# Section C — RSS statistical analysis
# ---------------------------------------------------------------------------


def test_demo_rss_combined_sigma_is_positive() -> None:
    c = _demo_controller()
    c.set_analysis_mode("rss_statistical")
    result = c.run_analysis()
    sigma = result.summary_values["combined_sigma"]
    assert sigma > 0.0


def test_demo_rss_passes_specification() -> None:
    c = _demo_controller()
    c.set_analysis_mode("rss_statistical")
    c.run_analysis()
    decision = c.evaluate_decision()
    assert decision.statistical_passed is True


# ---------------------------------------------------------------------------
# Section D — Sensitivity
# ---------------------------------------------------------------------------


def test_demo_sensitivity_has_three_impacts() -> None:
    c = _demo_controller()
    c.run_analysis()
    sens = c.run_sensitivity()
    assert isinstance(sens, WorstCaseSensitivityResult)
    assert len(sens.impacts) == 3


def test_demo_sensitivity_percentages_sum_to_100() -> None:
    c = _demo_controller()
    c.run_analysis()
    sens = c.run_sensitivity()
    assert isinstance(sens, WorstCaseSensitivityResult)
    total_pct = sum(impact.percentage for impact in sens.impacts)
    assert total_pct == pytest.approx(100.0, abs=1e-6)


def test_demo_bracket_depth_has_highest_sensitivity() -> None:
    c = _demo_controller()
    c.run_analysis()
    sens = c.run_sensitivity()
    assert isinstance(sens, WorstCaseSensitivityResult)
    impacts_by_name = {imp.name: imp for imp in sens.impacts}
    assert (
        impacts_by_name["bracket_depth"].percentage
        > impacts_by_name["pin_length"].percentage
    )
    assert (
        impacts_by_name["pin_length"].percentage
        > impacts_by_name["shim_thickness"].percentage
    )


# ---------------------------------------------------------------------------
# Section E — Budget
# ---------------------------------------------------------------------------


def test_demo_budget_actual_span_matches_worst_case() -> None:
    c = _demo_controller()
    c.run_analysis()
    budget = c.run_budget()
    assert budget.actual_span == pytest.approx(0.46, rel=1e-9)


def test_demo_budget_over_specification() -> None:
    c = _demo_controller()
    c.run_analysis()
    budget = c.run_budget()
    from origlyph.tolerance.models import BudgetStatus
    assert budget.status == BudgetStatus.OVER_BUDGET


def test_demo_budget_has_three_contributions() -> None:
    c = _demo_controller()
    c.run_analysis()
    budget = c.run_budget()
    assert len(budget.contributions) == 3


# ---------------------------------------------------------------------------
# Section F — Allocation validation
# ---------------------------------------------------------------------------


def test_demo_allocation_validation_passes() -> None:
    c = _demo_controller()
    result = c.validate_allocation()
    from origlyph.tolerance.models import AllocationStatus
    assert result.status == AllocationStatus.FULLY_ALLOCATED


def test_demo_allocation_budget_matches_plan() -> None:
    c = _demo_controller()
    result = c.validate_allocation()
    assert result.allowed_budget == pytest.approx(0.30)


def test_demo_allocation_total_matches_sum_of_entries() -> None:
    c = _demo_controller()
    result = c.validate_allocation()
    # 0.12 + 0.10 + 0.08 = 0.30
    assert result.allocated_total == pytest.approx(0.30, rel=1e-9)


def test_demo_allocation_remaining_is_zero() -> None:
    c = _demo_controller()
    result = c.validate_allocation()
    assert result.remaining_unallocated == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Section G — Configuration fingerprint stability
# ---------------------------------------------------------------------------


def test_demo_fingerprint_is_deterministic() -> None:
    c1 = _demo_controller()
    c2 = _demo_controller()
    assert c1.configuration_fingerprint() == c2.configuration_fingerprint()


def test_demo_fingerprint_changes_after_plan_change() -> None:
    c = _demo_controller()
    fp1 = c.configuration_fingerprint()
    new_plan = WorkspaceAllocationPlan(
        allowed_budget=0.35,
        entries=(
            WorkspaceAllocationEntry(
                contributor_id="bracket_depth", allocated_span=0.14
            ),
            WorkspaceAllocationEntry(
                contributor_id="pin_length", allocated_span=0.12
            ),
            WorkspaceAllocationEntry(
                contributor_id="shim_thickness", allocated_span=0.09
            ),
        ),
    )
    c.set_allocation_plan(new_plan)
    assert c.configuration_fingerprint() != fp1
