# Canonical Topology Contracts v1 (Stage 22C)

## Purpose

Stage 22C introduces a **kernel-independent canonical topology layer** for
Origlyph CAD.  Its purpose is to provide a stable, deterministic, strongly
validated representation of CAD/B-Rep connectivity that can serve as the
integration boundary between:

* a future CAD kernel/backend (STEP parser, OpenCascade adapter, etc.), and
* the Origlyph domain (datum selection, GD&T analysis, tolerance workspace,
  governance chain).

This layer defines the structural contracts.  It does not perform any geometry
kernel computation and does not implement any file-format parser.

**Stage 22C does not implement production STEP import.**

**Stage 22C does not introduce a B-Rep CAD kernel dependency.**

---

## Topology vs Geometry

These two concerns are strictly separated in this architecture:

| Concern | Responsibility | Location |
|---------|----------------|----------|
| **Topology** | Connectivity and identity — which entities exist and how they reference each other | `origlyph.cad.topology` |
| **Geometry** | Shape and location — where things are in space, curve/surface math | `origlyph.geometry` |

A topology entity may carry an *optional* geometry binding (e.g.
`TopologyVertex.point: Optional[Point3D]`) but topology identity is never
derived from geometry values.  This separation means:

* The topology layer can be populated from a STEP file before full geometry
  evaluation is complete.
* Geometry can be updated or recomputed without invalidating topology identity.
* Tests can validate topology contracts without needing geometry math.

---

## Topology Hierarchy

```
CanonicalTopologyModel
  │
  ├─ TopologyVertex   (0-D: a point in topological space)
  │
  ├─ TopologyEdge     (1-D: bounded by two vertices, oriented)
  │
  ├─ TopologyWire     (ordered sequence of edges; a connected path)
  │
  ├─ TopologyFace     (2-D: outer wire + optional inner wires/holes, oriented)
  │
  ├─ TopologyShell    (ordered set of faces forming a surface network)
  │
  └─ TopologySolid    (volumetric: outer shell + optional inner voids)
```

Each level in the hierarchy references the level below by
`TopologyEntityId` — an explicit, immutable, deterministic identifier.

---

## Identity Rules

### `TopologyEntityId`

* An immutable frozen dataclass wrapping a non-empty, stripped `str`.
* Identity is purely value-based: no memory address, no random UUID, no
  timestamp, no hostname, no local filesystem path.
* `TopologyEntityId("v1") == TopologyEntityId("v1")` always.
* `hash(TopologyEntityId("v1")) == hash(TopologyEntityId("v1"))` always.

### ID namespace policy

IDs are **unique within their entity kind collection** inside a
`CanonicalTopologyModel`.  Cross-kind collision is **permitted and expected**:
the same string value (e.g. `"1"`) may appear as both a vertex ID and an edge
ID without conflict.  This follows B-Rep source format conventions where
different entity types often share integer key spaces.

### Source vs canonical identity

| Concept | Type | Scope |
|---------|------|-------|
| **Source entity key** | `SourceEntityIdentity.source_entity_key` | Native to one CAD document |
| **Canonical topology ID** | `TopologyEntityId.value` | Scoped to one `CanonicalTopologyModel` snapshot |

These are distinct concepts.  A `CanonicalTopologyModel` does not claim that
its `TopologyEntityId` values survive across CAD revisions.

---

## Persistent Topology Naming Across Revisions

**Canonical topology identity within a model snapshot does not by itself solve
persistent topology naming across CAD revisions.**

A face that is assigned `TopologyEntityId("face_42")` in one import result may
receive a different ID when the source CAD file is revised — or the face may
be split, merged, or removed entirely.  Origlyph does not claim to solve this
problem in Stage 22C.  Future work may introduce topology naming heuristics
(e.g. geometric proximity matching, stable sub-graph fingerprinting) but these
require explicit design, proof, and test coverage before they can be claimed.

**`PERSISTENT_TOPOLOGY_NAMING_ACROSS_REVISIONS: NOT_SOLVED`**

---

## Reference Validation

`CanonicalTopologyModel` performs fail-closed validation at construction:

1. **Duplicate IDs within a kind** → `DuplicateTopologyIdError`
2. **Dangling references** (a reference to a non-existent entity) → `DanglingTopologyReferenceError`

No partial or silently repaired models are produced.  Either construction
succeeds with a fully valid model or it raises.

Validation covers:

* `TopologyEdge.start_vertex_id` and `end_vertex_id` → must exist in `vertices`
* `TopologyWire.edge_ids` → each must exist in `edges`
* `TopologyFace.outer_wire_id` and `inner_wire_ids` → must exist in `wires`
* `TopologyShell.face_ids` → each must exist in `faces`
* `TopologySolid.outer_shell_id` and `inner_shell_ids` → must exist in `shells`

---

## Orientation

`TopologyOrientation` is a two-member `str` enum:

* `FORWARD` — natural parametric sense
* `REVERSED` — reversed sense (flipped normal / reversed traversal)

There is no `UNKNOWN` member.  An invalid orientation string is rejected with
`TopologyValidationError` at entity construction.

---

## Adjacency

`CanonicalTopologyModel` exposes derived, stateless adjacency helpers:

