# Origlyph AI v0.4.0-alpha.9

Release date: 2026-10-30

## Overview

v0.4.0-alpha.9 completes the **Stage 20 governance chain workspace surface**: a full
end-to-end deterministic engineering governance workflow built on top of the Stage 15
pure-functional backends.  Every governance step from tolerance analysis through
acceptance closure is now exposed through the `ToleranceWorkspaceController`,
`WorkspaceSession`, and `ToleranceWorkspaceView` layers.

No engineering formulas, audit hash logic, change-impact logic, or acceptance logic
are implemented in the workspace layer.  All engineering authority resides exclusively
in the Stage 15 backends.

---

## New Features in Stage 20 (since v0.4.0-alpha.8)

### Decision Evidence + Explanation Workspace Surface (Stage 20B)

- `run_decision_evidence()` delegates to Stage 15L
  (`build_decision_evidence` / `explain_tolerance_decision`).
- Exposes `last_evidence` and `last_explanation` on the controller and session.
- UI frame at row 16: "Decision Evidence".

### Decision Report Workspace Surface (Stage 20C)

- `run_decision_report()` delegates to Stage 15M (`build_decision_report`).
- Requires `_last_decision`, `_last_evidence`, and `_last_explanation` as
  preconditions; fails closed otherwise.
- UI frame at row 17: "Decision Report".

### Audit Integrity + Audit Package Surface (Stage 20D)

- `run_audit_integrity()` delegates to Stage 15N
  (`validate_decision_report_integrity`).
- `run_audit_package()` delegates to Stage 15O (`build_decision_audit_package`).
- Both require `_last_decision_report` as precondition.
- UI frames at rows 18–19.

### Audit Package Comparison + Change Impact Surface (Stage 20E)

- `load_comparison_audit_package(path)` loads a previously exported audit package
  from a JSON file for diff comparison.
- `run_audit_comparison()` delegates to Stage 15P
  (`compare_decision_audit_packages`).
- `run_change_impact()` delegates to Stage 15Q (`assess_audit_change_impact`).
- Requires `_last_audit_package` and `_comparison_audit_package`.
- UI frames at rows 19–20.

### Change Disposition + Approval Readiness Surface (Stage 20F)

- `run_change_disposition()` delegates to Stage 15R
  (`determine_audit_change_disposition`).
- `run_approval_readiness()` delegates to Stage 15S
  (`evaluate_audit_approval_readiness`).
- Requires `_last_change_impact` → `_last_change_disposition` → readiness.
- UI frames at rows 21–22.

### Workspace Schema v5 + Persisted Acceptance Inputs (Stage 20G.2)

- `WorkspaceAcceptanceState` is the only new persisted artifact in v5:
  `decision`, `authority_reference`, `decision_reference`, `handoff_id`.
- Additive schema version upgrade; v1–v4 projects load cleanly with no
  fabricated acceptance state.
- `configuration_fingerprint()` rotates when acceptance state changes.
- `set_acceptance_state()` clears downstream record, verification, and closure.

### Governed Acceptance Handoff + Acceptance Record Surface (Stage 20G.3)

- `run_acceptance_handoff()` delegates to Stage 15T
  (`build_audit_acceptance_handoff`).  Requires full change governance chain as
  precondition.
- `run_acceptance_record()` delegates to Stage 15U
  (`validate_audit_acceptance_record`).  Requires handoff and persisted
  `WorkspaceAcceptanceState` with matching `handoff_id`.
- Session provides UI-friendly text properties for status and detail display.
- UI frames at rows 20–21.

### Acceptance Verification + Acceptance Closure Manifest Surface (Stage 20H)

- `run_acceptance_verification()` delegates to Stage 15V
  (`build_acceptance_record_verification_envelope`).
- Produces an `AuditAcceptanceVerificationEnvelope` with `status =
  VERIFIED_BINDING` and four verification facts:
  `HANDOFF_FINGERPRINT_MATCH`, `ACCEPTANCE_RECORD_FINGERPRINT_MATCH`,
  `HANDOFF_BINDING_MATCH`, `REFERENCE_CONTENT_PRESERVED`.
