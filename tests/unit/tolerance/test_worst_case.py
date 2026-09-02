"""Tests for Origlyph 1D Worst-Case Tolerance Engine — calculation core.

Stage 15B — golden case matrix from locked Stage 15A contract.
All cases use synthetic/anonymized data only.
All tests use standalone functions (project convention: python_classes = []).
"""

from __future__ import annotations

import pytest

from origlyph.tolerance import calculate_worst_case
from origlyph.tolerance.models import (
    Contributor,
    FunctionalRequirement,
    WorstCaseStatus,
)


def _req(lower: float, upper: float, unit: str = "mm") -> FunctionalRequirement:
    return FunctionalRequirement(lower_limit=lower, upper_limit=upper, unit=unit)


def _contrib(
    nominal: float, lower_dev: float, upper_dev: float,
    coeff: float = 1.0, unit: str = "mm", source=None, enabled: bool = True,
) -> Contributor:
    return Contributor(
        nominal=nominal, lower_deviation=lower_dev, upper_deviation=upper_dev,
        coefficient=coeff, unit=unit, source_identity=source, enabled=enabled,
    )


# --------------------------------------------------------------------------- #
# Golden cases 1-13
# --------------------------------------------------------------------------- #


def test_case_01_single_positive_contributor() -> None:
    req = _req(9.5, 10.5)
    result = calculate_worst_case(req, [_contrib(10.0, -0.2, +0.2)])
    assert result.calculatable is True
    assert result.releasable is False  # no source
    assert result.nominal_result == 10.0
    assert result.minimum_result == 9.8
    assert result.maximum_result == 10.2
    assert result.lower_margin == pytest.approx(0.3)
    assert result.upper_margin == pytest.approx(0.3)


def test_case_02_multiple_positive_contributors() -> None:
    req = _req(19.0, 21.0)
    contributors = [
        _contrib(10.0, -0.3, +0.3),
        _contrib(5.0, -0.2, +0.2),
        _contrib(4.5, -0.1, +0.1),
    ]
    result = calculate_worst_case(req, contributors)
    assert result.calculatable is True
    assert result.nominal_result == pytest.approx(19.5)
    assert result.minimum_result == pytest.approx(18.9)
    assert result.maximum_result == pytest.approx(20.1)


def test_case_03_single_negative_coefficient() -> None:
    req = _req(4.0, 6.0)
    result = calculate_worst_case(req, [_contrib(10.0, -0.5, +0.5, coeff=-1.0)])
    assert result.calculatable is True
    assert result.nominal_result == pytest.approx(-10.0)
    assert result.minimum_result == pytest.approx(-10.5)
    assert result.maximum_result == pytest.approx(-9.5)


def test_case_04_mixed_coefficients() -> None:
    req = _req(-1.0, 1.0)
    contributors = [
        _contrib(5.0, -0.2, +0.2, coeff=+1.0),
        _contrib(3.0, -0.1, +0.1, coeff=-1.0),
    ]
    result = calculate_worst_case(req, contributors)
    assert result.calculatable is True
    assert result.nominal_result == pytest.approx(2.0)
    assert result.minimum_result == pytest.approx(1.7)
    assert result.maximum_result == pytest.approx(2.3)


def test_case_05_symmetric_tolerance() -> None:
    req = _req(9.0, 11.0)
    result = calculate_worst_case(req, [_contrib(10.0, -0.5, +0.5)])
    assert result.calculatable is True
    assert result.nominal_result == 10.0
    assert result.minimum_result == 9.5
    assert result.maximum_result == 10.5


def test_case_06_asymmetric_tolerance() -> None:
    req = _req(9.0, 11.0)
    result = calculate_worst_case(req, [_contrib(10.0, -0.2, +0.8)])
    assert result.calculatable is True
    assert result.nominal_result == 10.0
    assert result.minimum_result == 9.8
    assert result.maximum_result == 10.8
    assert result.lower_margin == pytest.approx(0.8)
    assert result.upper_margin == pytest.approx(0.2)


def test_case_07_nonzero_nominal_coefficient_scaling() -> None:
    req = _req(0.0, 2.0)
    result = calculate_worst_case(req, [_contrib(50.0, -0.1, +0.1, coeff=0.02)])
    assert result.calculatable is True
    assert result.nominal_result == pytest.approx(1.0)
    assert result.minimum_result == pytest.approx(0.998)
    assert result.maximum_result == pytest.approx(1.002)


def test_case_08_zero_tolerance_contributor() -> None:
    req = _req(9.5, 10.5)
    result = calculate_worst_case(req, [_contrib(10.0, 0.0, 0.0)])
    assert result.calculatable is True
    assert result.nominal_result == 10.0
    assert result.minimum_result == 10.0
    assert result.maximum_result == 10.0


def test_case_09_zero_coefficient_contributor() -> None:
    req = _req(0.0, 100.0)
    result = calculate_worst_case(req, [_contrib(999.0, -10.0, +10.0, coeff=0.0)])
    assert result.calculatable is True
    assert result.nominal_result == 0.0
    assert result.minimum_result == 0.0
    assert result.maximum_result == 0.0


def test_case_10_pass_requirement() -> None:
    req = _req(0.0, 100.0)
    result = calculate_worst_case(req, [_contrib(50.0, -1.0, +1.0)])
    assert result.calculatable is True
    assert result.lower_margin == pytest.approx(49.0)
    assert result.upper_margin == pytest.approx(49.0)


