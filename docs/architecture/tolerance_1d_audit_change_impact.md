# Stage 15Q: Deterministic Audit Change Impact Assessment

## Purpose

Stage 15P detects deterministic changes. Stage 15Q assesses the deterministic
impact of those already-detected changes. It turns an authoritative, ordered
`AuditPackageComparisonResult` into a typed impact assessment without
re-detecting differences or interpreting either package independently.

Stage 15Q does not recompute engineering results and does not replace Stage 15P
comparison.

## Relationship to Stage 15P

```text
Stage 15O audit packages
    -> Stage 15P deterministic comparison (what changed?)
    -> Stage 15Q deterministic impact assessment (what is the impact?)
```

`assess_audit_change_impact(comparison_result)` accepts only the frozen Stage
15P result. It does not accept raw audit packages and does not call
`compare_decision_audit_packages`. The Stage 15P change codes, baseline and
candidate values, and ordering remain authoritative.

## Public API

- `AuditChangeImpact` defines the impact level.
- `AuditChangeImpactReason` supplies a stable machine-readable rationale.
- `AuditChangeImpactAssessment` links one Stage 15P change to its impact.
- `AuditChangeImpactResult` contains the aggregate impact, decision transition,
  flags, and ordered assessments.
- `InvalidAuditChangeImpactError` rejects invalid or inconsistent comparison
  results.
- `assess_audit_change_impact(...)` performs the read-only assessment.

All result models are frozen. `as_dict()` and `to_json()` provide deterministic
serialization using stable enum values and canonical JSON.

## Impact Model

- `NO_IMPACT`: Stage 15P found no deterministic change.
- `TRACEABILITY_ONLY`: identity or traceability changed without independently
  changing engineering evidence, compliance semantics, or decision status.
- `ENGINEERING_EVIDENCE`: preserved numeric, contributor, or supporting
  evidence changed while no stronger impact is present.
- `COMPLIANCE_RELEVANT`: policy, governing or marginal evidence, allocation,
  reconciliation, correlation, completeness, or trustworthy-interpretation
  state changed without an explicit final decision transition.
- `DECISION_CHANGING`: the Stage 15P final decision status changed.
- `REPLAY_BLOCKING`: compatibility, verification, candidate integrity, or
  candidate replayability prevents trustworthy deterministic replay.

These are semantic classes, not scores and not better/worse rankings.

## Precedence

When multiple change classes occur, the aggregate precedence is:

```text
REPLAY_BLOCKING
> DECISION_CHANGING
> COMPLIANCE_RELEVANT
> ENGINEERING_EVIDENCE
> TRACEABILITY_ONLY
> NO_IMPACT
```

No numeric severity or weighted score is calculated. Every individual change
assessment remains present even when a stronger class controls the aggregate.

## Comparison Status Policy

`IDENTICAL` requires an empty Stage 15P change tuple and maps to `NO_IMPACT`.
This preserves Stage 15P's default exclusion of provenance-only differences.

`CHANGED` requires at least one change and is assessed only from those change
entries.

`INCOMPATIBLE` requires an explicit incompatible or blocking structural change
and always maps to `REPLAY_BLOCKING`. It is never treated as an ordinary
comparable engineering state.

## Decision-Transition Policy

`DECISION_STATUS_CHANGED` supplies the only decision transition. Both values
must be real `ToleranceDecisionStatus` values and must differ. Transitions such
as PASS to MARGINAL, PASS to FAIL, FAIL to PASS, INCOMPLETE to PASS, and PASS to
INCOMPLETE are all `DECISION_CHANGING`; Stage 15Q assigns no desirability.

For PASS to PASS or FAIL to FAIL, Stage 15P emits no decision-status change.
Stage 15Q therefore reports `decision_changed=False` and leaves previous and
current decision statuses unavailable rather than inventing them.

## Evidence Impact

Input metrics, contributor additions/removals/order, contributor spans, sigma,
bounds, mode fields, supporting reasons, and generic evidence additions,
removals, or code mutations are `ENGINEERING_EVIDENCE`. Evidence-source-only
changes are `TRACEABILITY_ONLY`.

