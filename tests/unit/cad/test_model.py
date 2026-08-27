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
from origlyph.geometry import (
    BoundedPlanarFace,
    Frame,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)


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
def _square_face() -> BoundedPlanarFace:
    return BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(10.0, 0.0, 0.0),
            Point3D(10.0, 20.0, 0.0),
            Point3D(0.0, 20.0, 0.0),
        )
    )


def _surface_identity(
    key: str,
    *,
    source: SourceEntityIdentity | None = None,
    generated: bool = False,
) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=NeutralEntityKind.SURFACE,
        source_identity=source,
        generated=generated,
    )


def test_entry_carries_bounded_planar_face() -> None:
    face = _square_face()
    entry = _entry(geometry=face)
    assert entry.geometry == face


def test_entry_retains_face_object_verbatim() -> None:
    face = _square_face()
    entry = NeutralEntityEntry(
        identity=_surface_identity("face-1", source=_source_entity()),
        geometry=face,
    )
    assert entry.geometry is face


def test_source_provenance_reachable_through_face_entry() -> None:
    source = _source_entity(key="slab-face-7")
    entry = NeutralEntityEntry(
        identity=_surface_identity("n-face", source=source),
        geometry=_square_face(),
    )
    linked = entry.identity.source_identity
    assert linked is not None
    assert linked is source
    assert linked.source_document.source_id == "doc-1"


def test_generated_identity_may_carry_bounded_face() -> None:
    entry = NeutralEntityEntry(
        identity=_surface_identity("gen-face", generated=True),
        geometry=_square_face(),
    )
    assert entry.identity.generated is True
    assert entry.identity.source_identity is None
    assert isinstance(entry.geometry, BoundedPlanarFace)


def test_same_geometry_different_identities_remain_distinct_entries() -> None:
    face = _square_face()
    first = NeutralEntityEntry(
        identity=_surface_identity("face-a", source=_source_entity(key="a")),
        geometry=face,
    )
    second = NeutralEntityEntry(
        identity=_surface_identity("face-b", source=_source_entity(key="b")),
        geometry=face,
    )
    assert first.geometry == second.geometry
    assert first != second
    assert first.identity != second.identity


def test_arbitrary_payload_remains_rejected_after_widening() -> None:
    with pytest.raises(TypeError):
        _entry(geometry=object())  # type: ignore[arg-type]


def test_face_bearing_entry_without_coordinate_frame_is_legal() -> None:
    entry = NeutralEntityEntry(
        identity=_surface_identity("face-noframe", source=_source_entity()),
        geometry=_square_face(),
    )
    assert entry.coordinate_frame is None


def test_model_lookup_returns_face_bearing_entry() -> None:
    identity = _surface_identity("n-face", source=_source_entity())
    entry = NeutralEntityEntry(identity=identity, geometry=_square_face())
    model = _model(entities=[entry])
    found = model.entity_by_identity(identity)
    assert found is not None
    assert found is entry
    assert isinstance(found.geometry, BoundedPlanarFace)
    assert len(model.entities) == 1


def test_model_has_no_topology_tree() -> None:
    model = _model()
    for name in ("topology", "brep_kernel", "b_rep"):
        assert not hasattr(model, name)


# ---------------------------------------------------------------------------
# Stage 10P — model-scoped source-identity reverse lookup.
# ---------------------------------------------------------------------------
# Contract: `NeutralModel.reverse_lookup(source)` returns the *neutral identity*
# mapped from the exact `SourceEntityIdentity` within ONE NeutralModel snapshot.
# - exact identity comparison only; deterministic; model-local;
# - fail closed on NO match;
# - ambiguity (>1) is structurally impossible: SourceToNeutralMapping rejects
#   duplicate source keys and duplicate neutral identities at construction.
# No geometry, binding, ConstraintType, role, DatumConstraint/DRF, standards,
# fingerprint/revision, AI/heuristic, or cross-model behavior is introduced.


def _other_source_document() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="doc-2",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source_with_document(
    document: SourceDocumentIdentity, key: str = "slab-1"
) -> SourceEntityIdentity:
    return SourceEntityIdentity(
        source_document=document,
        source_entity_key=key,
    )


