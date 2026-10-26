# Origlyph AI v0.4.0-alpha.7

**Release date:** 2026-10-26
**Package version:** `0.4.0a7`
**Tag:** `v0.4.0-alpha.7`
**Status:** PRE-RELEASE / ALPHA

---

## Highlights

This release completes the tolerance workspace productization arc (Stages 17A–17E-3),
delivering a specification-aware, decision-guided, sensitivity-and-budget-inspectable
interactive tolerance workspace with an explicit allocation plan editor and
allocation validation workflow.

- **Stage 17A** — Workspace specification contract (`WorkspaceSpecification`);
  `allowed_worst_case_span` and `allowed_combined_sigma`; workspace schema v2
- **Stage 17B** — Deterministic tolerance decision surface; `evaluate_decision`
  wired to specification; PASS/FAIL/INCONCLUSIVE states; workspace schema v2
  decision caching
- **Stage 17C** — Tolerance sensitivity UI; worst-case and RSS sensitivity
  treeview; `WorstCaseSensitivityResult` / `StatisticalSensitivityResult`
  presentation
- **Stage 17D** — Tolerance budget UI; worst-case budget surface; budget status /
  summary / per-contributor treeview
- **Stage 17E-1** — Workspace allocation plan contract v3;
  `WorkspaceAllocationPlan` / `WorkspaceAllocationEntry`; `set_allocation_plan` /
  `clear_allocation_plan`; workspace schema v3; allocation plan persistence and
  project-identity integration
- **Stage 17E-2** — Allocation validation controller and session;
  `validate_allocation()` delegates to Stage 15 engine; contributor-binding
  validation; stale-result clearing on plan and contributor changes; session
  presentation helpers (`allocation_validation_status_text`,
  `allocation_validation_summary_text`, `allocation_validation_rows()`)
- **Stage 17E-3** — Allocation Plan editor Tkinter UI section; explicit **Apply
  Allocation Plan** and **Validate Allocation** actions; fail-closed input
  parsing; contributor binding by stable `contributor_id`; transient session
  fields for budget and per-contributor span strings; Allocation Validation
  Result treeview section

---

## Supported User Flow

```
Create / Open Project
→ Define tolerance chain (add / edit / remove contributors)
→ Configure specification (allowed WC span, allowed σ)
→ Run analysis (worst-case or RSS statistical)
→ Evaluate decision (PASS / FAIL / INCONCLUSIVE)
→ Inspect sensitivity (per-contributor impact and share)
→ Inspect budget (per-contributor span and budget utilization)
→ Create allocation plan (budget + per-contributor allocated span)
→ Apply Allocation Plan (explicit action; writes to authoritative state)
→ Validate Allocation (explicit action; delegates to Stage 15 engine)
→ Save / Open project (full workspace v3 round-trip)
```

---

## Engineering Integrity

- Stage 15 mathematical engines remain the sole authority for all tolerance
  analysis, decision evaluation, sensitivity, budget, and allocation validation.
  No engineering mathematics are duplicated in the workspace UI or session layer.
- Workspace schema v1 and v2 projects remain fully loadable (backward
  compatibility preserved). Schema v1 → no specification, no allocation plan.
  Schema v2 → optional specification, no allocation plan. Schema v3 → optional
  specification, optional allocation plan. Unknown schema versions fail closed.
- `allocation_plan` is authoritative state: persisted in the project file,
  identity-bearing (rotation of the workspace configuration fingerprint), and
  restored exactly on project open.
- Allocation validation results are runtime-derived: not persisted, not
  identity-bearing, cleared automatically when authoritative allocation inputs
  change (plan write, contributor add/edit/remove).
- Fail-closed throughout: blank or invalid budget / span raises
  `InvalidToleranceWorkspaceError`; no implicit zero; no silent rebinding.
- Contributor binding is by stable `contributor_id`, not position. Removed
  contributors are excluded silently from the next sync; new contributors require
  explicit span entry.
- `validate_allocation()` does not mutate `last_result`, `last_decision`,
  `last_sensitivity`, or `last_budget`. Analysis/decision/sensitivity/budget
  actions do not trigger allocation validation or modify `last_allocation_validation`.

---

## Known Limitations

- **No allocation plan generation or optimization.** The allocation plan must be
  constructed manually by the user. No auto-balance, optimal-span calculation, or
  constraint-based generation is implemented.
- **No reconciliation UI.** The Stage 15 `reconcile_allocation` and
  `reconcile_statistical_allocation` engines are available but have no workspace
  UI surface yet (Stage 17F, future work).
- **No audit/governance UI.** The Stage 15 audit, evidence, change-impact,
  approval-readiness, and acceptance/closure engines are available but have no
  workspace UI surface yet.
- **Budget surface: worst-case mode only.** RSS statistical budget requires a
  separate allowed-span input not yet represented in the workspace specification
  (documented in controller; deferred).
- **No STEP/B-Rep/full GD&T authoring.** CAD ingestion remains ASCII/binary STL
  only. Full GD&T authoring and multidimensional tolerance simulation remain
  future work.
- Allocation validation calls the worst-case stack regardless of workspace
  analysis mode. This is consistent with the Stage 15 `validate_allocation`
  engine interface.

---

## Verification

Quality gates run against commit `f236a5db417bada6110666820026ef41a5f7885e`
(Stage 17E-3) before release preparation:

| Suite | Result |
|-------|--------|
| Project tests | 26 passed |
| Tolerance tests | 1086 passed |
| Full suite | 1646 passed |
| Ruff | PASS |
| Pyright | 0 errors, 0 warnings |

Stage 17E-4 integration and release readiness assessment concluded:

```
FINAL_DECISION: ALPHA7_RELEASE_READY
```

---

## Previous Release

`v0.4.0-alpha.6` — Deterministic persisted project model v1; tolerance workspace
foundation v1; workspace schema v2; specification-aware decision, sensitivity,
and budget surfaces.
