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