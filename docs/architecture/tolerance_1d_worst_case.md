# Origlyph — Deterministic 1D Worst-Case Tolerance Engine

## Purpose

This document describes the deterministic 1D worst-case tolerance stack
analysis engine implemented in Stage 15C-R of the Origlyph platform.

The engine computes the worst-case minimum, maximum, deviations, and total
span for a one-dimensional tolerance stack. It is based on interval
propagation and is fully deterministic: identical inputs always produce
identical outputs.

## Scope

This stage establishes:

- **Tolerance domain model** — typed, immutable, unit-aware value objects
  representing tolerance contributions, stacks, and analysis results.
- **Deterministic 1D worst-case engine** — interval-propagation calculation
  of stack extremes.

## Terminology

| Term | Meaning |
|------|---------|
| Tolerance contribution | A single dimension with nominal value and deviation bounds |
| Lower deviation | The lower deviation from nominal (typically negative or zero) |
| Upper deviation | The upper deviation from nominal (typically positive or zero) |
| Stack direction | FORWARD (adds to stack) or INVERSE (subtracts from stack) |
| Nominal stack value | Sum of signed nominals across all contributions |
| Worst-case minimum | Minimum possible stack value under worst-case combination |
| Worst-case maximum | Maximum possible stack value under worst-case combination |
| Total span | Maximum minus minimum (total worst-case tolerance range) |

## Mathematical Model

### Contribution Sign Convention

Each tolerance contribution has:

- `nominal` — the signed nominal dimension
- `lower_deviation` — lower deviation from nominal (typically negative or zero)
- `upper_deviation` — upper deviation from nominal (typically positive or zero)
- `direction` — FORWARD (adds) or INVERSE (subtracts)

The admissible interval for a contribution is:

```
[nominal + lower_deviation, nominal + upper_deviation]
```

### Interval Propagation

For a **FORWARD** contribution, the interval in stack space is:

```
(nominal + lower_deviation, nominal + upper_deviation)
```

For an **INVERSE** contribution, the interval is reversed because the
contribution is subtracted from the stack:

```
(-(nominal + upper_deviation), -(nominal + lower_deviation))
```

### Stack Calculation

Given contributions `c_1, c_2, ..., c_n` with intervals `(l_i, u_i)` in
stack space:

```
nominal = sum of signed nominals (FORWARD: +nominal, INVERSE: -nominal)
minimum = sum of all l_i
maximum = sum of all u_i
lower_deviation = minimum - nominal
upper_deviation = maximum - nominal
total_span = maximum - minimum
```

### Worked Example

Given: A = 100 +0.20/-0.10 (FORWARD), B = 40 +0.10/-0.05 (INVERSE)

Stack = A - B

```
A (FORWARD): [100.0 - 0.10, 100.0 + 0.20] = [99.90, 100.20]
B (INVERSE): [-(40.0 + 0.10), -(40.0 - 0.05)] = [-40.10, -39.95]

nominal = 100.0 - 40.0 = 60.0
minimum = 99.90 + (-40.10) = 59.80
maximum = 100.20 + (-39.95) = 60.25
lower_deviation = 59.80 - 60.0 = -0.20
upper_deviation = 60.25 - 60.0 = +0.25
total_span = 60.25 - 59.80 = 0.45
```

## Units Policy

- All numeric values are standard Python `float` (IEEE 754 double precision).
- No unit conversion is performed. The caller is responsible for ensuring
  consistent units across all contributions.
- No `Decimal`, NumPy, or other numeric dependency is introduced.

## Validation Behavior

The engine rejects invalid tolerance definitions:

- Lower deviation must not exceed upper deviation
- All numeric values must be finite (NaN rejected, infinity rejected)
- Empty stacks are rejected at construction
- Malformed stack definitions are rejected

Invalid input raises a typed exception. No silent repair or undocumented
defaults are applied.

## Deterministic Behavior

- Identical inputs always produce identical outputs.
- No random behavior, timestamps, network calls, or AI participation.
- Input order is preserved for traceability.

## Public API

```python
from origlyph.tolerance import (
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
    StackDirection,
    worst_case,
    OriglyphToleranceError,
    InvalidToleranceError,
    InvalidStackError,
)
```

## Exclusions

This stage explicitly does **not** implement:

- RSS / statistical tolerance analysis
- Monte Carlo simulation
- Capability distributions (Cp/Cpk)
- Nonlinear geometric tolerance propagation
- 3D tolerance stack analysis
- GD&T semantic interpretation
- CAD automatic tolerance extraction
- GUI integration
- AI-generated engineering authority
- Tolerance optimization
- Manufacturing capability recommendations
- Supplier/OEM rules

## AI Boundary

**AI does not override deterministic tolerance calculations.** The engine
is purely deterministic. AI may assist in explaining results or retrieving
reference information, but it never participates in the calculation itself.
