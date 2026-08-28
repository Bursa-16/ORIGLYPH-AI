"""Unit tests for origlyph.cad.bridge (Stage 1D deterministic bridge)."""
import dataclasses

import pytest

from origlyph.cad import (
    CadFormat,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    bind_datum_constraint,
    bind_datum_reference_frame,
    bind_reference,
)
from origlyph.cad.bridge import (
    BridgedCandidate,
    CandidateResult,
    SkippedCandidate,
    domain_identity,
    extract_candidates,
    identity_chain,
    resolve_entity_frame,
    select_reference,
)
from origlyph.cad.identity import NeutralEntityIdentity
from origlyph.cad.model import NeutralEntityEntry, NeutralModel, SourceToNeutralMapping
from origlyph.datum import (
    ConstraintType,
    FeatureKind,
    LocatingFeature,
    PhysicalFeature,
    ReferencePoint,
    ReferenceSurface,
)
from origlyph.geometry import (
    BoundedPlanarFace,
    Frame,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)


def _world() -> Frame:
    return Frame.world()


def _doc() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="doc-1",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _source(key: str) -> SourceEntityIdentity:
    return SourceEntityIdentity(source_document=_doc(), source_entity_key=key)


def _neutral(
    key: str,
    kind: NeutralEntityKind,
    *,
    source: bool = True,
    generated: bool = False,
) -> NeutralEntityIdentity:
    return NeutralEntityIdentity(
        neutral_entity_key=key,
        kind=kind,
        source_identity=_source(key) if source else None,
        generated=generated,
    )


def _entry(
    key: str,
    kind: NeutralEntityKind,
    *,
    frame=None,
    geometry=None,
    source: bool = True,
    generated: bool = False,
) -> NeutralEntityEntry:
    return NeutralEntityEntry(
        identity=_neutral(key, kind, source=source, generated=generated),
        geometry=geometry,
        coordinate_frame=frame,
    )


def _model(entries) -> NeutralModel:
    return NeutralModel(
        source=_doc(),
        root_frame=_world(),
        entities=list(entries),
        source_to_neutral=SourceToNeutralMapping(),
    )


def _square_face() -> BoundedPlanarFace:
    return BoundedPlanarFace(
        vertices=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(4.0, 0.0, 0.0),
            Point3D(4.0, 4.0, 0.0),
            Point3D(0.0, 4.0, 0.0),
        )
    )
def test_domain_identity_deterministic() -> None:
    neutral = _neutral("n-1", NeutralEntityKind.POINT)
    first = domain_identity(neutral)
    second = domain_identity(neutral)
    assert first == second
    assert hash(first) == hash(second)


def test_domain_identity_distinct_for_distinct_keys() -> None:
    a = domain_identity(_neutral("a", NeutralEntityKind.POINT))
    b = domain_identity(_neutral("b", NeutralEntityKind.POINT))
    assert a != b


def test_domain_identity_value_equals_neutral_key() -> None:
    neutral = _neutral("slab-1", NeutralEntityKind.PLANE)
    assert domain_identity(neutral).value == "slab-1"


