"""Unit tests for origlyph.datum.datum_reference_frame (3-2-1 DatumReferenceFrame)."""
import dataclasses

import pytest

from origlyph.datum import (
    Axis,
    ConstrainedResult,
    ConstraintType,
    DatumConstraint,
    DatumReferenceFrame,
    DegreesOfFreedom,
    FeatureKind,
    PhysicalFeature,
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


def _datum_constraint(seq: int, entity: str) -> DatumConstraint:
    role = _ROLES[seq]
    pf = PhysicalFeature(entity_id=entity, frame=_world(), kind=FeatureKind.PLANE)
    th = default_simulator(pf)
    return DatumConstraint(
        sequence=seq,
        datum_feature=pf,
        theoretical=th,
        dof=DegreesOfFreedom(constrained=constrained_axes(role)),
    )


def _call(cls, *args, **kwargs):
    return cls(*args, **kwargs)


def _full_frame() -> DatumReferenceFrame:
    return DatumReferenceFrame(
        name="drf",
        constraints=(
            _datum_constraint(1, "A"),
            _datum_constraint(2, "B"),
            _datum_constraint(3, "C"),
        ),
    )


def test_datum_constraint_is_frozen_and_mapped_to_role() -> None:
    c = _datum_constraint(1, "A")
    assert isinstance(c, DatumConstraint)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(c, "sequence", 9)  # noqa: B010
    assert c.sequence == 1
    assert c.constraint_type is ConstraintType.PRIMARY
    assert _datum_constraint(2, "B").constraint_type is ConstraintType.SECONDARY
    assert _datum_constraint(3, "C").constraint_type is ConstraintType.TERTIARY


def test_invalid_sequence_rejected() -> None:
    pf = PhysicalFeature(entity_id="x", frame=_world())
    th = default_simulator(pf)
    good_dof = DegreesOfFreedom(constrained=constrained_axes(ConstraintType.PRIMARY))
    for bad in (0, 4, -1, 9):
        with pytest.raises(ValueError):
            _call(
                DatumConstraint,
                sequence=bad,
                datum_feature=pf,
                theoretical=th,
                dof=good_dof,
            )


def test_overlapping_dof_rejected() -> None:
    pf = PhysicalFeature(entity_id="x", frame=_world())
    th = default_simulator(pf)
    with pytest.raises(ValueError):
        _call(
            DatumConstraint,
            sequence=1,
            datum_feature=pf,
            theoretical=th,
            dof=DegreesOfFreedom(constrained=frozenset({Axis.TX})),
        )


def test_mismatched_feature_rejected() -> None:
    pf1 = PhysicalFeature(entity_id="x", frame=_world())
    pf2 = PhysicalFeature(entity_id="y", frame=_world())
    th2 = default_simulator(pf2)
    with pytest.raises(ValueError):
        _call(
            DatumConstraint,
            sequence=1,
            datum_feature=pf1,
            theoretical=th2,
            dof=DegreesOfFreedom(constrained=constrained_axes(ConstraintType.PRIMARY)),
        )


def test_fully_located_frame_3_2_1() -> None:
    drf = _full_frame()
    assert drf.is_fully_located
    assert drf.total_constrained == 6
    assert drf.remaining_free == 0
    assert not drf.free_dof
    assert drf.constrained_dof.is_fully_constrained
    assert set(drf.free_dof) == set()


def test_partial_frame_does_not_infer_missing() -> None:
    drf = DatumReferenceFrame(name="p", constraints=(_datum_constraint(1, "A"),))
    assert not drf.is_fully_located
    assert drf.remaining_free == 3
    assert drf.total_constrained == 3
    assert drf.free_dof == frozenset(Axis) - constrained_axes(ConstraintType.PRIMARY)


def test_reference_frame_uses_primary_theoretical() -> None:
    c1 = _datum_constraint(1, "A")
    drf = _full_frame()
    assert drf.reference_frame == c1.theoretical.frame


def test_drf_objects_are_immutable() -> None:
    c = _datum_constraint(1, "A")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(c, "sequence", 2)  # noqa: B010
    drf = _full_frame()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(drf, "name", "other")  # noqa: B010


def test_duplicate_sequence_rejected() -> None:
    with pytest.raises(ValueError):
        _call(
            DatumReferenceFrame,
            name="bad",
            constraints=(_datum_constraint(1, "A"), _datum_constraint(1, "B")),
        )


def test_duplicate_feature_rejected() -> None:
    with pytest.raises(ValueError):
        _call(
            DatumReferenceFrame,
            name="bad",
            constraints=(_datum_constraint(1, "A"), _datum_constraint(2, "A")),
        )


def test_out_of_order_sequence_rejected() -> None:
    with pytest.raises(ValueError):
        _call(
            DatumReferenceFrame,
            name="bad",
            constraints=(_datum_constraint(2, "B"), _datum_constraint(1, "A")),
        )


def test_empty_constraints_rejected() -> None:
    with pytest.raises(ValueError):
        _call(DatumReferenceFrame, name="bad", constraints=())


def test_sequences_and_roles_are_deterministic_ordered() -> None:
    drf = _full_frame()
    assert tuple(c.sequence for c in drf.constraints) == (1, 2, 3)
    assert [c.constraint_type for c in drf.constraints] == [
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
        ConstraintType.TERTIARY,
    ]


def test_constrained_result_behavior() -> None:
    drf = _full_frame()
    res = ConstrainedResult(frame=drf, constrained_dof=drf.constrained_dof)
    assert res.frame is drf
    assert res.is_fully_located
    assert res.remaining == 0
    assert set(res.constrained) == set(Axis)
    assert not res.free


def test_constrained_result_partial() -> None:
    drf = DatumReferenceFrame(name="p", constraints=(_datum_constraint(1, "A"),))
    res = ConstrainedResult(frame=drf, constrained_dof=drf.constrained_dof)
    assert not res.is_fully_located
    assert res.remaining == 3
    assert len(res.free) == 3
    assert set(res.constrained) == set(constrained_axes(ConstraintType.PRIMARY))
