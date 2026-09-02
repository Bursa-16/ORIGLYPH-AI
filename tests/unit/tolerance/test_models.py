"""Tests for Origlyph 1D Worst-Case Tolerance Engine — data models.

Stage 15B — model construction, validation, and invariant enforcement.
All tests use standalone functions (project convention: python_classes = []).
"""

from __future__ import annotations

import pytest

from origlyph.tolerance.models import (
    Contributor,
    FunctionalRequirement,
    WorstCaseResult,
    WorstCaseStatus,
)

# --------------------------------------------------------------------------- #
# FunctionalRequirement tests
# --------------------------------------------------------------------------- #


def test_requirement_valid_basic() -> None:
    req = FunctionalRequirement(lower_limit=9.5, upper_limit=10.5, unit="mm")
    assert req.lower_limit == 9.5
    assert req.upper_limit == 10.5
    assert req.unit == "mm"
    assert req.nominal_target is None


def test_requirement_valid_with_nominal() -> None:
    req = FunctionalRequirement(
        lower_limit=9.0, upper_limit=11.0, unit="mm",
        nominal_target=10.0, requirement_id="REQ-001", direction="axial",
    )
    assert req.nominal_target == 10.0
    assert req.requirement_id == "REQ-001"
    assert req.direction == "axial"


def test_requirement_valid_equal_bounds() -> None:
    req = FunctionalRequirement(lower_limit=10.0, upper_limit=10.0, unit="mm")
    assert req.lower_limit == 10.0
    assert req.upper_limit == 10.0


def test_requirement_invalid_lower_greater_than_upper() -> None:
    with pytest.raises(ValueError, match="lower_limit .* must be <= upper_limit"):
        FunctionalRequirement(lower_limit=11.0, upper_limit=9.0, unit="mm")


def test_requirement_invalid_empty_unit() -> None:
    with pytest.raises(ValueError, match="unit must be an explicit non-empty string"):
        FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="")


def test_requirement_invalid_whitespace_unit() -> None:
    with pytest.raises(ValueError, match="unit must be an explicit non-empty string"):
        FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="   ")


def test_requirement_invalid_nan_lower_limit() -> None:
    with pytest.raises(ValueError, match="lower_limit must be finite"):
        FunctionalRequirement(lower_limit=float("nan"), upper_limit=11.0, unit="mm")


def test_requirement_invalid_inf_upper_limit() -> None:
    with pytest.raises(ValueError, match="upper_limit must be finite"):
        FunctionalRequirement(lower_limit=9.0, upper_limit=float("inf"), unit="mm")


def test_requirement_invalid_nominal_below_lower() -> None:
    with pytest.raises(ValueError, match="nominal_target must be >= lower_limit"):
        FunctionalRequirement(
            lower_limit=9.0, upper_limit=11.0, unit="mm", nominal_target=8.0,
        )


def test_requirement_invalid_nominal_above_upper() -> None:
    with pytest.raises(ValueError, match="nominal_target must be <= upper_limit"):
        FunctionalRequirement(
            lower_limit=9.0, upper_limit=11.0, unit="mm", nominal_target=12.0,
        )


def test_requirement_frozen_immutable() -> None:
    req = FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="mm")
    with pytest.raises(AttributeError):
        req.lower_limit = 5.0  # type: ignore[misc]


def test_requirement_hashable() -> None:
    req = FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="mm")
    hash(req)


def test_requirement_equal_values() -> None:
    req1 = FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="mm")
    req2 = FunctionalRequirement(lower_limit=9.0, upper_limit=11.0, unit="mm")
    assert req1 == req2


# --------------------------------------------------------------------------- #
# Contributor tests
# --------------------------------------------------------------------------- #


def test_contributor_valid_symmetric() -> None:
    c = Contributor(nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2)
    assert c.nominal == 10.0
    assert c.lower_deviation == -0.2
    assert c.upper_deviation == 0.2
    assert c.coefficient == 1.0
    assert c.unit == "mm"
    assert c.enabled is True


def test_contributor_valid_asymmetric() -> None:
    c = Contributor(nominal=10.0, lower_deviation=-0.1, upper_deviation=+0.5)
    assert c.lower == 9.9
    assert c.upper == 10.5


def test_contributor_valid_negative_coefficient() -> None:
    c = Contributor(
        nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2, coefficient=-1.0,
    )
    assert c.coefficient == -1.0


def test_contributor_valid_zero_coefficient() -> None:
    c = Contributor(
        nominal=999.0, lower_deviation=-10.0, upper_deviation=+10.0, coefficient=0.0,
    )
    assert c.coefficient == 0.0


