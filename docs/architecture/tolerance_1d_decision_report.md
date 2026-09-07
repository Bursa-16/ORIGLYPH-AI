# Stage 15M: Deterministic Tolerance Decision Report Envelope

## Purpose

Stage 15M provides a deterministic, export-ready **audit envelope** that packages
the authoritative Stage 15K decision result and the Stage 15L evidence/explanation
into a single, serializable report structure.

## Architectural Position

Stage 15M sits ABOVE the Stage 15K/15L layers:

```
authoritative tolerance engines
        |
Stage 15K decision layer
        |
Stage 15L evidence / explainability layer
        |
Stage 15M deterministic report model  (this module)
```

## Core Principle

**The decision report is an audit envelope; it does not recompute authoritative
engineering calculations.**

## DecisionInputs

`DecisionInputs` is an immutable container holding the three authoritative inputs:

- `decision_result`: The Stage 15K `ToleranceDecisionResult`
- `evidence_bundle`: The Stage 15L `DecisionEvidenceBundle`
- `explanation`: The Stage 15L `DecisionExplanation`

## DecisionProvenance

`DecisionProvenance` holds optional metadata about report generation context:

- `generated_by`: Identifies the generating system or user
- `generation_timestamp`: ISO timestamp of generation (for audit only)
- `audit_id`: Optional audit tracking identifier
- `metadata`: Arbitrary key-value audit metadata

**Provenance metadata is AUDIT-ONLY. It does NOT participate in the deterministic
decision identity. The same inputs with different provenance MUST produce
byte-identical reports.**

## ToleranceDecisionReport

`ToleranceDecisionReport` is the frozen, immutable report model containing:

- `schema_version`: Stable schema identifier (`origlyph.tolerance.decision_report.v1`)
- `final_status`: The authoritative `ToleranceDecisionStatus`
- `is_complete`: Boolean completeness flag
- `summary_code` and `summary_text`: Human-readable summary from Stage 15L
- `governing_reason_codes`, `marginal_reason_codes`, `supporting_reason_codes`: Reason groupings
- `triggered_reasons`: Detailed reason references with evidence links
- `contributors`: Contributor table from authoritative sources
- Section metrics (worst_case, statistical, correlation, sensitivity, budget, allocation, reconciliation)
- `evidence_refs`: Evidence item references
- `equality_tolerance`: Authoritative equality tolerance value
- `provenance`: Optional provenance metadata (excluded from decision identity)

## Schema Version

`REPORT_SCHEMA_VERSION = "origlyph.tolerance.decision_report.v1"`

This is a stable schema identifier independent of the package version.
Changes only when the report contract itself changes.

## Deterministic Decision ID

The report provides `decision_id()` which returns a deterministic hash of the
report contents. **Provenance metadata is excluded from the identity calculation.**

The same authoritative inputs always produce the same decision ID.

## Canonical Serialization

`ToleranceDecisionReport.as_dict()` produces a deterministic, byte-stable dictionary.
`to_json()` produces deterministic JSON using stdlib only (no external dependencies).

Serialization does NOT turn geometry into manufacturing semantics. Report serialization
does not introduce manufacturing feature boundaries.

## Round-Trip Contract

`decision_report_from_dict(data)` reconstructs a `ToleranceDecisionReport` from a dict.

Round-trip produces an equal report:

```python
report = decision_report_from_dict(original.as_dict())
assert report == original
```

## Evidence Preservation

The report preserves evidence references verbatim from Stage 15L:

- Evidence IDs
- Source types
- Evidence codes
- Reason code associations

No evidence is recomputed or regenerated.

## Explanation Preservation

The report preserves the Stage 15L explanation:

- Summary code
- Summary text
- Final status (must match decision)
- Completeness flag (must match evidence bundle)

## Deterministic Identity vs Optional Provenance

The decision ID is computed EXCLUDING provenance:

```python
report_no_prov = build_decision_report(result, bundle, exp, provenance=None)
report_with_prov = build_decision_report(result, bundle, exp, provenance=prov)
assert report_no_prov.decision_id() == report_with_prov.decision_id()
```

This ensures audit metadata does not alter the engineering decision identity.

## Fail-Closed Consistency Rules

The report builder fails closed (`InvalidDecisionReportError`) when:

- Decision status != Evidence bundle status
- Decision completeness != Evidence bundle completeness
- Explanation status != Decision status
- Explanation completeness != Evidence bundle completeness
- Evidence ID referenced by reason does not exist in bundle
- Reason has evidence but no matching evidence code
- Equality tolerance is missing or non-finite
- Schema version is unsupported

## No Engineering Recomputation

The report NEVER recomputes:

- Worst-case spans
- Statistical sigma values
- Covariance propagation
- Budget compliance checks
- Allocation validation
- Reconciliation calculations
- Decision status logic
- Evidence derivation

All values are taken verbatim from the authoritative Stage 15K/15L inputs.

## Geometry / Manufacturing Boundary

Report serialization does not turn geometry into manufacturing semantics.
The report preserves geometry identifiers as provided by upstream engines.

## Non-Goals

- The report does NOT generate engineering recommendations
- The report does NOT optimize allocations
- The report does NOT replace underlying engines
- The report is NOT an AI recommendation system

## Zero New Runtime Dependencies

Stage 15M introduces NO new runtime dependencies. All dependencies are stdlib:

- `json` (stdlib)
- `math` (stdlib)
- `dataclasses` (stdlib)
- `enum` (stdlib)
- `typing` (stdlib)

## API Surface

### Constants
- `REPORT_SCHEMA_VERSION`: Stable schema identifier

### Models
- `DecisionInputs`: Immutable input container
- `DecisionProvenance`: Optional provenance metadata
- `ReportSection`: Enum of report sections
- `ReportMetricValue`: Immutable metric with optional bounds
- `ReportReasonRef`: Immutable reason reference
- `ReportEvidenceRef`: Immutable evidence reference
- `ReportContributor`: Immutable contributor entry
- `ToleranceDecisionReport`: Frozen report model

### Exceptions
- `InvalidDecisionReportError`: Raised on consistency failures

### Functions
- `build_decision_report(decision_result, evidence_bundle, explanation, provenance=None)`
- `build_tolerance_decision_report(...)`: Alias for backward compatibility
- `decision_report_from_dict(data)`: Round-trip reconstruction

## Testing Requirements

Tests verify:

- Schema version exact value
- Frozen/immutable models
- Required API presence
- Deterministic decision ID
- Provenance excluded from identity
- Input change alters decision ID
- `as_dict()` determinism
- `to_json()` determinism
- Round-trip exact equality
- Enum serialization stability
- Evidence preservation
- Explanation preservation
- Fail-closed consistency checks
- Non-finite value rejection
- No timestamps in schema
- No UUIDs in models
- No engineering recomputation

---

*AI does not override deterministic tolerance calculations.*
