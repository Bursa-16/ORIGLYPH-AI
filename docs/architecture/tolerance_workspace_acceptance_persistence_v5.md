# Tolerance Workspace — Acceptance Persistence Contract (Schema v5)

## Why v5 Exists

Stage 20G.1 identified that the Stage 15U `AuditAcceptanceRecord` contains three
externally supplied, non-re-derivable fields:

- `decision` (`AuditAcceptanceDecision` enum value)
- `authority_reference` (canonical string reference to governing authority)
- `decision_reference` (canonical string reference to decision record)

These fields represent authoritative human-entered governance inputs.  They cannot
be reconstructed from runtime computation.  Without persistence, every project
reload loses the record of who approved or rejected a tolerance chain under what
authority reference.

Workspace v5 adds a `WorkspaceAcceptanceState` field to `WorkspaceState` that
persists exactly the minimum set of fields required to safely reconstruct an
`AuditAcceptanceRecord` after project reload.

## Authoritative Acceptance Fields

Only the minimum required set is persisted:

| Field | Type | Classification |
|---|---|---|
| `decision` | `AuditAcceptanceDecision` enum | AUTHORITATIVE_INPUT |
| `authority_reference` | `str` | AUTHORITATIVE_INPUT |
| `decision_reference` | `str` | AUTHORITATIVE_INPUT |
| `handoff_id` | `str` (SHA-256 hex) | IDENTITY_REFERENCE |

`handoff_id` is included as an identity reference: it is the SHA-256 fingerprint
of the acceptance handoff package that this record was bound to.  It is used at
reconstruction time to detect incompatibility between the stored record and the
current runtime governance chain.

## Schema Shape

```
TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5 = "origlyph.tolerance.workspace.v5"

WorkspaceAcceptanceState (frozen dataclass):
    decision: AuditAcceptanceDecision
    authority_reference: str
    decision_reference: str
    handoff_id: str  (64-char lowercase SHA-256 hex)

WorkspaceState v5:
    {v4 fields} + acceptance_state: WorkspaceAcceptanceState | None
```

Snapshot form (dict):

```json
{
  "schema_version": "origlyph.tolerance.workspace.v5",
  "chain_name": "...",
  "analysis_mode": "...",
  "contributors": [...],
  "specification": {...} | null,
  "allocation_plan": {...} | null,
  "statistical_allocation_plan": {...} | null,
  "acceptance_state": {
    "decision": "approved" | "rejected" | "returned_for_action",
    "authority_reference": "...",
    "decision_reference": "...",
    "handoff_id": "<64 hex chars>"
  } | null
}
```

## Persistence Rules

- **Persisted**: `WorkspaceAcceptanceState` (the four fields above).
- **Not persisted**: `AuditAcceptanceRecord` (the full engine input type).
- **Not persisted**: `AuditAcceptanceHandoffPackage` (runtime-derived from chain).
- **Not persisted**: `ValidatedAuditAcceptanceRecord` (runtime-derived from handoff + record).

The workspace serializer calls `WorkspaceAcceptanceState.as_dict()` and stores the
result under the `"acceptance_state"` key of the v5 snapshot.  The `decision` field
is stored as its string enum value (`"approved"`, `"rejected"`, `"returned_for_action"`).

## Identity Participation

`WorkspaceAcceptanceState` participates fully in workspace identity:

- Any change to `acceptance_state` (set, clear, or modify any field) changes the
  workspace snapshot.
- `workspace_configuration_fingerprint()` is the SHA-256 of the canonical JSON of
  `WorkspaceState.as_dict()`.
- The workspace fingerprint is stored in `project.tolerance_state.configuration_fingerprint`.
- Both the fingerprint and the raw snapshot (in `project.extensions`) feed into
  `project_id`.
- Therefore: any acceptance state change rotates `project_id`.

This is the correct behavior.  Governance inputs are authoritative state; their
fingerprint must be part of project identity.

## V1–V4 Compatibility

The extension follows the exact v1–v4 additive-versioned-extension pattern:

| Schema | acceptance_state |
|---|---|
| v1 | must be `None` |
| v2 | must be `None` |
| v3 | must be `None` |
| v4 | must be `None` |
| v5 | optional (`None` or `WorkspaceAcceptanceState`) |

Loading a v1–v4 snapshot always produces `acceptance_state=None`.  Attempting to
construct a `WorkspaceState` with `acceptance_state` set and a v1/v2/v3/v4 schema
version raises `InvalidToleranceWorkspaceError`.

