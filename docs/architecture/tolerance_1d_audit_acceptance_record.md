# Stage 15U: Deterministic Governed Acceptance Record Intake

## Purpose and Pipeline Position

Stage 15U receives an acceptance decision supplied by an external governed
authority and validates that record against one existing Stage 15T handoff.

```text
Stage 15P comparison -> Stage 15Q impact -> Stage 15R disposition
    -> Stage 15S readiness -> Stage 15T handoff
    -> Stage 15U external acceptance-record intake
```

Stage 15U does not approve anything. It validates and preserves an acceptance
decision supplied by an external governed authority.

## Stage 15T Relationship

The intake API accepts the authoritative `AuditAcceptanceHandoffPackage`, not
raw Stage 15P--15S results. It checks the supported handoff schema, canonical
shape, lowercase SHA-256 identity, and identity/content agreement. It never
calls `build_audit_acceptance_handoff` and never reconstructs the upstream
chain.

## External-Authority Principle and Trust Boundary

The decision and both references cross into Origlyph as explicit caller input.
Origlyph does not select or default the decision and does not generate an
authority, reviewer, approver, actor, signature, or approval time.

`authority_reference` and `decision_reference` are non-empty, canonical, opaque
strings. Preserving them does not authenticate their source. A structurally
valid acceptance record does not imply that Origlyph has cryptographically
verified the human identity or legal authority of the external actor unless a
future dedicated verification mechanism explicitly provides that guarantee.

## Public API

- `ACCEPTANCE_RECORD_SCHEMA_VERSION` identifies caller records.
- `VALIDATED_ACCEPTANCE_RECORD_SCHEMA_VERSION` identifies successful intake
  artifacts.
- `AuditAcceptanceDecision` contains `APPROVED`, `REJECTED`, and
  `RETURNED_FOR_ACTION`.
- `AuditAcceptanceRecord` is the frozen caller-supplied record.
- `ValidatedAuditAcceptanceRecord` is the frozen successful intake artifact.
- `InvalidAuditAcceptanceRecordError` represents every fail-closed rejection.
- `validate_audit_acceptance_record(handoff_package, acceptance_record)`
  validates binding and returns the deterministic intake artifact.

## External Acceptance Record Model

The record contains exactly its schema version, the Stage 15T `handoff_id`, an
explicit decision, an external authority reference, and an external decision
reference. It has no inferred or pending state. All fields are supplied by the
caller, and Stage 15U never mutates the record.

## Decision Model and Readiness Consistency

A ready handoff may be approved, rejected, or returned for action. Readiness
does not compel approval, and an external authority may decline a ready item.

An `ACTION_REQUIRED` or `BLOCKED` handoff cannot carry `APPROVED`. Either may
carry `REJECTED` or `RETURNED_FOR_ACTION`. These are the smallest deterministic
constraints needed to prevent approval from contradicting the Stage 15T state;
they do not infer an external outcome.

## Handoff Binding

The record `handoff_id` must exactly equal the handoff `handoff_id`. Both use
the existing lowercase 64-character SHA-256 convention. Empty, malformed,
uppercase, truncated, normalized, or mismatched identities fail closed. The
handoff fingerprint is recomputed from its canonical content, excluding its
own identity field, without running any upstream stage.

Record binding validates deterministic content linkage. A SHA-256 fingerprint
is not a signature, and record binding does not mean a human identity was
cryptographically verified.

## Canonical Serialization and Fingerprint Identity

Both record models provide `as_dict()` and `to_json()`. JSON serialization uses
sorted keys, compact separators, ASCII escaping, and `allow_nan=False`.

`acceptance_record_id` is lowercase SHA-256 over the validated artifact's
canonical identity payload, excluding the identity field itself. The payload
includes both schema versions, exact handoff identity and status, decision,
and opaque references. Equal semantic input bound to the same handoff produces
the same ID; any preserved content change produces a different ID. The ID is
an integrity fingerprint, not an authority signature.

## Immutability and Deterministic Ordering

Public Stage 15U models are frozen slotted dataclasses. The API does not mutate
the handoff or caller record. No unordered collection is exposed, so repeated
intake produces identical dictionaries, JSON, and fingerprints.

## Fail-Closed Behavior

Stage 15U rejects wrong types, unsupported schemas, malformed or inconsistent
handoff fingerprints, empty or malformed binding IDs, mismatched IDs, unknown
decisions, empty or whitespace-padded references, approval against a nonready
handoff, and non-canonical or non-finite handoff content. Invalid state is not
trimmed, repaired, normalized, defaulted, or converted.

## No-Recomputation Policy

The intake layer does not invoke comparison, impact assessment, disposition,
readiness, handoff construction, audit construction or validation, replay, or
any worst-case, statistical, covariance, sensitivity, budget, allocation,
reconciliation, decision, evidence, or engineering engine. It consumes the
existing Stage 15T package only.

## No-Approval-Fabrication Policy

Stage 15U never creates approval, chooses a decision, maps readiness to a
decision, generates identity or authority data, signs a record, timestamps an
approval, or claims legal validity. All acceptance semantics originate in the
external record.

## Examples

- Ready handoff plus external `APPROVED`: structurally valid intake.
- Ready handoff plus external `REJECTED`: structurally valid intake.
- Action-required handoff plus `RETURNED_FOR_ACTION`: structurally valid
  intake.
- Blocked handoff plus `REJECTED`: structurally valid intake.
- Action-required or blocked handoff plus `APPROVED`: rejected.
- Any exact handoff-ID mismatch: rejected.

## Non-Goals

Stage 15U does not review engineering, approve, reject, authorize, authenticate
people, verify legal authority, validate signatures, contact an external
governance system, persist records, repair records, compare audit packages,
assess impact, determine disposition or readiness, build a handoff, or start a
later workflow stage.

AI does not override deterministic tolerance calculations or external governed
authority.
