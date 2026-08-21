"""Unit tests for origlyph.cad.binding (Stage 2B CAD->datum binding).

Contract lock is derived from Stage 1D (origlyph.cad.bridge) and the Stage 1B
datum/reference domain. These tests exercise the validated, provenance-traced
binding boundary only; they must not construct datums or DRFs.
"""
import dataclasses

import pytest

from origlyph.cad import (
    CadFormat,
    DomainIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
)
from origlyph.cad.bridge import BridgedCandidate, extract_candidates
from origlyph.cad.binding import BoundReference, bind_reference, bind_references
from origlyph.cad.identity import NeutralEntityIdentity
from origlyph.cad.model import NeutralEntityEntry, NeutralModel, SourceToNeutralMapping
from origlyph.datum import (
    FeatureKind,
    PhysicalFeature,
    ReferencePoint,
    ReferenceSurface,
)
from origlyph.geometry import Frame, Point3D, Vector3D


def _world() -> Frame:
    return Frame.world()


def _shifted() -> Frame:
    return Frame(
        origin=Point3D(1.0, 2.0, 3.0),
        x_axis=Vector3D(1.0, 0.0, 0.0),
        y_axis=Vector3D(0.0, 1.0, 0.0),
        z_axis=Vector3D(0.0, 0.0, 1.0),
    )


def _doc() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="doc-1",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source(key: str) -> SourceEntityIdentity:
    return SourceEntityIdentity(source_document=_doc(), source_entity_key=key)


def _neutral(key: str, kind: NeutralEntityKind, *, source: bool = True) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=kind,
        source_identity=_source(key) if source else None,
    )


def _entry(key: str, kind: NeutralEntityKind, *, frame=None) -> NeutralEntityEntry:
    return NeutralEntityEntry(
        identity=_neutral(key, kind),
        coordinate_frame=frame,
    )


def _model(entries) -> NeutralModel:
    return NeutralModel(
        source=_doc(),
        root_frame=_world(),
        entities=list(entries),
        source_to_neutral=SourceToNeutralMapping(),
    )


def _candidate(key: str, kind: NeutralEntityKind, *, frame=None) -> BridgedCandidate:
    result = extract_candidates(_model([_entry(key, kind, frame=frame or _world())]))
    assert len(result.candidates) == 1
    return result.candidates[0]


def _identities(key: str = "d-1", kind: NeutralEntityKind = NeutralEntityKind.POINT):
    neutral = _neutral(key, kind)
    domain = DomainIdentity(key)
    return neutral, domain


# --------------------------------------------------------------------------- #
# Positive: construction & provenance
# --------------------------------------------------------------------------- #
def test_point_candidate_binds_correctly() -> None:
    candidate = _candidate("p-1", NeutralEntityKind.POINT)
    bound = bind_reference(candidate)
    assert isinstance(bound, BoundReference)
    assert isinstance(bound.reference, ReferencePoint)
    assert isinstance(bound.datum_feature, PhysicalFeature)
    assert bound.datum_feature.kind is FeatureKind.POINT
    assert bound.reference.entity_id == bound.datum_feature.entity_id == "p-1"
    assert bound.entity_id == "p-1"


def test_plane_candidate_binds_correctly() -> None:
    candidate = _candidate("pl-1", NeutralEntityKind.PLANE)
    bound = bind_reference(candidate)
    assert isinstance(bound.reference, ReferenceSurface)
    assert bound.datum_feature.kind is FeatureKind.PLANE
    assert bound.reference.entity_id == bound.datum_feature.entity_id == "pl-1"


def test_axis_feature_binds_with_reference_none() -> None:
    candidate = _candidate("ax-1", NeutralEntityKind.AXIS)
    bound = bind_reference(candidate)
    assert bound.reference is None
    assert bound.datum_feature.kind is FeatureKind.AXIS
    assert bound.datum_feature.entity_id == "ax-1"


def test_line_binds_as_axis_with_reference_none() -> None:
    candidate = _candidate("ln-1", NeutralEntityKind.LINE)
    bound = bind_reference(candidate)
    assert bound.reference is None
    assert bound.datum_feature.kind is FeatureKind.AXIS


def test_bound_reference_is_immutable() -> None:
    bound = bind_reference(_candidate("p-1", NeutralEntityKind.POINT))
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(bound, "datum_feature", None)  # noqa: B010
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(bound, "source_identity", None)  # noqa: B010


def test_equal_bindings_are_equal() -> None:
    first = bind_reference(_candidate("p-1", NeutralEntityKind.POINT))
    second = bind_reference(_candidate("p-1", NeutralEntityKind.POINT))
    assert first == second
    assert hash(first) == hash(second)


