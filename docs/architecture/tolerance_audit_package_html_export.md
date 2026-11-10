# Tolerance Audit Package — HTML Export (Stage 21C)

## Purpose

Stage 21C introduces a deterministic, stdlib-only HTML renderer for
`ToleranceDecisionAuditPackage` (Stage 15O).  The rendered output is a
self-contained single-file engineering governance artifact suitable for
archive, review, and delivery without requiring any third-party toolchain.

**Audit Package HTML export is a deterministic presentation of an existing
audit package.  It does not build, verify, approve, certify, sign,
authenticate, or authorize the underlying engineering decision.**

## Source audit-package model

The renderer consumes `ToleranceDecisionAuditPackage` as defined in
`src/origlyph/tolerance/audit.py`.  Its structure:

| Field | Type | Description |
|-------|------|-------------|
| `audit_schema_version` | `str` | Schema version constant |
| `package_id` | `str` | Full SHA-256 package identity fingerprint |
| `report` | `ToleranceDecisionReport` | Bound decision report |
| `integrity_result` | `AuditIntegrityResult` | Integrity check outcome |
| `replay_manifest` | `DecisionReplayManifest` | Replay contract |
| `replayability_status` | `ReplayabilityStatus` | Structural replay readiness |
| `provenance` | `DecisionProvenance \| None` | Optional environment context |

The `DecisionReplayManifest` contains all fingerprints, policy identifiers,
and structural replay inputs.

## Engineering authority boundary

HTML export is a **presentation** of an already-generated
`ToleranceDecisionAuditPackage`.  It is **not** a build, verification,
approval, certification, digital signature, authentication, or release
authorization.

The renderer never calls:
- `build_decision_audit_package()`
- `verify_decision_audit_package()`
- `validate_decision_report_integrity()`
- `run_decision_report()`
- `evaluate_tolerance_decision()`
- `build_decision_evidence()`
- `assess_audit_change_impact()`
- `evaluate_audit_approval_readiness()`
- Any engineering engine

It only reads fields from the provided package and formats them into HTML.

## Renderer API

| Symbol | Description |
|--------|-------------|
| `render_audit_package_html(package)` | Render to an in-memory HTML string |
| `write_audit_package_html(package, path)` | Render and write to a file; returns resolved `Path` |
| `AuditPackageHtmlExportError` | Raised on invalid input or file I/O failure |

Both public functions validate that `package` is a
`ToleranceDecisionAuditPackage` instance and raise
`AuditPackageHtmlExportError` otherwise.

## Writer API

`write_audit_package_html(package, path)`:

- Accepts `str | Path` destination.
- Creates parent directories with `mkdir(parents=True, exist_ok=True)`.
- Writes `encoding="utf-8", newline="\n"` for cross-platform reproducibility.
- Wraps `OSError` in `AuditPackageHtmlExportError`.
- Returns the resolved `Path` of the written file.

## Deterministic contract

Identical `ToleranceDecisionAuditPackage` input always produces byte-identical
HTML output.  The renderer guarantees:

- No timestamps or wall-clock values
- No UUIDs or random identifiers
- No machine names, usernames, or environment paths
- No session-specific state
- No external CDN, stylesheet, font, image, or script references
- `render(pkg) == render(pkg)` and encoded UTF-8 bytes match exactly

Existing authoritative values already present inside the audit package
(fingerprints, IDs, timestamps stored in provenance) may be displayed
exactly as stored.  New values are never generated.

## Fingerprint fidelity

**Critical contract:** Every identifier and fingerprint stored in the audit
package is rendered exactly as stored.  The following fields are rendered at
full length without modification:

- `package.package_id` (64-char SHA-256)
- `replay_manifest.input_fingerprint` (64-char SHA-256)
- `replay_manifest.report_fingerprint` (64-char SHA-256)
- `replay_manifest.integrity_fingerprint` (64-char SHA-256)
- `replay_manifest.package_id` (64-char SHA-256)

`manifest.report_fingerprint` is the authoritative SHA-256 binding fingerprint
used in the Decision Report Binding section.

**Note:** `ToleranceDecisionReport.decision_id()` returns canonical decision
identity content (a full JSON representation of the decision), not a SHA-256
hash.  Similarly, `replay_manifest.decision_id` stores canonical decision
identity content rather than a compact hash.  Neither is rendered as a
fingerprint field; the renderer uses `manifest.report_fingerprint` for report
binding identity.

