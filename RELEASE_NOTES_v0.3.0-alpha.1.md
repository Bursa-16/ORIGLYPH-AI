# Origlyph v0.3.0-alpha.1

## Summary

Third alpha release. Origlyph now includes its first concrete CAD importer.
STL geometry can flow end-to-end through the deterministic CAD/datum pipeline:

STL facets
→ NeutralModel
→ BoundedPlanarFace
→ candidate extraction
→ explicit reference binding
→ explicit datum roles
→ DatumReferenceFrame

The release remains deterministic, provenance-aware, fail-closed, and
non-authoritative with respect to AI.

## Key capabilities

- model-scoped exact source identity reverse lookup through NeutralModel.reverse_lookup
- drawing datum-feature and datum-reference-frame declaration records
- BoundedPlanarFace support in the CAD-to-datum candidate chain
- deterministic datum/reference binding and explicit role assignment
- advisory candidate evaluation without ranking or automatic assignment
- concrete STL importer feeding real CAD geometry into the existing chain

## STL importer

- ASCII STL support
- binary STL support
- deterministic binary detection using exact 84 + 50 * facet_count layout
- binary headers beginning with "solid" supported correctly
- injected bytes_loader is the only source-acquisition boundary
- no filesystem I/O inside StlImporter
- declared source length unit must be mm
- no implicit unit conversion
- no scale inference
- stable 0-based facet-{i} source and neutral identities
- STL stored facet normals are diagnostic metadata only
- vertex winding is authoritative for BoundedPlanarFace geometry
- vertices are never reordered or flipped
- degenerate facets are recorded through CadWarning(DEGENERATE_FACET)
  and UnsupportedContent rather than disappearing silently
- malformed/truncated/oversized payloads and non-finite numeric values fail closed

End-to-end validation includes three STL facets flowing through
PRIMARY / SECONDARY / TERTIARY assignments into a valid 3-2-1 DRF.

## Deterministic engineering boundaries

- no hidden datum inference
- no automatic PRIMARY / SECONDARY / TERTIARY assignment
- explicit ConstraintType remains the role authority
- no automatic datum ranking
- no standards inference
- no engineering tolerance runtime
- geometry floating-point tolerance remains computational only
- AI is not an authoritative engineering decision source

## Validation

- 501 tests passed
- Ruff PASS
- Pyright PASS
- git diff --check PASS

## Known limitations

- STL is treated as facet soup
- no topology adjacency
- no watertightness guarantee
- no shared-vertex welding
- no mesh repair
- no B-Rep
- STL normals are not authoritative geometry
- importer receives bytes through caller-supplied loader
- README capability/version summary remains behind the current implementation
  and will be refreshed separately

## Explicitly not included

- STEP
- IGES
- DXF
- topology/B-Rep
- automatic datum ranking/recommendation
- GD&T compliance engine
- engineering tolerance runtime
- measurement acceptance
- tolerance stack-up
- authoritative AI
- production certification claims
- ASME/ISO compliance claims
