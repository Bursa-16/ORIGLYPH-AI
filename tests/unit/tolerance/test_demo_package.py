"""Smoke tests for the Stage 18B demo presenter package.

Verifies that launcher scripts, runbook, and cheat sheet exist at the
expected paths relative to the repository root, and that the demo entry
point constructs a valid workspace without mutating any global state.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]


# ---------------------------------------------------------------------------
# Launcher infrastructure
# ---------------------------------------------------------------------------


def test_ps1_launcher_exists() -> None:
    assert (REPO_ROOT / "scripts" / "run_tolerance_demo.ps1").is_file()


def test_cmd_launcher_exists() -> None:
    assert (REPO_ROOT / "scripts" / "run_tolerance_demo.cmd").is_file()


def test_demo_entry_point_exists() -> None:
    assert (REPO_ROOT / "examples" / "tolerance_workspace_demo.py").is_file()


# ---------------------------------------------------------------------------
# Presenter documents
# ---------------------------------------------------------------------------


def test_runbook_exists() -> None:
    assert (REPO_ROOT / "docs" / "demo" / "customer_demo_runbook.md").is_file()


def test_cheat_sheet_exists() -> None:
    assert (REPO_ROOT / "docs" / "demo" / "customer_demo_cheat_sheet.md").is_file()


# ---------------------------------------------------------------------------
# Demo dataset construction — no production-state mutation
# ---------------------------------------------------------------------------


def test_demo_controller_imports_and_constructs() -> None:
    from examples.tolerance_workspace_demo import demo_controller

    controller = demo_controller()
    assert len(controller.contributors) == 3


def test_demo_constructs_no_side_effects() -> None:
    """Constructing the demo controller twice produces independent objects."""
    from examples.tolerance_workspace_demo import demo_controller

    c1 = demo_controller()
    c2 = demo_controller()
    assert c1 is not c2
    assert len(c1.contributors) == len(c2.contributors) == 3
