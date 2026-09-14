# Origlyph Project Model v1

## Purpose

`origlyph.project.v1` defines the deterministic, file-based container for an
Origlyph engineering project snapshot. A project snapshot is the smallest unit
of reproducibility: saving a project and reopening it must recover an
equivalent engineering configuration with an identical deterministic
`project_id`.

This is Stage 16B of the Origlyph architecture. It intentionally captures
*authoritative* project state only. Non-authoritative UI convenience state is
not part of the schema.

## Boundaries

The project model is storage format, not an analysis engine. It does **not**
execute tolerance arithmetic, geometry computation, or datum solving. The
models that perform engineering work (geometry, CAD, datum, tolerance) remain
fully authoritative; the project model references them.

## Schema

```
schema_version: "origlyph.project.v1"
project_id: <lowercase sha256 hex>
metadata:
  name, description, revision, local_path_hint, extra
cad_sources:
  - source_id, format, length_unit, fingerprint, local_path_hint
datum_state:
  frame_name, assignments[]
tolerance_state:
  chain_name, configuration_fingerprint, result_identities[], summary_values
artifact_refs: { <logical_name>: <sha256 hex>, ... }
extensions: { <key>: <json-serializable value> }
```

## Project Identity

`project_id` is a SHA-256 digest over the canonical identity payload:

- `schema_version`
- `cad_sources` (identity subset only: `source_id`, `format`, `length_unit`, `fingerprint`; `local_path_hint` excluded)
- `datum_state` (authoritative)
- `tolerance_state` (authoritative)
- `artifact_refs`
- `extensions`

The `metadata` block is explicitly **excluded** from `project_id` because it is
non-authoritative descriptive information. In particular:

- `name`, `description`, `revision` — descriptive only.
- `local_path_hint` — convenience, environment-specific, excluded from identity.
- `extra` — caller-defined; the caller is responsible for determinism if it is
  meant to be authoritative. Any non-finite number or unsupported JSON type
  causes rejection at construction.

No timestamp, UUID, random value, hostname, username, PID, or absolute local
filesystem path participates in project identity.

## Deterministic Serialization

Serialization follows the established Origlyph deterministic JSON convention:

- `sort_keys=True`
- compact separators `(",", ":")`
- `ensure_ascii=True`
- `allow_nan=False`
- finite numbers only (NaN and Infinity are rejected)

## File Persistence

`save_project(project, path)` writes a single deterministic JSON file (UTF-8,
LF newline). `load_project(path)` reads and verifies the file.

Filesystem I/O is isolated from the model layer. Models do not perform
filesystem operations themselves.

## Fail-Closed Behavior

Loading fails closed on:

- malformed JSON
- missing required top-level fields
- unknown `schema_version`
- invalid field types
- non-finite numeric values
- invalid `project_id` format
- `project_id` mismatch (content vs stored identity — tamper/stale detection)

All failures raise `OriglyphProjectError` (subclass) and never return silent
defaults.

## Schema Version Policy

Only `origlyph.project.v1` is supported. Unknown schemas raise
`UnsupportedProjectSchemaError`. No silent migration is performed. Migration
strategy is reserved for a future stage.

## CAD Source References

Sources are persisted by logical identity (`source_id`, `format`, `length_unit`,
`fingerprint`). The `fingerprint` is a SHA-256 content digest of the CAD source.
An optional `local_path_hint` may be stored for convenience but is excluded
from `project_id`. CAD files themselves are never embedded in the project file.

## Datum State

Only datum/reference information that is already explicitly bound is persisted:
`frame_name` and explicit role assignments (`PRIMARY`, `SECONDARY`, `TERTIARY`).
No automatic inference is stored. Role ordering is sorted for determinism.

## Tolerance State

Stage 16B persists tolerance state as an authoritative **reference**: the
tolerance `chain_name`, a `configuration_fingerprint` that uniquely identifies
the chain configuration, `result_identities` (deterministic identifiers of
analysis results), and `summary_values` (deterministic scalar summaries).

This preserves the exact design constraint from Stage 16B: the project model
does not alter Stage 15 tolerance mathematics. The actual contributor list and
analysis results remain under the authority of the Stage 15 tolerance engine.
The project model records a fingerprint of the configuration so that a
meaningful change to authoritative inputs (nominal, tolerance, direction,
contributor set, analysis mode, target/specification) is detectable and would
yield a different `configuration_fingerprint`, which in turn changes
`project_id`.

## What V1 Does Not Persist

- Full STEP/B-Rep topology
- GD&T feature control frame semantics
- Visual 3D viewport state
- Transient UI state (selection, focus, scroll, window geometry)
- CAD file contents
- Audit/governance decision chain payloads (recorded by reference/fingerprint)

## Extensions

`extensions` is an explicit deterministic extension slot. It participates in
identity. Non-finite or non-JSON-serializable content is rejected.

## Relation to Other Layers

| Layer              | Authority            | Persisted by project |
|--------------------|----------------------|----------------------|
| Geometry           | Engine (Stage 15)     | Via CAD fingerprint  |
| CAD                | Engine (Stage 15)     | Via CAD source ref   |
| Datum              | Engine (Stage 15)     | Snapshot (explicit)  |
| Tolerance          | Engine (Stage 15)     | Snapshot + fingerprint|
| Audit/Governance   | Engine (Stage 15)     | By reference         |

## Future Migration Boundary

A future stage may introduce `origlyph.project.v2` for additional artifact
sections. Migration of existing v1 files into v2 (if ever required) is a
separate, explicit step and will not happen silently.
