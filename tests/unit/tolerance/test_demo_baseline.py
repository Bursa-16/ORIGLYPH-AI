"""Tests for the Stage 18D demo freeze package.

Verifies that the golden demo baseline document, readiness script,
baseline manifest, and required demo assets are present, internally
consistent, and free from destructive git commands.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]

GOLDEN_COMMIT  = "7fc11129ca63d09d0054ceb8afe241ea894ca93a"
GOLDEN_VERSION = "0.4.0a7"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Required file existence
# ---------------------------------------------------------------------------


def test_golden_baseline_doc_exists() -> None:
    assert (REPO_ROOT / "docs" / "demo" / "golden_demo_baseline.md").is_file()


def test_readiness_script_exists() -> None:
    assert (REPO_ROOT / "scripts" / "check_demo_readiness.ps1").is_file()


def test_demo_baseline_manifest_exists() -> None:
    assert (REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json").is_file()


def test_required_demo_assets_exist() -> None:
    assets = [
        "examples/tolerance_workspace_demo.py",
        "scripts/run_tolerance_demo.ps1",
        "scripts/run_tolerance_demo.cmd",
        "docs/demo/customer_demo_runbook.md",
        "docs/demo/customer_demo_cheat_sheet.md",
    ]
    for rel in assets:
        assert (REPO_ROOT / rel).is_file(), f"Missing demo asset: {rel}"


# ---------------------------------------------------------------------------
# Golden baseline document content
# ---------------------------------------------------------------------------


def test_golden_baseline_records_commit() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert GOLDEN_COMMIT in text


def test_golden_baseline_records_version() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert GOLDEN_VERSION in text


def test_golden_baseline_approved_claims_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "Approved claims" in text
    assert "Deterministic tolerance analysis" in text


def test_golden_baseline_prohibited_claims_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "Prohibited demo claims" in text
    assert "Automatic allocation optimisation" in text


def test_golden_baseline_known_limitations_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "Known limitations" in text


def test_golden_baseline_freeze_policy_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "freeze policy" in text.lower()


def test_golden_baseline_presenter_preflight_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "pre-flight" in text.lower() or "preflight" in text.lower()


def test_golden_baseline_launcher_documented() -> None:
    text = _read("docs/demo/golden_demo_baseline.md")
    assert "run_tolerance_demo.ps1" in text


# ---------------------------------------------------------------------------
# Baseline manifest validity
# ---------------------------------------------------------------------------


def test_manifest_is_valid_json() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_manifest_commit_matches_baseline() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["baseline_commit"] == GOLDEN_COMMIT


def test_manifest_version_matches_baseline() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == GOLDEN_VERSION


def test_manifest_customer_demo_ready() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["customer_demo_ready"] is True


def test_manifest_launcher_path_exists() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    launcher = data["launcher"]
    assert (REPO_ROOT / launcher).is_file(), f"Launcher not found: {launcher}"


def test_manifest_demo_entry_point_exists() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["demo_entry_point"]
    assert (REPO_ROOT / entry).is_file(), f"Demo entry point not found: {entry}"


def test_manifest_runbook_exists() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    runbook = data["runbook"]
    assert (REPO_ROOT / runbook).is_file(), f"Runbook not found: {runbook}"


def test_manifest_validation_stage_is_18c() -> None:
    path = REPO_ROOT / "docs" / "demo" / "demo_baseline_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["validation_stage"] == "18C"


# ---------------------------------------------------------------------------
# Readiness script — no destructive git commands
# ---------------------------------------------------------------------------

_DESTRUCTIVE_GIT_PATTERNS = [
    r"\bgit\s+reset\b",
    r"\bgit\s+checkout\s",
    r"\bgit\s+stash\b",
    r"\bgit\s+pull\b",
    r"\bgit\s+merge\b",
    r"\bgit\s+rebase\b",
    r"\bgit\s+push\b",
    r"\bgit\s+clean\b",
    r"\bgit\s+branch\s+-[Dd]\b",
    r"\bgit\s+restore\b",
]


def test_readiness_script_has_no_destructive_git_commands() -> None:
    text = _read("scripts/check_demo_readiness.ps1")
    lines = text.splitlines()
    for pattern in _DESTRUCTIVE_GIT_PATTERNS:
        rx = re.compile(pattern, re.IGNORECASE)
        for i, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert not rx.search(line), (
                f"Destructive git command matched pattern '{pattern}' "
                f"at line {i}: {line.strip()!r}"
            )


def test_readiness_script_references_golden_commit() -> None:
    text = _read("scripts/check_demo_readiness.ps1")
    assert GOLDEN_COMMIT in text


def test_readiness_script_references_golden_version() -> None:
    text = _read("scripts/check_demo_readiness.ps1")
    assert GOLDEN_VERSION in text


def test_readiness_script_outputs_pass_or_fail() -> None:
    text = _read("scripts/check_demo_readiness.ps1")
    assert "DEMO_READINESS: PASS" in text
    assert "DEMO_READINESS: FAIL" in text
