# Origlyph AI — Canonical Decision Evidence & Explainability

Stage 15L adds a deterministic evidence and explainability layer on top
of the Stage 15K deterministic tolerance decision layer.

## 1. Purpose

The Stage 15K decision layer produces a deterministic engineering
status (`PASS`, `MARGINAL`, `FAIL`, `INCOMPLETE`) together with a
typed list of triggered reason observations.  Stage 15L answers the
question **"why did Origlyph produce this deterministic tolerance
decision?"** by exposing a typed, ordered, serializable evidence
bundle that links every triggered reason to one or more concrete
evidence items carrying the authoritative source values.

## 2. Relationship to CER

Stage 15L lives **above** the decision layer.  It consumes the
authoritative Stage 15K result, the six Stage 15L source-snapshot
tuples that preserve the data needed for explainability, and
emits a structured evidence / explanation object that can be
serialized and audited.  Stage 15L never recomputes any engineering
result; it only organizes already-authoritative observations.

## 3. Geometry vs Topology

Not applicable in the same way as CAD geometry / topology.  Stage 15L
preserves the same separation of concerns as Stage 15K:

- **Decision evidence** is the structured numeric observation
  (actual, reference, margin, comparison).
- **Decision topology** is the linkage of triggered reasons to
  evidence items and the deterministic ordering of those items.

Evidence is not conflated with reasoning; the two are linked by
stable reason codes.

## 4. Units

No new unit system is introduced.  Stage 15L preserves the
authoritative numeric values passed through from Stage 15K
(`worst_case_actual_span`, `statistical_actual_combined_sigma`, etc.).
All numerics are floating-point and use the Stage 15K equality
policy (`1e-12`) when computing the `DecisionComparison` enum.

## 5. Canonical Sources, Comparisons, and Evidence Codes

Stage 15L introduces three stable enums whose string values are the
authoritative serialization identity:

- `DecisionEvidenceSource` — provenance of one piece of evidence
  (`worst_case`, `statistical`, `correlated_statistical`,
  `sensitivity`, `budget`, `allocation`,
  `worst_case_reconciliation`, `statistical_reconciliation`,
  `decision`, `structural`).
- `DecisionComparison` — comparison state of observed vs reference
  (`less_than`, `at_boundary`, `greater_than`, `not_applicable`).
- `DecisionEvidenceCode` — stable technical codes that identify one
  observation (e.g. `wc_span_exceeds_limit`,
  `covariance_increases_variance`, `allocation_missing_contributors`).

## 6. Evidence Item

`DecisionEvidenceItem` is a frozen dataclass carrying:

- `evidence_id` — deterministic identifier
  (`source:code:scope:subject:index`).
- `evidence_code` — stable technical code.
- `source` — `DecisionEvidenceSource`.
- `scope` — optional scope label (e.g. `worst_case_requirement`).
- `subject_id` — optional subject (e.g. a contributor name, a
  canonical pair, or a missing contributor ID).
- `reason_code` — the Stage 15K `ToleranceDecisionReasonCode` this
  item explains, when applicable.
- `observed_value` / `reference_value` — exact authoritative
  numerics, or `None` for structural evidence.
- `comparison` — `DecisionComparison` (e.g. `GREATER_THAN` for a
  hard failure).
- `severity` — `ToleranceDecisionSeverity` (`FAILURE`,
  `BOUNDARY`, `INFO`).
- `detail` — deterministic text with values
  (`"actual=0.45 allowed=0.4"`).
- `metrics` — sorted, unique-keyed `DecisionMetric` entries for
  retained numerics (margin, utilization, rank, fraction,
  percentage, independent sigma, rho, equality tolerance,
  variance).

NaN, infinities and booleans are rejected at the metric and value
boundaries.  Numeric values are never rounded.

## 7. Deterministic Evidence ID

Evidence IDs are deterministic and contain no timestamps, UUIDs,
random values or object memory addresses.  The format is
`source:code:scope:subject:index`, where `index` is the stable
build-order index used as a tiebreaker.  Repeated calls on the same
decision result produce identical IDs and identical ordering.

## 8. Evidence Bundle

`DecisionEvidenceBundle` is a frozen container that exposes:

