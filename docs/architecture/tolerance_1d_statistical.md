# Origlyph — Deterministic 1D Statistical (RSS) Tolerance Analysis

## Purpose

This document describes the deterministic 1D statistical tolerance stack
analysis engine implemented in Stage 15D of the Origlyph platform.

The engine combines independent tolerance contributors using root-sum-square
(RSS) propagation to produce a nominal stack value, a combined standard
deviation (sigma), and statistical lower/upper bounds for a configurable
sigma multiplier.

The engine is fully deterministic: identical inputs always produce identical
outputs.

## Mathematical Model

### Independence Assumption

Statistical combination is only valid for **independent** contributors.
This engine assumes every contribution is independent. Correlated
contributors and covariance matrices are **not** supported in this stage.

### RSS Equation

For independent contributions with standard deviations `sigma_i`, the
combined standard deviation is:

```
combined_sigma = sqrt(sum(sigma_i^2))
```

### Sigma Meaning

Each `StatisticalContribution` carries an explicit, user-supplied standard
deviation `sigma`. No distribution is assumed. The engine does not derive
sigma from tolerance limits, and it does not infer process capability.

### Sigma Multiplier

For a requested multiplier `k` (finite and strictly positive), the
statistical bounds are:

```
lower_bound = nominal - k * combined_sigma
upper_bound = nominal + k * combined_sigma
```

Common values are `k = 1`, `k = 2`, and `k = 3`. For a normal distribution
these correspond to approximately 68%, 95%, and 99.7% coverage, but the
engine makes no distribution assumption.

### Nominal Handling

The nominal stack value is the sum of signed nominals. A `FORWARD`
contribution adds its nominal; an `INVERSE` contribution subtracts it.

### Sign Handling

Direction/sign affects the nominal contribution only. The standard
deviation contribution is always non-negative because variance is additive
regardless of direction:

```
sigma_combined = sqrt(sum(sigma_i^2))
```

is identical whether any contributor is FORWARD or INVERSE.

### Worked Example

Given two independent contributors:

```
A: nominal = 100.0, sigma = 0.1 (FORWARD)
B: nominal = 40.0,  sigma = 0.2 (INVERSE)
```

```
combined_sigma = sqrt(0.1^2 + 0.2^2) = sqrt(0.05) ≈ 0.2236
nominal        = 100.0 - 40.0 = 60.0

for k = 1:
lower_bound = 60.0 - 0.2236 = 59.7764
upper_bound = 60.0 + 0.2236 = 60.2236

for k = 3:
lower_bound = 60.0 - 3 * 0.2236 = 59.3292
upper_bound = 60.0 + 3 * 0.2236 = 60.6708
```

## Units

- All numeric values are standard Python `float` (IEEE 754 double precision).
- No unit conversion is performed. The caller is responsible for ensuring
  consistent units across all contributions.
- No `Decimal`, NumPy, or other numeric dependency is introduced.
- `math.fsum`-style stabilization is used for summation where warranted.

## Validation

The engine rejects invalid statistical definitions:

- NaN rejected
- +/- infinity rejected
- negative sigma rejected
- zero or negative sigma multiplier rejected
- invalid (non-finite) sigma multiplier rejected
- empty statistical stacks rejected
- malformed statistical stacks rejected

Zero sigma is permitted and explicitly supported: a constant (deterministic)
including a zero-sigma contribution adds no uncertainty.

No silent coercion of invalid engineering data is performed.

## Relationship to Worst-Case Analysis

`worst_case(...)` and `statistical(...)` are separate, distinct APIs with
separate result models (`WorstCaseResult` and `StatisticalResult`).

The Stage 15C-R worst-case engine is unchanged. Statistical analysis does
not modify worst-case behavior.

**Statistical tolerance analysis does not replace worst-case analysis.**

## Deterministic Behavior

- Identical inputs always produce identical outputs.
- No random behavior, timestamps, network calls, or AI participation.
- Input order is preserved for traceability.
- Repeated identical calculations produce identical results.

## Public API

```python
from origlyph.tolerance import (
    StatisticalContribution,
    StatisticalStack,
    StatisticalResult,
    statistical,
    StackDirection,
    InvalidStatisticalError,
)
```

## Limitations

- Correlated contributors are not supported
- Covariance matrices are not supported
- Non-normal distribution modeling is not supported
- Monte Carlo simulation is not supported
- Process capability (Cp/Cpk) prediction is not supported
- 3D stack analysis is not supported
- GD&T semantic analysis is not supported
- CAD automatic tolerance extraction is not supported
- Optimization is not supported
- AI-generated engineering authority is not supported

## AI Boundary

**AI does not override deterministic tolerance calculations.** The engine
is purely deterministic. AI may assist in explaining results or retrieving
reference information, but it never participates in the calculation itself.