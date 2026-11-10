# Tolerance Governance Chain — HTML Export (Stage 21D)

## Purpose

Stage 21D introduces a deterministic, stdlib-only HTML renderer for the complete
governance/acceptance chain produced by Stages 15P–15W.  The rendered output is a
self-contained single-file engineering governance report suitable for archive,
review, and delivery without requiring any third-party toolchain.

**Governance HTML export is a deterministic presentation of already-generated
governance and acceptance artifacts.  It does not calculate, approve,
authenticate, sign, certify, or authorize the engineering decision.**

## Input artifacts

The renderer requires all eight governance/acceptance chain artifacts:

| Parameter | Type | Stage |
|-----------|------|-------|
| `comparison` | `AuditPackageComparisonResult` | 15P |
| `change_impact` | `AuditChangeImpactResult` | 15Q |
| `disposition` | `AuditChangeDispositionResult` | 15R |
| `approval_readiness` | `AuditApprovalReadinessResult` | 15S |
| `acceptance_handoff` | `AuditAcceptanceHandoffPackage` | 15T |
| `acceptance_record` | `ValidatedAuditAcceptanceRecord` | 15U |
| `acceptance_verification` | `AuditAcceptanceVerificationEnvelope` | 15V |
| `acceptance_closure` | `AuditAcceptanceClosureManifest` | 15W |

## Completeness requirement

**All eight artifacts are required.**  Partial chain export is not supported.
If any artifact is missing, `GovernanceHtmlExportError` is raised by the renderer
and `InvalidToleranceWorkspaceError` is raised by the controller.

## Engineering authority boundary

HTML export is a **presentation** of an already-generated complete governance
chain.  It is **not** a calculation, approval, authentication, certification,
digital signature, or release authorization.

The renderer never calls:
- `compare_decision_audit_packages()`
- `assess_audit_change_impact()`
- `determine_audit_change_disposition()`
- `evaluate_audit_approval_readiness()`
- `build_audit_acceptance_handoff()`
- `validate_audit_acceptance_record()`
- `build_acceptance_record_verification_envelope()`
- `build_acceptance_closure_manifest()`
- Any engineering engine

It only reads fields from the provided chain artifacts and formats them into HTML.

## Renderer API

| Symbol | Description |
|--------|-------------|
| `render_governance_chain_html(**chain_kwargs)` | Render to an in-memory HTML string |
| `write_governance_chain_html(**chain_kwargs, path=...)` | Render and write to a file; returns resolved `Path` |
| `GovernanceHtmlExportError` | Raised on invalid input or file I/O failure |

Both public functions accept all eight chain artifacts as keyword-only arguments
and validate that each is the expected type.

## Writer API

`write_governance_chain_html(**chain_kwargs, path)`:

- Accepts `str | Path` destination.
- Creates parent directories with `mkdir(parents=True, exist_ok=True)`.
- Writes `encoding="utf-8", newline="\n"` for cross-platform reproducibility.
- Wraps `OSError` in `GovernanceHtmlExportError`.
- Returns the resolved `Path` of the written file.

## Deterministic contract

Identical runtime artifact inputs always produce byte-identical HTML output.
The renderer guarantees:

- No timestamps or wall-clock values
- No UUIDs or random identifiers
- No machine names, usernames, or environment paths
- No session-specific state
- No external CDN, stylesheet, font, image, or script references
- `render(**kwargs) == render(**kwargs)` and encoded UTF-8 bytes match exactly

Existing authoritative values already present inside the governance artifacts
(fingerprints, IDs, references stored by Stage 15 builders) are displayed
exactly as stored.  New values are never generated.

## No hidden regeneration

The renderer and controller export method never trigger:

- `run_audit_comparison()`
- `run_change_impact()`
- `run_change_disposition()`
- `run_approval_readiness()`
- `run_acceptance_handoff()`
- `run_acceptance_record()`
- `run_acceptance_verification()`
- `run_acceptance_closure()`

If the full chain has not been built, the export fails closed.

## Fingerprint fidelity

**Critical contract:** Every identifier and fingerprint stored in governance
artifacts is rendered exactly as stored:

- `acceptance_handoff.handoff_id` (SHA-256)
- `acceptance_handoff.baseline_package_id` (SHA-256)
- `acceptance_handoff.candidate_package_id` (SHA-256)
- `acceptance_record.acceptance_record_id` (SHA-256)
- `acceptance_verification.envelope_id` (SHA-256)
- `acceptance_closure.closure_id` (SHA-256)
- `comparison.baseline_package_id` (SHA-256)
- `comparison.candidate_package_id` (SHA-256)
- `acceptance_record.authority_reference` (governance reference — not SHA-256)
- `acceptance_record.decision_reference` (governance reference — not SHA-256)

The renderer **never** recomputes, truncates, re-hashes, normalizes, transforms,
or reinterprets any identifier.

**Note:** `authority_reference` and `decision_reference` are user-supplied
governance references, not cryptographic hashes.  They are displayed as text
references, not as fingerprints.

## HTML escaping

All user-derived text is passed through `html.escape(str(value), quote=True)`
before insertion into the output.  This covers all string fields including
`authority_reference`, `decision_reference`, violation details, enum values,
schema versions, IDs, and all other dynamic content.

