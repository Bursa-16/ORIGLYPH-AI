"""Foundation architecture import tests for the Origlyph package."""

import importlib
import importlib.util

import pytest


def test_import_origlyph_succeeds() -> None:
    """The top-level ``origlyph`` package imports successfully."""
    module = importlib.import_module("origlyph")
    assert module is not None


def test_origlyph_version() -> None:
    """``origlyph`` exposes the canonical foundation version."""
    module = importlib.import_module("origlyph")
    assert module.__version__ == "0.1.0a1"


@pytest.mark.parametrize(
    "module_name",
    [
        "origlyph.core",
        "origlyph.geometry",
        "origlyph.datum",
        "origlyph.gdandt",
        "origlyph.tolerance",
        "origlyph.assembly",
        "origlyph.provenance",
        "origlyph.ai",
    ],
)
def test_top_level_packages_import(module_name: str) -> None:
    """Each approved top-level Origlyph package imports successfully."""
    module = importlib.import_module(module_name)
    assert module is not None


@pytest.mark.parametrize(
    "module_name",
    [
        "engineering",
        "origlyph_ai_core",
    ],
)
def test_deprecated_namespace_not_present(module_name: str) -> None:
    """Deprecated/unapproved namespaces are not importable as project packages."""
    assert importlib.util.find_spec(module_name) is None
