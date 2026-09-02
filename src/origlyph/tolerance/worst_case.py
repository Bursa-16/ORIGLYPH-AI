"""1D Worst-Case Tolerance Engine calculation core.

Stage 15B — deterministic, pure function, no side effects.

Implements the locked Stage 15A mathematical model:
  Y = c + Σ(a_i * X_i)

With signed coefficient propagation:
  If a_i >= 0:
    lower_contribution = a_i * lower_i
    upper_contribution = a_i * upper_i
  If a_i < 0:
    lower_contribution = a_i * upper_i
    upper_contribution = a_i * lower_i

Eligibility gates:
  - Calculation blocking: prevents numerical computation
  - Release blocking: prevents engineering release (but allows calculation)
  - Warning only: non-blocking advisory messages

Fail-closed: no authoritative PASS when blocking conditions exist.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import (
    Contributor,
    FunctionalRequirement,
    WorstCaseResult,
    WorstCaseStatus,
)

__all__ = [
    "calculate_worst_case",
    "ENGINE_VERSION",
]

ENGINE_VERSION = "15B.0.1"


def calculate_worst_case(
    requirement: FunctionalRequirement,
    contributors: Sequence[Contributor],
    constant: float = 0.0,
) -> WorstCaseResult:
    """Calculate 1D worst-case tolerance analysis result.

    Pure deterministic calculation. No UI, filesystem, network,
    persistence, AI, or global mutable state.

    Parameters
    ----------
    requirement : FunctionalRequirement
        The engineering requirement specification.
    contributors : Sequence[Contributor]
        The dimensional contributors in the tolerance stack.
    constant : float, optional
        Constant offset term (default 0.0).

    Returns
    -------
    WorstCaseResult
        Complete analysis result with margins, status, and traceability.

    Raises
    ------
    ValueError
        If requirement is None.
    TypeError
        If inputs are not of expected types.
    """
    if requirement is None:
        raise ValueError("requirement must not be None")
    if not isinstance(requirement, FunctionalRequirement):
        raise TypeError("requirement must be a FunctionalRequirement")
    if contributors is None:
        raise ValueError("contributors must not be None")

    # Check calculation blocking conditions
    calc_blocked, calc_reasons = _check_calculation_blocking(
        requirement, contributors, constant
    )
    if calc_blocked:
        return WorstCaseResult(
            nominal_result=0.0,
            minimum_result=0.0,
            maximum_result=0.0,
            lower_margin=0.0,
            upper_margin=0.0,
            status=WorstCaseStatus.INDETERMINATE,
            calculatable=False,
            releasable=False,
            blocking_reasons=calc_reasons,
            engine_version=ENGINE_VERSION,
        )

    # Perform deterministic calculation
    y_nominal, y_min, y_max = _compute_worst_case(requirement, contributors, constant)

    # Compute margins
    lower_margin = y_min - requirement.lower_limit
    upper_margin = requirement.upper_limit - y_max

    # Check release blocking conditions
    release_blocked, release_reasons = _check_release_blocking(
        requirement, contributors, y_min, y_max
    )

    # Collect warnings
    warnings = _collect_warnings(requirement, contributors, lower_margin, upper_margin)

    # Determine status
    calculatable = True
    releasable = not release_blocked

    if not releasable:
        status = WorstCaseStatus.INDETERMINATE
    elif lower_margin >= 0 and upper_margin >= 0:
        status = WorstCaseStatus.PASS
    else:
        status = WorstCaseStatus.FAIL

    return WorstCaseResult(
        nominal_result=y_nominal,
        minimum_result=y_min,
        maximum_result=y_max,
        lower_margin=lower_margin,
        upper_margin=upper_margin,
        status=status,
        calculatable=calculatable,
        releasable=releasable,
        warnings=warnings,
        blocking_reasons=release_reasons,
        engine_version=ENGINE_VERSION,
    )


def _check_calculation_blocking(
    requirement: FunctionalRequirement,
    contributors: Sequence[Contributor],
    constant: float,
) -> tuple[bool, tuple[str, ...]]:
    """Check conditions that prevent numerical calculation.

    Returns (is_blocked, blocking_reasons).
    """
    reasons: list[str] = []

    if math.isnan(constant) or math.isinf(constant):
        reasons.append("constant term is not finite")

    if not contributors:
        reasons.append("no contributors provided")
    else:
        enabled_contributors = [c for c in contributors if c.enabled]
        if not enabled_contributors:
            reasons.append("no enabled contributors")

        for i, c in enumerate(contributors):
            if c.enabled and c.unit.strip() != requirement.unit.strip():
                reasons.append(
                    f"unit mismatch: contributor[{i}] unit '{c.unit}' "
                    f"does not match requirement unit '{requirement.unit}'"
                )

    is_blocked = len(reasons) > 0
    return is_blocked, tuple(reasons)


def _check_release_blocking(
    requirement: FunctionalRequirement,
    contributors: Sequence[Contributor],
    y_min: float,
    y_max: float,
) -> tuple[bool, tuple[str, ...]]:
    """Check conditions that prevent engineering release.

    Returns (is_blocked, blocking_reasons).
    """
    reasons: list[str] = []

    for i, c in enumerate(contributors):
        if c.enabled and c.source_identity is None:
            reasons.append(
                f"contributor[{i}] missing source_identity: "
                f"calculatable but not releasable"
            )

    is_blocked = len(reasons) > 0
    return is_blocked, tuple(reasons)


def _collect_warnings(
    requirement: FunctionalRequirement,
    contributors: Sequence[Contributor],
    lower_margin: float,
    upper_margin: float,
) -> tuple[str, ...]:
    """Collect non-blocking warning messages."""
    warnings: list[str] = []

    for i, c in enumerate(contributors):
        if c.enabled and c.coefficient == 0.0:
            warnings.append(f"contributor[{i}] has zero coefficient (no contribution)")

    for i, c in enumerate(contributors):
        if c.enabled and c.lower_deviation == 0.0 and c.upper_deviation == 0.0:
            warnings.append(f"contributor[{i}] has zero tolerance (exact dimension)")

    if abs(lower_margin) < 1e-12:
        warnings.append("exact lower boundary contact (margin ~ 0)")
    if abs(upper_margin) < 1e-12:
        warnings.append("exact upper boundary contact (margin ~ 0)")

    return tuple(warnings)


def _compute_worst_case(
    requirement: FunctionalRequirement,
    contributors: Sequence[Contributor],
    constant: float,
) -> tuple[float, float, float]:
    """Core worst-case computation using signed propagation rule.

    Y_nominal = c + Σ(a_i * nominal_i)
    Y_min = c + Σ(lower_contribution_i)
    Y_max = c + Σ(upper_contribution_i)

    Uses math.fsum for deterministic precision.
    """
    nominal_contributions: list[float] = []
    lower_contributions: list[float] = []
    upper_contributions: list[float] = []

    for c in contributors:
        if not c.enabled:
            continue

        a_i = c.coefficient
        nominal_i = c.nominal
        lower_i = c.lower
        upper_i = c.upper

        nominal_contributions.append(a_i * nominal_i)

        if a_i >= 0:
            lower_contributions.append(a_i * lower_i)
            upper_contributions.append(a_i * upper_i)
        else:
            lower_contributions.append(a_i * upper_i)
            upper_contributions.append(a_i * lower_i)

    y_nominal = constant + math.fsum(nominal_contributions)
    y_min = constant + math.fsum(lower_contributions)
    y_max = constant + math.fsum(upper_contributions)

    return y_nominal, y_min, y_max