## Injection protection

All dynamic strings are HTML-escaped.  The following inputs produce safe output:

- `<script>alert(1)</script>` in `authority_reference` → escaped
- `</td></table><img src=x onerror=alert(1)>` in `decision_reference` → escaped
- Raw `<`, `>`, `&`, `"`, `'` → all escaped

## Self-contained / offline output

The rendered HTML is a single file with inline CSS.  No external resources:

- No external stylesheets
- No external JavaScript
- No CDN references
- No external fonts
- No remote images
- No `file://` references
- No network resources

Output is a valid, standalone HTML5 document fully readable offline.

## Document layout

The rendered document contains sections where actual chain data supports them:

1. **Governance Chain Summary** — status badges for each chain stage
2. **Audit Comparison** — comparison status, package IDs, change table
3. **Change Impact** — overall impact, decision change, assessed changes
4. **Change Disposition** — disposition, source impact, disposition reasons
5. **Approval Readiness** — readiness status, `is_ready`, readiness reasons
6. **Acceptance Handoff** — handoff ID, schema version, package IDs
7. **Acceptance Record** — record ID, decision, authority/decision references
8. **Acceptance Verification** — envelope ID, verification facts
9. **Acceptance Closure** — closure ID, complete closure references
10. **Traceability References** — all SHA-256 IDs and governance references in one table
11. **Governance Notice** — static semantic safety statement

No data is invented.  No fake "approved" or "certified" sections are created.

## Semantic safety

| Concept | Correct interpretation |
|---------|----------------------|
| Approval Readiness | Readiness gate result; not an approval decision |
| Acceptance Handoff | Governance handoff status; not an acceptance decision |
| Acceptance Record | Externally supplied governance record; not a digital signature |
| Authority Reference | Governance reference string; not an authenticated identity |
| Decision Reference | Governance reference string; not a digital signature |
| Verification | Structural binding consistency; not identity authentication |
| Closure | Reference packaging; not regulatory certification or release authorization |

Forbidden labels (not present in rendered output):
- Certified
- Digitally Signed
- Authenticated Approver
- Regulatory Approved
- Authorized Release
- Compliance Certified

## Security notice (static)

The governance notice section states verbatim:

> "This governance report presents deterministic engineering governance
> artifacts. Approval readiness is not approval. Acceptance references are
> governance references, not authenticated identities. Verification and closure
> artifacts do not constitute digital signatures, regulatory certification,
> compliance approval, or release authorization."

This text is static and contains no dynamic date/time or generated values.

## Workspace integration

### Controller (`workspace_controller.py`)

`ToleranceWorkspaceController.export_governance_html(path)`:

- Requires all eight governance/acceptance chain artifacts to be cached.
- Raises `InvalidToleranceWorkspaceError` if any artifact is missing,
  naming the missing cached attributes.
- Delegates to `write_governance_chain_html` via a lazy local import.
- Does **not** call any governance or acceptance builder.
- Does **not** mutate workspace state, project identity, or any
  engineering or governance cache.
- Accepts `str | Path`; returns the resolved `Path` of the written file.

### Session (`workspace_model.py — WorkspaceSession`)

`WorkspaceSession.governance_html_available` — boolean property; `True` when
all eight chain artifacts are non-None in the controller.

`WorkspaceSession.export_governance_html(path)` — delegates to the controller.

### View (`workspace_model.py — ToleranceWorkspaceView`)

An "Export Governance HTML" button is added to the Acceptance Closure
labelframe at `row=2`, after the closure detail label.  The button handler
follows the existing `_guard()` pattern:

```
_export_governance_html()  →  _guard(lambda: _export_governance_html_impl())
```

`_export_governance_html_impl()` opens a save-file dialog
(`asksaveasfilename`) with `.html` as the default extension and
`origlyph_governance_report.html` as the default filename, then calls
`self._session.export_governance_html(path)` and shows an info dialog on
success.

The default filename `origlyph_governance_report.html` contains no timestamp,
username, hostname, UUID, or random suffix.

## Project identity boundary

The export path is **not** persisted.  Export does **not** affect the
configuration fingerprint.  `project_id` is identical before and after
export, regardless of destination path or repetition count.

## Authoritative acceptance state boundary

`WorkspaceAcceptanceState` (the persisted schema v5 acceptance input) is
read-only during export.  Export does not set, update, or clear acceptance
state.

## Runtime-only governance boundary

The runtime governance chain (comparison, impact, disposition, readiness,
handoff, record, verification, closure) is consumed as already-existing state.
Export reads these artifacts; it never builds, replays, or modifies them.

## Limitations

- The renderer does not access the filesystem, network, or environment beyond
  what `Path.parent.mkdir()` and `Path.write_text()` require.
- Rendered output is not a legally binding document, digital signature,
  regulatory submission, or compliance record.
- `authority_reference` and `decision_reference` values are governance
  references supplied by the external caller; the renderer displays them
  as plain text without validation or interpretation.

## Non-goals

- Not a re-verification of the acceptance chain
- Not a new integrity check
- Not an approval mechanism
- Not a certification artifact
- Not a release document
- Not a comparison between governance chains
- Not a replay trigger
- Not a PDF, DOCX, or any format other than a standalone HTML file
- Not a database or cloud-sync operation
