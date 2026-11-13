# Datum-to-Topology Binding v1

**Stage:** 22G
**Classification:** DATUM_TOPOLOGY_BINDING_PERSISTENCE
**Status:** Pre-commit review

---

## Purpose

Stage 22G introduces a persistent binding from an explicit datum role
assignment to a canonical topology entity (face) in a STEP-sourced
`CanonicalTopologyModel`.  The binding allows an Origlyph project to record
which topology entity an engineer designated as a primary/secondary/tertiary
datum, so that the assignment survives a save-reload cycle without requiring
the engineer to repeat the selection.

This is not automatic datum selection, GD&T extraction, or topology naming.
The engineer explicitly selects the face; the binding records that decision
durably.

---

## Mandatory Disclosures

**Datum topology bindings are anchored to an exact CAD source fingerprint.**

**Bindings are deterministic for the same CAD artifact and canonical topology
snapshot.**

**Bindings are not guaranteed to survive CAD source revision changes.**

**CAD revision changes require explicit engineering remapping.**

**CanonicalTopologyModel is not serialized into origlyph.project.v1.**

**Persistent topology naming across CAD revisions remains unsolved.**

---

## Source Fingerprint Anchor

The binding identity is anchored to the SHA-256 content hash of the STEP
file bytes (`CadSourceReference.fingerprint`), which is computed by Stage 22F
(`cad_source_reference_from_step`).

Properties of the fingerprint anchor:

| Scenario | Outcome |
|----------|---------|
| Same file bytes, same path | Same fingerprint |
| Same file bytes, different path | Same fingerprint |
| Different file bytes | Different fingerprint |
| Changed STEP revision | Different fingerprint → binding unresolved |

Local filesystem paths are excluded from the fingerprint and from the binding
encoding.

---

## Canonical Entity Identity

Stage 22C `TopologyEntityId.value` is a deterministic string derived from
OCP/OCCT B-Rep traversal order.  It is unique within a kind-collection within
one topology snapshot.

| Property | Value |
|----------|-------|
| Deterministic for same file bytes + OCP version | Yes |
| Stable across CAD revisions | No |
| UUID/timestamp/random component | No |
| OCP handle or object address | No |

Stage 22G uses `TopologyEntityId.value` as the `entity_id` component of the
binding key.

---

## Binding Encoding

The binding is stored in the existing
`DatumRoleAssignment.bound_reference_key: str | None` field.  No schema
change is required or introduced.

### Binding Format Version

`topology:v1`

### Wire Format

```
topology:v1:{source_fingerprint}:{entity_kind}:{entity_id}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `source_fingerprint` | 64-char lowercase sha256 hex | No colons |
| `entity_kind` | string | `"face"` only (Stage 22G) |
| `entity_id` | non-empty string | May contain colons |

Parsing uses `str.split(":", 4)` (maxsplit=4), which produces exactly five
fields regardless of colons embedded in `entity_id`.  The encoding is
unambiguous, reversible, and deterministic.

### Example

```
topology:v1:a3f8...d1c2:face:0
```

### Backward Compatibility

A `bound_reference_key` that does not start with `topology:v1:` is treated
as `RESOLUTION_UNBOUND` during resolution.  Existing projects with
`bound_reference_key = None` or an older non-topology string continue to load
and behave correctly.

The binding format version (`topology:v1`) is distinct from and independent
of the project schema version (`origlyph.project.v1`).

---

## Project Schema Unchanged

Stage 22G introduces no new project schema version.  `origlyph.project.v1`
is preserved exactly.  The `DatumRoleAssignment.bound_reference_key` field
already exists as `str | None` in the schema and can hold the encoding
described above.

---

## Project Identity Behavior

`DatumRoleAssignment.bound_reference_key` contributes to `datum_state`, which
is included in the `project_id` derivation.  Therefore:

| Scenario | project_id |
|----------|-----------|
| Same binding (same fingerprint + same entity_id) | Unchanged |
| Different entity_id | Changes |
| Different source fingerprint | Changes |
| local_path_hint change only | Unchanged |
| Save + load roundtrip | Unchanged |

---

## Local Path Exclusion

Local filesystem paths are **not** included in:

- `DatumTopologyRef.source_fingerprint` (content hash only)
- The encoded `bound_reference_key` wire format
- `project_id`

The `local_path_hint` field on `CadSourceReference` (from Stage 22F) is a
reopen-convenience field that is excluded from authoritative identity.

---

## Same-Source Reopen Resolution

For the same exact STEP file bytes:

```
load_project(path)
  → datum_state.assignments[*].bound_reference_key
  → decode_datum_topology_ref(key)
  → DatumTopologyRef.source_fingerprint
  → verify matches project.cad_sources[*].fingerprint    ← Stage 22F
  → load_step_topology(step_path, source)                ← Stage 22E explicit
  → resolve_datum_topology_bindings(project, topology, fp)
  → RESOLUTION_RESOLVED
