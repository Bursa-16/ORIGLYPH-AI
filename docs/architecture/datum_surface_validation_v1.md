# Datum Surface-Type Validation v1 (Stage 22H)

## Purpose

Provides a CAD geometry-layer check that confirms the surface type of a bound
datum topology entity is geometrically appropriate for a GD&T datum role
(PRIMARY, SECONDARY, TERTIARY).

Stage 22H v1 accepts only planar faces (PLANE).  CYLINDER, CONE, TORUS, and
other surface types are classified as INVALID\_SURFACE\_TYPE; unknown geometry
(UNKNOWN) is classified as SURFACE\_TYPE\_UNVALIDATABLE.  Both outcomes fail
closed — no automatic acceptance or override is provided.

## Authoritative statements

**Surface-type validation is a CAD geometry-layer check.**

**Validation does not approve an engineering datum strategy.**

**Validation results are derived state and are not persisted in origlyph.project.v1.**

## Module

`src/origlyph/project/datum_surface_validation.py`

Public API exported via `origlyph.project`:

| Symbol | Kind |
|--------|------|
| `SUPPORTED_VALIDATION_ENTITY_KINDS` | `frozenset[str]` |
| `DatumSurfaceValidationStatus` | `str` enum |
| `DatumSurfaceValidationResult` | frozen dataclass |
| `validate_datum_surface` | function |
| `validate_datum_role_surface` | function |

## Validation flow

```
DatumTopologyRef
  ↓
resolve_datum_topology_bindings()     # binding layer
  ↓
_validate_one_resolution()            # maps resolution status
  ↓
_validate_resolved_face()             # face lookup + surface type check
  ↓
DatumSurfaceValidationResult
```

## Status values

| Status | Meaning |
|--------|---------|
| `VALID` | PLANE face confirmed valid for the datum role |
| `INVALID_SURFACE_TYPE` | Known surface type not accepted in Stage 22H v1 |
| `UNRESOLVED_SURFACE_TYPE` | Face has no surface signature; fail closed |
| `SURFACE_TYPE_UNVALIDATABLE` | UNKNOWN surface type; kernel could not classify |
| `UNSUPPORTED_ENTITY_KIND` | entity\_kind not in `SUPPORTED_VALIDATION_ENTITY_KINDS` |
| `MISSING_ENTITY` | Bound entity absent from topology |
| `SOURCE_MISMATCH` | Binding fingerprint does not match topology fingerprint |
| `UNBOUND` | Assignment has no topology binding |

## Constraints

- Validation **does not** modify the project.
- Validation **does not** persist results to `OriglyphProject`.
- Validation **does not** change `project_id`.
- Validation **does not** introduce automatic datum selection.
- Validation **does not** auto-confirm PROBABLE or AMBIGUOUS remap matches.
- `CanonicalTopologyModel` is never serialized.
- OCP objects are never referenced.
- Schema version is unchanged.

## Surface-type rule table

| Surface type | Stage 22H v1 outcome |
|---|---|
| PLANE | VALID |
| UNKNOWN | SURFACE\_TYPE\_UNVALIDATABLE (fail closed) |
| CYLINDER, CONE, SPHERE, TORUS, REVOLUTION, EXTRUSION, OFFSET, BSPLINE | INVALID\_SURFACE\_TYPE |

Pairwise geometric checks (parallelism, perpendicularity, coaxiality) are
**not** implemented in Stage 22H — no authoritative tolerance constants for
those checks exist in the repository at this stage.

## reason\_code

`DatumSurfaceValidationResult.reason_code` is the authoritative field for
programmatic logic.  `diagnostic` is a human-readable hint and may change
between releases.

| reason\_code | Status |
|---|---|
| `SURFACE_TYPE_VALID` | VALID |
| `SURFACE_SIGNATURE_ABSENT` | UNRESOLVED\_SURFACE\_TYPE |
| `SURFACE_TYPE_UNKNOWN` | SURFACE\_TYPE\_UNVALIDATABLE |
| `SURFACE_TYPE_NOT_SUPPORTED_FOR_DATUM_ROLE` | INVALID\_SURFACE\_TYPE |
| `ENTITY_KIND_NOT_VALIDATABLE` | UNSUPPORTED\_ENTITY\_KIND |
| `FACE_LOOKUP_FAILED` | MISSING\_ENTITY (topology layer) |
| `BOUND_ENTITY_NOT_FOUND` | MISSING\_ENTITY (resolution layer) |
| `SOURCE_FINGERPRINT_MISMATCH` | SOURCE\_MISMATCH |
| `UNBOUND_ASSIGNMENT` | UNBOUND |
| `INTERNAL_RESOLUTION_INCONSISTENCY` | MISSING\_ENTITY (guard) |

## Related architecture documents

- `datum_topology_binding_v1.md` — binding and resolution contracts
- `persistent_topology_identity_v1.md` — SHA-256 face signatures
- `canonical_topology_v1.md` — CanonicalTopologyModel
