# Origlyph v0.4.0-alpha.4 - Deterministic Tolerance Architecture Freeze

## Overview

Origlyph AI v0.4.0-alpha.4 is an alpha prerelease that freezes the deterministic tolerance architecture completed through Stage 15W and assessed in Stage 15X as release-ready for the current milestone.

This release does not add a new tolerance feature stage. It records the completed architecture, updates the package version to `0.4.0a4`, and preserves the deterministic behavior already implemented on `main`.

## Engineering analysis evolution

The tolerance stack now covers deterministic 1D engineering analysis across:

- worst-case analysis
- independent RSS statistical analysis
- covariance-aware statistical propagation
- sensitivity and contributor-impact analysis
- tolerance budget compliance
- user-supplied allocation validation
- worst-case allocation reconciliation
- statistical allocation reconciliation

These calculations remain deterministic engineering code paths. AI does not override or replace them.

## Decision, evidence, and report architecture

The deterministic decision layer aggregates the tolerance engines into a typed decision result. The evidence layer preserves reason-linked observations, and the decision report packages the decision and evidence into an export-ready deterministic report envelope.

## Audit and replay architecture

Audit integrity validation checks report consistency without recomputing engineering calculations. The audit package adds deterministic fingerprints, replay metadata, package identity, and structural replayability status for the report and integrity result.

## Comparison, impact, disposition, and readiness pipeline

The audit comparison pipeline detects deterministic package changes, classifies their impact, maps that impact to governed disposition, and evaluates whether the disposition is ready for an external governed acceptance workflow.

## Governed acceptance artifact chain

The governed acceptance chain packages readiness into a handoff, validates an externally supplied acceptance record, verifies structural binding between the handoff and record, and closes the chain with a deterministic closure manifest.

The implemented chain is:

```text
audit package comparison
-> change impact
-> change disposition
-> approval readiness
-> governed acceptance handoff
-> external acceptance record intake
-> acceptance verification envelope
-> governed acceptance closure manifest
```

## Deterministic identity and canonical serialization

Stage 15 audit and governed-acceptance identities use deterministic canonical serialization and SHA-256 fingerprints where required by the current artifact contracts. Identity payloads exclude their own self-identity fields, use finite JSON payloads, and reject unsupported or malformed schemas.

## Fail-closed behavior

Malformed, incomplete, unsupported, contradictory, stale, or forged artifacts fail closed. Blocking states cannot silently become ready, accepted, verified, or complete through later stages.

## Trust-boundary limitations

Origlyph validates deterministic structure and binding only. This release does not verify human identity, legal authority, organizational authorization, signature authenticity, non-repudiation, legal approval, or production manufacturing acceptance. External authority and decision references remain opaque references supplied outside Origlyph.

## Validation

- Tolerance suite: 741 passed
- Full suite: 1275 passed
- Ruff: PASS
- Pyright: 0 errors, 0 warnings
- diff-check: PASS
- Stage 15X: RELEASE_READINESS_CONFIRMED

Release preparation does not alter engineering behavior.

## Future / non-blocking items

The following are intentionally not current release capabilities:

- shared canonical hashing utility
- serialized artifact reconstruction/deserialization
- schema migration/version compatibility
- persistence/storage
- CLI/GUI exposure for the tolerance-governance workflow
- external signature or human-identity verification

## Tag

A new annotated tag `v0.4.0-alpha.4` will point at this release commit. Historical tags remain immutable.

## Artifacts

Source archives only. No wheel or sdist is built for this prerelease.