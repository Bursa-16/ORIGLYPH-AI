"""Deterministic datum reference frame assembly (3-2-1 locating).

Stage 1B foundation. Immutable value types that assemble an ordered 3-2-1
constraint sequence into a deterministic rigidity result. This module holds
only deterministic engineering logic: no CAD ingestion, no standards
corpus, no recommendation/AI logic, and no persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple

from origlyph.geometry import Frame

from .datum import (
    PhysicalFeature,
    TheoreticalDatum,
)
from .dof import (
    Axis,
    ConstraintType,
    DegreesOfFreedom,
    constrained_axes,
)

# Explicit deterministic precedence for the 3-2-1 locating principle:
# position 1 -> primary, 2 -> secondary, 3 -> tertiary.
_SEQUENCE_TO_ROLE: dict[int, ConstraintType] = {
    1: ConstraintType.PRIMARY,
    2: ConstraintType.SECONDARY,
    3: ConstraintType.TERTIARY,
}


@dataclass(frozen=True)
class DatumConstraint:
    """A single locating element: an ordered datum reference and its DOF."""

    sequence: int
    datum_feature: PhysicalFeature
    theoretical: TheoreticalDatum
    dof: DegreesOfFreedom

    def __post_init__(self) -> None:
        role = _SEQUENCE_TO_ROLE.get(self.sequence)
        if role is None:
            raise ValueError(
                f"sequence {self.sequence} is not a 3-2-1 role (1, 2, 3)"
            )
        expected_axes = constrained_axes(role)
        if self.dof.constrained != expected_axes:
            actual = sorted(a.value for a in self.dof.constrained)
            want = sorted(a.value for a in expected_axes)
            raise ValueError(
                f"dof {actual} does not match the {role.value} role: {want}"
            )
        if self.theoretical.feature is not self.datum_feature:
            raise ValueError(
                "datum_feature and theoretical.feature must agree"
            )

    @property
    def constraint_type(self) -> ConstraintType:
        """The 3-2-1 locating role implied by this constraint's position."""
        return _SEQUENCE_TO_ROLE[self.sequence]


@dataclass(frozen=True)
class DatumReferenceFrame:
    """An immutable, ordered 3-2-1 datum reference frame.

    ``constraints`` is an ordered sequence whose sequences must be contiguous
    (1..n) and follow the 3-2-1 prefix order. The frame never infers missing
    constraints automatically: a partially-specified frame only reports the
    remaining free DOF.
    """

    name: str
    constraints: Tuple[DatumConstraint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints", tuple(self.constraints))
        if not self.constraints:
            raise ValueError(
                "a datum reference frame requires at least one constraint"
            )
        seen_features: set[str] = set()
        seen_sequences: set[int] = set()
        cumulative = DegreesOfFreedom()
        for index, constraint in enumerate(self.constraints, start=1):
            if constraint.sequence != index:
                raise ValueError(
                    f"constraint at position {index} has sequence "
                    f"{constraint.sequence}; sequences must be contiguous"
                )
            if constraint.sequence in seen_sequences:
                raise ValueError(
                    f"duplicate sequence {constraint.sequence}"
                )
            seen_sequences.add(constraint.sequence)
            if constraint.datum_feature.entity_id in seen_features:
                raise ValueError(
                    "duplicate datum feature "
                    f"{constraint.datum_feature.entity_id}"
                )
            seen_features.add(constraint.datum_feature.entity_id)
            overlap = constraint.dof.constrained & cumulative.constrained
            if overlap:
                bad = sorted(a.value for a in overlap)
                raise ValueError(
                    f"conflicting constraints on DOF {bad} (over-constrained)"
                )
            cumulative = cumulative.constrain(constraint.dof.constrained)

    @property
    def reference_frame(self) -> Frame:
        """Deterministic frame: the primary datum's theoretical frame."""
        for constraint in self.constraints:
            if constraint.constraint_type is ConstraintType.PRIMARY:
                return constraint.theoretical.frame
        raise ValueError("reference frame has no primary datum")

    @property
    def constrained_dof(self) -> DegreesOfFreedom:
        cumulative = DegreesOfFreedom()
        for constraint in self.constraints:
            cumulative = cumulative.constrain(constraint.dof.constrained)
        return cumulative

    @property
    def total_constrained(self) -> int:
        return len(self.constrained_dof.constrained)

    @property
    def remaining_free(self) -> int:
        return self.constrained_dof.remaining

    @property
    def free_dof(self) -> FrozenSet[Axis]:
        return self.constrained_dof.free_axes

    @property
    def is_fully_located(self) -> bool:
        return self.constrained_dof.is_fully_constrained


@dataclass(frozen=True)
class ConstrainedResult:
    """Immutable deterministic result of a datum reference frame calculation."""

    frame: DatumReferenceFrame
    constrained_dof: DegreesOfFreedom

    @property
    def constrained(self) -> FrozenSet[Axis]:
        return self.constrained_dof.constrained

    @property
    def free(self) -> FrozenSet[Axis]:
        return self.constrained_dof.free_axes

    @property
    def remaining(self) -> int:
        return self.constrained_dof.remaining

    @property
    def is_fully_located(self) -> bool:
        return self.constrained_dof.is_fully_constrained
