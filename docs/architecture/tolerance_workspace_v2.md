# Tolerance Workspace Specification Contract v2 (Stage 17A)

## Overview

Stage 17A introduces `WorkspaceSpecification` — an immutable engineering limit
model — and `origlyph.tolerance.workspace.v2` schema version for persisting
those limits inside a tolerance workspace project snapshot.

## Motivation

The Stage 15K decision engine (`evaluate_tolerance_decision`) accepts optional
`allowed_worst_case_span` and `allowed_combined_sigma` parameters.  Prior to
Stage 17A the workspace had no way to store or surface these limits; every
analysis ran without comparison thresholds.  Stage 17A adds exactly that
storage contract without adding any PASS/FAIL verdict computation to the
workspace layer.

---

## Model: `WorkspaceSpecification`

```
WorkspaceSpecification(frozen=True, slots=True)
  allowed_worst_case_span: float | None
  allowed_combined_sigma:  float | None
```

**Invariants (enforced in `__post_init__`)**

- Each present field must be strictly positive (`> 0.0`) and finite.
- Semantics match `_validate_positive_finite()` in `decision.py` exactly.
- Dataclass equality: two instances with the same field values are equal.

**`as_dict()`** serialises to `{"allowed_worst_case_span": …, "allowed_combined_sigma": …}`
with `None` for absent limits.

---

## Schema versioning

| Constant | Value |
|---|---|
| `TOLERANCE_WORKSPACE_SCHEMA_VERSION` | `"origlyph.tolerance.workspace.v1"` |
| `TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2` | `"origlyph.tolerance.workspace.v2"` |

The **extension key** (`TOLERANCE_WORKSPACE_EXTENSION_KEY =
"origlyph.tolerance.workspace.v1"`) is **stable** — both v1 and v2 snapshots
are stored under the same project extension key.  The `schema_version` field
**inside** the snapshot discriminates versions.

### v1 snapshot shape (unchanged)

```json
{
  "schema_version": "origlyph.tolerance.workspace.v1",
  "chain_name": "…",
  "analysis_mode": "worst_case",
  "contributors": […]
}
```

### v2 snapshot shape

```json
{
  "schema_version": "origlyph.tolerance.workspace.v2",
  "chain_name": "…",
  "analysis_mode": "worst_case",
  "contributors": […],
  "specification": {
    "allowed_worst_case_span": 0.6,
    "allowed_combined_sigma": null
  }
}
```

`"specification"` may be `null` (limits cleared after upgrade) or an object
with exactly two keys.  Unknown keys always raise `InvalidToleranceWorkspaceError`.

---

## Backward compatibility

- Existing v1 projects load without modification.
- `WorkspaceState.specification` is `None` for any v1 project.
- Setting `specification ≠ None` on a v1-schema `WorkspaceState` raises
  `InvalidToleranceWorkspaceError` — `specification` is a v2-only field.
- No engineering defaults are fabricated for v1 projects.

---

## `WorkspaceState` extension

```
WorkspaceState(frozen=True, slots=True)
  …existing fields…
  specification: WorkspaceSpecification | None = None  ← v2 only
```

`__post_init__` enforces: if `schema_version == v1` and `specification is not
None` → error.

`as_dict()` emits the `"specification"` key only for v2 snapshots.

---

## `ToleranceWorkspaceController` extension

### `specification` property

Returns `self._state.specification`.

### `set_specification(specification: WorkspaceSpecification | None) → None`

- Accepts `WorkspaceSpecification` or `None`.
- **No-op** when the new value equals the current value (dataclass equality).
- Setting `None` on a v1-schema state is a no-op (state stays v1, result preserved).
- Setting `None` on a v2-schema state clears the spec but **keeps the schema
  at v2** (a cleared v2 is not downgraded to v1).
- Any actual change invalidates `_last_result`.
- Schema upgrades automatically: first `set_specification(non-None)` on a v1
  controller sets `schema_version = v2`.

### `from_state(state)` bypass

Uses `cls.__new__(cls)` + direct attribute assignment to preserve the **exact**
`schema_version` read from disk without re-deriving it from `specification`
presence.

---

## Identity and fingerprinting

`WorkspaceState.as_dict()` includes `"specification"` for v2 states, so the
specification value propagates through `workspace_configuration_fingerprint()`
→ `_identity_payload()` → `project_id`.

- Changing `specification` rotates `project_id`.
- Same `specification` → same `project_id` (deterministic).
- v1→v2 upgrade (first spec set) also rotates `project_id`.

---

## UI surface (`workspace_model.py`)

A "Specification limits" `Labelframe` at grid row=1 exposes two `Entry`
widgets:

| Widget | StringVar | Purpose |
|---|---|---|
| Allowed WC Span | `_allowed_wc_span` | `allowed_worst_case_span` |
| Allowed σ | `_allowed_sigma` | `allowed_combined_sigma` |

**Blank field = unspecified** (not zero).  Invalid or non-positive values
surface `InvalidToleranceWorkspaceError` via the existing `_guard()` handler.

The view **never** computes or displays PASS/FAIL verdicts from the
specification.  It stores limits only; verdict logic belongs to a future stage.

---

## Files changed

| File | Change |
|---|---|
| `src/origlyph/tolerance/workspace_controller.py` | Add `WorkspaceSpecification`, `TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2`, v2 snapshot parse/emit, `set_specification()`, updated `from_state()` |
| `src/origlyph/tolerance/workspace_model.py` | Add `WorkspaceSession.sync_specification()`, spec `Entry` widgets |
| `src/origlyph/tolerance/__init__.py` | Export `WorkspaceSpecification`, `TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2` |
| `tests/unit/tolerance/test_workspace_specification.py` | 61 new tests (model, v2 snapshot, backward compat, controller, persistence, view/session) |

No Stage 15 engine files were modified.
