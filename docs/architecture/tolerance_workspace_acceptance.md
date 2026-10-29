# Tolerance Workspace — Governed Acceptance + Acceptance Record Surface (Stage 20G.3)

## Overview

Stage 20G.3 implements the full vertical slice from Approval Readiness through
Acceptance Record in the Tolerance Workspace.  The slice covers:

1. **Prepare Acceptance Handoff** — assembles the runtime `AuditAcceptanceHandoffPackage`
   from the live governance chain (Stage 15T).
2. **Governed Acceptance inputs** — user enters `decision`, `authority_reference`, and
   `decision_reference`; these are validated and persisted as `WorkspaceAcceptanceState`
   (Schema v5, Stage 20G.2).
3. **Build Acceptance Record** — reconstructs a `ValidatedAuditAcceptanceRecord` from
   the persisted inputs and the live handoff, using `validate_audit_acceptance_record`
   (Stage 15U).

## Authority Model

| Artifact | Classification | Persisted |
|---|---|---|
| `AuditAcceptanceHandoffPackage` | Runtime-derived | No |
| `WorkspaceAcceptanceState` | Authoritative inputs + identity reference | Yes (v5) |
| `AuditAcceptanceRecord` | Input type for Stage 15U | No |
| `ValidatedAuditAcceptanceRecord` | Runtime-derived | No |

The workspace persists only `WorkspaceAcceptanceState` — the minimum set required to
reconstruct the validated record after project reload, without loss of authoritative
governance data.

## Controller Methods

### `run_acceptance_handoff() → AuditAcceptanceHandoffPackage`

Requires: `_last_audit_comparison`, `_last_change_impact`, `_last_change_disposition`,
`_last_approval_readiness` — all non-None.

Calls `build_audit_acceptance_handoff(comparison, impact, disposition, readiness)`.
Stores the result in `_last_acceptance_handoff`.  Clears `_last_acceptance_record`.

### `run_acceptance_record() → ValidatedAuditAcceptanceRecord`

Requires: `_last_acceptance_handoff` and `controller.acceptance_state` — both non-None.

Asserts `acceptance_state.handoff_id == handoff.handoff_id`.  If they differ, raises
`InvalidToleranceWorkspaceError` with an explicit incompatibility message.  The
persisted acceptance state is NOT automatically cleared on mismatch — the user must
explicitly act.

Reconstructs `AuditAcceptanceRecord` from the persisted fields and calls
`validate_audit_acceptance_record(handoff, record)`.  Stores the result in
`_last_acceptance_record`.

## Session Methods

### `prepare_acceptance_handoff() → AuditAcceptanceHandoffPackage`

Delegates to `controller.run_acceptance_handoff()`.

### `sync_acceptance_state() → None`

Parses the session's transient string fields (`acceptance_decision`,
`acceptance_authority_reference`, `acceptance_decision_reference`).  Validates:

- `acceptance_decision` is non-empty and a valid `AuditAcceptanceDecision` value.
- `authority_reference` is non-empty, no leading/trailing whitespace.
- `decision_reference` is non-empty, no leading/trailing whitespace.
- A live `_last_acceptance_handoff` is present (supplies the `handoff_id`).

On success, constructs `WorkspaceAcceptanceState` with the current `handoff_id` and
calls `controller.set_acceptance_state(state)`.

### `clear_acceptance_state() → None`

Delegates to `controller.clear_acceptance_state()`.  Resets transient string fields to
empty strings.

### `build_acceptance_record() → ValidatedAuditAcceptanceRecord`

Delegates to `controller.run_acceptance_record()`.

### `load_acceptance_fields() → None`

Reads `controller.acceptance_state` and populates the session's transient string fields.
Called in `WorkspaceSession.__init__` and in `_open_impl()` after project load.  When
`acceptance_state` is `None`, all three fields are set to `""`.

## Stale Clearing Chain

Any upstream change clears both `_last_acceptance_handoff` and `_last_acceptance_record`.
This preserves the Stage 20F pattern: derived runtime artifacts are cleared when the
chain that produced them is invalidated.

