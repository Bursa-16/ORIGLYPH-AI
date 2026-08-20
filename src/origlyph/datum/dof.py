"""Degrees-of-freedom model for Origlyph datum/reference locating.

Deterministic and dependency-free. Models the six rigid-body degrees of
freedom of a part and the documented 3-2-1 locating reduction applied by a
datum reference frame. The calculation here is authoritative engineering
logic; the choice of *which* features to use is advisory and belongs to the
recommendation boundary (see :mod:`origlyph.datum.selection`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Iterable


class Axis(str, Enum):
    """The six rigid-body degrees of freedom of a part in space."""

    TX = "tx"
    TY = "ty"
    TZ = "tz"
    RX = "rx"
    RY = "ry"
    RZ = "rz"


class ConstraintType(str, Enum):
    """Role of a locating element within a 3-2-1 datum reference frame."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


_ALL_AXES: FrozenSet[Axis] = frozenset(Axis)


def constrained_axes(constraint_type: ConstraintType) -> FrozenSet[Axis]:
    """Return the deterministic DOF set removed by one 3-2-1 locating element.

    Axes are named relative to a right-handed frame fixed to the part:

    * primary (Z normal)    -> {Tz, Rx, Ry}  (3 constraints)
    * secondary (Y in-plane) -> {Ty, Rz}      (2 constraints)
    * tertiary (X axis)     -> {Tx}          (1 constraint)

    This is the classic 3-2-1 locating principle. It is fail-closed and
    independent of any particular CAD geometry or standard corpus.
    """
    if constraint_type is ConstraintType.PRIMARY:
        return frozenset({Axis.TZ, Axis.RX, Axis.RY})
    if constraint_type is ConstraintType.SECONDARY:
        return frozenset({Axis.TY, Axis.RZ})
    return frozenset({Axis.TX})


@dataclass(frozen=True)
class DegreesOfFreedom:
    """Rigidity state of a part: the DOFs already constrained by locating."""

    constrained: FrozenSet[Axis] = field(default_factory=frozenset)

    @property
    def free_axes(self) -> FrozenSet[Axis]:
        """Degrees of freedom the part can still move in."""
        return _ALL_AXES - self.constrained

    @property
    def is_fully_constrained(self) -> bool:
        """True once all six rigid-body DOFs are constrained."""
        return self.constrained == _ALL_AXES

    @property
    def remaining(self) -> int:
        """Number of DOFs still free (0 == fully located)."""
        return len(_ALL_AXES) - len(self.constrained)

    def constrain(self, axes: Iterable[Axis]) -> DegreesOfFreedom:
        """Return a new state with ``axes`` additionally constrained."""
        return DegreesOfFreedom(frozenset(self.constrained | set(axes)))


@dataclass(frozen=True)
class ConstraintEffect:
    """The result of applying one locating constraint to a DOF state."""

    constraint_type: ConstraintType
    newly_constrained: FrozenSet[Axis]
    remaining_state: DegreesOfFreedom

    @property
    def fully_located(self) -> bool:
        return self.remaining_state.is_fully_constrained

    @property
    def remaining(self) -> int:
        return self.remaining_state.remaining
