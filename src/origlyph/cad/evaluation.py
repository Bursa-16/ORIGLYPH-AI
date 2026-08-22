"""Deterministic candidate eligibility and evidence (Stage 4B).

Advisory recommendation boundary of the datum chain:

``Sequence[BoundReference]`` + an explicitly requested
:class:`~origlyph.datum.ConstraintType` are converted into deterministic,
advisory :class:`CandidateEvaluation` records for engineer review.

This module **IS** the ``RECOMMENDATION != ASSIGNMENT`` firewall. It never
simulates a datum, never constructs a constraint or a reference-frame object,
and never calls any Stage 3 binding function. Assigning an engineer-chosen
role to a candidate happens later, in a separate explicit step.

Evidence is derived only from fields the already-validated
:class:`~origlyph.cad.binding.BoundReference` actually carries. No scoring,
no ranking, no role inference, no invented engineering heuristics, no AI.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from origlyph.cad.binding import BoundReference
from origlyph.datum import (
    ConstraintType,
    EngineeringRationale,
    FeatureKind,
    RecommendationConfidence,
    ValidationState,
    constrained_axes,
)

__all__ = [
    "CandidateEvaluation",
    "evaluate_candidates",
]


@dataclass(frozen=True)
class CandidateEvaluation:
    """Advisory evaluation of one validated binding for one requested role.

    Frozen, value-comparable, hashable. The original
    :class:`~origlyph.cad.binding.BoundReference` is retained verbatim as the
    provenance anchor; no identity field is copied into this record.

    Fields
    ------
    bound_reference
        The actual validated binding being evaluated.
    constraint_type
        The explicitly requested evaluation role (never inferred).
    eligible
        Deterministic eligibility. Every valid BoundReference produced by the
        locked Stage 2 boundary is eligible; no repository-supported rule
        makes POINT/PLANE/AXIS ineligible for a role.
    validation
        Existing :class:`~origlyph.datum.ValidationState` for the evaluation.
        ``validation == ValidationState.PASS`` means only: *"the
        deterministic candidate-evaluation rules completed successfully for
        this validated binding."*

        ``PASS`` does **not** mean engineer approval, datum selected, datum
        assigned, preferred candidate, ranking, recommendation acceptance,
        or DRF acceptance. Those are separate, explicitly later actions.
        Evidence completeness is reported separately via ``confidence``;
        admissibility via ``eligible``.
    confidence
        Strength of the deterministic evidence: MEDIUM when the binding
        carries a source identity, LOW when provenance is absent. HIGH is
        never emitted by this stage.
    rationale
        Deterministic rationale derived from the feature kind only.
    evidence
        Fixed-order, deterministic evidence strings derived from the actual
        fields of ``bound_reference`` and ``constraint_type``.
    """

    bound_reference: BoundReference
    constraint_type: ConstraintType
    eligible: bool
    validation: ValidationState
    confidence: RecommendationConfidence
    rationale: EngineeringRationale | str
    evidence: tuple[str, ...]


def evaluate_candidates(
    candidates: Sequence[BoundReference],
    constraint_type: ConstraintType,
) -> tuple[CandidateEvaluation, ...]:
    """Evaluate validated bindings for one explicit role (advisory only).

    Produces one :class:`CandidateEvaluation` per candidate, preserving input
    order. The evaluation is purely advisory: it never binds a datum, never
    assembles a frame, and never infers or assigns a role.

    Parameters
    ----------
    candidates
        Already-validated Stage 2 bindings to evaluate.
    constraint_type
        The explicitly requested role context (PRIMARY / SECONDARY /
        TERTIARY). Never inferred.

    Returns
    -------
    tuple[CandidateEvaluation, ...]
        Deterministic evaluations in input order. An empty sequence of
        candidates yields an empty tuple (a legitimate engineering signal).

    Raises
    ------
    TypeError
        If ``candidates`` is not a ``Sequence``, any element is not a
        :class:`BoundReference`, or ``constraint_type`` is not a
        :class:`ConstraintType`.
    """
    if not isinstance(constraint_type, ConstraintType):
        raise TypeError("constraint_type must be a ConstraintType")
    if not isinstance(candidates, Sequence):
        raise TypeError("evaluate_candidates requires a Sequence of BoundReference")

    evaluations: list[CandidateEvaluation] = []
    for candidate in candidates:
        if not isinstance(candidate, BoundReference):
            raise TypeError("every candidate must be a BoundReference")
        evaluations.append(_evaluate_one(candidate, constraint_type))
    return tuple(evaluations)


def _evaluate_one(
    candidate: BoundReference,
    constraint_type: ConstraintType,
) -> CandidateEvaluation:
    """Build the evidence and advisory record for one candidate."""
    feature_kind = candidate.datum_feature.kind

    rationale: EngineeringRationale | str
    if feature_kind is FeatureKind.PLANE:
        rationale = EngineeringRationale.FLAT_SURFACE
    elif feature_kind is FeatureKind.AXIS:
        rationale = EngineeringRationale.CYLINDRICAL_AXIS
    else:
        rationale = EngineeringRationale.CUSTOM

    source_identity = candidate.source_identity
    confidence = (
        RecommendationConfidence.MEDIUM
        if source_identity is not None
        else RecommendationConfidence.LOW
    )

    evidence = (
        f"role={constraint_type.value}",
        f"feature_kind={feature_kind.value}",
        f"has_reference={str(candidate.reference is not None).lower()}",
        f"has_frame={str(candidate.datum_feature.frame is not None).lower()}",
        f"has_source_identity={str(source_identity is not None).lower()}",
        f"generated={str(candidate.neutral_identity.generated).lower()}",
        "constrained_axes="
        + ",".join(sorted(axis.value for axis in constrained_axes(constraint_type))),
    )

    return CandidateEvaluation(
        bound_reference=candidate,
        constraint_type=constraint_type,
        eligible=True,
        validation=ValidationState.PASS,
        confidence=confidence,
        rationale=rationale,
        evidence=evidence,
    )