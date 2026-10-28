# Origlyph AI v0.4.0-alpha.8

**Release date:** 2026-10-28
**Package version:** `0.4.0a8`
**Tag:** `v0.4.0-alpha.8`
**Status:** PRE-RELEASE / ALPHA

---

## Highlights

This release completes the tolerance workspace reconciliation arc (Stages 19B and 19D),
exposing deterministic worst-case and statistical allocation reconciliation directly
inside the interactive workspace.

- **Worst-case reconciliation workspace UI** — Run Reconciliation button; per-contributor
  actual-vs-allocated compliance; reconciliation status, summary, and treeview
- **Workspace schema v4** — introduces `statistical_allocation_plan` as an optional
  persisted field; backward-compatible with v1, v2, and v3 project files
- **Statistical allocation plan** — explicit `WorkspaceStatisticalAllocationPlan` with
  user-supplied sigma multiplier, per-contributor allocated sigma budgets, and an
  optional combined-sigma budget; identity-bearing; persisted in project files
- **Statistical Reconciliation UI** — sigma multiplier entry, statistical allocation
  plan treeview, Run Statistical Reconciliation; per-contributor compliance treeview;
  Alloc σ / Actual σ / Margin σ / Utilization columns
- All reconciliation and statistical reconciliation results remain **runtime-only**
  (not persisted, cleared on authoritative input changes)
- **Frozen Stage 18 golden demo remains unchanged** — alpha.8 adds new panels
  without touching demo dataset, launchers, or existing workspace flow

---

## Reconciliation Workspace

### Worst-Case Allocation Reconciliation (Stage 19B)

`ToleranceWorkspaceController.run_reconciliation()` and `WorkspaceSession.run_reconciliation()`
delegate to the Stage 15I `reconcile_allocation()` engine.

**Behavior:**
- Requires `allocation_plan` to be set; fail-closed otherwise
- Requires at least one contributor; fail-closed otherwise
- Validates all allocation entry contributor IDs against the current workspace
- Builds `AllocationPlan` and `ToleranceStack` from workspace state; no math duplicated
- Caches result as `_last_reconciliation` (runtime-only, not persisted)

**Result fields surfaced in the UI:**
- Reconciliation status: `ACTUAL_WITHIN_ALLOCATION` / `ACTUAL_AT_ALLOCATION` /
  `ACTUAL_EXCEEDS_ALLOCATION`
- Summary: Budget / Allocated / Actual / Margin compact line
- Per-contributor treeview: Contributor, Allocated Span, Actual Span, Margin,
  Utilization %, Status

**Stale-result clearing:**

| Event | Clears `_last_reconciliation` |
|---|---|
| `_replace_contributors()` | YES — actual spans derive from contributors |
| `set_allocation_plan()` | YES — allocated spans derive from the plan |
| `from_state()` (open project) | YES — all runtime state cleared at persistence boundary |

Specification changes do not clear reconciliation (specification does not affect
actual vs allocated comparison).

---

## Statistical Reconciliation / Workspace v4

### Workspace Schema v4 (Stage 19D)

`WorkspaceState` gains `statistical_allocation_plan: WorkspaceStatisticalAllocationPlan | None`.

Schema version constants:

| Constant | Value |
|---|---|
| v1 | `origlyph.tolerance.workspace.v1` |
| v2 | `origlyph.tolerance.workspace.v2` |
| v3 | `origlyph.tolerance.workspace.v3` |
| v4 | `origlyph.tolerance.workspace.v4` |

Schema v4 is selected automatically when `set_statistical_allocation_plan()` is
called with a non-None plan. No downgrade occurs when the plan is subsequently
cleared — v4 persists once reached, consistent with the v3/v2 precedents.

### `WorkspaceStatisticalAllocationPlan`

Workspace-layer type (not a Stage 15 engine type). Fields:

| Field | Type | Constraint |
|---|---|---|
| `sigma_multiplier` | `float` | strictly positive, finite |
| `entries` | `tuple[WorkspaceStatisticalAllocationEntry, ...]` | no duplicate contributor IDs |
| `allowed_combined_sigma` | `float \| None` | strictly positive when present |

`WorkspaceStatisticalAllocationEntry` fields: `contributor_id` (str), `allocated_sigma`
(float, non-negative).

Both types implement `as_dict()` for JSON persistence. Stage 15 engine types
(`StatisticalAllocationPlan`, `StatisticalAllocation`) are constructed at call time
inside `run_statistical_reconciliation()` and do not appear in workspace persistence.

