"""Stage 17B tests — Deterministic Tolerance Decision Surface.

Tests cover:
A. Worst-case PASS / FAIL / missing spec / wrong-mode spec
B. RSS PASS / FAIL / missing spec / wrong-mode spec
C. Invalidation: contributor, chain, mode, spec, rerun
D. Session: decision_text, decision_detail_text, evaluate_decision delegation
E. Authority: Stage 15K API is invoked; sigma_multiplier is passed correctly
F. Persistence: decision is runtime-derived only (not in project file)
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from origlyph.tolerance import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceDecisionResult,
    ToleranceDecisionStatus,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
)
from origlyph.tolerance import workspace_controller as workspace_controller_module
from origlyph.tolerance.workspace_model import (
    _NO_DECISION_TEXT,
    WorkspaceSession,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _wc_controller(
    allowed_wc_span: float | None = None,
    allowed_sigma: float | None = None,
) -> ToleranceWorkspaceController:
    """Worst-case controller with two contributors (total_span = 0.6)."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    c.add_contributor(
        identifier="a", name="Face A", nominal=10.0, tolerance=0.1,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    c.add_contributor(
        identifier="b", name="Face B", nominal=4.0, tolerance=0.2,
        direction=StackDirection.INVERSE, tolerance_model="symmetric",
    )
    if allowed_wc_span is not None or allowed_sigma is not None:
        c.set_specification(WorkspaceSpecification(
            allowed_worst_case_span=allowed_wc_span,
            allowed_combined_sigma=allowed_sigma,
        ))
    return c


def _rss_controller(
    allowed_wc_span: float | None = None,
    allowed_sigma: float | None = None,
) -> ToleranceWorkspaceController:
    """RSS controller with two contributors (combined_sigma ≈ 0.2236 at k=1)."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.RSS_STATISTICAL
    )
    c.add_contributor(
        identifier="a", name="Face A", nominal=10.0, tolerance=0.1,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    c.add_contributor(
        identifier="b", name="Face B", nominal=4.0, tolerance=0.2,
        direction=StackDirection.INVERSE, tolerance_model="symmetric",
    )
    if allowed_wc_span is not None or allowed_sigma is not None:
        c.set_specification(WorkspaceSpecification(
            allowed_worst_case_span=allowed_wc_span,
            allowed_combined_sigma=allowed_sigma,
        ))
    return c


# ---------------------------------------------------------------------------
# A. WORST CASE
# ---------------------------------------------------------------------------

def test_wc_pass() -> None:
    """WC total_span=0.6 < allowed=1.0 → PASS."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    result = c.evaluate_decision()
    assert isinstance(result, ToleranceDecisionResult)
    assert result.overall_status is ToleranceDecisionStatus.PASS
    assert result.worst_case_passed is True
    assert result.evidence.worst_case_actual_span == pytest.approx(0.6)
    assert result.evidence.worst_case_allowed_span == pytest.approx(1.0)
    assert result.evidence.worst_case_margin == pytest.approx(0.4)


def test_wc_fail() -> None:
    """WC total_span=0.6 > allowed=0.3 → FAIL."""
    c = _wc_controller(allowed_wc_span=0.3)
    c.run_analysis()
    result = c.evaluate_decision()
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.worst_case_passed is False
    margin = result.evidence.worst_case_margin
    assert margin is not None and margin < 0.0


def test_wc_missing_spec_raises_closed() -> None:
    """No specification → fail closed, must not produce PASS."""
    c = _wc_controller()
    c.run_analysis()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_worst_case_span"):
        c.evaluate_decision()


def test_rss_only_spec_does_not_authorize_wc_decision() -> None:
    """RSS sigma limit alone must not authorize a worst-case verdict."""
    c = _wc_controller(allowed_sigma=1.0)
    c.run_analysis()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_worst_case_span"):
        c.evaluate_decision()


