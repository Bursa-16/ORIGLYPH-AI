"""Unit tests for origlyph.cad.role (Stage 3B explicit datum-role binding).

Contract under test: ``bind_datum_constraint`` binds an explicit
:class:`~origlyph.datum.ConstraintType` to a provenance-traced
:class:`~origlyph.cad.binding.BoundReference` and yields a validated
:class:`~origlyph.datum.DatumConstraint`, with NO role inference, NO
``LocatingFeature`` construction, and NO datum reference frame assembly.

Construction paths and provenance helpers mirror the established patterns in
``tests/unit/cad/test_binding.py`` so the Stage 3 boundary is exercised on the
same valid Stage 2B bindings.
"""
import dataclasses

import pytest

from origlyph.cad import (
    CadFormat,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    bind_datum_constraint,
)
from origlyph.cad.binding import BoundReference, bind_reference
from origlyph.cad.bridge import BridgedCandidate, extract_candidates
from origlyph.cad.model import NeutralEntityEntry, NeutralModel, SourceToNeutralMapping
from origlyph.datum import (
    Axis,
    ConstraintType,
    DatumConstraint,
    DatumReferenceFrame,
    FeatureKind,
    PhysicalFeature,
    TheoreticalDatum,
    constrained_axes,
)
from origlyph.geometry import Frame, Point3D, Vector3D


class _CustomError(Exception):
    """Sentinel exception to verify simulator errors propagate unchanged."""


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
) -> NeutralEntityIdentity:
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


def _bound(key: str, kind: NeutralEntityKind, *, frame=None) -> BoundReference:
    return bind_reference(_candidate(key, kind, frame=frame))


# Positive: deterministic role -> constraint mapping
def test_point_feature_assigned_primary() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert isinstance(constraint, DatumConstraint)
    assert constraint.sequence == 1
    assert constraint.constraint_type is ConstraintType.PRIMARY
    assert constraint.dof.constrained == frozenset({Axis.TZ, Axis.RX, Axis.RY})
    assert constraint.dof.constrained == constrained_axes(ConstraintType.PRIMARY)
    assert constraint.datum_feature is bound.datum_feature
    assert constraint.theoretical.feature is bound.datum_feature
    assert constraint.theoretical.kind is FeatureKind.POINT


def test_plane_feature_assigned_secondary() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    constraint = bind_datum_constraint(bound, ConstraintType.SECONDARY)
    assert constraint.sequence == 2
    assert constraint.constraint_type is ConstraintType.SECONDARY
    assert constraint.dof.constrained == frozenset({Axis.TY, Axis.RZ})
    assert constraint.dof.constrained == constrained_axes(ConstraintType.SECONDARY)
    assert constraint.datum_feature is bound.datum_feature
    assert constraint.theoretical.feature is bound.datum_feature


def test_axis_reference_none_assigned_tertiary() -> None:
    bound = _bound("ax-1", NeutralEntityKind.AXIS)
    assert bound.reference is None
    assert bound.datum_feature.kind is FeatureKind.AXIS
    constraint = bind_datum_constraint(bound, ConstraintType.TERTIARY)
    assert constraint.sequence == 3
    assert constraint.constraint_type is ConstraintType.TERTIARY
    assert constraint.dof.constrained == frozenset({Axis.TX})
    assert constraint.theoretical.feature is bound.datum_feature


def test_theoretical_feature_is_bound_datum_feature() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert constraint.theoretical.feature is bound.datum_feature
    assert constraint.theoretical.frame == bound.datum_feature.frame
    assert constraint.theoretical.kind is FeatureKind.POINT


def test_default_simulator_preserves_frame_and_kind() -> None:
    frame = _shifted()
    bound = _bound("p-1", NeutralEntityKind.POINT, frame=frame)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert constraint.theoretical.frame == bound.datum_feature.frame == frame
    assert constraint.theoretical.kind is FeatureKind.POINT
    assert constraint.theoretical.feature is bound.datum_feature


def test_all_roles_map_to_constrained_axes() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    for role in (
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
        ConstraintType.TERTIARY,
    ):
        constraint = bind_datum_constraint(bound, role)
        assert constraint.dof.constrained == constrained_axes(role)


