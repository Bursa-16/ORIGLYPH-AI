from __future__ import annotations

import math

import pytest

from origlyph.tolerance import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorstCaseResult,
    workspace_state_from_snapshot,
)
from origlyph.tolerance import workspace_controller as workspace_controller_module


def _controller(
    mode: AnalysisMode = AnalysisMode.WORST_CASE,
) -> ToleranceWorkspaceController:
    controller = ToleranceWorkspaceController.empty(
        chain_name="main-chain", analysis_mode=mode
    )
    controller.add_contributor(
        identifier="a",
        name="Face A",
        nominal="10.0",
        tolerance="0.1",
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="b",
        name="Face B",
        nominal=4.0,
        tolerance=0.2,
        direction="inverse",
        tolerance_model="symmetric",
    )
    return controller


def test_workspace_starts_empty_and_requires_explicit_contributors() -> None:
    controller = ToleranceWorkspaceController.empty(
        chain_name="main-chain", analysis_mode="worst_case"
    )

    assert controller.contributors == ()
    assert controller.snapshot()["contributors"] == []
    with pytest.raises(InvalidToleranceWorkspaceError, match="at least one"):
        controller.run_analysis()


def test_worst_case_controller_delegates_to_engine_and_maps_summary(
    monkeypatch,
) -> None:
    controller = _controller()
    calls = 0
    original = workspace_controller_module.worst_case

    def spy(stack):
        nonlocal calls
        calls += 1
        return original(stack)

    monkeypatch.setattr(workspace_controller_module, "worst_case", spy)

    result = controller.run_analysis()

    assert calls == 1
    assert isinstance(result.backend_result, WorstCaseResult)
    assert result.summary_values == {
        "nominal": 6.0,
        "minimum": pytest.approx(5.7),
        "maximum": pytest.approx(6.3),
        "lower_deviation": pytest.approx(-0.3),
        "upper_deviation": pytest.approx(0.3),
        "total_span": pytest.approx(0.6),
    }
    assert controller.result_view()["result_id"] == result.result_id


def test_rss_statistical_controller_delegates_to_engine_and_maps_summary(
    monkeypatch,
) -> None:
    controller = _controller(AnalysisMode.RSS_STATISTICAL)
    calls = 0
    original = workspace_controller_module.statistical

    def spy(stack, *, sigma_multiplier, correlations):
        nonlocal calls
        calls += 1
        return original(
            stack, sigma_multiplier=sigma_multiplier, correlations=correlations
        )

    monkeypatch.setattr(workspace_controller_module, "statistical", spy)

    result = controller.run_analysis()

    assert calls == 1
    expected_sigma = math.sqrt(0.1**2 + 0.2**2)
    assert result.summary_values == {
        "nominal": 6.0,
        "combined_sigma": pytest.approx(expected_sigma),
        "sigma_multiplier": 1.0,
        "lower_bound": pytest.approx(6.0 - expected_sigma),
        "upper_bound": pytest.approx(6.0 + expected_sigma),
    }


def test_workspace_validation_rejects_invalid_numeric_and_modes() -> None:
    controller = ToleranceWorkspaceController.empty(
        chain_name="main-chain", analysis_mode=AnalysisMode.WORST_CASE
    )

    with pytest.raises(InvalidToleranceWorkspaceError, match="nominal"):
        controller.add_contributor(
            identifier="a",
            name="Face A",
            nominal="abc",
            tolerance=0.1,
            direction="forward",
            tolerance_model="symmetric",
        )
    with pytest.raises(InvalidToleranceWorkspaceError, match="finite"):
        controller.add_contributor(
            identifier="a",
            name="Face A",
            nominal=1.0,
            tolerance=float("nan"),
            direction="forward",
            tolerance_model="symmetric",
        )
    with pytest.raises(InvalidToleranceWorkspaceError, match="direction"):
        controller.add_contributor(
            identifier="a",
            name="Face A",
            nominal=1.0,
            tolerance=0.1,
            direction="sideways",
            tolerance_model="symmetric",
        )
    with pytest.raises(InvalidToleranceWorkspaceError, match="analysis mode"):
        ToleranceWorkspaceController.empty(
            chain_name="main-chain", analysis_mode="budget"
        )


def test_workspace_requires_supported_tolerance_model_and_unique_ids() -> None:
    controller = _controller()

    with pytest.raises(
        InvalidToleranceWorkspaceError, match="unsupported tolerance model"
    ):
        controller.add_contributor(
            identifier="c",
            name="Face C",
            nominal=1.0,
            tolerance=0.1,
            direction="forward",
            tolerance_model="bilateral-plus-clearance",
        )
    with pytest.raises(InvalidToleranceWorkspaceError, match="duplicate"):
        controller.add_contributor(
            identifier="a",
            name="Duplicate",
            nominal=1.0,
            tolerance=0.1,
            direction="forward",
            tolerance_model="symmetric",
        )


def test_workspace_edit_remove_and_snapshot_roundtrip() -> None:
    controller = _controller()

    updated = controller.edit_contributor("a", tolerance=0.15, direction="inverse")
    assert updated.tolerance == 0.15
    assert updated.direction is StackDirection.INVERSE
    controller.remove_contributor("b")

    restored = workspace_state_from_snapshot(controller.snapshot())

    assert [item.identifier for item in restored.contributors] == ["a"]
    assert restored.contributors[0].tolerance == 0.15
    assert controller.last_result is None


def test_set_chain_name_preserves_result_when_unchanged() -> None:
    controller = _controller()
    result = controller.run_analysis()

    controller.set_chain_name("main-chain")

    assert controller.state.chain_name == "main-chain"
    assert controller.last_result is result


def test_set_chain_name_invalidates_result_when_changed() -> None:
    controller = _controller()
    result = controller.run_analysis()

    controller.set_chain_name("secondary-chain")

    assert controller.state.chain_name == "secondary-chain"
    assert controller.last_result is not result
    assert controller.last_result is None


def test_set_chain_name_rejects_invalid_names_without_side_effects() -> None:
    controller = _controller()
    result = controller.run_analysis()

    with pytest.raises(InvalidToleranceWorkspaceError, match="chain_name"):
        controller.set_chain_name("")
    with pytest.raises(InvalidToleranceWorkspaceError, match="chain_name"):
        controller.set_chain_name("   ")
    with pytest.raises(InvalidToleranceWorkspaceError, match="chain_name"):
        controller.set_chain_name(" padded ")

    assert controller.state.chain_name == "main-chain"
    assert controller.last_result is result


def test_set_analysis_mode_preserves_result_when_unchanged() -> None:
    controller = _controller()
    result = controller.run_analysis()

    controller.set_analysis_mode(AnalysisMode.WORST_CASE)
    controller.set_analysis_mode("worst_case")

    assert controller.analysis_mode is AnalysisMode.WORST_CASE
    assert controller.last_result is result


def test_set_analysis_mode_invalidates_result_when_changed() -> None:
    controller = _controller()
    result = controller.run_analysis()

    controller.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)

    assert controller.analysis_mode is AnalysisMode.RSS_STATISTICAL
    assert controller.last_result is not result
    assert controller.last_result is None