def test_contributor_valid_zero_tolerance() -> None:
    c = Contributor(nominal=10.0, lower_deviation=0.0, upper_deviation=0.0)
    assert c.lower == 10.0
    assert c.upper == 10.0


def test_contributor_invalid_lower_deviation_greater_than_upper() -> None:
    with pytest.raises(ValueError, match="derived lower .* must be <= derived upper"):
        Contributor(nominal=10.0, lower_deviation=+0.5, upper_deviation=-0.5)


def test_contributor_invalid_nan_nominal() -> None:
    with pytest.raises(ValueError, match="nominal must be finite"):
        Contributor(nominal=float("nan"), lower_deviation=-0.1, upper_deviation=+0.1)


def test_contributor_invalid_inf_coefficient() -> None:
    with pytest.raises(ValueError, match="coefficient must be finite"):
        Contributor(
            nominal=10.0, lower_deviation=-0.1, upper_deviation=+0.1,
            coefficient=float("inf"),
        )


def test_contributor_invalid_empty_unit() -> None:
    with pytest.raises(ValueError, match="unit must be an explicit non-empty string"):
        Contributor(nominal=10.0, lower_deviation=-0.1, upper_deviation=+0.1, unit="")


def test_contributor_frozen_immutable() -> None:
    c = Contributor(nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2)
    with pytest.raises(AttributeError):
        c.nominal = 5.0  # type: ignore[misc]


def test_contributor_hashable() -> None:
    c = Contributor(nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2)
    hash(c)


def test_contributor_equal_values() -> None:
    c1 = Contributor(nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2)
    c2 = Contributor(nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2)
    assert c1 == c2


def test_contributor_disabled() -> None:
    c = Contributor(
        nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2, enabled=False,
    )
    assert c.enabled is False


def test_contributor_custom_id() -> None:
    c = Contributor(
        nominal=10.0, lower_deviation=-0.2, upper_deviation=+0.2,
        contributor_id="C-001", feature_ref="hole_A",
    )
    assert c.contributor_id == "C-001"
    assert c.feature_ref == "hole_A"


# --------------------------------------------------------------------------- #
# WorstCaseResult tests
# --------------------------------------------------------------------------- #


def test_worst_case_result_valid_pass() -> None:
    result = WorstCaseResult(
        nominal_result=10.0, minimum_result=9.8, maximum_result=10.2,
        lower_margin=0.3, upper_margin=0.3,
        status=WorstCaseStatus.PASS, calculatable=True, releasable=True,
    )
    assert result.status == WorstCaseStatus.PASS
    assert result.calculatable is True
    assert result.releasable is True
    assert result.engine_version == "15B.0.1"


def test_worst_case_result_valid_fail() -> None:
    result = WorstCaseResult(
        nominal_result=10.0, minimum_result=9.0, maximum_result=10.5,
        lower_margin=-0.5, upper_margin=0.5,
        status=WorstCaseStatus.FAIL, calculatable=True, releasable=True,
    )
    assert result.status == WorstCaseStatus.FAIL


def test_worst_case_result_valid_indeterminate() -> None:
    result = WorstCaseResult(
        nominal_result=0.0, minimum_result=0.0, maximum_result=0.0,
        lower_margin=0.0, upper_margin=0.0,
        status=WorstCaseStatus.INDETERMINATE,
        calculatable=False, releasable=False,
        blocking_reasons=("no contributors",),
    )
    assert result.status == WorstCaseStatus.INDETERMINATE
    assert result.calculatable is False
    assert result.releasable is False


def test_worst_case_result_frozen_immutable() -> None:
    result = WorstCaseResult(
        nominal_result=10.0, minimum_result=9.8, maximum_result=10.2,
        lower_margin=0.3, upper_margin=0.3,
        status=WorstCaseStatus.PASS, calculatable=True, releasable=True,
    )
    with pytest.raises(AttributeError):
        result.status = WorstCaseStatus.FAIL  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# WorstCaseStatus tests
# --------------------------------------------------------------------------- #


def test_worst_case_status_pass_value() -> None:
    assert WorstCaseStatus.PASS.value == "pass"


def test_worst_case_status_fail_value() -> None:
    assert WorstCaseStatus.FAIL.value == "fail"


def test_worst_case_status_indeterminate_value() -> None:
    assert WorstCaseStatus.INDETERMINATE.value == "indeterminate"


def test_worst_case_status_enum_comparison() -> None:
    assert WorstCaseStatus.PASS == "pass"
    assert WorstCaseStatus.FAIL != WorstCaseStatus.PASS

