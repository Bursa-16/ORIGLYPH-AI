"""Deterministic 1D statistical (RSS) tolerance stack engine.

This engine computes the statistical combination of 1D tolerance
contributors using root-sum-square (RSS) propagation with optional
covariance-aware correlated-contributor support.

For **independent** contributions with standard deviations sigma_i::

    combined_sigma = sqrt(sum(sigma_i^2))

For **correlated** contributions the propagation generalises to::

    Var(Y) = sum_i(a_i^2 * sigma_i^2)
           + 2 * sum_{i<j}(a_i * a_j * rho_{ij} * sigma_i * sigma_j)

where *a_i* is the algebraic stack direction (+1 forward, −1 inverse)
and *rho_{ij}* is the Pearson correlation coefficient between contributors
*i* and *j*.

For a requested sigma multiplier k::

    lower_bound = nominal - k * combined_sigma
    upper_bound = nominal + k * combined_sigma

Direction/sign affects the nominal contribution.  Variance contributions
are always non-negative, but covariance terms can be positive or negative
depending on the signs of the directions and the value of rho.

The engine is deterministic: identical inputs always produce identical
outputs.  No random behavior, timestamps, network calls, or AI participation
is involved.

Correlations must be supplied explicitly by the caller.  Origlyph never
infers manufacturing correlations; a missing pairwise correlation defaults
to rho = 0 (independent).

Statistical tolerance analysis does not replace worst-case analysis.
"""

from __future__ import annotations

import math

from .exceptions import (
    InvalidCorrelationError,
    InvalidStatisticalError,
    InvalidVarianceError,
)
from .models import (
    Correlation,
    StackDirection,
    StatisticalResult,
    StatisticalStack,
)

_NEGLIGIBLE_VARIANCE = 1e-15


def _validate_multiplier(k: float) -> float:
    """Validate and return the sigma multiplier.

    Parameters
    ----------
    k:
        The sigma multiplier to validate. Must be finite and strictly
        positive.

    Returns
    -------
    float
        The validated multiplier.

    Raises
    ------
    InvalidStatisticalError
        If the multiplier is NaN, infinity, zero, or negative.
    """
    result = float(k)
    if math.isnan(result):
        raise InvalidStatisticalError(
            "sigma_multiplier must be a finite number, got NaN"
        )
    if math.isinf(result):
        raise InvalidStatisticalError(
            "sigma_multiplier must be a finite number, got infinity"
        )
    if result <= 0.0:
        raise InvalidStatisticalError(
            f"sigma_multiplier must be strictly positive, got {result}"
        )
    return result


def _build_correlation_map(
    stack: StatisticalStack,
    correlations: tuple[Correlation, ...] | None,
) -> dict[tuple[str, str], float]:
    """Build a validated rho lookup from the caller-supplied correlations.

    Contributor identifiers are validated against the stack.  Pair symmetry
    is enforced via the canonical ordering already applied to ``Correlation``.
    Missing pairs default to rho = 0 (independence).

    Raises
    ------
    InvalidCorrelationError
        If any correlation references an unknown contributor or if a
        duplicate/conflicting pair is supplied with differing coefficients.
    """
    if correlations is None:
        return {}
    names = {c.name for c in stack.contributions}
    if len(names) != len(stack.contributions):
        raise InvalidCorrelationError(
            "contributor names must be unique for unambiguous correlation"
            " references; duplicate contributor identifiers found"
        )
    result: dict[tuple[str, str], float] = {}

    for corr in correlations:
        if corr.first not in names:
            raise InvalidCorrelationError(
                f"correlation references unknown contributor: {corr.first!r}"
            )
        if corr.second not in names:
            raise InvalidCorrelationError(
                f"correlation references unknown contributor: {corr.second!r}"
            )
        key = corr.pair
        if key in result and result[key] != corr.coefficient:
            raise InvalidCorrelationError(
                f"conflicting correlation coefficients for pair "
                f"{corr.first!r}, {corr.second!r}: "
                f"{result[key]!r} vs {corr.coefficient!r}"
            )
        result[key] = corr.coefficient

    return result


def statistical(
    stack: StatisticalStack,
    sigma_multiplier: float = 1.0,
    correlations: tuple[Correlation, ...] | None = None,
) -> StatisticalResult:
    """Compute the deterministic 1D statistical (RSS) result.

    Parameters
    ----------
    stack:
        The ordered statistical stack to analyse. Must contain at least
        one contribution.
    sigma_multiplier:
        Multiplier ``k`` applied to ``combined_sigma`` for bound computation.
        Must be finite and strictly positive.  Common values are 1, 2, or
        3 (corresponding to approximately 68%, 95%, or 99.7% coverage
        for normal distributions, though no distribution assumption is
        made by this engine).
    correlations:
        Optional sequence of explicit pairwise ``Correlation`` objects.
        Each correlation must reference contributors present in the stack.
        Missing pairwise correlations default to ρ = 0 (independent).

    Returns
    -------
    StatisticalResult
        The deterministic statistical analysis result.

    Raises
    ------
    InvalidStatisticalError
        If the stack is empty or the multiplier is invalid.
    InvalidCorrelationError
        If any correlation references an unknown contributor or if a
        duplicate/conflicting pair is supplied.
    InvalidVarianceError
        If propagated variance becomes materially negative beyond
        floating-point round-off.
    """
    if not stack.contributions:
        raise InvalidStatisticalError(
            "cannot analyse an empty statistical stack"
        )

    k = _validate_multiplier(sigma_multiplier)

    # --- algebraic signs (stack directions) ---
    signs: list[float] = []
    for contribution in stack.contributions:
        if contribution.direction is StackDirection.FORWARD:
            signs.append(+1.0)
        else:
            signs.append(-1.0)

    # --- nominal (uses signs) ---
    nominal_terms = [
        signs[i] * contribution.nominal
        for i, contribution in enumerate(stack.contributions)
    ]
    nominal_total = math.fsum(nominal_terms)

    # --- variance + covariance (uses signs in covariance term) ---
    corr_map = _build_correlation_map(stack, correlations)

    variance_terms: list[float] = []
    for i, contribution in enumerate(stack.contributions):
        a_i = signs[i]
        s_i = contribution.sigma
        variance_terms.append(a_i * a_i * s_i * s_i)

    for i in range(len(stack.contributions)):
        for j in range(i + 1, len(stack.contributions)):
            first_name, second_name = sorted(
                (stack.contributions[i].name, stack.contributions[j].name)
            )
            rho = corr_map.get((first_name, second_name), 0.0)
            if rho == 0.0:
                continue
            a_i = signs[i]
            a_j = signs[j]
            s_i = stack.contributions[i].sigma
            s_j = stack.contributions[j].sigma
            variance_terms.append(2.0 * a_i * a_j * rho * s_i * s_j)

    variance_sum = math.fsum(variance_terms)

    # Allow only negligible floating-point round-off; reject material negatives.
    if variance_sum < -_NEGLIGIBLE_VARIANCE:
        raise InvalidVarianceError(
            f"propagated variance is materially negative ({variance_sum}); "
            "correlation inputs may be inconsistent"
        )
    variance_sum = max(variance_sum, 0.0)

    combined_sigma = math.sqrt(variance_sum)

    return StatisticalResult(
        nominal=nominal_total,
        combined_sigma=combined_sigma,
        sigma_multiplier=k,
        lower_bound=nominal_total - k * combined_sigma,
        upper_bound=nominal_total + k * combined_sigma,
    )
