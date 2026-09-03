# Deterministic 1D Tolerance Sensitivity & Contributor Impact Analysis

Stage: 15F
Status: Active
Supersedes: none
Extends: `tolerance_1d_worst_case.md` (15C-R), `tolerance_1d_statistical.md`
(15D), `tolerance_1d_correlated_statistical.md` (15E)

> Sensitivity analysis explains contribution; it does not change
> authoritative tolerance results.
>
> Negative covariance contribution represents statistical cancellation and
> must not be silently converted to a positive impact.
>
> AI does not override deterministic tolerance calculations.

## 1. Purpose

Stage 15F adds an explanatory layer on top of the three authoritative
tolerance engines. It answers the engineering question *"which contributors
dominate this stack?"* by decomposing each authoritative result into
per-contributor and per-pair impacts with explicit fractions and percentages.

Sensitivity analysis is read-only by contract: it never modifies tolerances,
never optimizes the stack, never recommends design changes, never infers
manufacturing capability, and never involves AI.

## 2. Scope

In scope:

* Worst-case contributor impact decomposition of the authoritative
  worst-case span.
* Independent statistical variance decomposition
  (`a_i^2 * sigma_i^2` per contributor).
* Correlated statistical decomposition into individual variance terms and
  signed pairwise covariance terms.
* Deterministic ranking with documented tie-breaking.

Out of scope (explicit exclusions):

* Tolerance optimization or automatic tolerance redistribution
* Automatic recommendations or cost optimization
* Monte Carlo simulation
* Nonlinear sensitivity
* 3D tolerance stacks
* GD&T semantic interpretation
* CAD tolerance extraction
* Cp/Cpk or process capability prediction
* AI recommendations or AI engineering authority

## 3. Authoritative-Result Principle

Every total used by sensitivity analysis is taken from the authoritative
engine result, never recomputed independently:

* `worst_case_sensitivity(stack)` calls `worst_case(stack)` and uses its
  `total_span`.
* `statistical_sensitivity(stack, ...)` calls `statistical(stack, ...)`
  and uses its `nominal`, `combined_sigma`, and `sigma_multiplier`.

Consequences:

* All engine validation applies unchanged — invalid input that
  `worst_case`/`statistical` rejects can never become valid through a
  sensitivity API (finite-value checks, sigma checks, multiplier checks,
  correlation identity, duplicate/conflicting pairs, non-PSD variance).
* `total_variance == combined_sigma ** 2` exactly, by construction.

## 4. Worst-Case Contributor Impact

For each contribution of the stack:

* `signed_nominal` — algebraic stack contribution of the nominal:
  `+nominal` for `FORWARD`, `-nominal` for `INVERSE`.
* `lower_deviation`, `upper_deviation` — the contribution's own deviations
  from its nominal.
* `span = upper_deviation - lower_deviation` — the contributor tolerance
  span. Direction never makes it negative; the span is the width of the
  admissible interval in stack space and is always non-negative.
* `fraction = span / total_span` — share of the authoritative worst-case
  span.
* `percentage = fraction * 100.0`.

The individual spans partition the worst-case span: for a 1D linear stack
the worst-case span equals the sum of the contributor spans, so the
fractions sum to exactly `1.0` whenever `total_span > 0`.

### Zero-span policy

If the authoritative `total_span` is exactly `0.0` (all deviations zero),
there is no division by zero and no NaN/infinity: **every fraction and
percentage is deterministically reported as `0.0`.**

## 5. Independent Statistical Variance Contribution

For each statistical contribution:

* `variance = a_i^2 * sigma_i^2`, where `a_i` is `+1` (`FORWARD`) or `-1`
  (`INVERSE`). Since the term is squared, the direction does not change the
  individual variance; it only changes the nominal.
* `fraction = variance / total_variance`,
  `percentage = fraction * 100.0`, with `total_variance` taken from the
  authoritative engine (`combined_sigma ** 2`).

