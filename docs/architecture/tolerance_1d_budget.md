# Stage 15G — Deterministic Tolerance Budget Analysis

Deterministic 1D tolerance-budget compliance analysis for Origlyph AI.

## Purpose

Stage 15G answers budget-compliance questions for 1D tolerance stacks:

- What tolerance budget is allowed?
- How much is consumed?
- How much margin remains?
- Is the stack `UNDER_BUDGET`, `AT_BUDGET`, or `OVER_BUDGET`?
- What share of the allowed budget is consumed by each contributor?

## Scope

Budget analysis is **analysis only**. It does **not**:

- modify tolerances
- optimize the stack
- recommend design changes
- resize tolerances
- use Monte Carlo simulation
- perform 3D analysis
- interpret GD&T semantics
- extract tolerances from CAD
- compute Cp/Cpk
- use AI recommendations

## Authoritative Engines

Budget analysis delegates all authoritative math to the existing engines:

| Stage | Engine | Module |
|-------|--------|--------|
| 15C-R | Worst-case analysis | `origlyph.tolerance.worst_case` |
| 15D   | Independent RSS | `origlyph.tolerance.statistical` |
| 15E   | Covariance-aware statistical | `origlyph.tolerance.statistical` |
| 15F   | Sensitivity analysis | `origlyph.tolerance.sensitivity` |

Budget analysis does not replace or duplicate these engines.

## Public API

```python
from origlyph.tolerance import (
    # Worst-case budget compliance
    worst_case_budget,         # (stack, allowed_span) -> WorstCaseBudgetResult
    # Statistical budget compliance
    statistical_budget,        # (stack, allowed_span, sigma_multiplier=3.0, correlations=None)
                             #   -> StatisticalBudgetResult
    # Window compliance check
    worst_case_window_compliance,  # (stack, allowed_lower, allowed_upper)
                                 #   -> WorstCaseWindowResult
    # Compliance status enum
    BudgetStatus,              # UNDER_BUDGET | AT_BUDGET | OVER_BUDGET
    # Result models
    WorstCaseBudgetResult,
    StatisticalBudgetResult,
    WorstCaseContributionBudget,
    StatisticalContributionBudget,
    WorstCaseWindowResult,
)
```

## Compliance Semantics

### UNDER_BUDGET

The stack's actual span fits within the allowed budget with positive
remaining margin:

```
actual_span < allowed_span (within tolerance)
remaining_margin > 0
```

### AT_BUDGET

The actual span equals the allowed span within a small deterministic
tolerance (`1e-12`):

```
|actual_span - allowed_span| <= 1e-12
remaining_margin ≈ 0
```

### OVER_BUDGET

The actual span exceeds the allowed budget:

```
actual_span > allowed_span (beyond tolerance)
remaining_margin < 0
```

## Worst-Case Budget

```python
result = worst_case_budget(stack, allowed_span)
```

Computes:

| Field | Formula |
|-------|---------|
| `actual_span` | From authoritative worst-case engine (`maximum - minimum`) |
| `allowed_span` | Validated input (finite, > 0) |
| `remaining_margin` | `allowed_span - actual_span` |
| `utilization_fraction` | `actual_span / allowed_span` |
| `utilization_percentage` | `100 * utilization_fraction` |
| `status` | `UNDER_BUDGET`, `AT_BUDGET`, or `OVER_BUDGET` |

### Contributor Budget Impact

For each contributor:

| Field | Formula |
|-------|---------|
| `span` | `upper_deviation - lower_deviation` (always >= 0) |
| `share_of_consumed` | `span / actual_span` (0.0 if `actual_span == 0`) |
| `share_of_allowed` | `span / allowed_span` |
| `percentage_of_consumed` | `100 * share_of_consumed` |
| `percentage_of_allowed` | `100 * share_of_allowed` |

Contributors are ordered by descending span; ties preserve input order.

## Statistical Budget

```python
result = statistical_budget(
    stack,
    allowed_span,
    sigma_multiplier=3.0,
    correlations=None,
)
```

