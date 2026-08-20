"""Datum features, theoretical datums, and the simulator boundary.

This module draws a sharp line, required by the clean-room policy and the
engineered-authority model:

* a :class:`PhysicalFeature` is a real feature selected from source geometry
  (a CAD entity reference);
* a :class:`TheoreticalDatum` is the idealized datum produced by a
  :class:`DatumFeatureSimulator` -- an analysis artifact, never the geometry
  itself;
* a :class:`Datum` is a named theoretical datum with an engineering rationale.

The simulator is deterministic engineering logic. Future simulators (fit
plane/axis through measured points, etc.) plug in behind the same protocol.
No AI and no CAD SDK are required to construct these primitives.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from origlyph.geometry import Frame

Simulator = Callable[["PhysicalFeature"], "TheoreticalDatum"]


class FeatureKind(str, Enum):
    """Coarse classification of a physical feature."""

    PLANE = "plane"
    AXIS = "axis"
    POINT = "point"
    CYLINDER = "cylinder"


@dataclass(frozen=True)
class PhysicalFeature:
    """A real feature selected from source geometry.

    Carries stable identity and a local coordinate frame only; the actual
    geometry lives in the CAD ingestion layer and is not copied here.
    """

    entity_id: str
    frame: Frame
    kind: FeatureKind = FeatureKind.PLANE
    name: str | None = None


@dataclass(frozen=True)
class TheoreticalDatum:
    """The idealized datum derived from a physical feature by simulation.

    This is an analysis artifact: it references the physical feature it was
    derived from, but is not the physical geometry itself.
    """

    feature: PhysicalFeature
    frame: Frame
    kind: FeatureKind


class DatumFeatureSimulator(Protocol):
    """Deterministic simulator producing a theoretical datum from a feature."""

    def simulate(self, feature: PhysicalFeature) -> TheoreticalDatum:
        """Return the theoretical datum for ``feature``."""
        ...


def default_simulator(feature: PhysicalFeature) -> TheoreticalDatum:
    """Default deterministic simulator: the datum frame IS the feature frame.

    The theoretical datum inherits the physical feature's coordinate frame.
    Real simulators (best-fit plane/axis, etc.) implement the same
    :class:`DatumFeatureSimulator` protocol and are drop-in replacements.
    """
    return TheoreticalDatum(feature=feature, frame=feature.frame, kind=feature.kind)


@dataclass(frozen=True)
class Datum:
    """A named, rationale-bound theoretical datum."""

    name: str
    theoretical: TheoreticalDatum
    rationale: str | None = None
