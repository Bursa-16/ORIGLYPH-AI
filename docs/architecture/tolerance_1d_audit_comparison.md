# Stage 15P: Deterministic Audit Package Comparison

## Purpose

Stage 15P compares two immutable Stage 15O
`ToleranceDecisionAuditPackage` objects and emits an ordered, typed change set.
The first object is always the baseline reference and the second is always the
candidate. Timestamps do not determine chronology.

Audit comparison detects deterministic differences; it does not recompute
authoritative engineering calculations.

Comparison does not rank one design as better or worse. It selects no preferred
package and makes no design recommendation.

## Architectural Position

```text
authoritative tolerance engines
    -> Stage 15K decision
    -> Stage 15L evidence and explanation
    -> Stage 15M report envelope
    -> Stage 15N integrity validation
    -> Stage 15O audit package and replay manifest
    -> Stage 15P deterministic package comparison
```

Stage 15P reads existing audit artifacts. It may call Stage 15O structural
verification but never calls tolerance, statistical, sensitivity, budget,
allocation, reconciliation, or decision engines.

## Public Contract

`compare_decision_audit_packages(baseline, candidate)` returns a frozen
`AuditPackageComparisonResult`. Its status is one of:

- `IDENTICAL`: all deterministic Stage 15O content is equal;
- `CHANGED`: deterministic content differs and both packages remain
  structurally comparable;
- `INCOMPATIBLE`: schemas differ, a schema is unsupported, or a package does
  not verify as its declared structural state.

Wrong invocation types raise `InvalidAuditComparisonError`.

Each frozen `AuditChange` contains a stable `AuditChangeCode`,
`AuditChangeCategory`, neutral `AuditChangeSignificance`, scope, subject,
field path, baseline value, candidate value, and deterministic detail.

## Change Categories

Stable categories cover schema, input, policy, decision, integrity,
replayability, evidence, explanation, contributor, correlation, allocation,
reconciliation, fingerprint, report, and structural changes. Significance is
classified as informational, structural, engineering-relevant, or incompatible;
it is never an improvement/degradation judgment.

## Input and Policy Changes

The comparator uses only deterministic input content preserved in the Stage 15M
report and Stage 15O manifest. It detects contributor and metric additions,
removals, value changes, ordering changes, allocation and reconciliation metric
changes, equality-tolerance changes, sigma-multiplier changes, completeness
policy markers, policy-identifier changes, and input-fingerprint changes.

Raw values absent from report schema v1 are not inferred. In particular, the
Stage 15O `not_recorded_by_report_schema_v1` completeness-policy marker is
compared as the explicit preserved value.

## Decision and Explanation Changes

Decision-status and completeness transitions are represented neutrally as
baseline and candidate values. The comparator also detects summary-code,
governing-reason, marginal-reason, supporting-reason, governing-evidence, and
marginal-evidence changes. Human-readable summary text is not the sole basis
for explanation comparison; any remaining deterministic report change is still
visible through report identity and fingerprint changes.

## Evidence Changes

Evidence references are matched by `evidence_id`, not list position. Added and
removed references, evidence-code changes, source changes, reason-code changes,
and triggered-reason linkage changes are classified explicitly. Numeric metrics
preserved in report sections are compared by stable metric key without
recomputing their effects.

## Integrity and Replayability

Integrity status transitions and violation additions, removals, or changes are
compared using stable violation codes, scopes, subjects, severities, and details.
Replayability transitions are a separate structural category.

Engineering decision status and replayability status are separate dimensions.
For example, an engineering FAIL package may remain structurally replayable.

## Contributors, Allocations, and Reconciliation

Contributor identity uses the preserved name and contribution type. The change
set detects additions, removals, order changes, actual-span changes, sigma
changes, bound changes, and preserved mode flags. Allocation, statistical
allocation, and reconciliation metrics are compared by their stable report
section and metric keys. Sensitivity or rank fields are reported when present;
missing fields are not invented.

## Correlations

Correlation assumptions use the canonical Stage 15O metric-pair identifier.
The comparator detects pair additions, removals, and coefficient changes.
Canonical pair identity follows the upstream Origlyph contract, so reversed
pair spelling is not independently invented by Stage 15P.

## Fingerprints and Structural Drift

The comparison checks decision identity, package identity, input fingerprint,
report fingerprint, and integrity fingerprint. Fingerprint changes are emitted
alongside semantic changes. If a fingerprint differs while its underlying
deterministic content is equal, Stage 15P emits
`UNEXPLAINED_FINGERPRINT_DRIFT` and treats the setup as incompatible.

These checks detect deterministic inconsistency; they are not digital
signatures and do not establish actor authenticity.

## Provenance Policy

Provenance-only differences are ignored by default for deterministic
comparison. Actor, timestamp, external audit ID, and metadata do not make two
otherwise identical packages changed. The result records that provenance was
not compared.

## Deterministic Ordering and Serialization

Changes are ordered by stable category priority, then scope, subject, field
path, and change code. Repeated comparison of identical inputs produces equal
results and byte-identical canonical JSON. `as_dict()` uses stable enum strings;
`to_json()` uses standard-library JSON with sorted keys and `allow_nan=False`.

## Fail-Closed Behavior

Audit and report schema differences are incompatible; no migration is inferred.
Both packages are structurally verified before semantic comparison. A package
whose verified state disagrees with its declared replayability is not compared
as valid. Broken identities and unexplained fingerprint drift are surfaced as
incompatible structural changes rather than ignored.

Neither input package is mutated or repaired.

## Exclusions

Stage 15P does not implement design recommendation, alternative ranking,
preferred-package selection, optimization, tolerance redistribution,
engineering recomputation, audit repair, report repair, persistence, document
export, UI, web APIs, multi-stack aggregation, CAD or GD&T semantics, Monte
Carlo analysis, process capability analysis, or AI-generated narrative.

AI does not override deterministic tolerance calculations.
