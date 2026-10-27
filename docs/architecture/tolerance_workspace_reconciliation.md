# Tolerance Workspace Reconciliation (Stage 19B)

## Purpose

The reconciliation section of the Tolerance Workspace exposes **Stage 15I
deterministic allocation reconciliation** through the workspace UI and session
layer. It answers whether actual contributor tolerance consumption is within,
at, or exceeding the allocation plan that was previously validated.

---

## Scope

**V1 (Stage 19B) — Worst-case reconciliation only.**

The `WorkspaceAllocationPlan` stores per-contributor worst-case span entries,
which map directly to `AllocationPlan` in the Stage 15 engine. Statistical
reconciliation (`reconcile_statistical_allocation`, Stage 15J) requires a
`StatisticalAllocationPlan` (sigma-based entries), which is not yet represented
in workspace state. Statistical reconciliation is deferred to a future stage.

---

## Backend

`origlyph.tolerance.reconciliation.reconcile_allocation(stack, plan)` (Stage 15I):

- Delegates plan validation to Stage 15H (`validate_allocation`)
- Computes per-contributor actual span from the worst-case `ToleranceStack`
- Returns `AllocationReconciliationResult` with:
  - `allowed_budget` — engineering budget from the plan
  - `allocated_total` — sum of all allocated spans
  - `actual_total_span` — sum of all actual contributor spans
  - `allocation_remaining` — budget minus allocated total
  - `engineering_remaining_margin` — budget minus actual total
  - `total_allocation_margin` — allocated total minus actual total
  - `allocation_plan_status` — `AllocationStatus` from Stage 15H
  - `engineering_budget_status` — `BudgetStatus` (budget utilization)
  - `reconciliation_status` — `ReconciliationStatus` (actual vs allocated)
  - `contributor_compliances` — per-contributor `ContributorAllocationCompliance`

`ContributorAllocationCompliance` fields:
- `contributor_id`, `allocated_span`, `actual_span`, `margin`
- `utilization_fraction`, `utilization_percentage` (None when allocated span = 0)
- `status` — `AllocationComplianceStatus`: UNDER / AT / OVER_ALLOCATION

`ReconciliationStatus` values:
- `ACTUAL_WITHIN_ALLOCATION` — actual total < allocated total
- `ACTUAL_AT_ALLOCATION` — actual total ≈ allocated total (within 1e-12)
- `ACTUAL_EXCEEDS_ALLOCATION` — actual total > allocated total

---

## Controller Layer

`ToleranceWorkspaceController.run_reconciliation()`:

- Requires `allocation_plan` to be set; raises `InvalidToleranceWorkspaceError`
  otherwise
- Requires at least one contributor; raises `InvalidToleranceWorkspaceError`
  otherwise
- Validates all allocation entry contributor IDs against current workspace
  contributors
- Builds `AllocationPlan` and `ToleranceStack`, delegates to
  `reconcile_allocation`
- Caches result as `_last_reconciliation`
- Propagates `InvalidAllocationError` from Stage 15 on plan validity failure

`last_reconciliation` property returns the cached result or `None`.

### Stale-result clearing

`_last_reconciliation` is set to `None` on:

| Event | Reason |
|---|---|
| `_replace_contributors()` | Actual spans derive from contributors |
| `set_allocation_plan()` | Allocated spans derive from the plan |
| `from_state()` | Persistence/reload boundary — all runtime state cleared |

Specification changes (`set_specification`) do **not** clear reconciliation
because the specification (allowed WC span / allowed sigma) does not affect
per-contributor actual vs allocated comparison.

---

## Session Layer

`WorkspaceSession` exposes:

| Member | Description |
|---|---|
| `last_reconciliation` | Delegates to controller property |
| `run_reconciliation()` | Delegates to controller method |
| `reconciliation_status_text` | `rec.reconciliation_status.value.upper()` or "NOT RUN" |
| `reconciliation_summary_text` | Budget / Allocated / Actual / Margin compact line |
| `reconciliation_rows()` | Per-contributor dict rows for the treeview |

`reconciliation_rows()` row keys: `rank`, `contributor_id`, `allocated_span`,
`actual_span`, `margin`, `utilization_pct` (float or None), `status` (str).

---

## UI Layer

`ToleranceWorkspaceView` adds a **Reconciliation** labelframe at grid row 10
(Project File moved to row 11).

Frame contents:
- **Run Reconciliation** button → `_run_reconciliation_impl()` → session
- Bold status label bound to `_reconciliation_status` StringVar
- Summary label bound to `_reconciliation_summary` StringVar
- Treeview with columns: Contributor, Allocated, Actual Span, Margin,
  Utiliz. %, Status

`_refresh_reconciliation()` is called from `_refresh_result()` so that any
workspace mutation that resets the result (contributor changes, mode change,
plan change) also clears the reconciliation display.

---

## Relationship to Other Stages

| Stage | Function |
|---|---|
| 15G Budget | Actual budget utilization — does not compare vs allocation plan |
| 15H Allocation | Validates plan completeness and budget ≥ allocated total |
| 15I Reconciliation | Compares validated allocation against actual consumption |
| 15J Statistical Reconciliation | Deferred — requires StatisticalAllocationPlan |
