# Origlyph AI v0.4.0-alpha.6 - Persisted Project Model & Tolerance Workspace Foundation

## Overview

Origlyph AI v0.4.0-alpha.6 follows the already-published `v0.4.0-alpha.5` prerelease. Historical tags remain immutable.

This release adds the deterministic persisted project model v1 (Stage 16B) and the interactive tolerance workspace foundation v1 (Stage 16D), incorporating the R1 UI/controller persistence correction and post-16D EOF whitespace hygiene. The read-only Stage 16E project identity integrity and release-readiness assessment concluded `ALPHA6_RELEASE_READY`.

The Stage 15 tolerance engines, decision, evidence, audit, and governed-acceptance architecture are preserved unchanged. Release preparation does not alter engineering behavior.

## Persisted Project Model v1

- Schema `origlyph.project.v1`, strict fail-closed loading: unknown keys, wrong schemas, non-finite numerics, and malformed documents are rejected.
- Deterministic project identity: `project_id` is a SHA-256 fingerprint of a canonical JSON identity payload, re-derived and verified on every construction and load. Any identity-bearing change to a loaded document raises an integrity error; forged identity or derived-evidence fields fail closed.
- Authoritative engineering state contributes to identity: CAD source identity (source id, format, length unit, fingerprint), datum assignments canonicalized by role, and the tolerance chain configuration (chain name, ordered contributors, analysis mode, configuration fingerprint) plus artifact references.
- Non-identity project state is persisted but excluded from identity: project metadata (name, description, revision, extra) and local source path hints.
- Canonical serialization: UTF-8, stable key ordering, finite numbers only, no filesystem-path dependence, no process or session randomness.
- Deterministic save/load with byte-identical round-trip reconstruction. Documents written under the Stage 16B-compatible v1 shape (no tolerance workspace extension) remain loadable; there is no schema v2 and no silent destructive migration.

## Tolerance Workspace Foundation v1

- Interactive workspace session and controller layered over the deterministic Stage 15 analysis engines.
- Simple 1D tolerance contributor editing: identifier, name, nominal value, tolerance magnitude, and forward/inverse direction. Unsupported tolerance models, distributions, weights, targets, and unknown keys fail closed instead of defaulting.
- `worst_case` and `rss_statistical` analysis modes.
- Deterministic result persistence: result identity and summary values persist only after explicit analysis and are tied to the configuration fingerprint of the authoritative inputs.
- Workspace save/load reconstruction preserves contributors (order included), chain name, analysis mode, and persisted evidence exactly, with no numeric drift and no hidden defaults.

## Deterministic Identity & Persistence

Stage 16E programmatically verified:

- Identity matrix: chain name, contributor identifier, contributor name, contributor add, contributor remove, contributor order, nominal value, tolerance magnitude, direction, and analysis mode each rotate `project_id` individually; a no-op re-serialization does not.
- Non-identity matrix: project metadata, local source path hints, and transient UI state never change `project_id`. Transient widget state (selection, focus, scroll, window geometry) does not reach the persisted schema at all.
- Save -> load -> reconstruct preserves authoritative workspace state and `project_id` exactly.
- Repeated canonical serialization is byte-for-byte identical and independent of dictionary insertion order.

Persisted derived evidence participates in `project_id`. The `configuration_fingerprint` field represents pure engineering configuration identity and should be used where configuration-only identity is needed.

## UI/Controller Authority Boundary

- UI/widget state flows through a thin workspace session into `ToleranceWorkspaceController`, which delegates to the deterministic Stage 15 APIs. The controller is the engineering authority.
- No tolerance formulas and no independent PASS/FAIL logic exist in the view or session layers.
- Analysis runs only on explicit request. Save, load, and header synchronization never trigger analysis.
- Stale results are cleared on every authoritative configuration change; loading a project never promotes persisted evidence to controller authority.
- Invalid UI input fails closed with surfaced errors.

## Validation & Quality Gates

- Project tests: 26 passed
- Workspace controller tests: 11 passed
- Workspace persistence tests: 7 passed
- Workspace view tests: 7 passed
- Tolerance suite: 766 passed
- Full suite: 1326 passed
- Ruff: PASS
- Pyright: PASS - 0 errors, 0 warnings
- diff-check: PASS
- Stage 16E decision: ALPHA6_RELEASE_READY

## Known Limitations / Non-Blocking Follow-ups

These are documented debt, not release blockers:

- `ToleranceWorkspaceController.result_view()` can lazily compute an analysis when called with an empty cache, but no current production UI, session, example, or documentation path calls it. Shipped UI behavior honors the explicit-analysis contract.
- Persisted derived evidence participates in `project_id`. Use `configuration_fingerprint` where pure engineering configuration identity is needed.
- `examples/tolerance_workspace.py` opens a Tk window unless `--headless` is passed.

## Out of Scope

This release does not implement and does not claim:

- STEP / B-Rep import
- a production CAD kernel
- an advanced 3D viewer
- full GD&T authoring
- audit / governance UI
- a report / export suite
- tolerance sensitivity UI
- tolerance allocation UI
- tolerance target / specification objects
- asymmetric, bilateral, or limit-range tolerance models, distributions, weights, or contributor correlations
- autonomous AI engineering authority

## Upgrade / Compatibility Notes

- Package version moves from `0.4.0a5` to `0.4.0a6`.
- Schema remains `origlyph.project.v1`. Existing valid v1 project files load unchanged; a missing tolerance workspace extension is handled intentionally and reported as an invalid project rather than migrated.
- Prior Stage 15 tolerance APIs are unchanged; the workspace foundation delegates to them and adds no engine behavior.
- Historical releases, including `v0.4.0-alpha.5`, remain unchanged.

## Tag

A new annotated tag `v0.4.0-alpha.6` points at this release commit.

## Artifacts

Source archives only. No wheel or sdist is built for this prerelease.
