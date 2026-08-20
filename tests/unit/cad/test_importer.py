"""Unit tests for the CadImporter Protocol boundary (Stage 1C)."""
import typing

from origlyph.cad import CadImporter
from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem


class _StepImporter:
    """Structural stand-in for a future STEP adapter (test only)."""

    importer_id = "test-step"
    importer_version = "0.1.0"
    supported_formats = frozenset({CadFormat.STEP})

    def can_import(self, source_document) -> bool:
        return source_document.format == CadFormat.STEP

    def import_document(self, source_document):
        # Real importers return a NeutralModel; this stand-in only proves the
        # protocol accepts structurally-compatible adapters.
        raise NotImplementedError


class _MissingImportDocument:
    importer_id = "broken"
    importer_version = "0.0.1"
    supported_formats = frozenset({CadFormat.STEP})


class _NoImportDocumentMethod:
    importer_id = "partial"
    importer_version = "0.0.1"
    supported_formats = frozenset()

    def can_import(self, source_document) -> bool:
        return False


def test_cad_importer_is_a_protocol() -> None:
    assert issubclass(CadImporter, typing.Protocol)
    assert hasattr(CadImporter, "_is_protocol")


def test_cad_importer_is_runtime_checkable() -> None:
    assert isinstance(_StepImporter(), CadImporter)


def test_no_concrete_parser_implementation() -> None:
    # CadImporter remains an interface only: the module exports exactly the
    # Protocol and nothing else (no parser, SDK, or kernel resolution).
    import origlyph.cad.importer as importer_module

    assert importer_module.__all__ == ["CadImporter"]
    assert CadImporter.__module__ == "origlyph.cad.importer"
    assert isinstance(_StepImporter(), CadImporter)


def test_missing_method_fails_runtime_check() -> None:
    assert not isinstance(_MissingImportDocument(), CadImporter)
    assert not isinstance(_NoImportDocumentMethod(), CadImporter)


def test_importer_contract_members_exist() -> None:
    names = ("importer_id", "importer_version", "supported_formats")
    for name in names:
        assert hasattr(_StepImporter(), name)


def test_can_import_true_for_supported_format() -> None:
    doc = SourceDocumentIdentity(
        source_id="doc",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )
    assert _StepImporter().can_import(doc) is True


def test_can_import_false_for_unsupported_format() -> None:
    doc = SourceDocumentIdentity(
        source_id="doc",
        format=CadFormat.DXF,
        unit_system=SourceUnitSystem(),
    )
    assert _StepImporter().can_import(doc) is False


def test_import_document_is_an_abstract_callable() -> None:
    # Import must always be a callable in the protocol; direct invocation
    # without an adapter is not possible (structural TypeError for bare object).
    assert callable(CadImporter.import_document)