"""Deterministic 1D statistical (RSS) tolerance stack engine.

This engine computes the statistical combination of independent tolerance
contributors using root-sum-square (RSS) propagation. For independent
contributions with standard deviations sigma_i::

    combined_sigma = sqrt(sum(sigma_i^2))

For a requested sigma multiplier k::

    lower_bound = nominal - k * combined_sigma
    upper_bound = nominal + k * combined_sigma

Direction/sign affects the nominal contribution, but the standard deviation
contribution remains non-negative (variance is always additive).

The engine is deterministic: identical inputs always produce identical
outputs. No random behavior, timestamps, network calls, or AI participation
is involved.

Statistical tolerance analysis does not replace worst-case analysis.
"""

from __future__ import annotations

import math

from .exceptions import InvalidStatisticalError
from .models import (
    StackDirection,
    StatisticalResult,
    StatisticalStack,
)


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


def statistical(
    stack: StatisticalStack,
    sigma_multiplier: float = 1.0,
) -> StatisticalResult:
    """Compute the deterministic 1D statistical (RSS) result.

    Parameters
    ----------
    stack:
        The ordered statistical stack to analyse. Must contain at least
        one contribution.
    sigma_multiplier:
        Multiplier k applied to combined_sigma for bound computation.
        Must be finite and strictly positive. Common values are 1, 2, or
        3 (corresponding to approximately 68%, 95%, or 99.7% coverage
        for normal distributions, though no distribution assumption is
        made by this engine).

    Returns
    -------
    StatisticalResult
        The deterministic statistical analysis result.

    Raises
    ------
    InvalidStatisticalError
        If the stack is empty or the multiplier is invalid.
    """
    if not stack.contributions:
        raise InvalidStatisticalError(
            "cannot analyse an empty statistical stack"
        )

    k = _validate_multiplier(sigma_multiplier)

    nominal_terms: list[float] = []
    variance_terms: list[float] = []

    for contribution in stack.contributions:
        if contribution.direction is StackDirection.FORWARD:
            nominal_terms.append(contribution.nominal)
        else:
            nominal_terms.append(-contribution.nominal)
        # Variance is always additive regardless of direction.
        variance_terms.append(contribution.sigma * contribution.sigma)

    # math.fsum provides numerically stable summation.
    nominal_total = math.fsum(nominal_terms)
    variance_sum = math.fsum(variance_terms)
    combined_sigma = math.sqrt(variance_sum)

    return StatisticalResult(
        nominal=nominal_total,
        combined_sigma=combined_sigma,
        sigma_multiplier=k,
        lower_bound=nominal_total - k * combined_sigma,
        upper_bound=nominal_total + k * combined_sigma,
    )
