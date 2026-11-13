# CAD Source Project Bridge v1

**Stage:** 22F
**Classification:** STEP_SOURCE_REFERENCE_BRIDGE
**Status:** Pre-commit review

---

## Purpose

Stage 22F introduces a bridge between the Stage 22E controlled STEP import
(`load_step_topology`) and the Origlyph project persistence model
(`OriglyphProject`).  After importing a STEP file at runtime, an engineer can
record the source identity — but not the topology — in a saved project.

**Stage 22F persists STEP source identity, not B-Rep topology.**

---

## Mandatory Disclosures

**CanonicalTopologyModel is not serialized into origlyph.project.v1.**

**Local filesystem paths do not participate in authoritative project identity.**

**Persistent topology naming across CAD revisions remains unsolved.**

**Reopening a project restores the STEP source reference; runtime topology
must be reconstructed explicitly.**

---

## Public Entry Points

```python
from origlyph.project import (
    cad_source_reference_from_step,
    project_with_step_source,
)
```

### `cad_source_reference_from_step`

```python
def cad_source_reference_from_step(
    source: SourceDocumentIdentity,
    path: Path | str,
    *,
    expected_fingerprint: str | None = None,
    local_path_hint: str | None = None,
) -> CadSourceReference:
```

Converts a Stage 22E `SourceDocumentIdentity` to a `CadSourceReference`
suitable for inclusion in an `OriglyphProject`.  Does not parse STEP topology.

### `project_with_step_source`

```python
def project_with_step_source(
    project: OriglyphProject,
    source: SourceDocumentIdentity,
    path: Path | str,
    *,
    expected_fingerprint: str | None = None,
    local_path_hint: str | None = None,
) -> OriglyphProject:
```

Returns a new `OriglyphProject` with the STEP source reference appended.
All existing state is preserved.

---

## CadSourceReference Reuse

Stage 22F reuses the existing `CadSourceReference` from `origlyph.project.v1`
without modification.  No new persistence types are introduced.

```python
@dataclass(frozen=True, slots=True)
class CadSourceReference:
    source_id: str
    format: str             # "step" for STEP/STP files
    length_unit: str        # from source.unit_system.length_unit
    fingerprint: str        # SHA-256 of file bytes (64-char hex)
    local_path_hint: str | None = None
```

---

## SHA-256 Source Identity

The authoritative content fingerprint is computed as:

```
SHA-256(file_bytes)  →  64-character lowercase hex string
```

Properties:
- Same bytes, same path → same fingerprint
- Same bytes, different path → same fingerprint
- Different bytes → different fingerprint
- Fingerprint does not include: absolute path, machine name, username,
  timestamp, mtime, UUID, Python `hash()`, or OCP handle

---

## .step / .stp Normalization

Both `.step` and `.stp` extensions are accepted (case-insensitive).  Both
normalize to `format = "step"` in the persisted `CadSourceReference`.

Rejected formats: `.stl`, `.iges`, `.igs`, `.dxf`, unknown extensions.
All rejections are fail-closed (`InvalidProjectError`).

---

## local_path_hint Semantics

`local_path_hint` is an optional reopen-convenience field.  It is stored in
the serialized project to help the user locate the original file when
reopening a project.

| Property | Value |
|----------|-------|
| Included in `identity_dict()` | No |
| Included in `project_id` | No |
| Changes `fingerprint` | No |
| Changes `project_id` | No |
| Included in `as_dict()` | Yes |
| Persisted to JSON | Yes |

Changing only `local_path_hint` does not change the authoritative project
identity.

---

## Project Identity Behavior

`project_id` is SHA-256 of canonical JSON of:
`{schema_version, cad_sources[identity_dict()], datum_state, tolerance_state,
artifact_refs, extensions}`

Adding a STEP source reference changes `cad_sources`, which changes
`project_id`.  This is by design: different CAD source content produces
different project identity.

| Scenario | Outcome |
|----------|---------|
| Same project + same STEP bytes | Same `project_id` |
| Same STEP bytes, different path | Same `project_id` |
| Different STEP bytes | Different `source.fingerprint` → different `project_id` |
| `local_path_hint` change only | `project_id` unchanged |
| Save + load | `project_id` unchanged |

