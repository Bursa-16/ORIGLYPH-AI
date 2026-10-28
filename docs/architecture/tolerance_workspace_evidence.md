# Tolerance Workspace — Decision Evidence & Explanation

## Purpose

The Decision Evidence & Explanation surface exposes the Stage 15L deterministic evidence layer
through the tolerance workspace UI. It allows an engineer to inspect the full set of evidence
items that underlie a tolerance decision result, along with a structured explanation of that
decision, without leaving the workspace.

## Explicit Workflow

1. Engineer configures contributors and specification.
2. Engineer runs Analysis (`run_analysis`).
3. Engineer runs Decision (`evaluate_decision`).
4. Engineer clicks **Generate Evidence** in the workspace UI.
5. The workspace calls `run_decision_evidence()` on the controller.
6. The controller delegates to Stage 15L: `build_decision_evidence(decision)` then
   `explain_tolerance_decision(decision, bundle)`.
7. Evidence bundle and explanation are cached as runtime-only state on the controller.
8. The UI presents: decision status, explanation summary, and the full evidence item table.

Evidence is not persisted. It is always re-derived from the current decision result.

## Stage 15 Authority

Decision evidence and explanation are produced exclusively by the Stage 15L engine functions:

- `build_decision_evidence(decision_result: ToleranceDecisionResult) → DecisionEvidenceBundle`
- `explain_tolerance_decision(decision_result, evidence_bundle) → DecisionExplanation`

The workspace controller, session, and UI are consumers only. They do not duplicate decision
logic, create PASS/FAIL outcomes independently, infer reasons, fabricate evidence, reinterpret
severity, invent recommendations, or add AI-generated explanations.

**Decision evidence explains and preserves deterministic decision reasoning. It does not replace
engineering judgment and does not constitute approval, certification, or autonomous engineering
decision-making.**

## Evidence Contract

`DecisionEvidenceBundle` fields presented in the workspace:

| Field | Meaning |
|---|---|
| `decision_status` | Overall status of the decision result (mirrors `ToleranceDecisionResult.overall_status`) |
| `is_complete` | Whether all required evidence is present |
| `evidence_items` | Ordered tuple of `DecisionEvidenceItem` |
| `governing_evidence_ids` | IDs of items that drove the final status |
| `marginal_evidence_ids` | IDs of items near the threshold |

Each `DecisionEvidenceItem` exposes: `evidence_code`, `source`, `scope`, `subject_id`,
`reason_code`, `observed_value`, `reference_value`, `comparison`, `severity`, `detail`,
`metrics`.

## Explanation Contract

`DecisionExplanation` fields presented in the workspace:

| Field | Meaning |
|---|---|
| `final_status` | Mirrors `decision_status` |
| `summary_code` | Machine-readable summary identifier |
| `summary` | Fixed-template human-readable summary string (no LLM, no free text) |
| `governing_reasons` | Reason codes that determined the final status |
| `governing_evidence` | Evidence items with governing role |
| `marginal_evidence` | Evidence items with marginal role |
| `supporting_evidence` | Evidence items with supporting role |
| `is_complete` | Whether the explanation covers all decision aspects |

## Runtime-Only Nature

Evidence and explanation are **never persisted** to the workspace schema or project file.
They are ephemeral runtime snapshots derived from `_last_decision`.

- `save_project` / `open_project`: evidence is not saved; restored controller has `last_evidence = None`.
- `from_state`: evidence is not included in state dict; restored controller has `last_evidence = None`.
- Evidence must be regenerated after every session load.

## Persistence Boundary

```
WorkspaceProject (persisted JSON)
  └── chain_name, analysis_mode, contributors, specification
  └── allocation_plan, statistical_allocation_plan
  ← last_result, last_decision, last_sensitivity, last_budget,
     last_reconciliation, last_statistical_reconciliation  (runtime, not persisted)
  ← last_evidence, last_explanation  (runtime, not persisted — Stage 20B)
```

## Identity Boundary

`run_decision_evidence()` is a read operation on `_last_decision`. It:

- Does NOT mutate `_last_decision`
- Does NOT re-run analysis
- Does NOT re-evaluate the decision
- Does NOT alter sensitivity, budget, allocation, reconciliation, or statistical reconciliation
- Does NOT change `configuration_fingerprint()`

## Stale Clearing

Evidence and explanation are cleared (set to `None`) whenever the decision result becomes
stale. Cleared in all the same locations that clear `_last_decision`:

- `set_chain_name()`
- `set_analysis_mode()`
- `set_specification()`
- `run_analysis()`
- `evaluate_decision()` (before caching the new decision)
- `_replace_contributors()`
- `from_state()` (constructor path)

## Feature Isolation

The evidence surface is fully isolated. Generating evidence has no side-effects on any
other workspace feature. All other features (sensitivity, budget, allocation, reconciliation,
statistical reconciliation) are unaffected by calling `run_decision_evidence()`.

## UI Presentation

The Evidence section appears at workspace row 11 (between Reconciliation at row 10 and
Statistical Allocation Plan at row 12) as a `ttk.Labelframe` titled
**"Decision Evidence & Explanation"**.

- **Generate Evidence** button: calls `run_decision_evidence()` and refreshes the section.
- **Status label**: shows `evidence_status_text` — `"NOT GENERATED"` if no evidence, or the
  decision status value in uppercase once generated.
- **Summary label**: shows `explanation_summary_text` — the fixed-template explanation summary.
- **Evidence table**: `ttk.Treeview` with columns: Evidence Code, Source, Scope, Observed,
  Reference, Severity, Detail. Populated from `evidence_items_rows()`.

Evidence display is refreshed automatically after every Decision run and after every full
result refresh, so status reflects the current state.

## Non-Goals

The evidence surface explicitly does NOT:

- Produce, alter, or re-derive a tolerance decision result.
- Generate recommendations beyond the fixed-template explanation summary.
- Add LLM-generated text, AI commentary, or free-form assessment.
- Persist evidence or explanation to disk.
- Export evidence to any format (export is a separate future track).
- Certify, approve, or reject an engineering design on behalf of the engineer.
- Serve as the engineering authority for tolerance calculations.
