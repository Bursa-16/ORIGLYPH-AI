# Tolerance Workspace Governance State Restoration

**Stage:** 21G  
**Component:** `ToleranceWorkspaceController.restore_governance_state`

---

## Motivation

After saving and reopening an Origlyph project file, all computed governance artifacts
are absent: the project file persists only authoritative inputs
(`chain_name`, `contributors`, `specification`, `allocation_plan`,
`statistical_allocation_plan`, `acceptance_state`), not the runtime-derived
outputs. Users who need the full governance chain available immediately after
reopening a project would otherwise have to re-run each step manually in the
correct order.

`restore_governance_state` provides a single explicit action that regenerates
the entire runtime governance chain from persisted authoritative inputs,
deterministically and without altering any persisted state.

---

## Authoritative vs Derived State

| State | Persisted? | Restored by `restore_governance_state`? |
|---|---|---|
| `chain_name` | Yes | — (input) |
| `contributors` | Yes | — (input) |
| `specification` | Yes | — (input) |
| `allocation_plan` | Yes | — (input) |
| `statistical_allocation_plan` | Yes | — (input) |
| `acceptance_state` (decision / authority_reference / decision_reference / handoff_id) | Yes | — (input) |
| `last_result` | No | Yes |
| `last_decision` | No | Yes |
| `last_evidence` | No | Yes |
| `last_decision_report` | No | Yes |
| `last_audit_integrity` | No | Yes |
| `last_audit_package` | No | Yes |
| `comparison_audit_package` | No | Yes (if comparison_path supplied) |
| `last_audit_comparison` | No | Yes (if comparison_path supplied) |
| `last_change_impact` | No | Yes (if comparison_path supplied) |
| `last_change_disposition` | No | Yes (if comparison_path supplied) |
| `last_approval_readiness` | No | Yes (if comparison_path supplied) |
| `last_acceptance_handoff` | No | Yes (if comparison_path supplied) |
| `last_acceptance_record` | No | Yes (if comparison_path and acceptance_state supplied) |
| `last_acceptance_verification` | No | Yes (if comparison_path and acceptance_state supplied) |
| `last_acceptance_closure` | No | Yes (if comparison_path and acceptance_state supplied) |

---

## Restore Sequence

```
Pre-validate prerequisites
    │
    ├── Requires: at least one contributor
    ├── Requires: specification set
    └── If comparison_path supplied: file must exist
    │
Capture acceptance_state reference (_acc_before)
    │
_clear_all_governance_runtime_state()          ← fail-safe: clears all 21 fields
    │
run_analysis()
evaluate_decision()
run_decision_evidence()
run_decision_report()
run_audit_integrity()
run_audit_package()
    │
If comparison_path is None → STOP HERE
    │
load_comparison_audit_package(comparison_path)
run_audit_comparison()
run_change_impact()
run_change_disposition()
run_approval_readiness()
run_acceptance_handoff()
    │
If acceptance_state is None → STOP HERE
    │
run_acceptance_record()
run_acceptance_verification()
run_acceptance_closure()
    │
Assert: acceptance_state == _acc_before       ← invariant check
```

---

## Prerequisites

### Always Required

- **At least one contributor** — the analysis and audit chain requires
  at least one tolerance entry to compute.
- **Specification** — `allowed_worst_case_span` or `allowed_combined_sigma`
  must be set; without a specification the decision engine cannot evaluate
  the tolerance stack.

### Required for Comparison-Dependent Chain

- **Comparison audit package file** — the caller must supply an external
  `.json` file produced by a prior audit package export. The file is
  deserialized and fingerprint-verified before the chain continues.
- **`acceptance_state`** — when present, the restore chain continues through
  acceptance record, verification, and closure. When absent, the chain stops
  after `run_acceptance_handoff`.

---

## Optional Comparison Behavior

When `comparison_path` is `None`, restoration stops after `run_audit_package`.
The comparison-dependent chain (audit comparison → change impact → change
disposition → approval readiness → acceptance handoff → acceptance record →
acceptance verification → acceptance closure) requires an external comparison
file and is not regenerated without one.

