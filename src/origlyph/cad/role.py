"""Deterministic datum-role binding for a validated CAD reference (Stage 3B).

Minimal, fail-closed bridge from a provenance-traced
:class:`~origlyph.cad.binding.BoundReference` plus an explicit, engineer-supplied
:class:`~origlyph.datum.ConstraintType` to a validated
:class:`~origlyph.datum.DatumConstraint`.

No role inference is performed: the explicit ``ConstraintType`` is the
authoritative input. The module reuses the existing datum-domain primitives
(:func:`~origlyph.datum.constrained_axes`,
:class:`~origlyph.datum.DegreesOfFreedom`,
:func:`~origlyph.datum.default_simulator`,
:class:`~origlyph.datum.DatumConstraint`) and adds no new domain types, no new
validation logic, and no CAD/geometry knowledge. Axis features (whose
:class:`~origlyph.cad.binding.BoundReference` legitimately carries
``reference=None``) are supported directly, because
:class:`~origlyph.datum.DatumConstraint` carries no reference and therefore
needs none.
"""
from __future__ import annotations

from collections.abc import Sequence

from origlyph.cad.binding import BoundReference
from origlyph.datum import (
    ConstraintType,
    DatumConstraint,
    DatumReferenceFrame,
    DegreesOfFreedom,
    PhysicalFeature,
    Simulator,
    TheoreticalDatum,
    constrained_axes,
    default_simulator,
)

__all__ = [
    "bind_datum_constraint",
    "bind_datum_reference_frame",
]

# Explicit, deterministic, non-inferred mapping of engineering role to the
# 3-2-1 positional sequence stored by DatumConstraint. This is the inverse of
# the private datum.datum_reference_frame._SEQUENCE_TO_ROLE (kept private there
# on purpose). DatumConstraint.__post_init__ re-validates role/DOF coherence, so
# any drift fails closed instead of silently corrupting a frame.
_ROLE_TO_SEQUENCE = {
    ConstraintType.PRIMARY: 1,
    ConstraintType.SECONDARY: 2,
    ConstraintType.TERTIARY: 3,
}


def bind_datum_constraint(
    bound_reference: BoundReference,
    constraint_type: ConstraintType,
    *,
    simulator: Simulator = default_simulator,
) -> DatumConstraint:
    """Bind an explicit engineering role to a provenance-traced binding.

    Produces a validated :class:`~origlyph.datum.DatumConstraint` whose
    ``datum_feature`` is the bound reference's datum feature, whose
    ``theoretical`` datum is produced by ``simulator``, and whose
    :class:`~origlyph.datum.DegreesOfFreedom` is the deterministic 3-2-1 set
    for ``constraint_type``.

    Parameters
    ----------
    bound_reference
        A validated, provenance-traced binding from Stage 2B.
    constraint_type
        The explicit engineering role (PRIMARY / SECONDARY / TERTIARY).
    simulator
        Deterministic feature -> theoretical-datum simulator
        (:func:`~origlyph.datum.default_simulator` by default). Injected, never
        inferred. Simulator exceptions propagate unchanged.

    Returns
    -------
    DatumConstraint
        A constraint validated by the existing datum-domain constructor.

    Raises
    ------
    TypeError
        If ``bound_reference`` is not a :class:`BoundReference` or
        ``constraint_type`` is not a :class:`ConstraintType`.
    ValueError
        If ``simulator`` does not return a :class:`~origlyph.datum.TheoreticalDatum`,
        or if :class:`~origlyph.datum.DatumConstraint` validation rejects the
        constructed constraint.
    """
    if not isinstance(bound_reference, BoundReference):
        raise TypeError("bind_datum_constraint requires a BoundReference")
    if not isinstance(constraint_type, ConstraintType):
        raise TypeError("constraint_type must be a ConstraintType")

    datum_feature: PhysicalFeature = bound_reference.datum_feature
    theoretical: TheoreticalDatum = simulator(datum_feature)
    if not isinstance(theoretical, TheoreticalDatum):
        raise ValueError("simulator must return a TheoreticalDatum")

    dof = DegreesOfFreedom(constrained=constrained_axes(constraint_type))
    sequence = _ROLE_TO_SEQUENCE[constraint_type]

    return DatumConstraint(
        sequence=sequence,
        datum_feature=datum_feature,
        theoretical=theoretical,
        dof=dof,
    )


def bind_datum_reference_frame(
    name: str,
    assignments: Sequence[tuple[BoundReference, ConstraintType]],
    *,
    simulator: Simulator = default_simulator,
) -> DatumReferenceFrame:
    """Assemble explicit role assignments into a validated DRF.

    Converts ``(BoundReference, ConstraintType)`` assignments into
    :class:`~origlyph.datum.DatumConstraint` objects through
    :func:`bind_datum_constraint`, orders the constraints deterministically
    by their resulting ``sequence``, and delegates every cross-constraint
    rule (non-empty, contiguity, duplicate sequence, duplicate feature, DOF
    overlap) to the existing :class:`~origlyph.datum.DatumReferenceFrame`.

    The single ordering authority is the produced
    ``DatumConstraint.sequence`` — never the input order and never a second
    role→sequence map. Input order is irrelevant on success paths: unordered
    assignments such as SECONDARY, PRIMARY, TERTIARY yield constraints
    ordered 1, 2, 3. This is ordering only; roles come exclusively from the
    explicit assignments.

    Parameters
    ----------
    name
        Verbatim frame name. Never normalized, stripped, or rejected beyond
        requiring ``str`` (existing ``DatumReferenceFrame`` imposes no name
        semantics).
    assignments
        Explicit assignments; every item is exactly a
        ``(bound_reference, constraint_type)`` pair. Any prefix that starts
        with PRIMARY yields a valid partial frame; gaps, duplicates, and
        over-constraining fail through existing domain validation.
    simulator
        One shared deterministic simulator applied to every assignment
        (:func:`~origlyph.datum.default_simulator` by default). Its
        exceptions propagate unchanged.

    Returns
    -------
    DatumReferenceFrame
        A validated frame. Provenance-free by design: callers retain the
        original :class:`BoundReference` objects and associate them with the
        resulting constraints through ``entity_id``.

    Raises
    ------
    TypeError
        If ``name`` is not ``str``, ``assignments`` is not a ``Sequence``,
        or an item is not exactly a 2-tuple.
    ValueError
        Propagated unchanged from existing validation: element types and
        simulator output (via :func:`bind_datum_constraint`) and the
        empty/duplicate/gap/overlap rules (via
        :class:`~origlyph.datum.DatumReferenceFrame`).
    """
    if not isinstance(name, str):
        raise TypeError("bind_datum_reference_frame requires a string name")
    if not isinstance(assignments, Sequence):
        raise TypeError(
            "bind_datum_reference_frame requires a sequence of assignments"
        )

    constraints: list[DatumConstraint] = []
    for item in assignments:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                "each assignment must be a "
                "(bound_reference, constraint_type) tuple"
            )
        bound_reference, constraint_type = item
        constraints.append(
            bind_datum_constraint(
                bound_reference,
                constraint_type,
                simulator=simulator,
            )
        )

    ordered = tuple(
        sorted(
            constraints,
            key=lambda constraint: constraint.sequence,
        )
    )

    return DatumReferenceFrame(
        name=name,
        constraints=ordered,
    )
