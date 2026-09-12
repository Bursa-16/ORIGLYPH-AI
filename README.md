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

Supported candidate kinds include:

POINT
LINE
AXIS
PLANE

Additional behaviour:

ReferencePoint / ReferenceSurface artifacts for POINT / PLANE candidates
PhysicalFeature representation for all candidate kinds
deterministic provenance validation
explicit ConstraintType:
PRIMARY
SECONDARY
TERTIARY
deterministic 3-2-1 degree-of-freedom constraint sets
injected deterministic theoretical-datum simulator
sequence-authority ordering
support for partial datum reference frames
verified full 3-2-1 path from three STL facets
no automatic datum-role inference

The explicit role supplied by the engineering workflow remains authoritative.

Drawing / Context Foundation

Declaration records carry engineering context through exact model lookup APIs:

DatumFeatureDeclaration
DrawingDatumReferenceFrameDeclaration
FunctionalRelevanceDeclaration

These records preserve provenance and context. They do not automatically infer,
rank, or assign engineering meaning.

Deterministic 1D Tolerance Architecture

Origlyph currently includes a deterministic one-dimensional tolerance-analysis
architecture.

Engineering Analysis

Implemented capabilities include:

worst-case stack analysis
statistical RSS analysis
covariance-aware statistical analysis
sensitivity analysis
deterministic tolerance budgeting
allocation validation
worst-case allocation reconciliation
statistical allocation reconciliation

Representative public capabilities include:

worst_case_budget
statistical_budget
worst_case_window_compliance
validate_allocation
reconcile_allocation
reconcile_statistical_allocation
Deterministic Decision Layer

Engineering-analysis outputs may be aggregated into a deterministic tolerance
decision using:

evaluate_tolerance_decision

The decision layer evaluates authoritative engineering inputs and produces
explicit deterministic decision states rather than AI-generated engineering
judgements.

Decision Evidence

The deterministic decision may be converted into structured evidence through:

build_decision_evidence
explain_tolerance_decision

Evidence remains linked to the authoritative deterministic decision.

Decision Report

Origlyph provides a deterministic report envelope through:

build_decision_report
decision_report_from_dict

The report architecture preserves deterministic identity and structured
engineering evidence.

Audit and Replay Architecture

The deterministic audit chain extends the engineering decision without
recomputing engineering results unnecessarily.

Report Integrity
validate_decision_report_integrity

provides structural integrity validation of decision reports.

Audit Package and Replay Manifest

Origlyph provides:

build_decision_audit_package
verify_decision_audit_package
audit_package_from_dict

The audit package binds deterministic report, integrity, provenance, and replay
metadata using deterministic fingerprints.

Audit Package Comparison
compare_decision_audit_packages

compares deterministic audit packages and identifies structural or engineering
changes.

Change Impact Assessment
assess_audit_change_impact

classifies already-detected audit changes into deterministic impact categories.

Change Disposition
determine_audit_change_disposition

maps deterministic impact into governed action requirements.

Approval Readiness
evaluate_audit_approval_readiness

determines whether the deterministic engineering/audit chain is structurally
ready for an external governed-acceptance workflow.

Readiness is not equivalent to human approval.

Governed Acceptance Architecture

Origlyph provides a deterministic structural acceptance-artifact chain.

The implemented flow is:

Audit comparison
→ Change impact
→ Change disposition
→ Approval readiness
→ Governed acceptance handoff
→ External acceptance record
→ Verification envelope
→ Closure manifest
Governed Acceptance Handoff
build_audit_acceptance_handoff

packages the deterministic comparison, impact, disposition, and readiness chain
for an external governed workflow.

External Acceptance Record
validate_audit_acceptance_record

validates the structural consistency of a caller-supplied external acceptance
record.

External authority references remain opaque caller-supplied references.

Origlyph does not authenticate the referenced person, organisation, or legal
authority.

Acceptance Verification Envelope
build_acceptance_record_verification_envelope

verifies deterministic structural binding between the governed handoff and the
validated external acceptance record.

Acceptance Closure Manifest
build_acceptance_closure_manifest

creates the final deterministic closure manifest over:

governed handoff
validated acceptance record
verification envelope

The closure manifest provides structural completeness and deterministic identity.
It does not fabricate approval, signatures, authenticated identities, or legal
authority.

Deterministic Identity and Serialization

The late-stage audit and governed-acceptance architecture uses deterministic
canonical serialization and SHA-256 fingerprints.

Relevant identities include:

audit package identity/fingerprints
handoff_id
acceptance_record_id
envelope_id
closure_id