Governing and marginal reason sets, governing and marginal evidence sets, and
reason linkage directly affect compliance interpretation and are
`COMPLIANCE_RELEVANT`.

## Compliance Impact

Equality tolerance, sigma multiplier, completeness policy, policy identifiers,
report completeness, summary code, allocation, statistical allocation,
reconciliation, reconciliation margin, and correlation changes are
`COMPLIANCE_RELEVANT`. The classification is based on explicit Stage 15P codes,
not filename, path, or free-text heuristics.

Stage 15P report schema v1 represents general requirement metrics through its
input-metric codes. Stage 15Q does not infer a stronger requirement meaning
from a metric name; those changes remain `ENGINEERING_EVIDENCE` unless Stage
15P also emits a compliance-specific reason, decision, policy, allocation, or
reconciliation code.

## Integrity Impact

A candidate integrity transition to `INVALID` or `INCOMPLETE`, or an added or
mutated integrity violation, is `REPLAY_BLOCKING`. A transition to `VALID` or a
removed violation remains visible as `COMPLIANCE_RELEVANT`; it is not described
as an improvement. Package verification failure and unexplained identity drift
are also fail-closed and replay-blocking.

## Replayability Impact

A replayability transition to `NOT_REPLAYABLE` or `INCOMPLETE` is
`REPLAY_BLOCKING`, independently of engineering decision status. A transition
to `REPLAYABLE` is `COMPLIANCE_RELEVANT` and remains directionally neutral.

## Fingerprint and Identity Impact

Stage 15Q never recomputes fingerprints. Explained decision, package, input,
report, and integrity identity changes are `TRACEABILITY_ONLY` by themselves;
the accompanying semantic Stage 15P changes determine any stronger impact.
`UNEXPLAINED_FINGERPRINT_DRIFT` is always `REPLAY_BLOCKING`.

## Provenance Behavior

Stage 15P ignores provenance-only differences by default. Stage 15Q preserves
that behavior exactly: an `IDENTICAL` comparison maps to `NO_IMPACT`, and Stage
15Q never inspects provenance outside the comparison result.

## Ordering and Determinism

Assessments preserve the authoritative Stage 15P change order. No competing
sort is applied. Repeated assessment of equal input returns equal frozen
results and byte-identical canonical JSON. The input comparison result is never
mutated.

## Fail-Closed Policy

Wrong input types, invalid enum fields, non-tuple change collections, invalid
field types, duplicate changes, impossible empty/non-empty status combinations,
unsupported decision/integrity/replay values, duplicate decision transitions,
and unmapped Stage 15P change codes raise `InvalidAuditChangeImpactError`.

Malformed input never silently becomes `NO_IMPACT`. This strict mapping also
forces a future Stage 15P change code to receive an explicit Stage 15Q policy.

## No-Recomputation Policy

Stage 15Q calls no worst-case, statistical, covariance, sensitivity, budget,
allocation, reconciliation, decision, evidence, audit-builder, or comparison
engine. It reads the Stage 15P result only. It does not repair integrity,
normalize values, rebuild audit packages, or verify fingerprints.

## Examples

- Identical packages: `NO_IMPACT`.
- Changed contributor span with unchanged final status:
  `ENGINEERING_EVIDENCE`.
- Equality-tolerance change with unchanged final status:
  `COMPLIANCE_RELEVANT`.
- PASS to FAIL or FAIL to PASS: `DECISION_CHANGING`.
- PASS to PASS with a numeric metric change: `ENGINEERING_EVIDENCE`, with no
  inferred decision transition.
- Replayability loss despite an unchanged engineering status:
  `REPLAY_BLOCKING`.
- Decision change plus integrity degradation: both assessments are retained;
  aggregate impact is `REPLAY_BLOCKING`.

## Non-Goals

Stage 15Q does not compare packages, recompute engineering formulas, rank
designs, select a preferred result, assign business desirability, calculate a
score or probability, generate recommendations, repair audit content, infer
missing report-v1 inputs, inspect provenance, persist results, or provide AI
narrative.

AI does not override deterministic tolerance calculations.