### Statistical Reconciliation Controller (`run_statistical_reconciliation()`)

Delegates to Stage 15J `reconcile_statistical_allocation(stack, plan, correlations=None)`.

**Behavior:**
- Requires `statistical_allocation_plan` to be set; fail-closed otherwise
- Requires at least one contributor; fail-closed otherwise
- Validates all entry contributor IDs against the current workspace
- V1 correlation model: `correlations=None` (all contributors independent; no
  correlation modeling in this release)
- Caches result as `_last_statistical_reconciliation` (runtime-only, not persisted)
- Propagates `InvalidStatisticalAllocationError` from Stage 15 on plan validity failure

**Result fields surfaced in the UI:**
- Status: overall allocation plan status
- Summary: k / Alloc σ / Actual σ / Margin compact line
- Per-contributor treeview: Contributor, Alloc σ, Actual σ, Margin σ, Utiliz. %, Status

**Stale-result clearing:**

| Event | Clears `_last_statistical_reconciliation` |
|---|---|
| `_replace_contributors()` | YES — actual sigmas derive from contributors |
| `set_statistical_allocation_plan()` | YES — allocated sigmas derive from the plan |
| `from_state()` (open project) | YES — all runtime state cleared at persistence boundary |

### Statistical Allocation Plan Session Layer

`WorkspaceSession` exposes transient string fields for the UI editor:
`stat_sigma_multiplier`, `stat_allocation_budget`, `_stat_allocation_sigmas`.

`sync_statistical_allocation_plan()` parses all editor fields, validates, and
calls `set_statistical_allocation_plan()`. Fail-closed on blank/invalid multiplier
or blank/invalid sigma for any contributor.

`load_statistical_allocation_plan_fields()` populates transient fields from the
authoritative plan on open-project or initial construction.

---

## Backward Compatibility

| Schema version | Load support | Notes |
|---|---|---|
| v1 | SUPPORTED | No specification, no allocation plan, no statistical plan |
| v2 | SUPPORTED | Optional specification, no allocation plan |
| v3 | SUPPORTED | Optional specification, optional worst-case allocation plan |
| v4 | SUPPORTED | All optional fields, including statistical allocation plan |
| Unknown future schema | FAIL CLOSED | `InvalidToleranceWorkspaceError` raised immediately |

**Loading behavior:**
- v1 files load with `specification=None`, `allocation_plan=None`,
  `statistical_allocation_plan=None` — no fabrication
- v2 files load with `allocation_plan=None`, `statistical_allocation_plan=None`
- v3 files load with `statistical_allocation_plan=None`
- `_require_exact_keys` strict parsing is used at every schema level; extra or
  missing keys raise an error — no silent field injection

**Schema promotion on mutation (non-breaking):**
- `set_specification()` promotes v1 → v2 (preserves v3/v4)
- `set_allocation_plan()` promotes v1/v2 → v3 (preserves v4)
- `set_statistical_allocation_plan()` promotes any version → v4
- No downgrade occurs in any mutation path

---

## Persistence & Project Identity

**Authoritative state (identity-bearing, persisted):**
- `WorkspaceState`: chain name, analysis mode, contributors, specification,
  allocation plan, statistical allocation plan
- Configuration fingerprint covers all of the above
- Any change to `sigma_multiplier`, `allowed_combined_sigma`, entry membership,
  or any `allocated_sigma` rotates the fingerprint and project identity

**Runtime-derived state (not persisted, not identity-bearing):**
- `last_result`, `last_decision`, `last_sensitivity`, `last_budget`
- `last_allocation_validation`
- `last_reconciliation`
- `last_statistical_reconciliation`

`from_state()` (called by `open_project()`) sets all runtime caches to `None`
unconditionally. Save/open restores authoritative plans; it never restores
reconciliation results.

---

## UI / Workflow

The workspace now exposes the following sections in scroll order:

| Row | Section |
|---|---|
| 0 | Project context (chain name, mode) |
| 1 | Specification limits |
| 2 | Tolerance chain editor |
| 3 | Analysis control |
| 4 | Results |
| 5 | Decision |
| 6 | Sensitivity |
| 7 | Budget |
| 8 | Allocation Plan |
| 9 | Allocation Validation Result |
| 10 | Reconciliation *(new in alpha.8)* |
| 11 | *(reserved)* |
| 12 | Statistical Allocation Plan *(new in alpha.8)* |
| 13 | Statistical Reconciliation *(new in alpha.8)* |
| 14 | Project File |

