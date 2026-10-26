# Tolerance Workspace Allocation UI (Stage 17E-3)

## Purpose

Stage 17E-3 adds the user-facing Allocation Plan editor and the explicit
Validate Allocation action to the tolerance workspace.  It connects the
session-layer editor fields (Stage 17E-3) to the authoritative
`WorkspaceAllocationPlan` (Stage 17E-1) and the validation controller
(Stage 17E-2).

## UI Terminology

| UI Label | Meaning |
|----------|---------|
| Allocation Budget | `WorkspaceAllocationPlan.allowed_budget` — total span budget |
| Allocated Span | `WorkspaceAllocationEntry.allocated_span` — per-contributor span |
| Apply Allocation Plan | Explicit action that writes fields to controller state |
| Clear Plan | Removes the allocation plan from workspace state |
| Validate Allocation | Explicit action that calls `validate_allocation()` |

Terms NOT used:

- Run Allocation (the engine is a validator, not a runner)
- Generate Allocation (no generation implemented)
- Optimize Allocation (no optimization implemented)
- Auto Allocate (no automation implemented)

## Session Transient Fields

`WorkspaceSession` carries the following UI-layer fields:

| Field / Method | Type | Purpose |
|----------------|------|---------|
| `allocation_budget` | `str` | Budget string from the input widget |
| `set_pending_span(id, str)` | method | Store pending span for one contributor |
| `pending_span(id)` | method | Read pending span for one contributor |
| `load_allocation_plan_fields()` | method | Load existing plan into transient fields |

These fields are transient UI state.  They are **not** authoritative.  The
controller's `allocation_plan` is the authoritative state.

`load_allocation_plan_fields()` is called:

1. In `WorkspaceSession.__init__` — to populate fields from a pre-existing plan
   when the session wraps a controller that already has a plan (e.g., after
   `open_project`).
2. In `ToleranceWorkspaceView._open_impl` — after loading a project to populate
   the budget entry widget and span dict before refreshing the treeview.

## Authoritative Plan Editing

`WorkspaceSession.sync_allocation_plan()` is the only path that writes to the
controller.  It:

1. Parses `self.allocation_budget` as a strictly-positive finite float.
2. For each contributor in `controller.contributors` (not from the span dict):
   - Reads `self._allocation_spans.get(contributor_id, "")`.
   - Parses the span string as a non-negative finite float.
   - Blank span is an error (no implicit zero).
3. Builds `WorkspaceAllocationPlan` and calls `controller.set_allocation_plan`.

**Fail-closed**: blank budget, invalid numeric, non-finite, or blank span for
any current contributor raises `InvalidToleranceWorkspaceError`.

No auto-apply occurs on widget focus-out, plan field edit, project save,
project open, or contributor change.

## Contributor Binding

`sync_allocation_plan()` iterates `controller.contributors`, not the span dict.

Consequences:

- A removed contributor's pending span is ignored silently on the next sync.
- A new contributor added after the last sync has no default span; its blank
  entry causes `sync_allocation_plan()` to fail-closed until the user sets it.
- Entry order in `_allocation_spans` does not determine binding; the plan
  entries are ordered by `controller.contributors` order.
- Plan entries produced by `sync_allocation_plan()` carry `contributor_id`
  as the stable binding key, not position.

## Apply Plan Behavior

In the Tkinter view, the **Apply Allocation Plan** button:

1. Reads `_allocation_budget_var` into `session.allocation_budget`.
2. Calls `session.sync_allocation_plan()`.
3. Calls `_refresh_allocation_plan()` and `_refresh_allocation_validation()`.

The **Set Span** button updates `session._allocation_spans` for the selected
contributor (pending only) and refreshes the treeview display column.

No authoritative state is written until **Apply Allocation Plan** is clicked.

## Validate Allocation Flow

```
[Validate Allocation] button
→ ToleranceWorkspaceView._run_validate_allocation_impl()
→ WorkspaceSession.validate_allocation()
→ ToleranceWorkspaceController.validate_allocation()
→ Stage 15H validate_allocation(stack, plan)
→ AllocationValidationResult cached in controller
→ _refresh_allocation_validation() updates status / summary / rows
```

