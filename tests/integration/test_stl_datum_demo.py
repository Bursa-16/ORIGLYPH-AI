"""Integration tests for the Stage 13A STL -> datum demo runner.

These tests exercise the demo runner's user-facing behavior (CLI contract,
printed report, exit codes) through the real production pipeline
(STL import -> candidate extraction -> binding -> demo 3-2-1 DRF). The
StlImporter parser internals are covered by tests/unit/cad/test_stl_importer.py
and are deliberately not duplicated here.
"""

from __future__ import annotations

import importlib.util
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from origlyph._version import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "stl_datum_demo.py"


@pytest.fixture(scope="module")
def demo_main() -> Callable[..., int]:
    spec = importlib.util.spec_from_file_location("stl_datum_demo", DEMO_PATH)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


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


def _write(tmp_path: Path, name: str, payload: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def _three_facet_ascii() -> bytes:
    return _ascii(
        _facet_text(*_TRI_A), _facet_text(*_TRI_B), _facet_text(*_TRI_C)
    )


# 1. ASCII STL demo succeeds.
def test_ascii_stl_demo_succeeds(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "part.stl", _three_facet_ascii())
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Origlyph STL Datum Demo" in out
    assert f"Origlyph version: {__version__}" in out
    assert "Declared STL units: mm" in out
    assert "No automatic unit inference or conversion is performed." in out
    assert "Valid planar facets: 3" in out
    assert "Candidates: 3 (skipped: 0)" in out


# 2. Binary STL demo succeeds.
def test_binary_stl_demo_succeeds(tmp_path, capsys, demo_main) -> None:
    payload = _binary(
        _binary_facet(_TRI_A, _UP_Z),
        _binary_facet(_TRI_B, _UP_Z),
        _binary_facet(_TRI_C, _UP_Z),
    )
    path = _write(tmp_path, "part.stl", payload)
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Valid planar facets: 3" in out
    assert "Candidates: 3 (skipped: 0)" in out
    assert "Sequence: 1 -> 2 -> 3 (3-2-1)" in out


# 3. Nonexistent file fails.
def test_nonexistent_file_fails(tmp_path, capsys, demo_main) -> None:
    code = demo_main([str(tmp_path / "missing.stl")])
    captured = capsys.readouterr()
    assert code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


# 4. Wrong extension fails.
def test_wrong_extension_fails(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "part.step", _ascii(_facet_text(*_TRI_A)))
    code = demo_main([str(path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "unsupported file extension" in captured.err
    assert captured.out == ""


# 5. A directory passed instead of a file fails.
def test_directory_passed_fails(tmp_path, capsys, demo_main) -> None:
    code = demo_main([str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "not a regular file" in captured.err
    assert captured.out == ""


# 6. Malformed ASCII STL fails closed with a concise error.
def test_malformed_ascii_stl_fails(tmp_path, capsys, demo_main) -> None:
    path = _write(
        tmp_path,
        "broken.stl",
        b"solid part\nfacet normal 0 0 1\nendfacet\nendsolid part\n",
    )
    code = demo_main([str(path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "error: STL import failed" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


# 7. Truncated binary STL fails.
def test_truncated_binary_stl_fails(tmp_path, capsys, demo_main) -> None:
    facet = _binary_facet(_TRI_A, _UP_Z)
    payload = b"demo".ljust(80, b"\x00") + struct.pack("<I", 2) + facet
    path = _write(tmp_path, "truncated.stl", payload)
    code = demo_main([str(path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "error: STL import failed" in captured.err
    assert captured.out == ""


# 8. One valid facet: import/candidate summary, graceful no-DRF message.
def test_one_facet_demo_summary(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "one.stl", _ascii(_facet_text(*_TRI_A)))
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert f"Origlyph version: {__version__}" in out
    assert "Valid planar facets: 1" in out
    assert "Candidates: 1 (skipped: 0)" in out
    assert "Bound reference" in out
    assert "fewer than 3 valid planar candidates" in out
    assert "Datum Reference Frame Demo" not in out


# 9. Three valid facets produce the PRIMARY/SECONDARY/TERTIARY demo DRF.
def test_three_facets_demo_drf(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "PRIMARY:" in out
    assert "SECONDARY:" in out
    assert "TERTIARY:" in out
    assert "Sequence: 1 -> 2 -> 3 (3-2-1)" in out
    assert "Constrained DOF: 6 of 6" in out
    assert "Fully located: True" in out
    assert "Demo selection only" in out


# 10. Fewer than 3 facets is handled gracefully.
def test_fewer_than_three_facets_graceful(tmp_path, capsys, demo_main) -> None:
    path = _write(
        tmp_path, "two.stl", _ascii(_facet_text(*_TRI_A), _facet_text(*_TRI_B))
    )
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Valid planar facets: 2" in out
    assert "fewer than 3 valid planar candidates" in out
    assert "Datum Reference Frame Demo" not in out


# 11. A degenerate facet is visibly surfaced, not hidden.
def test_degenerate_facet_surfaced(tmp_path, capsys, demo_main) -> None:
    degenerate = _facet_text("0 0 0", "1 0 0", "2 0 0")
    path = _write(
        tmp_path, "degenerate.stl", _ascii(_facet_text(*_TRI_A), degenerate)
    )
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Warnings: 1" in out
    assert "[DEGENERATE_FACET]" in out
    assert "degenerate facet (facet-1)" in out
    assert "Unsupported facets: 1" in out
    assert "Valid planar facets: 1" in out


# 12. The stored STL normal is visibly labelled non-authoritative.
def test_stored_normal_non_authoritative(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "normal.stl", _ascii(_facet_text(*_TRI_A)))
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "STL diagnostic normal (stored in file): (0.0, 0.0, 1.0)" in out
    assert "Authority: NON-AUTHORITATIVE" in out
    assert "winding-derived face normal" in out


# 13. Output explicitly states no ranking/recommendation occurred.
def test_no_ranking_statement(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "three.stl", _three_facet_ascii())
    code = demo_main([str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "did not rank" in out
    assert "recommendation" in out
    assert "NOT automatic datum selection" in out


# 14. Exit codes are deterministic; identical runs produce identical output.
def test_deterministic_exit_codes(tmp_path, capsys, demo_main) -> None:
    path = _write(tmp_path, "part.stl", _three_facet_ascii())
    first_code = demo_main([str(path)])
    first_output = capsys.readouterr().out
    second_code = demo_main([str(path)])
    second_output = capsys.readouterr().out
    assert first_code == 0
    assert second_code == 0
    assert first_output == second_output
    bad_code = demo_main([str(tmp_path / "nope.stl")])
    capsys.readouterr()
    assert bad_code == 1
