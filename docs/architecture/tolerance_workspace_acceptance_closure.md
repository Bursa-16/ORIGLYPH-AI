# Tolerance Workspace — Acceptance Verification + Acceptance Closure Surface (Stage 20H)

## Overview

Stage 20H implements the final two steps of the governance chain:

1. **Acceptance Verification** — wraps the handoff and acceptance record in a
   `AuditAcceptanceVerificationEnvelope` (Stage 15V).  The envelope is
   `VERIFIED_BINDING` when all four verification facts pass.
2. **Acceptance Closure** — assembles the complete `AuditAcceptanceClosureManifest`
   (Stage 15W) from the handoff, record, and verification envelope.  Status is
   always `COMPLETE` when the constructor succeeds.

## Prerequisites

| Step | Required artifact |
|---|---|
| run_acceptance_verification | `_last_acceptance_handoff` + `_last_acceptance_record` |
| run_acceptance_closure | `_last_acceptance_handoff` + `_last_acceptance_record` + `_last_acceptance_verification` |

Calling either method without the required artifacts raises
`InvalidToleranceWorkspaceError` with an explicit message naming the missing step.

## Authority Model

| Artifact | Classification | Persisted |
|---|---|---|
| `AuditAcceptanceHandoffPackage` | Runtime-derived | No |
| `WorkspaceAcceptanceState` | Authoritative inputs | Yes (v5) |
| `ValidatedAuditAcceptanceRecord` | Runtime-derived | No |
| `AuditAcceptanceVerificationEnvelope` | Runtime-derived | No |
| `AuditAcceptanceClosureManifest` | Runtime-derived | No |

The workspace schema does not change in Stage 20H.  Both the verification
envelope and the closure manifest are fully derivable at runtime from the
already-persisted `WorkspaceAcceptanceState` plus the live governance chain.
`PERSISTENCE_CONTRACT_REQUIRED: NO`.

## Verification Semantics

`build_acceptance_record_verification_envelope(handoff_package, validated_record)`
returns an envelope whose `status` is always
`AuditAcceptanceVerificationStatus.VERIFIED_BINDING`.  The envelope contains:

- `envelope_id` — SHA-256 of the canonical chain representation (64 hex chars).
- `handoff_id` — copied from the handoff package.
- `acceptance_record_id` — copied from the validated record.
- `decision`, `authority_reference`, `decision_reference` — forwarded from the record.
- `verification_facts` — four facts: `HANDOFF_FINGERPRINT_MATCH`,
  `ACCEPTANCE_RECORD_FINGERPRINT_MATCH`, `HANDOFF_BINDING_MATCH`,
  `REFERENCE_CONTENT_PRESERVED`.

If any fact cannot be established, Stage 15V raises
`InvalidAuditAcceptanceVerificationError` and the controller propagates it unchanged.

## Closure Semantics

`build_acceptance_closure_manifest(handoff_package, validated_record, envelope)`
returns a manifest whose `status` is always
`AuditAcceptanceClosureStatus.COMPLETE`.  The manifest contains:

- `closure_id` — SHA-256 of the canonical chain (64 hex chars).
- `references` — an `AuditAcceptanceClosureReference` linking all three chain
  artifacts by their IDs, plus the decision, authority reference, and decision
  reference forwarded from the record.

If construction fails, Stage 15W raises `InvalidAuditAcceptanceClosureError`
and the controller propagates it unchanged.

## Runtime / Persistence Boundary

Neither the verification envelope nor the closure manifest is serialized.  On
project reload, both are `None`.  The user must re-run the full governance
chain — `run_acceptance_handoff()` → `run_acceptance_record()` →
`run_acceptance_verification()` → `run_acceptance_closure()` — to obtain a
live closure manifest.

The save/open round-trip preserves `WorkspaceAcceptanceState` exactly (Stage 20G.2
v5 schema).  This is sufficient to reconstruct the full chain from scratch.

## Project Identity Boundary

Neither `run_acceptance_verification()` nor `run_acceptance_closure()` mutates
`self._state`.  Only `set_acceptance_state()` mutates `_state` and therefore
changes `configuration_fingerprint()`.  Runtime governance artifacts have no
effect on project identity.

## Stale Clearing Chain

The full stale clearing order is:

```
upstream engineering change
  → clears: handoff, record, verification, closure

run_acceptance_handoff()
  → clears: record, verification, closure

set_acceptance_state()
  → clears: record, verification, closure

run_acceptance_record()
  → clears: verification, closure

run_acceptance_verification()
  → clears: closure only

run_acceptance_closure()
  → clears: nothing downstream
```

This ensures no stale derived artifacts survive upstream changes.

## UI Workflow

| Row | Frame |
|---|---|
| 20 | Governed Acceptance |
| 21 | Acceptance Record |
| **22** | **Acceptance Verification** ← new (Stage 20H) |
| **23** | **Acceptance Closure** ← new (Stage 20H) |
| 24 | Project File (moved from row 22) |

### Acceptance Verification frame (row 22)

- **Verify Acceptance Record** button — calls `run_acceptance_verification()`.
- Status label (bold): shows `VERIFIED_BINDING` or `NOT VERIFIED`.
- Detail label: shows `Envelope ID: <first 16 hex chars>…  Facts: 4`.

### Acceptance Closure frame (row 23)

- **Build Closure Manifest** button — calls `run_acceptance_closure()`.
- Status label (bold): shows `COMPLETE` or `NOT BUILT`.
- Detail label: shows `Closure ID: <first 16 hex chars>…  Decision: <decision value>`.

## Feature Isolation

`run_acceptance_verification()` does not mutate:

- `_last_acceptance_record`
- `_last_approval_readiness`
- `WorkspaceAcceptanceState`

`run_acceptance_closure()` does not mutate:

- `_last_acceptance_record`
- `_last_acceptance_verification`
- `WorkspaceAcceptanceState`

## Semantic Safety

Status text uses only exact enum values (`VERIFIED_BINDING`, `COMPLETE`, `NOT VERIFIED`,
`NOT BUILT`).  No Approve/Certify/Sign/Release/Authorize wording appears in any status
text, detail text, button label, or frame title.

**Mandatory statement:**

> Acceptance Verification and Acceptance Closure are deterministic governance
> artifacts.  They do not provide actor authentication, digital signatures,
> authorization proof, regulatory certification, or release authorization.

## Security Limitations

- `authority_reference` and `decision_reference` are free-text strings.  The
  workspace does not validate that they refer to real governance records.
- No authentication of the operator is performed.
- The `envelope_id` and `closure_id` are deterministic SHA-256 digests of the
  chain state.  They are integrity fingerprints, not cryptographic signatures.
- Storing the project file does not constitute a tamper-proof audit log.

## Non-Goals

This stage does NOT implement:

- Digital signatures, PKI, or SSO
- Authentication or authorization of users
- External approval service integration
- AI-generated acceptance or verification decisions
- Automatic chain reconstruction on project load
- Version bump or release
- Changes to the golden demo
