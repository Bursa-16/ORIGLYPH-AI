"""Unit tests for the Stage 6B functional-relevance declaration contract.

The declaration means ONLY: an identified engineer explicitly declares a
source CAD entity functionally relevant for datum consideration. It must
never encode datum roles, ranking, scoring, confidence overrides, or
acceptance — the structural firewall tests below pin that shape.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect

import pytest

from origlyph.cad import (
    CadFormat,
    DomainIdentity,
    FunctionalRelevanceDeclaration,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
)
from origlyph.cad import context as context_module


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
        "declarer": "engineer:j.doe",
        "rationale": "mating interface for the cover assembly",
    }
    values.update(overrides)
    return FunctionalRelevanceDeclaration(**values)


def test_valid_declaration_constructs() -> None:
    declaration = _declaration()
    assert declaration.declarer == "engineer:j.doe"
    assert declaration.rationale == "mating interface for the cover assembly"


def test_target_retained_verbatim() -> None:
    target = _target()
    declaration = _declaration(target=target)
    assert declaration.target is target


def test_target_must_be_source_entity_identity() -> None:
    with pytest.raises(TypeError):
        _declaration(target=DomainIdentity("face-7"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _declaration(target="face-7")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _declaration(target=None)  # type: ignore[arg-type]


def test_declarer_stripped_and_normalized() -> None:
    declaration = _declaration(declarer="  engineer:j.doe  ")
    assert declaration.declarer == "engineer:j.doe"


def test_whitespace_only_declarer_rejected() -> None:
    with pytest.raises(ValueError):
        _declaration(declarer="   ")


def test_non_string_declarer_rejected() -> None:
    with pytest.raises(TypeError):
        _declaration(declarer=42)  # type: ignore[arg-type]


def test_rationale_stripped() -> None:
    declaration = _declaration(rationale="  sealing interface  ")
    assert declaration.rationale == "sealing interface"


def test_whitespace_only_rationale_rejected() -> None:
    with pytest.raises(ValueError):
        _declaration(rationale="   ")


def test_non_string_rationale_rejected() -> None:
    with pytest.raises(TypeError):
        _declaration(rationale=["sealing"])  # type: ignore[arg-type]


def test_frozen_immutability() -> None:
    declaration = _declaration()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(declaration, "declarer", "other")  # noqa: B010


def test_value_equality() -> None:
    target = _target()
    first = _declaration(target=target)
    second = _declaration(target=target)
    assert first == second


def test_equal_declarations_share_hash() -> None:
    target = _target()
    first = _declaration(target=target)
    second = _declaration(target=target)
    assert hash(first) == hash(second)


def test_document_provenance_reachable_through_target() -> None:
    declaration = _declaration()
    document = declaration.target.source_document
    assert document.source_id == "doc-1"
    assert document.format is CadFormat.STEP


def test_source_entity_path_retained() -> None:
    declaration = _declaration()
    assert declaration.target.path == ("body-A", "face-7")


def test_different_targets_remain_distinct_declarations() -> None:
    first = _declaration(target=_target(key="face-7"))
    second = _declaration(target=_target(key="face-9"))
    assert first != second


def test_stored_fields_exactly_the_locked_minimum() -> None:
    names = {field.name for field in dataclasses.fields(_declaration())}
    assert names == {"target", "declarer", "rationale"}
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
        "acceptance",
        "accepted",
        "ai",
        "authority_level",
    ):
        assert not hasattr(declaration, forbidden)


def test_module_import_firewall() -> None:
    source = inspect.getsource(context_module)
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
        "evaluation",
        "binding",
        "ConstraintType",
        "CandidateEvaluation",
        "BoundReference",
        "PRIMARY",
        "SECONDARY",
        "TERTIARY",
        "score",
        "rank",
        "confidence",
    }
    assert not collected & forbidden


def test_no_functional_taxonomy_enum_added() -> None:
    public = {
        name
        for name in getattr(context_module, "__all__", [])
        if not name.startswith("_")
    }
    assert public == {"FunctionalRelevanceDeclaration"}