Auto-validation is NOT triggered by:

- Field edits (budget, span entries)
- Apply Allocation Plan
- Clear Plan
- Project save or open
- Contributor add/edit/remove
- Decision, sensitivity, or budget actions

## Validation Result Display

The Allocation Validation Result section displays fields from
`AllocationValidationResult` (Stage 15H model) only:

| Display label | Source field |
|---------------|-------------|
| Status | `status.value.upper()` |
| Budget / Allocated / Remaining / Utilization | summary text from session |
| Per-contributor rows | `contributor_results`: id, allocated, current_span, delta, fraction |

No warnings, scores, or pass/fail verdicts are introduced by the UI.
The UI presents what the engine returned.

## Stale Result Clearing

`last_allocation_validation` becomes `None` when authoritative allocation
inputs change.  The view reflects this immediately through
`_refresh_allocation_validation()`, which is called from `_refresh_result()`
on every contributor or header change, and directly after any plan action.

| User action | `last_allocation_validation` cleared? |
|-------------|--------------------------------------|
| Apply Allocation Plan (budget change) | YES |
| Apply Allocation Plan (span change) | YES |
| Clear Plan | YES |
| Add/edit/remove contributor | YES (via controller) |
| Set Span (pending only, not applied) | NO |
| Validate Allocation | NO (caches new result) |

## Persistence

`allocation_plan` is part of the authoritative workspace state (Stage 17E-1)
and is saved in the project file.

After opening a project:

- `load_allocation_plan_fields()` restores `allocation_budget` and per-contributor
  spans into transient session fields.
- `last_allocation_validation` is `None` — the validation result is not persisted.
- The Allocation Budget entry and contributor treeview Allocated Span column
  are populated from the restored plan.

## Identity

Changes to `allocation_plan` (budget, span, membership) rotate the workspace
configuration fingerprint.  Running `validate_allocation()` alone does not.

See Stage 17E-1 contract (`tolerance_workspace_allocation_plan_v3.md`) for the
complete identity semantics.

## Feature Isolation

`validate_allocation()` does **not** mutate:

- `last_result` (analysis)
- `last_decision`
- `last_sensitivity`
- `last_budget`

`run_analysis()`, `evaluate_decision()`, `run_sensitivity()`, and `run_budget()`
do **not** trigger allocation validation or modify `last_allocation_validation`.

`sync_allocation_plan()` does **not** call `validate_allocation()`.

## Session Integration

`WorkspaceSession` exposes the allocation UI contract:

| Member | Purpose |
|--------|---------|
| `allocation_budget` | Transient budget field |
| `set_pending_span(id, str)` | Update pending span for one contributor |
| `pending_span(id) → str` | Read pending span |
| `load_allocation_plan_fields()` | Load authoritative plan into fields |
| `sync_allocation_plan()` | Parse fields and apply to controller |
| `clear_allocation_plan()` | Clear plan and reset fields |
| `allocation_editor_rows()` | Rows for the editor treeview |
| `validate_allocation()` | Delegate to controller |
| `last_allocation_validation` | Mirror controller cache |
| `allocation_validation_status_text` | Display text ("NOT VALIDATED" or status) |
| `allocation_validation_summary_text` | Compact summary string |
| `allocation_validation_rows()` | Per-contributor rows for result treeview |

No engineering math in the session.  No parallel result cache.

## Explicit Exclusions

Stage 17E-3 does **not** implement:

- Allocation plan generation
- Optimal span calculation
- Auto-balance across contributors
- Worst-case reconciliation (`reconcile_allocation`, Stage 17F)
- Allocation validation UI integration into a notebook/tabbed layout
  (Stage 17E-4)

## Related Documents

- `tolerance_workspace_allocation_plan_v3.md` — Stage 17E-1 contract
- `tolerance_workspace_allocation_validation.md` — Stage 17E-2 contract
- `tolerance_workspace_budget.md` — Stage 17D budget surface
- `tolerance_1d_allocation.md` — Stage 15H validator API
