"""Unit tests for origlyph.datum.selection (advisory recommendation types)."""
import dataclasses

import pytest

from origlyph.datum import (
    ConstraintType,
    DatumConstraint,
    DatumRecommendation,
    DegreesOfFreedom,
    EngineeringRationale,
    FeatureKind,
    ManualOverride,
    PhysicalFeature,
    RecommendationConfidence,
    Recommender,
    ValidationState,
    constrained_axes,
    default_simulator,
)
from origlyph.geometry import Frame

_ROLES = {
    1: ConstraintType.PRIMARY,
    2: ConstraintType.SECONDARY,
    3: ConstraintType.TERTIARY,
}


def _world() -> Frame:
    return Frame.world()


def _datum_constraint(seq: int = 1) -> DatumConstraint:
    role = _ROLES[seq]
    pf = PhysicalFeature(
        entity_id="f" + str(seq), frame=_world(), kind=FeatureKind.PLANE
    )
    th = default_simulator(pf)
    return DatumConstraint(
        sequence=seq,
        datum_feature=pf,
        theoretical=th,
        dof=DegreesOfFreedom(constrained=constrained_axes(role)),
    )


def test_validation_state_enum() -> None:
    assert ValidationState.UNVALIDATED.value == "unvalidated"
    assert ValidationState.PASS.value == "pass"
    assert ValidationState.FAIL.value == "fail"


def test_recommendation_confidence_enum() -> None:
    assert {c.value for c in RecommendationConfidence} == {"high", "medium", "low"}


def test_engineering_rationale_enum() -> None:
    expected = {
        "flat_surface",
        "cylindrical_axis",
        "planar_edge",
        "largest_face",
        "custom",
    }
    assert {r.value for r in EngineeringRationale} == expected


def test_manual_override_defaults_and_frozen() -> None:
    mo = ManualOverride()
    assert not mo.applied
    assert mo.justification is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(mo, "applied", True)  # noqa: B010


def test_datum_recommendation_is_advisory_and_frozen() -> None:
    rec = DatumRecommendation(
        constraint=_datum_constraint(1),
        confidence=RecommendationConfidence.HIGH,
        rationale=EngineeringRationale.FLAT_SURFACE,
        override=ManualOverride(applied=True, justification="manual pick"),
    )
    assert rec.is_advisory
    assert rec.confidence is RecommendationConfidence.HIGH
    assert rec.rationale is EngineeringRationale.FLAT_SURFACE
    assert rec.validation is ValidationState.UNVALIDATED
    assert rec.override.applied
    assert rec.override.justification == "manual pick"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(rec, "confidence", RecommendationConfidence.LOW)  # noqa: B010


def test_datum_recommendation_defaults_are_fail_closed() -> None:
    rec = DatumRecommendation(
        constraint=_datum_constraint(1),
        confidence=RecommendationConfidence.LOW,
        rationale=EngineeringRationale.CUSTOM,
    )
    assert rec.validation is ValidationState.UNVALIDATED
    assert not rec.override.applied
    assert rec.is_advisory


def test_datum_recommendation_accepts_str_rationale() -> None:
    rec = DatumRecommendation(
        constraint=_datum_constraint(1),
        confidence=RecommendationConfidence.MEDIUM,
        rationale="custom reason",
        validation=ValidationState.PASS,
    )
    assert rec.rationale == "custom reason"
    assert rec.validation is ValidationState.PASS


def test_recommender_is_protocol_not_auto_executed() -> None:
    assert isinstance(Recommender, type)
    assert hasattr(Recommender, "recommend")
    rec = DatumRecommendation(
        constraint=_datum_constraint(1),
        confidence=RecommendationConfidence.HIGH,
        rationale=EngineeringRationale.FLAT_SURFACE,
    )
    assert not hasattr(rec, "apply")
    assert not hasattr(rec, "execute")
    assert rec.is_advisory