When `total_variance > 0` the individual fractions sum to approximately
`1.0` (floating-point summation tolerance only). Ranking is by descending
**variance**, never by sigma — sigma is reported for traceability, the
documented decomposition metric is variance.

## 6. Correlated Statistical Decomposition

For a stack with declared correlations the authoritative Stage 15E variance

    Var(Y) = sum_i(a_i^2 * sigma_i^2)
           + 2 * sum_{i<j}(a_i * a_j * rho_ij * sigma_i * sigma_j)

is exposed as **two separate contribution classes**:

**A. Individual variance terms** — one per contributor:

    variance_i = a_i^2 * sigma_i^2

Each carries the same fields as the independent case (identifier, sigma,
direction, variance, fraction, percentage).

**B. Pairwise covariance terms** — one per declared correlation:

    covariance_term = 2 * a_i * a_j * rho_ij * sigma_i * sigma_j

Each pair impact exposes:

* `first`, `second` — the contributor identifiers (canonical order)
* `rho` — the declared correlation coefficient
* `covariance_term` — the **signed** term exactly as it enters the
  variance equation
* `fraction` / `percentage` — signed share of the total variance, defined
  only when `total_variance > 0`
* `abs_magnitude` — `abs(covariance_term)`, provided for ranking only and
  never used in the variance equation

Contract rules:

* A covariance pair is **never assigned to a single contributor**. It is a
  first-class joint term of the pair.
* **Negative covariance terms are preserved as negative.** They represent
  statistical cancellation and must not be silently converted to a positive
  impact or to an absolute value.
* The authoritative variance identity holds by construction:

      total_variance == sum(individual variance terms)
                      + sum(pairwise covariance terms)

* Fractions of individual terms plus pair fractions sum to approximately
  `1.0` when `total_variance > 0` (floating-point tolerance), preserving
  signed cancellation rather than renormalizing it away.

### Near-zero variance policy

Stage 15E's numerical policy is reused **unchanged**: round-off variance
within `-1e-15` (the established `_NEGLIGIBLE_VARIANCE` tolerance) is
normalized to `0.0`; materially negative variance is rejected by the
authoritative engine as `InvalidVarianceError` before sensitivity runs.
There is no second, conflicting threshold. When the total variance is zero
(all-zero sigma, or exact cancellation at `rho = -1`), every fraction and
percentage is deterministically reported as `0.0`.

## 7. Ranking Policy

Ranking is deterministic and does not alter any reported value:

* **Worst-case:** descending contributor span.
* **Independent statistical:** descending individual variance.
* **Covariance pairs:** descending absolute covariance magnitude
  (`abs_magnitude`) — signed values are ranked by their magnitude so that
  strong cancellation ranks high; the signed `covariance_term` itself is
  never reordered into positivity.

**Tie-breaking:** when two entries have an exactly equal metric, original
input/declaration order is preserved (stable sort by input position). The
result models expose the ranked lists directly — `impacts` (worst-case),
`contributions` (statistical) and `covariance_pairs` — sorted descending by
the documented metric, with every record carrying its contributor
identifier and declared direction/rho so each ranked entry remains
traceable to its stack or declaration position.

## 8. Worked Examples

### 8.1 Worst-case contributor ranking

`A = 100 +0.20/-0.10` (span 0.30), `B = 40 +0.10/-0.05` (span 0.15),
both `FORWARD`.

    total_span = 0.30 + 0.15 = 0.45
    A: fraction 0.30/0.45 = 2/3 ~= 0.6667  (66.67%)
    B: fraction 0.15/0.45 = 1/3 ~= 0.3333  (33.33%)
    Ranking: A > B

### 8.2 Independent RSS variance decomposition

sigma_A = 0.1, sigma_B = 0.2, both `FORWARD`, no correlations.

    var_A = 0.01, var_B = 0.04, total = 0.05
    A: 0.01/0.05 = 0.20 (20%)
    B: 0.04/0.05 = 0.80 (80%)
    Ranking: B > A — even though A's nominal is larger; ranking is by
    variance contribution, not by nominal or sigma.

