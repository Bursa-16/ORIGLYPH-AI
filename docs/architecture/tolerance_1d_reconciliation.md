# Deterministic Allocation Reconciliation (Stage 15I)

## Purpose

Stage 15I adds deterministic reconciliation between a user-supplied allocation
plan and actual authoritative tolerance consumption.

It answers:

- Is the allocation plan valid?
- How much tolerance is allocated?
- How much tolerance is actually consumed?
- Is actual consumption within the allocation?
- Which contributors are over their allocated span?
- Which contributors are under their allocated span?
- What allocation margin remains per contributor?
- Is total allocated budget consistent with actual engineering budget?

This is reconciliation and compliance analysis only. It does **not**:

- create a new allocation plan
- change tolerance values
- optimize allocations
- recommend which tolerances to loosen/tighten
- infer manufacturing capability
- use AI

## Relationship to Other Stages

* **Stage 15G** (budget): actual budget utilization.
* **Stage 15H** (allocation): validation of a user-supplied allocation plan.
* **Stage 15I** (reconciliation): comparison of validated allocation against
  actual engineering consumption.

These responsibilities are kept distinct:

- A fully allocated plan can still fail actual engineering compliance.
- An under-allocated plan may still temporarily contain actual consumption.

## Actual Contributor Span

For each tolerance contribution, the actual span uses the same semantics
as Stage 15F / Stage 15G / Stage 15H:

```
actual_span = upper_deviation - lower_deviation
```

Direction must not make span negative. The span is always non-negative.

## Contributor Compliance Status

| Status | Condition | Meaning |
|--------|-----------|---------|
| `UNDER_ALLOCATION` | `actual_span < allocated_span` | Positive margin (unused room) |
| `AT_ALLOCATION` | `actual_span == allocated_span` | Zero margin |
| `OVER_ALLOCATION` | `actual_span > allocated_span` | Negative margin (exceeds allocation) |

### Zero Allocation Policy

When `allocated_span == 0`:
- `actual_span == 0` -> `AT_ALLOCATION`
- `actual_span > 0` -> `OVER_ALLOCATION`
- `utilization_fraction` is `None` (no division by zero)

## Total Reconciliation

The total reconciliation exposes:

- `allowed_budget`: from the plan
- `allocated_total`: sum of allocated spans
- `actual_total_span`: sum of actual spans
- `allocation_remaining`: `allowed_budget - allocated_total`
- `engineering_remaining_margin`: `allowed_budget - actual_total_span`
- `total_allocation_margin`: `allocated_total - actual_total_span`

## Reconciliation Status

| Status | Condition |
|--------|-----------|
| `ACTUAL_WITHIN_ALLOCATION` | `actual_total_span < allocated_total` |
| `ACTUAL_AT_ALLOCATION` | `actual_total_span == allocated_total` |
| `ACTUAL_EXCEEDS_ALLOCATION` | `actual_total_span > allocated_total` |

## Numerical Equality Policy

Reuses the established Origlyph tolerance numerical equality tolerance
(`1e-12`) from Stage 15G / Stage 15H. No new or contradictory epsilon
is introduced.

## API

```python
from origlyph.tolerance import reconcile_allocation

result = reconcile_allocation(stack, plan, require_complete=True)
```

### Parameters

- `stack`: `ToleranceStack` — the existing tolerance stack
- `plan`: `AllocationPlan` — the user-supplied allocation plan
- `require_complete`: `bool` — whether all stack contributors must be present (default `True`)

### Returns

`AllocationReconciliationResult` with:

- `allowed_budget`, `allocated_total`, `actual_total_span`
- `allocation_remaining`, `engineering_remaining_margin`
- `total_allocation_margin`
- `allocation_plan_status`, `engineering_budget_status`
- `reconciliation_status`
- `contributor_compliances`: per-contributor compliance

### Raises

`InvalidAllocationError` (propagated from Stage 15H) for invalid plans.

## Worked Examples

### Actual Within Allocation

```python
stack = ToleranceStack((
    ToleranceContribution("A", 100.0, -0.10, 0.20),  # span 0.30
))
plan = AllocationPlan(
    allowed_budget=1.0,
    allocations=(ToleranceAllocation("A", 0.60),),
)
result = reconcile_allocation(stack, plan)
cc = result.contributor_compliances[0]
assert cc.margin == pytest.approx(0.30)
assert cc.status is AllocationComplianceStatus.UNDER_ALLOCATION
```

### Actual Exceeds Allocation

```python
plan = AllocationPlan(
    allowed_budget=1.0,
    allocations=(ToleranceAllocation("A", 0.20),),
)
result = reconcile_allocation(stack, plan)
cc = result.contributor_compliances[0]
assert cc.margin == pytest.approx(-0.10)
assert cc.status is AllocationComplianceStatus.OVER_ALLOCATION
```

## Determinism

Identical inputs always produce identical outputs. There are no random
sources, no timestamps, no network access, no environment-dependent
behavior, and no AI participation in the calculation path.

## Input Immutability

The input stack and allocation plan are never mutated.

## Exclusions

This stage does **not** implement:

- automatic allocation changes
- optimization
- tolerance redistribution
- design recommendations
- cost optimization
- manufacturing capability optimization
- Monte Carlo
- nonlinear propagation
- 3D tolerance analysis
- GD&T semantic interpretation
- CAD tolerance extraction
- Cp/Cpk
- AI recommendations

## Statistical Reconciliation Scope

Stage 15I focuses on worst-case allocation reconciliation. Statistical
contributor reconciliation is deferred to a later stage to keep the
engineering model correct and unambiguous.

## Explicit Statements

"Reconciliation compares a validated allocation plan with actual tolerance
consumption; it does not generate a new allocation."

"Over-allocation findings are analytical results, not automatic design
recommendations."

"A valid allocation plan does not guarantee that the actual stack is
compliant."

"AI does not override deterministic tolerance calculations."