- `decision_status` — the authoritative Stage 15K status.
- `is_complete` — copied from the decision result.
- `evidence_items` — deterministically ordered evidence items.
- `reason_to_evidence` — `ReasonEvidenceLink` list mapping each
  triggered reason to the evidence IDs that explain it.
- `governing_evidence_ids` — all hard-failure / incomplete-structural
  evidence IDs (severity = `FAILURE`).
- `marginal_evidence_ids` — all boundary evidence IDs
  (severity = `BOUNDARY`).
- `governing_evidence`, `marginal_evidence`, `supporting_evidence`
  properties — typed convenience views.
- `primary_governing_evidence` — first governing evidence item.

## 9. Reason Linkage

Every triggered Stage 15K reason is linked to at least one evidence
item, except for `NO_REQUIREMENT_PROVIDED`, which is documented as
non-evidentiary.  Reason linkage is scope-aware with a documented
set of scope-agnostic reasons
(`INCOMPLETE_ALLOCATION`, `WC_STAT_INCONSISTENT`, the three
`CORRELATION_*` reasons) whose evidence items carry a global scope.
If a triggered reason has no matching evidence item, building the
bundle fails closed with
`InvalidDecisionEvidenceError`.

## 10. Governing Evidence

`governing_evidence_ids` contains every hard-failure evidence item,
in deterministic order.  `primary_governing_evidence` exposes the
first such item, and is also the first item in `evidence_items`
(severity ordering outranks source ordering).  Multiple hard
failures are all retained; nothing is hidden.

## 11. Evidence Ordering

`evidence_items` is ordered by:

1. severity priority (`FAILURE`, `BOUNDARY`, `INFO`),
2. evidence-source priority
   (`WORST_CASE`, `STATISTICAL`, `CORRELATED_STATISTICAL`,
   `SENSITIVITY`, `BUDGET`, `ALLOCATION`,
   `WORST_CASE_RECONCILIATION`, `STATISTICAL_RECONCILIATION`,
   `DECISION`, `STRUCTURAL`),
3. `scope` ascending,
4. `subject_id` ascending,
5. `evidence_code` ascending,
6. stable build-order index as final tiebreaker.

Repeated calls produce identical ordering.

## 12. Numeric Traceability

For every numeric evidence item, the original authoritative values
are preserved exactly.  Examples:

- Worst-case requirement: `observed_value = actual_span`,
  `reference_value = allowed_span`, `metrics` include
  `remaining_margin`, `utilization`, `equality_tolerance`.
- Statistical requirement: `observed_value = actual_combined_sigma`,
  `reference_value = allowed_combined_sigma`, `metrics` include
  `remaining_margin`, `utilization`,
  `independent_combined_sigma`, `equality_tolerance`.
- Budget and reconciliation items retain margin, utilization, and
  rank.

## 13. Correlated Statistical Evidence

When correlations are supplied, per-pair evidence items are emitted
with the canonical pair subject (`first|second`), the signed
`covariance_term` as `observed_value`, the `rho` metric, and the
signed `comparison` (`GREATER_THAN` for positive,
`LESS_THAN` for negative, `AT_BOUNDARY` for zero).  The combined-sigma
correlation effect is exposed separately by the correlation-reason
item, with `actual` and `independent` sigma and the
`CORRELATION_INCREASES_SIGMA` /
`CORRELATION_DECREASES_SIGMA` /
`CORRELATION_EFFECTIVELY_NEUTRAL` evidence codes.

Pairwise covariance is never assigned exclusively to one contributor,
and the sign of the contribution is never flipped.

## 14. Sensitivity Evidence

Sensitivity evidence items are emitted for every controlling
contributor (sorted by fraction descending, ties broken by name
ascending) with the rank, span / sigma, fraction, percentage and
(for statistical sensitivity) variance.  Sensitivity explains
contribution; it is supporting evidence only and never a design
recommendation.

## 15. Budget Evidence

Budget evidence items retain:

- `observed_value` (actual span or actual combined sigma),
- `reference_value` (allowed span or allowed combined sigma),
- `comparison`,
- `metrics.remaining_margin`, `metrics.utilization`,
- `metrics.equality_tolerance`.

