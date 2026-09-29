# Tolerance Workspace UI Foundation v1

Stage 16D adds a narrow tolerance workspace UI foundation without changing the project
schema or tolerance engines.

## Purpose

Give a single desktop surface for one 1D tolerance chain that:

* collects explicit contributor rows through a view,
* delegates every calculation to the existing deterministic engines, and
* persists the full authoritative workspace state inside a normal Origlyph project.

This is a foundation slice. It is not a CAD-integrated product surface and it introduces
no new engineering mathematics.

## Scope

In scope:

* a headless workspace controller holding validated, immutable state;
* the `worst_case` and `rss_statistical` analysis modes mapped onto existing engines;
* a thin Tkinter view organised into named areas;
* a persistence adapter that stores workspace state inside `OriglyphProject`.

Out of scope:

* project schema changes, engine changes, and additional tolerance models;
* weighted-average, sensitivity, budget, and optimisation workflows;
* CAD association, geometry import, and multi-chain documents;
* window or session restoration and any other transient UI persistence.

## Modules

* `tolerance/workspace_controller.py`: authoritative state, validation, engine
  delegation, snapshots, and fingerprints. Headless.
* `tolerance/workspace_model.py`: Tkinter view only. Imports Tk lazily and
  performs no engineering calculation.
* `project/tolerance_workspace.py`: adapter between workspace state and
  `OriglyphProject`.

## Boundaries

* The controller accepts only explicit contributor rows: identifier, display name,
  nominal value, tolerance, direction, and tolerance model.
* The only tolerance model in this slice is `symmetric`; the controller maps it to
  existing worst-case and RSS statistical engine inputs.
* The controller delegates calculations to `worst_case` and `statistical`; it does not
  duplicate formulas or infer missing engineering values.
* Tkinter code is isolated in `workspace_model.py` and imports Tk only when the view is
  constructed, so importing `origlyph.tolerance` never requires a display.
* The view never computes an engineering value. It formats the summary it receives.
* Every action commits the header fields into the controller first, so the controller is
  the only source of truth at the moment an action runs.

## State ownership

`WorkspaceState` is an immutable, validated snapshot of:

* `schema_version`, fixed to `origlyph.tolerance.workspace.v1`;
* `chain_name`, a non-empty canonical string;
* `analysis_mode`, one of `worst_case` or `rss_statistical`;
* `contributors`, a tuple of validated `WorkspaceContributor` rows with unique
  identifiers.

Updates replace the whole state instead of mutating it. Replacing contributors or
changing the analysis mode clears the cached analysis result, so a stale result
can never be presented or persisted as though it were current.

One contributor stores one `tolerance` value. Worst-case delegation maps it to
`lower_deviation = -tolerance` and `upper_deviation = +tolerance`; statistical
delegation maps it to `sigma = tolerance` with a fixed sigma multiplier of
`1.0` and no correlations. Both mappings preserve `StackDirection`.

## View contract

The view is organised into named areas:

* **Project context**: chain name and analysis mode. Both commit into the controller on
  edit; an invalid chain name is rejected rather than absorbed.
* **Tolerance chain editor**: contributor fields, Add, Update, the contributor table,
  and Remove.
* **Analysis control**: Run.
* **Results**: the formatted summary of the last explicit analysis.
* **Save / load**: Open and Save through the project persistence layer.

Selecting a table row repopulates the contributor fields, and the table preserves the
current selection across refreshes so Update and Remove address the intended row. The
analysis mode list and direction list are derived from `AnalysisMode` and
`StackDirection`; the view hardcodes no engineering vocabulary.

Errors raised inside an action are funnelled through one guard that reports the
message to an injected `on_error` callback when present, otherwise to a modal
error dialog. The view never silently swallows an exception or substitutes a
default value.

## Persistence

The persisted project schema remains `origlyph.project.v1`. Full authoritative workspace
state is stored in `OriglyphProject.extensions` under `origlyph.tolerance.workspace.v1`.
The project-level `ToleranceState` stores the chain name, deterministic configuration
fingerprint, result identities, and result summary values.

Saving persists only the last explicitly computed result. Saving before any analysis
produces empty result identities and summary values rather than triggering a hidden
analysis, so persisted evidence always corresponds to an analysis the user requested.

Reading a project restores the snapshot, then cross-checks that the chain name and
configuration fingerprint agree with `ToleranceState`. A mismatch raises
`InvalidProjectError` instead of returning a partially trusted state.

Transient UI state, such as window placement or selected rows, is intentionally excluded
from the project identity.

## Determinism

Workspace snapshots are canonical JSON-compatible dictionaries. Configuration
fingerprints and result identities use sorted-key SHA-256 payloads with
non-finite numeric values rejected before persistence.

A snapshot dictionary must contain exactly the expected keys. Unknown keys,
missing keys, duplicate contributor identifiers, non-canonical text, and
non-finite numbers are all rejected. Because fingerprints hash canonicalised
payloads, the same state always produces the same fingerprint and the same
result identity.

## Public API

`origlyph.tolerance` exports `ToleranceWorkspaceController`, `WorkspaceState`,
`WorkspaceContributor`, `WorkspaceAnalysisResult`, `AnalysisMode`,
`InvalidToleranceWorkspaceError`, `TOLERANCE_WORKSPACE_SCHEMA_VERSION`, the snapshot and
fingerprint helpers, and `ToleranceWorkspaceView` with `launch_tolerance_workspace`.

`origlyph.project` exports `TOLERANCE_WORKSPACE_EXTENSION_KEY`,
`build_project_with_tolerance_workspace`, `project_with_tolerance_workspace`, and
`workspace_state_from_project`.

## Examples

```python
from origlyph.tolerance import ToleranceWorkspaceController

controller = ToleranceWorkspaceController.empty(
    chain_name="cover-plate",
    analysis_mode="worst_case",
)
controller.add_contributor(
    identifier="cover",
    name="Cover",
    nominal=10.0,
    tolerance=0.2,
    direction="forward",
    tolerance_model="symmetric",
)
result = controller.run_analysis()
print(result.summary_values["total_span"])
```

Launching the desktop view is a single call, also available as
`examples/tolerance_workspace.py`:

```python
from origlyph.tolerance import launch_tolerance_workspace

launch_tolerance_workspace()
```

## Exclusions

* Asymmetric, unequal-bilateral, limit-range, and GD&T contributor models.
* Distributions, statistical weights, correlations, and sensitivity inputs.
* Result history, comparison, audit packaging, and reporting.
* Multi-chain documents and per-contributor CAD traceability.

## Relationship to Other Stages

Stage 16A supplies worst-case interval propagation, Stage 16B supplies RSS statistical
aggregation, and Stage 16C supplies the project document model. Stage 16D adds no engine
behaviour; it maps validated workspace rows onto those engines and stores the result in
the Stage 16C project document.

## AI Boundary

The workspace view and controller are deterministic. No AI participates in validation,
analysis, or persistence, and no AI output can override engine output.

