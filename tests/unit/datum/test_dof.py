"""Unit tests for origlyph.datum.dof (deterministic 3-2-1 DOF model)."""
import dataclasses

import pytest

from origlyph.datum import (
    Axis,
    ConstraintEffect,
    ConstraintType,
    DegreesOfFreedom,
    constrained_axes,
)
from origlyph.geometry import Frame

_THREE_ROLES = (
    ConstraintType.PRIMARY,
    ConstraintType.SECONDARY,
    ConstraintType.TERTIARY,
)


def _world() -> Frame:
    return Frame.world()


def test_six_rigid_body_axes() -> None:
    assert len(set(Axis)) == 6
    assert {a.value for a in Axis} == {"tx", "ty", "tz", "rx", "ry", "rz"}


def test_degrees_of_freedom_is_immutable() -> None:
    dof = DegreesOfFreedom()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(dof, "constrained", frozenset())  # noqa: B010


def test_constrained_axes_3_2_1_mapping() -> None:
    assert constrained_axes(ConstraintType.PRIMARY) == frozenset(
        {Axis.TZ, Axis.RX, Axis.RY}
    )
    assert constrained_axes(ConstraintType.SECONDARY) == frozenset(
        {Axis.TY, Axis.RZ}
    )
    assert constrained_axes(ConstraintType.TERTIARY) == frozenset({Axis.TX})


def test_role_axes_are_disjoint_and_exhaustive() -> None:
    primary = constrained_axes(ConstraintType.PRIMARY)
    secondary = constrained_axes(ConstraintType.SECONDARY)
    tertiary = constrained_axes(ConstraintType.TERTIARY)
    assert not (primary & secondary)
    assert not (primary & tertiary)
    assert not (secondary & tertiary)
    assert (primary | secondary | tertiary) == frozenset(Axis)


def test_empty_constrained_state() -> None:
    empty = DegreesOfFreedom()
    assert empty.remaining == 6
    assert not empty.is_fully_constrained
    assert set(empty.free_axes) == set(Axis)
    assert empty.constrained == frozenset()


def test_full_constrained_state() -> None:
    full = DegreesOfFreedom(constrained=frozenset(Axis))
    assert full.remaining == 0
    assert full.is_fully_constrained
    assert set(full.free_axes) == set()
    assert full.constrained == frozenset(Axis)


def test_constrained_free_complement() -> None:
    dof = DegreesOfFreedom(constrained=frozenset({Axis.TX, Axis.TY}))
    assert dof.remaining == 4
    assert set(dof.free_axes) == set(Axis) - {Axis.TX, Axis.TY}
    assert frozenset(dof.constrained) == frozenset({Axis.TX, Axis.TY})


def test_constrain_is_deterministic_regardless_of_order() -> None:
    start = DegreesOfFreedom()
    first = start.constrain([Axis.TX, Axis.TY])
    second = start.constrain([Axis.TY, Axis.TX])
    assert first.constrained == second.constrained
    assert first.constrained == frozenset({Axis.TX, Axis.TY})
    assert first.remaining == 4
    assert start.remaining == 6


def test_constrain_dedups_duplicate_inputs() -> None:
    dof = DegreesOfFreedom().constrain([Axis.TX, Axis.TX, Axis.TX])
    assert dof.constrained == frozenset({Axis.TX})
    assert dof.remaining == 5


def test_constrain_empty_is_noop() -> None:
    dof = DegreesOfFreedom().constrain([])
    assert dof.constrained == frozenset()
    assert dof.remaining == 6


def test_constrain_is_idempotent_for_already_constrained() -> None:
    base = DegreesOfFreedom(constrained=frozenset({Axis.TX}))
    again = base.constrain([Axis.TX, Axis.TY])
    assert again.constrained == frozenset({Axis.TX, Axis.TY})
    assert again.remaining == 4
    assert base.remaining == 5


def test_full_3_2_1_reduction_loops() -> None:
    dof = DegreesOfFreedom()
    for ct in _THREE_ROLES:
        dof = dof.constrain(constrained_axes(ct))
    assert dof.is_fully_constrained
    assert dof.remaining == 0


def test_constraint_effect_carries_newly_constrained_and_remaining() -> None:
    initial = DegreesOfFreedom()
    axes = constrained_axes(ConstraintType.PRIMARY)
    effect = ConstraintEffect(
        constraint_type=ConstraintType.PRIMARY,
        newly_constrained=axes,
        remaining_state=initial.constrain(axes),
    )
    assert effect.constraint_type is ConstraintType.PRIMARY
    assert effect.newly_constrained == axes
    assert effect.remaining == 3
    assert not effect.fully_located


def test_constraint_effect_fully_located_at_full_reduction() -> None:
    cumulative = DegreesOfFreedom()
    effect: ConstraintEffect | None = None
    for ct in _THREE_ROLES:
        axes = constrained_axes(ct)
        remaining = cumulative.constrain(axes)
        cumulative = remaining
        effect = ConstraintEffect(
            constraint_type=ct,
            newly_constrained=axes,
            remaining_state=remaining,
        )
    assert cumulative.is_fully_constrained
    assert effect is not None
    assert effect.remaining == 0
    assert effect.fully_located