---

## Duplicate Source Policy

| Condition | Outcome |
|-----------|---------|
| Same `source_id` + same `fingerprint` already in project | Return project unchanged (idempotent) |
| Same `source_id` + different `fingerprint` | `InvalidProjectError` |
| Different `source_id` | New entry appended |

---

## Save / Load / Reopen Continuity

```
load_step_topology(path, source)       # Stage 22E — runtime topology
         ↓
cad_source_reference_from_step(source, path)   # Stage 22F — source ref
         ↓
project_with_step_source(project, source, path)
         ↓
save_project(project, file_path)       # JSON on disk
         ↓
load_project(file_path)                # restored project
         ↓
project.cad_sources[0].source_id      # same source identity
project.cad_sources[0].fingerprint    # same fingerprint
         ↓                              project_id unchanged
load_step_topology(path, source)       # reconstruct topology explicitly
```

**Topology is NOT automatically reconstructed on project load.**
The persisted `CadSourceReference` provides the `source_id`, `format`,
`length_unit`, `fingerprint`, and optional `local_path_hint` to help
the engineer locate and reload the STEP file.  The `CanonicalTopologyModel`
must be obtained by calling `load_step_topology` again when needed.

---

## Schema Compatibility

| Schema version | Compatibility |
|----------------|---------------|
| `origlyph.project.v1` | Fully preserved |
| Any version without STEP source | Loads correctly (empty `cad_sources`) |
| New schema v2 | Not introduced in Stage 22F |

The serializer (`serialization.py`) uses `_exact_keys` validation.
`CadSourceReference` on-disk format is unchanged; no new fields are added.

---

## Topology Persistence Exclusion

The following types are **never** serialized into `origlyph.project.v1`:

- `CanonicalTopologyModel`
- `TopologyVertex`, `TopologyEdge`, `TopologyWire`
- `TopologyFace`, `TopologyShell`, `TopologySolid`
- Any OCP/OCCT kernel handle

Only source reference metadata (`source_id`, `format`, `length_unit`,
`fingerprint`, `local_path_hint`) is persisted.

---

## Kernel Independence

```
PROJECT_SOURCE_BRIDGE_REQUIRES_OCP: NO
```

`cad_source_reference_from_step` reads file bytes and computes SHA-256.
It does not import, invoke, or depend on the OCP kernel.  The bridge is
available in core installs without `origlyph[brep]`.

---

## Current Limitations

- Persistent topology naming across CAD revisions is not solved.
  Snapshot topology IDs from Stage 22E are deterministic within one import
  but may change when the STEP file is revised.

- The bridge records `length_unit` only; `angle_unit` from
  `SourceUnitSystem` is not persisted in `CadSourceReference` (which has no
  `angle_unit` field).  This is a v1 schema constraint, not a Stage 22F
  decision.

- `source.fingerprint` from `SourceDocumentIdentity` is not automatically
  cross-checked against the computed file hash.  Callers who want validation
  must pass the value as `expected_fingerprint`.

---

## Future Explicit Topology Rehydration

When a future stage requires topology in a project session:

```python
project = load_project(path)
source_ref = project.cad_sources[0]

# Reconstruct source identity explicitly
source = SourceDocumentIdentity(
    source_id=source_ref.source_id,
    format=CadFormat.STEP,
    unit_system=SourceUnitSystem(length_unit=source_ref.length_unit, ...),
    original_filename=source_ref.local_path_hint,
)

# Reload topology explicitly (Stage 22E)
topology = load_step_topology(step_file_path, source)
```

No automatic topology reconstruction is planned for Stage 22F or 22G.

---

## Not in Stage 22F

- Schema v2 or any schema change
- Persistence of `CanonicalTopologyModel` or topology entities
- Automatic datum selection from STEP geometry
- Automatic GD&T interpretation
- STEP property inspector or topology browser
- Persistent topology naming across CAD revisions
- OCP as a mandatory dependency
- Any modification to tolerance math, governance, or workspace schema