`set_acceptance_state` clears only `_last_acceptance_record` — the handoff is upstream
of the record, not downstream of the inputs, so it is preserved.

The persisted `WorkspaceAcceptanceState` is NEVER automatically cleared when upstream
engineering state changes.  Its clearing requires explicit user action via
`clear_acceptance_state()` or `set_acceptance_state(None)`.

Incompatibility between the stored acceptance state and the current governance chain is
detected at `run_acceptance_record()` time (handoff_id mismatch), not at upstream
mutation time.

## UI Layout

| Row | Frame |
|---|---|
| 0–7 | Project context, contributors, specification, analysis, decision |
| 8–12 | Allocation plan, validation, reconciliation |
| 13–14 | Statistical allocation plan, reconciliation |
| 15 | Decision Evidence + Explanation |
| 16 | Decision Report |
| 17 | Audit Integrity + Package |
| 18 | Audit Comparison + Change Impact |
| 19 | Change Disposition + Approval Readiness |
| **20** | **Governed Acceptance** ← new (Stage 20G.3) |
| **21** | **Acceptance Record** ← new (Stage 20G.3) |
| **22** | **Project File** (moved from row 20) |

### Governed Acceptance frame (row 20)

- **Prepare Acceptance Handoff** button — runs `prepare_acceptance_handoff()`; shows
  handoff status (e.g. `READY_FOR_GOVERNED_ACCEPTANCE`) and a short detail line
  containing the first 16 hex characters of the `handoff_id`.
- Decision combobox (values from `AuditAcceptanceDecision`).
- Authority Reference entry (free text; the user enters a canonical reference string).
- Decision Reference entry (free text; the user enters a canonical reference string).
- **Save Acceptance Inputs** button — reads the three fields, calls
  `sync_acceptance_state()`; on error the guard displays the message.
- **Clear Acceptance Inputs** button — calls `clear_acceptance_state()`, resets all
  three StringVars.

### Acceptance Record frame (row 21)

- **Build Acceptance Record** button — calls `build_acceptance_record()`.
- Status label (bold): shows `APPROVED`, `REJECTED`, `RETURNED_FOR_ACTION`, or
  `NOT BUILT`.
- Detail label: shows decision, authority, and decision reference on one line.

## Semantic Safety

The UI uses no Approve/Certify/Sign/Release wording.  `authority_reference` is labelled
"Authority Reference" (not "Approver" or "Signatory").  `decision_reference` is labelled
"Decision Reference" (not "Signature" or "Certificate").

Status text for the record uses `APPROVED`/`REJECTED`/`RETURNED_FOR_ACTION` — these are
the exact `AuditAcceptanceDecision` enum values, not invented authorization language.

**Mandatory statement:**

> Persisted acceptance references are governance references only.  They do not provide
> digital signatures, actor authentication, authorization proof, certification, or
> regulatory approval.

## Save / Open Behaviour

On project save: `WorkspaceAcceptanceState` is serialized into the v5 snapshot (see
`tolerance_workspace_acceptance_persistence_v5.md`).  Runtime artifacts
(`_last_acceptance_handoff`, `_last_acceptance_record`) are not serialized.

On project open: `open_project()` restores `WorkspaceAcceptanceState` from the v5
snapshot.  `_open_impl()` calls `load_acceptance_fields()` to populate the session
string fields from the restored state, then calls `_refresh_acceptance()` to update
the StringVar displays.  Runtime artifacts remain `None`; the user must re-run the
governance chain to obtain a live `ValidatedAuditAcceptanceRecord`.

## Non-Goals

This stage does NOT implement:

- Acceptance Verification (Stage 15V)
- Closure Manifest (Stage 15W)
- Digital signatures, PKI, or SSO
- Authentication or authorization of users
- External approval service integration
- AI-generated acceptance decisions
- Automatic handoff reconstruction on project load (the user re-runs the chain)
- Version bump or release
- Changes to the golden demo
