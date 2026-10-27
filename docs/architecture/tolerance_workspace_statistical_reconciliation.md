# Tolerance Workspace Statistical Reconciliation (Stage 19D)

## Purpose

The statistical reconciliation section of the Tolerance Workspace exposes **Stage 15J
statistical allocation reconciliation** through the workspace UI and session layer.
It answers whether the actual combined sigma is within the per-contributor statistical
allocation plan, using RSS statistics at a user-specified sigma multiplier.

---

## Scope

**V1 (Stage 19D).**

- Workspace schema v4 introduces `statistical_allocation_plan` as an optional field.
- Correlations are not modeled in V1; the engine call uses `correlations=None`
  (all contributors independent).
- The sigma multiplier is carried by the plan itself; no workspace-level default is
  applied.
- `allowed_combined_sigma` in the plan is optional; the allocation-side combined sigma
  defaults to the RSS of per-contributor allocated sigmas when absent.

Statistical allocation reconciliation is distinct from worst-case reconciliation
(Stage 15I, workspace v3).  Both can coexist on a single v4 workspace.

---

## Backend

`origlyph.tolerance.statistical_reconciliation.reconcile_statistical_allocation(
stack, plan, *, correlations=None)` (Stage 15J):

- Re-runs `statistical(stack, sigma_multiplier=plan.sigma_multiplier,
  correlations=None)` for a like-for-like comparison
- Computes per-contributor RSS allocation compliance
- Returns `StatisticalAllocationReconciliationResult` with:
  - `sigma_multiplier` — carried from the plan
  - `allocated_combined_sigma` — RSS of per-contributor allocated sigmas × multiplier
  - `actual_combined_sigma` — actual combined sigma × multiplier from the engine
  - `combined_sigma_margin` — allocated minus actual
  - `allocation_plan_status` — `AllocationStatus` overall plan status
  - `actual_statistical_status` — `StatisticalStatus` from the engine
  - `contributor_compliances` — per-contributor `StatisticalContributorCompliance`
  - `correlation_impacts` — empty list (V1; no correlations modeled)
  - `missing_contributors` — contributors present in stack but absent from plan
  - `is_complete` — True when all contributors have an allocation entry

`StatisticalContributorCompliance` fields:
- `contributor_id`, `allocated_sigma`, `actual_sigma`, `sigma_margin`
- `utilization_fraction`, `utilization_percentage` (None when allocated sigma = 0)
- `status` — `AllocationComplianceStatus`: UNDER / AT / OVER_ALLOCATION

---

## Workspace Schema v4

`WorkspaceState` gains:

```
statistical_allocation_plan: WorkspaceStatisticalAllocationPlan | None = None
```

`WorkspaceStatisticalAllocationPlan` (workspace-layer type):
- `sigma_multiplier: float` — strictly positive
- `entries: tuple[WorkspaceStatisticalAllocationEntry, ...]` — no duplicates
- `allowed_combined_sigma: float | None` — optional, strictly positive when present

`WorkspaceStatisticalAllocationEntry` (workspace-layer type):
- `contributor_id: str`
- `allocated_sigma: float` — non-negative

Both types implement `as_dict()` for JSON persistence.  Engine types
(`StatisticalAllocationPlan`, `StatisticalAllocation`) are constructed at call
time inside `run_statistical_reconciliation()` and do not appear in workspace
persistence.

### Schema version rules

| Schema | specification | allocation_plan | statistical_allocation_plan |
|---|---|---|---|
| v1 | not present | not present | not present |
| v2 | optional (null or dict) | not present | not present |
| v3 | optional | optional | not present |
| v4 | optional | optional | optional |

`_require_exact_keys` strict parsing is used throughout.  Adding a field to an
existing schema version breaks deserialization of files persisted under that version,
hence the new v4 constant.

---

## Controller Layer

`ToleranceWorkspaceController.set_statistical_allocation_plan(plan)`:

- Accepts `WorkspaceStatisticalAllocationPlan | None`
- When `plan` is not None → upgrades schema to v4; clears `_last_statistical_reconciliation`
- When `plan` is None and current schema is v4 → stays v4 (no downgrade), consistent
  with the v3 / `allocation_plan` precedent
