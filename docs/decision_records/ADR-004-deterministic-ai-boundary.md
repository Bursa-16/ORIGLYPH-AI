# ADR-004 — Deterministic Engineering and AI Boundary

## Context

Origlyph may use AI assistance, but engineering calculations and compliance decisions must remain traceable and authoritative.

## Decision

Deterministic engineering logic is authoritative.

AI may assist with:

* explanation
* interpretation
* workflow guidance
* recommendations

AI must not replace deterministic engineering calculations, geometric constraints, GD&T compliance checks, or tolerance-analysis results.

When required engineering evidence is missing or unverifiable, the system must fail closed rather than produce an authoritative engineering result.

## Consequences

* Engineering outputs remain auditable and reproducible
* AI output remains clearly separated from authoritative calculations
* Missing evidence produces controlled failure states
* Human review remains possible where appropriate

## Status

Accepted