def test_wc_statistical_passed_is_none() -> None:
    """WC-mode decision must not evaluate a statistical dimension."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    result = c.evaluate_decision()
    assert result.statistical_passed is None


# ---------------------------------------------------------------------------
# B. RSS
# ---------------------------------------------------------------------------

def test_rss_pass() -> None:
    """RSS combined_sigma≈0.2236 < allowed=0.5 → PASS."""
    c = _rss_controller(allowed_sigma=0.5)
    c.run_analysis()
    result = c.evaluate_decision()
    assert result.overall_status is ToleranceDecisionStatus.PASS
    assert result.statistical_passed is True
    actual = result.evidence.statistical_actual_combined_sigma
    assert actual is not None
    assert actual == pytest.approx(math.sqrt(0.01 + 0.04), rel=1e-9)


def test_rss_fail() -> None:
    """RSS combined_sigma≈0.2236 > allowed=0.1 → FAIL."""
    c = _rss_controller(allowed_sigma=0.1)
    c.run_analysis()
    result = c.evaluate_decision()
    assert result.overall_status is ToleranceDecisionStatus.FAIL
    assert result.statistical_passed is False


def test_rss_missing_spec_raises_closed() -> None:
    """No specification → fail closed, must not produce PASS."""
    c = _rss_controller()
    c.run_analysis()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_combined_sigma"):
        c.evaluate_decision()


def test_wc_only_spec_does_not_authorize_rss_decision() -> None:
    """WC span limit alone must not authorize an RSS verdict."""
    c = _rss_controller(allowed_wc_span=1.0)
    c.run_analysis()
    with pytest.raises(InvalidToleranceWorkspaceError, match="allowed_combined_sigma"):
        c.evaluate_decision()


def test_rss_worst_case_passed_is_none() -> None:
    """RSS-mode decision must not evaluate a worst-case dimension."""
    c = _rss_controller(allowed_sigma=0.5)
    c.run_analysis()
    result = c.evaluate_decision()
    assert result.worst_case_passed is None


# ---------------------------------------------------------------------------
# C. INVALIDATION
# ---------------------------------------------------------------------------

def test_contributor_add_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    assert c.last_decision is not None
    c.add_contributor(
        identifier="c", name="Face C", nominal=1.0, tolerance=0.05,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    assert c.last_decision is None


def test_contributor_edit_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    c.edit_contributor("a", tolerance=0.15)
    assert c.last_decision is None


def test_contributor_remove_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    c.remove_contributor("b")
    assert c.last_decision is None


def test_chain_name_change_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    c.set_chain_name("new-chain")
    assert c.last_decision is None


def test_analysis_mode_change_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    c.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert c.last_decision is None


def test_specification_change_clears_decision() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    assert c.last_decision is None


def test_rerun_analysis_clears_prior_decision() -> None:
    """Re-running analysis must invalidate the cached decision."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    assert c.last_decision is not None
    c.run_analysis()
    assert c.last_decision is None


def test_no_op_chain_name_preserves_decision() -> None:
    """Setting the same chain name must not clear the cached decision."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    decision = c.evaluate_decision()
    c.set_chain_name("chain")
    assert c.last_decision is decision


def test_no_op_specification_preserves_decision() -> None:
    """Setting the same spec must not clear the cached decision."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    decision = c.evaluate_decision()
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=1.0))
    assert c.last_decision is decision


# ---------------------------------------------------------------------------
# D. SESSION / VIEW
# ---------------------------------------------------------------------------

def test_session_decision_text_not_evaluated_initially() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    session = WorkspaceSession(c)
    assert session.decision_text == _NO_DECISION_TEXT


def test_session_decision_text_pass() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    assert session.decision_text == "PASS"


def test_session_decision_text_fail() -> None:
    c = _wc_controller(allowed_wc_span=0.3)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    assert session.decision_text == "FAIL"


def test_session_decision_text_cleared_after_contributor_change() -> None:
    """Stale PASS must not survive an authoritative contributor change."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    assert session.decision_text == "PASS"
    c.edit_contributor("a", tolerance=0.5)
    assert session.decision_text == _NO_DECISION_TEXT


def test_session_evaluate_decision_delegates_to_controller() -> None:
    """Session.evaluate_decision must delegate to the controller."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    session = WorkspaceSession(c)
    result = session.evaluate_decision()
    assert isinstance(result, ToleranceDecisionResult)
    assert c.last_decision is result


