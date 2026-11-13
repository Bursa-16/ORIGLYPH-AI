# Controlled STEP Integration v1

**Stage:** 22E
**Classification:** EXPERIMENTAL_CONTROLLED_STEP_IMPORT
**Status:** Pre-commit review

---

## Scope

Stage 22E introduces controlled STEP/STP import through the optional B-Rep backend.

This is **not** production STEP support.  It is an explicit, dependency-aware path
from a `.step` or `.stp` file to a `CanonicalTopologyModel` through the Stage 22D.1
OCP adapter.

---

## Mandatory Disclosures

**This stage does not solve persistent topology naming across CAD revisions.**

**STEP/B-Rep topology is not persisted into the Origlyph project model.**

**Automatic datum selection and automatic GD&T interpretation are outside Stage 22E.**

---

## Public Entry Point

```python
from origlyph.cad import load_step_topology

model = load_step_topology(path, source)
```

`load_step_topology(path, source) -> CanonicalTopologyModel`

- `path`: filesystem path to a `.step` or `.stp` file
- `source`: `SourceDocumentIdentity` with `format=CadFormat.STEP`

This is the only new public API surface added in Stage 22E.

---

## Supported Extensions

| Extension | Case-sensitive | Accepted |
|-----------|---------------|----------|
| `.step`   | No (normalized) | Yes |
| `.stp`    | No (normalized) | Yes |

All other extensions fail closed with `UnsupportedCadFormatError`.  No implicit
content-based format detection.

---

## Optional Dependency Requirement

STEP/STP import requires the optional `brep` extra:

```
pip install origlyph[brep]
```

This installs `cadquery-ocp-novtk>=8.0.1.1.0,<9` (Python >=3.11 only).

**Core install (`pip install origlyph`) remains kernel-free.**

When the `brep` extra is not installed:

- `origlyph.cad` imports successfully
- STL workflow is unaffected
- `load_step_topology` raises `StepKernelUnavailableError` with an explicit,
  user-actionable message mentioning `pip install origlyph[brep]`
- No `ImportError` traceback leaks into user-visible output

---

## Dispatch Path

```
load_step_topology(path, source)
  │
  ├─ validate extension (.step / .stp, case-insensitive)   → UnsupportedCadFormatError
  ├─ validate source.format == CadFormat.STEP              → UnsupportedCadFormatError
  │
  └─ StepKernelAdapter(path).to_canonical_topology(source)
       │
       ├─ OCP unavailable                                  → StepKernelUnavailableError
       ├─ file not found                                   → CadImportError
       ├─ malformed STEP                                   → CadImportError
       ├─ empty STEP                                       → CadImportError
       ├─ no solid bodies                                  → CadImportError
       └─ conversion success                               → CanonicalTopologyModel
```

---

## Canonical Topology Output

The returned `CanonicalTopologyModel` follows Stage 22C canonical contracts:

- `TopologySolid` → outer/inner shell references
- `TopologyShell` → face references
- `TopologyFace` → outer wire + inner wire (hole) references
- `TopologyWire` → ordered edge references
- `TopologyEdge` → start/end vertex references + orientation
- `TopologyVertex` → optional `Point3D` geometry binding

No OCP/OCCT kernel objects appear in any returned type.  All entity types are
immutable frozen dataclasses from `origlyph.cad.topology`.

---

## Unit Contract

OCP (OCCT kernel) delivers vertex coordinates in millimetres when reading a STEP
file whose internal unit is millimetres.  No unit conversion is applied by the
Stage 22D.1 adapter.  The declared `SourceUnitSystem` in the passed
`SourceDocumentIdentity` is propagated verbatim into `model.source`.

**Contract:** pass `SourceUnitSystem(length_unit="mm", angle_unit="rad")` for
standard metric STEP files.  The result coordinates will match the STEP file's
declared geometry in millimetres.

No silent unit inference.  An unrecognised source unit raises
`UnsupportedSourceUnitError` at `SourceDocumentIdentity` construction.

---

## Provenance Contract