### 8.3 Positive covariance

Same stack with `Correlation("A", "B", 1.0)`:

    covariance_term = 2*(+1)(+1)(1.0)(0.1)(0.2) = +0.04
    total_variance = 0.01 + 0.04 + 0.04 = 0.09 (matches Stage 15E)
    A: 0.01/0.09 ~= 0.1111, B: 0.04/0.09 ~= 0.4444
    pair: +0.04/0.09 ~= 0.4444 — the correlation contributes 44% of the
    variance and must not be attributed to either contributor alone.

### 8.4 Negative covariance (cancellation)

`A` and `B` at sigma 0.1 each, both `FORWARD`, `rho = -1.0`:

    covariance_term = 2*(1)(1)(-1)(0.1)(0.1) = -0.02
    total_variance = 0.01 + 0.01 - 0.02 = 0.0
    Zero-variance policy: all fractions/percentages are 0.0, bounds collapse
    onto the nominal. The pair's signed term remains -0.02 in the impact
    list; its abs_covariance ranks it, but nothing is made positive.

### 8.5 Mixed contributor directions

`A = 100` sigma 0.1 `FORWARD`, `B = 40` sigma 0.2 `INVERSE`,
`Correlation("A", "B", 1.0)`:

    covariance_term = 2*(+1)(-1)(1.0)(0.1)(0.2) = -0.04
    total_variance = 0.01 + 0.04 - 0.04 = 0.01
    The opposite stack direction flips the sign of the covariance term:
    the same positive correlation that increased variance in 8.3 now
    cancels variance here. Direction signs are never absolutized.

## 9. Numerical Stability and Determinism

* `math.fsum` is used for all summation of variance/covariance terms.
* No internal rounding of engineering results; approximate assertions exist
  only in tests and in the established near-zero handling above.
* Identical inputs produce identical outputs: no randomness, no timestamps,
  no network, no environment dependence, no AI in the calculation path.
* Sensitivity functions **never mutate** their inputs — stacks, contributors
  and correlations are only read.

## 10. Public API

```python
from origlyph.tolerance import (
    worst_case_sensitivity,        # (stack) -> WorstCaseSensitivityResult
    statistical_sensitivity,       # (stack, sigma_multiplier=1.0,
                                   #  correlations=None)
                                   #   -> StatisticalSensitivityResult
    WorstCaseContributionImpact,   # name, direction, signed_nominal,
                                   # lower_deviation, upper_deviation, span,
                                   # fraction, percentage
    StatisticalContributionImpact, # name, direction, sigma, variance,
                                   # fraction, percentage
    CovariancePairImpact,          # first, second, rho, covariance_term,
                                   # fraction, percentage, abs_covariance
    WorstCaseSensitivityResult,    # total_span,
                                   # impacts (ranked: descending span)
    StatisticalSensitivityResult,  # nominal, total_variance, combined_sigma,
                                   # sigma_multiplier,
                                   # contributions (ranked: descending
                                   # variance),
                                   # covariance_pairs (ranked: descending
                                   # abs_covariance)
)
```

Ranking notes:

* Results expose the ranked lists directly; ties preserve original
  stack/declaration order (stable sort).
* An explicitly declared `rho = 0` pair contributes nothing to the variance
  and produces no `CovariancePairImpact` entry; identical duplicate
  declarations are idempotent (one entry per canonical pair).

The existing `worst_case` and `statistical` entry points are unchanged;
`worst_case_sensitivity` / `statistical_sensitivity` are deliberately
separate: analysis and explanation are different operations with different
contracts.

## 11. Traceability

Impact records preserve contributor identifiers, declared directions and
declared correlations exactly as supplied. The ranked lists are stable
sorts: on ties, entries keep their original stack or declaration position,
and every record carries its identifier pair (`name` / `first`, `second`),
so any reported fraction or percentage can be traced back to the exact
contributor or `Correlation` declaration and audited against the
authoritative engine result it decomposes.


