"""Deterministic sensitivity and contributor-impact analysis (Stage 15F).

This module explains **which contributors dominate** a 1D tolerance stack.
It is explanatory only: it delegates every authoritative number to the
existing engines (Stage 15C-R worst case, Stage 15D/15E statistical RSS)
and decomposes those totals into per-contributor and per-pair terms with
deterministic fractions, percentages, and rankings.

Sensitivity analysis explains contribution; it does not change
authoritative tolerance results.

Negative covariance contribution represents statistical cancellation and
must not be silently converted to a positive impact.

AI does not override deterministic tolerance calculations.

Decompositions
--------------

Worst case, for each contribution ``i``::

    span_i     = upper_deviation_i - lower_deviation_i   (always >= 0)
    fraction_i = span_i / total_span      (total from the engine)

Independent and correlated statistics::

    individual_variance_i = a_i^2 * sigma_i^2
    covariance_ij         = 2 * a_i * a_j * rho_ij * sigma_i * sigma_j
    total_variance        = sum_i(individual_variance_i)
                          + sum_{i<j}(covariance_ij)

``a_i`` is the algebraic stack direction (+1 FORWARD, -1 INVERSE). The
covariance terms keep their sign: a negative term is cancellation, never
an absolute impact.

Zero policies
-------------

* Worst case: if the authoritative ``total_span`` is zero, every fraction
  and percentage is exactly ``0.0`` (documented policy; no division is
  performed, no NaN or infinity is produced).
* Statistical: a total variance at or below the Stage 15E package-wide
  threshold (``_NEGLIGIBLE_VARIANCE = 1e-15``) is treated as zero; every
  fraction and percentage is ``0.0``. The engine's own threshold is
  reused; no new or conflicting threshold is introduced.

Ranking policy
--------------

* Worst-case impacts: descending ``span``.
* Statistical impacts: descending ``individual_variance``.
* Covariance pairs: descending ``abs(covariance_term)`` (magnitude is
  used for ranking only; the authoritative total always uses the signed
  term).
* Ties preserve the original input order (worst-case and statistical
  contributions) or the original correlation declaration order (pairs);
  Python's stable sort makes this deterministic.

The functions in this module never mutate their inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import (
    Correlation,
    StackDirection,
    StatisticalStack,
    ToleranceStack,
)
from .statistical import (
    _NEGLIGIBLE_VARIANCE,
    statistical,
)
from .worst_case import worst_case

__all__ = [
    "CovariancePairImpact",
    "StatisticalContributionImpact",
    "StatisticalSensitivityResult",
    "WorstCaseContributionImpact",
    "WorstCaseSensitivityResult",
    "statistical_sensitivity",
    "worst_case_sensitivity",
]


def _sign(direction: StackDirection) -> float:
    """Return the algebraic stack coefficient (+1 FORWARD, -1 INVERSE)."""
    if direction is StackDirection.FORWARD:
        return 1.0
    return -1.0


@dataclass(frozen=True)
class WorstCaseContributionImpact:
    """Explanatory impact of one contribution on the worst-case stack span.

    Every numeric field is derived read-only from the contribution and the
    authoritative worst-case result. ``span`` is the non-negative span of
    the contribution's admissible interval in stack space; direction and
    sign never make it negative (``upper_deviation >= lower_deviation`` is
    enforced at construction).

    Attributes
    ----------
    name:
        Contributor identifier (traceability).
    direction:
        How the contribution enters the stack (FORWARD adds, INVERSE
        subtracts).
    signed_nominal:
        Algebraic nominal contribution to the stack: ``+nominal`` for
        FORWARD, ``-nominal`` for INVERSE.
    lower_deviation:
        Lower deviation from the contribution's own nominal.
    upper_deviation:
        Upper deviation from the contribution's own nominal.
    span:
        Non-negative contributor tolerance span
        (``upper_deviation - lower_deviation``). This is the absolute span
        contribution in stack space.
    fraction:
        ``span / total_span``; exactly ``0.0`` when the authoritative
        ``total_span`` is zero (documented zero policy; no NaN, no infinity).
    percentage:
        ``fraction * 100.0``.
    """

    name: str
    direction: StackDirection
    signed_nominal: float
    lower_deviation: float
    upper_deviation: float
    span: float
    fraction: float
    percentage: float


@dataclass(frozen=True)
class WorstCaseSensitivityResult:
    """Explanatory decomposition of an authoritative worst-case result.

    Attributes
    ----------
    total_span:
        The authoritative total worst-case span from :func:`worst_case`.
    impacts:
        Per-contribution impacts ranked by descending ``span``; ties
        preserve the original contributor order (stable sort).
    """

    total_span: float
    impacts: tuple[WorstCaseContributionImpact, ...]


@dataclass(frozen=True)
class StatisticalContributionImpact:
    """Explanatory variance impact of one statistical contributor.

    Attributes
    ----------
    name:
        Contributor identifier (traceability).
    direction:
        How the contribution enters the stack (FORWARD adds, INVERSE
        subtracts).
    sigma:
        Contributor standard deviation exactly as supplied (never modified).
    variance:
        Individual variance term ``a_i^2 * sigma_i^2`` (always >= 0, where
        ``a_i`` is the algebraic direction).
    fraction:
        ``variance / total_variance``; exactly ``0.0`` when the total
        variance is at or below the package-wide negligible threshold.
    percentage:
        ``fraction * 100.0``.
    """

    name: str
    direction: StackDirection
    sigma: float
    variance: float
    fraction: float
    percentage: float


@dataclass(frozen=True)
class CovariancePairImpact:
    """Explanatory signed covariance impact of one declared pair.

    A covariance pair is never assigned to a single contributor: it is a
    joint property of two contributors. The term keeps its sign — a negative
    ``covariance_term`` is statistical cancellation and is never converted
    to a positive impact.

    Attributes
    ----------
    first:
        First contributor of the canonical pair (``first <= second``).
    second:
        Second contributor of the canonical pair.
    rho:
        Declared Pearson correlation coefficient for the pair.
    covariance_term:
        Signed term ``2 * a_i * a_j * rho * sigma_i * sigma_j``.
    fraction:
        Signed ``covariance_term / total_variance``; exactly ``0.0`` when
        the total variance is treated as zero.
    percentage:
        Signed ``fraction * 100.0``.
    abs_covariance:
        ``abs(covariance_term)``; provided for ranking only and never used
        in the authoritative variance equation.
    """

    first: str
    second: str
    rho: float
    covariance_term: float
    fraction: float
    percentage: float
    abs_covariance: float


@dataclass(frozen=True)
class StatisticalSensitivityResult:
    """Explanatory decomposition of an authoritative statistical result.

    Attributes
    ----------
    nominal:
        The authoritative stack nominal from :func:`statistical`.
    total_variance:
        The authoritative propagated variance (individual terms plus signed
        covariance terms), clamped exactly as the engine clamps it.
    combined_sigma:
        The authoritative combined sigma from :func:`statistical`.
    sigma_multiplier:
        The authoritative multiplier from :func:`statistical`.
    contributions:
        Per-contributor variance impacts ranked by descending
        ``variance``; ties preserve the original contributor order
        (stable sort).
    covariance_pairs:
        Signed covariance-pair impacts ranked by descending
        ``abs_covariance``; ties preserve the original correlation
        declaration/discovery order (stable sort).
    """

    nominal: float
    total_variance: float
    combined_sigma: float
    sigma_multiplier: float
    contributions: tuple[StatisticalContributionImpact, ...]
    covariance_pairs: tuple[CovariancePairImpact, ...]


def worst_case_sensitivity(stack: ToleranceStack) -> WorstCaseSensitivityResult:
    """Explain per-contributor impact on the authoritative worst-case span.

    The authoritative totals come from :func:`worst_case` itself, so every
    validation rule and numeric result of the engine applies unchanged.

    Each contribution's span is ``upper_deviation - lower_deviation``, which
    is non-negative by model validation and is independent of the stack
    direction (an INVERSE contribution's interval is reversed, but its width
    is unchanged). Because the engine's total span is the sum of the interval
    widths, ``span_i / total_span`` is an exact decomposition.

    Parameters
    ----------
    stack:
        The ordered tolerance stack to explain. Must contain at least one
        contribution (validated by the engine).

    Returns
    -------
    WorstCaseSensitivityResult
        Impacts ranked by descending span; ties preserve input order.

    Raises
    ------
    InvalidStackError
        If the stack is empty (raised by the authoritative engine).
    """
    authoritative = worst_case(stack)
    total_span = authoritative.total_span

    impacts: list[WorstCaseContributionImpact] = []
    for contribution in stack.contributions:
        span = contribution.upper_deviation - contribution.lower_deviation
        if total_span > 0.0:
            fraction = span / total_span
        else:
            # Documented zero-span policy: no division, no NaN, no infinity.
            fraction = 0.0
        impacts.append(
            WorstCaseContributionImpact(
                name=contribution.name,
                direction=contribution.direction,
                signed_nominal=_sign(contribution.direction) * contribution.nominal,
                lower_deviation=contribution.lower_deviation,
                upper_deviation=contribution.upper_deviation,
                span=span,
                fraction=fraction,
                percentage=fraction * 100.0,
            )
        )

    # Stable sort: descending span, ties keep original contributor order.
    impacts.sort(key=lambda impact: impact.span, reverse=True)

    return WorstCaseSensitivityResult(
        total_span=total_span,
        impacts=tuple(impacts),
    )


def statistical_sensitivity(
    stack: StatisticalStack,
    sigma_multiplier: float = 1.0,
    correlations: tuple[Correlation, ...] | None = None,
) -> StatisticalSensitivityResult:
    """Explain variance and covariance contributions of a statistical stack.

    The authoritative totals come from :func:`statistical` itself, so every
    validation rule (finite sigma, multiplier, correlation identity,
    duplicate/conflicting pairs, materially negative variance) and every
    numeric result of the engine applies unchanged.

    Decomposition exposed:

    * individual variance terms ``a_i^2 * sigma_i^2`` (always non-negative),
    * signed pairwise covariance terms
      ``2 * a_i * a_j * rho_ij * sigma_i * sigma_j`` (never assigned to a
      single contributor, never forced positive — a negative term is
      statistical cancellation).

    Parameters
    ----------
    stack:
        The ordered statistical stack to explain. Must contain at least one
        contribution (validated by the engine).
    sigma_multiplier:
        Multiplier ``k``; forwarded unchanged to the authoritative engine.
    correlations:
        Optional explicit pairwise correlations; forwarded unchanged to the
        authoritative engine.

    Returns
    -------
    StatisticalSensitivityResult
        Contributions ranked by descending individual variance; covariance
        pairs ranked by descending absolute term. Ties preserve original
        input/declaration order (stable sort).

    Raises
    ------
    InvalidStatisticalError
        If the stack is empty or the multiplier is invalid (authoritative
        engine validation).
    InvalidCorrelationError
        For unknown contributor references, ambiguous duplicate names, or
        conflicting pair definitions (authoritative engine validation).
    InvalidVarianceError
        If propagated variance becomes materially negative (authoritative
        engine validation).
    """
    # Authoritative numbers and validation first — identical behaviour.
    authoritative = statistical(
        stack,
        sigma_multiplier=sigma_multiplier,
        correlations=correlations,
    )

    contributions = stack.contributions
    signs = [_sign(contribution.direction) for contribution in contributions]

    individual_variances = [
        sign * sign * contribution.sigma * contribution.sigma
        for sign, contribution in zip(signs, contributions, strict=True)
    ]

    # Signed covariance terms in correlation declaration order. Each
    # canonical pair appears exactly once: identical duplicate declarations
    # are idempotent and conflicting duplicates are rejected by the
    # authoritative engine before this point. Ties in the ranking below
    # therefore preserve declaration order, as documented.
    discovered: list[tuple[str, str, float, float]] = []  # (first, second, rho, term)
    if correlations:
        sigma_by_name = {c.name: c.sigma for c in contributions}
        sign_by_name = {
            contribution.name: sign
            for contribution, sign in zip(contributions, signs, strict=True)
        }
        seen_pairs: set[tuple[str, str]] = set()
        for correlation in correlations:
            pair = (correlation.first, correlation.second)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            rho = correlation.coefficient
            if rho == 0.0:
                continue
            term = (
                2.0
                * sign_by_name[pair[0]]
                * sign_by_name[pair[1]]
                * rho
                * sigma_by_name[pair[0]]
                * sigma_by_name[pair[1]]
            )
            discovered.append((pair[0], pair[1], rho, term))

    total_variance = math.fsum(individual_variances) + math.fsum(
        term for _, _, _, term in discovered
    )
    # Mirror the authoritative clamping: the engine has already rejected
    # materially negative variance, so only round-off can remain.
    total_variance = max(total_variance, 0.0)

    # Documented zero-variance policy (reuses the Stage 15E package-wide
    # threshold; no new or conflicting threshold is introduced).
    zero_variance = total_variance <= _NEGLIGIBLE_VARIANCE

    contribution_impacts: list[StatisticalContributionImpact] = []
    for contribution, variance in zip(
        contributions, individual_variances, strict=True
    ):
        fraction = 0.0 if zero_variance else variance / total_variance
        contribution_impacts.append(
            StatisticalContributionImpact(
                name=contribution.name,
                direction=contribution.direction,
                sigma=contribution.sigma,
                variance=variance,
                fraction=fraction,
                percentage=fraction * 100.0,
            )
        )

    # Stable sort: descending variance, ties keep original contributor order.
    contribution_impacts.sort(key=lambda impact: impact.variance, reverse=True)

    pair_impacts: list[CovariancePairImpact] = []
    for first_name, second_name, rho, term in discovered:
        fraction = 0.0 if zero_variance else term / total_variance
        pair_impacts.append(
            CovariancePairImpact(
                first=first_name,
                second=second_name,
                rho=rho,
                covariance_term=term,
                fraction=fraction,
                percentage=fraction * 100.0,
                abs_covariance=abs(term),
            )
        )

    # Stable sort: descending magnitude, ties keep declaration order.
    pair_impacts.sort(key=lambda impact: impact.abs_covariance, reverse=True)

    return StatisticalSensitivityResult(
        nominal=authoritative.nominal,
        total_variance=total_variance,
        combined_sigma=authoritative.combined_sigma,
        sigma_multiplier=authoritative.sigma_multiplier,
        contributions=tuple(contribution_impacts),
        covariance_pairs=tuple(pair_impacts),
    )