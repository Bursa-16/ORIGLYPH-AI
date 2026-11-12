# B-Rep Optional Dependency Contract — Origlyph Stage 22D.2

**Status:** APPROVED
**Stage:** 22D.2
**Date:** 2026-11-12
**Baseline commit:** 6d33e6038a75e0a9735bee6578e89664e126072b (Stage 22D.1 spike)

---

## Mandatory Statements

**B-Rep support is an optional capability and is not required for the Origlyph
core installation.**

**Adding the optional B-Rep dependency does not constitute production STEP
support.**

**Persistent topology naming across CAD revisions remains unsolved.**

**No B-Rep topology is persisted into the Origlyph project model in
Stage 22D.2.**

---

## 1. Why OCP is Optional

The Origlyph core domain (DXF import, NeutralModel, datum/tolerance governance,
GD&T analysis, HTML exports) has zero dependency on a CAD geometry kernel.
The Stage 22D.1 spike proved that OCCT-based B-Rep traversal is feasible via
the Python OCP binding; it did not establish production readiness.

Keeping OCP optional preserves:

- Core installation size and startup time
- Python version flexibility (core supports Python >=3.10; OCP requires >=3.11)
- Distribution simplicity (no LGPL-licensed native binary in the default wheel)
- Fail-closed behavior: if OCP is absent the spike adapter raises
  `StepKernelUnavailableError`; core workflows are unaffected

---

## 2. Selected Package

| Field            | Value                   |
|------------------|-------------------------|
| Package          | `cadquery-ocp-novtk`    |
| Validated version | 8.0.1.1.0              |
| Source           | PyPI                    |
| License          | Apache-2.0              |
| Requires         | `cadquery-ocp-proxy`    |
| Validated on     | Python 3.14.6, Windows  |

The `novtk` variant omits the VTK visualization dependency, reducing install
size substantially. No VTK features are used by the Origlyph adapter.

---

## 3. Requirement Range

```toml
brep = [
    "cadquery-ocp-novtk>=8.0.1.1.0,<9; python_version >= '3.11'",
]
```

**Lower bound `>=8.0.1.1.0`:** the validated Stage 22D.1 version. Earlier
versions are unvalidated.

**Upper bound `<9`:** guards against a potential major-version API break in the
OCP/OCCT Python binding. Versions within the 8.x line share the same traversal
API surface used in Stage 22D.1.

**Environment marker `; python_version >= '3.11'`:** `cadquery-ocp-novtk`
requires Python `>=3.11`. On Python 3.10 the dependency spec evaluates to
false and the package is not requested, preserving the core minimum.

---

## 4. Installation

**Core install (no kernel):**

```
pip install origlyph
pip install "origlyph[dev]"
```

Both install without any native geometry kernel. All DXF, STL, datum/tolerance,
and GD&T workflows remain fully functional.

**B-Rep install (optional kernel):**

```
pip install "origlyph[brep]"
pip install "origlyph[dev,brep]"
```

Installs `cadquery-ocp-novtk` and its proxy package. Enables use of
`StepKernelAdapter` for experimental STEP topology extraction.

**Python compatibility:** The `brep` extra requires Python >=3.11 and is a
no-op on Python 3.10.

---

## 5. Python Compatibility

| Component          | Minimum Python |
|--------------------|----------------|
| Core (`origlyph`)  | 3.10           |
| `brep` extra       | 3.11           |

The `requires-python = ">=3.10"` declaration in `pyproject.toml` is unchanged.
The environment marker on the optional dependency handles the per-extra minimum
without raising the core minimum.

---

## 6. Kernel-Unavailable Behavior

When `cadquery-ocp-novtk` is not installed:

- `import origlyph` succeeds
- `import origlyph.cad` succeeds
- All existing DXF/STL/topology/datum/tolerance workflows function normally
- `origlyph.cad.step_kernel_adapter` can be imported; `StepKernelAdapter` is
  constructible; calling `to_canonical_topology()` raises
  `StepKernelUnavailableError` immediately (fail-closed, no partial state)
- `StepKernelUnavailableError` is a subclass of `OriglyphCadError`

The `StepKernelAdapter` module uses `importlib.util.find_spec("OCP")` to detect
presence at call time. All OCP imports are function-local with
`# type: ignore[import-not-found]`. No OCP type appears in the returned
`CanonicalTopologyModel` or in any Origlyph domain contract.

