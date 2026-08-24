"""Unit tests for the origlyph.cad public API surface (Stage 1C)."""
import importlib

import origlyph.cad as cad_module

EXPECTED_EXPORTS = {
    "BoundReference",
    "bind_reference",
    "bind_references",
    "bind_datum_constraint",
    "bind_datum_reference_frame",
    "evaluate_candidates",
    "CadFormat",
    "CadImporter",
    "CadImportError",
    "CadWarning",
    "CandidateEvaluation",
    "DomainIdentity",
    "DuplicateNeutralEntityError",
    "DuplicateSourceEntityError",
    "FunctionalRelevanceDeclaration",
    "InvalidSourceIdentityError",
    "NeutralEntityEntry",
    "NeutralEntityIdentity",
    "NeutralEntityKind",
    "NeutralModel",
    "OriglyphCadError",
    "SourceDocumentIdentity",
    "SourceEntityIdentity",
    "SourceToNeutralMapping",
    "SourceUnitSystem",
    "UnsupportedCadFormatError",
    "UnsupportedContent",
    "UnsupportedSourceUnitError",
}


def test_import_origlyph_cad_succeeds() -> None:
    module = importlib.import_module("origlyph.cad")
    assert module is cad_module


def test_public_names_resolve() -> None:
    for name in EXPECTED_EXPORTS:
        assert getattr(cad_module, name) is not None


def test_all_is_exactly_the_public_surface() -> None:
    assert set(cad_module.__all__) == EXPECTED_EXPORTS
    assert len(cad_module.__all__) == len(set(cad_module.__all__))


def test_private_helpers_are_not_exported() -> None:
    # GeometryValue is an internal helper of origlyph.cad.model that must not
    # be re-exported through the package public API.
    assert "GeometryValue" not in cad_module.__all__
    for name in cad_module.__all__:
        assert not name.startswith("_")


def test_no_kernel_or_parser_exports() -> None:
    for name in ("Kernel", "StepParser", "BRepTopology", "Persistence"):
        assert name not in cad_module.__all__
        assert not hasattr(cad_module, name)