**Complete supported user flow:**

```
Create / Open Project
→ Define tolerance chain
→ Configure specification
→ Run analysis (worst-case or RSS statistical)
→ Evaluate decision
→ Inspect sensitivity
→ Inspect budget
→ Create allocation plan
→ Apply / Validate allocation
→ Run Reconciliation  ← new in alpha.8
→ Create statistical allocation plan (sigma multiplier + per-contributor σ)
→ Apply Statistical Plan                    ← new in alpha.8
→ Run Statistical Reconciliation            ← new in alpha.8
→ Save / Open project (v4 round-trip)       ← new in alpha.8
```

---

## Engineering Authority & Safety

- All reconciliation computation is delegated to Stage 15 deterministic engines:
  - Worst-case reconciliation → `reconcile_allocation()` (Stage 15I)
  - Statistical reconciliation → `reconcile_statistical_allocation()` (Stage 15J)
- No engineering mathematics are duplicated in the workspace controller, session,
  or view layer.
- The product does **not** perform automatic allocation optimization. All allocation
  values (spans and sigmas) are user-supplied explicitly.
- No autonomous engineering decisions are generated.
- Reconciliation status is read from engine result fields only; no UI-side status
  inference occurs.
- Fail-closed throughout: missing plan, missing contributors, invalid input fields,
  and unknown contributor IDs all raise `InvalidToleranceWorkspaceError` with an
  explicit message.
- `clear_allocation_plan()` and `clear_statistical_allocation_plan()` are explicit
  user actions; there is no implicit plan reset.

---

## Testing / Quality

Quality gates run against commit `4aa573e9ba43a7352f90a6eaa359e328e7cbf194`
(Stage 19D) before release preparation:

| Suite | Result |
|---|---|
| Project tests | 26 passed |
| Tolerance tests | 1219 passed |
| Full suite | 1779 passed |
| Ruff | PASS |
| Pyright | 0 errors, 0 warnings |
| `git diff --check` | PASS |

Stage 19E release readiness assessment concluded:

```
FINAL_DECISION: ALPHA8_RELEASE_READY
```

---

## Known Limitations

- **No allocation plan generation or optimization.** Allocation plans (worst-case
  and statistical) must be constructed manually. No auto-balance, optimal-span
  calculation, or constraint-based generation is implemented.
- **No statistical budget surface.** RSS statistical budget analysis requires a
  separate allowed-span input not yet represented in the workspace specification.
  Running budget in RSS mode raises `InvalidToleranceWorkspaceError` (documented,
  deferred).
- **Statistical reconciliation V1: no correlation modeling.** The reconciliation
  engine call uses `correlations=None` (all contributors independent). Correlated
  RSS reconciliation is deferred to a future stage.
- **Current golden demo remains the Stage 18 frozen baseline.** The customer demo
  (`examples/tolerance_workspace_demo.py`, launchers, runbook) uses the Stage 18D
  frozen dataset and does not yet expose Stage 19 reconciliation capabilities. A
  new demo validation cycle is required before a Stage 19 customer demo baseline
  can be established.
- **No audit/governance UI.** Stage 15 audit, evidence, change-impact,
  approval-readiness, and acceptance/closure engines are available but have no
  workspace UI surface yet.
- **No STEP/B-Rep/full GD&T authoring.** CAD ingestion remains ASCII/binary STL
  only. Full GD&T authoring and multidimensional tolerance simulation remain future
  work.
- Allocation validation continues to use the worst-case stack regardless of workspace
  analysis mode (consistent with the Stage 15H engine interface).

---

## Upgrade Notes

- **v1/v2/v3 project files load without modification.** No migration step required.
- **New workspace features (reconciliation, statistical allocation plan) are
  opt-in.** Existing projects that do not use these features are unaffected.
- **Saving a project that has a statistical allocation plan writes schema v4.**
  The resulting file cannot be opened by alpha.7 or earlier (v4 is not recognized
  by older versions). Projects without a statistical allocation plan continue to
  save as v3 (or lower) and remain compatible with alpha.7.
- The golden demo baseline is unchanged. Existing demo launchers and runbooks
  remain valid.

---

## Previous Release

`v0.4.0-alpha.7` — Specification-aware workspace; decision surface; sensitivity
and budget UI; allocation plan editor; allocation validation; workspace schema v3;
Stage 15 engineering authority.
