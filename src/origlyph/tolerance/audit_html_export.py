"""Deterministic audit package HTML export (Stage 21C).

Renders a :class:`~origlyph.tolerance.audit.ToleranceDecisionAuditPackage`
into a self-contained, single-file HTML artifact.

Engineering authority boundary
-------------------------------
HTML export is a deterministic PRESENTATION of an already-generated
ToleranceDecisionAuditPackage.  It is NOT a build, verification, approval,
certification, digital signature, authentication, or release authorization.

The renderer reads package fields and formats them into HTML.  It never calls
the audit package builder, integrity validator, decision builder, evidence
builder, report builder, change impact, approval readiness, or any
engineering engine.

Determinism contract
---------------------
Identical :class:`~origlyph.tolerance.audit.ToleranceDecisionAuditPackage`
input always produces byte-identical HTML output.  The renderer includes no
timestamps, UUIDs, random values, machine names, environment paths, or other
non-deterministic values.

Fingerprint fidelity
---------------------
Every identifier and fingerprint stored in the audit package is rendered
exactly as stored.  No field is recomputed, truncated, re-hashed, normalized,
transformed, or reinterpreted by the renderer.

Self-contained output
----------------------
The rendered HTML is a single file with inline CSS.  No external stylesheets,
fonts, scripts, CDN resources, or local filesystem references are included.
"""

from __future__ import annotations

import html
from pathlib import Path

from .audit import ToleranceDecisionAuditPackage

__all__ = [
    "AuditPackageHtmlExportError",
    "render_audit_package_html",
    "write_audit_package_html",
]


class AuditPackageHtmlExportError(Exception):
    """Raised when the audit HTML export cannot be rendered or written."""


def render_audit_package_html(package: ToleranceDecisionAuditPackage) -> str:
    """Render a deterministic HTML artifact from a ToleranceDecisionAuditPackage.

    Returns a self-contained UTF-8 HTML string.  No external resources.
    Identical inputs produce byte-identical output.

    Parameters
    ----------
    package:
        An authoritative
        :class:`~origlyph.tolerance.audit.ToleranceDecisionAuditPackage`.

    Returns
    -------
    str
        Deterministic, self-contained HTML string.

    Raises
    ------
    AuditPackageHtmlExportError
        If ``package`` is not a ``ToleranceDecisionAuditPackage``.
    """
    if not isinstance(package, ToleranceDecisionAuditPackage):
        raise AuditPackageHtmlExportError(
            f"package must be a ToleranceDecisionAuditPackage, "
            f"got {type(package).__name__}"
        )
    return _render(package)


def write_audit_package_html(
    package: ToleranceDecisionAuditPackage,
    path: str | Path,
) -> Path:
    """Render and write the deterministic HTML artifact to a file.

    Parameters
    ----------
    package:
        An authoritative
        :class:`~origlyph.tolerance.audit.ToleranceDecisionAuditPackage`.
    path:
        Destination file path.

    Returns
    -------
    Path
        The resolved path of the written file.

    Raises
    ------
    AuditPackageHtmlExportError
        If the package is not a ``ToleranceDecisionAuditPackage`` or the file
        cannot be written.
    """
    html_content = render_audit_package_html(package)
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise AuditPackageHtmlExportError(
            f"Audit HTML artifact could not be written to {target}: {exc}"
        ) from exc
    return target


# ---------------------------------------------------------------------------
# Internal renderer — all functions below are private
# ---------------------------------------------------------------------------


def _esc(value: object) -> str:
    """HTML-escape any value converted to string."""
    return html.escape(str(value), quote=True)


def _replay_class(status_value: str) -> str:
    v = status_value.lower()
    if v == "replayable":
        return "badge-pass"
    if v == "not_replayable":
        return "badge-fail"
    if v == "incomplete":
        return "badge-marginal"
    return "badge-neutral"


def _integrity_class(status_value: str) -> str:
    v = status_value.lower()
    if v == "valid":
        return "badge-pass"
    if v == "invalid":
        return "badge-fail"
    if v == "incomplete":
        return "badge-marginal"
    return "badge-neutral"


def _severity_class(severity_value: str) -> str:
    v = severity_value.lower()
    if v == "error":
        return "sev-failure"
    if v == "warning":
        return "sev-boundary"
    return "sev-info"


