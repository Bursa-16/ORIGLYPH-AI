# Origlyph v0.2.0-alpha.1

## Status
Alpha engineering release.

## Highlights
- Deterministic CAD identity and neutral model
- CAD-to-datum binding
- Explicit datum-role binding
- Deterministic datum-reference-frame assembly
- Advisory candidate evaluation
- Bounded planar-face geometry
- Bounded geometry carriage in neutral entities
- Functional relevance declaration with provenance

## Engineering Safety Boundaries
- Recommendation is not assignment
- No automatic datum-role inference
- No ranking/scoring
- AI is not engineering authority
- Datum domain remains CAD-free
- Deterministic calculations remain authoritative

## Validation
- Full unit suite: 407 passed
- `ruff check src tests`: PASS
- `pyright`: 0 errors, 0 warnings, 0 informations

## Known Limits
- No automatic candidate ranking
- No drawing/GD&T parser
- No standards/OEM rule packs
- No curved bounded-surface foundation yet
- No automatic datum assignment
- Functional declarations are evidence/context only

## Compatibility
Alpha API; backward compatibility not guaranteed across future alpha releases.