Worst-case and statistical budgets are emitted as separate
items (one per dimension).

## 16. Allocation Evidence

Allocation evidence emits the per-plan total-vs-allowed comparison
as well as per-contributor reconciliation items.  Missing
contributors are emitted as structural evidence (severity
`FAILURE`, code `allocation_missing_contributors`), scoped globally
so they can be linked from any `INCOMPLETE_ALLOCATION` reason.
Allocation validity does not imply engineering compliance; both
are exposed independently.

## 17. Reconciliation Evidence

Worst-case and statistical reconciliation are kept strictly
separate.  Each emits per-contributor evidence with actual vs
allocated values, signed margin, status, rank, and (for WC) a
utilization metric.  Per-reconciliation totals are exposed in the
Stage 15K dimension evidence, not aggregated into the per-contributor
items.

## 18. Decision Explanation

`DecisionExplanation` is a frozen structured explanation that
exposes:

- `final_status` — `ToleranceDecisionStatus`.
- `summary_code` — deterministic code, e.g. `fail:wc_span_exceeds_limit`.
- `governing_reasons` — `ToleranceDecisionReasonCode` list.
- `governing_evidence`, `marginal_evidence`, `supporting_evidence`.
- `is_complete` — copied from the bundle.
- `summary` — deterministic fixed-template sentence (no LLM, no
  generative wording, no stochastic text).

## 19. Public API

```python
from origlyph.tolerance import (
    DecisionComparison,
    DecisionEvidenceBundle,
    DecisionEvidenceCode,
    DecisionEvidenceItem,
    DecisionEvidenceSource,
    DecisionExplanation,
    DecisionMetric,
    ReasonEvidenceLink,
    build_decision_evidence,
    explain_tolerance_decision,
)
```

`build_decision_evidence(decision_result)` and
`explain_tolerance_decision(decision_result, evidence_bundle=None)`
are the only public functions.

## 20. Fail-Closed Policy

If authoritative source data required to support a triggered reason
is missing, building the bundle raises
`InvalidDecisionEvidenceError` instead of fabricating evidence.
Examples of fail-closed paths include:

- A `ToleranceDecisionReason` whose code has no evidence mapping.
- A dimension with a numeric state but missing `actual` or
  `allowed` values.
- A controlling-contributor name in `sensitivity` whose
  corresponding snapshot is absent.
- A correlation reason without authoritative
  `actual` / `independent` sigma values.

## 21. Determinism

Repeated evaluation of the same decision result produces:

- identical evidence IDs,
- identical ordering,
- identical serialization,
- identical explanation summary code and summary text.

No timestamps, UUIDs, random values, monotonic clocks or
`time.time()` participate in any identity or value.

## 22. Example — FAIL Decision

For a hard worst-case failure (`actual_span = 0.45`,
`allowed_span = 0.40`):

```
status: FAIL
governing: wc_span_exceeds_limit
  observed: 0.45
  reference: 0.40
  margin: -0.05
  utilization: 1.125
summary: Decision fail: governed by wc_span_exceeds_limit
  (observed 0.45, reference 0.4).
```

## 23. Example — Cylinder Is Not A Manufacturing Hole

Stage 15L explains geometric and statistical observations.  It does
not classify any geometry as a manufacturing feature.  A geometric
cylinder (or any other canonical surface) appears in the evidence
bundle as a structural or numeric observation only; whether it is a
hole, a turned diameter, a boss or any other feature is a Stage 4D+
decision outside Stage 15L.

## 24. Non-Goals

Stage 15L is representation, not geometric healing.  It does not
implement: tolerance redistribution, automatic corrective action,
optimization, recommendations, AI-generated explanations, LLM text,
RAG, stochastic wording, cost optimization, Monte Carlo, nonlinear
propagation, 3D tolerance analysis, GD&T semantics, CAD tolerance
extraction, Cp/Cpk, report / PDF generation, GUI, web API or
database persistence.

## 25. Relationship to Stage 15C and Beyond

Stage 15L is the evidence / explainability layer for the existing
deterministic decision engine.  It depends only on the Stage 15K
public API and the six Stage 15L source-snapshot tuples, and is
consumed by future reporting and audit layers.



