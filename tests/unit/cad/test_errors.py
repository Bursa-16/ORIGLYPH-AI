"""Unit tests for the origlyph.cad exception contract (Stage 1C)."""
import pytest

from origlyph.cad import (
    CadImportError,
    CadWarning,
    DuplicateNeutralEntityError,
    DuplicateSourceEntityError,
    InvalidSourceIdentityError,
    OriglyphCadError,
    UnsupportedCadFormatError,
    UnsupportedSourceUnitError,
)
from origlyph.cad.identity import SourceUnitSystem


def test_exception_hierarchy_is_explicit() -> None:
    assert issubclass(CadImportError, OriglyphCadError)
    assert issubclass(UnsupportedCadFormatError, CadImportError)
    assert issubclass(UnsupportedSourceUnitError, OriglyphCadError)
    assert issubclass(InvalidSourceIdentityError, OriglyphCadError)
    assert issubclass(DuplicateSourceEntityError, OriglyphCadError)
    assert issubclass(DuplicateNeutralEntityError, OriglyphCadError)


def test_unsupported_format_is_fatal() -> None:
    # A fatal import error is catchable at every level of the hierarchy.
    with pytest.raises(UnsupportedCadFormatError):
        raise UnsupportedCadFormatError("step parser unavailable")
    assert issubclass(UnsupportedCadFormatError, CadImportError)


def test_unsupported_unit_fails_closed() -> None:
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="furlong", angle_unit="rad")
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="mm", angle_unit="cubits")


def test_duplicate_mapping_errors_are_explicit() -> None:
    assert DuplicateSourceEntityError is not DuplicateNeutralEntityError
    assert issubclass(DuplicateSourceEntityError, OriglyphCadError)
    assert issubclass(DuplicateNeutralEntityError, OriglyphCadError)


def test_warning_is_not_a_fatal_exception() -> None:
    warning = CadWarning(code="W-001", message="mesh cleanup")
    assert isinstance(warning, CadWarning)
    assert not isinstance(warning, Exception)
    assert not isinstance(warning, OriglyphCadError)