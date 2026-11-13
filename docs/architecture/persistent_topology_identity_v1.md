# Persistent Topology Identity v1

Stage 22H — implemented 2026-11-13

## Purpose

Canonical topology entity IDs (e.g. `f:0001`) are deterministic within a
single STEP file import but change when the source CAD file is revised. This
document describes the persistent identity mechanism introduced in Stage 22H
that allows datum-to-topology bindings to survive CAD revision changes.

---

## Persistent ID Algorithm

Each face in a `CanonicalTopologyModel` receives a `TopologyFaceSignature`
(module `origlyph.cad.topology_signature`). The signature's `persistent_id`
is a **SHA-256 hex digest** of:

```json
{
  "vertex_fingerprint": "<sha256-of-normalised-vertices>",
  "surface_type": "PLANE",
  "surface_params": [0.0, 0.0, 1.0, 0.0]
}
```

This payload does **not** include:

- Python `id()` values, memory addresses, or traversal order
- OCP object pointers
- Entity sequential counters

### Vertex Fingerprint (`compute_vertex_fingerprint`)

1. Collect all vertex coordinates `(x, y, z)` from the face boundary.
2. Compute the centroid of all vertices.
3. Subtract the centroid from every coordinate (translation-invariant).
4. Quantize each coordinate to `QUANTIZE_PRECISION = 1e-6` (sub-micron).
5. Sort all translated, quantized coordinate triples lexicographically
   (order-independent).
6. SHA-256 of the compact canonical JSON of the sorted list.

The fingerprint is **translation-invariant** and **order-independent**.
It is NOT rotation-invariant (by design; rotation changes surface orientation).

---

## Normalization Policy

| Input | Normalization |
|-------|---------------|
| Coordinates | Centroid-subtracted, then quantized to `1e-6` |
| Surface parameters | Quantized to `1e-6` per parameter |
| Face normal | Divided by magnitude, then quantized to `1e-6` |
| Area | Quantized to `1e-6` |
| Non-finite values | Replaced by `0.0` via `_safe_finite()` |

---

## Match Classes

The remap engine (`origlyph.project.topology_revision_remap`) classifies
how well a stored face signature matches candidates in a revised topology:

| Class | Meaning | Auto-remap | Confirmation required |
|-------|---------|-----------|----------------------|
| `EXACT` | `persistent_id` match, or vertex fingerprint + surface type + params all match | Yes | No |
| `PROBABLE` | Surface type matches + centroid within `0.01 mm` + area within 5% | No | Yes |
| `AMBIGUOUS` | Multiple candidates, face split/merge, or identity uncertain | No | Yes |
| `NO_MATCH` | No credible candidate found | No | Yes |

### Scoring Hierarchy

1. **`persistent_id` equality** → `EXACT` (confidence 1.0)
2. **vertex fingerprint + surface type + surface params all match** → `EXACT`
   (confidence 0.98)
3. **surface type match + centroid ≤ 0.01 mm + area within 5%** → `PROBABLE`
   (confidence 0.6–1.0 proportional to centroid distance)
4. **Otherwise** → `NO_MATCH`

### Thresholds

| Constant | Value | Meaning |
|---------|-------|---------|
| `_CENTROID_PROBABLE_TOLERANCE` | `0.01` model units | Max centroid shift for PROBABLE |
| `_AREA_PROBABLE_MAX_RATIO` | `0.05` (5 %) | Max fractional area change for PROBABLE |

---

## Fail-Closed Behavior

| Scenario | Result |
|---------|--------|
| No signature on stored binding (pre-22H) | `NO_MATCH` |
| No candidate in new topology | `NO_MATCH` |
| Multiple candidates (face split/merge) | `AMBIGUOUS` |
| PROBABLE match | `confirmation_required=True`, `auto_remapped=False` |
| EXACT match | `auto_remapped=True` |

**Face split and merge are never auto-remapped** (`FACE_SPLIT_AUTO_REMAP=NO`,
`FACE_MERGE_AUTO_REMAP=NO`).  When a face produces two candidates or two
old faces match one new face, the result is always `AMBIGUOUS`, requiring
explicit engineer confirmation.

---

## Backward Compatibility

### Binding key formats

**v1 (Stage 22G, unchanged):**
```
topology:v1:{source_fingerprint}:{entity_kind}:{entity_id}
```

**v2 (Stage 22H, new):**
```
topology:v2:{source_fingerprint}:{entity_kind}:{entity_id}:{persistent_id_64hex}
```

Where `persistent_id_64hex` is exactly 64 lowercase hex characters (SHA-256).

Parsing rules:
- Detect version by prefix (`topology:v1:` vs `topology:v2:`).
- v1 keys always decode to `DatumTopologyRef.persistent_id = None`.
- v2 keys: `split(":", 4)` → 5 parts; `parts[4]` ends with `":" + 64-hex`.
- `is_topology_binding()` accepts both v1 and v2 prefixes.
- **Schema version unchanged.** No `origlyph.project.v1` schema version bump.

### Pre-22H fixture decode

A Stage 22G binding key (v1 format) decodes unchanged.  The `persistent_id`
field is `None`, which causes `remap_face_binding()` to return `NO_MATCH`
rather than attempting an invalid remap.

---

## OCP Isolation

- No OCP objects are stored in `TopologyFaceSignature`.
- OCP extraction (vertex coordinates, surface type/params) happens inside
  `_get_or_add_face()` in `step_kernel_adapter.py`, inside `try/except`
  blocks that degrade gracefully to `FaceSurfaceType.UNKNOWN` with empty
  `surface_params` on any OCP failure.
- `topology_signature.py` imports only standard-library modules (`hashlib`,
  `json`, `math`, `dataclasses`, `enum`, `typing`).

---

## Files Changed

| File | Role |
|------|------|
| `src/origlyph/cad/topology_signature.py` | NEW — signature data model + computation |
| `src/origlyph/project/topology_revision_remap.py` | NEW — remap engine |
| `src/origlyph/cad/topology.py` | MOD — `TopologyFace.surface_signature` field |
| `src/origlyph/cad/step_kernel_adapter.py` | MOD — OCC surface extraction |
| `src/origlyph/project/datum_topology_binding.py` | MOD — v2 format + new RESOLUTION constants |
| `tests/unit/cad/test_topology_signature.py` | NEW — 36 tests |
| `tests/unit/project/test_topology_revision_remap.py` | NEW — 38 tests |
| `docs/architecture/persistent_topology_identity_v1.md` | NEW — this document |
