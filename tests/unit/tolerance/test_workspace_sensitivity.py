"""Stage 17C tests — Tolerance Sensitivity UI Foundation.

Tests cover:
A. Engine delegation: Stage 15F API is invoked; no controller formula
B. Determinism: same input → same result; stable ranking
C. Invalidation: contributor/chain/mode clear; spec does not; run_analysis does not
D. Session: sensitivity_rows, run_sensitivity delegation, stale display
E. Decision isolation: sensitivity does not alter verdict
F. Persistence: runtime-derived only; save/open does not fabricate result
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from origlyph.tolerance import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    StackDirection,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
    WorstCaseSensitivityResult,
)
from origlyph.tolerance import workspace_controller as workspace_controller_module
from origlyph.tolerance.sensitivity import StatisticalSensitivityResult
from origlyph.tolerance.workspace_model import WorkspaceSession

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _wc_controller(
    allowed_wc_span: float | None = None,
) -> ToleranceWorkspaceController:
    """WC controller with two contributors (total_span = 0.6)."""
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
    if allowed_wc_span is not None:
        c.set_specification(
            WorkspaceSpecification(allowed_worst_case_span=allowed_wc_span)
        )
    return c


def _rss_controller(
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
    if allowed_sigma is not None:
        c.set_specification(
            WorkspaceSpecification(allowed_combined_sigma=allowed_sigma)
        )
    return c


# ---------------------------------------------------------------------------
# A. ENGINE DELEGATION
# ---------------------------------------------------------------------------


def test_wc_delegates_to_worst_case_sensitivity(monkeypatch) -> None:
    """Controller must call worst_case_sensitivity, not reimplement."""
    c = _wc_controller()
    calls = 0
    original = workspace_controller_module.worst_case_sensitivity

    def spy(stack):
        nonlocal calls
        calls += 1
        return original(stack)

    monkeypatch.setattr(
        workspace_controller_module, "worst_case_sensitivity", spy
    )
    c.run_sensitivity()
    assert calls == 1


def test_rss_delegates_to_statistical_sensitivity(monkeypatch) -> None:
    """Controller must call statistical_sensitivity, not reimplement."""
    c = _rss_controller()
    calls = 0
    original = workspace_controller_module.statistical_sensitivity

    def spy(stack, *, sigma_multiplier, correlations):
        nonlocal calls
        calls += 1
        return original(
            stack, sigma_multiplier=sigma_multiplier, correlations=correlations
        )

    monkeypatch.setattr(
        workspace_controller_module, "statistical_sensitivity", spy
    )
    c.run_sensitivity()
    assert calls == 1


def test_rss_sensitivity_passes_workspace_sigma_multiplier(monkeypatch) -> None:
    """RSS sensitivity must forward sigma_multiplier=1.0 (matching analysis)."""
    c = _rss_controller()
    captured: dict = {}
    original = workspace_controller_module.statistical_sensitivity

    def spy(stack, *, sigma_multiplier, correlations):
        captured["sigma_multiplier"] = sigma_multiplier
        return original(
            stack, sigma_multiplier=sigma_multiplier, correlations=correlations
        )

    monkeypatch.setattr(
        workspace_controller_module, "statistical_sensitivity", spy
    )
    c.run_sensitivity()
    assert captured.get("sigma_multiplier") == pytest.approx(1.0)


def test_no_contributors_raises() -> None:
    """Empty workspace must fail closed on sensitivity."""
    c = ToleranceWorkspaceController.empty(
        chain_name="chain", analysis_mode=AnalysisMode.WORST_CASE
    )
    with pytest.raises(InvalidToleranceWorkspaceError, match="at least one"):
        c.run_sensitivity()


# ---------------------------------------------------------------------------
# B. DETERMINISM
# ---------------------------------------------------------------------------


def test_wc_sensitivity_result_type() -> None:
    c = _wc_controller()
    result = c.run_sensitivity()
    assert isinstance(result, WorstCaseSensitivityResult)


def test_rss_sensitivity_result_type() -> None:
    c = _rss_controller()
    result = c.run_sensitivity()
    assert isinstance(result, StatisticalSensitivityResult)


def test_wc_sensitivity_values() -> None:
    """WC: contributor b (span=0.4) ranks first, a (span=0.2) ranks second."""
    c = _wc_controller()
    result = c.run_sensitivity()
    assert isinstance(result, WorstCaseSensitivityResult)
    assert result.total_span == pytest.approx(0.6)
    assert len(result.impacts) == 2
    first, second = result.impacts
    assert first.name == "b"
    assert first.span == pytest.approx(0.4)
    assert first.percentage == pytest.approx(400.0 / 6.0, rel=1e-9)
    assert second.name == "a"
    assert second.span == pytest.approx(0.2)


def test_rss_sensitivity_values() -> None:
    """RSS: contributor b (variance=0.04) ranks first, a (variance=0.01) second."""
    c = _rss_controller()
    result = c.run_sensitivity()
    assert isinstance(result, StatisticalSensitivityResult)
    total_var = 0.01 + 0.04
    assert result.total_variance == pytest.approx(total_var)
    assert result.combined_sigma == pytest.approx(math.sqrt(total_var))
    first, second = result.contributions
    assert first.name == "b"
    assert first.variance == pytest.approx(0.04)
    assert first.percentage == pytest.approx(80.0)
    assert second.name == "a"
    assert second.variance == pytest.approx(0.01)


def test_wc_sensitivity_deterministic() -> None:
    """Same WC inputs produce identical results on repeated calls."""
    c = _wc_controller()
    r1 = c.run_sensitivity()
    r2 = c.run_sensitivity()
    assert isinstance(r1, WorstCaseSensitivityResult)
    assert isinstance(r2, WorstCaseSensitivityResult)
    assert r1.total_span == r2.total_span
    assert r1.impacts[0].name == r2.impacts[0].name
    assert r1.impacts[0].span == r2.impacts[0].span


# ---------------------------------------------------------------------------
# C. INVALIDATION
# ---------------------------------------------------------------------------


def test_last_sensitivity_starts_none() -> None:
    c = _wc_controller()
    assert c.last_sensitivity is None


def test_last_sensitivity_set_after_run() -> None:
    c = _wc_controller()
    result = c.run_sensitivity()
    assert c.last_sensitivity is result


def test_contributor_add_clears_sensitivity() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    assert c.last_sensitivity is not None
    c.add_contributor(
        identifier="c", name="Face C", nominal=1.0, tolerance=0.05,
        direction=StackDirection.FORWARD, tolerance_model="symmetric",
    )
    assert c.last_sensitivity is None


def test_contributor_edit_clears_sensitivity() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    c.edit_contributor("a", tolerance=0.15)
    assert c.last_sensitivity is None


def test_contributor_remove_clears_sensitivity() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    c.remove_contributor("b")
    assert c.last_sensitivity is None


def test_chain_name_change_clears_sensitivity() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    c.set_chain_name("new-chain")
    assert c.last_sensitivity is None


def test_analysis_mode_change_clears_sensitivity() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    c.set_analysis_mode(AnalysisMode.RSS_STATISTICAL)
    assert c.last_sensitivity is None


def test_specification_change_does_not_clear_sensitivity() -> None:
    """Spec changes must not clear sensitivity (sensitivity is spec-independent)."""
    c = _wc_controller()
    c.run_sensitivity()
    sensitivity = c.last_sensitivity
    assert sensitivity is not None
    c.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))
    assert c.last_sensitivity is sensitivity


def test_run_analysis_does_not_clear_sensitivity() -> None:
    """Re-running analysis must not clear the cached sensitivity."""
    c = _wc_controller()
    c.run_sensitivity()
    sensitivity = c.last_sensitivity
    assert sensitivity is not None
    c.run_analysis()
    assert c.last_sensitivity is sensitivity


def test_no_op_chain_preserves_sensitivity() -> None:
    """Setting the same chain name must not clear sensitivity."""
    c = _wc_controller()
    c.run_sensitivity()
    sensitivity = c.last_sensitivity
    c.set_chain_name("chain")
    assert c.last_sensitivity is sensitivity


# ---------------------------------------------------------------------------
# D. SESSION / VIEW
# ---------------------------------------------------------------------------


def test_session_sensitivity_rows_empty_initially() -> None:
    c = _wc_controller()
    session = WorkspaceSession(c)
    assert session.sensitivity_rows() == []


def test_session_sensitivity_rows_after_run() -> None:
    c = _wc_controller()
    c.run_sensitivity()
    session = WorkspaceSession(c)
    rows = session.sensitivity_rows()
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "b"
    assert rows[0]["impact"] == pytest.approx(0.4)
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "a"


def test_session_sensitivity_rows_rss() -> None:
    c = _rss_controller()
    c.run_sensitivity()
    session = WorkspaceSession(c)
    rows = session.sensitivity_rows()
    assert len(rows) == 2
    assert rows[0]["name"] == "b"
    assert rows[0]["impact"] == pytest.approx(0.04)
    assert rows[0]["share_pct"] == pytest.approx(80.0)


def test_session_run_sensitivity_delegates_to_controller() -> None:
    c = _wc_controller()
    session = WorkspaceSession(c)
    result = session.run_sensitivity()
    assert isinstance(result, WorstCaseSensitivityResult)
    assert c.last_sensitivity is result


def test_session_sensitivity_rows_cleared_after_contributor_change() -> None:
    """Stale rows must not survive an authoritative contributor change."""
    c = _wc_controller()
    c.run_sensitivity()
    session = WorkspaceSession(c)
    assert len(session.sensitivity_rows()) == 2
    c.edit_contributor("a", tolerance=0.5)
    assert session.sensitivity_rows() == []


def test_session_no_independent_sensitivity_logic() -> None:
    """sensitivity_rows must read controller state; no local computation."""
    c = _wc_controller()
    session = WorkspaceSession(c)
    assert session.sensitivity_rows() == []
    c.run_sensitivity()
    assert len(session.sensitivity_rows()) == 2


# ---------------------------------------------------------------------------
# E. DECISION ISOLATION
# ---------------------------------------------------------------------------


def test_sensitivity_does_not_alter_decision() -> None:
    """Running sensitivity must not change an existing decision verdict."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    decision = c.evaluate_decision()
    c.run_sensitivity()
    assert c.last_decision is decision


