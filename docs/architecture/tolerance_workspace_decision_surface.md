# Stage 17B — Deterministic Tolerance Decision Surface

## Purpose

Stage 17B adds an explicit, deterministic decision surface to the tolerance
workspace.  The user can configure contributors and specification limits, run
analysis, and then explicitly evaluate a PASS / FAIL / NOT EVALUATED verdict.
Every verdict is produced by the Stage 15K decision API; no threshold logic is
duplicated in the workspace layer.

## Decision Authority

All PASS / FAIL verdicts originate exclusively from
`origlyph.tolerance.evaluate_tolerance_decision` (Stage 15K).  The workspace
controller is a thin delegation layer: it validates preconditions, selects the
mode-specific stack and limit, and stores the returned
`ToleranceDecisionResult`.  It never reimplements engineering formulas.

The verdict is **not** AI-generated, probabilistic, or heuristic.  It is
deterministic, traceable, and reproducible from the same inputs.

## Mode-Specific Specification Mapping

| Analysis mode      | Required specification field    | Passed to Stage 15K as          |
|--------------------|---------------------------------|---------------------------------|
| `worst_case`       | `allowed_worst_case_span`       | `allowed_worst_case_span`       |
| `rss_statistical`  | `allowed_combined_sigma`        | `allowed_combined_sigma`        |

Cross-mode limits are not interchangeable:

- A worst-case limit must not authorize an RSS decision.
- An RSS sigma limit must not authorize a worst-case decision.

## Explicit Evaluation Behavior

Decision evaluation is triggered only by an explicit user action
("Evaluate Decision" button or `controller.evaluate_decision()` call).

Evaluation requires:

1. Analysis has been run (`controller.last_result` is not None).
2. The applicable specification limit for the active mode is present.

The controller fails closed on either precondition: it raises
`InvalidToleranceWorkspaceError` rather than fabricating a verdict.  The UI
surfaces the error through the guard; the decision display stays "NOT
EVALUATED".

The sigma multiplier used for RSS decision evaluation matches the workspace
analysis multiplier (`_DEFAULT_SIGMA_MULTIPLIER = 1.0`) so that the "Actual"
value shown in the decision is consistent with the analysis result.

## Invalidation Semantics

Any authoritative engineering change clears both the cached analysis result and
the cached decision result immediately:

| Change                      | Clears `last_result` | Clears `last_decision` |
|-----------------------------|----------------------|------------------------|
| Contributor add / edit / remove | Yes              | Yes                    |
| Chain name change           | Yes                  | Yes                    |
| Analysis mode change        | Yes                  | Yes                    |
| Specification change        | Yes                  | Yes                    |
| `run_analysis()` called     | (replaces)           | Yes                    |

No-op mutations (setting the same value) do not clear either cache.

The UI never shows PASS or FAIL after any of these changes.  The decision
display reverts to "NOT EVALUATED" immediately.  No automatic re-evaluation
occurs.

## UI Authority Boundary

The Tkinter view (`ToleranceWorkspaceView`) and the session seam
(`WorkspaceSession`) carry no independent PASS / FAIL logic.  The display
reads `controller.last_decision.overall_status` and formats it.  The view
cannot fabricate a verdict.

Flow:

```
Tkinter widgets
    → WorkspaceSession.evaluate_decision()
        → ToleranceWorkspaceController.evaluate_decision()
            → evaluate_tolerance_decision() [Stage 15K]
```

The session exposes two read-only presentation properties:

- `decision_text`: "PASS" / "FAIL" / "MARGINAL" / "INCOMPLETE" / "NOT EVALUATED"
- `decision_detail_text`: "Actual: … Limit: … Margin: … Reason: …"

Both derive purely from `controller.last_decision`.

## Persistence Boundary

The decision result is **runtime-derived only**.  It is not persisted in the
project file.

- Authoritative engineering inputs (contributors, mode, specification) are
  persisted under the workspace schema.
- Derived evidence (analysis result, decision result) is recomputed on demand.

Loading a project clears `last_decision`.  A loaded controller always starts
with `last_decision = None`.

No project schema change is required.  The workspace schema remains
`origlyph.tolerance.workspace.v2`.

## Identity Implications

Specification remains identity-bearing engineering state.  Changing the
specification changes the project identity.  A stale decision result cannot
survive an authoritative mutation — the controller clears `_last_decision`
whenever state changes.

## Missing Specification Never Means PASS

If the applicable specification limit is absent, `evaluate_decision()` raises
rather than producing an INCOMPLETE result that the caller might misread as
acceptable.  The UI shows "NOT EVALUATED" for this case.

## Stage 15 Engine Freeze

Stage 17B does not modify any Stage 15 engine file (`worst_case.py`,
`statistical.py`, `decision.py`, etc.).  The Stage 15K decision API is called
as-is; its mathematical semantics are unchanged.
