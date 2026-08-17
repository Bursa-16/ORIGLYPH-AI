# ADR-001 — Python Package Namespace

## Context

Origlyph requires one canonical Python namespace for long-term maintainability and consistent imports.

## Decision

Use `src/origlyph/` as the canonical Python package namespace.

Do not use `engineering` or `origlyph_ai_core` as runtime package namespaces.

## Consequences

* Clear product-aligned imports
* Consistent version/import ownership
* Future domain modules remain under `origlyph.*`

## Status

Accepted
