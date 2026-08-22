"""Unit tests for origlyph.cad.evaluation (Stage 4B candidate evaluation).

Contract under test: ``evaluate_candidates`` converts an explicit
``Sequence[BoundReference]`` plus one explicitly requested
:class:`ConstraintType` into deterministic, advisory
:class:`CandidateEvaluation` records. It never binds a datum, never assembles
a frame, never infers a role, and never emits scoring or ranking.
"""
import dataclasses
import importlib
import inspect

import pytest

from origlyph.cad import (
    CadFormat,
    CandidateEvaluation,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    evaluate_candidates,
)
from origlyph.cad.binding import BoundReference, bind_reference
from origlyph.cad.bridge import BridgedCandidate, domain_identity, extract_candidates
from origlyph.cad.model import NeutralEntityEntry, NeutralModel, SourceToNeutralMapping
from origlyph.datum import (
    ConstraintType,
    EngineeringRationale,
    FeatureKind,
    PhysicalFeature,
    RecommendationConfidence,
    ReferencePoint,
    ReferenceSurface,
    ValidationState,
)
from origlyph.geometry import Frame, Point3D, Vector3D

_ROLES = (
    ConstraintType.PRIMARY,
    ConstraintType.SECONDARY,
    ConstraintType.TERTIARY,
)


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
) -> NeutralEntityEntry:
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


def _bound(key: str, kind: NeutralEntityKind, *, frame=None) -> BoundReference:
    return bind_reference(_candidate(key, kind, frame=frame))


def _feature(key: str, kind: NeutralEntityKind) -> PhysicalFeature:
    if kind is NeutralEntityKind.POINT:
        feature_kind = FeatureKind.POINT
    elif kind is NeutralEntityKind.PLANE:
        feature_kind = FeatureKind.PLANE
    else:
        feature_kind = FeatureKind.AXIS
    return PhysicalFeature(entity_id=key, frame=_world(), kind=feature_kind)


def _source_less_bound(key: str, kind: NeutralEntityKind) -> BoundReference:
    """A valid binding that carries no source provenance.

    Neutral identities require a source or ``generated=True``; extraction
    skips generated entities, so the candidate is constructed directly (same
    pattern as
    tests/unit/cad/test_bridge.py::test_identity_chain_source_none_for_generated).
    """
    neutral = _neutral(key, kind, source=False, generated=True)
    reference = None
    if kind is NeutralEntityKind.PLANE:
        reference = ReferenceSurface(entity_id=key, frame=_world())
    elif kind is NeutralEntityKind.POINT:
        reference = ReferencePoint(entity_id=key, frame=_world())
    candidate = BridgedCandidate(
        domain_identity=domain_identity(neutral),
        neutral_identity=neutral,
        reference=reference,
        datum_feature=_feature(key, kind),
    )
    return bind_reference(candidate)


def test_valid_plane_candidate_evaluated() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    result = evaluate_candidates([bound], ConstraintType.PRIMARY)
    assert len(result) == 1
    evaluation = result[0]
    assert isinstance(evaluation, CandidateEvaluation)
    assert evaluation.bound_reference is bound
    assert evaluation.eligible
    assert evaluation.validation is ValidationState.PASS


def test_valid_point_candidate_evaluated() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.eligible
    assert evaluation.bound_reference is bound
    assert evaluation.validation is ValidationState.PASS


def test_valid_axis_candidate_evaluated() -> None:
    bound = _bound("ax-1", NeutralEntityKind.AXIS)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.eligible
    assert evaluation.bound_reference.datum_feature.kind is FeatureKind.AXIS
    assert evaluation.validation is ValidationState.PASS


def test_primary_role_preserved() -> None:
    for kind in (
        NeutralEntityKind.POINT,
        NeutralEntityKind.PLANE,
        NeutralEntityKind.AXIS,
    ):
        bound = _bound("primary-candidate", kind)
        evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
        assert evaluation.constraint_type is ConstraintType.PRIMARY


def test_secondary_role_preserved() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evaluation = evaluate_candidates([bound], ConstraintType.SECONDARY)[0]
    assert evaluation.constraint_type is ConstraintType.SECONDARY


def test_tertiary_role_preserved() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evaluation = evaluate_candidates([bound], ConstraintType.TERTIARY)[0]
    assert evaluation.constraint_type is ConstraintType.TERTIARY


