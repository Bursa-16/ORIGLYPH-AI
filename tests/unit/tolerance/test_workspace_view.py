from __future__ import annotations

from pathlib import Path

import pytest

from origlyph.project import load_project
from origlyph.tolerance import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
)
from origlyph.tolerance.workspace_model import _NO_RESULT_TEXT, WorkspaceSession


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


def _session() -> WorkspaceSession:
    """Build the view seam exactly as the Tkinter view wires it."""
    return WorkspaceSession(_controller())


def test_view_save_persists_last_computed_result(tmp_path: Path) -> None:
    session = _session()
    result = session.run_analysis()

    target = session.save_project(
        tmp_path / "workspace.origlyph.json", project_name=session.chain_name
    )

    loaded = load_project(target)

    assert loaded.tolerance_state is not None
    assert loaded.tolerance_state.result_identities == (result.result_id,)
    assert loaded.tolerance_state.summary_values == result.summary_values
    assert loaded.tolerance_state.summary_values
    assert session.result_text.startswith("worst_case:")


def test_save_before_analysis_persists_no_result_evidence(tmp_path: Path) -> None:
    session = _session()

    target = session.save_project(
        tmp_path / "empty.origlyph.json", project_name=session.chain_name
    )

    loaded = load_project(target)

    assert loaded.tolerance_state is not None
    assert loaded.tolerance_state.result_identities == ()
    assert loaded.tolerance_state.summary_values == {}


def test_no_op_header_sync_preserves_cached_result() -> None:
    session = _session()
    result = session.run_analysis()

    session.chain_name = "main-chain"
    session.analysis_mode = AnalysisMode.WORST_CASE.value
    session.sync_header()

    assert session.controller.last_result is result
    assert session.result_text != _NO_RESULT_TEXT


def test_chain_name_change_invalidates_result_and_clears_label() -> None:
    session = _session()
    session.run_analysis()
    assert session.result_text != _NO_RESULT_TEXT

    session.chain_name = "secondary-chain"
    session.sync_header()

    assert session.controller.state.chain_name == "secondary-chain"
    assert session.controller.last_result is None
    assert session.result_text == _NO_RESULT_TEXT


def test_analysis_mode_change_invalidates_result_and_clears_label() -> None:
    session = _session()
    session.run_analysis()

    session.analysis_mode = AnalysisMode.RSS_STATISTICAL.value
    session.sync_header()

    assert session.controller.analysis_mode is AnalysisMode.RSS_STATISTICAL
    assert session.controller.last_result is None
    assert session.result_text == _NO_RESULT_TEXT


def test_contributor_changes_invalidate_result_and_clear_label() -> None:
    session = _session()

    session.run_analysis()
    session.controller.add_contributor(
        identifier="c",
        name="Face C",
        nominal=1.0,
        tolerance=0.05,
        direction=StackDirection.FORWARD,
        tolerance_model="symmetric",
    )
    assert session.controller.last_result is None
    assert session.result_text == _NO_RESULT_TEXT

    session.run_analysis()
    session.controller.edit_contributor("a", tolerance=0.15)
    assert session.controller.last_result is None
    assert session.result_text == _NO_RESULT_TEXT

    session.run_analysis()
    session.controller.remove_contributor("b")
    assert session.controller.last_result is None
    assert session.result_text == _NO_RESULT_TEXT


def test_rejected_header_sync_keeps_cached_result() -> None:
    session = _session()
    result = session.run_analysis()

    session.chain_name = "   "
    with pytest.raises(InvalidToleranceWorkspaceError, match="chain_name"):
        session.sync_header()

    assert session.controller.state.chain_name == "main-chain"
    assert session.controller.last_result is result
    assert session.result_text != _NO_RESULT_TEXT
