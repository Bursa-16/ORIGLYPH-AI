# Origlyph Engineering Platform

## Project Identity

* **Name:** Origlyph
* **Current status:** First public alpha / early engineering foundation
* **Version:** `0.1.0a1`
* Intended Git tag: `v0.1.0-alpha.1` — GitHub release title: `Origlyph v0.1.0-alpha.1`

## Short Purpose Statement

Engineering platform for CAD data opening, geometry interrogation, automatic datum/reference surface/point definition, GD&T assistance, tolerance analysis, dimensional chain analysis, and assembly-level geometry reasoning.

## Current Development Status

First public alpha — early engineering foundation. This release provides a deterministic geometry foundation. It does not claim production readiness, certification, ASME/ISO compliance, or validated manufacturing capability.

## What Is Currently Implemented

* Deterministic geometry foundation (Python standard library only, no runtime dependencies)
* Geometry value objects: `Point3D`, `Vector3D`, `Line3D`, `Plane3D` — immutable, validated, canonical millimetre coordinates
* Units: canonical internal length (millimetres) and angle (radians), with dimensionally distinct `Length` and `Angle`
* Computational geometry tolerance policy — numerical robustness only, explicitly not an engineering tolerance
* Coordinate frames (orthonormal, right-handed) and rigid transforms (translation, rotation, composition, inverse)
* Operations: distances, angles, projections, and closest-point computations

## Explicit Alpha Limitations / Non-Scope

This alpha does **not** yet provide:

* CAD parsing
* STEP/IGES import
* surfaces
* solids
* topology
* Boolean operations
* Axis3D, Circle3D, Arc3D
* intersection algorithms
* GD&T evaluation
* datum selection
* tolerance stack-up / dimensional-chain analysis
* engineering acceptance/rejection decisions
* AI engineering decisions

Origlyph does not claim production readiness, certification, ASME compliance, ISO compliance, or validated manufacturing capability at this stage.

## Architecture Principles

1. Deterministic engineering logic is authoritative
2. AI is additive, explainable, traceable, and must not silently override engineering rules
3. Engineering calculations, AI reasoning, UI, data access, and governance must remain architecturally separated
4. No proprietary/OEM/standards content may be embedded without explicit provenance and approval
5. The system must support future TR/EN internationalization
6. The architecture must support future CAD integration without tightly coupling the core domain to one CAD vendor
7. Geometry, GD&T, datum definition, and tolerance-analysis domains must remain modular
8. Auditability, provenance, revisioning, validation, and fail-closed behavior must be designed from the beginning
9. Legacy material may be used only as requirements/reference material, not as migrated source code
10. Repository foundation should be production-oriented, testable, and extensible

## Deterministic Engineering Authority

All engineering calculations, geometric constraints, GD&T compliance, and tolerance results are deterministic and traceable. AI outputs are recommendations only and must not override deterministic results.

## AI Boundary

AI assists with explanation, interpretation, workflow guidance, and recommendations. AI must not silently override deterministic engineering results. Fail-closed behavior: when required engineering evidence is missing, the system defaults to human approval required.

## Clean-Room Policy

No legacy DatumIQ source code is migrated. No TorqPro source/material is copied. No SpotWeld-AI source/material is copied. No OEM/FCA proprietary material is copied. No proprietary standards text or tables are embedded without provenance and authorization. Reference material may only guide clean-room reimplementation. All engineering logic must have traceable provenance or first-principles derivation.

## Package Structure Overview

- src/origlyph/ - Canonical Python package namespace
- src/origlyph/core/ - Core engine and orchestration
- src/origlyph/geometry/ - Geometry interrogation and measurement (foundation implemented)
- src/origlyph/datum/ - Reference surface/point definition (not yet implemented)
- src/origlyph/gdandt/ - GD&T assistance and automation (not yet implemented)
- src/origlyph/tolerance/ - Tolerance analysis (not yet implemented)
- src/origlyph/assembly/ - Assembly-level geometry reasoning (not yet implemented)
- src/origlyph/provenance/ - Auditability and provenance tracking (not yet implemented)
- src/origlyph/ai/ - AI integration boundary (not yet implemented)

## Installation (development)

```sh
py -m pip install -e ".[dev]"
```

## Verification

```sh
py -m pytest
ruff check src tests
pyright
```

Verified baseline for this release (v0.1.0-alpha.1): 86 tests passing; Ruff PASS; Pyright PASS.

## License

Released under the MIT License. See [LICENSE](LICENSE).
