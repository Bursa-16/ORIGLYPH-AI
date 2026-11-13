"""Unit tests for the controlled STEP dispatch (Stage 22E).

Covers dispatch logic, extension handling, dependency guard, and format
validation without requiring the OCP kernel for most cases.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from origlyph.cad.exceptions import CadImportError, UnsupportedCadFormatError
from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.cad.step_kernel_adapter import StepKernelUnavailableError
from origlyph.cad.step_loader import load_step_topology

OCP_PRESENT: bool = importlib.util.find_spec("OCP") is not None

skip_if_no_ocp = pytest.mark.skipif(
    not OCP_PRESENT, reason="OCP/cadquery-ocp-novtk not installed"
)

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "cad"
SIMPLE_BOX_STEP = FIXTURE_DIR / "simple_box.step"


def _make_source(
    source_id: str = "dispatch-test-001",
    filename: str = "part.step",
) -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename=filename,
    )


# ---------------------------------------------------------------------------
# A. .step extension dispatch
# ---------------------------------------------------------------------------


def test_step_extension_accepted(tmp_path: Path) -> None:
    """.step extension passes dispatch and reaches file/kernel check."""
    f = tmp_path / "part.step"
    f.write_bytes(b"")
    source = _make_source(filename="part.step")
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


# ---------------------------------------------------------------------------
# B. .stp extension dispatch
# ---------------------------------------------------------------------------


def test_stp_extension_accepted(tmp_path: Path) -> None:
    """.stp extension passes dispatch and reaches file/kernel check."""
    f = tmp_path / "part.stp"
    f.write_bytes(b"")
    source = _make_source(filename="part.stp")
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


# ---------------------------------------------------------------------------
# C. Case-insensitive extension handling
# ---------------------------------------------------------------------------


def test_uppercase_step_extension_accepted(tmp_path: Path) -> None:
    """.STEP (upper-case) passes dispatch validation."""
    f = tmp_path / "PART.STEP"
    f.write_bytes(b"")
    source = _make_source(filename="PART.STEP")
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


def test_uppercase_stp_extension_accepted(tmp_path: Path) -> None:
    """.STP (upper-case) passes dispatch validation."""
    f = tmp_path / "PART.STP"
    f.write_bytes(b"")
    source = _make_source(filename="PART.STP")
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


def test_mixed_case_step_extension_accepted(tmp_path: Path) -> None:
    """.Step (mixed-case) passes dispatch validation."""
    f = tmp_path / "part.Step"
    f.write_bytes(b"")
    source = _make_source(filename="part.Step")
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


# ---------------------------------------------------------------------------
# D. Missing brep extra — fail closed
# ---------------------------------------------------------------------------


def test_missing_brep_raises_step_kernel_unavailable(tmp_path: Path) -> None:
    """When OCP is absent, load_step_topology raises StepKernelUnavailableError."""
    f = tmp_path / "part.step"
    f.write_bytes(b"")
    source = _make_source()
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError):
            load_step_topology(f, source)


def test_missing_brep_error_mentions_brep_extra(tmp_path: Path) -> None:
    """Error message for absent OCP explicitly mentions the brep extra."""
    f = tmp_path / "part.step"
    f.write_bytes(b"")
    source = _make_source()
    with patch(
        "origlyph.cad.step_kernel_adapter._ocp_available", return_value=False
    ):
        with pytest.raises(StepKernelUnavailableError, match="brep"):
            load_step_topology(f, source)


def test_missing_brep_error_is_origlyph_error(tmp_path: Path) -> None:
    """StepKernelUnavailableError is an OriglyphCadError subclass."""
    from origlyph.cad.exceptions import OriglyphCadError

    assert issubclass(StepKernelUnavailableError, OriglyphCadError)


# ---------------------------------------------------------------------------
# F. Missing file — fail closed
# ---------------------------------------------------------------------------


def test_missing_file_raises_cad_import_error() -> None:
    """Non-existent .step file raises CadImportError."""
    source = _make_source()
    with pytest.raises(CadImportError, match="not found"):
        load_step_topology(FIXTURE_DIR / "does_not_exist.step", source)


def test_missing_stp_file_raises_cad_import_error(tmp_path: Path) -> None:
    """Non-existent .stp file raises CadImportError."""
    source = _make_source(filename="missing.stp")
    with pytest.raises(CadImportError):
        load_step_topology(tmp_path / "missing.stp", source)


# ---------------------------------------------------------------------------
# G. Unknown extension — fail closed
# ---------------------------------------------------------------------------


def test_unknown_extension_raises_unsupported_format() -> None:
    """Unknown file extension raises UnsupportedCadFormatError."""
    source = _make_source(filename="part.iges")
    with pytest.raises(UnsupportedCadFormatError, match=".iges"):
        load_step_topology(Path("part.iges"), source)


def test_stl_extension_raises_unsupported_format() -> None:
    """.stl extension raises UnsupportedCadFormatError from load_step_topology."""
    source = _make_source(filename="part.stl")
    with pytest.raises(UnsupportedCadFormatError):
        load_step_topology(Path("part.stl"), source)


def test_no_extension_raises_unsupported_format() -> None:
    """File with no extension raises UnsupportedCadFormatError."""
    source = _make_source(filename="part")
    with pytest.raises(UnsupportedCadFormatError):
        load_step_topology(Path("part"), source)


def test_dxf_extension_raises_unsupported_format() -> None:
    """.dxf extension raises UnsupportedCadFormatError."""
    source = _make_source(filename="drawing.dxf")
    with pytest.raises(UnsupportedCadFormatError):
        load_step_topology(Path("drawing.dxf"), source)


# ---------------------------------------------------------------------------
# Source format validation
# ---------------------------------------------------------------------------


def test_wrong_source_format_raises_unsupported(tmp_path: Path) -> None:
    """source.format != CadFormat.STEP raises UnsupportedCadFormatError."""
    f = tmp_path / "part.step"
    f.write_bytes(b"")
    source = SourceDocumentIdentity(
        source_id="wrong-format",
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit="mm", angle_unit="rad"),
        original_filename="part.step",
    )
    with pytest.raises(UnsupportedCadFormatError, match="CadFormat.STEP"):
        load_step_topology(f, source)


# ---------------------------------------------------------------------------
# Public API visibility
# ---------------------------------------------------------------------------


def test_load_step_topology_in_cad_public_api() -> None:
    """load_step_topology is accessible from origlyph.cad."""
    import origlyph.cad as cad_pkg

    assert hasattr(cad_pkg, "load_step_topology")
    assert "load_step_topology" in cad_pkg.__all__


def test_step_kernel_adapter_still_not_in_cad_api() -> None:
    """StepKernelAdapter is still NOT exposed from origlyph.cad."""
    import origlyph.cad as cad_pkg

    assert not hasattr(cad_pkg, "StepKernelAdapter")
    assert "StepKernelAdapter" not in cad_pkg.__all__


# ---------------------------------------------------------------------------
# N. STL behavior unchanged
# ---------------------------------------------------------------------------


def test_stl_importer_still_importable() -> None:
    """Stage 22E does not affect StlImporter availability."""
    from origlyph.cad import StlImporter

    importer = StlImporter()
    assert CadFormat.STL in importer.supported_formats


def test_stl_importer_does_not_accept_step() -> None:
    """StlImporter still rejects STEP format."""
    from origlyph.cad import StlImporter

    importer = StlImporter()
    source = _make_source()
    assert not importer.can_import(source)
