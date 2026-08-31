# Origlyph Engineering Platform

## Project Identity

* **Name:** Origlyph
* **Current status:** Third public alpha — deterministic CAD and datum engineering foundation
* **Package version:** `0.3.0a2`
* **Current release/tag:** `v0.3.0-alpha.2`

## Purpose

Origlyph is an engineering platform intended for:

* CAD data ingestion and geometry interrogation
* datum/reference definition workflows
* GD&T assistance
* tolerance analysis
* dimensional-chain / tolerance-stack analysis
* assembly geometry reasoning
* deterministic engineering workflows with provenance
* future explainable AI assistance

These are product goals. Only the capabilities listed under
[What Is Currently Implemented](#what-is-currently-implemented) exist today;
everything else is roadmap, not implementation.

## Current Development Status

v0.3.0-alpha.2 provides a deterministic geometry foundation, CAD identity and
neutral-model contracts, a concrete STL importer, source-to-neutral
provenance, a CAD-to-datum candidate bridge, explicit datum/reference
binding, explicit PRIMARY / SECONDARY / TERTIARY role assignment,
`DatumReferenceFrame` construction, and advisory candidate evaluation.

This release is still alpha. It does **not** claim production readiness,
certification, ASME/ISO compliance, or validated manufacturing acceptance
capability.

## What Is Currently Implemented

### Geometry foundation

* `Point3D`, `Vector3D`, `Line3D`, `Plane3D` — immutable, validated value objects in canonical millimetre coordinates
* bounded planar faces (`BoundedPlanarFace`) — ordered, coplanar vertex cycles with derived plane / area / centroid / perimeter
* coordinate frames (orthonormal, right-handed) and rigid transforms (translation, rotation, composition, inverse)
* distances, angles, projections, and closest-point operations
* computational floating-point tolerance policy — numerical robustness only; explicitly **not** an engineering tolerance

### CAD foundation

* identity separation for source documents, source entities, neutral entities, and the domain (`SourceDocumentIdentity`, `SourceEntityIdentity`, `NeutralEntityIdentity`, `DomainIdentity`, `SourceUnitSystem`)
* `NeutralModel` with duplicate rejection and deterministic entity ordering
* `SourceToNeutralMapping` — exact, duplicate-safe source↔neutral mapping
* `NeutralModel.reverse_lookup` — model-scoped, exact, fail-closed source identity resolution
* deterministic provenance carried on every imported entity
* fail-closed warning / unsupported-content handling (`CadWarning`, `UnsupportedContent`) — nothing silently dropped
* the `CadImporter` protocol plus the concrete `StlImporter`

### STL importer

* ASCII STL and binary STL support
* injected `bytes_loader` is the only source-acquisition boundary — no filesystem I/O inside the importer
* deterministic binary detection using the exact `84 + 50 * facet_count` layout (binary headers beginning with `solid` handled correctly)
* declared source length unit must be `mm`; no implicit unit conversion and no scale inference
* stable 0-based `facet-{i}` source and neutral identities
* each facet becomes a `BoundedPlanarFace`; the STL stored facet normal is diagnostic metadata only — vertex winding determines face geometry, and vertices are never reordered or flipped
* degenerate facets (duplicate / collinear / zero-area vertices) are surfaced via `CadWarning("DEGENERATE_FACET")` plus `UnsupportedContent`
* malformed, truncated, oversized, or non-finite payloads fail closed with `CadImportError`

### Datum/reference workflow

The deterministic chain, exactly as implemented:

STL / `NeutralModel`
→ candidate extraction (`extract_candidates`)
→ `BridgedCandidate` (POINT / LINE / AXIS / PLANE, including lifted `BoundedPlanarFace` planes)
→ `bind_reference` → `BoundReference` (provenance-traced, coherence-validated)
→ explicit `ConstraintType` (PRIMARY / SECONDARY / TERTIARY)
→ `bind_datum_constraint` → `DatumConstraint`
→ `bind_datum_reference_frame` → `DatumReferenceFrame`
→ advisory `evaluate_candidates`

* `ReferencePoint` / `ReferenceSurface` artifacts for POINT / PLANE candidates; `PhysicalFeature` for all candidate kinds
* `DatumConstraint` with deterministic 3-2-1 degree-of-freedom sets and an injected, deterministic theoretical-datum simulator
* `DatumReferenceFrame` construction with sequence-authority ordering; partial DRFs (any PRIMARY-prefixed assignment set) are supported
* the full 3-2-1 path — including three STL facets assigned PRIMARY / SECONDARY / TERTIARY — is verified by tests
* no automatic role inference: the explicit `ConstraintType` is the sole role authority

### Drawing/context foundation

Declaration records that carry engineering context, consumable through the
model's exact lookup APIs:

* `DatumFeatureDeclaration` and `DrawingDatumReferenceFrameDeclaration` (drawing datum context)
* `FunctionalRelevanceDeclaration` (functional relevance context)

These are provenance-carrying records; they do not infer or assign anything.

### Deterministic boundaries

* no hidden datum inference
* no automatic ranking
* no automatic standards interpretation
* no authoritative AI
* missing evidence fails closed

## End-to-End Capability

The first concrete CAD-file-to-datum workflow in Origlyph:

```text
ASCII/Binary STL
→ NeutralModel
→ BoundedPlanarFace (per facet)
→ PLANE candidate
→ BoundReference
→ DatumConstraint (explicit role)
→ DatumReferenceFrame (3-2-1)
```

This flow is exercised end-to-end by tests. STL is facet geometry only —
this does not imply mesh topology, and STEP/B-Rep support does not exist.

## Explicit Alpha Limitations / Non-Scope

This alpha does **not** yet provide:

* STEP import
* IGES import
* DXF import
* B-Rep / topology
* topology adjacency
* mesh welding / repair
* watertightness inference
* solids / Boolean modeling as a CAD kernel
* automatic datum ranking / recommendation
* automatic datum role inference
* a full GD&T compliance/evaluation engine
* an engineering tolerance runtime
* tolerance stack-up / dimensional-chain solver
* measurement acceptance/rejection
* standards interpretation
* production certification
* authoritative AI engineering decisions

Standing distinction: the computational floating-point tolerance policy is
**not** an engineering tolerance and must never be used to mask an
engineering-relevant deviation.

## Architecture Principles

1. Where deterministic engineering calculations are implemented, they are the authoritative computational path. AI may assist but must not silently override deterministic results.
2. AI is additive, explainable, traceable, and must not silently override engineering rules.
3. Engineering calculations, AI reasoning, UI, data access, and governance must remain architecturally separated.
4. No proprietary/OEM/standards content may be embedded without explicit provenance and approval.
5. The system must support future TR/EN internationalization.
6. The architecture must support future CAD integration without tightly coupling the core domain to one CAD vendor.
7. Geometry, GD&T, datum definition, and tolerance-analysis domains must remain modular.
8. Auditability, provenance, revisioning, validation, and fail-closed behavior are designed in from the beginning.
9. Legacy material may be used only as requirements/reference material, never as migrated source code.
10. The repository foundation is production-oriented, testable, and extensible.

## AI Boundary

AI is advisory and additive: explainable, traceable, and never
authoritative. It must not override deterministic engineering results, and
when required engineering evidence is missing the system fails closed to
human approval. No AI datum ranking exists today; the `Recommender` contract
is a reserved future protocol.

## Clean-Room Policy

No legacy DatumIQ source code is migrated. No TorqPro source/material is
copied. No SpotWeld-AI source/material is copied. No OEM/FCA proprietary
material is copied. No proprietary standards text or tables are embedded
without provenance and authorization. Reference material may only guide
clean-room reimplementation. All engineering logic must have traceable
provenance or first-principles derivation.

## Package Structure Overview

* `src/origlyph/` — canonical Python package namespace
* `src/origlyph/geometry/` — geometry interrogation foundation (implemented)
* `src/origlyph/cad/` — CAD identity, neutral model, importer protocol, STL importer, bridge, binding, roles, evaluation (implemented)
* `src/origlyph/datum/` — datum/reference domain: references, DOF, constraints, DRF (implemented)
* `src/origlyph/gdandt/` — GD&T assistance and automation (reserved, not yet implemented)
* `src/origlyph/tolerance/` — tolerance analysis (reserved, not yet implemented)
* `src/origlyph/assembly/` — assembly-level geometry reasoning (reserved, not yet implemented)
* `src/origlyph/provenance/` — dedicated provenance layer (reserved; provenance is currently carried inline by the CAD contracts)
* `src/origlyph/core/` — core engine and orchestration (reserved, not yet implemented)
* `src/origlyph/ai/` — AI integration boundary (reserved, not yet implemented)

## Installation (development)

```sh
py -m pip install -e ".[dev]"
```

## Quick STL Demo

```sh
py examples\stl_datum_demo.py path\to\part.stl
```

* STL coordinates are explicitly declared as millimetres (`mm`); no automatic
  unit inference or conversion is performed.
* The demo datum reference frame is built from the first three valid planar
  facets in file order, only to exercise the deterministic API.
* This is **not** automatic datum recommendation: Origlyph does not rank,
  score, or recommend datum features.

## Quick GUI Demo

```sh
py examples\stl_datum_gui.py
```

* Launches a minimal Tkinter desktop GUI over the same deterministic pipeline.
* A native local `*.stl` file picker is used; no path is hardcoded and no
  network is involved.
* STL units are explicitly declared as millimetres (`mm`); no unit inference
  or unit conversion is performed.
* The STL stored facet normal is shown only as a diagnostic labelled
  `Authority: NON-AUTHORITATIVE`; the winding-derived face normal is the
  geometry authority.
* The operator explicitly assigns PRIMARY, SECONDARY, and TERTIARY roles to
  three distinct candidates — the same candidate cannot occupy two roles at
  once.
* Origlyph does **not** automatically rank, score, or recommend datum
  features: every role assignment is a manual operator choice.

## Verification

```sh
py -m pytest -q
py -m ruff check src tests
py -m pyright
```

Verified baseline for v0.3.0-alpha.2: 515 tests passed; Ruff PASS; Pyright PASS.

## Release

Current prerelease: `v0.3.0-alpha.2` (package version `0.3.0a2`).
Release notes: [RELEASE_NOTES_v0.3.0-alpha.2.md](RELEASE_NOTES_v0.3.0-alpha.2.md);
previous: [RELEASE_NOTES_v0.3.0-alpha.1.md](RELEASE_NOTES_v0.3.0-alpha.1.md).

## License

Released under the MIT License. See [LICENSE](LICENSE).
