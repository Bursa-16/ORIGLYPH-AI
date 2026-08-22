"""Unit tests for origlyph.cad.role DRF assembly (Stage 3F).

Contract under test: ``bind_datum_reference_frame`` converts explicit
``(BoundReference, ConstraintType)`` assignments into constraints through
:func:`~origlyph.cad.bind_datum_constraint`, orders them by the resulting
``DatumConstraint.sequence``, and delegates every cross-constraint rule to
the existing :class:`~origlyph.datum.DatumReferenceFrame`. No role inference,
no duplicate/gap pre-validation, no provenance wrapper.

Fixture helpers mirror ``tests/unit/cad/test_role.py`` so assembly runs on
the same valid Stage 2B/3B bindings.
"""
import pytest

from origlyph.cad import (
    CadFormat,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    bind_datum_reference_frame,
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
    default_simulator,
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


# Positive: deterministic assembly through existing validation
def test_primary_only_builds_valid_partial_drf() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    drf = bind_datum_reference_frame("n", [(bound, ConstraintType.PRIMARY)])
    assert isinstance(drf, DatumReferenceFrame)
    assert len(drf.constraints) == 1
    constraint = drf.constraints[0]
    assert isinstance(constraint, DatumConstraint)
    assert constraint.sequence == 1
    assert constraint.constraint_type is ConstraintType.PRIMARY
    assert constraint.dof.constrained == constrained_axes(ConstraintType.PRIMARY)
    assert not drf.is_fully_located
    assert drf.remaining_free == 3
    assert drf.total_constrained == 3


def test_primary_secondary_builds_valid_partial_drf() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    drf = bind_datum_reference_frame(
        "n",
        [
            (secondary, ConstraintType.SECONDARY),
            (primary, ConstraintType.PRIMARY),
        ],
    )
    assert tuple(c.sequence for c in drf.constraints) == (1, 2)
    assert [c.constraint_type for c in drf.constraints] == [
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
    ]
    assert not drf.is_fully_located
    assert drf.remaining_free == 1
    assert drf.free_dof == frozenset({Axis.TX})


def test_full_321_builds_fully_located_drf() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    tertiary = _bound("pl-2", NeutralEntityKind.PLANE)
    drf = bind_datum_reference_frame(
        "n",
        [
            (tertiary, ConstraintType.TERTIARY),
            (primary, ConstraintType.PRIMARY),
            (secondary, ConstraintType.SECONDARY),
        ],
    )
    assert drf.is_fully_located
    assert drf.remaining_free == 0
    assert drf.total_constrained == 6
    assert not drf.free_dof
    assert tuple(c.sequence for c in drf.constraints) == (1, 2, 3)


def test_unordered_input_is_reordered_by_constraint_sequence() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    tertiary = _bound("ax-1", NeutralEntityKind.AXIS)
    drf = bind_datum_reference_frame(
        "n",
        [
            (secondary, ConstraintType.SECONDARY),
            (primary, ConstraintType.PRIMARY),
            (tertiary, ConstraintType.TERTIARY),
        ],
    )
    assert [c.constraint_type for c in drf.constraints] == [
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
        ConstraintType.TERTIARY,
    ]
    assert tuple(c.sequence for c in drf.constraints) == (1, 2, 3)
    assert drf.is_fully_located


def test_axis_can_participate_in_drf() -> None:
    primary = _bound("pl-1", NeutralEntityKind.PLANE)
    secondary = _bound("pl-2", NeutralEntityKind.PLANE)
    tertiary = _bound("ax-1", NeutralEntityKind.AXIS)
    assert tertiary.reference is None
    assert tertiary.datum_feature.kind is FeatureKind.AXIS
    drf = bind_datum_reference_frame(
        "n",
        [
            (tertiary, ConstraintType.TERTIARY),
            (secondary, ConstraintType.SECONDARY),
            (primary, ConstraintType.PRIMARY),
        ],
    )
    assert drf.is_fully_located
    tertiary_constraint = drf.constraints[2]
    assert tertiary_constraint.sequence == 3
    assert tertiary_constraint.datum_feature.kind is FeatureKind.AXIS
    assert tertiary_constraint.datum_feature.entity_id == "ax-1"


def test_reference_frame_comes_from_primary_theoretical() -> None:
    frame = _shifted()
    primary = _bound("p-1", NeutralEntityKind.POINT, frame=frame)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    drf = bind_datum_reference_frame(
        "n",
        [
            (secondary, ConstraintType.SECONDARY),
            (primary, ConstraintType.PRIMARY),
        ],
    )
    primary_constraint = drf.constraints[0]
    assert primary_constraint.sequence == 1
    assert drf.reference_frame == primary_constraint.theoretical.frame
    assert drf.reference_frame == primary.datum_feature.frame
    assert drf.reference_frame == frame


def test_same_inputs_produce_equal_drf() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    assignments = [
        (secondary, ConstraintType.SECONDARY),
        (primary, ConstraintType.PRIMARY),
    ]
    first = bind_datum_reference_frame("n", assignments)
    second = bind_datum_reference_frame("n", assignments)
    assert first == second


def test_hash_equal_for_equal_drf_if_hashable() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    assignments = [
        (secondary, ConstraintType.SECONDARY),
        (primary, ConstraintType.PRIMARY),
    ]
    first = bind_datum_reference_frame("n", assignments)
    second = bind_datum_reference_frame("n", assignments)
    assert first == second
    assert hash(first) == hash(second)


def test_input_bound_references_unchanged() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    bounds = (primary, secondary)
    snapshots = [
        (
            bound.reference,
            bound.datum_feature,
            bound.neutral_identity,
            bound.domain_identity,
            bound.source_identity,
        )
        for bound in bounds
    ]
    bind_datum_reference_frame(
        "n",
        [
            (secondary, ConstraintType.SECONDARY),
            (primary, ConstraintType.PRIMARY),
        ],
    )
    for bound, snapshot in zip(bounds, snapshots, strict=True):
        assert bound.reference is snapshot[0]
        assert bound.datum_feature is snapshot[1]
        assert bound.neutral_identity is snapshot[2]
        assert bound.domain_identity is snapshot[3]
        assert bound.source_identity is snapshot[4]


def test_provenance_remains_externally_available() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    tertiary = _bound("ax-1", NeutralEntityKind.AXIS)
    bounds = {
        "p-1": primary,
        "pl-1": secondary,
        "ax-1": tertiary,
    }
    drf = bind_datum_reference_frame(
        "n",
        [
            (tertiary, ConstraintType.TERTIARY),
            (primary, ConstraintType.PRIMARY),
            (secondary, ConstraintType.SECONDARY),
        ],
    )
    assert {bound.entity_id for bound in bounds.values()} == {
        constraint.datum_feature.entity_id for constraint in drf.constraints
    }
    for constraint in drf.constraints:
        bound = bounds[constraint.datum_feature.entity_id]
        assert constraint.datum_feature is bound.datum_feature
        assert bound.source_identity is not None
        assert bound.neutral_identity.source_identity is bound.source_identity
    # The frame and its constraints stay provenance-free.
    for forbidden in ("neutral_identity", "domain_identity", "source_identity"):
        assert not hasattr(drf, forbidden)
        for constraint in drf.constraints:
            assert not hasattr(constraint, forbidden)


def test_single_simulator_applies_to_all_assignments() -> None:
    calls: list[str] = []

    def spy(feature: PhysicalFeature) -> TheoreticalDatum:
        calls.append(feature.entity_id)
        return default_simulator(feature)

    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    tertiary = _bound("ax-1", NeutralEntityKind.AXIS)
    drf = bind_datum_reference_frame(
        "n",
        [
            (tertiary, ConstraintType.TERTIARY),
            (primary, ConstraintType.PRIMARY),
            (secondary, ConstraintType.SECONDARY),
        ],
        simulator=spy,
    )
    assert sorted(calls) == ["ax-1", "p-1", "pl-1"]
    for constraint in drf.constraints:
        assert constraint.theoretical.feature is constraint.datum_feature
        assert constraint.theoretical.frame == constraint.datum_feature.frame


# Negative: fail-closed delegation to existing domain validation


def test_empty_assignments_rejected() -> None:
    with pytest.raises(ValueError):
        bind_datum_reference_frame("n", [])


def test_secondary_only_rejected() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    with pytest.raises(ValueError):
        bind_datum_reference_frame("n", [(bound, ConstraintType.SECONDARY)])


def test_tertiary_only_rejected() -> None:
    bound = _bound("pl-1", NeutralEntityKind.PLANE)
    with pytest.raises(ValueError):
        bind_datum_reference_frame("n", [(bound, ConstraintType.TERTIARY)])


def test_primary_tertiary_gap_rejected() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    tertiary = _bound("pl-1", NeutralEntityKind.PLANE)
    with pytest.raises(ValueError):
        bind_datum_reference_frame(
            "n",
            [
                (primary, ConstraintType.PRIMARY),
                (tertiary, ConstraintType.TERTIARY),
            ],
        )


def test_duplicate_primary_rejected() -> None:
    first = _bound("p-1", NeutralEntityKind.POINT)
    second = _bound("p-2", NeutralEntityKind.POINT)
    with pytest.raises(ValueError):
        bind_datum_reference_frame(
            "n",
            [
                (first, ConstraintType.PRIMARY),
                (second, ConstraintType.PRIMARY),
            ],
        )


def test_duplicate_feature_rejected() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(ValueError):
        bind_datum_reference_frame(
            "n",
            [
                (bound, ConstraintType.PRIMARY),
                (bound, ConstraintType.SECONDARY),
            ],
        )


def test_non_sequence_assignments_rejected() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)

    def generate():
        yield (primary, ConstraintType.PRIMARY)

    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", generate())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", 123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", None)  # type: ignore[arg-type]


