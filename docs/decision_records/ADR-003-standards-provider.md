# ADR-003 — Standards Provider Architecture

## Context

Origlyph must support multiple GD&T / GPS standards families and versions without hard-coding one standard globally.

## Decision

Use a standards-aware, version-aware provider abstraction.

The architecture must allow engineering workflows to select the applicable standards family explicitly, including ASME Y14.5 and ISO GPS / ISO 1101 related standards.

Do not embed proprietary standards text or tables unless independently authorized and provenance-controlled.

## Consequences

* No global hard-coded standards assumption
* Standards family/version can be selected explicitly
* Future standards providers can be added without changing core domain boundaries
* Provenance requirements remain enforceable

## Status

Accepted