---

## 7. Production STEP Support

The `brep` optional dependency does **not** enable production STEP support.

| Check                                    | State |
|------------------------------------------|-------|
| `.step`/`.stp` in production CAD dispatch | NO   |
| `.step`/`.stp` in supported-format registry | NO |
| `.step`/`.stp` in UI file filters         | NO   |
| `StepKernelAdapter` exported from `origlyph.cad` | NO |
| STEP topology persisted into project model | NO  |

Production STEP support requires a separate Stage 22E decision gate.

---

## 8. CI Contract

The CI workflow (`ci.yml`) defines two jobs:

### Path A — `ci` (core, Python 3.10, always runs)

- Installs `pip install -e ".[dev]"` — no kernel
- Runs: `ruff check`, `pyright`, `pytest` (full suite)
- Verifies core works without the B-Rep extra

### Path B — `ci-brep` (B-Rep, Python 3.11, always runs)

- Installs `pip install -e ".[dev,brep]"` — includes kernel
- Explicitly verifies `import OCP` succeeds
- Runs focused test targets:
  - `tests/unit/test_optional_dependencies.py`
  - `tests/unit/cad/test_step_kernel_adapter.py`
  - `tests/unit/cad/test_topology.py`
  - `tests/unit/cad/test_topology_adapter.py`
  - `tests/integration/test_step_topology_spike.py`

**The `ci-brep` job is NOT marked `allow-failure`.** If the optional package
cannot install, or OCP import fails, or any adapter or integration test fails,
CI fails.

---

## 9. License and Distribution Notes

> These notes are informational only. They do not constitute legal advice.
> Consult qualified counsel before any commercial distribution.

| Component              | License       |
|------------------------|---------------|
| `cadquery-ocp-novtk`   | Apache-2.0    |
| `cadquery-ocp-proxy`   | Apache-2.0    |
| OpenCASCADE Technology | LGPL-2.1+     |

The Python `OCP` package is a wrapper around OCCT native libraries. The OCCT
runtime is linked dynamically. LGPL-2.1 permits dynamic linking without
requiring source disclosure of the linking application, subject to allowing
users to relink with a modified LGPL library. Commercial redistribution of
binaries that include OCCT native code requires a dedicated license review.

The `brep` extra is excluded from the core wheel. Users who install it accept
the LGPL-2.1 terms of the OCCT runtime.

---

## 10. Architecture Boundaries

### Limitations not addressed in Stage 22D.2

- **Persistent topology naming across CAD revisions:** Canonical IDs are
  traversal-order-local to one import session. They are not stable across CAD
  file revisions. This problem is unsolved and outside Stage 22D scope.
- **Workspace schema:** No B-Rep topology is added to the Workspace schema (v5
  unchanged). No schema v6 is introduced.
- **Project model:** No B-Rep or STEP data is persisted into the Origlyph
  project model at any stage.

### Stage 22E prerequisites (future, not started)

Stage 22E may integrate the spike adapter into a production STEP registration
path. Prerequisites established in Stages 22D.1 and 22D.2:

1. OCP/OCCT traversal spike validated (Stage 22D.1) ✓
2. `brep` optional dependency contract established (Stage 22D.2) ✓
3. CI B-Rep path validated (Stage 22D.2) ✓
4. `.gitattributes` with `*.step binary` / `*.stp binary` (pending maintenance commit)
5. Stage 22E decision gate: production registration, persistent ID design, schema migration

---

## 11. Summary

| Property                               | Value                               |
|----------------------------------------|-------------------------------------|
| Selected package                       | `cadquery-ocp-novtk`                |
| Validated version                      | 8.0.1.1.0                          |
| Requirement                            | `>=8.0.1.1.0,<9`                   |
| Python marker                          | `python_version >= '3.11'`          |
| Core installation kernel-free          | YES                                 |
| Core Python minimum changed            | NO (remains >=3.10)                |
| Production STEP support                | NO                                  |
| Topology persistence                   | NO                                  |
| Persistent topology naming solved      | NO (explicitly unsolved)           |
| Workspace schema changed               | NO (v5 unchanged)                   |
| Stage 22E started                      | NO                                  |