`model.source` is the exact `SourceDocumentIdentity` passed to `load_step_topology`.

The following provenance fields are available:

| Field | Content |
|-------|---------|
| `source.format` | `CadFormat.STEP` |
| `source.unit_system.length_unit` | caller-declared (typically `"mm"`) |
| `source.original_filename` | caller-provided filename |
| `source.source_id` | caller-provided stable ID |
| `source.fingerprint` | optional caller-provided hash |

No absolute filesystem paths are embedded in canonical IDs.  No usernames or
hostnames appear in any returned entity.

---

## Snapshot Identity

Topology entity IDs (`TopologyEntityId`) are deterministic for the same STEP
file when traversed by the same OCP version.  Three repeated imports of the same
file produce identical vertex/edge/face/solid IDs.

**Snapshot IDs are NOT persistent names across CAD revisions.**  A face ID that
is stable within one import result may be assigned differently when the source CAD
file is revised.  This limitation is intentional, explicit, and not addressed in
Stage 22E.

---

## Failure Modes

All failure modes are fail-closed.  No silent fallback, no empty partial result,
no retry.

| Condition | Exception |
|-----------|-----------|
| Unknown file extension | `UnsupportedCadFormatError` |
| `source.format != CadFormat.STEP` | `UnsupportedCadFormatError` |
| OCP kernel not installed | `StepKernelUnavailableError` |
| File not found | `CadImportError` |
| File is not a regular file | `CadImportError` |
| Malformed STEP content | `CadImportError` |
| Empty STEP file | `CadImportError` |
| STEP with no solid bodies | `CadImportError` |
| Adapter conversion failure | `CadImportError` |
| Topology validation failure | `TopologyValidationError` |

---

## Persistence Boundary

**No topology is persisted.**  `CanonicalTopologyModel` is not written into the
Origlyph project serialization schema.  Project schema v5 is unchanged.

The `SourceDocumentIdentity` metadata (source ID, format, unit, filename,
fingerprint) may be recorded using the existing project source-reference
contract — no new schema fields are added.

---

## STL Behavior

Stage 22E does not modify `StlImporter`, `NeutralModel`, or any existing STL
workflow.  The `load_step_topology` function is a new, independent path.
`StlImporter.can_import()` correctly returns `False` for `CadFormat.STEP` sources.

---

## Core vs. B-Rep Install

| Install command | OCP present | STEP import |
|-----------------|-------------|-------------|
| `pip install origlyph` | No | Fails closed (`StepKernelUnavailableError`) |
| `pip install origlyph[dev]` | No | Fails closed |
| `pip install origlyph[brep]` | Yes (Python ≥3.11) | Real OCCT path |
| `pip install origlyph[dev,brep]` | Yes (Python ≥3.11) | Real OCCT path |

---

## CI Contract

Stage 22E follows the Stage 22D.2 CI split:

**`ci` job** (Python 3.10, no OCP):
- Runs all tests; OCP-dependent tests are skipped via `skip_if_no_ocp`
- New dispatch tests run (OCP-independent paths are exercised via mocking)
- Core install remains kernel-free

**`ci-brep` job** (Python 3.11, `.[dev,brep]`):
- Installs OCP kernel
- Runs all Stage 22D and Stage 22E tests including real STEP traversal
- Both `test_step_dispatch.py` and `test_step_controlled_import.py` are included

---

## Not in Stage 22E

The following are explicitly outside this stage:

- Persistent topology naming across CAD revisions
- Automatic datum selection from STEP geometry
- Automatic GD&T interpretation from STEP annotations
- STEP property inspector or topology browser
- B-Rep rendering or 3D tessellation
- Full/production-grade STEP support
- Schema v6
- Any new persistence layer for topology
- Project identity or governance semantics changes
- IGES, DXF, or any other format beyond `.step`/`.stp`

---

## Next-Stage Candidates

- **Stage 22F:** STEP source reference integration with existing project model
- **Stage 23:** Persistent topology naming strategy (requires dedicated research)
- **Stage 24:** STEP annotation / PMI extraction (requires GD&T domain extension)