def test_multiple_candidates_preserve_input_order() -> None:
    bounds = [
        _bound("p-1", NeutralEntityKind.POINT),
        _bound("pl-1", NeutralEntityKind.PLANE),
        _bound("ax-1", NeutralEntityKind.AXIS),
    ]
    result = evaluate_candidates(bounds, ConstraintType.PRIMARY)
    assert [evaluation.bound_reference.entity_id for evaluation in result] == [
        "p-1",
        "pl-1",
        "ax-1",
    ]


def test_repeated_evaluation_is_equal() -> None:
    bounds = [
        _bound("p-1", NeutralEntityKind.POINT),
        _bound("pl-1", NeutralEntityKind.PLANE),
    ]
    first = evaluate_candidates(bounds, ConstraintType.PRIMARY)
    second = evaluate_candidates(bounds, ConstraintType.PRIMARY)
    assert first == second
    assert hash(first) == hash(second)


def test_candidate_evaluation_is_frozen() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(evaluation, "eligible", False)  # noqa: B010


def test_input_is_not_mutated() -> None:
    bounds = [
        _bound("p-1", NeutralEntityKind.POINT),
        _bound("pl-1", NeutralEntityKind.PLANE),
    ]
    before = [
        (
            bound.reference,
            bound.datum_feature,
            bound.neutral_identity,
            bound.domain_identity,
            bound.source_identity,
        )
        for bound in bounds
    ]
    evaluate_candidates(bounds, ConstraintType.PRIMARY)
    after = [
        (
            bound.reference,
            bound.datum_feature,
            bound.neutral_identity,
            bound.domain_identity,
            bound.source_identity,
        )
        for bound in bounds
    ]
    assert after == before


def test_bound_reference_provenance_is_retained() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.bound_reference is bound
    assert evaluation.bound_reference.neutral_identity == bound.neutral_identity
    assert evaluation.bound_reference.domain_identity == bound.domain_identity


def test_source_provenance_present_is_medium_confidence() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    assert bound.source_identity is not None
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.confidence is RecommendationConfidence.MEDIUM


def test_missing_source_provenance_is_low_confidence() -> None:
    bound = _source_less_bound("gen-1", NeutralEntityKind.POINT)
    assert bound.source_identity is None
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.confidence is RecommendationConfidence.LOW
    assert evaluation.validation is ValidationState.PASS


def test_high_confidence_is_not_emitted() -> None:
    bounds = [
        _bound("p-1", NeutralEntityKind.POINT),
        _bound("pl-1", NeutralEntityKind.PLANE),
        _bound("ax-1", NeutralEntityKind.AXIS),
    ]
    for role in _ROLES:
        for evaluation in evaluate_candidates(bounds, role):
            assert evaluation.confidence is not RecommendationConfidence.HIGH


def test_axis_reference_none_is_not_ineligible() -> None:
    bound = _bound("ax-1", NeutralEntityKind.AXIS)
    assert bound.reference is None
    evaluation = evaluate_candidates([bound], ConstraintType.TERTIARY)[0]
    assert evaluation.eligible
    assert any(item == "has_reference=false" for item in evaluation.evidence)


def test_plane_rationale_is_flat_surface() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.rationale is EngineeringRationale.FLAT_SURFACE


def test_axis_rationale_is_cylindrical_axis() -> None:
    bound = _bound("ax-1", NeutralEntityKind.AXIS)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.rationale is EngineeringRationale.CYLINDRICAL_AXIS


def test_point_rationale_is_custom() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert evaluation.rationale is EngineeringRationale.CUSTOM


def test_evidence_is_deterministic() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    first = evaluate_candidates([bound], ConstraintType.PRIMARY)[0].evidence
    second = evaluate_candidates([bound], ConstraintType.PRIMARY)[0].evidence
    assert first == second
    assert all(isinstance(item, str) for item in first)


def test_evidence_contains_role_context() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evidence = evaluate_candidates([bound], ConstraintType.PRIMARY)[0].evidence
    assert "role=primary" in evidence
    assert any(item.startswith("constrained_axes=") for item in evidence)


def test_evidence_contains_feature_kind() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evidence = evaluate_candidates([bound], ConstraintType.PRIMARY)[0].evidence
    assert f"feature_kind={bound.datum_feature.kind.value}" in evidence


def test_evidence_contains_reference_presence() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evidence = evaluate_candidates([bound], ConstraintType.SECONDARY)[0].evidence
    assert f"has_reference={str(bound.reference is not None).lower()}" in evidence


