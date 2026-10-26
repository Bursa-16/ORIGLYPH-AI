# Tolerance Workspace Budget (Stage 17D)

## Overview

Stage 17D exposes the existing deterministic Stage 15G tolerance-budget
capability in the workspace UI.  Budget analysis answers the question
"does this tolerance stack fit within a stated budget?" without modifying
tolerances, optimising the stack, or providing recommendations.

---

## Budget Authority API

All budget calculation is delegated to the Stage 15G engine.  No formula
is reproduced in the workspace layer.

### Worst-case budget

```python
from origlyph.tolerance import worst_case_budget, WorstCaseBudgetResult

result: WorstCaseBudgetResult = worst_case_budget(
    stack: ToleranceStack,
    allowed_span: float,          # strictly positive, finite
)
```

### Statistical budget (Stage 15G, not exposed in 17D)

```python
from origlyph.tolerance import statistical_budget, StatisticalBudgetResult

result: StatisticalBudgetResult = statistical_budget(
    stack: StatisticalStack,
    allowed_span: float,          # strictly positive, finite, in span units
    sigma_multiplier: float = 3.0,
    correlations: tuple[Correlation, ...] | None = None,
)
```

Statistical budget is **not wired to the workspace in Stage 17D** because
the workspace specification stores `allowed_combined_sigma` (a sigma value)
while `statistical_budget` expects `allowed_span` (an interval span = 2·k·σ).
These have different engineering units and cannot be silently reinterpreted.
See **Deferred: RSS Statistical Budget** below.

---

## Inputs

| Field | Source | Notes |
|---|---|---|
| `stack` | `ToleranceWorkspaceController._worst_case_stack()` | Derived from workspace contributors |
| `allowed_span` | `WorkspaceSpecification.allowed_worst_case_span` | Must be strictly positive and finite |

`allowed_worst_case_span` is the maximum permitted worst-case span.  Its
engineering meaning maps exactly to `worst_case_budget`'s `allowed_span`
parameter.  No reinterpretation occurs.

---

## Supported Analysis Modes

| Mode | Budget supported | Notes |
|---|---|---|
| `WORST_CASE` | YES | Delegates to `worst_case_budget` |
| `RSS_STATISTICAL` | NO (fail-closed) | Deferred; requires new workspace input |

---

## Outputs (WorstCaseBudgetResult)

| Field | Description |
|---|---|
| `actual_span` | Worst-case span from the authoritative engine |
| `allowed_span` | Budget target (from `allowed_worst_case_span`) |
| `remaining_margin` | `allowed_span − actual_span` (negative when over) |
| `utilization_fraction` | `actual_span / allowed_span` |
| `utilization_percentage` | `utilization_fraction × 100` |
| `status` | `UNDER_BUDGET`, `AT_BUDGET`, or `OVER_BUDGET` |
| `contributions` | Per-contributor budget impacts, sorted by descending span |

Each `WorstCaseContributionBudget` includes: `name`, `span`,
`share_of_consumed`, `share_of_allowed`, `percentage_of_consumed`,
`percentage_of_allowed`.

---

## Execution Behaviour

Budget execution is **explicit only**.

`ToleranceWorkspaceController.run_budget()` must be called directly.
Budget is **never** executed automatically on:

- workspace open or save
- contributor add / edit / remove
- specification sync
- chain name change
- analysis mode change
- analysis run (`run_analysis`)
- decision evaluation (`evaluate_decision`)
- sensitivity execution (`run_sensitivity`)
- selection change

In the UI, the user must press **Run Budget** to obtain a result.

---

## Invalidation

The cached budget result (`_last_budget`) is set to `None` when any
authoritative input changes:

| Trigger | Clears budget? |
|---|---|
| Contributor add / edit / remove | YES |
| `set_specification` (budget target) | YES |
| `set_analysis_mode` | YES |
| `set_chain_name` | YES |
| `evaluate_decision` | NO |
| `run_sensitivity` | NO |
| `run_analysis` | NO |
| Presentation state changes | NO |

---

## Relationship to Analysis / Decision / Sensitivity

| Result type | Independence |
|---|---|
| Analysis result | Independent; `run_budget` does not clear or alter it |
| Decision result | Independent; `run_budget` does not clear or alter it |
| Sensitivity result | Independent; `run_budget` does not clear or alter it |
| Budget result | Independent; decision, sensitivity, analysis do not clear it |

These four results are separate derived outputs of the same authoritative
workspace configuration.  They have no ordering dependency.

---

## Persistence Boundary

Budget result is **RUNTIME_DERIVED_ONLY**.

- Budget is not written to the project file.
- Opening a saved project always yields `last_budget = None`.
- Running budget does not rotate `project_id` or alter the workspace
  configuration fingerprint.

Current schemas are unchanged:

| Schema key | Version |
|---|---|
| `project` | `origlyph.project.v1` |
| `workspace` | `origlyph.tolerance.workspace.v2` |

---

## Identity Boundary

The budget result is derived evidence.  Running budget alone does not
rotate engineering configuration identity.  The budget target
`allowed_worst_case_span` is an existing field in `WorkspaceSpecification`
and is already identity-bearing under the workspace v2 schema.

---

## Exclusions

Stage 17D is **budget inspection only**.  The following are explicitly
out of scope:

- Tolerance redistribution
- Tolerance optimisation
- Contributor reallocation sliders
- Automatic stack rebalancing
- AI-based recommendations
- Speculative risk scoring

---

## Deferred: RSS Statistical Budget

`statistical_budget` requires `allowed_span` in interval-span units
(millimetres, micrometres, etc.).  The workspace v2 specification stores
`allowed_combined_sigma`, which is a sigma value.  Converting between them
requires knowing `sigma_multiplier` and involves engineering semantics that
differ between the two fields.

To support RSS statistical budget, a new authoritative field
(e.g., `allowed_statistical_span`) would be needed in the workspace
specification.  This is deferred to a later stage to avoid silently
overloading existing specification fields.

---

## BUDGET ANALYSIS vs TOLERANCE ALLOCATION

**BUDGET ANALYSIS** (this stage):
Evaluates whether the current worst-case span of a defined tolerance stack
fits within a stated budget limit.  It is a read-only compliance check.
It does not change any tolerance values.

**TOLERANCE ALLOCATION** (future stage):
Distributes a stated budget target across contributors, computing
recommended individual tolerances to satisfy that budget.  Allocation
produces a *plan*; it requires reconciliation with engineering judgement
and authoritative acceptance records.

These are distinct engineering operations.  Stage 17D implements budget
analysis only.

---

## Stage 15G Engine Freeze

Stage 17D does not modify:

- `budget.py`
- `allocation.py`
- `worst_case.py`
- `statistical.py`
- `correlated.py`
- `sensitivity.py`
- `decision.py`
- `reconciliation.py`

The workspace layer delegates entirely to the existing Stage 15 APIs.