_CSS = (
    "*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\n"
    "body {\n"
    "  font-family: ui-monospace, 'Courier New', Courier, monospace;\n"
    "  font-size: 13px;\n"
    "  line-height: 1.5;\n"
    "  color: #1a1a1a;\n"
    "  background: #f5f5f5;\n"
    "  padding: 32px 24px;\n"
    "}\n"
    ".report-wrapper {\n"
    "  max-width: 1100px;\n"
    "  margin: 0 auto;\n"
    "  background: #ffffff;\n"
    "  border: 1px solid #d0d0d0;\n"
    "  border-radius: 4px;\n"
    "  padding: 32px 36px;\n"
    "}\n"
    "h1 { font-size: 18px; font-weight: bold; margin-bottom: 4px; color: #111; }\n"
    ".report-meta { font-size: 11px; color: #555; margin-bottom: 24px; }\n"
    "h2 {\n"
    "  font-size: 13px;\n"
    "  font-weight: bold;\n"
    "  letter-spacing: 0.04em;\n"
    "  text-transform: uppercase;\n"
    "  color: #333;\n"
    "  border-bottom: 1px solid #ddd;\n"
    "  padding-bottom: 4px;\n"
    "  margin: 24px 0 10px 0;\n"
    "}\n"
    ".summary-row {\n"
    "  display: flex;\n"
    "  align-items: center;\n"
    "  gap: 16px;\n"
    "  margin-bottom: 8px;\n"
    "}\n"
    ".badge {\n"
    "  display: inline-block;\n"
    "  font-size: 12px;\n"
    "  font-weight: bold;\n"
    "  padding: 3px 10px;\n"
    "  border-radius: 3px;\n"
    "  letter-spacing: 0.05em;\n"
    "}\n"
    ".badge-pass     { background: #d4edda; color: #155724;"
    " border: 1px solid #c3e6cb; }\n"
    ".badge-fail     { background: #f8d7da; color: #721c24;"
    " border: 1px solid #f5c6cb; }\n"
    ".badge-marginal { background: #fff3cd; color: #856404;"
    " border: 1px solid #ffc107; }\n"
    ".badge-neutral  { background: #e2e3e5; color: #383d41;"
    " border: 1px solid #d6d8db; }\n"
    "table {\n"
    "  width: 100%;\n"
    "  border-collapse: collapse;\n"
    "  font-size: 12px;\n"
    "  margin-bottom: 8px;\n"
    "}\n"
    "th {\n"
    "  text-align: left;\n"
    "  background: #f0f0f0;\n"
    "  border: 1px solid #ccc;\n"
    "  padding: 5px 8px;\n"
    "  font-weight: bold;\n"
    "  white-space: nowrap;\n"
    "}\n"
    "td {\n"
    "  border: 1px solid #ddd;\n"
    "  padding: 4px 8px;\n"
    "  vertical-align: top;\n"
    "}\n"
    "tr:nth-child(even) td { background: #fafafa; }\n"
    ".fingerprint {\n"
    "  font-family: ui-monospace, 'Courier New', Courier, monospace;\n"
    "  font-size: 11px;\n"
    "  word-break: break-all;\n"
    "  color: #333;\n"
    "}\n"
    ".sev-failure { color: #721c24; font-weight: bold; }\n"
    ".sev-boundary { color: #856404; font-weight: bold; }\n"
    ".sev-info { color: #383d41; }\n"
    ".notice {\n"
    "  background: #fff8e1;\n"
    "  border: 1px solid #ffe082;\n"
    "  border-radius: 3px;\n"
    "  padding: 12px 16px;\n"
    "  font-size: 11px;\n"
    "  color: #5d4037;\n"
    "  margin: 24px 0 8px 0;\n"
    "  line-height: 1.6;\n"
    "}\n"
    ".footer {\n"
    "  margin-top: 36px;\n"
    "  font-size: 10px;\n"
    "  color: #888;\n"
    "  border-top: 1px solid #eee;\n"
    "  padding-top: 8px;\n"
    "}\n"
    "@media print {\n"
    "  body { background: white; padding: 0; }\n"
    "  .report-wrapper { border: none; border-radius: 0; padding: 0; }\n"
    "}\n"
)


def _render(package: ToleranceDecisionAuditPackage) -> str:
    parts: list[str] = []
    _render_head(package, parts)
    _render_summary(package, parts)
    _render_package_identity(package, parts)
    _render_report_binding(package, parts)
    _render_integrity_summary(package, parts)
    _render_evidence_refs(package, parts)
    _render_replay_manifest(package, parts)
    _render_provenance(package, parts)
    _render_fingerprints(package, parts)
    _render_governance_notice(parts)
    _render_footer(parts)
    return "\n".join(parts)