No comparison data is substituted, synthesised, or silently fabricated.

---

## Fail-Closed

All derived runtime state is cleared atomically at the start of restoration
(before any chain step runs). If any chain step raises, the cleared state
remains — no misleadingly partial governance chain is left in place.
The caller receives the exception from the failing step.

Stale comparison state (from a prior load) is also cleared during
`_clear_all_governance_runtime_state`, so a failed restore starting with a
comparison file cannot leave residue from a previous comparison.

---

## Stale-State Clearing

`_clear_all_governance_runtime_state` clears all 21 derived runtime fields
before rebuilding:

```
_last_result, _last_decision, _last_sensitivity, _last_budget,
_last_allocation_validation, _last_reconciliation,
_last_statistical_reconciliation, _last_evidence, _last_explanation,
_last_decision_report, _last_audit_integrity, _last_audit_package,
_comparison_audit_package, _last_audit_comparison, _last_change_impact,
_last_change_disposition, _last_approval_readiness,
_last_acceptance_handoff, _last_acceptance_record,
_last_acceptance_verification, _last_acceptance_closure
```

This guarantees that old artifacts (e.g., from a prior chain run before save)
are never visible after a restore starts, even if the restore fails partway through.

---

## Project Identity Invariance

`restore_governance_state` never mutates `WorkspaceState` (the authoritative
project record). The `configuration_fingerprint` is identical before and after
restoration. `acceptance_state` fields (`decision`, `authority_reference`,
`decision_reference`, `handoff_id`) are invariant inputs — the method asserts
this via `assert self._state.acceptance_state == _acc_before` as a final guard.

No new project file is written, no sidecar artifact files are created.

---

## Acceptance Input Protection

`restore_governance_state` reads `acceptance_state.handoff_id` from the
persisted project record as an input to `run_acceptance_record`, which
validates it against the restored `last_acceptance_handoff`. If the two IDs
do not match (engineering state changed since acceptance was recorded),
`run_acceptance_record` raises `InvalidToleranceWorkspaceError`. This is
the expected fail-closed behaviour — no acceptance decision is fabricated
or silently substituted.

---

## Determinism

Given the same authoritative project inputs and the same comparison file,
`restore_governance_state` produces byte-identical runtime artifacts on
every invocation. The `handoff_id`, audit package `fingerprint`, and all
chain outputs are determined entirely by inputs — no random values, no
timestamps, no hostname or username are incorporated.

---

## Explicit-Only Activation

`restore_governance_state` is never called automatically on project open.
The UI provides a "Restore Governance State" button in the Project File
labelframe; the user is prompted whether to supply a comparison file before
the restore chain runs.

---

## Limitations

- `_last_sensitivity`, `_last_budget`, `_last_allocation_validation`,
  `_last_reconciliation`, and `_last_statistical_reconciliation` are cleared
  by `_clear_all_governance_runtime_state` but are not regenerated by
  `restore_governance_state`. These require separate analysis runs.
- The comparison file is an external artifact not stored in the project file.
  The caller is responsible for supplying the correct file.
- If `acceptance_state.handoff_id` does not match the restored chain's
  `handoff_id`, the acceptance record step raises. This indicates that the
  persisted acceptance state references a different engineering configuration
  than the one being restored; the acceptance state must be updated.

---

## Non-Goals

- **Not** a rollback or undo mechanism.
- **Not** a snapshot of computed artifacts — no sidecar files.
- **Not** automatic — never triggered by project open or save.
- **Not** a schema migration — the workspace schema is not changed.
- **Not** a recomputation of sensitivity, budget, or allocation validation.

---

## Core Principle

> Governance restoration deterministically regenerates runtime-derived
> artifacts from persisted authoritative project inputs and explicitly
> supplied external artifacts. It does not persist derived governance
> state or fabricate missing engineering or acceptance inputs.