def test_provenance_participates_in_equality() -> None:
    first = bind_reference(_candidate("a-1", NeutralEntityKind.POINT))
    second = bind_reference(_candidate("b-1", NeutralEntityKind.POINT))
    assert first != second
    assert first.source_identity != second.source_identity


# --------------------------------------------------------------------------- #
# Positive: batch & verbatim pass-through
# --------------------------------------------------------------------------- #
def test_batch_binding_preserves_input_order() -> None:
    point = _candidate("p-1", NeutralEntityKind.POINT)
    plane = _candidate("pl-1", NeutralEntityKind.PLANE)
    axis = _candidate("ax-1", NeutralEntityKind.AXIS)
    bound = bind_references([point, plane, axis])
    assert len(bound) == 3
    assert [b.entity_id for b in bound] == ["p-1", "pl-1", "ax-1"]
    assert isinstance(bound[0].reference, ReferencePoint)
    assert isinstance(bound[1].reference, ReferenceSurface)
    assert bound[2].reference is None


def test_batch_fails_closed_when_one_is_invalid() -> None:
    good = _candidate("p-1", NeutralEntityKind.POINT)
    neutral, domain = _identities("bad", NeutralEntityKind.POINT)
    bad = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="x", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="y", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(ValueError):
        bind_references([good, bad])


def test_identity_chain_is_preserved() -> None:
    candidate = _candidate("p-1", NeutralEntityKind.POINT)
    bound = bind_reference(candidate)
    assert bound.neutral_identity is candidate.neutral_identity
    assert bound.domain_identity is candidate.domain_identity
    assert bound.source_identity is candidate.neutral_identity.source_identity


def test_entity_id_is_consistent_with_domain_identity() -> None:
    candidate = _candidate("p-1", NeutralEntityKind.POINT)
    bound = bind_reference(candidate)
    assert bound.entity_id == bound.domain_identity.value == "p-1"


def test_bound_fields_are_exact_references() -> None:
    candidate = _candidate("p-1", NeutralEntityKind.POINT)
    bound = bind_reference(candidate)
    assert bound.reference is candidate.reference
    assert bound.datum_feature is candidate.datum_feature
    assert bound.neutral_identity is candidate.neutral_identity
    assert bound.domain_identity is candidate.domain_identity


# --------------------------------------------------------------------------- #
# Negative: contract violations (fail-closed)
# --------------------------------------------------------------------------- #
def test_reference_entity_id_mismatch_raises() -> None:
    neutral, domain = _identities("d-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="ref-id", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="feat-id", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(ValueError):
        bind_reference(candidate)


def test_reference_feature_frame_mismatch_raises() -> None:
    neutral, domain = _identities("d-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="d-1", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="d-1", frame=_shifted(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(ValueError):
        bind_reference(candidate)


def test_reference_feature_kind_mismatch_raises() -> None:
    neutral, domain = _identities("d-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=ReferenceSurface(entity_id="d-1", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="d-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(ValueError):
        bind_reference(candidate)


def test_reference_point_does_not_bind_axis_feature() -> None:
    neutral, domain = _identities("d-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="d-1", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="d-1", frame=_world(), kind=FeatureKind.AXIS
        ),
    )
    with pytest.raises(ValueError):
        bind_reference(candidate)


def test_reference_less_non_axis_raises() -> None:
    neutral, domain = _identities("d-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain,
        neutral_identity=neutral,
        reference=None,
        datum_feature=PhysicalFeature(
            entity_id="d-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(ValueError):
        bind_reference(candidate)


def test_non_bridged_candidate_input_raises_type_error() -> None:
    with pytest.raises(TypeError):
        bind_reference(object())  # type: ignore[arg-type]


def test_bind_references_rejects_non_sequence() -> None:
    with pytest.raises(TypeError):
        bind_references(123)  # type: ignore[arg-type]


def test_bind_references_empty_returns_empty_tuple() -> None:
    assert bind_references([]) == ()


def test_bind_references_rejects_non_candidate_element() -> None:
    with pytest.raises(TypeError):
        bind_references([object()])  # type: ignore[list-item]


def test_source_identity_propagates() -> None:
    candidate = _candidate("p-1", NeutralEntityKind.POINT)
    bound = bind_reference(candidate)
    assert bound.source_identity is candidate.neutral_identity.source_identity
    assert bound.source_identity is not None
    assert isinstance(bound.source_identity, SourceEntityIdentity)


def test_bound_reference_is_hash_fingerprinted_by_provenance() -> None:
    bound = bind_reference(_candidate("p-1", NeutralEntityKind.POINT))
    fingerprint = (
        bound.reference,
        bound.datum_feature,
        bound.neutral_identity,
        bound.domain_identity,
        bound.source_identity,
    )
    assert hash(bound) == hash(fingerprint)