def test_decision_does_not_alter_sensitivity() -> None:
    """Running decision must not clear the cached sensitivity."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.run_sensitivity()
    sensitivity = c.last_sensitivity
    assert sensitivity is not None
    c.evaluate_decision()
    assert c.last_sensitivity is sensitivity


def test_sensitivity_does_not_change_pass_fail() -> None:
    """Sensitivity result must not affect the decision verdict."""
    c = _wc_controller(allowed_wc_span=1.0)
    c.run_analysis()
    c.evaluate_decision()
    from origlyph.tolerance import ToleranceDecisionStatus
    assert c.last_decision is not None
    assert c.last_decision.overall_status is ToleranceDecisionStatus.PASS
    c.run_sensitivity()
    assert c.last_decision is not None
    assert c.last_decision.overall_status is ToleranceDecisionStatus.PASS


# ---------------------------------------------------------------------------
# F. PERSISTENCE (runtime-derived only)
# ---------------------------------------------------------------------------


def test_sensitivity_is_not_persisted(tmp_path: Path) -> None:
    """Sensitivity result is runtime-derived; project file must not carry it."""
    c = _wc_controller()
    c.run_sensitivity()
    assert c.last_sensitivity is not None
    path = c.save_project(
        tmp_path / "workspace.origlyph.json", project_name="test"
    )
    loaded = ToleranceWorkspaceController.open_project(path)
    assert loaded.last_sensitivity is None


def test_project_schema_unchanged_after_sensitivity(tmp_path: Path) -> None:
    """Stage 17C must not alter the workspace schema version."""
    from origlyph.project import load_project
    from origlyph.project.tolerance_workspace import TOLERANCE_WORKSPACE_EXTENSION_KEY
    from origlyph.tolerance import TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2

    c = _wc_controller(allowed_wc_span=1.0)
    c.run_sensitivity()
    path = c.save_project(
        tmp_path / "schema_check.origlyph.json", project_name="test"
    )
    loaded = load_project(path)
    ws_snap = loaded.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
    assert ws_snap["schema_version"] == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
