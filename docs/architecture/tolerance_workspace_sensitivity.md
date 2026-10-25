# Stage 17C — Tolerance Sensitivity UI Foundation

## Purpose

Stage 17C adds an explicit, deterministic sensitivity analysis surface to the
tolerance workspace.  After configuring contributors and running analysis, the
user can explicitly run sensitivity analysis and inspect ranked contributor
impact.  Every sensitivity value is produced by the Stage 15F sensitivity
API; no threshold logic, normalization formula, or ranking rule is duplicated
in the workspace layer.

## Sensitivity Authority API

All sensitivity values originate exclusively from the Stage 15F functions:

| Analysis mode      | Delegated to                    |
|--------------------|---------------------------------|
| `worst_case`       | `worst_case_sensitivity(stack)` |
| `rss_statistical`  | `statistical_sensitivity(stack, sigma_multiplier=1.0, correlations=())` |

The workspace controller is a thin delegation layer: it validates preconditions,
selects the mode-specific stack, and stores the returned result.  It never
reimplements engineering formulas.

The sigma multiplier used for RSS sensitivity matches the workspace analysis
multiplier (`_DEFAULT_SIGMA_MULTIPLIER = 1.0`) so that the sensitivity values
are consistent with the displayed analysis result.

## Supported Metrics

### Worst-case mode (`WorstCaseSensitivityResult`)

Per contributor (`WorstCaseContributionImpact`):

| Field      | Meaning                                                    |
|------------|------------------------------------------------------------|
| `name`     | Contributor identifier (traceability)                      |
| `span`     | Non-negative tolerance span in stack space                 |
| `fraction` | `span / total_span`; 0.0 when total_span is zero           |
| `percentage` | `fraction × 100`                                         |

Ranking: descending `span`; ties preserve original contributor order.

### RSS statistical mode (`StatisticalSensitivityResult`)

Per contributor (`StatisticalContributionImpact`):

| Field      | Meaning                                                          |
|------------|------------------------------------------------------------------|
| `name`     | Contributor identifier                                           |
| `sigma`    | Contributor standard deviation as supplied                       |
| `variance` | Individual variance term `a_i² σ_i²` (always ≥ 0)               |
| `fraction` | `variance / total_variance`; 0.0 when variance is negligible    |
| `percentage` | `fraction × 100`                                               |

Ranking: descending `variance`; ties preserve original contributor order.

Covariance pairs are available in the result object but are not currently
surfaced in the UI (the workspace has no correlation mechanism).

## Execution Behavior

Sensitivity evaluation is triggered only by an explicit user action
("Run Sensitivity" button or `controller.run_sensitivity()` call).

Evaluation requires at least one contributor.  The controller fails closed
on this precondition: it raises `InvalidToleranceWorkspaceError` rather than
fabricating a result.

Sensitivity does NOT require a prior call to `run_analysis()`.  The Stage 15F
functions call the authoritative engine internally.

No implicit `run_analysis()` occurs to support sensitivity evaluation.

## Invalidation Semantics

Any authoritative engineering change that affects the contributor stack or
analysis mode clears the cached sensitivity result immediately:

| Change                          | Clears `last_sensitivity` |
|---------------------------------|---------------------------|
| Contributor add / edit / remove | Yes                       |
| Chain name change               | Yes                       |
| Analysis mode change            | Yes                       |
| Specification change            | **No** (spec-independent) |
| `run_analysis()` called         | **No** (result-independent) |

Sensitivity depends only on the contributor stack and analysis mode, not on
the specification limits or the cached analysis result.  Spec-only mutations
and re-running analysis do not clear the sensitivity cache.

The UI never shows stale sensitivity data.  After any invalidating change the
sensitivity treeview is cleared by `_refresh_sensitivity()`.  No automatic
re-evaluation occurs.

## Relationship to Analysis and Decision

Three distinct derived evidence types exist in the workspace:

| Type                | API call          | Persisted |
|---------------------|-------------------|-----------|
| Analysis result     | `run_analysis()`  | No        |
| Decision result     | `evaluate_decision()` | No    |
| Sensitivity result  | `run_sensitivity()` | No      |

Sensitivity is explanatory evidence; it has no authority over PASS/FAIL.
Running sensitivity does not alter `last_decision`.  Running decision does
not alter `last_sensitivity`.  The Stage 15K decision API remains the sole
PASS/FAIL authority.

## Persistence Boundary

The sensitivity result is **runtime-derived only**.  It is not persisted in
the project file.

- Authoritative engineering inputs (contributors, mode, specification) are
  persisted under the workspace schema.
- Derived evidence (analysis result, decision result, sensitivity result) is
  recomputed on demand.

Loading a project clears `last_sensitivity`.  A loaded controller always
starts with `last_sensitivity = None`.

No project schema change is required.  The workspace schema remains
`origlyph.tolerance.workspace.v2`.

## Identity Boundary

Sensitivity output is derived evidence only.  It must not become an
authoritative engineering input.

Running sensitivity does not alter the workspace's configuration identity.
The same engineering configuration before and after running sensitivity
retains the same `workspace_configuration_fingerprint()`.

## UI Scope

The "Sensitivity" labelframe contains:

- A "Run Sensitivity" button (explicit trigger only)
- A read-only treeview with columns: Rank, Contributor, Impact, Share %

The view and the session seam (`WorkspaceSession`) carry no independent
sensitivity logic.  The treeview is populated from `session.sensitivity_rows()`,
which reads `controller.last_sensitivity` and formats it.  The view cannot
fabricate sensitivity values.

Flow:

```
Tkinter widgets
    → WorkspaceSession.run_sensitivity()
        → ToleranceWorkspaceController.run_sensitivity()
            → worst_case_sensitivity() / statistical_sensitivity() [Stage 15F]
```

## Exclusions

- No advanced plotting or charting library
- No 3D visualization
- No AI-generated recommendations
- No optimization suggestions
- No speculative engineering advice
- No covariance-pair display (workspace has no correlation mechanism)
- No new dependency introduced

## Deterministic Nature

The sensitivity analysis is deterministic, traceable, and reproducible from
the same inputs.  The verdict is not AI-generated, probabilistic, or heuristic.

## Stage 15 Engine Freeze

Stage 17C does not modify any Stage 15 engine file (`sensitivity.py`,
`worst_case.py`, `statistical.py`, `decision.py`, etc.).  The Stage 15F
sensitivity API is called as-is; its mathematical semantics are unchanged.
