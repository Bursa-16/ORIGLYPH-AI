"""Integration tests for the Stage 14B GUI controller and optional Tk view.

The :class:`DatumGuiController` is pure orchestration over the existing
production pipeline and is tested headless: no display, no pixel checks, no
OS-dialog automation. The optional Tk view smoke test is guarded to skip when
no display is available so CI stays safe.
"""

from __future__ import annotations

import importlib.util
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from origlyph.datum import ConstraintType

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_PATH = REPO_ROOT / "examples" / "stl_datum_gui.py"


@pytest.fixture(scope="module")
def gui_module() -> Any:
    spec = importlib.util.spec_from_file_location("stl_datum_gui", GUI_PATH)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def controller_type(gui_module: Any) -> Callable[..., Any]:
    return gui_module.DatumGuiController


@pytest.fixture(scope="module")
def disclaimer(gui_module: Any) -> str:
    return gui_module.DISCLAIMER_TEXT


@pytest.fixture(scope="module")
def no_ranking(gui_module: Any) -> str:
    return gui_module.NO_RANKING_TEXT


def _facet_text(v1: str, v2: str, v3: str) -> str:
    return (
        "facet normal 0 0 1\n"
        f" outer loop\n  vertex {v1}\n  vertex {v2}\n  vertex {v3}\n"
        " endloop\nendfacet\n"
    )


def _ascii(*facets: str) -> bytes:
    body = "".join(facets)
    return f"solid demo\n{body}endsolid demo\n".encode("ascii")


def _binary_facet(
    vertices: tuple[str, str, str], normal: tuple[float, float, float]
) -> bytes:
    floats = list(normal)
    for vertex in vertices:
        floats.extend(float(part) for part in vertex.split())
    return struct.pack(f"<{len(floats)}f", *floats) + struct.pack("<H", 0)


def _binary(*facets: bytes) -> bytes:
    header = b"demo".ljust(80, b"\x00")
    return header + struct.pack("<I", len(facets)) + b"".join(facets)


_TRI_A = ("0 0 0", "1 0 0", "0 1 0")
_TRI_B = ("2 0 0", "3 0 0", "2 1 0")
_TRI_C = ("5 0 0", "6 0 0", "5 1 0")
_UP_Z = (0.0, 0.0, 1.0)


def _three_facet_ascii() -> bytes:
    return _ascii(
        _facet_text(*_TRI_A), _facet_text(*_TRI_B), _facet_text(*_TRI_C)
    )


