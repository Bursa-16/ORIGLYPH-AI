"""Unit tests for origlyph.cad.identity contracts (Stage 1C)."""
import dataclasses

import pytest

from origlyph.cad import (
    CadFormat,
    DomainIdentity,
    InvalidSourceIdentityError,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    UnsupportedSourceUnitError,
)


def _source_document(
    source_id: str = "doc-1",
    fmt: CadFormat = CadFormat.STEP,
    units: SourceUnitSystem | None = None,
) -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=source_id,
        format=fmt,
        unit_system=units if units is not None else SourceUnitSystem(),
    )


def _source_entity(
    key: str = "slab-1",
    document: SourceDocumentIdentity | None = None,
) -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=document if document is not None else _source_document(),
        source_entity_key=key,
    )


def _neutral_entity(
    key: str = "n-1",
    kind: NeutralEntityKind = NeutralEntityKind.SOLID_BODY,
    source: SourceEntityIdentity | None = None,
    generated: bool = False,
) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=kind,
        source_identity=source,
        generated=generated,
    )


def test_domain_identity_rejects_empty_or_blank() -> None:
    with pytest.raises(ValueError):
        DomainIdentity("")
    with pytest.raises(ValueError):
        DomainIdentity("   ")


def test_domain_identity_normalizes_whitespace() -> None:
    ident = DomainIdentity("  analysis-a  ")
    assert ident.value == "analysis-a"


def test_domain_identity_is_frozen() -> None:
    ident = DomainIdentity("analysis-a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ident, "value", "other")  # noqa: B010


def test_four_identity_types_are_distinct() -> None:
    domain = DomainIdentity("a")
    doc = _source_document()
    entity = _source_entity()
    neutral = _neutral_entity(source=entity)
    assert not isinstance(doc, DomainIdentity)
    assert not isinstance(domain, SourceDocumentIdentity)
    assert not isinstance(entity, SourceDocumentIdentity)
    assert not isinstance(entity, NeutralEntityIdentity)
    assert not isinstance(neutral, SourceEntityIdentity)


def test_source_document_is_frozen() -> None:
    doc = _source_document()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(doc, "source_id", "changed")  # noqa: B010


def test_source_document_rejects_empty_source_id() -> None:
    with pytest.raises(InvalidSourceIdentityError):
        _source_document(source_id="  ")


def test_source_document_rejects_non_cad_format() -> None:
    with pytest.raises(InvalidSourceIdentityError):
        SourceDocumentIdentity(
            source_id="doc-1",
            format="stp",  # type: ignore[arg-type]
            unit_system=SourceUnitSystem(),
        )


def test_source_document_format_is_explicit() -> None:
    doc = _source_document(fmt=CadFormat.STEP)
    assert doc.format is CadFormat.STEP


def test_source_entity_rejects_empty_key() -> None:
    with pytest.raises(InvalidSourceIdentityError):
        _source_entity(key="")


def test_source_entity_scoped_to_source_document() -> None:
    doc_a = _source_document(source_id="a")
    doc_b = _source_document(source_id="b")
    in_a = SourceEntityIdentity(doc_a, "k")
    in_a_again = SourceEntityIdentity(doc_a, "k")
    in_b = SourceEntityIdentity(doc_b, "k")
    other_key = SourceEntityIdentity(doc_a, "k2")
    assert in_a == in_a_again
    assert in_a != in_b
    assert in_a != other_key


def test_source_entity_path_coerced_to_tuple() -> None:
    entity = SourceEntityIdentity(
        _source_document(),
        "k",
        path=["/root", "group"],  # type: ignore[arg-type]
    )
    assert entity.path == ("/root", "group")
    assert isinstance(entity.path, tuple)


def test_neutral_entity_is_immutable() -> None:
    neutral = _neutral_entity(source=_source_entity())
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(neutral, "neutral_entity_key", "changed")  # noqa: B010
def test_neutral_entity_is_hashable() -> None:
    neutral = _neutral_entity(source=_source_entity())
    same = _neutral_entity(source=_source_entity())
    assert hash(neutral) == hash(same)
    assert len({neutral, same}) == 1


def test_neutral_equality_uses_source_and_generated() -> None:
    derived = _neutral_entity(source=_source_entity())
    synthetic = _neutral_entity(source=None, generated=True)
    assert derived != synthetic
    assert derived.generated is False
    assert synthetic.generated is True


def test_neutral_requires_source_or_generated_flag() -> None:
    with pytest.raises(ValueError):
        _neutral_entity(source=None, generated=False)


def test_neutral_generated_cannot_carry_source() -> None:
    with pytest.raises(ValueError):
        _neutral_entity(source=_source_entity(), generated=True)


def test_neutral_source_derived_and_generated_variants_allowed() -> None:
    derived = _neutral_entity(source=_source_entity())
    synthetic = _neutral_entity(source=None, generated=True)
    assert derived.source_identity is not None
    assert synthetic.source_identity is None


def test_neutral_rejects_bad_kind() -> None:
    with pytest.raises(ValueError):
        NeutralEntityIdentity(
            "k",
            kind="solid",  # type: ignore[arg-type]
            generated=True,
        )


def test_neutral_equality_is_deterministic() -> None:
    entity = _source_entity()
    a = _neutral_entity(source=entity)
    b = _neutral_entity(source=entity)
    assert a == b
    assert hash(a) == hash(b)


def test_cad_format_members_are_explicit() -> None:
    assert {member.value for member in CadFormat} == {"step", "iges", "stl", "dxf"}


def test_cad_format_has_no_unknown_member() -> None:
    assert not hasattr(CadFormat, "UNKNOWN")
    with pytest.raises(ValueError):
        CadFormat("unknown-format")


def test_source_units_default_to_mm_rad() -> None:
    units = SourceUnitSystem()
    assert units.length_unit == "mm"
    assert units.angle_unit == "rad"


def test_source_units_stored_verbatim() -> None:
    units = SourceUnitSystem(length_unit="inch", angle_unit="deg")
    assert units.length_unit == "inch"
    assert units.angle_unit == "deg"


def test_unknown_length_unit_fails_closed() -> None:
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="parsec", angle_unit="rad")
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="", angle_unit="rad")


def test_unknown_angle_unit_fails_closed() -> None:
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="mm", angle_unit="gradian")


def test_no_silent_mm_assumption() -> None:
    # An unknown source unit must never silently fall back to millimetres.
    with pytest.raises(UnsupportedSourceUnitError):
        SourceUnitSystem(length_unit="furlong", angle_unit="rad")


def test_identity_makes_no_persistence_claim() -> None:
    entity = _source_entity()
    neutral = _neutral_entity(source=entity)
    for obj in (entity, neutral, DomainIdentity("x")):
        assert not hasattr(obj, "database_key")
        assert not hasattr(obj, "persistence_id")