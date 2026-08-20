"""Unit tests for origlyph.datum.datum (features, datums, simulator)."""
import dataclasses

import pytest

from origlyph.datum import (
    Datum,
    DatumFeatureSimulator,
    FeatureKind,
    PhysicalFeature,
    TheoreticalDatum,
    default_simulator,
)
from origlyph.geometry import Frame


def _world() -> Frame:
    return Frame.world()


def _call(cls, *args, **kwargs):
    return cls(*args, **kwargs)


def test_physical_feature_is_frozen() -> None:
    f = PhysicalFeature(entity_id="f1", frame=_world())
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(f, "entity_id", "f2")  # noqa: B010


def test_valid_physical_feature_construction_defaults() -> None:
    f = PhysicalFeature(entity_id="f1", frame=_world())
    assert f.entity_id == "f1"
    assert f.frame == _world()
    assert f.kind is FeatureKind.PLANE
    assert f.name is None


def test_physical_feature_accepts_named_fields() -> None:
    f = PhysicalFeature(
        entity_id="cyl-1", frame=_world(), kind=FeatureKind.CYLINDER, name="C"
    )
    assert f.kind is FeatureKind.CYLINDER
    assert f.name == "C"


def test_empty_entity_id_is_not_prevented_by_contract() -> None:
    # Current production contract: PhysicalFeature has no __post_init__
    # validation, so an empty entity_id is accepted (not rejected).
    f = PhysicalFeature(entity_id="", frame=_world())
    assert f.entity_id == ""
    assert f.kind is FeatureKind.PLANE


def test_theoretical_datum_is_not_physical_feature() -> None:
    pf = PhysicalFeature(entity_id="f1", frame=_world(), kind=FeatureKind.PLANE)
    td = default_simulator(pf)
    assert isinstance(td, TheoreticalDatum)
    assert isinstance(pf, PhysicalFeature)
    assert not isinstance(td, PhysicalFeature)
    assert not isinstance(pf, TheoreticalDatum)
    assert td.feature is pf
    assert td.frame == pf.frame
    assert td.kind is pf.kind


@pytest.mark.parametrize(
    "kind", [FeatureKind.POINT, FeatureKind.AXIS, FeatureKind.PLANE]
)
def test_default_simulator_maps_point_line_plane(kind: FeatureKind) -> None:
    pf = PhysicalFeature(entity_id="k", frame=_world(), kind=kind)
    td = default_simulator(pf)
    assert td.kind is kind
    assert td.feature is pf
    assert td.frame == pf.frame


def test_default_simulator_is_deterministic() -> None:
    pf = PhysicalFeature(entity_id="f1", frame=_world(), kind=FeatureKind.AXIS)
    a = default_simulator(pf)
    b = default_simulator(pf)
    assert a.feature is b.feature is pf
    assert a.frame == b.frame == pf.frame
    assert a.kind is b.kind is FeatureKind.AXIS


def test_datum_feature_simulator_protocol_shape() -> None:
    assert isinstance(DatumFeatureSimulator, type)
    assert hasattr(DatumFeatureSimulator, "simulate")
    pf = PhysicalFeature(entity_id="f1", frame=_world())
    td = default_simulator(pf)
    assert isinstance(td, TheoreticalDatum)
    assert not isinstance(td, PhysicalFeature)


def test_datum_construction_bindings() -> None:
    pf = PhysicalFeature(entity_id="axis-1", frame=_world(), kind=FeatureKind.AXIS)
    td = default_simulator(pf)
    d = Datum(name="A", theoretical=td, rationale="largest face")
    assert d.name == "A"
    assert d.theoretical is td
    assert d.theoretical.feature is pf
    assert d.rationale == "largest face"


def test_datum_default_rationale_is_none() -> None:
    pf = PhysicalFeature(entity_id="f1", frame=_world())
    d = Datum(name="A", theoretical=default_simulator(pf))
    assert d.rationale is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(d, "name", "B")  # noqa: B010


def test_datum_is_frozen() -> None:
    pf = PhysicalFeature(entity_id="x", frame=_world())
    d = Datum(name="A", theoretical=default_simulator(pf))
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(d, "rationale", "changed")  # noqa: B010


def test_invalid_construction_raises() -> None:
    with pytest.raises(TypeError):
        _call(PhysicalFeature, frame=_world())
    with pytest.raises(TypeError):
        _call(TheoreticalDatum)
    with pytest.raises(TypeError):
        _call(Datum)
