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

from origlyph.cad.binding import BoundReference
from origlyph.datum import (
    ConstraintType,
    DatumConstraint,
    DegreesOfFreedom,
    PhysicalFeature,
    Simulator,
    TheoreticalDatum,
    constrained_axes,
    default_simulator,
)

__all__ = [
    "bind_datum_constraint",
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
