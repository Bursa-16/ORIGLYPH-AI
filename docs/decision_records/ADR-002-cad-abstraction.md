# ADR-002 — CAD Integration Abstraction

## Context

Origlyph must support CAD-related workflows without locking the core architecture to a proprietary CAD vendor or kernel.

## Decision

Use a vendor-agnostic three-layer CAD architecture:

1. neutral-format/import boundary
2. geometry-kernel abstraction
3. vendor-specific adapters outside the core domain

Do not add proprietary CAD SDK dependencies at foundation stage.

## Consequences

* Reduced vendor lock-in
* Core engineering logic remains portable
* Vendor-specific integrations can be added later behind adapters

## Status

Accepted
