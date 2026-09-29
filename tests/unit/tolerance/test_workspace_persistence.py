from __future__ import annotations

import pytest

from origlyph.project import (
    TOLERANCE_WORKSPACE_EXTENSION_KEY,
    InvalidProjectError,
    ToleranceState,
    build_project,
    build_project_with_tolerance_workspace,
    load_project,
    project_with_tolerance_workspace,
    workspace_state_from_project,
)
from origlyph.tolerance import (
    AnalysisMode,
    StackDirection,
    ToleranceWorkspaceController,
    workspace_configuration_fingerprint,
)

_OTHER_SHA = "1" * 64


def _controller() -> ToleranceWorkspaceController:
    controller = ToleranceWorkspaceController.empty(
        chain_name="main-chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    controller.add_contributor(
        identifier="a",
        name="Face A",
        nominal=10.0,
        tolerance=0.1,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="b",
        name="Face B",
        nominal=4.0,
        tolerance=0.2,
        direction=StackDirection.INVERSE,
        tolerance_model="symmetric",
    )
    return controller


def test_workspace_project_roundtrip_preserves_authoritative_state(tmp_path) -> None:
    controller = _controller()
    result = controller.run_analysis()
    project = build_project_with_tolerance_workspace(
        controller.state, result=result, project_name="workspace"
    )
    target = controller.save_project(tmp_path / "workspace.origlyph.json")

    loaded = load_project(target)
    reopened = ToleranceWorkspaceController.open_project(target)

    assert loaded.project_id == project.project_id
    assert workspace_state_from_project(loaded) == controller.state
    assert reopened.state == controller.state
    assert loaded.tolerance_state is not None
    assert loaded.tolerance_state.result_identities == (result.result_id,)
    assert loaded.tolerance_state.summary_values == result.summary_values


def test_workspace_extension_preserves_contributor_order() -> None:
    controller = _controller()
    project = build_project_with_tolerance_workspace(controller.state)

    state = workspace_state_from_project(project)

    assert [item.identifier for item in state.contributors] == ["a", "b"]
    assert project.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]["contributors"][0][
        "identifier"
    ] == "a"


def test_project_identity_changes_when_authoritative_workspace_changes() -> None:
    controller = _controller()
    first = build_project_with_tolerance_workspace(controller.state)

    controller.edit_contributor("a", tolerance=0.15)
    changed_tolerance = build_project_with_tolerance_workspace(controller.state)
    controller.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    changed_mode = build_project_with_tolerance_workspace(controller.state)

    assert changed_tolerance.project_id != first.project_id
    assert changed_mode.project_id != changed_tolerance.project_id


def test_transient_ui_state_is_excluded_from_project_identity() -> None:
    controller = _controller()

    first = build_project_with_tolerance_workspace(
        controller.state,
        transient_ui_state={"selected_row": "a", "window": [10, 20]},
    )
    second = build_project_with_tolerance_workspace(
        controller.state,
        transient_ui_state={"selected_row": "b", "window": [30, 40]},
    )

    assert second.project_id == first.project_id
    assert second.extensions == first.extensions


def test_project_with_workspace_preserves_existing_project_fields() -> None:
    controller = _controller()
    original = build_project(metadata=None, artifact_refs={"report": _OTHER_SHA})

    updated = project_with_tolerance_workspace(original, controller.state)

    assert updated.metadata == original.metadata
    assert updated.artifact_refs == original.artifact_refs
    assert workspace_state_from_project(updated) == controller.state


def test_workspace_from_project_rejects_malformed_extension() -> None:
    controller = _controller()
    fingerprint = workspace_configuration_fingerprint(controller.state)
    project = build_project(
        tolerance_state=ToleranceState(
            chain_name="main-chain", configuration_fingerprint=fingerprint
        ),
        extensions={TOLERANCE_WORKSPACE_EXTENSION_KEY: {"schema_version": "bad"}},
    )

    with pytest.raises(InvalidProjectError, match="invalid tolerance workspace"):
        workspace_state_from_project(project)


def test_workspace_from_project_rejects_tolerance_state_mismatch() -> None:
    controller = _controller()
    project = build_project(
        tolerance_state=ToleranceState(
            chain_name="main-chain", configuration_fingerprint=_OTHER_SHA
        ),
        extensions={TOLERANCE_WORKSPACE_EXTENSION_KEY: controller.snapshot()},
    )

    with pytest.raises(InvalidProjectError, match="fingerprint"):
        workspace_state_from_project(project)
