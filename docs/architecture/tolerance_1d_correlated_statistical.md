# Correlated Statistical 1D Tolerance Analysis (Covariance-Aware RSS)

Stage: 15E
Status: Active
Supersedes: none
Extends: `tolerance_1d_statistical.md` (Stage 15D, independent RSS)

> Statistical tolerance analysis does not replace worst-case analysis.
>
> Correlation assumptions must be supplied explicitly; Origlyph does not
> infer manufacturing correlation.
>
> AI does not override deterministic tolerance calculations.

## 1. Purpose

Stage 15E extends the deterministic Stage 15D statistical (RSS) engine with
explicit covariance-aware correlated-contributor support. Engineers who know
— and can justify — a statistical dependence between two contributors may
declare it explicitly; the engine then propagates that dependence through the
1D stack using standard linear variance propagation.

The Stage 15D independent-RSS behavior, the Stage 15C-R worst-case engine,
and every existing public API remain unchanged.

## 2. Scope

In scope:

* Explicit pairwise Pearson correlation coefficients between named
  contributors of a statistical stack.
* Sign-sensitive (direction-aware) covariance propagation.
* A configurable sigma multiplier applied to the combined sigma.
* Typed validation of correlations, contributor references, and propagated
  variance.

Out of scope (explicit exclusions):

* Monte Carlo simulation
* Nonlinear propagation
* Arbitrary or fitted distributions
* Automatic correlation inference from data
* Sensitivity analysis or optimization
* 3D tolerance stacks
* GD&T semantic interpretation
* CAD tolerance extraction
* Cp/Cpk or process capability prediction
* AI recommendations or AI engineering authority

## 3. Terminology

* **Contribution** — one named element of the 1D statistical stack
  (`StatisticalContribution`), with a nominal value, a standard deviation
  `sigma >= 0`, and a stack direction (`FORWARD` adds, `INVERSE` subtracts).
* **Stack direction / sign** — the algebraic coefficient `a_i` of a
  contribution in the linear stack: `+1` for `FORWARD`, `-1` for `INVERSE`.
* **Correlation coefficient rho** — the Pearson correlation between two
  contributors, supplied explicitly by the engineer.
* **Covariance** — `Cov(X_i, X_j) = rho_ij * sigma_i * sigma_j`.
* **Combined sigma** — the standard deviation of the stack sum `Y`.
* **Sigma multiplier k** — user-supplied factor defining the reported
  bounds: `nominal ± k * combined_sigma`.

## 4. Mathematical Model

For a linear 1D stack `Y = sum_i(a_i * X_i)` with independent-and-uncorrelated
errors except for explicitly declared pairwise correlations:

    Var(Y) = sum_i(a_i^2 * sigma_i^2)
           + 2 * sum_{i<j}(a_i * a_j * rho_ij * sigma_i * sigma_j)

Equivalently `Var(Y) = a^T * Sigma * a` where `Sigma` is the covariance
matrix implied by the declared correlations, and:

    combined_sigma = sqrt(Var(Y))
    lower_bound    = nominal - k * combined_sigma
    upper_bound    = nominal + k * combined_sigma

The nominal stack value is unaffected by correlations:

    nominal = sum_i(a_i * nominal_i)

## 5. Sign / Direction Handling

The covariance term uses the **algebraic** signs of the directions:

    2 * a_i * a_j * rho_ij * sigma_i * sigma_j

Directions are never replaced by their absolute values. Consequences:

* Same direction, `rho > 0`: the covariance term is positive — variance grows.
* Opposite directions, `rho > 0`: the covariance term is negative — variance
  shrinks (errors partially cancel across the stack sum).
* Opposite directions, `rho < 0`: the covariance term is positive — variance
  grows.
* The independent variance terms `a_i^2 * sigma_i^2` are always
  non-negative.

## 6. Correlation Contract

* Correlations are supplied as `Correlation(first, second, coefficient)`
  objects — small, typed, frozen, validated value objects.
* `coefficient` must be finite and within the closed interval `[-1, 1]`.
  Values outside the interval, NaN, and infinities are rejected. **No
  clamping is performed.**
* The pair is canonicalized so that `first <= second` lexicographically;
  `Correlation("B", "A", 0.5)` and `Correlation("A", "B", 0.5)` are the same
  object state (equal and hash-identical). Pair symmetry is therefore
  structural, and a pair can never be double counted.
* A contributor may not be correlated with itself. The self-correlation
  (diagonal) is implicitly `rho = 1.0` and must not be declared.
* Every referenced contributor name must exist in the stack. Unknown names
  are rejected.
