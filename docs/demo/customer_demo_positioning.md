# Origlyph AI — Customer Demo Positioning Guide

**Purpose:** Help presenters stay accurate and avoid overclaiming.
**Version:** v0.4.0-alpha.7

Use this as a quick reference during preparation and Q&A.

---

## A. SAY CONFIDENTLY

These capabilities are fully implemented and demonstrated in the current release.

- Deterministic tolerance calculations — same inputs always produce the same outputs
- Worst-case tolerance analysis
- RSS (root sum of squares) statistical analysis
- Explicit specification limits — entered by the engineer, never auto-set
- Deterministic PASS/FAIL decision surface
- Sensitivity analysis — per-contributor impact ranking
- Tolerance budget analysis — actual versus allowed span
- Allocation plan input — manual tolerance target distribution
- Allocation validation — structural consistency check
- Deterministic project persistence — save/open restores exact state
- Reproducible project identity — SHA-256 configuration fingerprint
- Fail-closed validation — invalid or blank inputs raise explicit errors, no silent defaults
- Local desktop deployment — no internet dependency, no cloud calls

---

## B. SAY WITH QUALIFICATION

These are feasible or partially implemented, but not yet delivered as full customer-facing features.

**Correlated RSS (covariance-aware statistical analysis)**
> "The covariance-aware statistical engine is implemented in the engineering
> layer. Correlated contributors are supported in the backend.
> The workspace UI does not yet expose covariance input — that is planned."

**Audit and governance workflows**
> "The audit chain — decision evidence, change impact, approval readiness —
> is fully implemented in the engineering backend. The workspace UI for
> audit and governance is planned for a future release."

**AI-assisted engineering workflows**
> "The platform is designed to support AI-advisory functions alongside
> deterministic engineering engines. In the current release, all engineering
> results are deterministic. AI-advisory features are on the roadmap."

**Company-specific integration**
> "Integration with company tolerance standards, ERP systems, or PLM tools
> is feasible from an architecture standpoint. The integration model and
> timeline would be scoped as part of a pilot engagement."

**Local / corporate network deployment**
> "The application runs locally with no internet dependency today.
> Enterprise deployment — packaging, IT approval, licensing — is not yet
> defined for the current alpha but is straightforward in principle."

---

## C. DO NOT CLAIM YET

These capabilities are **not implemented** in v0.4.0-alpha.7.
Do not claim them, imply them, or leave them ambiguous.

- **Automatic allocation optimisation** — the allocation plan is manual entry only
- **Automatic tolerance optimisation** — no constraint-based or AI-driven redesign
- **Autonomous engineering decisions** — all decisions require explicit engineer input
- **CAD / geometry binding** — no link between the chain and CAD dimensions
- **STEP / B-Rep production workflow** — STEP import is not implemented
- **Full GD&T evaluation** — GD&T authoring and standards compliance are not implemented
- **Company standards library** — no standards database or tolerance rule library
- **Report generation** — no PDF, DOCX, or HTML export
- **Reconciliation UI** — reconciliation is not exposed in the workspace UI
- **Full CAD workstation** — Origlyph is not a CAD system

---

## Quick Decision Rule

When a customer asks about a feature:

1. Is it in section A? → Say it confidently.
2. Is it in section B? → Say it with the qualification given.
3. Is it in section C? → Say clearly: "That is not in the current release.
   It is planned as future work."
4. Not listed? → Do not speculate. Say: "Let me confirm that and follow up."
