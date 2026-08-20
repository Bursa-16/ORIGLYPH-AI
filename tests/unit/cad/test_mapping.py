"""Unit tests for SourceToNeutralMapping (Stage 1C)."""
import dataclasses

import pytest

from origlyph.cad import (
    CadFormat,
    DuplicateNeutralEntityError,
    DuplicateSourceEntityError,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceToNeutralMapping,
    SourceUnitSystem,
)


def _source_document(doc_id: str = "doc-1") -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=doc_id,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source(key: str, doc_id: str = "doc-1") -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=_source_document(doc_id),
        source_entity_key=key,
    )


def _neutral(
    key: str, source: SourceEntityIdentity | None, generated: bool = False
) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=NeutralEntityKind.SOLID_BODY,
        source_identity=source,
        generated=generated,
    )


def test_empty_mapping_is_allowed() -> None:
    mapping = SourceToNeutralMapping()
    assert mapping.pairs == ()
    assert mapping.source_to_neutral(_source("a")) is None
    assert mapping.neutral_to_source(_neutral("n", None, True)) is None


def test_source_to_neutral_lookup_is_deterministic() -> None:
    source = _source("a-1")
    neutral = _neutral("n-1", source)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    for _ in range(3):
        assert mapping.source_to_neutral(source) == neutral


def test_neutral_to_source_lookup_is_deterministic() -> None:
    source = _source("a-1")
    neutral = _neutral("n-1", source)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    for _ in range(3):
        assert mapping.neutral_to_source(neutral) == source


def test_duplicate_source_is_rejected() -> None:
    source = _source("a-1")
    first = _neutral("n-1", source)
    second = _neutral("n-2", source)
    with pytest.raises(DuplicateSourceEntityError):
        SourceToNeutralMapping(pairs=[(source, first), (source, second)])


def test_duplicate_neutral_is_rejected() -> None:
    neutral = _neutral("n-1", _source("a-1"))
    other_source = _source("b-1")
    with pytest.raises(DuplicateNeutralEntityError):
        SourceToNeutralMapping(
            pairs=[
                (_source("a-1"), neutral),
                (other_source, neutral),
            ]
        )


def test_no_silent_remap() -> None:
    source = _source("a-1")
    original = _neutral("n-1", source)
    replacement = _neutral("n-9", source)
    # Re-mapping the same source to a different neutral in one construction
    # must raise instead of silently keeping the last-writer-wins value.
    with pytest.raises(DuplicateSourceEntityError):
        SourceToNeutralMapping(
            pairs=[(source, original), (source, replacement)]
        )
    # The standalone mapping keeps its deterministic pair.
    mapping = SourceToNeutralMapping(pairs=[(source, original)])
    assert mapping.source_to_neutral(source) == original
    assert mapping.source_to_neutral(source) != replacement


def test_mapping_is_immutable() -> None:
    source = _source("a-1")
    neutral = _neutral("n-1", source)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    with pytest.raises(dataclasses.FrozenInstanceError):
        mapping._source_to_neutral = {}  # type: ignore[misc]
    assert isinstance(mapping.pairs, tuple)
    assert mapping.pairs == ((source, neutral),)