The renderer **never**:
- recomputes fingerprints
- truncates fingerprints
- re-hashes any value
- normalizes, transforms, or reinterprets any identifier

## HTML escaping

All user-derived text is passed through `html.escape(str(value), quote=True)`
before insertion into the output.  This covers all string fields: schema
versions, IDs, fingerprints, enum values, violation details, evidence fields,
policy identifiers, provenance fields, metadata keys and values, and all other
dynamic content.

## Injection protection

All dynamic strings are HTML-escaped.  The following inputs produce safe output:

- `<script>alert(1)</script>` → escaped
- `</td></table><img src=x onerror=alert(1)>` → escaped
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

The rendered document contains sections where actual package data supports them:

1. **Audit Package Summary** — replayability and integrity status badges
2. **Package Identity** — `package_id`, schema version, replayability
3. **Decision Report Binding** — decision ID, report schema, final status
4. **Integrity Summary** — integrity status badge, violations table if present
5. **Evidence References** — from `report.evidence_refs`
6. **Replay Manifest** — all manifest fields, correlation assumptions, policies
7. **Package Relationships** — provenance (if present)
8. **Fingerprints** — input, report, and integrity fingerprints
9. **Governance Notice** — static security disclaimer

No data is invented.  No fake "approved" or "certified" sections are created.

## Semantic safety

| Concept | Correct interpretation |
|---------|----------------------|
| Audit integrity | Structural consistency check; not a digital signature |
| Audit package | Governance artifact; not a certification |
| Fingerprint | Traceability identifier; not an authenticated identity |
| Verification | Structural check; not authentication |
| Closure | Reference packaging; not release authorization |

Forbidden labels (not present in rendered output):
- Certified
- Digitally Signed
- Authenticated User
- Regulatory Approved
- Authorized Release
- Compliance Certified

## Security notice (static)

The governance notice section states verbatim:

> "This audit package is a deterministic engineering governance artifact.
> Its identifiers and fingerprints support traceability and integrity comparison.
> They do not constitute digital signatures, authenticated identity,
> regulatory certification, compliance approval, or release authorization."

This text is static and contains no dynamic date/time or generated values.

## Workspace integration

### Controller (`workspace_controller.py`)

`ToleranceWorkspaceController.export_audit_html(path)`:

- Requires `self._last_audit_package` to be non-None (i.e.
  `run_audit_package()` must have been called since the last state mutation).
- Raises `InvalidToleranceWorkspaceError` if no audit package is cached.
- Delegates to `write_audit_package_html` via a lazy local import.
- Does **not** call `run_audit_package()`, `run_audit_integrity()`,
  `run_decision_report()`, `run_analysis()`, or any engineering function.
- Does **not** mutate workspace state, project identity, or any
  engineering or governance cache.
- Accepts `str | Path`; returns the resolved `Path` of the written file.

### Session (`workspace_model.py — WorkspaceSession`)

`WorkspaceSession.audit_html_available` — boolean property; `True` when
the controller has a cached audit package.

`WorkspaceSession.export_audit_html(path)` — delegates to the controller.

### View (`workspace_model.py — ToleranceWorkspaceView`)

An "Export Audit HTML" button is added to the Audit Package labelframe
at `row=5`, after the manifest treeview.  The button handler follows the
existing `_guard()` pattern:

```
_export_audit_html()  →  _guard(lambda: _export_audit_html_impl())
```

`_export_audit_html_impl()` opens a save-file dialog
(`asksaveasfilename`) with `.html` as the default extension and
`origlyph_audit_package.html` as the default filename, then calls
`self._session.export_audit_html(path)` and shows an info dialog on
success.

The default filename `origlyph_audit_package.html` contains no timestamp,
username, hostname, UUID, or random suffix.

## Project identity boundary

The export path is **not** persisted.  Export does **not** affect the
configuration fingerprint.  `project_id` is identical before and after
export, regardless of destination path or repetition count.

## Limitations

- `DecisionProvenance` fields are displayed only if present in the package.
  They are environment-specific values stored by the package builder; the
  renderer does not generate them.
- The renderer does not access the filesystem, network, or environment
  beyond what `Path.parent.mkdir()` and `Path.write_text()` require.
- Rendered output is not a legally binding document, digital signature,
  regulatory submission, or compliance record.

## Non-goals

- Not a re-verification of the audit package
- Not a new integrity check
- Not an approval mechanism
- Not a certification artifact
- Not a release document
- Not a comparison between packages
- Not a replay trigger