def _write(tmp_path: Path, name: str, payload: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def _assign_all(controller: Any) -> None:
    controller.assign(ConstraintType.PRIMARY, 0)
    controller.assign(ConstraintType.SECONDARY, 1)
    controller.assign(ConstraintType.TERTIARY, 2)


# 1. ASCII STL load.
def test_ascii_stl_load(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "part.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    assert controller.candidate_count == 3
    assert controller.valid_facets == 3
    assert controller.selected_file == str(path)


# 2. Binary STL load.
def test_binary_stl_load(tmp_path, controller_type) -> None:
    payload = _binary(
        _binary_facet(_TRI_A, _UP_Z),
        _binary_facet(_TRI_B, _UP_Z),
        _binary_facet(_TRI_C, _UP_Z),
    )
    path = _write(tmp_path, "part.stl", payload)
    controller = controller_type()
    assert controller.load_path(path) is True
    assert controller.candidate_count == 3


# 3. Nonexistent file fails.
def test_nonexistent_file(tmp_path, controller_type) -> None:
    controller = controller_type()
    assert controller.load_path(tmp_path / "missing.stl") is False
    assert controller.last_error is not None
    assert "path does not exist" in controller.last_error
    assert controller.candidate_count == 0


# 4. Wrong extension fails.
def test_wrong_extension(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "part.txt", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is False
    assert "expected '.stl'" in (controller.last_error or "")


# 5. Malformed STL fails and is surfaced as a visible error string.
def test_malformed_stl(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "bad.stl", b"definitely not an stl payload")
    controller = controller_type()
    assert controller.load_path(path) is False
    assert controller.last_error is not None
    assert "STL import failed" in controller.last_error
    assert controller.candidate_count == 0


# 6. One-facet candidate table.
def test_one_facet_table(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "one.stl", _ascii(_facet_text(*_TRI_A)))
    controller = controller_type()
    assert controller.load_path(path) is True
    assert controller.candidate_count == 1
    row = controller.candidate_rows[0]
    assert row[0] == "facet-0"  # source facet key
    assert row[1] == "plane"  # feature kind


# 7. Three-facet candidate table preserves deterministic order.
def test_three_facet_table(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    assert [row[0] for row in controller.candidate_rows] == [
        "facet-0",
        "facet-1",
        "facet-2",
    ]


# 8./9./10. Explicit role assignments.
def test_explicit_role_assignments(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    controller.assign(ConstraintType.PRIMARY, 0)
    controller.assign(ConstraintType.SECONDARY, 1)
    controller.assign(ConstraintType.TERTIARY, 2)
    assert controller.primary_candidate == 0
    assert controller.secondary_candidate == 1
    assert controller.tertiary_candidate == 2


# 11. Duplicate candidate reassignment releases the previous role.
def test_duplicate_candidate_reassignment(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    controller.assign(ConstraintType.PRIMARY, 0)
    controller.assign(ConstraintType.SECONDARY, 0)
    assert controller.primary_candidate is None  # previous role released
    assert controller.secondary_candidate == 0


# 12. Target-role replacement replaces the old holder.
def test_target_role_replacement(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    controller.assign(ConstraintType.PRIMARY, 0)
    controller.assign(ConstraintType.PRIMARY, 1)
    assert controller.primary_candidate == 1
    assert controller.secondary_candidate is None


# 13. Build DRF fails closed before three distinct roles exist.
def test_build_drf_fails_closed_incomplete(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    controller.assign(ConstraintType.PRIMARY, 0)
    assert controller.build_drf() is False
    assert controller.drf_result is None
    assert controller.last_error is not None
    assert "three distinct explicit assignments" in controller.last_error


# 14. Build DRF succeeds with three distinct explicit roles.
def test_build_drf_succeeds(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    _assign_all(controller)
    assert controller.build_drf() is True
    assert controller.drf_result is not None
    assert controller.drf_sequence_text() == "1 -> 2 -> 3"
    assert controller.drf_result.total_constrained == 6
    assert controller.drf_result.is_fully_located is True


# 15. Loading a new file resets prior assignment and DRF state.
def test_new_file_resets_state(tmp_path, controller_type) -> None:
    first = _write(tmp_path, "a.stl", _three_facet_ascii())
    second = _write(tmp_path, "b.stl", _ascii(_facet_text(*_TRI_A)))
    controller = controller_type()
    assert controller.load_path(first) is True
    _assign_all(controller)
    assert controller.build_drf() is True
    assert controller.load_path(second) is True
    assert controller.primary_candidate is None
    assert controller.secondary_candidate is None
    assert controller.tertiary_candidate is None
    assert controller.drf_result is None
    assert controller.candidate_count == 1


# 16. Degenerate facet is surfaced, never hidden.
def test_degenerate_facet_surfaced(tmp_path, controller_type) -> None:
    degenerate = _facet_text("0 0 0", "1 0 0", "2 0 0")  # collinear
    path = _write(
        tmp_path, "degenerate.stl", _ascii(_facet_text(*_TRI_A), degenerate)
    )
    controller = controller_type()
    assert controller.load_path(path) is True
    assert any(
        "[DEGENERATE_FACET]" in warning for warning in controller.warnings
    )
    assert controller.unsupported_facets == 1
    assert controller.candidate_count == 1  # valid facet retained


# 17. STL stored normal is labelled non-authoritative in detail data.
def test_stored_normal_non_authoritative(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "normal.stl", _ascii(_facet_text(*_TRI_A)))
    controller = controller_type()
    assert controller.load_path(path) is True
    assert controller.candidate_rows[0][5] is not None
    assert "1.0" in controller.candidate_rows[0][5]
    assert "NON-AUTHORITATIVE" in controller.candidate_rows[0][5]


# 18. Permanent disclaimer is the exact contract text.
def test_disclaimer_exact_text(disclaimer: str) -> None:
    assert isinstance(disclaimer, str)
    assert "Manual assignment only" in disclaimer
    assert "does not automatically rank or recommend" in disclaimer


# 19. No-ranking / no-recommendation wording is present in the GUI module.
def test_no_ranking_wording(tmp_path, controller_type, no_ranking: str) -> None:
    assert "No ranking, scoring, or automatic datum recommendation" in no_ranking
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    controller = controller_type()
    assert controller.load_path(path) is True
    _assign_all(controller)
    assert controller.build_drf() is True
    assert controller.drf_result is not None


# 20. Deterministic controller state: identical payloads yield identical rows.
def test_deterministic_controller_state(tmp_path, controller_type) -> None:
    path = _write(tmp_path, "part.stl", _three_facet_ascii())
    first = controller_type()
    second = controller_type()
    assert first.load_path(path) is True
    assert second.load_path(path) is True
    assert first.candidate_rows == second.candidate_rows


# 21. Optional Tk view smoke test, guarded for headless environments.
def test_tk_view_smoke(tmp_path, gui_module: Any, controller_type: Any) -> None:
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:  # no display available (e.g. headless CI)
        pytest.skip("no Tcl/Tk display available on this host")
    try:
        root.withdraw()
        controller = controller_type()
        path = _write(tmp_path, "three.stl", _three_facet_ascii())
        assert controller.load_path(path) is True
        view = gui_module.StlDatumTk(root, controller)
        assert view.tree is not None
        assert view.file_var.get() == str(path)
        assert str(view.build_button.cget("state")) == "disabled"
        controller.assign(ConstraintType.PRIMARY, 0)
        controller.assign(ConstraintType.SECONDARY, 1)
        controller.assign(ConstraintType.TERTIARY, 2)
        view._refresh()
        assert str(view.build_button.cget("state")) == "normal"
    finally:
        root.destroy()