- No-op when `plan == self._state.statistical_allocation_plan`

`set_specification()` and `set_allocation_plan()` are v4-aware: they preserve v4
when the workspace is already at v4 (they do not downgrade to v2/v3).

`run_statistical_reconciliation()`:

- Requires `statistical_allocation_plan` to be set; raises `InvalidToleranceWorkspaceError`
- Requires at least one contributor; raises `InvalidToleranceWorkspaceError`
- Validates all entry contributor IDs against current workspace contributors
- Builds `StatisticalAllocationPlan` and `StatisticalStack`, delegates to
  `reconcile_statistical_allocation(stack, plan, correlations=None)`
- Caches result as `_last_statistical_reconciliation`
- Propagates `InvalidStatisticalAllocationError` from Stage 15 on plan validity failure

`last_statistical_reconciliation` property returns the cached result or `None`.

### Stale-result clearing

`_last_statistical_reconciliation` is set to `None` on:

| Event | Reason |
|---|---|
| `_replace_contributors()` | Actual sigmas derive from contributors |
| `set_statistical_allocation_plan()` | Allocated sigmas derive from the plan |
| `from_state()` | Persistence/reload boundary — all runtime state cleared |

---

## Session Layer

`WorkspaceSession` exposes:

| Member | Description |
|---|---|
| `stat_sigma_multiplier` | Transient string field for the sigma multiplier entry |
| `stat_allocation_budget` | Transient string field for optional combined sigma budget |
| `load_statistical_allocation_plan_fields()` | Populate transient fields from the plan |
| `pending_sigma(contributor_id)` | Return pending allocated sigma string |
| `set_pending_sigma(contributor_id, sigma_str)` | Set pending sigma string |
| `sync_statistical_allocation_plan()` | Parse editor fields → controller |
| `clear_statistical_allocation_plan()` | Clear plan and reset transient fields |
| `statistical_allocation_editor_rows()` | Per-contributor editor table rows |
| `last_statistical_reconciliation` | Delegates to controller property |
| `run_statistical_reconciliation()` | Delegates to controller method |
| `statistical_reconciliation_status_text` | `allocation_plan_status.value.upper()` or "NOT RUN" |
| `statistical_reconciliation_summary_text` | k / Alloc σ / Actual σ / Margin compact line |
| `statistical_reconciliation_rows()` | Per-contributor dict rows for the treeview |

`statistical_reconciliation_rows()` row keys: `rank`, `contributor_id`,
`allocated_sigma`, `actual_sigma`, `margin`, `utilization_pct` (float or None),
`status` (str).

---

## UI Layer

`ToleranceWorkspaceView` adds:

- **Statistical Allocation Plan** labelframe at grid row 12
  - Sigma multiplier entry (required, > 0)
  - Optional combined-sigma budget entry
  - Treeview: Contributor, Current σ, Allocated σ
  - Allocated-σ-for-selected entry + Set σ button
  - Apply Statistical Plan / Clear Statistical Plan / Run Statistical Reconciliation buttons

- **Statistical Reconciliation** labelframe at grid row 13
  - Bold status label bound to `_stat_reconciliation_status`
  - Summary label bound to `_stat_reconciliation_summary`
  - Treeview: Contributor, Alloc σ, Actual σ, Margin σ, Utiliz. %, Status

Project File is at grid row 14 (was row 11 before Stage 19D).

`_refresh_statistical_allocation_plan()` and `_refresh_statistical_reconciliation()`
are called from `_refresh_result()` so any workspace mutation (contributor change,
plan change) also clears the display.

---

## Relationship to Other Stages

| Stage | Function |
|---|---|
| 15F Sensitivity | Per-contributor variance/span impact shares |
| 15G Budget | Actual budget utilization — no allocation comparison |
| 15H Allocation | Validates worst-case allocation plan completeness and budget |
| 15I Reconciliation | Compares worst-case allocation vs actual consumption |
| 15J Statistical Reconciliation | Compares sigma allocation vs actual sigma (THIS STAGE) |