def test_malformed_assignment_tuple_rejected() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [(bound,)])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame(
            "n", [(bound, ConstraintType.PRIMARY, "x")]  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", ["not-a-tuple"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [None])  # type: ignore[arg-type]


def test_invalid_bound_reference_rejected() -> None:
    bad_str = ("not-a-bound-reference", ConstraintType.PRIMARY)
    bad_none = (None, ConstraintType.PRIMARY)
    bad_object = (object(), ConstraintType.PRIMARY)
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [bad_str])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [bad_none])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [bad_object])  # type: ignore[arg-type]


def test_invalid_constraint_type_rejected() -> None:
    bound = _bound("p-1", NeutralEntityKind.POINT)
    with pytest.raises(TypeError):
        bind_datum_reference_frame(
            "n", [(bound, "primary")]  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        bind_datum_reference_frame("n", [(bound, None)])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame(
            "n", [(bound, 123)]  # type: ignore[arg-type]
        )


def test_simulator_returning_invalid_object_rejected() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)
    with pytest.raises(ValueError):
        bind_datum_reference_frame(
            "n",
            [
                (primary, ConstraintType.PRIMARY),
                (secondary, ConstraintType.SECONDARY),
            ],
            simulator=lambda _: None,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        bind_datum_reference_frame(
            "n",
            [(primary, ConstraintType.PRIMARY)],
            simulator=lambda _: "not-a-theoretical-datum",  # type: ignore[arg-type]
        )


def test_simulator_exception_propagates() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    secondary = _bound("pl-1", NeutralEntityKind.PLANE)

    def boom(feature: PhysicalFeature) -> TheoreticalDatum:
        raise _CustomError("boom")

    with pytest.raises(_CustomError, match="boom"):
        bind_datum_reference_frame(
            "n",
            [
                (primary, ConstraintType.PRIMARY),
                (secondary, ConstraintType.SECONDARY),
            ],
            simulator=boom,
        )


def test_non_string_name_rejected() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    assignments = [(primary, ConstraintType.PRIMARY)]
    with pytest.raises(TypeError):
        bind_datum_reference_frame(None, assignments)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_datum_reference_frame(123, assignments)  # type: ignore[arg-type]


def test_empty_string_name_is_not_normalized_or_rejected() -> None:
    primary = _bound("p-1", NeutralEntityKind.POINT)
    drf = bind_datum_reference_frame("", [(primary, ConstraintType.PRIMARY)])
    assert drf.name == ""