Canonical serialization conventions include:

sorted JSON keys
compact deterministic separators where used by identity-bearing artifacts
ASCII-safe serialization
rejection of non-finite numeric values
deterministic collection ordering
explicit exclusion of self-identifying hash fields from their own fingerprint payloads

No runtime identity depends on:

timestamps
UUIDs
randomness
hostnames
user names
local filesystem paths
process IDs
Python object memory addresses
Fail-Closed Engineering Policy

Origlyph follows fail-closed behaviour throughout the deterministic engineering,
audit, and acceptance chain.

Malformed, incomplete, contradictory, incompatible, stale, or unsupported
artifacts must not silently become:

PASS
READY
ACCEPT
VERIFIED
COMPLETE

Engineering evidence must remain explicit and internally consistent.

Trust Boundary

Origlyph deliberately distinguishes deterministic structural verification from
external human or legal authority.

Origlyph currently does not provide:

human identity authentication
organisational authority authentication
digital-signature validation
cryptographic signer verification
legal authorization validation
non-repudiation services
legally binding approval
manufacturing certification

Fields such as external authority references are preserved as caller-supplied
references only.

End-to-End Capability
CAD to Datum

The first concrete CAD-file-to-datum workflow is:

ASCII/Binary STL
→ NeutralModel
→ BoundedPlanarFace
→ PLANE candidate
→ BoundReference
→ DatumConstraint
→ DatumReferenceFrame

This flow is exercised end-to-end by tests.

STL support represents facet geometry only. It does not imply:

mesh topology
B-Rep topology
solids
STEP support
Tolerance to Governed Closure

The deterministic tolerance/governance flow is:

Engineering analysis
→ Tolerance decision
→ Decision evidence
→ Decision report
→ Report integrity
→ Audit package / replay manifest
→ Audit comparison
→ Change impact
→ Change disposition
→ Approval readiness
→ Governed acceptance handoff
→ External acceptance record
→ Verification envelope
→ Closure manifest

Each stage has a distinct responsibility and preserves deterministic traceability
through the chain.

Deterministic Boundaries

Origlyph currently enforces:

no hidden datum inference
no automatic datum-role inference
no authoritative AI engineering decisions
no silent standards interpretation
no silent engineering-evidence substitution
no fabricated approval
no fabricated reviewer/signature identity
no upstream recomputation in the governed-acceptance artifact chain
missing or contradictory evidence fails closed
Explicit Alpha Limitations / Non-Scope

This alpha does not yet provide:

CAD
STEP import
IGES import
DXF import
B-Rep topology
topology adjacency
mesh welding / repair
watertightness inference
solid / Boolean modelling as a CAD kernel
Datum / GD&T
automatic datum ranking
automatic datum recommendation
automatic datum-role inference
full GD&T compliance evaluation
automatic standards interpretation
Tolerance

The deterministic 1D tolerance architecture is implemented, but this alpha does
not claim:

full multidimensional tolerance simulation
production-certified tolerance verification
manufacturing measurement acceptance/rejection
complete ISO GPS compliance
complete ASME Y14.5 compliance
Monte Carlo production simulation
commercial-grade variation-analysis equivalence
Governance / Acceptance

This alpha does not provide:

authenticated external signers
signature verification
legal acceptance validation
organisational authority validation
non-repudiation infrastructure
persistence-backed governance workflow
production workflow orchestration
Productization

The current architecture does not yet provide:

complete production GUI coverage
full CLI exposure for all tolerance/audit capabilities
persistence/storage integration
serialized reconstruction APIs for all governed-acceptance artifacts
schema migration framework
enterprise authorization
production certification
Architecture Principles
Deterministic engineering calculations are the authoritative computational path wherever implemented.
AI may assist but must never silently override deterministic engineering results.
AI behaviour must remain additive, explainable, and traceable.
Engineering calculations, AI reasoning, UI, data access, and governance remain architecturally separated.
No proprietary OEM or standards content may be embedded without explicit provenance and authorization.
The system must support future TR/EN internationalization.
CAD integration must remain decoupled from individual CAD vendors.
Geometry, datum, GD&T, tolerance, audit, and governance domains remain modular.
Auditability, provenance, revisioning, deterministic identity, validation, and fail-closed behaviour are first-class architectural concerns.
Legacy code may be used only as requirements/reference material under the clean-room policy.
Engineering artefacts should be immutable wherever practical.
Deterministic workflow stages must preserve responsibility boundaries and avoid silent recomputation.
AI Boundary

AI is advisory and additive.

AI is not an engineering authority inside Origlyph.

It must not silently override:

deterministic calculations
tolerance decisions
datum-role assignments
audit results
change dispositions
readiness gates
governed acceptance records

When required engineering evidence is unavailable or contradictory, deterministic
processing fails closed.

No AI datum-ranking system is implemented in this release.

The Recommender contract remains a reserved future protocol.

Clean-Room Policy

No legacy DatumIQ source code is migrated.

No TorqPro source/material is copied.

No SpotWeld-AI source/material is copied.

No OEM/FCA proprietary material is copied.

No proprietary standards text or tables are embedded without provenance and
authorization.

Reference material may guide clean-room reimplementation only.

All engineering logic must have traceable provenance or first-principles
derivation.

Package Structure Overview
src/origlyph/ — canonical Python package namespace
src/origlyph/geometry/ — geometry interrogation foundation
src/origlyph/cad/ — CAD identity, neutral model, importer, STL bridge, binding, roles, evaluation
src/origlyph/datum/ — datum/reference domain, constraints, DOF, DRF
src/origlyph/tolerance/ — deterministic tolerance analysis, decision, evidence, audit, change governance, and governed-acceptance architecture
src/origlyph/gdandt/ — GD&T assistance / automation boundary; broader implementation remains future work
src/origlyph/assembly/ — assembly-level geometry reasoning boundary; broader implementation remains future work
src/origlyph/provenance/ — dedicated provenance layer reserved; provenance currently carried by domain contracts
src/origlyph/core/ — future cross-domain orchestration boundary
src/origlyph/ai/ — future AI integration boundary
Installation

Development installation:

py -m pip install -e ".[dev]"
Quick STL Demo
py examples\stl_datum_demo.py path\to\part.stl

Notes:

STL coordinates are explicitly declared as millimetres (mm)
no automatic unit inference or conversion is performed
the demo DRF uses valid planar facets only to exercise the deterministic API
this is not automatic datum recommendation

Origlyph does not automatically rank, score, or recommend datum features.

Quick GUI Demo
py examples\stl_datum_gui.py

The current GUI:

provides a native local *.stl file picker
contains no hardcoded CAD path
performs no network operation
treats STL dimensions explicitly as millimetres
displays stored STL facet normal as non-authoritative diagnostic metadata
preserves winding-derived face geometry as authoritative
requires manual PRIMARY / SECONDARY / TERTIARY role assignment
prevents the same candidate from occupying multiple DRF roles
does not automatically rank or recommend datum features
Verification

Development quality gates:

py -m pytest tests/unit/tolerance -q
py -m pytest -q
py -m ruff check src tests
py -m pyright

Verified architecture-freeze baseline for v0.4.0-alpha.4:

Tolerance tests: 741 passed
Full test suite: 1275 passed
Ruff: PASS
Pyright: PASS — 0 errors, 0 warnings

Stage 15X architecture and release-readiness assessment concluded:

RELEASE_READINESS_CONFIRMED

No additional tolerance-domain primitive was identified as required before the
current alpha architecture freeze.

Release

Current prerelease:

v0.4.0-alpha.4

Package version:

0.4.0a4

Release status:

PRE-RELEASE / ALPHA

The release consolidates the deterministic tolerance, audit, replay,
change-governance, and governed-acceptance architecture completed through
Stage 15W.

Previous release:

v0.4.0-alpha.3
Future / Non-Blocking Work

The following items remain future work and are not release blockers for the
current architecture:

shared internal canonical hashing utility
deserialization / reconstruction APIs for serialized governed artifacts
schema migration and version-compatibility policy
persistence / storage integration
broader CLI exposure
broader GUI exposure
external signature verification
external identity / authority verification
multidimensional tolerance-analysis expansion
broader GD&T capability
STEP / B-Rep support
assembly-level variation analysis
explainable AI assistance over deterministic engineering results
License

Released under the MIT License.

See LICENSE.


Ben özellikle şu üç önemli düzeltmeyi yaptım:

- `alpha.3 / 0.4.0a3` → **`alpha.4 / 0.4.0a4`**
- Eski README’deki **“engineering tolerance runtime / tolerance stack-up solver yok”** ifadelerini kaldırdım; artık 1D deterministic tolerance mimarisi gerçekten mevcut.
- Stage 15K–15W arasındaki **decision → evidence → audit → comparison → impact → disposition → readiness → handoff → acceptance → verification → closure** zincirini README’ye ekledim.

Bir nokta daha: Release commit/tag henüz gerçekten tamamlanmadıysa, README’deki `v0.4.0-alpha.4` ve `0.4.0a4` ifadeleri
