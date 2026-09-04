# Deterministic Tolerance Allocation Validation (Stage 15H)

## Purpose

Stage 15H adds deterministic validation of **user-supplied** tolerance
allocation plans. Given an explicit total tolerance budget and
contributor-level allocated tolerance spans, it determines whether the plan
is:

- structurally valid
- complete
- internally consistent
- under-allocated
- fully allocated
- over-allocated
- compatible with the referenced tolerance stack

This stage validates a supplied plan **only**. It does **not**:

- generate a new allocation
- redistribute tolerance
- optimize tolerance values
- choose which contributor should change
- recommend design changes
- infer manufacturing capability
- use AI

## Allocation Semantics

### Allowed Budget

The `allowed_budget` is the total tolerance budget for the allocation plan.
It must be finite and strictly positive. Zero, negative, NaN, and infinity
are all rejected.

### Allocated Total

The `allocated_total` is the sum of all allocated spans, computed using
`math.fsum` for numerical stability:

```
allocated_total = sum(allocated_span_i)
```

### Remaining Unallocated

```
remaining_unallocated = allowed_budget - allocated_total
```

### Utilization

```
utilization_fraction = allocated_total / allowed_budget
utilization_percentage = 100 * utilization_fraction
```

## Allocation Status

| Status | Condition | Meaning |
|--------|-----------|---------|
| `UNDER_ALLOCATED` | `allocated_total < allowed_budget` (beyond tolerance) | Positive remaining |
| `FULLY_ALLOCATED` | `allocated_total ≈ allowed_budget` (within tolerance) | Zero remaining |
| `OVER_ALLOCATED` | `allocated_total > allowed_budget` (beyond tolerance) | Negative remaining |

## Completeness Mode

### `require_complete=True` (default)

All stack contributors must appear exactly once in the plan. Missing
contributors cause validation failure with `InvalidAllocationError`.

### `require_complete=False`

Partial allocation plans are accepted. The result explicitly reports
incompleteness via `is_complete=False` and lists `missing_contributors`.

An unknown contributor always fails regardless of the completeness mode.

## Duplicate Handling

Duplicate contributor IDs are rejected at `AllocationPlan` construction
time with `InvalidAllocationError`.

## Unknown Contributor Handling

Contributors referenced in the plan but not present in the stack are
rejected with `InvalidAllocationError`.

## Current-Span Comparison

For each stack contributor, the current tolerance span is derived using
the same semantics as Stage 15F / Stage 15G:

```
current_span = upper_deviation - lower_deviation
```

The per-contributor comparison exposes:

- `contributor_id`: identifier
- `allocated_span`: span from the plan
- `current_span`: span from the stack
- `delta_from_current`: `allocated_span - current_span`
- `fraction_of_allowed_budget`: `allocated_span / allowed_budget`

### Zero Current Span

When `current_span == 0`, no division by zero occurs. The
`fraction_of_allowed_budget` is computed directly as
`allocated_span / allowed_budget`.

## Numerical Equality Policy

`FULLY_ALLOCATED` uses the same absolute-tolerance semantics as Stage 15G's
`AT_BUDGET`: an absolute tolerance of `1e-12` on the difference between
allocated total and allowed budget. This is a deterministic engineering
tolerance, not a statistical confidence interval.

## Relation to Stage 15G

Stage 15G answers: "What is the actual stack budget utilization?"

Stage 15H answers: "Is this user-provided allocation plan valid against
its stated budget?"

These are distinct concepts:

- **Allocation status** (`AllocationStatus`): describes whether a *plan*
  is under-, fully, or over-allocated against its *stated budget*.
- **Budget status** (`BudgetStatus`, Stage 15G): describes whether the
  *actual engineering consumption* is under, at, or over budget.

A valid allocation plan does **not** prove actual stack compliance.

## API

```python
from origlyph.tolerance import validate_allocation, AllocationPlan, ToleranceAllocation

result = validate_allocation(
    stack,
    plan,
    require_complete=True,
)
```

### Parameters

- `stack`: `ToleranceStack` — the existing tolerance stack
- `plan`: `AllocationPlan` — the user-supplied allocation plan
- `require_complete`: `bool` — whether all stack contributors must be present (default `True`)

### Returns

`AllocationValidationResult` with:

- `allowed_budget`: the total budget
- `allocated_total`: sum of allocated spans
- `remaining_unallocated`: budget minus allocated
- `utilization_fraction`: allocated / budget
- `utilization_percentage`: 100 * utilization_fraction
- `status`: `UNDER_ALLOCATED`, `FULLY_ALLOCATED`, or `OVER_ALLOCATED`
- `is_complete`: whether all stack contributors are present
- `contributor_results`: per-contributor comparison
- `missing_contributors`: IDs not in the plan

### Raises

`InvalidAllocationError` for:

- invalid total budget (zero, negative, NaN, infinity)
- negative or non-finite allocation
- duplicate contributor IDs
- unknown contributors
- incomplete plan (when `require_complete=True`)

## Worked Examples

### Fully Allocated

```python
stack = ToleranceStack((
    ToleranceContribution("A", 100.0, -0.10, 0.20),
    ToleranceContribution("B", 40.0, -0.05, 0.10),
))
plan = AllocationPlan(
    allowed_budget=1.0,
    allocations=(
        ToleranceAllocation("A", 0.4),
        ToleranceAllocation("B", 0.6),
    ),
)
result = validate_allocation(stack, plan)
assert result.allocated_total == 1.0
assert result.remaining_unallocated == 0.0
assert result.status is AllocationStatus.FULLY_ALLOCATED
```

### Under-Allocated

```python
plan = AllocationPlan(
    allowed_budget=1.0,
    allocations=(
        ToleranceAllocation("A", 0.4),
        ToleranceAllocation("B", 0.3),
    ),
)
result = validate_allocation(stack, plan)
assert result.remaining_unallocated == 0.3
assert result.status is AllocationStatus.UNDER_ALLOCATED
```

### Over-Allocated

```python
plan = AllocationPlan(
    allowed_budget=1.0,
    allocations=(
        ToleranceAllocation("A", 0.7),
        ToleranceAllocation("B", 0.5),
    ),
)
result = validate_allocation(stack, plan)
assert result.remaining_unallocated == -0.2
assert result.status is AllocationStatus.OVER_ALLOCATED
```

## Determinism

Identical inputs always produce identical outputs. There are no random
sources, no timestamps, no network access, no environment-dependent
behavior, and no AI participation in the calculation path.

## Input Immutability

The input stack and allocation plan are never mutated.

## Exclusions

This stage does **not** implement:

- automatic allocation generation
- tolerance redistribution
- optimization
- design recommendation
- cost optimization
- process capability optimization
- Monte Carlo
- nonlinear propagation
- 3D tolerance analysis
- GD&T semantic interpretation
- CAD tolerance extraction
- Cp/Cpk
- AI recommendations

## Explicit Statements

"Allocation validation checks a user-provided plan; it does not generate
or optimize tolerance allocations."

"A valid allocation plan does not by itself prove that the actual
engineering stack satisfies its tolerance requirement."

"Allocation validation does not change authoritative tolerance results."

"AI does not override deterministic tolerance calculations."