def test_repeated_identical_construction_is_equal() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    a = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    b = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert a == b


def test_hash_equal_when_values_are_equal() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    a = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    b = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert a == b
    assert hash(a) == hash(b)


def test_bound_reference_unchanged_after_binding() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    reference = bound.reference
    datum_feature = bound.datum_feature
    neutral_identity = bound.neutral_identity
    domain_identity = bound.domain_identity
    source_identity = bound.source_identity
    bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert bound.reference is reference
    assert bound.datum_feature is datum_feature
    assert bound.neutral_identity is neutral_identity
    assert bound.domain_identity is domain_identity
    assert bound.source_identity is source_identity


def test_provenance_remains_on_bound_reference() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    # The bound reference retains full provenance ...
    assert bound.source_identity is not None
    assert bound.neutral_identity.source_identity is bound.source_identity
    assert bound.domain_identity.value == "p-1"
    # ... while the constraint carries only the shared feature, no identities.
    assert constraint.datum_feature is bound.datum_feature
    assert constraint.datum_feature.entity_id == bound.entity_id


def test_datum_constraint_has_no_invented_provenance_fields() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    for name in (
        "neutral_identity",
        "domain_identity",
        "source_identity",
        "reference",
    ):
        assert not hasattr(constraint, name)
    assert {f.name for f in dataclasses.fields(constraint)} == {
        "sequence",
        "datum_feature",
        "theoretical",
        "dof",
    }


def test_three_constraints_enter_existing_drf() -> None:
    c1 = bind_datum_constraint(
        _bound("p1", NeutralEntityKind.POINT), ConstraintType.PRIMARY
    )
    c2 = bind_datum_constraint(
        _bound("pl2", NeutralEntityKind.PLANE), ConstraintType.SECONDARY
    )
    c3 = bind_datum_constraint(
        _bound("pl3", NeutralEntityKind.PLANE), ConstraintType.TERTIARY
    )
    drf = DatumReferenceFrame(name="drf", constraints=(c1, c2, c3))
    assert drf.is_fully_located
    assert drf.remaining_free == 0


# Negative: fail-closed input validation


def test_non_bound_reference_input_raises_type_error() -> None:
    with pytest.raises(TypeError):
        bind_datum_constraint(
            object(), ConstraintType.PRIMARY  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        bind_datum_constraint(None, ConstraintType.PRIMARY)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_constraint(
            "not-a-bound-reference", ConstraintType.PRIMARY  # type: ignore[arg-type]
        )


def test_string_role_raises_type_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(TypeError):
        bind_datum_constraint(bound, "primary")  # type: ignore[arg-type]


def test_none_role_raises_type_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(TypeError):
        bind_datum_constraint(bound, None)  # type: ignore[arg-type]


def test_simulator_returns_none_raises_value_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(ValueError):
        bind_datum_constraint(
            bound,
            ConstraintType.PRIMARY,
            simulator=lambda _: None,  # type: ignore[arg-type]
        )


def test_simulator_returns_arbitrary_object_raises_value_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(ValueError):
        bind_datum_constraint(
            bound,
            ConstraintType.PRIMARY,
            simulator=lambda _: "not-a-theoretical-datum",  # type: ignore[arg-type]
        )


def test_simulator_returning_foreign_theoretical_raises_value_error() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    other = PhysicalFeature(entity_id="other", frame=_world(), kind=FeatureKind.PLANE)

    def foreign_simulator(feature: PhysicalFeature) -> TheoreticalDatum:
        return TheoreticalDatum(feature=other, frame=other.frame, kind=other.kind)

    with pytest.raises(ValueError):
        bind_datum_constraint(
            bound,
            ConstraintType.PRIMARY,
            simulator=foreign_simulator,
        )


def test_simulator_exception_propagates_unchanged() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)

    def boom_simulator(feature: PhysicalFeature) -> TheoreticalDatum:
        raise _CustomError("boom")

    with pytest.raises(_CustomError, match="boom"):
        bind_datum_constraint(
            bound,
            ConstraintType.PRIMARY,
            simulator=boom_simulator,
        )
