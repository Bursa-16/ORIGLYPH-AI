# Origlyph Architecture Overview

This document records the approved Stage 1A architecture decisions only. It is a
foundation reference and does not claim production readiness, certification,
standards compliance, or validated engineering capability.

## Canonical Namespace

* The canonical Python namespace is `src/origlyph/`.

## CAD Abstraction

* A vendor-agnostic CAD abstraction isolates domain logic from any specific CAD
  vendor or file format.

## GD&T Provider Architecture

* GD&T behavior is provided through a standards-aware provider architecture,
  allowing standards and revisions to be selected and isolated.

## Tolerance-Analysis Method Selection

* Tolerance-analysis methods are selected explicitly; results are tied to the
  chosen method.

## Determinism and AI

* Deterministic engineering logic is authoritative.
* AI is assistive only and never authoritative over deterministic logic.

## API Layer

* FastAPI may be used only at the API layer, kept separate from domain logic.

## Source Keys

* A TR/EN source-key architecture is present from the foundation stage.

## Persistence

* Persistence is file-based initially.

## Deployment

* The architecture is deployment-agnostic.