def test_case_11_lower_limit_fail() -> None:
    req = _req(10.0, 20.0)
    result = calculate_worst_case(req, [_contrib(10.0, -1.0, +0.5)])
    assert result.calculatable is True
    assert result.minimum_result == 9.0
    assert result.lower_margin == pytest.approx(-1.0)


def test_case_12_upper_limit_fail() -> None:
    req = _req(10.0, 20.0)
    result = calculate_worst_case(req, [_contrib(19.0, -0.5, +2.0)])
    assert result.calculatable is True
    assert result.maximum_result == 21.0
    assert result.upper_margin == pytest.approx(-1.0)


def test_case_13_exact_lower_boundary() -> None:
    req = _req(10.0, 20.0)
    result = calculate_worst_case(req, [_contrib(10.5, -0.5, +0.5)])
    assert result.calculatable is True
    assert result.minimum_result == 10.0
    assert result.lower_margin == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Golden cases 14-25
# --------------------------------------------------------------------------- #


def test_case_14_exact_upper_boundary() -> None:
    req = _req(10.0, 20.0)
    result = calculate_worst_case(req, [_contrib(19.5, -0.5, +0.5)])
    assert result.calculatable is True
    assert result.maximum_result == 20.0
    assert result.upper_margin == pytest.approx(0.0)


def test_case_15_mixed_units_fail_closed() -> None:
    req = _req(0.0, 10.0, unit="mm")
    result = calculate_worst_case(req, [_contrib(5.0, -0.1, +0.1, unit="inch")])
    assert result.calculatable is False
    assert result.status == WorstCaseStatus.INDETERMINATE
    assert len(result.blocking_reasons) > 0


def test_case_16_missing_source_calculatable_not_releasable() -> None:
    req = _req(9.5, 10.5)
    result = calculate_worst_case(req, [_contrib(10.0, -0.1, +0.1, source=None)])
    assert result.calculatable is True
    assert result.releasable is False
    assert result.status == WorstCaseStatus.INDETERMINATE
    assert any("missing source_identity" in r for r in result.blocking_reasons)


def test_case_17_invalid_bounds_ordering() -> None:
    with pytest.raises(ValueError, match="derived lower .* must be <= derived upper"):
        Contributor(nominal=10.0, lower_deviation=+0.5, upper_deviation=-0.5)


def test_case_18_nan_nominal() -> None:
    with pytest.raises(ValueError, match="nominal must be finite"):
        Contributor(nominal=float("nan"), lower_deviation=-0.1, upper_deviation=+0.1)


def test_case_19_infinity_coefficient() -> None:
    with pytest.raises(ValueError, match="coefficient must be finite"):
        Contributor(
            nominal=10.0, lower_deviation=-0.1, upper_deviation=+0.1,
            coefficient=float("inf"),
        )


def test_case_20_empty_contributors() -> None:
    req = _req(0.0, 10.0)
    result = calculate_worst_case(req, [])
    assert result.calculatable is False
    assert result.status == WorstCaseStatus.INDETERMINATE
    assert any("no contributors" in r for r in result.blocking_reasons)


def test_case_21_permutation_invariance() -> None:
    req = _req(0.0, 100.0)
    c1 = _contrib(10.0, -0.2, +0.2)
    c2 = _contrib(5.0, -0.1, +0.1)
    c3 = _contrib(3.0, -0.3, +0.3)
    r1 = calculate_worst_case(req, [c1, c2, c3])
    r2 = calculate_worst_case(req, [c3, c1, c2])
    r3 = calculate_worst_case(req, [c2, c3, c1])
    assert r1.nominal_result == r2.nominal_result == r3.nominal_result
    assert r1.minimum_result == r2.minimum_result == r3.minimum_result
    assert r1.maximum_result == r2.maximum_result == r3.maximum_result


def test_case_22_deterministic_repeated() -> None:
    req = _req(0.0, 100.0)
    contributors = [_contrib(50.0, -1.0, +1.0), _contrib(25.0, -0.5, +0.5)]
    results = [calculate_worst_case(req, contributors) for _ in range(50)]
    first = results[0]
    for r in results[1:]:
        assert r.nominal_result == first.nominal_result
        assert r.minimum_result == first.minimum_result
        assert r.maximum_result == first.maximum_result


def test_case_23_hand_calculated_golden() -> None:
    req = _req(0.0, 0.5)
    contributors = [
        _contrib(25.4, -0.1, +0.1, coeff=0.02),
        _contrib(-12.7, -0.05, +0.05, coeff=-0.04),
        _contrib(6.35, -0.02, +0.02, coeff=0.08),
    ]
    result = calculate_worst_case(req, contributors)
    assert result.calculatable is True
    assert result.nominal_result == pytest.approx(1.524)
    assert result.minimum_result == pytest.approx(1.5184)
    assert result.maximum_result == pytest.approx(1.5296)


def test_case_24_calculatable_not_releasable() -> None:
    req = _req(9.5, 10.5)
    result = calculate_worst_case(req, [_contrib(10.0, -0.1, +0.1, source=None)])
    assert result.calculatable is True
    assert result.releasable is False
    assert result.status == WorstCaseStatus.INDETERMINATE


def test_case_25_linear_eligibility() -> None:
    req = _req(0.0, 10.0)
    result = calculate_worst_case(req, [_contrib(5.0, -0.1, +0.1)])
    assert result.calculatable is True

