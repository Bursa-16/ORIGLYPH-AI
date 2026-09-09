# Stage 15R: Deterministic Audit Change Disposition

## Purpose

Stage 15P detects changes. Stage 15Q assesses deterministic impact. Stage 15R
determines deterministic disposition.

Stage 15R maps an authoritative Stage 15Q impact result to the governance
action required before acceptance. It does not perform approval, validation,
replay, or engineering recomputation.

## Relationship to Stages 15P and 15Q

```text
Stage 15P comparison: what changed?
    -> Stage 15Q impact: what deterministic impact does it have?
    -> Stage 15R disposition: what governed action is required?
```

`determine_audit_change_disposition(...)` accepts only an
`AuditChangeImpactResult`. It does not accept audit packages or comparison
results, call the Stage 15P comparator, or call the Stage 15Q assessor. Stage
15P owns changes and their order; Stage 15Q owns impact classification; Stage
15R owns disposition only.

## Public API

- `AuditChangeDisposition` defines the governed disposition.
- `AuditChangeDispositionReasonCode` defines stable reason identities.
- `AuditChangeDispositionReason` retains the source impact reason and optional
  Stage 15P change reference.
- `AuditChangeDispositionResult` contains the aggregate disposition, decision
  transition, and ordered reasons.
- `InvalidAuditChangeDispositionError` rejects malformed impact results.
- `determine_audit_change_disposition(impact_result)` is the read-only entry
  point.

Models are frozen and expose deterministic `as_dict()` and canonical `to_json()`
serialization.

## Disposition Model

- `ACCEPT`: no meaningful deterministic change requires action.
- `ACCEPT_WITH_TRACEABILITY`: identity or traceability changed; acceptance must
  retain explicit audit history.
- `ENGINEERING_REVIEW_REQUIRED`: engineering evidence changed and requires
  review before acceptance.
- `REVALIDATION_REQUIRED`: compliance-relevant content or the deterministic
  decision changed and requires governed revalidation.
- `REPLAY_REQUIRED`: replayability was explicitly re-established, so a new
  deterministic replay is required before acceptance.
- `BLOCKED`: safe acceptance is unavailable because trustworthy replay,
  integrity, schema, identity, or compatibility is blocked.

These dispositions describe required action only. They are not approval
records, business desirability rankings, confidence levels, probabilities, or
weighted scores.

## Precedence

When ordered reasons require multiple dispositions, the aggregate precedence
is:

```text
BLOCKED
> REPLAY_REQUIRED
> REVALIDATION_REQUIRED
> ENGINEERING_REVIEW_REQUIRED
> ACCEPT_WITH_TRACEABILITY
> ACCEPT
```

No numeric severity is assigned. All reasons remain present even when a
stronger disposition controls the result.

## Impact Mapping Policy

The direct mapping is:

```text
NO_IMPACT            -> ACCEPT
TRACEABILITY_ONLY    -> ACCEPT_WITH_TRACEABILITY
ENGINEERING_EVIDENCE -> ENGINEERING_REVIEW_REQUIRED
COMPLIANCE_RELEVANT  -> REVALIDATION_REQUIRED
DECISION_CHANGING    -> REVALIDATION_REQUIRED
REPLAY_BLOCKING      -> BLOCKED
```

The sole explicit replay-required refinement is a Stage 15Q
`COMPLIANCE_RELEVANT` assessment whose retained Stage 15P change code is
`REPLAYABILITY_STATUS_CHANGED`. Stage 15Q classifies replayability loss as
`REPLAY_BLOCKING`; therefore the non-blocking form means replayability was
re-established and replay is possible. Stage 15R then requires replay before
acceptance. No other content is inferred to require replay.

## Decision-Transition Policy

Stage 15R copies, but does not reinterpret, the Stage 15Q decision transition.
PASS to FAIL, FAIL to PASS, PASS to INCOMPLETE, INCOMPLETE to PASS, and every
other valid distinct transition require `REVALIDATION_REQUIRED`. No direction
is called good, bad, improved, or degraded.

