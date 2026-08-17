# Origlyph Engineering Platform

## Project Name
Origlyph

## Short Purpose Statement
Engineering platform for CAD data opening, geometry interrogation, automatic datum/reference surface/point definition, GD&T assistance, tolerance analysis, dimensional chain analysis, and assembly-level geometry reasoning.

## Architecture Principles
1. Deterministic engineering logic is authoritative
2. AI is additive, explainable, traceable, and must not silently override engineering rules
3. Engineering calculations, AI reasoning, UI, data access, and governance must remain architecturally separated
4. No proprietary/OEM/standards content may be embedded without explicit provenance and approval
5. The system must support future TR/EN internationalization
6. The architecture must support future CAD integration without tightly coupling the core domain to one CAD vendor
7. Geometry, GD&T, datum definition, and tolerance-analysis domains must remain modular
8. Auditability, provenance, revisioning, validation, and fail-closed behavior must be designed from the beginning
9. Legacy DatumIQ material may be used only as requirements/reference material, not as migrated source code
10. Repository foundation should be production-oriented, testable, and extensible

## Deterministic Engineering Authority
All engineering calculations, geometric constraints, GD&T compliance, and tolerance results are deterministic and traceable. AI outputs are recommendations only and must not override deterministic results.

## AI Boundary
AI assists with explanation, interpretation, workflow guidance, and recommendations. AI must not silently override deterministic engineering results. Fail-closed behavior: when required engineering evidence is missing, system defaults to human approval required.

## Clean-Room Policy
No legacy DatumIQ source code is migrated. No TorqPro source/material is copied. No SpotWeld-AI source/material is copied. No OEM/FCA proprietary material is copied. No proprietary standards text or tables are embedded without provenance and authorization. Reference material may only guide clean-room reimplementation. All engineering logic must have traceable provenance or first-principles derivation.

## Current Development Status
Stage 1B: Minimal repository skeleton. Foundation architecture defined. No engineering algorithms implemented yet.

## Package Structure Overview
- src/origlyph/ - Canonical Python package namespace
- src/origlyph/core/ - Core engine and orchestration
- src/origlyph/geometry/ - Geometry interrogation and measurement
- src/origlyph/datum/ - Reference surface/point definition
- src/origlyph/gdandt/ - GD&T assistance and automation
- src/origlyph/tolerance/ - Tolerance analysis
- src/origlyph/assembly/ - Assembly-level geometry reasoning
- src/origlyph/provenance/ - Auditability and provenance tracking
- src/origlyph/ai/ - AI integration boundary