def _keyed_model(
    source: SourceEntityIdentity,
    neutral: NeutralEntityIdentity,
) -> NeutralModel:
    entry = NeutralEntityEntry(identity=neutral)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    return _model(entities=[entry], mapping=mapping)


def test_reverse_lookup_resolves_exact_source_in_same_snapshot() -> None:
    from origlyph.cad.exceptions import UnresolvedSourceIdentityError  # noqa: F401

    source = _source_entity(key="slab-1")
    neutral = _neutral_identity(key="n-1", source=source)
    model = _keyed_model(source, neutral)
    assert model.reverse_lookup(source) == neutral
    assert model.reverse_lookup(source) is neutral


def test_reverse_lookup_returns_neutral_identity_only() -> None:
    source = _source_entity(key="slab-1")
    neutral = _neutral_identity(key="n-1", source=source)
    entry = NeutralEntityEntry(identity=neutral, coordinate_frame=Frame.world())
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    model = _model(entities=[entry], mapping=mapping)
    result = model.reverse_lookup(source)
    assert result == neutral
    assert isinstance(result, NeutralEntityIdentity)
    # identity-only result: no geometry / none of the downstream binding types.
    assert not isinstance(result, NeutralEntityEntry)
    assert not hasattr(result, "coordinate_frame")


def test_reverse_lookup_unknown_source_fails_closed() -> None:
    from origlyph.cad.exceptions import UnresolvedSourceIdentityError

    model = _model()
    missing = _source_entity(key="absent")
    with pytest.raises(UnresolvedSourceIdentityError):
        model.reverse_lookup(missing)


def test_reverse_lookup_same_key_different_document_does_not_alias() -> None:
    from origlyph.cad.exceptions import UnresolvedSourceIdentityError

    doc_a = _source_document()
    doc_b = _other_source_document()
    src_a = _source_with_document(doc_a, "shared-key")
    src_b = _source_with_document(doc_b, "shared-key")
    neutral = _neutral_identity(key="n", source=src_a)
    model = _keyed_model(src_a, neutral)
    assert model.reverse_lookup(src_a) is neutral
    assert src_a != src_b
    with pytest.raises(UnresolvedSourceIdentityError):
        model.reverse_lookup(src_b)


def test_reverse_lookup_does_not_cross_model_snapshots() -> None:
    from origlyph.cad.exceptions import UnresolvedSourceIdentityError

    source = _source_entity(key="slab-1")
    neutral = _neutral_identity(key="n", source=source)
    entry = NeutralEntityEntry(identity=neutral)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    model_a = _model(entities=[entry], mapping=mapping)
    model_b = _model()
    assert model_a.reverse_lookup(source) is neutral
    with pytest.raises(UnresolvedSourceIdentityError):
        model_b.reverse_lookup(source)


def test_reverse_lookup_is_deterministic() -> None:
    source = _source_entity(key="slab-1")
    neutral = _neutral_identity(key="n", source=source)
    model = _keyed_model(source, neutral)
    first = model.reverse_lookup(source)
    second = model.reverse_lookup(source)
    assert first is neutral
    assert first == second
    assert hash(first) == hash(second)


def test_reverse_lookup_leaves_existing_lookups_unchanged() -> None:
    source = _source_entity(key="slab-1")
    neutral = _neutral_identity(key="n", source=source)
    entry = NeutralEntityEntry(identity=neutral)
    mapping = SourceToNeutralMapping(pairs=[(source, neutral)])
    model = _model(entities=[entry], mapping=mapping)
    # existing forward lookups still behave exactly as before.
    assert model.entity_by_identity(neutral) is entry
    assert model.entity_by_source(source) is entry
    # new reverse lookup returns the identity only.
    assert model.reverse_lookup(source) is neutral


def test_mapping_duplicate_rejection_precludes_ambiguity() -> None:
    # A single SourceEntityIdentity can never map to >1 neutral identity:
    # SourceToNeutralMapping rejects a duplicate source key at construction.
    from origlyph.cad import DuplicateSourceEntityError

    source = _source_entity(key="slab-1")
    neutral_a = _neutral_identity(key="n-a", source=source)
    neutral_b = _neutral_identity(key="n-b", source=source)
    with pytest.raises(DuplicateSourceEntityError):
        SourceToNeutralMapping(
            pairs=[(source, neutral_a), (source, neutral_b)]
        )