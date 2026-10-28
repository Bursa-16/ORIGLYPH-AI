# Tolerance Workspace — Audit Integrity & Audit Package

## Purpose

The Audit Package surface exposes the Stage 15N audit integrity validation and Stage 15O
audit package capabilities through the tolerance workspace UI. It allows an engineer to
produce a deterministic, structurally consistent audit record of a completed tolerance
decision without leaving the workspace.

## Explicit Workflow

1. Engineer configures contributors and specification.
2. Engineer runs Analysis (`run_analysis`).
3. Engineer runs Decision (`evaluate_decision`).
4. Engineer clicks **Generate Evidence** → Stage 15L evidence + explanation cached.
5. Engineer clicks **Generate Decision Report** → Stage 15M report cached.
6. Engineer clicks **Generate Audit Package** in the workspace UI.
7. The workspace calls `run_audit_package()` on the controller.
8. If `_last_audit_integrity` is already cached, the controller passes it to
   `build_decision_audit_package`; otherwise the backend computes it internally.
9. The audit package is cached as runtime-only state on the controller.
10. The UI presents: replayability status, integrity status, package ID prefix, integrity
    violations table, and replay manifest table.

Optionally, the engineer may call **run_audit_integrity()** first to inspect structural
integrity before building the full package.

## Stage 15 Authority

Audit integrity is produced exclusively by the Stage 15N engine function:

```
validate_decision_report_integrity(
    report: ToleranceDecisionReport,
) → AuditIntegrityResult
```

The audit package is produced exclusively by the Stage 15O engine function:

```
build_decision_audit_package(
    report: ToleranceDecisionReport,
    integrity_result: AuditIntegrityResult | None = None,
    provenance: DecisionProvenance | None = None,
) → ToleranceDecisionAuditPackage
```

The workspace controller, session, and UI are consumers only. They do not recompute
fingerprints, duplicate hashing logic, fabricate integrity status, or reinterpret
audit meaning.

**Audit integrity verifies deterministic package consistency. It is not regulatory
certification, approval, or autonomous engineering judgment.**

## Prerequisites

`run_audit_integrity()` and `run_audit_package()` both require:

- `_last_decision_report` must not be `None` (raised: "Generate Decision Report first.")

No other preconditions are checked; both calls are fail-closed if the report is absent.
Neither method auto-generates missing prerequisites.

## Integrity Contract

`AuditIntegrityResult` fields presented:

| Field | Meaning |
|---|---|
| `status` | `VALID`, `INCOMPLETE`, or `INVALID` |
| `violations` | Tuple of `AuditIntegrityViolation` items |

Each `AuditIntegrityViolation` exposes: `code`, `severity`, `scope`, `subject`, `detail`.

An integrity `VALID` result means the decision package is structurally consistent. It does
NOT mean the engineering decision is PASS.

## Audit Package Contract

`ToleranceDecisionAuditPackage` fields presented:

| Field | Meaning |
|---|---|
| `audit_schema_version` | `"origlyph.tolerance.audit_package.v1"` |
| `package_id` | SHA-256 fingerprint of the full package identity (64 hex chars) |
| `replayability_status` | `REPLAYABLE`, `NOT_REPLAYABLE`, or `INCOMPLETE` |
| `integrity_result` | Embedded `AuditIntegrityResult` |
| `replay_manifest` | `DecisionReplayManifest` |

## Replay Manifest Behavior

`DecisionReplayManifest` is an intrinsic part of every `ToleranceDecisionAuditPackage`.
It is produced automatically by Stage 15O inside `build_decision_audit_package`. The
workspace does not need a separate workflow to produce it.

Fields presented from the manifest:

| Field | Meaning |
|---|---|
| `package_id` | Package identity fingerprint |
| `decision_id` | Decision identity fingerprint |
| `integrity_status` | Matches embedded integrity result status |
| `replayability_status` | Structural replay readiness |
| `is_complete` | Whether manifest covers all required fields |
| `equality_tolerance` | Numeric equality threshold used in report |
| `sigma_multiplier` | RSS sigma multiplier (if applicable) |
| `input_fingerprint` | SHA-256 of the deterministic input surface |
| `report_fingerprint` | SHA-256 of the full report payload |

## Runtime-Only Nature

Audit integrity and audit package are **never persisted** to the workspace schema or
project file. They are ephemeral runtime snapshots derived from `_last_decision_report`.

- `save_project` / `open_project`: audit state not saved; restored controller has
  `last_audit_integrity = None` and `last_audit_package = None`.
- `from_state`: audit state not included; restored controller clears both.
- Audit must be regenerated after every session load.

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
```

## Identity Boundary

`run_audit_package()` does not touch `configuration_fingerprint()` (which hashes
`WorkspaceState` only). No schema version increment. No audit fields added to workspace
identity.

## Stale Clearing

Both `_last_audit_integrity` and `_last_audit_package` are cleared (set to `None`)
whenever any upstream artifact becomes stale:

- `set_chain_name()`
- `set_analysis_mode()`
- `set_specification()`
- `run_analysis()`
- `evaluate_decision()`
- `run_decision_evidence()` (evidence regeneration → report stale → audit stale)
- `run_decision_report()` (new report → old audit stale)
- `run_audit_integrity()` (new integrity → old package stale; `_last_audit_package` only)
- `_replace_contributors()`
- `from_state()`

No automatic regeneration.

## Feature Isolation

The audit surface is fully isolated. Generating audit integrity or an audit package has
no side-effects on any other workspace feature. All other features (sensitivity, budget,
allocation, reconciliation, statistical reconciliation) are unaffected by calling
`run_audit_integrity()` or `run_audit_package()`.

## UI Presentation

The Audit Package section appears at workspace row 15 (between Decision Report at row 14
and Project File at row 16) as a `ttk.Labelframe` titled **"Audit Package"**.

- **Generate Audit Package** button: calls `run_audit_package()` and refreshes the section.
- **Integrity status label**: shows `audit_integrity_status_text` — `"NOT GENERATED"` or
  the integrity status value in uppercase once generated.
- **Replayability status label**: shows `audit_package_status_text`.
- **Package ID label**: shows first 16 hex chars of `package_id` (truncated for display).
- **Violations table**: `ttk.Treeview` with columns: Severity, Code, Scope, Subject,
  Detail. Empty when no violations.
- **Manifest table**: `ttk.Treeview` with columns: Manifest Field, Value. Populated from
  `audit_manifest_rows()`.

## Non-Goals

The audit surface explicitly does NOT:

- Implement audit package comparison or change-impact workflow.
- Implement change disposition or approval readiness assessment.
- Implement governed acceptance or acceptance verification.
- Implement a closure manifest UI.
- Export audit package to HTML or PDF.
- Add AI-generated audit explanation or commentary.
- Certify, approve, or reject an engineering design.
- Persist the audit package to disk.
- Serve as the engineering authority for tolerance calculations.
- Auto-generate missing prerequisite objects.
