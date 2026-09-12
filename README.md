# Origlyph Engineering Platform

## Project Identity

* **Name:** Origlyph
* **Current status:** Fifth public alpha — deterministic CAD, datum, tolerance-analysis, audit, and governed-acceptance engineering foundation with interactive desktop GUI
* **Package version:** `0.4.0a4`
* **Current release/tag:** `v0.4.0-alpha.4`

## Purpose

Origlyph is an engineering platform intended for:

* CAD data ingestion and geometry interrogation
* datum/reference definition workflows
* GD&T assistance
* deterministic tolerance analysis
* dimensional-chain / tolerance-stack analysis
* assembly geometry reasoning
* deterministic engineering decisions with traceable evidence
* audit, replay, change-impact, and governed engineering workflows
* future explainable AI assistance

These are product goals. Only the capabilities listed under
[What Is Currently Implemented](#what-is-currently-implemented) exist today;
everything else is roadmap, not implementation.

## Current Development Status

v0.4.0-alpha.4 consolidates the deterministic engineering architecture developed
through the Stage 15 tolerance and governed-acceptance programme.

The current release includes:

* deterministic geometry foundations
* CAD identity and neutral-model contracts
* concrete ASCII/binary STL import
* source-to-neutral provenance
* CAD-to-datum candidate bridging
* explicit datum/reference binding
* explicit PRIMARY / SECONDARY / TERTIARY role assignment
* `DatumReferenceFrame` construction
* advisory candidate evaluation
* executable STL datum CLI workflow
* interactive Tkinter desktop GUI
* deterministic 1D worst-case tolerance analysis
* statistical RSS analysis
* covariance-aware statistical analysis
* sensitivity analysis
* tolerance budgeting
* allocation validation
* worst-case allocation reconciliation
* statistical allocation reconciliation
* deterministic tolerance decision evaluation
* deterministic decision evidence and explanation
* deterministic report and integrity validation
* deterministic audit package and replay manifest
* audit package comparison
* deterministic change-impact assessment
* deterministic change disposition
* approval-readiness evaluation
* governed acceptance handoff
* external acceptance-record validation
* acceptance-record verification envelope
* final governed acceptance closure manifest

The tolerance and governed-acceptance pipeline has been architecture-audited for
determinism, canonical serialization, fail-closed behaviour, identity integrity,
immutability, trust-boundary correctness, public API consistency, and regression
coverage.

This release remains **alpha**. It does **not** claim production certification,
ASME/ISO compliance, authenticated human authority, digital-signature validation,
legal acceptance, or validated manufacturing acceptance.

---

# What Is Currently Implemented

## Geometry Foundation

* `Point3D`, `Vector3D`, `Line3D`, `Plane3D` — immutable, validated value objects in canonical millimetre coordinates
* bounded planar faces (`BoundedPlanarFace`) — ordered, coplanar vertex cycles with derived plane / area / centroid / perimeter
* coordinate frames — orthonormal, right-handed
* rigid transforms — translation, rotation, composition, inverse
* distances, angles, projections, and closest-point operations
* computational floating-point tolerance policy for numerical robustness

The computational floating-point policy is explicitly **not** an engineering
tolerance and must never be used to mask an engineering-relevant deviation.

## CAD Foundation

* identity separation for source documents, source entities, neutral entities, and the domain:
  * `SourceDocumentIdentity`
  * `SourceEntityIdentity`
  * `NeutralEntityIdentity`
  * `DomainIdentity`
  * `SourceUnitSystem`
* `NeutralModel` with duplicate rejection and deterministic entity ordering
* `SourceToNeutralMapping` — exact, duplicate-safe source↔neutral mapping
* `NeutralModel.reverse_lookup` — model-scoped, exact, fail-closed source identity resolution
* deterministic provenance carried on imported entities
* fail-closed warning / unsupported-content handling:
  * `CadWarning`
  * `UnsupportedContent`
* `CadImporter` protocol
* concrete `StlImporter`

## STL Importer

* ASCII STL support
* binary STL support
* injected `bytes_loader` as the source-acquisition boundary
* no filesystem I/O inside the importer
* deterministic binary detection using the exact `84 + 50 * facet_count` layout
* correct handling of binary headers beginning with `solid`
* declared source length unit must be `mm`
* no implicit unit conversion
* no scale inference
* stable 0-based `facet-{i}` source and neutral identities
* each valid facet becomes a `BoundedPlanarFace`
* stored STL facet normals remain diagnostic metadata only
* vertex winding remains the geometry authority
* vertices are never silently reordered or flipped
* degenerate facets surface:
  * `CadWarning("DEGENERATE_FACET")`
  * `UnsupportedContent`
* malformed, truncated, oversized, or non-finite payloads fail closed with `CadImportError`

## Datum / Reference Workflow

The deterministic chain currently implemented is:

```text
STL / NeutralModel
→ candidate extraction
→ BridgedCandidate
→ bind_reference
→ BoundReference
→ explicit ConstraintType
→ bind_datum_constraint
→ DatumConstraint
→ bind_datum_reference_frame
→ DatumReferenceFrame
→ advisory evaluate_candidates
