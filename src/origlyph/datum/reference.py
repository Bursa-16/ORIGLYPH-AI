"""Reference surface / reference point / locating definitions.

These types model the *reference / locating convention*: which physical
features are designated as references and how they are assigned to
primary / secondary / tertiary roles. References carry identity and a local
coordinate frame only -- they never embed CAD geometry (clean-room
boundary). They reference features by stable entity id so the CAD ingestion
layer can resolve them later.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from origlyph.geometry import Frame

from .dof import ConstraintType


class ReferenceKind(str, Enum):
    """Kind of physical reference."""

    SURFACE = "surface"
    POINT = "point"


@dataclass(frozen=True)
class ReferenceSurface:
    """A physical surface designated as a locating reference."""

    entity_id: str
    frame: Frame
    name: str | None = None
    kind: ReferenceKind = ReferenceKind.SURFACE


@dataclass(frozen=True)
class ReferencePoint:
    """A physical point designated as a locating reference."""

    entity_id: str
    frame: Frame
    name: str | None = None
    kind: ReferenceKind = ReferenceKind.POINT


Reference = Union[ReferenceSurface, ReferencePoint]


@dataclass(frozen=True)
class LocatingFeature:
    """One element of a reference convention: a reference + its role."""

    reference: Reference
    constraint_type: ConstraintType
    manual: bool = False


@dataclass(frozen=True)
class ReferenceConvention:
    """The user-approved locating plan: ordered references and their roles.

    Ordering is authoritative: a convention lists the primary reference first,
    then secondary, then tertiary. The datum reference frame assembly validates
    that an input convention obeys the 3-2-1 prefix property.
    """

    name: str
    locating: tuple[LocatingFeature, ...] = ()

    def roles(self) -> tuple[ConstraintType, ...]:
        return tuple(lf.constraint_type for lf in self.locating)