* Contributor names must be unique when correlations are supplied;
  duplicates would make a correlation reference ambiguous and are rejected.
  (Stacks without correlations are not affected.)
* Re-declaring the same canonical pair with the *same* coefficient is
  accepted and idempotent. Declaring the same pair with *different*
  coefficients is a conflict and is rejected. This behavior is deterministic
  and documented; nothing is silently averaged or overwritten.

### Missing-correlation policy

**A missing pairwise correlation means `rho = 0` (independence).** This is
the exact Stage 15D behavior: supplying no correlations reproduces the
independent RSS result identically. Declaring `rho = 0` explicitly is
accepted and produces the identical result.

## 8. Independence Assumption

The propagation assumes:

* each contributor's error acts linearly on the stack (unit sensitivity),
* all undeclared pairs are independent (`rho = 0`),
* declared correlations are exact engineer-supplied assumptions, not
  estimates fitted by Origlyph.

Origlyph performs no distribution fitting and stores no distribution
assumption: sigma values and correlations are inputs, not inferences.

## 9. Worked Examples

### 9.1 rho = 0 (independence)

`A`: sigma 0.1, `B`: sigma 0.2, both `FORWARD`, no correlations.

    Var = 0.1^2 + 0.2^2 = 0.05
    combined_sigma = sqrt(0.05) ~= 0.223606797749979

### 9.2 rho = +1 (perfect positive, same direction)

Same stack, `Correlation("A", "B", 1.0)`.

    Var = 0.01 + 0.04 + 2*(+1)(+1)(1.0)(0.1)(0.2) = 0.09
    combined_sigma = 0.3

Perfect positive correlation of same-direction contributors makes the stack
behave like a worst-case sum of sigmas: `0.1 + 0.2 = 0.3`.

### 9.3 rho = -1 (perfect negative, same direction)

`A`: sigma 0.1, `B`: sigma 0.1, both `FORWARD`, `Correlation("A", "B", -1.0)`.

    Var = 0.01 + 0.01 + 2*(+1)(+1)(-1.0)(0.1)(0.1) = 0.0
    combined_sigma = 0.0

The bounds collapse onto the nominal; the errors fully cancel.

### 9.4 Mixed-sign contributions (direction-sensitive)

`A`: nominal 100, sigma 0.1, `FORWARD`; `B`: nominal 40, sigma 0.2,
`INVERSE`; `Correlation("A", "B", 1.0)`.

    nominal = (+1)(100) + (-1)(40) = 60
    Var     = 0.01 + 0.04 + 2*(+1)(-1)(1.0)(0.1)(0.2) = 0.01
    combined_sigma = 0.1

Compare `rho = 0`: combined sigma `sqrt(0.05) ~= 0.223606797749979`; and
`rho = -1`: `Var = 0.01 + 0.04 + 0.04 = 0.09`, sigma `0.3`. Same nominal,
three different combined sigmas — the direction signs matter.

## 10. Relationship to the Other Engines

* **Worst-case (Stage 15C-R)** operates on tolerance limit intervals and is
  untouched by Stage 15E. It remains the conservative bound.
* **Independent RSS (Stage 15D)** is the special case of Stage 15E with no
  declared correlations; results are bit-for-bit compatible.
* **Correlated RSS (Stage 15E)** generalizes Stage 15D with explicitly
  declared pairwise correlations only.

A correlated result may be smaller or larger than the independent RSS
result depending on the declared signs and magnitudes; neither statistical
result is a safety guarantee against worst case.

## 11. Determinism

Identical inputs produce identical outputs. There are no random sources, no
timestamps, no network access, no environment-dependent behavior, and no AI
participation in the calculation path. `math.fsum` is used for numerically
stable summation. Input order is preserved for traceability.

## 12. Units Policy

All values are unitless floats at the engine level; contributors in a single
stack must carry consistent units. The engine does not convert, mix, or
interpret units.

## 13. Public API

```python
from origlyph.tolerance import (
    Correlation,               # typed pairwise correlation value object
    StatisticalContribution,   # name, nominal, sigma, direction
    StatisticalStack,          # ordered tuple of contributions
    StatisticalResult,         # nominal, combined_sigma, sigma_multiplier,
                               # lower_bound, upper_bound
    statistical,               # statistical(stack, sigma_multiplier=1.0,
                               #                  correlations=None)
)
```

`Correlation`, `InvalidCorrelationError`, and `InvalidVarianceError` are
additions of Stage 15E. All Stage 15C-R and Stage 15D exports remain
unchanged.