PASS to PASS and FAIL to FAIL do not carry an explicit Stage 15Q transition.
When their evidence changes, the evidence impact still produces
`ENGINEERING_REVIEW_REQUIRED` or a stronger disposition. Stage 15R does not
invent unavailable unchanged status values.

## Engineering-Review Policy

`ENGINEERING_EVIDENCE` requires `ENGINEERING_REVIEW_REQUIRED`. Stage 15R does
not perform the review, decide whether evidence is acceptable, or sign off the
change. Structured source impact and change references remain attached to the
reason.

## Revalidation Policy

`COMPLIANCE_RELEVANT` and `DECISION_CHANGING` normally require
`REVALIDATION_REQUIRED`. This is a requirement for a later governed action,
not evidence that validation or approval occurred.

## Replay-Required Policy

`REPLAY_REQUIRED` is distinct from `BLOCKED`. It is emitted only when Stage 15Q
reports a non-blocking explicit replayability transition, meaning replayability
has been re-established. Stage 15R does not execute replay and does not treat
generic engineering, fingerprint, or policy changes as replay-required.

## Blocked and Integrity Policy

Every `REPLAY_BLOCKING` impact maps to `BLOCKED`. This covers integrity
degradation, added or mutated integrity violations, replayability loss,
unsupported schema, failed package verification, incompatible comparison, and
unexplained identity drift already classified by Stage 15Q.

These conditions can never produce an accepting disposition. Stage 15R does
not repair, normalize, or override integrity evidence.

## Traceability

Every result includes structured reason codes. Change-bearing reasons retain
the authoritative Stage 15Q source impact, source impact reason, and the full
Stage 15P `AuditChange` reference, including code, category, scope, subject,
path, values, significance, and detail. `NO_IMPACT` has a stable no-action
reason without fabricating a change.

No reviewer, approver, actor, signature, timestamp, or authority record is
created. Stage 15R never claims a human action occurred.

## Ordering and Determinism

Disposition reasons preserve Stage 15Q assessment order. No alternative sort
is applied. Aggregate precedence is fixed and non-numeric. Repeated calls with
equal input produce equal frozen results and byte-identical canonical JSON.
The input impact result and nested changes are never mutated.

## Fail-Closed Behavior

Stage 15R rejects wrong input types, invalid enums, non-tuple or duplicate
assessments, per-change `NO_IMPACT`, inconsistent impact/reason pairs,
impossible identical or changed structures, unrepresented overall impact,
invalid or contradictory decision transitions, and incompatible results that
are not replay-blocking.

Unknown or unmapped impact states do not default to acceptance. Every current
`AuditChangeImpact` member has an explicit disposition mapping; future members
must receive an explicit policy.

## No-Recomputation Rule

Stage 15R calls none of the comparison, impact, worst-case, statistical,
covariance, sensitivity, budget, allocation, reconciliation, decision,
evidence, or audit-building functions. It consumes Stage 15Q output only.

## Examples

- Identical deterministic content: `ACCEPT`.
- Package-identity-only change: `ACCEPT_WITH_TRACEABILITY`.
- Contributor or numeric evidence change with unchanged decision:
  `ENGINEERING_REVIEW_REQUIRED`.
- Compliance policy or final decision change: `REVALIDATION_REQUIRED`.
- Replayability re-established: `REPLAY_REQUIRED`.
- Replayability lost or integrity untrustworthy: `BLOCKED`.
- Decision change plus replay-blocking integrity change: both reasons remain;
  aggregate disposition is `BLOCKED`.

## Non-Goals

Stage 15R does not detect changes, reassess impact, recompute engineering,
perform review, validate or approve a change, execute replay, create workflow
actors, fabricate authority, sign records, rank alternatives, optimize a
design, assign probability or confidence, persist records, or generate AI
narrative.

AI does not override deterministic tolerance calculations.
