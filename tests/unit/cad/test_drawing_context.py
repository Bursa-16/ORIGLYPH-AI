"""Unit tests for the Stage 7C datum-feature declaration contract.

A datum feature label is NOT a datum role: ``label == "A"`` must never imply
PRIMARY/SECONDARY/TERTIARY, ranking, scoring, or acceptance. The structural
firewall tests below pin that shape.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect

import pytest

from origlyph.cad import (
    CadFormat,
    DatumFeatureDeclaration,
    DomainIdentity,
    DrawingDatumReferenceFrameDeclaration,
    FunctionalRelevanceDeclaration,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
)
from origlyph.cad import drawing_context as drawing_context_module


def _document() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="doc-1",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _target(key: str = "face-7") -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=_document(),
        source_entity_key=key,
        path=("body-A", key),
    )


def _declaration(**overrides):
    values = {
        "target": _target(),
        "label": "A",
        "transcriber": "engineer:j.doe",
        "drawing_reference": "DWG-100 rev B",
        "location": None,
    }
    values.update(overrides)
    return DatumFeatureDeclaration(**values)


def test_valid_declaration_constructs() -> None:
    declaration = _declaration()
    assert declaration.label == "A"
    assert declaration.transcriber == "engineer:j.doe"
    assert declaration.drawing_reference == "DWG-100 rev B"
    assert declaration.location is None


def test_field_names_and_order_exact() -> None:
    names = [field.name for field in dataclasses.fields(_declaration())]
    assert names == [
        "target",
        "label",
        "transcriber",
        "drawing_reference",
        "location",
    ]


def test_target_retained_verbatim() -> None:
    target = _target()
    declaration = _declaration(target=target)
    assert declaration.target is target


def test_target_must_be_source_entity_identity() -> None:
    with pytest.raises(TypeError):
        _declaration(target=DomainIdentity("face-7"))  # type: ignore[arg-type]
    generated_neutral = NeutralEntityIdentity(
        neutral_entity_key="gen-1",
        kind=NeutralEntityKind.SURFACE,
        generated=True,
    )
    with pytest.raises(TypeError):
        _declaration(target=generated_neutral)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _declaration(target="face-7")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _declaration(target=None)  # type: ignore[arg-type]


def test_label_must_be_string() -> None:
    with pytest.raises(TypeError):
        _declaration(label=42)  # type: ignore[arg-type]


def test_label_stripped() -> None:
    declaration = _declaration(label="  A  ")
    assert declaration.label == "A"


def test_blank_label_rejected() -> None:
    with pytest.raises(ValueError):
        _declaration(label="   ")


def test_label_case_preserved() -> None:
    assert _declaration(label="aBc").label == "aBc"
    assert _declaration(label="A").label == "A"


def test_internal_label_content_preserved() -> None:
    declaration = _declaration(label="  inner-plate 2  ")
    assert declaration.label == "inner-plate 2"


def test_transcriber_validation() -> None:
    with pytest.raises(TypeError):
        _declaration(transcriber=42)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _declaration(transcriber="   ")
    declaration = _declaration(transcriber="  engineer:j.doe  ")
    assert declaration.transcriber == "engineer:j.doe"


def test_drawing_reference_validation() -> None:
    with pytest.raises(TypeError):
        _declaration(drawing_reference=99)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _declaration(drawing_reference="   ")
    declaration = _declaration(drawing_reference="  DWG-100 rev B  ")
    assert declaration.drawing_reference == "DWG-100 rev B"


def test_location_none_retained() -> None:
    assert _declaration(location=None).location is None


def test_location_stripped() -> None:
    declaration = _declaration(location="  sheet 3, view B  ")
    assert declaration.location == "sheet 3, view B"


def test_blank_location_normalized_to_none() -> None:
    assert _declaration(location="   ").location is None


def test_non_string_non_none_location_rejected() -> None:
    with pytest.raises(TypeError):
        _declaration(location=7)  # type: ignore[arg-type]


def test_frozen_immutability() -> None:
    declaration = _declaration()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(declaration, "label", "B")  # noqa: B010


def test_value_equality_and_hash() -> None:
    target = _target()
    first = _declaration(target=target)
    second = _declaration(target=target)
    assert first == second
    assert hash(first) == hash(second)


def test_different_targets_remain_distinct_declarations() -> None:
    first = _declaration(target=_target(key="face-7"))
    second = _declaration(target=_target(key="face-9"))
    assert first != second


def test_document_provenance_reachable_through_target() -> None:
    declaration = _declaration()
    document = declaration.target.source_document
    assert document.source_id == "doc-1"
    assert document.format is CadFormat.STEP


def test_source_entity_path_retained() -> None:
    declaration = _declaration()
    assert declaration.target.path == ("body-A", "face-7")


def test_forbidden_semantic_fields_absent() -> None:
    names = {field.name for field in dataclasses.fields(_declaration())}
    assert names == {
        "target",
        "label",
        "transcriber",
        "drawing_reference",
        "location",
    }
    declaration = _declaration()
    for forbidden in (
        "constraint_type",
        "role",
        "primary",
        "secondary",
        "tertiary",
        "score",
        "rank",
        "confidence",
        "eligible",
        "acceptance",
        "accepted",
    ):
        assert not hasattr(declaration, forbidden)


def test_module_import_firewall() -> None:
    source = inspect.getsource(drawing_context_module)
    tree = ast.parse(source)
    collected: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            collected.add(node.id)
        elif isinstance(node, ast.Attribute):
            collected.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            collected.add(module)
            collected.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            collected.update(alias.name for alias in node.names)
    forbidden = {
        "origlyph.datum",
        "datum",
        "origlyph.geometry",
        "geometry",
        "evaluation",
        "binding",
        "role",
        "origlyph.cad.evaluation",
        "origlyph.cad.binding",
        "origlyph.cad.role",
        "ConstraintType",
        "CandidateEvaluation",
        "DatumConstraint",
        "DatumReferenceFrame",
        "FunctionalRelevanceDeclaration",
        "score",
        "rank",
        "confidence",
        "eligible",
        "PRIMARY",
        "SECONDARY",
        "TERTIARY",
    }
    assert not collected & forbidden


def test_coexistence_with_functional_declaration() -> None:
    target = _target()
    datum_feature = _declaration(target=target)
    functional = FunctionalRelevanceDeclaration(
        target=target,
        declarer="engineer:j.doe",
        rationale="mating interface",
    )
    assert datum_feature.target is functional.target is target
    assert datum_feature != functional
# ---------------------------------------------------------------------------
# Stage 9C — DrawingDatumReferenceFrameDeclaration (test-first)
#
# An attributed drawing/source datum-reference callout carrying ordered,
# unresolved labels plus drawing provenance only. Tuple order means
# drawing-callout precedence ONLY; it must never imply
# PRIMARY/SECONDARY/TERTIARY, ConstraintType, resolution, binding,
# DatumConstraint, DatumReferenceFrame, ranking, scoring, or acceptance.
# ---------------------------------------------------------------------------


def _drf(**overrides) -> DrawingDatumReferenceFrameDeclaration:
    values = {
        "labels": ("A", "B", "C"),
        "transcriber": "engineer:j.doe",
        "drawing_reference": "DWG-100 rev B",
        "location": None,
    }
    values.update(overrides)
    return DrawingDatumReferenceFrameDeclaration(**values)


def test_drf_valid_single_label() -> None:
    declaration = _drf(labels=("A",))
    assert declaration.labels == ("A",)


def test_drf_valid_multiple_labels() -> None:
    declaration = _drf()
    assert declaration.labels == ("A", "B", "C")


def test_drf_field_names_and_order_exact() -> None:
    names = [field.name for field in dataclasses.fields(_drf())]
    assert names == [
        "labels",
        "transcriber",
        "drawing_reference",
        "location",
    ]


def test_drf_labels_stored_as_tuple() -> None:
    assert isinstance(_drf().labels, tuple)


def test_drf_list_normalized_to_tuple() -> None:
    declaration = _drf(labels=["A", "B"])
    assert isinstance(declaration.labels, tuple)
    assert declaration.labels == ("A", "B")


def test_drf_generator_rejected() -> None:
    with pytest.raises(TypeError):
        _drf(labels=iter(("A", "B")))  # type: ignore[arg-type]


def test_drf_empty_labels_rejected() -> None:
    with pytest.raises(ValueError):
        _drf(labels=())


def test_drf_non_string_label_rejected() -> None:
    with pytest.raises(TypeError):
        _drf(labels=("A", 7))  # type: ignore[arg-type]


def test_drf_labels_stripped() -> None:
    declaration = _drf(labels=("  A  ", " B "))
    assert declaration.labels == ("A", "B")


def test_drf_blank_label_rejected() -> None:
    with pytest.raises(ValueError):
        _drf(labels=("A", "   "))


def test_drf_label_case_preserved() -> None:
    declaration = _drf(labels=("aBc", "D"))
    assert declaration.labels == ("aBc", "D")

def test_drf_internal_label_content_preserved() -> None:
    declaration = _drf(labels=("A-B", "C"))
    assert declaration.labels == ("A-B", "C")


def test_drf_label_order_preserved() -> None:
    declaration = _drf(labels=("C", "A", "B"))
    assert declaration.labels == ("C", "A", "B")


def test_drf_duplicate_labels_preserved() -> None:
    declaration = _drf(labels=("A", "A", "B"))
    assert declaration.labels == ("A", "A", "B")


def test_drf_transcriber_must_be_string() -> None:
    with pytest.raises(TypeError):
        _drf(transcriber=42)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _drf(transcriber="   ")


def test_drf_drawing_reference_must_be_string() -> None:
    with pytest.raises(TypeError):
        _drf(drawing_reference=42)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _drf(drawing_reference="   ")


def test_drf_location_normalization() -> None:
    assert _drf(location=None).location is None
    assert _drf(location="  flat  ").location == "flat"
    assert _drf(location="   ").location is None
    with pytest.raises(TypeError):
        _drf(location=7)  # type: ignore[arg-type]


def test_drf_frozen_immutability() -> None:
    declaration = _drf()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(declaration, "labels", ("X",))  # noqa: B010


def test_drf_value_equality_and_hash() -> None:
    first = _drf()
    second = _drf()
    assert first == second
    assert hash(first) == hash(second)


def test_drf_reversed_labels_unequal() -> None:
    assert _drf(labels=("A", "B")) != _drf(labels=("B", "A"))
def test_drf_forbidden_semantic_fields_absent() -> None:
    names = {field.name for field in dataclasses.fields(_drf())}
    assert names == {
        "labels",
        "transcriber",
        "drawing_reference",
        "location",
    }
    declaration = _drf()
    for forbidden in (
        "target",
        "kind",
        "sequence",
        "role",
        "constraint_type",
        "primary",
        "secondary",
        "tertiary",
        "score",
        "rank",
        "confidence",
        "eligible",
        "acceptance",
    ):
        assert not hasattr(declaration, forbidden)


def test_drf_no_source_entity_identity_stored() -> None:
    declaration = _drf()
    assert not hasattr(declaration, "target")
    assert not hasattr(declaration, "source_identity")


def test_drf_no_datum_binding_role_evaluation_imports() -> None:
    source = inspect.getsource(drawing_context_module)
    tree = ast.parse(source)
    collected: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            collected.add(node.id)
        elif isinstance(node, ast.Attribute):
            collected.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            collected.add(module)
            collected.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            collected.update(alias.name for alias in node.names)
    forbidden = {
        "BoundReference",
        "ConstraintType",
        "DatumConstraint",
        "DatumReferenceFrame",
        "origlyph.datum",
        "datum",
        "binding",
        "role",
        "evaluation",
        "resolver",
        "parser",
        "OCR",
        "PMI",
        "rank",
        "score",
    }
    assert not collected & forbidden