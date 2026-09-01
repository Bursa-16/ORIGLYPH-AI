# Origlyph v0.4.0-alpha.1 — First Interactive Desktop GUI

## Summary

This release adds the first executable STL datum CLI workflow and the first
interactive Tkinter desktop GUI to the Origlyph platform. The deterministic
engineering runtime is unchanged; this is a user-facing capability release.

## What changed

### First executable STL datum CLI workflow

- New `examples/stl_datum_demo.py` — command-line demo that imports an STL,
  extracts datum candidates, assigns PRIMARY / SECONDARY / TERTIARY roles, and
  builds a `DatumReferenceFrame` through existing production APIs.
- Launch: `py examples\stl_datum_demo.py path\to\part.stl`

### First interactive Tkinter desktop GUI

- New `examples/stl_datum_gui.py` — interactive desktop GUI with:
  - native local `*.stl` file picker
  - import summary panel (declared units, valid facets, warnings, candidate count)
  - deterministic candidate table (index, facet key, feature kind, centroid,
    winding-derived normal, STL diagnostic normal)
  - explicit manual PRIMARY / SECONDARY / TERTIARY assignment
  - DRF construction and results panel
  - permanent visible disclaimer: manual assignment only; Origlyph does not
    automatically rank or recommend datum features
- Launch: `py examples\stl_datum_gui.py`
- Headless-testable `DatumGuiController` orchestration layer (no Tk dependency
  in controller tests)

### Test coverage

- New `tests/integration/test_stl_datum_demo.py` — 14 tests
- New `tests/integration/test_stl_datum_gui.py` — 19 tests (controller tests
  run without Tk root/display; Tk smoke test guarded for headless environments)

## Engineering runtime

The deterministic engineering runtime is **unchanged** in this release:

- `StlImporter`, `extract_candidates`, `bind_reference`,
  `bind_datum_constraint`, `bind_datum_reference_frame` — reused as-is
- No new machining algorithms
- No changes to `src/origlyph/**` production behavior

## Validation

- Full suite: 534 passed
- Ruff: PASS
- Pyright: 0 errors
- diff-check: PASS

## Explicitly not included

- No automatic datum ranking
- No automatic datum recommendation
- No automatic role inference
- No AI engineering authority
- No unit inference or unit conversion
- STL normals are diagnostic / NON-AUTHORITATIVE
- No mesh repair or topology inference
- No GD&T compliance claim
- No engineering tolerance acceptance
- No database, persistence, network, or telemetry

## Tag

Annotated tag `v0.4.0-alpha.1` points at the release commit. Historical tags
(`v0.1.0-alpha.1`, `v0.2.0-alpha.1`, `v0.3.0-alpha.1`, `v0.3.0-alpha.2`)
remain immutable.

## Artifacts

Source archives only. No wheel or sdist is built for this prerelease.
