# Stage 15O: Deterministic Audit Package and Replay Manifest

## Purpose

Stage 15O packages an existing tolerance decision report and its audit-integrity
result into one deterministic, serializable audit artifact. It lets an external
consumer identify the evaluated report, verify its deterministic content, and
inspect the contract available for future replay.

The audit package verifies and preserves deterministic decision artifacts; it
does not recompute authoritative engineering calculations.

## Architectural Position

```text
authoritative tolerance engines
    -> Stage 15K decision
    -> Stage 15L evidence and explanation
    -> Stage 15M report envelope
    -> Stage 15N integrity validation
    -> Stage 15O audit package and replay manifest
```

Stage 15O consumes Stage 15M and Stage 15N artifacts. It may invoke the Stage
15N structural validator when no integrity result is supplied. It never invokes
worst-case, statistical, sensitivity, budget, allocation, reconciliation, or
decision engines.

## Audit Package Model

`ToleranceDecisionAuditPackage` is frozen and contains:

- the independent audit schema version;
- a deterministic SHA-256 `package_id`;
- the complete `ToleranceDecisionReport`;
- its `AuditIntegrityResult`;
- a `DecisionReplayManifest`;
- a structural `ReplayabilityStatus`;
- optional Stage 15M `DecisionProvenance`.

The public constructor is `build_decision_audit_package(...)`. Invalid types,
unsupported schemas, malformed payloads, non-finite deterministic content, and
identity mismatches fail closed with `InvalidDecisionAuditPackageError`.

## Schema Version

The audit schema identifier is:

```text
origlyph.tolerance.audit_package.v1
```

It is independent of package version `0.4.0a3` and report schema version
`origlyph.tolerance.decision_report.v1`.

## Replay Manifest

`DecisionReplayManifest` records the report and audit schema versions, report
decision identity, package identity, equality tolerance, optional sigma
multiplier, canonical correlation metrics, deterministic fingerprints,
integrity state, and fixed policy identifiers.

Stage 15M report schema v1 does not retain the raw Stage 15K
`require_complete` invocation flag. The manifest records this fact explicitly
as `not_recorded_by_report_schema_v1`; it does not infer that policy from the
report's completeness outcome. Likewise, the deterministic input fingerprint
covers only the input surface actually preserved by the report: contributors,
metric sections, equality tolerance, sigma multiplier, and the explicit
policy-availability marker.

This is intentional fail-closed provenance. Stage 15O does not invent missing
engineering assumptions.

## Deterministic Identity and Fingerprints

All fingerprints use standard-library SHA-256 over canonical JSON with sorted
keys, compact separators, ASCII escaping, and `allow_nan=False`.

- `input_fingerprint` covers the report-v1 deterministic input surface.
- `report_fingerprint` covers the complete deterministic report payload.
- `integrity_fingerprint` covers the complete integrity-result payload.
- `package_id` covers the audit schema, decision identity, report and integrity
  fingerprints, and replay-manifest identity content.

The manifest's copy of `package_id` is excluded from its own identity input to
avoid a circular hash definition, then populated with the resulting package
identity. Verification requires the package and manifest copies to match.

These hashes detect deterministic content changes. They are not digital
signatures, do not authenticate an actor, and make no key-based security claim.

## Optional Provenance

Stage 15O reuses `DecisionProvenance`; it does not introduce a competing
provenance model. When the builder receives no explicit provenance, it retains
the report's provenance where present.

Optional provenance metadata does not participate in deterministic package
identity. Changing actor, generation timestamp, audit ID, or metadata alone
does not change `decision_id`, `package_id`, or any deterministic fingerprint.
Provenance is still serialized and preserved by round trip.

## Replayability

`ReplayabilityStatus` has three states:

- `REPLAYABLE`: the manifest is structurally complete and integrity is `VALID`;
- `NOT_REPLAYABLE`: structural integrity is invalid or verification detects
  deterministic-content tampering;
- `INCOMPLETE`: a required schema or manifest element is unsupported or
  incomplete.

Engineering PASS/FAIL and audit replayability are separate concepts. A valid,
internally consistent engineering FAIL report remains structurally replayable.
An invalid integrity result is retained for inspection but is never labeled
replayable.

Replayability in Stage 15O refers to structural deterministic replay readiness,
not independent re-execution of every engineering engine. It means the package
contains the complete Stage 15M/15N contract available for future authoritative
replay and can verify that preserved contract without recomputing mathematics.

## Serialization and Round Trip

`as_dict()` emits the complete audit payload and `to_json()` emits canonical
JSON without timestamps or random data. `audit_package_from_dict(...)` requires
the complete v1 field set, rejects unknown top-level or manifest fields, rebuilds
all report metric sections, and verifies IDs and fingerprints.

The required invariant is:

```python
package.as_dict() == audit_package_from_dict(package.as_dict()).as_dict()
```

## Verification

`verify_decision_audit_package(...)` structurally verifies:

- audit and report schema versions;
- manifest completeness;
- report, input, and integrity fingerprints;
- report decision identity;
- package and manifest package identities;
- integrity status consistency and Stage 15N result consistency;
- deterministic serialization round trip.

Verification does not silently repair an invalid package. Unsupported or
incomplete contracts fail closed, and tampering produces a non-replayable
result or a loading exception.

## Exclusions

Stage 15O does not provide external persistence, databases, UI, web APIs,
document export, digital signatures, engineering-engine re-execution,
multi-stack aggregation, design comparison, optimization, recommendations,
Monte Carlo analysis, process capability analysis, CAD semantics, GD&T
interpretation, or AI-generated engineering narrative.

AI does not override deterministic tolerance calculations.
