# Stage 15S: Deterministic Audit Approval Readiness Gate

## Purpose

Stage 15P detects changes. Stage 15Q assesses deterministic impact. Stage 15R
determines deterministic disposition. Stage 15S evaluates whether that existing
disposition is ready to enter an external approval process.

Readiness is not approval. Stage 15S does not perform approval, validation,
review, replay, disposition, impact assessment, comparison, or engineering
recomputation.

## Architectural Position

```text
Stage 15P comparison
    -> Stage 15Q impact assessment
    -> Stage 15R disposition
    -> Stage 15S approval-readiness gate
```

`evaluate_audit_approval_readiness(...)` accepts only the immutable Stage 15R
`AuditChangeDispositionResult`. It does not accept raw packages, comparisons,
or impact results, and it does not invoke any upstream stage.

## Public API

- `AuditApprovalReadinessStatus` defines the gate state.
- `AuditApprovalReadinessReasonCode` defines stable machine-readable reasons.
- `AuditApprovalReadinessReason` retains the authoritative Stage 15R reason.
- `AuditApprovalReadinessResult` contains gate status, readiness boolean,
  decision transition, source state, and ordered reasons.
- `InvalidAuditApprovalReadinessError` rejects malformed dispositions.
- `evaluate_audit_approval_readiness(disposition_result)` evaluates the gate.

All models are frozen. `as_dict()` and `to_json()` serialize deterministically
with stable enum values and canonical JSON.

## Readiness Model

- `READY`: the Stage 15R disposition permits entry into an external approval
  process without a pending prerequisite represented by the current contract.
- `ACTION_REQUIRED`: Stage 15R requires engineering review, revalidation, or
  replay before approval readiness.
- `BLOCKED`: Stage 15R reports that trustworthy acceptance is blocked.

`is_ready` is true only for `READY`. It is not an `is_approved` field and does
not represent authorization, acceptance, or sign-off.

## Disposition Mapping

```text
ACCEPT                       -> READY
ACCEPT_WITH_TRACEABILITY     -> READY
ENGINEERING_REVIEW_REQUIRED  -> ACTION_REQUIRED
REVALIDATION_REQUIRED        -> ACTION_REQUIRED
REPLAY_REQUIRED              -> ACTION_REQUIRED
BLOCKED                      -> BLOCKED
```

`ACCEPT_WITH_TRACEABILITY` is ready because the Stage 15R result already
retains the structured audit history. Stage 15S preserves that traceability
reason in its output; it does not discard the condition.

## Precedence

When the ordered Stage 15R reasons contain multiple states, aggregate
precedence is:

```text
BLOCKED > ACTION_REQUIRED > READY
```

No number, weight, score, confidence, probability, or desirability is assigned.
All reasons remain visible even when a stronger state controls the gate.

## Ready Policy

`ACCEPT` maps to `READY` with `NO_FURTHER_ACTION_REQUIRED`.
`ACCEPT_WITH_TRACEABILITY` maps to `READY` with `TRACEABILITY_PRESERVED`.

Ready means only that no prerequisite represented by Stage 15R remains. It
does not say that an approver exists, that approval was requested, or that an
approval decision was made.

## Action-Required Policy

`ENGINEERING_REVIEW_REQUIRED` maps to `ENGINEERING_REVIEW_PENDING`.
`REVALIDATION_REQUIRED` maps to `REVALIDATION_PENDING`. `REPLAY_REQUIRED` maps
to `REPLAY_PENDING`. Each produces `ACTION_REQUIRED` and `is_ready=False`.

Stage 15S does not perform these actions and accepts no flags claiming that a
review, revalidation, or replay has been completed. Such completion evidence is
outside the current repository contract.

## Blocked and Integrity Policy

`BLOCKED` maps to `BLOCKED` and `is_ready=False`. This preserves Stage 15R's
fail-closed treatment of incompatible comparison, replayability loss,
untrustworthy integrity, unsupported schema, package verification failure, and
unexplained identity drift.

Stage 15S never converts a blocked disposition into action-required or ready.
It does not repair integrity or normalize audit content.

## Decision-Transition Policy

Stage 15S copies the typed Stage 15R decision transition without ranking its
direction. PASS to FAIL, FAIL to PASS, PASS to INCOMPLETE, and INCOMPLETE to
PASS remain action-required through the revalidation disposition. A decision
transition cannot be ready under the current contract.

When a decision did not change, Stage 15S does not invent previous or current
decision statuses.

## Traceability and Reason Model

Each readiness reason retains the complete Stage 15R reason. That nested source
retains its Stage 15Q impact and impact reason and, where applicable, its Stage
15P change reference with code, category, scope, subject, path, values,
significance, and detail.

The no-impact path retains the Stage 15R no-action reason without fabricating a
change. Reason ordering follows Stage 15R exactly.

## No Approval Fabrication

Stage 15S creates no approval, reviewer, authority, actor, user, signature,
timestamp, workflow completion, or sign-off record. The API exposes
`is_ready`, never `is_approved`.

Consumers must not interpret `READY` as evidence that a human or external
authority approved the audit change.

## Determinism and Immutability

The input disposition and nested reasons are never mutated. Repeated evaluation
of equal input returns equal frozen results and byte-identical canonical JSON.
The gate uses explicit enum mappings and fixed precedence only.

## Fail-Closed Behavior

Stage 15S rejects wrong input types, invalid or unmapped enum states, empty or
non-tuple reasons, duplicate reasons, code/disposition contradictions,
impact/disposition contradictions, missing change traceability, fabricated
changes on no-action reasons, invalid decision transitions, incompatible
comparisons not marked blocked, and reason collections inconsistent with the
aggregate disposition.

Malformed input never defaults to `READY`. Future Stage 15R dispositions must
receive explicit readiness and reason mappings.

## No-Recomputation Rule

Stage 15S calls no Stage 15P comparator, Stage 15Q assessor, Stage 15R
disposition function, audit builder, or worst-case, statistical, covariance,
sensitivity, budget, allocation, reconciliation, decision, or evidence engine.
It consumes the authoritative Stage 15R result only.

## Examples

- No deterministic change: `READY`.
- Traceability-only accepted change: `READY`, with traceability reason retained.
- Changed engineering evidence awaiting review: `ACTION_REQUIRED`.
- Decision transition awaiting revalidation: `ACTION_REQUIRED`.
- Replayability restored but replay pending: `ACTION_REQUIRED`.
- Integrity or replayability blocked: `BLOCKED`.
- Review-required and blocked reasons together: both remain ordered; aggregate
  status is `BLOCKED`.

## Non-Goals

Stage 15S does not approve, reject, accept, sign, authorize, validate, review,
replay, compare, assess impact, determine disposition, recompute engineering,
rank alternatives, assign scores, create actors or workflows, persist records,
or generate AI narrative.

AI does not override deterministic tolerance calculations.
