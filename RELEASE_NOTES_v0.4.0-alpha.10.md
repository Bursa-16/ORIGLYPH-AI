# Origlyph AI v0.4.0-alpha.10

Release date: 2026-11-10

## Overview

v0.4.0-alpha.10 delivers the **deterministic reporting stack** and **project
reopen governance continuity** built on the complete Stage 20 governance chain
workspace surface shipped in alpha.9.

Every governance step — from tolerance analysis through acceptance closure —
was already exposed in alpha.9. This release adds four deterministic HTML export
surfaces that produce offline-readable, self-contained engineering artifacts from
those governance outputs, and adds an explicit "Restore Governance State" action
that regenerates the full governance chain from persisted authoritative inputs
after a project is saved and reopened.

No engineering formulas, audit hash logic, or acceptance logic are changed.
All engineering authority remains exclusively in the Stage 15 backends.

---

## Highlights

### Deterministic HTML Reporting (Stages 21C, 21D, 21E)

Four new deterministic HTML export surfaces:

**Decision Report HTML**
- `export_html_report(path)` on the workspace session
- Renders the full `ToleranceDecisionReport` as a self-contained,
  offline-readable HTML artifact
- Identical inputs produce byte-identical output; no timestamps, UUIDs,
  random values, or environment-dependent data in rendered HTML

**Audit Package HTML**
- `export_audit_html(path)` on the workspace session
- Renders the full `ToleranceDecisionAuditPackage` including provenance,
  integrity fingerprints, and disposition chain as a self-contained HTML artifact
- Explicit security notice embedded in rendered HTML:
  identifiers support traceability; they do not constitute digital signatures,
  authenticated identity, regulatory certification, or release authorization

**Governance Chain HTML**
- `export_governance_html(path)` on the workspace session
- Renders the complete governance chain (audit comparison, change impact,
  disposition, approval readiness, acceptance handoff through closure)
  as a self-contained HTML artifact

**Unified Engineering Report HTML**
- `export_unified_html_report(path)` on the workspace session
- Single-file aggregation of all four governance layers into one
  self-contained HTML artifact suitable for archival, review packages,
  and approval workflows

All four surfaces:
- produce a single UTF-8 HTML file with inline CSS
- require no external stylesheets, CDN resources, fonts, or scripts
- exclude all non-deterministic values (timestamps, UUIDs, hostnames,
  environment paths) from rendered output
- preserve project identity: `configuration_fingerprint` unchanged by export

### Project Reopen Governance Continuity (Stage 21G)

After a project is saved and reopened, all runtime governance artifacts
(decision, evidence, report, audit, comparison, change impact, disposition,
approval readiness, handoff, record, verification, closure) are absent.
This release adds an explicit restore mechanism.

**`restore_governance_state(*, comparison_path=None)`**
- Available on `ToleranceWorkspaceController` and `WorkspaceSession`
- Deterministically regenerates the full runtime governance chain from
  persisted authoritative project inputs
- Core restore chain (always): analysis → decision → evidence →
  decision report → audit integrity → audit package
- Full restore chain (with `comparison_path`): extends core with
  comparison load → audit comparison → change impact → disposition →
  approval readiness → acceptance handoff; continues through acceptance
  record → verification → closure when `acceptance_state` is present
- Fail-closed: all 21 derived runtime fields cleared atomically before
  any step; a failed restore leaves cleared state, never partial artifacts
- Never called automatically on project open; activated only by the user
- **"Restore Governance State"** button added to the Project File
  labelframe in the desktop UI; prompts whether to supply a comparison file

Determinism guarantees: given the same authoritative project inputs and
the same comparison file, `restore_governance_state` produces identical
runtime artifacts on every invocation.

---

## Quality

All quality gates pass against the final alpha.10 source.

| Gate | Result |
|---|---|
| Project tests | 26 passed |
| Tolerance tests | 2098 passed |
| Full suite | 2658 passed |
| Ruff | All checks passed |
| Pyright | 0 errors, 0 warnings, 0 informations |
| diff --check | Clean |

---

## Known Limitations

The following limitations apply to this release. All are non-blocking for
engineering team use.

**No digital signatures or cryptographic non-repudiation**
Governance identifiers and fingerprints are SHA-256-based and support
engineering traceability and integrity comparison. No cryptographic signing of
any artifact is performed. `authority_reference` and `decision_reference` are
plain caller-supplied strings, not verified identities.

**No authenticated actor identity**
No identity provider, PKI, or authentication mechanism is integrated.
Authority references are governance references only.

**No regulatory certification or compliance approval**
Origlyph governance workflows produce deterministic engineering records. They
do not confer, verify, or satisfy any regulatory standard or certification.

**No autonomous approval or release authorization**
Every acceptance decision requires explicit caller-supplied authoritative inputs
(`decision`, `authority_reference`, `decision_reference`, `handoff_id`).
The system does not autonomously approve or authorize releases.

**Runtime governance artifacts are not persisted**
Computed governance artifacts (decision, evidence, report, audit chain,
acceptance chain) are runtime-derived and absent after project save/reopen.
The user must invoke "Restore Governance State" explicitly to regenerate
the full chain. The comparison file (if required) must be retained externally.

**sensitivity, budget, allocation_validation, reconciliation, and
statistical_reconciliation not regenerated by restore_governance_state**
These five artifacts require separate user-initiated analysis steps after
restore. See `docs/architecture/tolerance_workspace_governance_restore.md`.

**No PDF or DOCX export**
All export surfaces produce self-contained HTML only.

**STEP / B-Rep geometry not implemented**
CAD geometry input for tolerance stack derivation from 3D models remains
outside this release line.

**GD&T UI remains partial**
GD&T configuration is not part of the current workspace surface.

**Golden demo baseline covers alpha.7 scope only**
The approved customer demo baseline (`docs/demo/golden_demo_baseline.md`)
is frozen at v0.4.0-alpha.7 (Stage 18D) and covers the original 16-step
analysis/sensitivity/budget/allocation flow. The HTML export surfaces and
governance restore capability are not in any approved customer demo script.

---

## Security and Authority Notice

Origlyph deterministic identifiers and fingerprints support engineering
traceability and integrity comparison. They do not constitute digital
signatures, authenticated identity, regulatory certification, compliance
approval, or product release authorization.
