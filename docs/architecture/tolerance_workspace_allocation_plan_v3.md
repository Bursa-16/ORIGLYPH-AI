# Tolerance Workspace Allocation Plan (v3 Schema) — Stage 17E-1

## Purpose

This document describes the workspace allocation plan contract introduced in
Stage 17E-1.  The allocation plan is the authoritative per-contributor input
required to call the Stage 15H allocation validator.

## Problem

Stage 15H `validate_allocation(stack, plan)` is a plan **validator**, not a
plan generator.  It requires user-supplied per-contributor `allocated_span`
values and a total `allowed_budget`.  These inputs are absent from workspace
v2 (`WorkspaceSpecification` carries engineering limits, not allocation spans).
Stage 17E cannot expose allocation validation without first representing these
inputs in workspace state.

Reusing `WorkspaceSpecification.allowed_worst_case_span` as the budget is
rejected: doing so gives one field two distinct engineering roles (budget
compliance inspection vs allocation validation), creating ambiguity and a
silent semantic hazard.

## Contract

### `WorkspaceAllocationEntry`

Carries one user-supplied allocated span for a single contributor.

| Field | Type | Rule |
|-------|------|------|
| `contributor_id` | `str` | Non-empty, non-whitespace |
| `allocated_span` | `float` | Finite, ≥ 0 |

`contributor_id` must match a `WorkspaceContributor.identifier` in the same
workspace.  This binding is enforced at validation time (Stage 17E-2), not at
construction, so the plan may be authored before contributors are finalised.

### `WorkspaceAllocationPlan`

Carries the total budget and a tuple of per-contributor entries.

| Field | Type | Rule |
|-------|------|------|
| `allowed_budget` | `float` | Finite, strictly > 0 |
| `entries` | `tuple[WorkspaceAllocationEntry, ...]` | No duplicate `contributor_id` values |

`allowed_budget` is a separate field from
`WorkspaceSpecification.allowed_worst_case_span`.  Both fields may coexist in
a v3 workspace; they serve different engineering roles and must not be aliased.

## Workspace Schema v3

Schema version string: `origlyph.tolerance.workspace.v3`

V3 extends v2 by adding `allocation_plan` to the snapshot.

**V3 snapshot keys (exact):**

```json
{
  "schema_version": "origlyph.tolerance.workspace.v3",
  "chain_name": "...",
  "analysis_mode": "worst_case",
  "contributors": [...],
  "specification": null,
  "allocation_plan": {
    "allowed_budget": 0.5,
    "entries": [
      {"contributor_id": "A", "allocated_span": 0.2},
      {"contributor_id": "B", "allocated_span": 0.3}
    ]
  }
}
```

`allocation_plan` may be `null` in a v3 snapshot (plan cleared after upgrade).
`specification` may also be `null`.

`_require_exact_keys` strict validation applies: any unknown key in the
snapshot, plan dict, or entry dict raises `InvalidToleranceWorkspaceError`.

## Schema Upgrade Rules

| Starting schema | `set_allocation_plan(plan)` | `clear_allocation_plan()` |
|---|---|---|
| v1 | Upgrades to v3 | No-op (plan already None) |
| v2 | Upgrades to v3 | No-op (plan already None) |
| v3 | Stays v3 (or no-op if same plan) | Stays v3, plan → None |

No downgrade ever occurs.  This matches the v1 → v2 precedent for
`set_specification`.

## Backward Compatibility

V1 and v2 snapshots load cleanly with `allocation_plan=None`.  The `from_dict`
dispatcher reads `schema_version` and routes to the correct loader.  V1 and v2
`WorkspaceState` objects reject a non-None `allocation_plan` at construction
time, preventing accidental misuse.

## Identity Semantics

`workspace_configuration_fingerprint` = SHA256(`workspace_state_to_snapshot`).
The allocation plan is part of the snapshot, so any change to the plan
(budget, entries, or any span) rotates the fingerprint and therefore the
project identity.

Changes that rotate fingerprint:
- `allowed_budget` value
- Adding or removing an entry
- Changing `contributor_id` in an entry
- Changing `allocated_span` in an entry

Changes that do NOT rotate fingerprint:
- Running analysis, sensitivity, budget, or decision (runtime-derived only)
- Schema upgrade alone (v3 with `allocation_plan=None` has a fixed fingerprint)

## Engine Adapter (Thin Layer)

`WorkspaceAllocationPlan` is a workspace-layer type.  Before calling the Stage
15H validator, the controller constructs:

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

Engine types (`AllocationPlan`, `ToleranceAllocation`) never appear in
workspace persistence.  This is the same thin-adapter pattern used for
`ToleranceStack` and `StatisticalStack`.

## Explicit Execution

`set_allocation_plan` carries the plan into workspace state.  It does **not**
run validation.  Validation is a separate explicit step (`validate_allocation`,
Stage 17E-2).  No auto-validation occurs on save, open, edit, or sync.

UI label: **Validate Allocation** (not "Run Allocation" — the engine is a
validator, not a generator or optimizer).

## Persistence

`allocation_plan` is part of the authoritative workspace snapshot and is
therefore saved in the project file.  Validation results are runtime-derived
and are **not** persisted.

## Stage Scope

Stage 17E-1 introduces the contract only.  It does **not** implement:
- Validation execution (Stage 17E-2)
- Validation UI (Stage 17E-3)
- Integration and release readiness (Stage 17E-4)
- Worst-case reconciliation via `reconcile_allocation` (Stage 17F)

## Related Documents

- `tolerance_workspace_v2.md` — v2 schema, `WorkspaceSpecification`
- `tolerance_workspace_budget.md` — Stage 17D budget surface
- `tolerance_1d_allocation.md` — Stage 15H validator API