def test_evidence_contains_frame_presence() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evidence = evaluate_candidates([bound], ConstraintType.SECONDARY)[0].evidence
    assert f"has_frame={str(bound.datum_feature.frame is not None).lower()}" in evidence


def test_evidence_contains_provenance_presence() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evidence = evaluate_candidates([bound], ConstraintType.SECONDARY)[0].evidence
    has_source = f"has_source_identity={str(bound.source_identity is not None).lower()}"
    assert has_source in evidence
    assert f"generated={str(bound.neutral_identity.generated).lower()}" in evidence


def test_evidence_does_not_contain_area_or_size() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evidence = evaluate_candidates([bound], ConstraintType.PRIMARY)[0].evidence
    for item in evidence:
        assert "area" not in item.lower()
        assert "size" not in item.lower()


def test_empty_candidates_returns_empty_tuple() -> None:
    assert evaluate_candidates([], ConstraintType.PRIMARY) == ()


def test_non_sequence_candidates_raise_type_error() -> None:
    with pytest.raises(TypeError):
        evaluate_candidates("not-a-sequence", ConstraintType.PRIMARY)  # type: ignore[arg-type]
    bounds = [_bound("p-1", NeutralEntityKind.POINT)]
    with pytest.raises(TypeError):
        evaluate_candidates(
            iter(bounds),  # type: ignore[arg-type]
            ConstraintType.PRIMARY,
        )


def test_non_bound_reference_element_raises_type_error() -> None:
    bounds = [_bound("p0", NeutralEntityKind.POINT), object()]  # type: ignore[list-item]
    with pytest.raises(TypeError):
        evaluate_candidates(bounds, ConstraintType.PRIMARY)


def test_invalid_constraint_type_raises_type_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(TypeError):
        evaluate_candidates([bound], "primary")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        evaluate_candidates([bound], None)  # type: ignore[arg-type]


def test_output_is_tuple() -> None:
    bounds = [
        _bound("p-1", NeutralEntityKind.POINT),
        _bound("pl-1", NeutralEntityKind.PLANE),
        _bound("ax-1", NeutralEntityKind.AXIS),
    ]
    result = evaluate_candidates(bounds, ConstraintType.PRIMARY)
    assert isinstance(result, tuple)
    assert all(isinstance(evaluation, CandidateEvaluation) for evaluation in result)


def test_no_ranking_or_reordering() -> None:
    bounds = [
        _bound("z-1", NeutralEntityKind.POINT),
        _bound("a-1", NeutralEntityKind.PLANE),
        _bound("m-1", NeutralEntityKind.AXIS),
    ]
    result = evaluate_candidates(bounds, ConstraintType.PRIMARY)
    assert [evaluation.bound_reference.entity_id for evaluation in result] == [
        "z-1",
        "a-1",
        "m-1",
    ]
    assert all(
        evaluation.eligible and evaluation.validation is ValidationState.PASS
        for evaluation in result
    )


def test_evaluation_does_not_create_datum_constraint() -> None:
    module = importlib.import_module("origlyph.cad.evaluation")
    assert not hasattr(module, "DatumConstraint")
    assert "DatumConstraint" not in module.__all__
    bound = _bound("p-1", NeutralEntityKind.POINT)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert not hasattr(evaluation, "constraint")


def test_evaluation_does_not_create_drf() -> None:
    module = importlib.import_module("origlyph.cad.evaluation")
    assert not hasattr(module, "DatumReferenceFrame")
    assert "DatumReferenceFrame" not in module.__all__
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    evaluation = evaluate_candidates([bound], ConstraintType.PRIMARY)[0]
    assert not hasattr(evaluation, "frame")


def test_candidate_evaluation_fields_are_exactly_the_locked_set() -> None:
    fields = {field.name for field in dataclasses.fields(CandidateEvaluation)}
    assert fields == {
        "bound_reference",
        "constraint_type",
        "eligible",
        "validation",
        "confidence",
        "rationale",
        "evidence",
    }
    assert not fields & {
        "score",
        "rank",
        "entity_id",
        "neutral_identity",
        "domain_identity",
        "source_identity",
    }


def test_evaluation_module_does_not_reference_assignment_symbols() -> None:
    module = importlib.import_module("origlyph.cad.evaluation")
    source = inspect.getsource(module)
    for forbidden in (
        "bind_datum_constraint",
        "bind_datum_reference_frame",
        "DatumReferenceFrame",
        "DatumConstraint",
        "default_simulator",
        "Simulator",
    ):
        assert forbidden not in source