# Tolerance Unified Engineering Report — HTML Export (Stage 21E)

## Purpose

Stage 21E introduces a deterministic, stdlib-only HTML renderer that combines all
three prior export layers (Decision Report, Audit Package, Governance Chain) into a
single, self-contained unified engineering report suitable for archive, review,
and delivery.

**Unified Engineering Report HTML export is a deterministic presentation of
already-generated engineering, audit, and governance artifacts.  It does not
recalculate, approve, authenticate, sign, certify, or authorize those artifacts.**

## Required input artifacts

The renderer requires all ten runtime artifacts to be present:

| Parameter | Type | Stage |
|-----------|------|-------|
| `decision_report` | `ToleranceDecisionReport` | 15K/15L |
| `audit_package` | `ToleranceDecisionAuditPackage` | 15O |
| `comparison` | `AuditPackageComparisonResult` | 15P |
| `change_impact` | `AuditChangeImpactResult` | 15Q |
| `disposition` | `AuditChangeDispositionResult` | 15R |
| `approval_readiness` | `AuditApprovalReadinessResult` | 15S |
| `acceptance_handoff` | `AuditAcceptanceHandoffPackage` | 15T |
| `acceptance_record` | `ValidatedAuditAcceptanceRecord` | 15U |
| `acceptance_verification` | `AuditAcceptanceVerificationEnvelope` | 15V |
| `acceptance_closure` | `AuditAcceptanceClosureManifest` | 15W |

## Completeness requirement

**All ten artifacts are required.**  Partial export is not supported.
If any artifact is missing, `UnifiedEngineeringHtmlExportError` is raised by the
renderer and `InvalidToleranceWorkspaceError` is raised by the controller.

## Engineering authority boundary

HTML export is a **presentation** of an already-generated complete engineering,
audit, and governance chain.  It is **not** a calculation, approval, authentication,
certification, digital signature, or release authorization.

The renderer never calls:
- Any engineering engine (`run_analysis`, `evaluate_decision`, `run_decision_evidence`, `run_decision_report`)
- Any audit builder (`run_audit_package`, `validate_audit_integrity`)
- Any governance builder (`run_audit_comparison`, `run_change_impact`, `run_change_disposition`, `run_approval_readiness`)
- Any acceptance builder (`run_acceptance_handoff`, `run_acceptance_record`, `run_acceptance_verification`, `run_acceptance_closure`)

It only reads fields from the provided artifacts and formats them into HTML.

## Renderer API

| Symbol | Description |
|--------|-------------|
| `render_unified_engineering_report_html(**kwargs)` | Render to an in-memory HTML string |
| `write_unified_engineering_report_html(**kwargs, path=...)` | Render and write to a file; returns resolved `Path` |
| `UnifiedEngineeringHtmlExportError` | Raised on invalid input or file I/O failure |

Both public functions accept all ten artifacts as keyword-only arguments and
validate that each is the expected type.

## Writer API

`write_unified_engineering_report_html(**kwargs, path)`:

- Accepts `str | Path` destination.
- Creates parent directories with `mkdir(parents=True, exist_ok=True)`.
- Writes `encoding="utf-8", newline="\n"` for cross-platform reproducibility.
- Wraps `OSError` in `UnifiedEngineeringHtmlExportError`.
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

## No hidden regeneration

The renderer and controller export method never trigger upstream artifact creation.
If the full chain has not been built, the export fails closed with a clear error
naming the missing artifact cache attribute.

## Identifier / fingerprint fidelity

Every identifier and fingerprint stored in the artifacts is rendered exactly as
stored.  The renderer never recomputes, truncates, re-hashes, normalizes,
transforms, or reinterprets any identifier.

Fingerprints rendered include:
- `audit_package.package_id`
- `comparison.baseline_package_id` and `.candidate_package_id`
- `acceptance_handoff.handoff_id`
- `acceptance_record.acceptance_record_id`
- `acceptance_verification.envelope_id`
- `acceptance_closure.closure_id`

Governance references rendered:
- `acceptance_record.authority_reference`
- `acceptance_record.decision_reference`

## HTML escaping

