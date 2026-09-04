# 1D Tolerance Statistical Allocation Reconciliation (Stage 15J)

## Purpose

Stage 15J adds deterministic statistical allocation reconciliation for 1D
tolerance stacks. It compares a user-supplied **statistical allocation
plan** against the **actual statistical uncertainty** produced by the
authoritative Stage 15D/15E engine.

Reconciliation answers:

- Is the allocation plan valid?
- How much sigma is allocated (per contributor and combined)?
- How much sigma is actually consumed?
- Is the actual consumption within the allocation?
- Which contributors are over their allocated sigma?
- Which contributors are under their allocated sigma?
- What allocation margin remains per contributor?
- Is the total allocated budget consistent with actual engineering
  consumption?

This stage **does not**:

- create a new allocation plan
- change tolerance values
- optimize allocations
- recommend design actions
- infer manufacturing capability
- redistribute tolerance
- use AI

## Allocation vs. Actual Distinction

Stage 15I reconciles **worst-case** allocation (linear spans) against actual
worst-case consumption. Stage 15J reconciles **statistical** allocation
(sigma budgets) against actual statistical consumption. The two are
different physical quantities and are never interchanged.

| Stage | Quantity | Engine |
|-------|----------|--------|
| 15I   | ``allocated_span`` vs ``upper_deviation - lower_deviation`` | ``reconcile_allocation`` |
| 15J   | ``allocated_sigma`` vs contributor ``sigma`` | ``reconcile_statistical_allocation`` |

## Allocation Model

A statistical allocation plan is a typed immutable contract:

```python
StatisticalAllocationPlan(
    sigma_multiplier=3.0,
    allocations=(
        StatisticalAllocation("A", 0.20),
        StatisticalAllocation("B", 0.30),
    ),
    allowed_combined_sigma=None,  # optional total budget
)
```

Each ``StatisticalAllocation`` is a per-contributor ``allocated_sigma``:

- finite
- non-negative
- NaN and infinity rejected
- zero permitted (deterministic contributor)

The plan has:

- ``sigma_multiplier``: strictly positive finite ``k``
- ``allocations``: ordered, no duplicate IDs
- ``allowed_combined_sigma``: optional total budget; when supplied must be
  finite and strictly positive

## Independent RSS Reconciliation

For each contributor:

```
margin_sigma = allocated_sigma - actual_sigma
utilization_fraction = actual_sigma / allocated_sigma   (when allocated > 0)
status = UNDER_ALLOCATION | AT_ALLOCATION | OVER_ALLOCATION
```

For the total:

```
allocated_combined_sigma = sqrt(sum(allocated_sigma_i^2))
actual_combined_sigma   = statistical(stack, sigma_multiplier).combined_sigma
combined_sigma_margin   = allocated_combined_sigma - actual_combined_sigma
overall status          = ACTUAL_WITHIN_ALLOCATION | ACTUAL_AT_ALLOCATION
                       | ACTUAL_EXCEEDS_ALLOCATION
```

## Correlated Reconciliation

When ``correlations`` are supplied, both the allocation-side variance and
the actual-side variance use the same correlation structure:

```
allocated_variance = sum_i(a_i^2 * alloc_sigma_i^2)
                  + 2 * sum_{i<j}(
                        a_i * a_j * rho_ij *
                        alloc_sigma_i * alloc_sigma_j
                    )
allocated_combined_sigma = sqrt(allocated_variance)
```

``a_i`` is the algebraic stack direction (+1 FORWARD, -1 INVERSE). Direction
is sign-sensitive: opposite-direction pairs with positive correlation
**cancel** part of the variance. The same correlation structure is passed
to the authoritative ``statistical`` engine to compute the actual combined
sigma, ensuring a valid like-for-like comparison.

The actual combined sigma is **never** re-computed; it is always delegated
to the authoritative Stage 15D/15E engine.

## Zero Allocation Policy

| ``allocated_sigma`` | ``actual_sigma`` | status | ``utilization_fraction`` |
|---------------------|------------------|--------|--------------------------|
| 0                   | 0                | AT_ALLOCATION | ``None``       |
| 0                   | > 0              | OVER_ALLOCATION | ``None``      |
| > 0                 | (any)            | computed from margin | computed |

No division by zero. ``utilization_fraction`` and ``utilization_percentage``
are ``None`` when ``allocated_sigma == 0``.

## Completeness

Default behaviour is ``require_complete=True``: every stack contributor
must appear in the plan. If a contributor is missing, reconciliation fails
with ``InvalidStatisticalAllocationError``.

When ``require_complete=False``:

- missing contributors are reported in ``missing_contributors``
- ``is_complete`` is ``False``
- per-contributor compliance still uses ``0.0`` for unallocated
  contributors, which is consistent with "no budget was assigned"

## Sigma Multiplier

