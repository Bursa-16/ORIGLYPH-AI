"""Unit tests for the origlyph.datum public package API surface."""

import origlyph.datum as d

PUBLIC_NAMES = {
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
}


def test_package_has_all_attribute() -> None:
    assert hasattr(d, "__all__")
    assert isinstance(d.__all__, list)


def test_public_names_resolve() -> None:
    for name in PUBLIC_NAMES:
        assert hasattr(d, name), name
    assert set(d.__all__) == PUBLIC_NAMES


def test_private_sequence_role_not_exported() -> None:
    assert not hasattr(d, "_SEQUENCE_TO_ROLE")
    assert "_SEQUENCE_TO_ROLE" not in d.__all__


def test_public_enums_are_str_enums() -> None:
    assert d.ConstraintType.PRIMARY.value == "primary"
    assert d.ReferenceKind.SURFACE.value == "surface"
    assert d.FeatureKind.PLANE.value == "plane"
    assert d.RecommendationConfidence.HIGH.value == "high"
    assert d.ValidationState.PASS.value == "pass"
    assert d.EngineeringRationale.FLAT_SURFACE.value == "flat_surface"