Unknown future schemas fail closed (unsupported schema error).

**No downgrade**: a v5 workspace remains v5 even if `acceptance_state` is cleared
to `None`, consistent with the v3/v4 precedent for `allocation_plan` and
`statistical_allocation_plan`.

## Save / Open Contract

1. User supplies `decision`, `authority_reference`, `decision_reference`.
2. Caller constructs `WorkspaceAcceptanceState(decision, authority_reference,
   decision_reference, handoff_id)` and calls
   `controller.set_acceptance_state(state)`.
3. Controller upgrades `WorkspaceState` to v5 and stores the acceptance state.
4. `save_project()` serializes the v5 snapshot including `acceptance_state`.
5. `open_project()` / `from_state()` reads the v5 snapshot, dispatches to
   `_workspace_state_v5_from_dict()`, restores all four persisted fields exactly.
6. Runtime governance fields (`_last_acceptance_handoff`, etc.) are `None` after load.

Zero authoritative field loss across save/open round-trips.

## Reconstruction Boundary

On project reload, the workspace carries `acceptance_state` with the persisted
fields, but no live `AuditAcceptanceHandoffPackage` or `AuditAcceptanceRecord`.

To reconstruct a `ValidatedAuditAcceptanceRecord`:

1. Re-run the full governance chain:
   audit package → load comparison → compare → change impact → change disposition
   → approval readiness → `build_audit_acceptance_handoff()`.
2. Assert that the runtime `handoff_id` matches the stored `acceptance_state.handoff_id`.
3. Reconstruct `AuditAcceptanceRecord` from the persisted fields.
4. Call `validate_audit_acceptance_record(handoff_package, record)`.

If the `handoff_id` does not match (upstream engineering state changed since the
record was saved), the implementation must raise `InvalidToleranceWorkspaceError`
with an explicit incompatibility message.  The acceptance state is NOT automatically
cleared.

The full reconstruction workflow is implemented in Stage 20G.3 (not this stage).

## Stale-State Policy

**Runtime derived fields** (`_last_acceptance_handoff`, `_last_validated_acceptance_record`):
Cleared on any upstream change (consistent with the stale-clearing chain from
Stage 20F).  These are not yet implemented in this stage.

**Persisted `acceptance_state` in `WorkspaceState`**: **NOT automatically cleared
when upstream engineering state changes.**  Preservation principle: the user entered
authoritative governance data; clearing it requires explicit user intent via
`clear_acceptance_state()` or `set_acceptance_state(None)`.

Incompatibility with the current governance chain is detected at reconstruction
time (Step 2 above), not at upstream mutation time.

## Security and Identity Limitations

**`authority_reference` is not identity authentication.**
It is a user-supplied canonical string reference to an external authority document
or system.  Origlyph does not verify that the referenced authority exists, that the
referenced person approved, or that the reference is authentic.

**`decision_reference` is not a digital signature.**
It is a user-supplied canonical string reference to an external decision record.
Origlyph does not cryptographically verify its authenticity.

**`handoff_id` is not a cryptographic proof of actor identity.**
It is a deterministic SHA-256 fingerprint of the governance chain inputs.  It proves
chain integrity, not actor identity.

**Mandatory statement:**

> Persisted acceptance references are governance references only.  They do not
> provide digital signatures, actor authentication, authorization proof,
> certification, or regulatory approval.

## Non-Goals

This stage (20G.2) explicitly does NOT implement:

- Full Governed Acceptance UI
- Acceptance Record UI
- Acceptance Verification (Stage 15V)
- Closure Manifest (Stage 15W)
- Digital signatures
- PKI or SSO
- Authentication or authorization
- External approval service integration
- AI-generated acceptance decisions
- Automatic reconstruction of `AuditAcceptanceRecord` on project load
- Automatic detection of handoff incompatibility on project load
  (this is Stage 20G.3)
- Version bump or release
- Changes to the golden demo

## Files Introduced / Modified

### Modified
- `src/origlyph/tolerance/workspace_controller.py` — v5 schema, `WorkspaceAcceptanceState`, serialization, controller methods
- `src/origlyph/tolerance/__init__.py` — exports `TOLERANCE_WORKSPACE_SCHEMA_VERSION_V5` and `WorkspaceAcceptanceState`

### Created
- `tests/unit/tolerance/test_workspace_acceptance_v5.py` — full v5 persistence test matrix
- `docs/architecture/tolerance_workspace_acceptance_persistence_v5.md` — this document