| Helper | Returns |
|--------|---------|
| `edges_for_vertex(vertex_id)` | edges whose start or end is `vertex_id` |
| `wires_for_edge(edge_id)` | wires that reference `edge_id` |
| `faces_for_wire(wire_id)` | faces whose outer or inner boundary is `wire_id` |
| `shells_for_face(face_id)` | shells that reference `face_id` |
| `solids_for_shell(shell_id)` | solids whose outer or inner shell is `shell_id` |

These are computed on each call with no mutable hidden cache.  Traversal
is deterministic: entities are stored in declaration order.

---

## Provenance Binding

Each topology entity carries an `Optional[SourceEntityIdentity]` that traces
it back to the native entity in the originating CAD document:

```
TopologyVertex.source_identity: Optional[SourceEntityIdentity]
TopologyEdge.source_identity:   Optional[SourceEntityIdentity]
TopologyFace.source_identity:   Optional[SourceEntityIdentity]
TopologyShell.source_identity:  Optional[SourceEntityIdentity]
TopologySolid.source_identity:  Optional[SourceEntityIdentity]
```

`SourceEntityIdentity` carries `source_document: SourceDocumentIdentity` and
`source_entity_key: str` — both explicit, both deterministic.  `topology ID`
does not encode local absolute filesystem paths; paths are carried only by
`SourceDocumentIdentity.original_filename` where explicitly supplied.

---

## Adapter Boundary

`CadTopologyAdapter` (defined in `origlyph.cad.topology_adapter`) is a
`runtime_checkable` Protocol that isolates the future kernel-specific backend
object from the Origlyph domain:

```python
class CadTopologyAdapter(Protocol):
    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel: ...
```

The adapter is the only entity permitted to hold kernel-specific objects.
Nothing beyond `CadTopologyAdapter.to_canonical_topology()` ever enters the
Origlyph domain.

`UnsupportedCadTopologyBackendError` is raised by any code path that would
require a real kernel but has none.  This makes it impossible to accidentally
claim STEP/B-Rep support in Stage 22C.

---

## Relationship to `NeutralModel`

`CanonicalTopologyModel` and `NeutralModel` are **separate layers** in
Stage 22C.  They are not interchangeable:

| Layer | Purpose | Input |
|-------|---------|-------|
| `NeutralModel` | Flat entity classification + optional primitive geometry | STL facets, DXF entities |
| `CanonicalTopologyModel` | B-Rep connectivity hierarchy | Future STEP/B-Rep backend |

The intended future relationship:

```
STEP file
  → CadTopologyAdapter.to_canonical_topology()
  → CanonicalTopologyModel          ← topology connectivity
  → (future) geometry evaluation
  → (future) bridge to NeutralModel / datum/GD&T layer
```

In Stage 22C these paths are not yet connected.  The existing STL workflow
remains unchanged:

```
STL bytes
  → StlImporter
  → NeutralModel
  → extract_candidates (bridge.py)
  → datum/tolerance pipeline
```

---

## Geometry Binding

A topology entity that carries geometry uses **existing `origlyph.geometry`
value objects** only:

* `TopologyVertex.point: Optional[Point3D]`

Future stages may add:

* `TopologyEdge` → curve reference (not introduced in Stage 22C; no curve
  types currently exist in `origlyph.geometry`)
* `TopologyFace` → surface reference (not introduced in Stage 22C)

Stage 22C does not invent fake curve or surface mathematics.  Unsupported
geometry bindings are represented as `None` (explicitly absent, not silently
dropped).

---

## Persistence Non-Goal

`CanonicalTopologyModel` is a **runtime/domain object only** in Stage 22C.
It is not persisted to the project file and does not modify the workspace
schema (currently at `v5`).

If persistence becomes necessary in a future stage, it will require:
* Explicit schema design
* `OriglyphProject.extensions` key registration
* Full roundtrip test coverage

Stage 22C does not introduce schema v6.

---

## Current Limitations

1. No STEP parser — `CanonicalTopologyModel` can only be constructed
   programmatically in Stage 22C.
2. No B-Rep kernel — no watertightness solver, no boolean operations, no mass
   property computation.
3. No curve/surface geometry on edges/faces — bindings are `None` until a
   geometry layer expansion is authorised.
4. No persistent naming across CAD revisions — see dedicated section above.
5. No automatic datum selection from topology — datum assignment remains
   explicit and manual.

---

## Future Integration Path

```
Stage 22C (now)
  Canonical topology contracts, kernel-independent
  CadTopologyAdapter protocol defined, no backend

Future stage N
  STEP backend authorised (CadTopologyAdapter implementation)
  Topology → NeutralModel bridge designed

Future stage N+1
  Persistent naming heuristics (if approved)
  Topology → datum/GD&T extraction (if approved)
```

---

## Exception Hierarchy

```
OriglyphCadError
  └─ TopologyValidationError        (topology is structurally invalid)
       ├─ DuplicateTopologyIdError  (same ID used twice in one kind collection)
       └─ DanglingTopologyReferenceError  (reference to non-existent entity)

OriglyphCadError
  └─ UnsupportedCadTopologyBackendError  (no kernel available)
```

---

*Stage 22C — Canonical Topology Contracts & CAD Adapter Isolation v1*