All user-derived text is passed through `html.escape(str(value), quote=True)` before
insertion into the output.  This covers all string fields including identifiers,
references, enum values, schema versions, and all other dynamic content.

## Injection protection

All dynamic strings are HTML-escaped.  The following inputs produce safe output:

- `<script>alert(1)</script>` in `authority_reference` → escaped
- `</table><img src=x onerror=alert(1)>` in `decision_reference` → escaped
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

## Document layout

The rendered document contains:

1. **Origlyph AI Engineering Report** — header
2. **Executive Engineering Summary** — status badge grid for all ten artifacts
3. **Decision Report** — final status, reasons, contributors, evidence
4. **Audit Package** — package ID, integrity status, replayability
5. **Audit Comparison** — comparison status, package IDs, change table
6. **Change Impact** — overall impact, decision change flags
7. **Change Disposition** — disposition and source impact
8. **Approval Readiness** — readiness status and gate result
9. **Acceptance Handoff** — handoff ID, package IDs, schema version
10. **Acceptance Record** — record ID, decision, governance references
11. **Acceptance Verification** — envelope ID, verification facts
12. **Acceptance Closure** — closure ID, complete closure references
13. **Engineering Traceability Summary** — all SHA-256 IDs and governance references in one table
14. **Engineering Report Notice** — static semantic safety statement

No data is invented.  No fake "approved" or "certified" sections are created.

## Semantic safety

| Concept | Correct interpretation |
|---------|----------------------|
| Engineering Pass | Decision result, not certification |
| Approval Readiness | Gate result; not an approval decision |
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

## Unified notice (static)

The notice section states:

> "This report presents deterministic engineering, audit, and governance artifacts
> already generated by Origlyph AI. It does not independently calculate engineering
> results, authenticate identities, create digital signatures, provide regulatory
> certification, grant approval, or authorize product release."

This text is static and contains no dynamic date/time or generated values.

## Workspace integration

### Controller (`workspace_controller.py`)

`ToleranceWorkspaceController.export_unified_html_report(path)`:

- Requires all ten artifacts to be cached.
- Raises `InvalidToleranceWorkspaceError` if any artifact is missing,
  naming the missing cached attribute.
- Delegates to `write_unified_engineering_report_html` via a lazy local import.
- Does **not** call any engineering, audit, governance, or acceptance builder.
- Does **not** mutate workspace state, project identity, or any cache.
- Accepts `str | Path`; returns the resolved `Path` of the written file.

### Session (`workspace_model.py — WorkspaceSession`)

`WorkspaceSession.unified_html_available` — boolean property; `True` when
all ten artifacts are non-None in the controller.

`WorkspaceSession.export_unified_html_report(path)` — delegates to the controller.

### View (`workspace_model.py — ToleranceWorkspaceView`)

An "Export Unified Engineering Report" button is added in a dedicated
"Unified Engineering Report" labelframe at `row=25` (after the Acceptance Closure
frame at row=23 and Project File frame at row=24).

The button handler follows the existing `_guard()` pattern:

```
_export_unified_html_report()  →  _guard(lambda: _export_unified_html_report_impl())
```

`_export_unified_html_report_impl()` opens a save-file dialog
(`asksaveasfilename`) with `.html` as the default extension and
`origlyph_engineering_report.html` as the default filename, then calls
`self._session.export_unified_html_report(path)` and shows an info dialog on
success.

The default filename `origlyph_engineering_report.html` contains no timestamp,
username, hostname, UUID, or random suffix.

## Project identity boundary

The export path is **not** persisted.  Export does **not** affect the
configuration fingerprint.  `project_id` is identical before and after export.

## Engineering state boundary

Export reads engineering artifacts; it never builds, replays, or modifies them.

## Authoritative acceptance state boundary

`WorkspaceAcceptanceState` (the persisted schema v5 acceptance input) is
read-only during export.

## Runtime governance boundary

The runtime governance chain is consumed as already-existing state.
Export reads these artifacts; it never builds, replays, or modifies them.

## Semantic limitations

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
- Not a regeneration trigger for missing upstream artifacts
- Not a Workspace schema v6 migration
