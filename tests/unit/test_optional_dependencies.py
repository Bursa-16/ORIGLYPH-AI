"""Tests for optional B-Rep dependency configuration (Stage 22D.2).

Verifies that:
- pyproject.toml declares the brep extra correctly (skipped on Python <3.11)
- core installation does not pull in the OCP kernel
- origlyph imports work when the OCP kernel is absent
- the STEP adapter fails closed when the kernel is absent
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PYPROJECT_PATH = Path(__file__).parent.parent.parent / "pyproject.toml"
STEP_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "cad" / "simple_box.step"
)
APPROVED_BREP_PACKAGE = "cadquery-ocp-novtk"
APPROVED_LOWER_BOUND = "8.0.1.1.0"
FORBIDDEN_BREP_PACKAGES = frozenset(
    {"cadquery", "build123d", "pythonocc-core", "cadquery-ocp"}
)

requires_tomllib = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="tomllib requires Python >=3.11",
)


def _load_pyproject() -> dict:
    import tomllib  # local import — stdlib on Python 3.11+

    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Package metadata — brep optional-dependency configuration
# ---------------------------------------------------------------------------


@requires_tomllib
def test_optional_dependencies_section_exists() -> None:
    data = _load_pyproject()
    assert "optional-dependencies" in data["project"]


@requires_tomllib
def test_brep_extra_exists() -> None:
    data = _load_pyproject()
    extras = data["project"]["optional-dependencies"]
    assert "brep" in extras, (
        "brep extra not found in [project.optional-dependencies]"
    )


@requires_tomllib
def test_approved_package_in_brep() -> None:
    data = _load_pyproject()
    brep_reqs = data["project"]["optional-dependencies"]["brep"]
    names = [
        r.split(">=")[0].split(">")[0].split("==")[0].split(";")[0].strip()
        for r in brep_reqs
    ]
    assert APPROVED_BREP_PACKAGE in names, (
        f"{APPROVED_BREP_PACKAGE!r} not found in brep requirements: {brep_reqs}"
    )


@requires_tomllib
def test_brep_package_not_in_core_dependencies() -> None:
    data = _load_pyproject()
    core_deps = data["project"].get("dependencies", [])
    combined = " ".join(core_deps).lower()
    assert APPROVED_BREP_PACKAGE.lower() not in combined, (
        f"{APPROVED_BREP_PACKAGE!r} must not appear in core dependencies"
    )


@requires_tomllib
def test_no_competing_brep_packages_in_brep_extra() -> None:
    import re

    data = _load_pyproject()
    brep_reqs = data["project"]["optional-dependencies"]["brep"]
    brep_names = {
        re.split(r"[>=<!;\s]", r.strip())[0].strip().lower()
        for r in brep_reqs
    }
    for pkg in FORBIDDEN_BREP_PACKAGES:
        assert pkg.lower() not in brep_names, (
            f"Forbidden B-Rep package {pkg!r} found in brep extra"
        )


@requires_tomllib
def test_brep_version_lower_bound() -> None:
    data = _load_pyproject()
    brep_reqs = data["project"]["optional-dependencies"]["brep"]
    pkg_req = next(
        r for r in brep_reqs if APPROVED_BREP_PACKAGE.lower() in r.lower()
    )
    assert APPROVED_LOWER_BOUND in pkg_req, (
        f"Lower bound {APPROVED_LOWER_BOUND!r} not in requirement: {pkg_req!r}"
    )


@requires_tomllib
def test_brep_version_upper_bound() -> None:
    data = _load_pyproject()
    brep_reqs = data["project"]["optional-dependencies"]["brep"]
    pkg_req = next(
        r for r in brep_reqs if APPROVED_BREP_PACKAGE.lower() in r.lower()
    )
    assert "<9" in pkg_req, (
        f"Upper bound <9 not found in requirement: {pkg_req!r}"
    )


@requires_tomllib
def test_brep_python_version_marker() -> None:
    data = _load_pyproject()
    brep_reqs = data["project"]["optional-dependencies"]["brep"]
    pkg_req = next(
        r for r in brep_reqs if APPROVED_BREP_PACKAGE.lower() in r.lower()
    )
    assert "python_version" in pkg_req and "3.11" in pkg_req, (
        f"Python version marker >=3.11 not found in requirement: {pkg_req!r}"
    )


@requires_tomllib
def test_core_python_requirement_unchanged() -> None:
    data = _load_pyproject()
    requires_python = data["project"]["requires-python"]
    assert requires_python == ">=3.10", (
        f"Core requires-python changed: {requires_python!r} (must remain '>=3.10')"
    )


# ---------------------------------------------------------------------------
# Core imports work without OCP present
# ---------------------------------------------------------------------------


def test_origlyph_top_level_import() -> None:
    """origlyph top-level import works; no OCP at module level."""
    import origlyph

    assert hasattr(origlyph, "__version__")


def test_origlyph_cad_import() -> None:
    """origlyph.cad import works; step_kernel_adapter is not in public API."""
    import origlyph.cad

    assert hasattr(origlyph.cad, "NeutralModel")
    assert hasattr(origlyph.cad, "CadFormat")
    assert hasattr(origlyph.cad, "CanonicalTopologyModel")
    assert not hasattr(origlyph.cad, "StepKernelAdapter"), (
        "StepKernelAdapter must not be exported from origlyph.cad public API"
    )


def test_canonical_topology_model_usable_without_ocp() -> None:
    """CanonicalTopologyModel can be constructed without the OCP kernel."""
    from origlyph.cad.topology import CanonicalTopologyModel

    model = CanonicalTopologyModel()
    assert model.source is None
    assert len(model.vertices) == 0
    assert len(model.solids) == 0


def test_stl_importer_usable_without_ocp() -> None:
    """StlImporter has zero external dependencies — usable with no kernel."""
    from origlyph.cad.identity import CadFormat
    from origlyph.cad.stl import StlImporter

    importer = StlImporter()
    assert CadFormat.STL in importer.supported_formats


# ---------------------------------------------------------------------------
# STEP adapter fails closed when OCP kernel absent
# ---------------------------------------------------------------------------


def test_step_adapter_fails_closed_without_kernel() -> None:
    """StepKernelAdapter raises StepKernelUnavailableError when OCP absent."""
    from origlyph.cad.identity import (
        CadFormat,
        SourceDocumentIdentity,
        SourceUnitSystem,
    )
    from origlyph.cad.step_kernel_adapter import (
        StepKernelAdapter,
        StepKernelUnavailableError,
    )

    source = SourceDocumentIdentity(
        source_id="absence-test",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="simple_box.step",
    )
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        adapter = StepKernelAdapter(STEP_FIXTURE)
        with pytest.raises(StepKernelUnavailableError):
            adapter.to_canonical_topology(source)


def test_step_kernel_unavailable_error_subclass() -> None:
    """StepKernelUnavailableError is a subclass of OriglyphCadError."""
    from origlyph.cad.exceptions import OriglyphCadError
    from origlyph.cad.step_kernel_adapter import StepKernelUnavailableError

    assert issubclass(StepKernelUnavailableError, OriglyphCadError)
