"""Unit tests for origlyph.datum.reference (references / locating convention)."""
import dataclasses

import pytest

from origlyph.datum import (
    ConstraintType,
    Datum,
    LocatingFeature,
    PhysicalFeature,
    ReferenceConvention,
    ReferenceKind,
    ReferencePoint,
    ReferenceSurface,
    TheoreticalDatum,
    default_simulator,
)
from origlyph.geometry import Frame


def _world() -> Frame:
    return Frame.world()


def _call(cls, *args, **kwargs):
    return cls(*args, **kwargs)


def test_reference_kind_defaults() -> None:
    s = ReferenceSurface(entity_id="s1", frame=_world())
    p = ReferencePoint(entity_id="p1", frame=_world())
    assert s.kind is ReferenceKind.SURFACE
    assert p.kind is ReferenceKind.POINT
    assert isinstance(s, (ReferenceSurface, ReferencePoint))
    assert isinstance(p, (ReferenceSurface, ReferencePoint))
    assert s.frame == p.frame == _world()


def test_reference_point_is_not_theoretical_datum() -> None:
    pf = PhysicalFeature(entity_id="f1", frame=_world())
    td = default_simulator(pf)
    rp = ReferencePoint(entity_id="p1", frame=_world())
    assert isinstance(rp, ReferencePoint)
    assert isinstance(td, TheoreticalDatum)
    assert not isinstance(rp, TheoreticalDatum)
    assert not isinstance(td, ReferencePoint)


def test_reference_surface_is_not_datum() -> None:
    rs = ReferenceSurface(entity_id="s1", frame=_world())
    pf = PhysicalFeature(entity_id="A", frame=_world())
    d = Datum(name="A", theoretical=default_simulator(pf))
    assert not isinstance(rs, Datum)
    assert not isinstance(d, ReferenceSurface)
    assert isinstance(d, Datum)


def test_locating_feature_is_not_datum() -> None:
    rp = ReferencePoint(entity_id="p1", frame=_world())
    lf = LocatingFeature(reference=rp, constraint_type=ConstraintType.PRIMARY)
    assert isinstance(lf, LocatingFeature)
    assert not isinstance(lf, Datum)
    assert lf.reference is rp
    assert lf.constraint_type is ConstraintType.PRIMARY
    assert lf.manual is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(lf, "manual", True)  # noqa: B010


def test_reference_convention_deterministic_ordering() -> None:
    rp = ReferencePoint(entity_id="p1", frame=_world())
    rs = ReferenceSurface(entity_id="s1", frame=_world())
    conv = ReferenceConvention(
        name="c1",
        locating=(
            LocatingFeature(reference=rp, constraint_type=ConstraintType.TERTIARY),
            LocatingFeature(reference=rs, constraint_type=ConstraintType.PRIMARY),
            LocatingFeature(reference=rp, constraint_type=ConstraintType.SECONDARY),
        ),
    )
    assert conv.roles() == (
        ConstraintType.TERTIARY,
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
    )
    assert [lf.constraint_type for lf in conv.locating] == list(conv.roles())


def test_reference_convention_default_locating_is_empty() -> None:
    conv = ReferenceConvention(name="c0")
    assert conv.locating == ()
    assert conv.roles() == ()


def test_reference_objects_are_immutable() -> None:
    rs = ReferenceSurface(entity_id="s", frame=_world())
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(rs, "entity_id", "z")  # noqa: B010
    rp = ReferencePoint(entity_id="p", frame=_world())
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(rp, "entity_id", "z")  # noqa: B010
    conv = ReferenceConvention(name="c")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(conv, "name", "other")  # noqa: B010


def test_reference_point_requires_entity_id_and_frame() -> None:
    with pytest.raises(TypeError):
        _call(ReferencePoint)
    with pytest.raises(TypeError):
        _call(ReferenceSurface, frame=_world())
