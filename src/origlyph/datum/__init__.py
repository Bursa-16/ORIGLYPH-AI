"""Origlyph datum/reference domain foundation.

Deterministic, dependency-free building blocks for selecting physical
features, simulating theoretical datums, defining references and locating
conventions, and assembling datum reference frames. Advisory recommendation
types allow future AI integration without compromising the deterministic
engineering-authority model (see :mod:`origlyph.datum.selection`).
"""
from __future__ import annotations

from .datum import (
    Datum,
    DatumFeatureSimulator,
    FeatureKind,
    PhysicalFeature,
    Simulator,
    TheoreticalDatum,
    default_simulator,
)
from .datum_reference_frame import (
    ConstrainedResult,
    DatumConstraint,
    DatumReferenceFrame,
)
from .dof import (
    Axis,
    ConstraintEffect,
    ConstraintType,
    DegreesOfFreedom,
    constrained_axes,
)
from .reference import (
    LocatingFeature,
    Reference,
    ReferenceConvention,
    ReferenceKind,
    ReferencePoint,
    ReferenceSurface,
)
from .selection import (
    DatumRecommendation,
    EngineeringRationale,
    ManualOverride,
    RecommendationConfidence,
    Recommender,
    ValidationState,
)

__all__ = [
    "Axis",
    "ConstrainedResult",
    "ConstraintEffect",
    "ConstraintType",
    "Datum",
    "DatumConstraint",
    "DatumFeatureSimulator",
    "DatumRecommendation",
    "DatumReferenceFrame",
    "DegreesOfFreedom",
    "EngineeringRationale",
    "FeatureKind",
    "LocatingFeature",
    "ManualOverride",
    "PhysicalFeature",
    "Reference",
    "ReferenceConvention",
    "ReferenceKind",
    "ReferencePoint",
    "ReferenceSurface",
    "RecommendationConfidence",
    "Recommender",
    "Simulator",
    "TheoreticalDatum",
    "ValidationState",
        "constrained_axes",
    "default_simulator",
]