``sigma_multiplier`` is supplied by the caller and applied to the actual
combined sigma for interval bound computation by the authoritative
``statistical`` engine. The result is stored on
``StatisticalAllocationReconciliationResult.sigma_multiplier``. No
conversion is applied on the allocation side; only the actual-side
interval uses the multiplier.

## Relationship to Stage 15G (Budget)

Stage 15G reports actual budget utilization against an allowed budget
(UNDER / AT / OVER). Stage 15J's ``allocation_plan_status`` is a distinct
concept: it classifies the allocation plan against its stated budget
(UNDER_ALLOCATED / FULLY_ALLOCATED / OVER_ALLOCATED). A fully allocated
plan can still fail actual engineering compliance; an under-allocated
plan may still temporarily contain actual consumption. These statuses
are kept semantically distinct and are not collapsed into a single
boolean.

## Relationship to Stage 15H (Allocation)

Stage 15H validates an allocation plan against a stated budget and a
stack. Stage 15J reconciles a validated plan against the actual
statistical consumption. The plan must be valid in the Stage 15H sense
before Stage 15J reconciliation is meaningful, but Stage 15J does **not**
internally re-validate Stage 15H contracts; the plan is treated as a
typed input and its own structural invariants are checked.

## Determinism

The engine is deterministic:

- identical inputs always produce identical outputs
- no random sources, timestamps, network access, environment-dependent
  behavior, or AI participation

## Numerical Equality Policy

The same deterministic engineering equality tolerance of ``1e-12`` is
reused from Stage 15G and Stage 15H:

- ``ACTUAL_AT_ALLOCATION`` when ``|actual - allocated| <= 1e-12``
- otherwise ``ACTUAL_WITHIN_ALLOCATION`` or ``ACTUAL_EXCEEDS_ALLOCATION``

This is a deterministic engineering tolerance, not a statistical
confidence interval.

Sums use :func:`math.fsum`. Engineering values are never rounded
internally. Negligible floating-point round-off (``< 1e-15``) is
permitted in variance propagation; materially negative variance is
rejected.

## Worked Examples

### Independent, under allocation

```python
stack = StatisticalStack(
    (StatisticalContribution("A", 0.0, 0.10),
     StatisticalContribution("B", 0.0, 0.20))
)
plan = StatisticalAllocationPlan(
    sigma_multiplier=3.0,
    allocations=(
        StatisticalAllocation("A", 0.20),
        StatisticalAllocation("B", 0.30),
    ),
)
result = reconcile_statistical_allocation(stack, plan)
# result.allocated_combined_sigma = sqrt(0.20^2 + 0.30^2) = 0.3606
# result.actual_combined_sigma   = sqrt(0.10^2 + 0.20^2) = 0.2236
# result.combined_sigma_margin   = 0.137
# result.actual_statistical_status = ACTUAL_WITHIN_ALLOCATION
```

### Correlated, opposite directions

```python
stack = StatisticalStack(
    (StatisticalContribution("A", 0.0, 0.10, StackDirection.FORWARD),
     StatisticalContribution("B", 0.0, 0.20, StackDirection.INVERSE))
)
plan = StatisticalAllocationPlan(
    sigma_multiplier=3.0,
    allocations=(
        StatisticalAllocation("A", 0.20),
        StatisticalAllocation("B", 0.30),
    ),
)
corr = (Correlation("A", "B", 0.5),)
result = reconcile_statistical_allocation(stack, plan, correlations=corr)
# Cov term: 2 * (+1) * (-1) * 0.5 * 0.2 * 0.3 = -0.06
# Allocated variance = 0.04 + 0.09 - 0.06 = 0.07
# Allocated combined sigma = sqrt(0.07) ≈ 0.2646
```

### Partial plan in incomplete mode

```python
plan = StatisticalAllocationPlan(
    sigma_multiplier=3.0,
    allocations=(StatisticalAllocation("A", 0.20),),
)
result = reconcile_statistical_allocation(stack, plan, require_complete=False)
# result.is_complete is False
# "B" in result.missing_contributors
# B has allocated_sigma=0.0, actual_sigma=0.20 -> OVER_ALLOCATION
# B's utilization_fraction is None (no divide-by-zero)
```

## Exclusions

The following are **not** implemented and are not part of Stage 15J:

- automatic sigma allocation
- optimization
- tolerance redistribution
- design recommendations
- cost optimization
- manufacturing capability optimization
- Monte Carlo
- arbitrary probability distributions
- nonlinear propagation
- 3D tolerance analysis
- GD&T semantic interpretation
- CAD tolerance extraction
- Cp/Cpk
- AI recommendations
- conversion of worst-case spans to sigma

## Authority Statement

> Statistical allocation reconciliation compares explicit statistical
> allocation assumptions with actual statistical uncertainty; it does not
> convert worst-case allocation spans into sigma automatically.

> Statistical compliance does not imply worst-case compliance.

> Reconciliation does not generate or optimize allocation values.

> AI does not override deterministic tolerance calculations.