def _render_head(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    a = parts.append
    a("<!DOCTYPE html>")
    a('<html lang="en">')
    a("<head>")
    a('<meta charset="UTF-8">')
    a('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    a("<title>Origlyph Audit Package</title>")
    a(f"<style>\n{_CSS}</style>")
    a("</head>")
    a("<body>")
    a('<div class="report-wrapper">')
    a("<h1>Origlyph Engineering Audit Package</h1>")
    meta_parts = [
        f"Audit schema: {_esc(package.audit_schema_version)}",
        f"Report schema: {_esc(package.report.schema_version)}",
    ]
    a(f'<p class="report-meta">{" &nbsp;|&nbsp; ".join(meta_parts)}</p>')


def _render_summary(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Audit Package Summary</h2>")
    replay_cls = _replay_class(package.replayability_status.value)
    integrity_cls = _integrity_class(package.integrity_result.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(replay_cls)}">'
        f"Replay: {_esc(package.replayability_status.value.upper())}</span>"
    )
    a(
        f'<span class="badge {_esc(integrity_cls)}">'
        f"Integrity: {_esc(package.integrity_result.status.value.upper())}</span>"
    )
    a("</div>")


def _render_package_identity(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Package Identity</h2>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Package ID</td>"
        f'<td class="fingerprint">{_esc(package.package_id)}</td></tr>'
    )
    a(
        f"<tr><td>Audit Schema Version</td>"
        f"<td>{_esc(package.audit_schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Replayability Status</td>"
        f"<td>{_esc(package.replayability_status.value)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")


def _render_report_binding(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    report = package.report
    manifest = package.replay_manifest
    a = parts.append
    a("<h2>Decision Report Binding</h2>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Report Fingerprint (SHA-256)</td>"
        f'<td class="fingerprint">{_esc(manifest.report_fingerprint)}</td></tr>'
    )
    a(
        f"<tr><td>Report Schema Version</td>"
        f"<td>{_esc(report.schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Final Status</td>"
        f"<td>{_esc(report.final_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Is Complete</td>"
        f"<td>{_esc(report.is_complete)}</td></tr>"
    )
    a(
        f"<tr><td>Equality Tolerance</td>"
        f"<td>{_esc(report.equality_tolerance)}</td></tr>"
    )
    if report.sigma_multiplier is not None:
        a(
            f"<tr><td>Sigma Multiplier</td>"
            f"<td>{_esc(report.sigma_multiplier)}</td></tr>"
        )
    a("</tbody>")
    a("</table>")


def _render_integrity_summary(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    integrity = package.integrity_result
    a = parts.append
    a("<h2>Integrity Summary</h2>")
    integrity_cls = _integrity_class(integrity.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(integrity_cls)}">'
        f"{_esc(integrity.status.value.upper())}</span>"
    )
    a("</div>")
    if integrity.violations:
        a("<table>")
        a(
            "<thead><tr>"
            "<th>Severity</th><th>Code</th>"
            "<th>Scope</th><th>Subject</th><th>Detail</th>"
            "</tr></thead>"
        )
        a("<tbody>")
        for v in integrity.violations:
            sev_cls = _severity_class(v.severity.value)
            a(
                f"<tr>"
                f'<td class="{_esc(sev_cls)}">{_esc(v.severity.value)}</td>'
                f"<td>{_esc(v.code.value)}</td>"
                f"<td>{_esc(v.scope)}</td>"
                f"<td>{_esc(v.subject)}</td>"
                f"<td>{_esc(v.detail)}</td>"
                f"</tr>"
            )
        a("</tbody>")
        a("</table>")
    else:
        a("<p>No integrity violations.</p>")


def _render_evidence_refs(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    report = package.report
    if not report.evidence_refs:
        return
    a = parts.append
    a("<h2>Evidence References</h2>")
    a("<table>")
    a(
        "<thead><tr>"
        "<th>Evidence ID</th><th>Source</th>"
        "<th>Evidence Code</th><th>Reason Code</th>"
        "</tr></thead>"
    )
    a("<tbody>")
    for ref in report.evidence_refs:
        a(
            f"<tr>"
            f"<td>{_esc(ref.evidence_id)}</td>"
            f"<td>{_esc(ref.source)}</td>"
            f"<td>{_esc(ref.evidence_code)}</td>"
            f"<td>{_esc(ref.reason_code)}</td>"
            f"</tr>"
        )
    a("</tbody>")
    a("</table>")


def _render_replay_manifest(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    manifest = package.replay_manifest
    a = parts.append
    a("<h2>Replay Manifest</h2>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Report Schema Version</td>"
        f"<td>{_esc(manifest.report_schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Audit Schema Version</td>"
        f"<td>{_esc(manifest.audit_schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Package ID</td>"
        f'<td class="fingerprint">{_esc(manifest.package_id)}</td></tr>'
    )
    a(
        f"<tr><td>Equality Tolerance</td>"
        f"<td>{_esc(manifest.equality_tolerance)}</td></tr>"
    )
    if manifest.sigma_multiplier is not None:
        a(
            f"<tr><td>Sigma Multiplier</td>"
            f"<td>{_esc(manifest.sigma_multiplier)}</td></tr>"
        )
    a(
        f"<tr><td>Require Complete Policy</td>"
        f"<td>{_esc(manifest.require_complete_policy)}</td></tr>"
    )
    a(
        f"<tr><td>Integrity Status</td>"
        f"<td>{_esc(manifest.integrity_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Is Complete</td>"
        f"<td>{_esc(manifest.is_complete)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    if manifest.correlation_assumptions:
        a("<h2>Correlation Assumptions</h2>")
        a("<table>")
        a("<thead><tr><th>Metric Key</th><th>Coefficient</th></tr></thead>")
        a("<tbody>")
        for key, coefficient in manifest.correlation_assumptions:
            a(
                f"<tr>"
                f"<td>{_esc(key)}</td>"
                f"<td>{_esc(coefficient)}</td>"
                f"</tr>"
            )
        a("</tbody>")
        a("</table>")
    if manifest.policy_identifiers:
        a("<h2>Policy Identifiers</h2>")
        a("<table>")
        a("<thead><tr><th>Policy</th></tr></thead>")
        a("<tbody>")
        for policy in manifest.policy_identifiers:
            a(f"<tr><td>{_esc(policy)}</td></tr>")
        a("</tbody>")
        a("</table>")


def _render_provenance(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    if package.provenance is None:
        return
    prov = package.provenance
    a = parts.append
    a("<h2>Package Relationships</h2>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    if prov.generated_by is not None:
        a(
            f"<tr><td>Generated By</td>"
            f"<td>{_esc(prov.generated_by)}</td></tr>"
        )
    if prov.generation_timestamp is not None:
        a(
            f"<tr><td>Generation Timestamp</td>"
            f"<td>{_esc(prov.generation_timestamp)}</td></tr>"
        )
    if prov.audit_id is not None:
        a(
            f"<tr><td>Audit ID</td>"
            f'<td class="fingerprint">{_esc(prov.audit_id)}</td></tr>'
        )
    if prov.metadata:
        for meta_key, meta_val in sorted(prov.metadata.items()):
            a(
                f"<tr><td>metadata.{_esc(meta_key)}</td>"
                f"<td>{_esc(meta_val)}</td></tr>"
            )
    a("</tbody>")
    a("</table>")


def _render_fingerprints(
    package: ToleranceDecisionAuditPackage, parts: list[str]
) -> None:
    manifest = package.replay_manifest
    a = parts.append
    a("<h2>Fingerprints</h2>")
    a("<table>")
    a("<thead><tr><th>Name</th><th>SHA-256</th></tr></thead>")
    a("<tbody>")
    fingerprints = [
        ("Input Fingerprint", manifest.input_fingerprint),
        ("Report Fingerprint", manifest.report_fingerprint),
        ("Integrity Fingerprint", manifest.integrity_fingerprint),
    ]
    for name, fp in fingerprints:
        a(
            f"<tr>"
            f"<td>{_esc(name)}</td>"
            f'<td class="fingerprint">{_esc(fp)}</td>'
            f"</tr>"
        )
    a("</tbody>")
    a("</table>")


def _render_governance_notice(parts: list[str]) -> None:
    parts.append(
        '<div class="notice">'
        "<strong>Governance Notice</strong><br>"
        "This audit package is a deterministic engineering governance artifact. "
        "Its identifiers and fingerprints support traceability and integrity "
        "comparison. They do not constitute digital signatures, authenticated "
        "identity, regulatory certification, compliance approval, or release "
        "authorization."
        "</div>"
    )


def _render_footer(parts: list[str]) -> None:
    parts.append('<div class="footer">')
    parts.append(
        "Origlyph AI &mdash; Deterministic Engineering Audit Package"
        " &mdash; Audit Package HTML export is a deterministic presentation of an"
        " existing audit package. It does not build, verify, approve, certify,"
        " sign, authenticate, or authorize the underlying engineering decision."
    )
    parts.append("</div>")
    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
