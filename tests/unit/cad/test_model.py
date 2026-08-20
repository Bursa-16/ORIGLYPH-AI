"""Unit tests for origlyph.cad.model neutral model contracts (Stage 1C)."""
import dataclasses
from types import MappingProxyType

import pytest

from origlyph.cad import (
    CadFormat,
    CadWarning,
    DuplicateNeutralEntityError,
    NeutralEntityEntry,
    NeutralEntityIdentity,
    NeutralEntityKind,
    NeutralModel,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceToNeutralMapping,
    SourceUnitSystem,
    UnsupportedContent,
)
from origlyph.geometry import Frame, Line3D, Plane3D, Point3D, Vector3D


def _source_document() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="doc-1",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source_entity(key: str = "slab-1") -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=_source_document(),
        source_entity_key=key,
    )


def _neutral_identity(
    key: str = "n-1",
    source: SourceEntityIdentity | None = None,
    generated: bool = False,
) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=NeutralEntityKind.SOLID_BODY,
        source_identity=source,
        generated=generated,
    )


def _entry(*, geometry=None, coordinate_frame=None, metadata=None):
    if metadata is None:
        return NeutralEntityEntry(
            identity=_neutral_identity(source=_source_entity()),
            geometry=geometry,
            coordinate_frame=coordinate_frame,
        )
    return NeutralEntityEntry(
        identity=_neutral_identity(source=_source_entity()),
        geometry=geometry,
        coordinate_frame=coordinate_frame,
        metadata=metadata,
    )


def _model(entities=None, mapping=None, warnings=None, unsupported=None):
    return NeutralModel(
        source=_source_document(),
        root_frame=Frame.world(),
        entities=entities if entities is not None else [_entry()],
        source_to_neutral=mapping,
        warnings=warnings,
        unsupported=unsupported,
    )


def test_entry_is_immutable() -> None:
    entry = _entry()
    other_identity = _neutral_identity(key="other", generated=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(entry, "identity", other_identity)  # noqa: B010


def test_entry_kind_property_reflects_identity() -> None:
    entry = _entry()
    assert entry.kind is entry.identity.kind
    assert entry.kind is NeutralEntityKind.SOLID_BODY


def test_entry_accepts_existing_geometry_value_objects() -> None:
    geometries = [
        Point3D(1.0, 2.0, 3.0),
        Vector3D(1.0, 0.0, 0.0),
        Line3D(Point3D(0.0, 0.0, 0.0), Vector3D(1.0, 0.0, 0.0)),
        Plane3D(Point3D(0.0, 0.0, 0.0), Vector3D(0.0, 0.0, 1.0)),
    ]
    for geometry in geometries:
        entry = _entry(geometry=geometry)
        assert entry.geometry == geometry


def test_entry_has_no_brep_topology_or_kernel() -> None:
    entry = _entry()
    for name in ("topology", "b_rep", "kernel", "mesh"):
        assert not hasattr(entry, name)


def test_entry_rejects_unknown_geometry_type() -> None:
    with pytest.raises(TypeError):
        _entry(geometry="not-a-geometry")  # type: ignore[arg-type]


def test_entry_metadata_is_read_only_mapping() -> None:
    entry = _entry(metadata={"layer": "A"})
    assert isinstance(entry.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        entry.metadata["layer"] = "B"  # type: ignore[index]


def test_entry_coordinate_frame_reuses_geometry_frame() -> None:
    frame = Frame.world()
    entry = _entry(coordinate_frame=frame)
    assert isinstance(entry.coordinate_frame, Frame)
    assert entry.coordinate_frame == frame


def test_model_is_immutable() -> None:
    model = _model()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(model, "entities", ())  # noqa: B010
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(model, "source", _source_document())  # noqa: B010


def test_model_reuses_geometry_root_frame() -> None:
    model = _model()
    assert isinstance(model.root_frame, Frame)
    assert model.root_frame == Frame.world()


def test_model_duplicate_entities_rejected() -> None:
    entry = _entry()
    with pytest.raises(DuplicateNeutralEntityError):
        _model(entities=[entry, entry])


def test_model_lookup_by_identity_is_deterministic() -> None:
    identity = _neutral_identity(source=_source_entity())
    entry = NeutralEntityEntry(identity=identity)
    model = _model(entities=[entry])
    assert model.entity_by_identity(identity) == entry
    assert model.entity_by_identity(identity) is entry
    missing = _neutral_identity(key="nope", source=_source_entity())
    assert model.entity_by_identity(missing) is None


def test_model_lookup_by_source_identity_is_deterministic() -> None:
    source = _source_entity(key="slab-1")
    identity = _neutral_identity(key="n-1", source=source)
    entry = NeutralEntityEntry(identity=identity)
    mapping = SourceToNeutralMapping(pairs=[(source, identity)])
    model = _model(entities=[entry], mapping=mapping)
    assert model.entity_by_source(source) == entry
    other_source = _source_entity(key="absent")
    assert model.entity_by_source(other_source) is None


def test_model_retains_warnings() -> None:
    warning = CadWarning(code="W-001", message="key reused")
    model = _model(warnings=[warning])
    assert model.warnings == (warning,)


def test_model_retains_unsupported_content() -> None:
    unsupported = UnsupportedContent(reason="sweep unsupported")
    model = _model(unsupported=[unsupported])
    assert model.unsupported == (unsupported,)


def test_model_entities_are_a_fixed_tuple() -> None:
    model = _model()
    assert isinstance(model.entities, tuple)
    assert len(model.entities) == 1


def test_model_has_no_topology_tree() -> None:
    model = _model()
    for name in ("topology", "brep_kernel", "b_rep"):
        assert not hasattr(model, name)