The statistical interval span is:

```
actual_span = upper_bound - lower_bound
            = 2 * sigma_multiplier * combined_sigma
```

**Statistical budget compliance does NOT imply worst-case compliance.**
The two methods are separate and must be evaluated independently.

### Contributor Budget Impact

Contributor shares reuse the variance decomposition from Stage 15F
sensitivity analysis:

| Field | Formula |
|-------|---------|
| `variance` | `a_i^2 * sigma_i^2` (from sensitivity) |
| `share_of_consumed` | `variance / total_variance` (from sensitivity) |
| `share_of_allowed` | `share_of_consumed * utilization_fraction` |
| `percentage_of_consumed` | `100 * share_of_consumed` |
| `percentage_of_allowed` | `100 * share_of_allowed` |

Covariance pairs are carried over unchanged from sensitivity analysis.

## Window Compliance

```python
result = worst_case_window_compliance(stack, allowed_lower, allowed_upper)
```

Checks whether the authoritative worst-case interval lies completely
inside a permitted window:

```
is_compliant = (allowed_lower <= minimum) and (maximum <= allowed_upper)
```

Window compliance is **independent** of span-based budget analysis. A
stack can be within its span budget yet outside its permitted window, or
vice versa.

## Zero-Span Policy

If the actual span is exactly zero:

- All contributor `share_of_consumed` values are exactly `0.0`
- All contributor `share_of_allowed` values are exactly `0.0`
- No division is performed; no NaN or infinity is produced

This policy is deterministic and consistent with Stage 15F.

## Equality Policy

`AT_BUDGET` is determined by an absolute tolerance of `1e-12` on the
difference between actual and allowed spans. This is a deterministic
engineering tolerance, not a statistical confidence interval.

## Input Validation

`allowed_span` must be:

- Finite (not NaN, not infinity)
- Strictly positive (> 0)

Invalid values raise `InvalidBudgetError`. No silent repair is performed.

## Determinism

Identical inputs always produce identical outputs. There are no random
sources, no timestamps, no network access, no environment-dependent
behavior, and no AI participation in the calculation path.

## Examples

### Worst-case under-budget

```python
stack = ToleranceStack((
    ToleranceContribution("A", 100.0, -0.10, 0.20),  # span 0.30
    ToleranceContribution("B", 40.0, -0.05, 0.10),    # span 0.15
))
result = worst_case_budget(stack, 1.0)
# actual_span = 0.45, remaining = 0.55, utilization = 0.45
# status = BudgetStatus.UNDER_BUDGET
```

### Worst-case over-budget

```python
result = worst_case_budget(stack, 0.30)
# actual_span = 0.45, remaining = -0.15, utilization = 1.5
# status = BudgetStatus.OVER_BUDGET
```

### Statistical budget

```python
stack = StatisticalStack((
    StatisticalContribution("A", 100.0, 0.1),
    StatisticalContribution("B", 40.0, 0.2),
))
result = statistical_budget(stack, 2.0, sigma_multiplier=3.0)
# combined_sigma = sqrt(0.05) ~= 0.2236
# actual_span = 6 * 0.2236 ~= 1.3416
# status = BudgetStatus.UNDER_BUDGET
```

### Window compliance

```python
result = worst_case_window_compliance(stack, 139.0, 141.0)
# minimum = 139.85, maximum = 140.30
# is_compliant = True
```

## Exclusions

Budget analysis explicitly does **not**:

- Automatically redistribute tolerances
- Imply worst-case compliance from statistical compliance
- Change authoritative tolerance results
- Override deterministic tolerance calculations with AI

## Relationship to Other Stages

- **Stage 15C-R (Worst-case)**: Budget uses worst-case results unchanged.
- **Stage 15D (Independent RSS)**: Statistical budget uses independent RSS.
- **Stage 15E (Correlated RSS)**: Statistical budget supports correlations.
- **Stage 15F (Sensitivity)**: Contributor shares reuse sensitivity fractions.

Budget analysis is strictly additive — it does not modify any existing
engine behavior.