# Tolerance Workspace Allocation Validation (Stage 17E-2)

## Purpose

Stage 17E-2 connects the workspace v3 allocation plan contract (Stage 17E-1) to
the existing Stage 15H deterministic allocation validator.  It adds an explicit
**Validate Allocation** action to the workspace controller and session, exposing
the Stage 15 result as derived runtime evidence.

## Stage 15 Validation Authority

`origlyph.tolerance.allocation.validate_allocation(stack, plan, *, require_complete=True)`
is the sole allocation validation authority.  It is not duplicated or replaced.
Stage 17E-2 only adapts workspace types to Stage 15 types at the call boundary.

## Workspace v3 Plan Adapter

`WorkspaceAllocationPlan` and `WorkspaceAllocationEntry` are workspace-layer types.
Before calling the Stage 15 validator the controller constructs:

```python
AllocationPlan(
    allowed_budget=plan.allowed_budget,
    allocations=tuple(
        ToleranceAllocation(
            contributor_id=e.contributor_id,
            allocated_span=e.allocated_span,
        )
        for e in plan.entries
    ),
)
```

Engine types (`AllocationPlan`, `ToleranceAllocation`) never appear in workspace
persistence.  This is the same thin-adapter pattern used for `ToleranceStack` and
`StatisticalStack`.

The tolerance stack is always built from `_worst_case_stack()`.  Allocation spans
are tolerance spans, not sigma values; analysis mode does not affect which stack
is used for allocation validation.

## Explicit Validate Allocation Action

`ToleranceWorkspaceController.validate_allocation()` is the only entry point.

Pre-conditions (fail-closed):

1. `allocation_plan` must be present; absent plan raises
   `InvalidToleranceWorkspaceError`.
2. Workspace must have at least one contributor.
3. Every allocation entry `contributor_id` must match a
   `WorkspaceContributor.identifier`; an unknown ID raises
   `InvalidToleranceWorkspaceError`.
4. If the plan is structurally incomplete (a stack contributor has no entry),
   Stage 15 raises `InvalidAllocationError` with `require_complete=True`
   (the default).

No auto-validation occurs on save, open, plan set, or contributor change.
Validation is always explicitly requested by the caller.

## Result Fields

`AllocationValidationResult` (Stage 15H model, reused directly):

| Field | Description |
|-------|-------------|
| `allowed_budget` | Total budget from the plan |
| `allocated_total` | Sum of all allocated spans |
| `remaining_unallocated` | `allowed_budget - allocated_total` |
| `utilization_fraction` | `allocated_total / allowed_budget` |
| `utilization_percentage` | `100 * utilization_fraction` |
| `status` | `UNDER_ALLOCATED`, `FULLY_ALLOCATED`, or `OVER_ALLOCATED` |
| `is_complete` | True when every stack contributor appears in the plan |
| `contributor_results` | Per-contributor: allocated_span, current_span, delta, fraction |
| `missing_contributors` | Stack IDs absent from the plan |

No competing result model is introduced.  Stage 15 fields are exposed as-is.

## Invalidation

The cached `last_allocation_validation` clears when authoritative allocation
inputs change:

| Trigger | Clears? |
|---------|---------|
| `set_allocation_plan(...)` | **YES** |
| `clear_allocation_plan()` | **YES** |
| `add_contributor(...)` | **YES** (stack changes; current_span in result) |
| `edit_contributor(...)` | **YES** (tolerance changes; current_span changes) |
| `remove_contributor(...)` | **YES** (contributor binding may be invalidated) |
| `run_analysis()` | NO |
| `evaluate_decision()` | NO |
| `run_sensitivity()` | NO |
| `run_budget()` | NO |
| `set_specification(...)` | NO (specification is budget/decision only) |
| `set_chain_name(...)` | NO (label only) |
| `set_analysis_mode(...)` | NO (allocation uses worst_case stack always) |

## Contributor Binding

`validate_allocation()` performs a workspace-layer binding check before calling
Stage 15: each allocation entry `contributor_id` must match a
`WorkspaceContributor.identifier`.  Unknown IDs raise
`InvalidToleranceWorkspaceError`.

After `remove_contributor("x")`, any plan that still references `"x"` will fail
the binding check on next validation.  No silent rebinding occurs.

Duplicate `contributor_id` values in the plan are rejected at plan construction
time (`WorkspaceAllocationPlan.__post_init__`); they never reach the validator.

## Runtime-Only Validation Evidence

`last_allocation_validation` is derived runtime evidence.

- **Not persisted** in the project file.
- **Not identity-bearing**: running `validate_allocation()` alone does not change
  `workspace_configuration_fingerprint` or the project identity.
- After `open_project` / `from_state` / `from_snapshot`: `last_allocation_validation = None`.
- The `allocation_plan` itself is authoritative, identity-bearing, and persisted
  (Stage 17E-1 semantics preserved).

## Identity Boundary

`workspace_configuration_fingerprint` = SHA256(`workspace_state_to_snapshot`).

The snapshot contains `allocation_plan` (authoritative state) but not the
validation result (derived).  Therefore:

- Plan change → fingerprint rotates.
- `validate_allocation()` alone → fingerprint unchanged.

## Feature Isolation

`validate_allocation()` does **not** mutate:

- `last_result` (analysis)
- `last_decision`
- `last_sensitivity`
- `last_budget`

`run_analysis()`, `evaluate_decision()`, `run_sensitivity()`, and `run_budget()`
do **not** silently trigger allocation validation.

## Session Integration

`WorkspaceSession` delegates to the controller:

| Member | Description |
|--------|-------------|
| `validate_allocation()` | Delegates to controller |
| `last_allocation_validation` | Mirrors controller cache |
| `allocation_validation_status_text` | `"NOT VALIDATED"` or status string |
| `allocation_validation_summary_text` | Budget / Allocated / Remaining / Utilization |
| `allocation_validation_rows()` | Per-contributor rows for table presentation |

No engineering math in the session.  No parallel result cache.

## Stage Scope

Stage 17E-2 implements the controller/session contract only.  It does **not**
implement:

- Allocation validation UI (Stage 17E-3)
- Integration and release readiness (Stage 17E-4)
- Worst-case allocation reconciliation via `reconcile_allocation` (Stage 17F)

## No Plan Generation

`validate_allocation()` validates a user-supplied plan.  It does **not**:

- Generate an allocation
- Optimize allocated spans
- Auto-balance across contributors
- Suggest design changes
- Use AI

The UI label for this action is **Validate Allocation**, not "Run Allocation".

## Related Documents

- `tolerance_workspace_allocation_plan_v3.md` — Stage 17E-1 contract
- `tolerance_workspace_budget.md` — Stage 17D budget surface
- `tolerance_1d_allocation.md` — Stage 15H validator API