```

Topology is **not** automatically reconstructed on project load.  The
engineer must call `load_step_topology` explicitly and pass the resulting
`CanonicalTopologyModel` to `resolve_datum_topology_bindings`.

---

## CAD Revision Mismatch Behavior

When the STEP file content changes (even a single byte):

1. `sha256(new_bytes) != sha256(old_bytes)` → `topology_fingerprint` differs
2. `ref.source_fingerprint != topology_fingerprint` → resolution fails closed
3. Status: `RESOLUTION_UNRESOLVED_SOURCE_REVISION`
4. No automatic remapping occurs.  The engineer must re-select a face in the
   revised topology and create a new binding.

---

## Missing Entity Behavior

When the source fingerprint matches but the target `entity_id` is not found
in the topology model:

- Status: `RESOLUTION_UNRESOLVED_MISSING_ENTITY`
- No nearest-face matching, no geometric guessing.
- The engineer must re-select explicitly.

---

## No Automatic Remapping

Origlyph never carries datum-topology bindings forward across CAD revisions
automatically.  `RESOLUTION_UNRESOLVED_SOURCE_REVISION` is the explicit,
fail-closed signal that engineering remapping is required.

---

## No Topology Serialization

The following types are **never** serialized into `origlyph.project.v1`:

- `CanonicalTopologyModel`
- `TopologyFace`, `TopologyEdge`, `TopologyVertex`
- `TopologyWire`, `TopologyShell`, `TopologySolid`
- Any OCP/OCCT kernel handle

Only the `bound_reference_key` encoding
(`topology:v1:{fingerprint}:{kind}:{entity_id}`) is persisted.

---

## No OCP Serialization

`datum_topology_binding.py` does not import, invoke, or depend on the OCP
kernel.  The module is importable and usable in `origlyph[core]` installs
without `origlyph[brep]`.  The resolution function accepts a
`CanonicalTopologyModel` as a parameter (which the caller obtains via
`load_step_topology` when OCP is available) but the module itself requires
no OCP import.

---

## Supported Entity Kinds (Stage 22G)

| Kind | Supported | Notes |
|------|-----------|-------|
| `face` | **Yes** | Primary datum-eligible topology entity |
| `edge` | No | Future stage |
| `vertex` | No | Future stage |

---

## Persistent Naming Limitation

Stage 22G does not solve persistent topology naming across CAD revisions.
`TopologyEntityId.value` is deterministic for the same file bytes and OCP
version, but may change when the STEP file is modified or the OCP version
changes.  This limitation is explicit and documented in
`topology.py` (Stage 22C).

---

## Future Datum Semantics and Geometric Validation

Stage 22G binds at the topology connectivity level only.  No surface type
classification (planar, cylindrical, etc.) is attached to `TopologyFace` in
Stage 22G.  Future stages may:

- Add `surface_type: Optional[str]` to `TopologyFace` for geometric validation
- Validate that PRIMARY datum faces are planar or cylindrical
- Extend `SUPPORTED_DATUM_ENTITY_KINDS` to include `"edge"` and `"vertex"`
- Introduce edge-axis and vertex-point datum bindings

None of these changes require a project schema version change.

---

## Public Entry Points

```python
from origlyph.project import (
    DatumTopologyRef,
    DatumTopologyResolution,
    datum_role_assignment_with_topology,
    decode_datum_topology_ref,
    encode_datum_topology_ref,
    is_topology_binding,
    resolve_datum_topology_bindings,
    BINDING_FORMAT_VERSION,
    SUPPORTED_DATUM_ENTITY_KINDS,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED_SOURCE_REVISION,
    RESOLUTION_UNRESOLVED_MISSING_ENTITY,
    RESOLUTION_UNBOUND,
)
```

---

## Not in Stage 22G

- Schema v2 or any project schema change
- Automatic topology reconstruction on project load
- Automatic datum selection from geometry
- Automatic GD&T interpretation
- Geometric semantic validation of datum faces
- Edge or vertex datum bindings
- Multiple-entity datum bindings (e.g. two parallel faces)
- Datum targets (point target, line target, area target)
- Surface type classification on `TopologyFace`
- Persistent topology naming across CAD revisions
- Any modification to tolerance math, governance, or workspace schema
