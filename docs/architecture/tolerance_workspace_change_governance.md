# Tolerance Workspace — Change Disposition & Approval Readiness

## Purpose

The Change Governance surface exposes the Stage 15R (change disposition) and Stage 15S
(approval readiness) capabilities through the tolerance workspace UI. It allows an engineer
to determine the required governance action for a detected change impact, and to assess
whether the change is ready to enter an external approval process, without leaving the
workspace.

**Change disposition and approval readiness are deterministic, runtime-derived
classifications from Stage 15R and Stage 15S respectively. Neither represents approval,
certification, governed acceptance, or autonomous engineering judgment.**

## Explicit Workflow

1. Engineer completes the full change impact workflow: audit package → load comparison →
   compare → change impact (`run_change_impact()`).
2. Engineer clicks **Determine Change Disposition** → `run_change_disposition()` → Stage 15R
   disposition result cached as `_last_change_disposition`.
3. Engineer clicks **Evaluate Approval Readiness** → `run_approval_readiness()` → Stage 15S
   readiness result cached as `_last_approval_readiness`.

## Stage 15 Authority

Change disposition is produced exclusively by the Stage 15R engine function:

```
determine_audit_change_disposition(
    impact_result: AuditChangeImpactResult,
) → AuditChangeDispositionResult
```

Approval readiness is produced exclusively by the Stage 15S engine function:

```
evaluate_audit_approval_readiness(
    disposition_result: AuditChangeDispositionResult,
) → AuditApprovalReadinessResult
```

The workspace controller, session, and UI are consumers only. They do not recompute
disposition, duplicate approval logic, fabricate readiness classifications, or reinterpret
governance meaning.

## User Input Contract

Neither `run_change_disposition()` nor `run_approval_readiness()` accepts any user input.
Both are fully deterministic from their upstream runtime inputs. No user-specified
parameters are consulted. No workspace configuration is read beyond what is already encoded
in the cached impact and disposition results.

## Prerequisites

`run_change_disposition()` requires:

- `_last_change_impact` must not be `None` (raised: "Evaluate Change Impact first.")

`run_approval_readiness()` requires:

- `_last_change_disposition` must not be `None` (raised: "Determine Change Disposition first.")

No other preconditions are checked; all calls are fail-closed.

## Runtime-Only State

The following fields are **never persisted** to the workspace schema or project file:

| Field | Set by | Cleared by |
|---|---|---|
| `_last_change_disposition` | `run_change_disposition()` | Any upstream change (see Stale Clearing) |
| `_last_approval_readiness` | `run_approval_readiness()` | Any upstream change or new disposition |

- `save_project` / `open_project`: governance state not saved; restored controller has both
  fields as `None`.
- `from_state`: governance state not included; restored controller clears both.
- Governance must be re-run after every session load.

## Stale Clearing

`_last_change_disposition` and `_last_approval_readiness` are cleared (set to `None`)
whenever any upstream input becomes stale:

- `set_chain_name()`
- `set_analysis_mode()`
- `set_specification()`
- `run_analysis()`
- `evaluate_decision()`
- `run_decision_evidence()`
- `run_decision_report()`
- `run_audit_integrity()`
- `run_audit_package()`
- `load_comparison_audit_package()`
- `run_audit_comparison()`
- `run_change_impact()` (new impact replaces old input)
- `_replace_contributors()`
- `from_state()`

`_last_approval_readiness` is additionally cleared when:
- `run_change_disposition()` generates a new disposition result.

## Persistence Boundary

```
WorkspaceProject (persisted JSON)
  └── chain_name, analysis_mode, contributors, specification
  └── allocation_plan, statistical_allocation_plan
  ← last_result, last_decision, last_sensitivity, last_budget,
     last_reconciliation, last_statistical_reconciliation  (runtime)
  ← last_evidence, last_explanation  (runtime — Stage 20B)
  ← last_decision_report  (runtime — Stage 20C)
  ← last_audit_integrity, last_audit_package  (runtime — Stage 20D)
  ← comparison_audit_package, last_audit_comparison, last_change_impact
     (runtime — Stage 20E)
  ← last_change_disposition, last_approval_readiness  (runtime — Stage 20F)
```

## Identity Boundary

`run_change_disposition()` and `run_approval_readiness()` do not touch
`configuration_fingerprint()` (which hashes `WorkspaceState` only). No schema version
increment. No governance fields added to workspace identity.

## Feature Isolation

The governance surface is fully isolated. Running change disposition or approval readiness
has no side-effects on any other workspace feature. Analysis, decision, evidence, report,
audit integrity, audit package, comparison, and change impact are all unaffected.

## UI Presentation

**Change Disposition** section (workspace row 18):
- **Determine Change Disposition** button: calls `run_change_disposition()`.
- **Status** label: disposition value (ACCEPT / ACCEPT_WITH_TRACEABILITY /
  ENGINEERING_REVIEW_REQUIRED / REVALIDATION_REQUIRED / REPLAY_REQUIRED / BLOCKED) or
  "NOT DETERMINED".
- **Reasons** treeview: columns disposition, code, impact, impact_reason, change_code.
  Populated from `change_disposition_reasons_rows()`.

**Approval Readiness** section (workspace row 19):
- **Evaluate Approval Readiness** button: calls `run_approval_readiness()`.
- **Status** label: readiness status (READY / ACTION_REQUIRED / BLOCKED) or
  "NOT EVALUATED".
- **Reasons** treeview: columns status, code, source_disposition, source_code.
  Populated from `approval_readiness_reasons_rows()`.

## Non-Goals

The governance surface explicitly does NOT:

- Implement governed acceptance or acceptance verification.
- Implement approval workflow or approval state tracking.
- Grant, record, or certify approval.
- Export disposition or readiness results to HTML or PDF.
- Add AI-generated governance commentary.
- Make autonomous engineering decisions.
- Persist governance state to disk.
- Serve as the engineering authority for tolerance calculations.
- Auto-generate missing prerequisite objects.
- Independently classify or score change impact.