def test_identity_chain_has_source_for_derived() -> None:
    neutral = _neutral("n-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain_identity(neutral),
        neutral_identity=neutral,
        reference=None,
        datum_feature=PhysicalFeature(
            entity_id="n-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    source, returned_neutral, domain = identity_chain(candidate)
    assert source is not None
    assert source == neutral.source_identity
    assert returned_neutral is neutral
    assert domain.value == "n-1"


def test_identity_chain_source_none_for_generated() -> None:
    neutral = _neutral("g-1", NeutralEntityKind.POINT, source=False, generated=True)
    candidate = BridgedCandidate(
        domain_identity=domain_identity(neutral),
        neutral_identity=neutral,
        reference=None,
        datum_feature=PhysicalFeature(
            entity_id="g-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    source, _, _ = identity_chain(candidate)
    assert source is None
def test_point_with_frame_lifts_reference_and_feature() -> None:
    point = _entry("p-1", NeutralEntityKind.POINT, frame=_world())
    result = extract_candidates(_model([point]))
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.entity_id == "p-1"
    assert isinstance(candidate.reference, ReferencePoint)
    assert isinstance(candidate.datum_feature, PhysicalFeature)
    assert candidate.datum_feature.kind is FeatureKind.POINT


def test_plane_with_frame_lifts_reference_and_feature() -> None:
    plane = _entry("pl-1", NeutralEntityKind.PLANE, frame=_world())
    result = extract_candidates(_model([plane]))
    candidate = result.candidates[0]
    assert isinstance(candidate.reference, ReferenceSurface)
    assert candidate.datum_feature.kind is FeatureKind.PLANE


def test_axis_lifts_feature_only() -> None:
    axis = _entry("ax-1", NeutralEntityKind.AXIS, frame=_world())
    result = extract_candidates(_model([axis]))
    candidate = result.candidates[0]
    assert candidate.reference is None
    assert candidate.datum_feature.kind is FeatureKind.AXIS


def test_line_lifts_axis_feature_only() -> None:
    line = _entry("ln-1", NeutralEntityKind.LINE, frame=_world())
    result = extract_candidates(_model([line]))
    candidate = result.candidates[0]
    assert candidate.reference is None
    assert candidate.datum_feature.kind is FeatureKind.AXIS


def test_resolve_entity_frame_prefers_coordinate_frame() -> None:
    explicit = Frame(
        origin=Point3D(5.0, 0.0, 0.0),
        x_axis=Vector3D(1.0, 0.0, 0.0),
        y_axis=Vector3D(0.0, 1.0, 0.0),
        z_axis=Vector3D(0.0, 0.0, 1.0),
    )
    point_geometry = Point3D(0.0, 0.0, 0.0)
    entry = _entry(
        "p-1", NeutralEntityKind.POINT, frame=explicit, geometry=point_geometry
    )
    assert resolve_entity_frame(entry) == explicit


def test_resolve_entity_frame_derives_point_world_basis() -> None:
    entry = _entry(
        "p-1",
        NeutralEntityKind.POINT,
        geometry=Point3D(2.0, 3.0, 4.0),
    )
    frame = resolve_entity_frame(entry)
    assert frame is not None
    assert frame.origin == Point3D(2.0, 3.0, 4.0)
    assert frame.z_axis == Vector3D(0.0, 0.0, 1.0)
    assert frame.x_axis == Vector3D(1.0, 0.0, 0.0)


def test_resolve_entity_frame_plane_uses_normal_verbatim() -> None:
    entry = _entry(
        "pl-1",
        NeutralEntityKind.PLANE,
        geometry=Plane3D(Point3D(0.0, 0.0, 0.0), Vector3D(1.0, 2.0, 3.0)),
    )
    frame = resolve_entity_frame(entry)
    assert frame is not None
    assert frame.z_axis == Vector3D(1.0, 2.0, 3.0).normalize()


def test_resolve_entity_frame_line_uses_direction_verbatim() -> None:
    entry = _entry(
        "ln-1",
        NeutralEntityKind.LINE,
        geometry=Line3D(Point3D(0.0, 0.0, 0.0), Vector3D(0.0, 1.0, 0.0)),
    )
    frame = resolve_entity_frame(entry)
    assert frame is not None
    assert frame.z_axis == Vector3D(0.0, 1.0, 0.0).normalize()


def test_resolve_entity_frame_none_without_frame_or_geometry() -> None:
    entry = _entry("p-1", NeutralEntityKind.POINT)
    assert resolve_entity_frame(entry) is None


def test_resolve_entity_frame_face_uses_centroid_and_plane_normal() -> None:
    entry = _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    frame = resolve_entity_frame(entry)
    assert frame is not None
    assert frame.origin == Point3D(2.0, 2.0, 0.0)
    assert frame.z_axis == Vector3D(0.0, 0.0, 1.0)
    assert frame.x_axis == Vector3D(1.0, 0.0, 0.0)
    assert frame.y_axis == Vector3D(0.0, 1.0, 0.0)
    assert frame.x_axis.cross(frame.y_axis) == frame.z_axis


def test_resolve_entity_frame_face_prefers_explicit_coordinate_frame() -> None:
    explicit = Frame(
        origin=Point3D(5.0, 5.0, 5.0),
        x_axis=Vector3D(1.0, 0.0, 0.0),
        y_axis=Vector3D(0.0, 1.0, 0.0),
        z_axis=Vector3D(0.0, 0.0, 1.0),
    )
    entry = _entry(
        "f-1",
        NeutralEntityKind.PLANE,
        frame=explicit,
        geometry=_square_face(),
    )
    assert resolve_entity_frame(entry) == explicit


def test_resolve_entity_frame_face_is_deterministic() -> None:
    first = resolve_entity_frame(
        _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    )
    second = resolve_entity_frame(
        _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    )
    assert first is not None
    assert first == second


def test_face_entity_is_not_skipped_for_missing_frame() -> None:
    entry = _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    result = extract_candidates(_model([entry]))
    assert len(result.candidates) == 1
    assert result.skipped == ()


def test_face_candidate_preserves_identity_chain() -> None:
    entry = _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    candidate = extract_candidates(_model([entry])).candidates[0]
    source, neutral, domain = identity_chain(candidate)
    assert source == entry.identity.source_identity
    assert neutral == entry.identity
    assert domain.value == "f-1"
    bound = bind_reference(candidate)
    assert bound.source_identity == entry.identity.source_identity
    assert bound.neutral_identity == entry.identity


def test_face_candidate_carries_no_rank_or_role() -> None:
    entry = _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    candidate = extract_candidates(_model([entry])).candidates[0]
    assert isinstance(candidate.reference, ReferenceSurface)
    assert candidate.datum_feature.kind is FeatureKind.PLANE
    for name in ("rank", "score", "confidence"):
        assert not hasattr(candidate, name)


def test_face_lifts_through_full_datum_chain() -> None:
    entry = _entry("f-1", NeutralEntityKind.PLANE, geometry=_square_face())
    candidate = extract_candidates(_model([entry])).candidates[0]
    bound = bind_reference(candidate)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    frame = bind_datum_reference_frame("drf", [(bound, ConstraintType.PRIMARY)])
    assert frame.total_constrained == 3
    assert frame.remaining_free == 3
    assert frame.reference_frame == constraint.theoretical.frame


def test_unsupported_kind_is_skipped() -> None:
    for kind in (
        NeutralEntityKind.CURVE,
        NeutralEntityKind.SURFACE,
        NeutralEntityKind.SOLID_BODY,
        NeutralEntityKind.COMPONENT_INSTANCE,
        NeutralEntityKind.ANNOTATION_REFERENCE,
    ):
        entry = _entry("k", kind, frame=_world())
        result = extract_candidates(_model([entry]))
        assert result.candidates == ()
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "kind not eligible"


def test_generated_entity_is_skipped() -> None:
    entry = _entry(
        "g-1", NeutralEntityKind.PLANE, frame=_world(), source=False, generated=True
    )
    result = extract_candidates(_model([entry]))
    assert result.candidates == ()
    assert result.skipped[0].reason == "generated entity has no source provenance"


def test_entity_without_frame_is_skipped() -> None:
    entry = _entry("p-1", NeutralEntityKind.POINT)
    result = extract_candidates(_model([entry]))
    assert result.candidates == ()
    assert result.skipped[0].reason == "no resolvable coordinate frame"


def test_duplicate_domain_identity_skipped() -> None:
    # Two entities sharing the same neutral key but different kinds produce a
    # duplicate DomainIdentity; the later occurrence is skipped.
    a = _entry("dup", NeutralEntityKind.POINT, frame=_world())
    b = _entry("dup", NeutralEntityKind.PLANE, frame=_world())
    result = extract_candidates(_model([a, b]))
    assert len(result.candidates) == 1
    assert result.candidates[0].datum_feature.kind is FeatureKind.POINT
    assert result.skipped[0].reason == "duplicate domain identity in one model"


def test_empty_model_returns_empty_result() -> None:
    result = extract_candidates(_model([]))
    assert result.candidates == ()
    assert result.skipped == ()


def test_wrong_input_type_raises_type_error() -> None:
    with pytest.raises(TypeError):
        extract_candidates(object())  # type: ignore[arg-type]


def test_extraction_preserves_entity_order_and_is_deterministic() -> None:
    entries = [
        _entry("a", NeutralEntityKind.POINT, frame=_world()),
        _entry("b", NeutralEntityKind.PLANE, frame=_world()),
        _entry("ax", NeutralEntityKind.AXIS, frame=_world()),
    ]
    first = extract_candidates(_model(entries))
    second = extract_candidates(_model(entries))
    assert [c.entity_id for c in first.candidates] == ["a", "b", "ax"]
    assert first == second
def test_bridged_candidate_is_immutable() -> None:
    neutral = _neutral("p-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain_identity(neutral),
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="p-1", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="p-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(candidate, "datum_feature", None)  # noqa: B010


def test_skipped_candidate_is_immutable() -> None:
    neutral = _neutral("x", NeutralEntityKind.CURVE)
    skipped = SkippedCandidate(neutral, "kind not eligible")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(skipped, "reason", "changed")  # noqa: B010


def test_candidate_result_tuples_and_projections() -> None:
    entries = [
        _entry("p", NeutralEntityKind.POINT, frame=_world()),
        _entry("pl", NeutralEntityKind.PLANE, frame=_world()),
        _entry("ax", NeutralEntityKind.AXIS, frame=_world()),
    ]
    result = extract_candidates(_model(entries))
    assert isinstance(result.candidates, tuple)
    assert isinstance(result.skipped, tuple)
    refs = result.references()
    features = result.datum_features()
    assert len(refs) == 2
    assert all(isinstance(r, (ReferencePoint, ReferenceSurface)) for r in refs)
    assert len(features) == 3


def test_candidate_result_is_immutable() -> None:
    result = CandidateResult()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(result, "candidates", ())  # noqa: B010


def test_select_reference_records_explicit_role() -> None:
    reference = ReferenceSurface(entity_id="pl-1", frame=_world())
    locating = select_reference(reference, ConstraintType.PRIMARY)
    assert isinstance(locating, LocatingFeature)
    assert locating.reference == reference
    assert locating.constraint_type is ConstraintType.PRIMARY
    assert locating.manual is True


def test_select_reference_requires_explicit_type() -> None:
    reference = ReferenceSurface(entity_id="pl-1", frame=_world())
    with pytest.raises(TypeError):
        select_reference(reference)  # type: ignore[call-arg]


def test_bridge_exposes_no_datum_constructor() -> None:
    import origlyph.cad.bridge as module

    public = set(module.__all__)
    assert not {"datum", "Datum", "build_datum", "construct_drf"}.intersection(public)


def test_bridged_candidate_has_no_ranking_field() -> None:
    neutral = _neutral("p-1", NeutralEntityKind.POINT)
    candidate = BridgedCandidate(
        domain_identity=domain_identity(neutral),
        neutral_identity=neutral,
        reference=ReferencePoint(entity_id="p-1", frame=_world()),
        datum_feature=PhysicalFeature(
            entity_id="p-1", frame=_world(), kind=FeatureKind.POINT
        ),
    )
    for name in ("rank", "score", "confidence"):
        assert not hasattr(candidate, name)


def test_bridge_public_api_has_no_kernel_parser_persistence() -> None:
    import origlyph.cad.bridge as module

    for name in ("Kernel", "StepParser", "Persistence", "BRepTopology"):
        assert name not in module.__all__
        assert not hasattr(module, name)