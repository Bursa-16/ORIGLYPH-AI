# Origlyph v0.4.0-alpha.3 — Deterministic Tolerance Analysis Stack

## Overview

Origlyph AI v0.4.0-alpha.3 is a release-only preparatory step covering all
completed engineering work between v0.4.0-alpha.2 and the current engineering
tip. It adds a deterministic, clean-room 1D tolerance analysis stack to the
Origlyph platform: independent RSS statistical analysis, covariance-aware
correlated statistical propagation, sensitivity / contributor-impact
analysis, tolerance budget compliance, worst-case target-window compliance,
user-supplied allocation validation, and allocation-vs-actual reconciliation.

This release does **not** change engineering behavior. The six tolerance
stages (15D–15I) are documented here for the first time at the release level.

## Engineering capabilities added

Since v0.4.0-alpha.2, the following deterministic capabilities were added:

### Stage 15D — Deterministic RSS / Statistical 1D Tolerance Foundation

- Independent root-sum-square (RSS) statistical tolerance propagation
- Explicit sigma-based contribution model (`SigmaContribution`,
  `SigmaStack`)
- Deterministic `statistical(...)` engine with a validated sigma multiplier

### Stage 15E — Covariance-Aware Statistical Analysis

- Explicit pairwise `Correlation` contracts (caller-supplied, never inferred)
- Sign-aware covariance handling for FORWARD / INVERSE stack directions
- `combined_sigma` and bounds over independent and correlated terms
- Materially-negative-variance rejection with documented round-off tolerance

### Stage 15F — Deterministic Sensitivity Analysis

- `worst_case_sensitivity(...)` — worst-case contribution ranking
- `statistical_sensitivity(...)` — variance / covariance-pair contribution
  analysis
- Deterministic fractions, percentages, and stable tie-preserving ordering

### Stage 15G — Deterministic Tolerance Budget Analysis

- `worst_case_budget(...)` / `statistical_budget(...)` compliance analysis
- `UNDER_BUDGET` / `AT_BUDGET` / `OVER_BUDGET` states
- Per-contributor budget share, remaining margin, and utilization
- `worst_case_window_compliance(...)` target-window check

### Stage 15H — Deterministic Tolerance Allocation Validation

- `validate_allocation(...)` for user-supplied allocation plans
- `UNDER_ALLOCATED` / `FULLY_ALLOCATED` / `OVER_ALLOCATED` states
- Duplicate / unknown / non-finite / malformed input rejection
- Completeness checking with `require_complete` mode
- Current-span versus allocation comparison

### Stage 15I — Deterministic Allocation vs Actual Reconciliation

- `reconcile_allocation(...)` comparing validated allocation against actual
  consumption
- Per-contributor allocation compliance (`UNDER` / `AT` / `OVER` allocation)
- Total allocation margin and engineering-remaining-margin reconciliation
- Combined allocation-plan, engineering-budget, and reconciliation status

## Stage progression

Previous release: v0.4.0-alpha.2

Previous release commit: `9d20a6ba4f328e0caa3b465b8d5739de89cd1166`

Current pre-release engineering tip: `2cc07f95d9beec4def89a14c31f6b0979ec30197`

Stage progression since alpha.2:

- `b2b9138` — deterministic RSS statistical analysis
- `bb65dfa` — covariance-aware statistical analysis
- `e3ed2c9` — deterministic sensitivity analysis
- `3b5d195` — deterministic budget analysis
- `34a0583` — deterministic allocation validation
- `2cc07f9` — deterministic allocation reconciliation

## Validation

- Full suite: 774 passed
- Ruff: PASS
- Pyright: 0 errors
- diff-check: PASS

Release preparation does not alter engineering behavior.

## Deterministic authority / clean-room boundary

All tolerance calculations in this release are deterministic. AI does not
override deterministic tolerance calculations.

Correlations are always supplied explicitly by the engineer; Origlyph does
not infer manufacturing correlations. Sensitivity, budget, allocation, and
reconciliation results are analytical outputs that do not by themselves
modify tolerances or recommend design changes.

## Known exclusions

This release does **not** provide or claim:

- Monte Carlo simulation
- arbitrary probability distributions
- nonlinear tolerance propagation
- 3D tolerance analysis
- GD&T semantic interpretation
- CAD automatic tolerance extraction
- automatic tolerance allocation
- automatic tolerance redistribution
- tolerance optimization
- cost optimization
- Cp/Cpk analysis
- process-capability prediction
- automatic correlation inference
- automatic design recommendations
- AI engineering authority

## Tag

A new annotated tag `v0.4.0-alpha.3` will point at this release commit.
Historical tags remain immutable.

## Artifacts

Source archives only. No wheel or sdist is built for this prerelease.