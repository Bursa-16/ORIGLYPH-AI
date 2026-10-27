# Origlyph AI — Customer Demo FAQ

**Version:** v0.4.0-alpha.7

Concise, factual answers for use during and after customer demos.

---

**1. Is the calculation deterministic?**

Yes. Every analysis in Origlyph AI uses fixed mathematical rules.
The same inputs always produce the same outputs. There is no
sampling, estimation, stochastic element, or probabilistic component
in the worst-case or RSS engines. Two separate runs on the same
project always return identical results.

---

**2. Is AI changing the numerical result?**

No. The AI boundary in Origlyph is advisory only. No AI component
modifies, overrides, or substitutes a deterministic engineering result.
The engines used in this demo — worst-case, RSS, sensitivity, budget,
and allocation validation — are purely deterministic.

---

**3. Can the project be saved and reopened?**

Yes. The project file (workspace schema v3) persists the tolerance chain,
specification limits, and allocation plan. Analysis results are runtime-derived
and recomputed from the saved inputs on demand. Reopening a saved project
on any machine with the same software version produces the same analysis results.

---

**4. What changes the project identity?**

The configuration fingerprint (SHA-256) changes whenever any authoritative
input changes: a contributor's nominal, tolerance, or direction; the
specification limits; or the allocation plan. The fingerprint is stable
as long as the authoritative inputs are unchanged. It makes every meaningful
engineering state uniquely identifiable.

---

**5. Can allocation be automatically optimised?**

Not in this release. The allocation plan must be constructed manually
by the engineer — each contributor's allocated span is entered explicitly.
Automatic balance, optimal-span calculation, and constraint-based allocation
generation are planned as future work.

---

**6. Does it support RSS?**

Yes. RSS (root sum of squares) statistical analysis is fully implemented.
It combines contributor variances quadratically and compares the combined
sigma against the specified sigma allowance.

---

**7. Does it support correlated RSS (covariance)?**

The Stage 15 covariance-aware statistical engine is implemented in the
engineering layer and supports correlated contributors. In the current
workspace demo, the standard RSS (independent contributors) mode is used.
Covariance input is not yet exposed in the workspace UI — that is planned
for a future release.

---

**8. Does it support asymmetric tolerances?**

The current demo uses symmetric tolerances (±half-span). Support for
asymmetric tolerance input in the workspace UI is not demonstrated in
this release. The underlying architecture is designed to accommodate
asymmetric models, but this is not yet validated as a customer-facing feature.

---

**9. Does it support CAD?**

This release supports ASCII and binary STL import only.
Direct CAD binding — linking tolerance contributors to CAD geometry,
features, or dimensions — is not yet implemented. CAD integration is
planned as future scope.

---

**10. Does it support STEP / B-Rep?**

STEP, IGES, DXF, and B-Rep topology import are not yet implemented.
STL import is available. STEP and B-Rep support are planned for future
development. This release does not make claims about STEP production workflow.

---

**11. Does it support GD&T?**

A GD&T assistance module boundary exists in the architecture. Full GD&T
compliance evaluation, automatic standards interpretation, and automatic
GD&T assignment are not yet implemented. GD&T support is planned for
future work.

---

**12. Can company-specific rules be added?**

Not in this alpha. Company-specific tolerance standards, tolerance limits
by material or process class, and enterprise authorization are future work.
The architecture is designed with extensibility in mind, but no integration
with company standards libraries is currently available.

---

**13. Can reports be generated?**

Report generation — structured PDF, DOCX, or HTML output of the analysis
results, decision chain, and project state — is not yet implemented.
It is identified as future scope.

---

**14. Can audit and governance be integrated?**

The Stage 15 audit chain — decision evidence, decision reports, audit packages,
change impact, approval readiness, and governed acceptance — is fully implemented
in the engineering layer. The workspace UI surface for audit and governance is
planned as future work. In the current demo, these backend capabilities are
not exposed through the UI.

---

**15. Can this be deployed inside a company network?**

Origlyph AI is a desktop application that runs locally on Python 3.10+.
It does not require an internet connection to operate. It has no cloud
dependency, no external API calls, and no telemetry in the current alpha.
Local or corporate-network deployment is straightforward from an
infrastructure perspective. Enterprise installation, licensing, and
support models are not yet defined for this alpha.

---

**16. Can customer standards be integrated later?**

Yes, in principle — the architecture is designed to support configurable
tolerance standards, standards-bound specification limits, and enterprise
data integration. None of this is implemented in the current alpha.
The integration approach and timeline would be defined in a pilot or
requirements engagement.
