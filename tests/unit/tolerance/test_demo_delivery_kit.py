"""Tests for the Stage 18E customer demo delivery kit.

Verifies that all delivery-kit files exist, that the package index
references valid paths, that no Stage 18E files contain unrelated
project names, and that unsupported capability phrases are only
present in a clearly disqualified context.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]

GOLDEN_COMMIT = "b68ab0e664805ef8c8c94a667c80b08706d13a30"

_DEMO_DIR = REPO_ROOT / "docs" / "demo"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Delivery-kit files exist
# ---------------------------------------------------------------------------

_DELIVERY_KIT_FILES = [
    "docs/demo/customer_demo_delivery_checklist.md",
    "docs/demo/origlyph_customer_one_pager.md",
    "docs/demo/customer_demo_5min_script.md",
    "docs/demo/customer_demo_15min_script.md",
    "docs/demo/customer_demo_faq.md",
    "docs/demo/customer_demo_positioning.md",
    "docs/demo/customer_demo_followup_email.md",
    "docs/demo/customer_discovery_questions.md",
    "docs/demo/customer_pilot_outline.md",
    "docs/demo/customer_demo_fallback.md",
    "docs/demo/README.md",
]


def test_all_delivery_kit_files_exist() -> None:
    for rel in _DELIVERY_KIT_FILES:
        assert (REPO_ROOT / rel).is_file(), f"Missing: {rel}"


def test_existing_demo_assets_unchanged() -> None:
    required = [
        "docs/demo/golden_demo_baseline.md",
        "docs/demo/demo_baseline_manifest.json",
        "docs/demo/customer_demo_runbook.md",
        "docs/demo/customer_demo_cheat_sheet.md",
        "scripts/check_demo_readiness.ps1",
        "scripts/run_tolerance_demo.ps1",
        "scripts/run_tolerance_demo.cmd",
        "examples/tolerance_workspace_demo.py",
    ]
    for rel in required:
        assert (REPO_ROOT / rel).is_file(), f"Missing existing asset: {rel}"


# ---------------------------------------------------------------------------
# README index references valid paths
# ---------------------------------------------------------------------------


def test_readme_references_golden_baseline() -> None:
    text = _read("docs/demo/README.md")
    assert "golden_demo_baseline.md" in text


def test_readme_references_runbook() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_runbook.md" in text


def test_readme_references_cheat_sheet() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_cheat_sheet.md" in text


def test_readme_references_readiness_script() -> None:
    text = _read("docs/demo/README.md")
    assert "check_demo_readiness.ps1" in text


def test_readme_references_launcher() -> None:
    text = _read("docs/demo/README.md")
    assert "run_tolerance_demo.ps1" in text


def test_readme_references_golden_commit() -> None:
    text = _read("docs/demo/README.md")
    assert GOLDEN_COMMIT in text


def test_readme_references_5min_script() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_5min_script.md" in text


def test_readme_references_faq() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_faq.md" in text


def test_readme_references_positioning_guide() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_positioning.md" in text


def test_readme_references_fallback() -> None:
    text = _read("docs/demo/README.md")
    assert "customer_demo_fallback.md" in text


# ---------------------------------------------------------------------------
# Contamination check — Stage 18E files only
# ---------------------------------------------------------------------------

_CONTAMINATION_NAMES = [
    "MachineryPro",
    "MachiningPro",
    "SpotWeld",
    "TorqPro",
    "DatumIQ",
]


def test_delivery_kit_files_have_no_contamination() -> None:
    for rel in _DELIVERY_KIT_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for name in _CONTAMINATION_NAMES:
            assert name not in text, (
                f"Contamination '{name}' found in {rel}"
            )


# ---------------------------------------------------------------------------
# Unsupported capability phrases only appear with disqualifying context
# ---------------------------------------------------------------------------

_UNSUPPORTED_PHRASES = [
    "automatic optimization",
    "automatic allocation optimis",
    "autonomous engineering",
    "full STEP support",
    "full GD&T",
    "full CAD workstation",
]

_DISQUALIFIERS = re.compile(
    r"not\b|future|NOT IMPLEMENTED|planned|not yet|not in this"
    r"|not currently|out of scope|excluded|exclusion",
    re.IGNORECASE,
)


def _phrase_has_disqualifier(text: str, phrase: str) -> bool:
    """True if every occurrence of phrase is within 200 chars of a disqualifier."""
    lower = text.lower()
    search = phrase.lower()
    idx = lower.find(search)
    while idx != -1:
        window_start = max(0, idx - 200)
        window_end = min(len(text), idx + len(phrase) + 200)
        window = text[window_start:window_end]
        if not _DISQUALIFIERS.search(window):
            return False
        idx = lower.find(search, idx + 1)
    return True


def test_unsupported_phrases_only_with_disqualifier() -> None:
    for rel in _DELIVERY_KIT_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for phrase in _UNSUPPORTED_PHRASES:
            if phrase.lower() in text.lower():
                assert _phrase_has_disqualifier(text, phrase), (
                    f"Phrase '{phrase}' in {rel} without disqualifying context"
                )


# ---------------------------------------------------------------------------
# Structural checks on key files
# ---------------------------------------------------------------------------


def test_delivery_checklist_has_five_sections() -> None:
    text = _read("docs/demo/customer_demo_delivery_checklist.md")
    for section in ("24 Hours", "1 Hour", "10 Minutes", "During", "After"):
        assert section in text, f"Missing section '{section}' in checklist"


def test_5min_script_has_all_time_blocks() -> None:
    text = _read("docs/demo/customer_demo_5min_script.md")
    assert "00:00" in text
    assert "04:30" in text or "04:00" in text


def test_faq_has_minimum_questions() -> None:
    text = _read("docs/demo/customer_demo_faq.md")
    # Verify at least 15 numbered questions exist
    matches = re.findall(r"^\*\*\d+\.", text, re.MULTILINE)
    assert len(matches) >= 15, f"Expected ≥15 FAQ entries, found {len(matches)}"


def test_positioning_guide_has_three_sections() -> None:
    text = _read("docs/demo/customer_demo_positioning.md")
    assert "SAY CONFIDENTLY" in text
    assert "SAY WITH QUALIFICATION" in text
    assert "DO NOT CLAIM" in text


def test_fallback_has_scenario_a_and_f() -> None:
    text = _read("docs/demo/customer_demo_fallback.md")
    assert "Scenario A" in text or "launcher fails" in text.lower()
    assert "Scenario F" in text or "demo should be stopped" in text.lower()


def test_discovery_questions_minimum_count() -> None:
    text = _read("docs/demo/customer_discovery_questions.md")
    # Count lines starting with a list bullet or number
    items = re.findall(r"^[-*]\s+\S|^\d+\.\s+\S", text, re.MULTILINE)
    assert len(items) >= 20, (
        f"Expected ≥20 discovery questions, found {len(items)}"
    )
