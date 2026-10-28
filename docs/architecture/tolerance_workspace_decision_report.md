# Tolerance Workspace — Decision Report

## Purpose

The Decision Report surface exposes the Stage 15M deterministic decision report envelope
through the tolerance workspace UI. It packages the decision result, evidence bundle, and
explanation into a single auditable record that an engineer can inspect without leaving the
workspace.

## Explicit Workflow

1. Engineer configures contributors and specification.
2. Engineer runs Analysis (`run_analysis`).
3. Engineer runs Decision (`evaluate_decision`).
4. Engineer clicks **Generate Evidence** — produces `DecisionEvidenceBundle` and
   `DecisionExplanation` (Stage 15L).
5. Engineer clicks **Generate Decision Report** in the workspace UI.
6. The workspace calls `run_decision_report()` on the controller.
7. The controller delegates to Stage 15M: `build_decision_report(decision, evidence, explanation)`.
8. The report is cached as runtime-only state on the controller.
9. The UI presents: report status, summary, and the contributor table.

The report is not persisted. It is always re-derived from the current decision, evidence, and
explanation.

## Stage 15 Authority

The decision report is produced exclusively by the Stage 15M engine function:

```
build_decision_report(
    decision_result: ToleranceDecisionResult,
    evidence_bundle: DecisionEvidenceBundle,
    explanation: DecisionExplanation,
    provenance: str | None = None,
) → ToleranceDecisionReport
```

The workspace controller, session, and UI are consumers only. They do not duplicate decision
logic, create PASS/FAIL outcomes independently, infer reasons, fabricate evidence, or add
AI-generated narrative.

**Decision Report is a deterministic derived report envelope. It is not approval, certification,
or an autonomous engineering judgment.**

## Prerequisites

`run_decision_report()` requires all three upstream results to be cached:

1. `_last_decision` — must not be `None` (raised: "Run Decision first.")
2. `_last_evidence` and `_last_explanation` — must not be `None` (raised: "Generate Evidence first.")

Both checks are fail-closed: the report is never generated with missing inputs and never
silently auto-generates missing prerequisites.

## Runtime-Only Nature

Decision reports are **never persisted** to the workspace schema or project file. They are
ephemeral runtime snapshots.

- `save_project` / `open_project`: report is not saved; restored controller has
  `last_decision_report = None`.
- `from_state`: report is not included in state dict; restored controller has
  `last_decision_report = None`.
- The report must be regenerated after every session load.

## Persistence Boundary

```
WorkspaceProject (persisted JSON)
  └── chain_name, analysis_mode, contributors, specification
  └── allocation_plan, statistical_allocation_plan
  ← last_result, last_decision, last_sensitivity, last_budget,
     last_reconciliation, last_statistical_reconciliation  (runtime, not persisted)
  ← last_evidence, last_explanation  (runtime, not persisted — Stage 20B)
  ← last_decision_report  (runtime, not persisted — Stage 20C)
```

## Identity Boundary

`run_decision_report()` is a read operation on `_last_decision`, `_last_evidence`, and
`_last_explanation`. It:

- Does NOT mutate any of those three inputs
- Does NOT re-run analysis
- Does NOT re-evaluate the decision
- Does NOT regenerate evidence or explanation
- Does NOT alter sensitivity, budget, allocation, reconciliation, or statistical reconciliation
- Does NOT change `configuration_fingerprint()`

## Stale Clearing

The decision report is cleared (set to `None`) whenever evidence/explanation become stale,
which in turn occurs whenever the decision result becomes stale. Cleared in all the same
locations that clear evidence/explanation:

- `set_chain_name()`
- `set_analysis_mode()`
- `set_specification()`
- `run_analysis()`
- `evaluate_decision()` (before caching the new decision)
- `run_decision_evidence()` (before caching the new evidence — report from old evidence is stale)
- `_replace_contributors()`
- `from_state()` (constructor path)

## Feature Isolation

The report surface is fully isolated. Generating a report has no side-effects on any other
workspace feature. All other features (sensitivity, budget, allocation, reconciliation,
statistical reconciliation, evidence) are unaffected by calling `run_decision_report()`.

## UI Presentation

The Decision Report section appears at workspace row 14 (between Statistical Reconciliation at
row 13 and Project File at row 15) as a `ttk.Labelframe` titled **"Decision Report"**.

- **Generate Decision Report** button: calls `run_decision_report()` and refreshes the section.
- **Status label**: shows `report_status_text` — `"NOT GENERATED"` if no report, or the final
  status value once generated.
- **Summary label**: shows `report_summary_text` — the fixed-template decision summary.
- **Contributors table**: `ttk.Treeview` with columns: Contributor, Type, Value, Sigma.
  Populated from `report_contributors_rows()`.

## Non-Goals

The decision report surface explicitly does NOT:

- Produce, alter, or re-derive a tolerance decision result, evidence bundle, or explanation.
- Generate recommendations beyond the fixed-template summary text.
- Add LLM-generated text, AI commentary, or free-form assessment.
- Persist the report to disk.
- Export the report to any format (export is a separate future track).
- Certify, approve, or reject an engineering design on behalf of the engineer.
- Serve as the engineering authority for tolerance calculations.
- Auto-generate missing prerequisites (decision, evidence, or explanation).