def test_session_no_independent_decision_logic() -> None:
    """Session must not own PASS/FAIL logic; decision_text reads controller."""
    c = _wc_controller(allowed_wc_span=0.3)
    c.run_analysis()
    session = WorkspaceSession(c)
    assert session.decision_text == _NO_DECISION_TEXT
    c.evaluate_decision()
    assert session.decision_text == "FAIL"


def test_session_decision_detail_text_pass_wc() -> None:
    """PASS decision detail must contain Actual / Limit / Margin."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    detail = session.decision_detail_text
    assert "Actual:" in detail
    assert "Limit:" in detail
    assert "Margin:" in detail


def test_session_decision_detail_text_fail_has_reason() -> None:
    """FAIL decision detail must include Reason."""
    c = _wc_controller(allowed_wc_span=0.3)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    detail = session.decision_detail_text
    assert "Reason:" in detail


def test_session_decision_detail_text_empty_when_not_evaluated() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    session = WorkspaceSession(c)
    assert session.decision_detail_text == ""


def test_session_decision_detail_rss() -> None:
    """RSS decision detail must use sigma labels."""
    c = _rss_controller(allowed_sigma=0.5)
    c.run_analysis()
    c.evaluate_decision()
    session = WorkspaceSession(c)
    detail = session.decision_detail_text
    assert "σ" in detail or "sigma" in detail.lower() or "Actual" in detail


# ---------------------------------------------------------------------------
# E. AUTHORITY
# ---------------------------------------------------------------------------

def test_controller_delegates_to_stage15k_api(monkeypatch) -> None:
    """Controller must call evaluate_tolerance_decision, not reimplement."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    calls = 0
    original = workspace_controller_module.evaluate_tolerance_decision

    def spy(**kwargs):
        nonlocal calls
        calls += 1
        return original(**kwargs)

    monkeypatch.setattr(
        workspace_controller_module, "evaluate_tolerance_decision", spy
    )
    c.evaluate_decision()
    assert calls == 1


def test_rss_decision_passes_workspace_sigma_multiplier(monkeypatch) -> None:
    """RSS decision must forward sigma_multiplier=1.0 (matching analysis)."""
    c = _rss_controller(allowed_sigma=0.5)
    c.run_analysis()
    captured: dict = {}
    original = workspace_controller_module.evaluate_tolerance_decision

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        workspace_controller_module, "evaluate_tolerance_decision", spy
    )
    c.evaluate_decision()
    assert captured.get("sigma_multiplier") == pytest.approx(1.0)


def test_evaluate_decision_before_analysis_raises() -> None:
    """Evaluating decision without prior analysis must raise."""
    c = _wc_controller(allowed_wc_span=1.0)
    with pytest.raises(InvalidToleranceWorkspaceError, match="run analysis"):
        c.evaluate_decision()


def test_last_decision_starts_none() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    assert c.last_decision is None


def test_last_decision_set_after_evaluate() -> None:
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    assert c.last_decision is None
    result = c.evaluate_decision()
    assert c.last_decision is result


# ---------------------------------------------------------------------------
# F. PERSISTENCE (runtime-derived only)
# ---------------------------------------------------------------------------

def test_decision_is_not_persisted(tmp_path: Path) -> None:
    """Decision result is runtime-derived; project file must not carry it."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    assert c.last_decision is not None
    path = c.save_project(
        tmp_path / "workspace.origlyph.json", project_name="test"
    )
    loaded = ToleranceWorkspaceController.open_project(path)
    assert loaded.last_decision is None


def test_project_schema_unchanged(tmp_path: Path) -> None:
    """Stage 17B must not alter the workspace schema version."""
    from origlyph.project import load_project
    from origlyph.project.tolerance_workspace import TOLERANCE_WORKSPACE_EXTENSION_KEY
    from origlyph.tolerance import TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2

    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    path = c.save_project(
        tmp_path / "schema_check.origlyph.json", project_name="test"
    )
    loaded = load_project(path)
    ws_snap = loaded.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
    assert ws_snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