- `run_acceptance_closure()` delegates to Stage 15W
  (`build_acceptance_closure_manifest`).
- Produces an `AuditAcceptanceClosureManifest` with `status = COMPLETE` and an
  `AuditAcceptanceClosureReference` linking all three chain artifacts.
- Both methods fail closed without their required preconditions.
- UI frames at rows 22–23.

---

## Architecture Properties

### Deterministic Backend Authority

All Stage 15 backends are pure functions.  Given identical inputs they always produce
identical outputs.  `envelope_id` and `closure_id` are SHA-256 integrity fingerprints
of the canonical chain state — the same inputs always hash to the same value.

### Persistence and Identity Boundaries

| Artifact | Classification | Persisted |
|---|---|---|
| Workspace configuration (contributors, chain, mode) | Authoritative input | Yes (v1+) |
| Specification, allocation plans | Authoritative input | Yes (v2–v4) |
| `WorkspaceAcceptanceState` | Authoritative input | Yes (v5) |
| Analysis result, decision, evidence, report | Runtime-derived | No |
| Audit package, comparison, change impact | Runtime-derived | No |
| Acceptance handoff, record | Runtime-derived | No |
| Acceptance verification, closure | Runtime-derived | No |

Runtime-derived artifacts must be explicitly regenerated after a project is opened.
No automatic chain reconstruction occurs on project load.

### Workspace Schema Backward Compatibility

| Schema | Key additions |
|---|---|
| v1 | chain_name, analysis_mode, contributors |
| v2 | specification |
| v3 | allocation_plan |
| v4 | statistical_allocation_plan |
| v5 | acceptance_state |

Unknown schema versions fail closed.

### Stale Clearing

Every upstream mutation cascades downstream: any change to contributors,
specification, or mode clears the entire governance chain through acceptance
closure.  Acceptance state changes clear the record, verification, and closure.
No stale derived artifact survives an upstream change.

---

## Quality Gates (at release)

| Gate | Result | Count |
|---|---|---|
| Project tests | PASS | 26 / 26 |
| Tolerance tests | PASS | 1643 / 1643 |
| Full suite | PASS | 2203 / 2203 |
| Ruff | PASS | — |
| Pyright | PASS | 0 errors, 0 warnings |
| diff --check | PASS | — |

---

## Non-Blocking Limitations

The following are known limitations by design.  They do not represent regressions
or unintended gaps.

1. **No digital signatures or cryptographic non-repudiation.**
   `envelope_id` and `closure_id` are deterministic SHA-256 integrity fingerprints,
   not cryptographic signatures.

2. **No authenticated actor identity.**
   `authority_reference` and `decision_reference` are free-text governance
   references.  The system does not verify that they correspond to authenticated
   identities or real governance records.  They are governance references only,
   not cryptographically verified identities.

3. **No regulatory certification or compliance framework.**
   Acceptance Verification and Acceptance Closure are deterministic governance
   artifacts.  They do not provide actor authentication, digital signatures,
   authorization proof, regulatory certification, or release authorization.

4. **Runtime-derived governance chain must be regenerated after project open.**
   Acceptance handoff, record, verification, and closure are all runtime-only
   and are cleared to `None` on project load.

5. **No export formats.**
   Governance artifacts are Python objects or JSON strings only.
   No PDF, HTML, or DOCX export is provided.

6. **RSS statistical budget surface remains deferred.**
   `run_budget()` raises `InvalidToleranceWorkspaceError` for RSS statistical mode.
   Worst-case budget only.

7. **Audit comparison requires external comparison package file.**
   No built-in package library; the user must supply a previously exported
   audit package JSON file via `load_comparison_audit_package(path)`.

8. **Acceptance references are not cryptographically verified.**
   The workspace validates that `authority_reference` and `decision_reference`
   are non-empty canonical strings.  No external authority system is contacted.

9. **Project file is not file-level tamper-evident.**
   The project file is standard JSON.  It is not signed, encrypted, or
   cryptographically protected at the file level.

---

## Upgrade Notes

- Version bump only from `0.4.0a8` to `0.4.0a9`.
- No schema migration required.  v1–v4 projects open without modification.
- No breaking API changes.
