# Origlyph v0.4.0-alpha.2 — Deterministic 1D Worst-Case Tolerance Engine

## Summary

This release adds a clean-room reimplementation of the deterministic 1D
worst-case tolerance stack analysis engine to the Origlyph platform. The
tolerance engine provides typed, immutable, unit-aware domain contracts and
a deterministic interval-propagation calculation for 1D tolerance stacks.

The previous Stage 15C implementation was deliberately reverted. This
release contains an independently reimplemented clean-room tolerance engine
built from current requirements, existing Origlyph architecture, mathematical
first principles, and traceable public engineering definitions.

## What changed

### Stage 15C-R: Deterministic 1D Worst-Case Tolerance Engine

- New `src/origlyph/tolerance/` package:
  - typed domain models: `ToleranceContribution`, `ToleranceStack`,
    `WorstCaseResult`, `StackDirection`
  - deterministic worst-case engine: interval-propagation calculation of
    stack minimum, maximum, deviations, and total span
  - support for positive (FORWARD) and negative (INVERSE) stack directions
  - support for symmetric, asymmetric, and unilateral tolerances
  - validation of malformed/non-finite engineering inputs
  - deterministic engineering result contracts
  - public tolerance API
  - domain exception hierarchy: `OriglyphToleranceError`,
    `InvalidToleranceError`, `InvalidStackError`
- New `tests/unit/tolerance/` test suite: 43 tests covering model
  validation, interval computation, worst-case scenarios, edge cases,
  and deterministic behavior
- Architecture documentation: `docs/architecture/tolerance_1d_worst_case.md`

### Test coverage

- New `tests/unit/tolerance/test_models.py` — 27 tests
- New `tests/unit/tolerance/test_worst_case.py` — 16 tests
- Total suite increased from 534 to 577 tests

## Engineering additions

- `ToleranceContribution` — immutable value object representing a single
  dimension with nominal value, lower/upper deviations, and stack direction
- `ToleranceStack` — ordered, immutable stack of contributions
- `WorstCaseResult` — deterministic result with nominal, minimum, maximum,
  deviations, and total span
- `worst_case()` — deterministic interval-propagation engine
- Handles symmetric, asymmetric, unilateral, positive, and negative
- Rejects NaN, infinity, and malformed tolerance definitions

## Validation

- Full suite: 577 passed
- Ruff: PASS
- Pyright: 0 errors
- diff-check: PASS

## Explicitly not included

- RSS/statistical tolerance analysis
- Monte Carlo simulation
- 3D tolerance stack analysis
- GD&T semantic interpretation
- CAD automatic tolerance extraction
- Automatic datum selection
- Cp/Cpk analysis
- AI engineering authority
- Database, persistence, network, or telemetry

## Engineering authority principle

AI does not override deterministic tolerance calculations.

## Baseline and feature

- Baseline before feature: `4817330`
- Feature commit: `a510195ba51b7fd367246642705427a5136a848e`

## Tag

Annotated tag `v0.4.0-alpha.2` points at the release commit. Historical tags
(`v0.1.0-alpha.1`, `v0.2.0-alpha.1`, `v0.3.0-alpha.1`, `v0.3.0-alpha.2`,
`v0.4.0-alpha.1`) remain immutable.

## Artifacts

Source archives only. No wheel or sdist is built for this prerelease.
