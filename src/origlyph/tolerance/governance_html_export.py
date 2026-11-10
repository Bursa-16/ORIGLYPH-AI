"""Deterministic governance chain HTML export (Stage 21D).

Renders an already-generated governance/acceptance chain as a self-contained,
single-file HTML artifact.

Engineering authority boundary
-------------------------------
Governance HTML export is a deterministic PRESENTATION of already-generated
governance and acceptance artifacts.  It does not calculate, approve,
authenticate, sign, certify, or authorize the engineering decision.

The renderer reads existing runtime artifact fields and formats them into HTML.
It never calls compare_decision_audit_packages(), assess_audit_change_impact(),
determine_audit_change_disposition(), evaluate_audit_approval_readiness(),
build_audit_acceptance_handoff(), validate_audit_acceptance_record(),
build_acceptance_record_verification_envelope(),
build_acceptance_closure_manifest(), or any engineering engine.

Completeness requirement
-------------------------
The renderer requires all eight governance/acceptance chain artifacts.  Partial
chain export is not supported.  Missing artifacts result in an error; the caller
must ensure the full chain has been generated before invoking export.

Determinism contract
---------------------
Identical runtime artifact inputs always produce byte-identical HTML output.
The renderer includes no timestamps, UUIDs, random values, machine names,
environment paths, or other non-deterministic values.

Fingerprint fidelity
---------------------
Every identifier and fingerprint stored in governance/acceptance artifacts is
rendered exactly as stored.  No field is recomputed, truncated, re-hashed,
normalized, transformed, or reinterpreted by the renderer.

Self-contained output
----------------------
The rendered HTML is a single file with inline CSS.  No external stylesheets,
fonts, scripts, CDN resources, or local filesystem references are included.
"""

from __future__ import annotations

import html
from pathlib import Path

from .acceptance_closure import AuditAcceptanceClosureManifest
from .acceptance_handoff import AuditAcceptanceHandoffPackage
from .acceptance_record import ValidatedAuditAcceptanceRecord
from .acceptance_verification import AuditAcceptanceVerificationEnvelope
from .approval_readiness import AuditApprovalReadinessResult
from .change_disposition import AuditChangeDispositionResult
from .change_impact import AuditChangeImpactResult
from .comparison import AuditPackageComparisonResult

__all__ = [
    "GovernanceHtmlExportError",
    "render_governance_chain_html",
    "write_governance_chain_html",
]


class GovernanceHtmlExportError(Exception):
    """Raised when the governance HTML export cannot be rendered or written."""


def render_governance_chain_html(
    *,
    comparison: AuditPackageComparisonResult,
    change_impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
    approval_readiness: AuditApprovalReadinessResult,
    acceptance_handoff: AuditAcceptanceHandoffPackage,
    acceptance_record: ValidatedAuditAcceptanceRecord,
    acceptance_verification: AuditAcceptanceVerificationEnvelope,
    acceptance_closure: AuditAcceptanceClosureManifest,
) -> str:
    """Render a deterministic HTML artifact from a complete governance chain.

    Returns a self-contained UTF-8 HTML string.  No external resources.
    Identical inputs produce byte-identical output.

    Parameters
    ----------
    comparison:
        AuditPackageComparisonResult from the runtime governance chain.
    change_impact:
        AuditChangeImpactResult from the runtime governance chain.
    disposition:
        AuditChangeDispositionResult from the runtime governance chain.
    approval_readiness:
        AuditApprovalReadinessResult from the runtime governance chain.
    acceptance_handoff:
        AuditAcceptanceHandoffPackage from the runtime governance chain.
    acceptance_record:
        ValidatedAuditAcceptanceRecord from the runtime governance chain.
    acceptance_verification:
        AuditAcceptanceVerificationEnvelope from the runtime governance chain.
    acceptance_closure:
        AuditAcceptanceClosureManifest from the runtime governance chain.

    Returns
    -------
    str
        Deterministic, self-contained HTML string.

    Raises
    ------
    GovernanceHtmlExportError
        If any argument is not the expected governance chain type.
    """
    _validate_all(
        comparison=comparison,
        change_impact=change_impact,
        disposition=disposition,
        approval_readiness=approval_readiness,
        acceptance_handoff=acceptance_handoff,
        acceptance_record=acceptance_record,
        acceptance_verification=acceptance_verification,
        acceptance_closure=acceptance_closure,
    )
    return _render(
        comparison=comparison,
        change_impact=change_impact,
        disposition=disposition,
        approval_readiness=approval_readiness,
        acceptance_handoff=acceptance_handoff,
        acceptance_record=acceptance_record,
        acceptance_verification=acceptance_verification,
        acceptance_closure=acceptance_closure,
    )


def write_governance_chain_html(
    *,
    comparison: AuditPackageComparisonResult,
    change_impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
    approval_readiness: AuditApprovalReadinessResult,
    acceptance_handoff: AuditAcceptanceHandoffPackage,
    acceptance_record: ValidatedAuditAcceptanceRecord,
    acceptance_verification: AuditAcceptanceVerificationEnvelope,
    acceptance_closure: AuditAcceptanceClosureManifest,
    path: str | Path,
) -> Path:
    """Render and write the deterministic governance HTML artifact to a file.

    Parameters
    ----------
    comparison, change_impact, disposition, approval_readiness,
    acceptance_handoff, acceptance_record, acceptance_verification,
    acceptance_closure:
        Complete governance/acceptance chain runtime artifacts.
    path:
        Destination file path.

    Returns
    -------
    Path
        The resolved path of the written file.

    Raises
    ------
    GovernanceHtmlExportError
        If any argument is not the expected type or the file cannot be written.
    """
    html_content = render_governance_chain_html(
        comparison=comparison,
        change_impact=change_impact,
        disposition=disposition,
        approval_readiness=approval_readiness,
        acceptance_handoff=acceptance_handoff,
        acceptance_record=acceptance_record,
        acceptance_verification=acceptance_verification,
        acceptance_closure=acceptance_closure,
    )
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise GovernanceHtmlExportError(
            f"Governance HTML artifact could not be written to {target}: {exc}"
        ) from exc
    return target


# ---------------------------------------------------------------------------
# Internal renderer — all functions below are private
# ---------------------------------------------------------------------------


def _esc(value: object) -> str:
    """HTML-escape any value converted to string."""
    return html.escape(str(value), quote=True)


def _validate_all(
    *,
    comparison: object,
    change_impact: object,
    disposition: object,
    approval_readiness: object,
    acceptance_handoff: object,
    acceptance_record: object,
    acceptance_verification: object,
    acceptance_closure: object,
) -> None:
    checks = [
        (comparison, AuditPackageComparisonResult, "comparison"),
        (change_impact, AuditChangeImpactResult, "change_impact"),
        (disposition, AuditChangeDispositionResult, "disposition"),
        (approval_readiness, AuditApprovalReadinessResult, "approval_readiness"),
        (acceptance_handoff, AuditAcceptanceHandoffPackage, "acceptance_handoff"),
        (acceptance_record, ValidatedAuditAcceptanceRecord, "acceptance_record"),
        (
            acceptance_verification,
            AuditAcceptanceVerificationEnvelope,
            "acceptance_verification",
        ),
        (acceptance_closure, AuditAcceptanceClosureManifest, "acceptance_closure"),
    ]
    for value, expected_type, name in checks:
        if not isinstance(value, expected_type):
            raise GovernanceHtmlExportError(
                f"{name} must be a {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )


def _status_class(status_value: str) -> str:
    v = status_value.lower()
    if v in ("identical", "complete", "verified_binding", "ready",
             "ready_for_governed_acceptance", "accept",
             "accept_with_traceability", "approved", "none"):
        return "badge-pass"
    if v in ("blocked", "structurally_incompatible", "rejected", "error"):
        return "badge-fail"
    if v in ("changed", "compliance_relevant", "engineering_evidence",
             "engineering_review_required", "revalidation_required",
             "replay_required", "action_required", "returned_for_action",
             "traceability_only"):
        return "badge-warn"
    return "badge-neutral"


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
    "  gap: 12px;\n"
    "  flex-wrap: wrap;\n"
    "  margin-bottom: 8px;\n"
    "}\n"
    ".badge {\n"
    "  display: inline-block;\n"
    "  padding: 2px 10px;\n"
    "  border-radius: 3px;\n"
    "  font-size: 11px;\n"
    "  font-weight: bold;\n"
    "  letter-spacing: 0.04em;\n"
    "}\n"
    ".badge-pass { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }\n"
    ".badge-fail { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }\n"
    ".badge-warn { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }\n"
    ".badge-neutral { background: #e2e3e5; color: #383d41; "
    "border: 1px solid #d6d8db; }\n"
    "table {\n"
    "  width: 100%;\n"
    "  border-collapse: collapse;\n"
    "  margin-bottom: 8px;\n"
    "  font-size: 12px;\n"
    "}\n"
    "thead th {\n"
    "  background: #f0f0f0;\n"
    "  font-weight: bold;\n"
    "  padding: 4px 8px;\n"
    "  text-align: left;\n"
    "  border: 1px solid #ccc;\n"
    "}\n"
    "tbody td {\n"
    "  padding: 3px 8px;\n"
    "  border: 1px solid #ddd;\n"
    "  vertical-align: top;\n"
    "}\n"
    ".fingerprint {\n"
    "  font-family: ui-monospace, 'Courier New', Courier, monospace;\n"
    "  font-size: 11px;\n"
    "  word-break: break-all;\n"
    "}\n"
    ".ref-label {\n"
    "  font-style: italic;\n"
    "  color: #555;\n"
    "  font-size: 11px;\n"
    "}\n"
    ".notice {\n"
    "  background: #fff8e1;\n"
    "  border: 1px solid #ffe082;\n"
    "  border-radius: 4px;\n"
    "  padding: 12px 16px;\n"
    "  margin-top: 24px;\n"
    "  font-size: 12px;\n"
    "  color: #3e2000;\n"
    "}\n"
    ".footer {\n"
    "  margin-top: 24px;\n"
    "  padding-top: 10px;\n"
    "  border-top: 1px solid #ddd;\n"
    "  font-size: 11px;\n"
    "  color: #777;\n"
    "}\n"
)


def _render(
    *,
    comparison: AuditPackageComparisonResult,
    change_impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
    approval_readiness: AuditApprovalReadinessResult,
    acceptance_handoff: AuditAcceptanceHandoffPackage,
    acceptance_record: ValidatedAuditAcceptanceRecord,
    acceptance_verification: AuditAcceptanceVerificationEnvelope,
    acceptance_closure: AuditAcceptanceClosureManifest,
) -> str:
    parts: list[str] = []
    _render_head(parts)
    _render_chain_summary(
        comparison, change_impact, disposition, approval_readiness,
        acceptance_record, acceptance_closure, parts,
    )
    _render_comparison(comparison, parts)
    _render_change_impact(change_impact, parts)
    _render_disposition(disposition, parts)
    _render_approval_readiness(approval_readiness, parts)
    _render_acceptance_handoff(acceptance_handoff, parts)
    _render_acceptance_record(acceptance_record, parts)
    _render_acceptance_verification(acceptance_verification, parts)
    _render_acceptance_closure(acceptance_closure, parts)
    _render_traceability(acceptance_handoff, acceptance_record,
                         acceptance_verification, acceptance_closure, parts)
    _render_governance_notice(parts)
    _render_footer(parts)
    return "\n".join(parts)


def _render_head(parts: list[str]) -> None:
    a = parts.append
    a("<!DOCTYPE html>")
    a('<html lang="en">')
    a("<head>")
    a('<meta charset="UTF-8">')
    a('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    a("<title>Origlyph Governance Report</title>")
    a(f"<style>\n{_CSS}</style>")
    a("</head>")
    a("<body>")
    a('<div class="report-wrapper">')
    a("<h1>Origlyph Engineering Governance Report</h1>")
    a('<p class="report-meta">Deterministic Governance Chain HTML Export &mdash; '
      "Stage 21D</p>")


def _render_chain_summary(
    comparison: AuditPackageComparisonResult,
    change_impact: AuditChangeImpactResult,
    disposition: AuditChangeDispositionResult,
    approval_readiness: AuditApprovalReadinessResult,
    acceptance_record: ValidatedAuditAcceptanceRecord,
    acceptance_closure: AuditAcceptanceClosureManifest,
    parts: list[str],
) -> None:
    a = parts.append
    a("<h2>Governance Chain Summary</h2>")
    a('<div class="summary-row">')
    for label, value in [
        ("Comparison", comparison.status.value),
        ("Impact", change_impact.overall_impact.value),
        ("Disposition", disposition.disposition.value),
        ("Readiness", approval_readiness.status.value),
        ("Decision", acceptance_record.decision.value),
        ("Closure", acceptance_closure.status.value),
    ]:
        cls = _status_class(value)
        a(
            f'<span class="badge {_esc(cls)}">'
            f"{_esc(label)}: {_esc(value.upper())}</span>"
        )
    a("</div>")


def _render_comparison(
    comparison: AuditPackageComparisonResult, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Audit Comparison</h2>")
    cls = _status_class(comparison.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Status: {_esc(comparison.status.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Baseline Package ID</td>"
        f'<td class="fingerprint">{_esc(comparison.baseline_package_id)}</td></tr>'
    )
    a(
        f"<tr><td>Candidate Package ID</td>"
        f'<td class="fingerprint">{_esc(comparison.candidate_package_id)}</td></tr>'
    )
    a(
        f"<tr><td>Provenance Compared</td>"
        f"<td>{_esc(comparison.provenance_compared)}</td></tr>"
    )
    a(
        f"<tr><td>Change Count</td>"
        f"<td>{_esc(len(comparison.changes))}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    if comparison.changes:
        a("<table>")
        a(
            "<thead><tr>"
            "<th>Code</th><th>Category</th><th>Significance</th>"
            "<th>Scope</th><th>Subject ID</th><th>Detail</th>"
            "</tr></thead>"
        )
        a("<tbody>")
        for change in comparison.changes:
            a(
                f"<tr>"
                f"<td>{_esc(change.code.value)}</td>"
                f"<td>{_esc(change.category.value)}</td>"
                f"<td>{_esc(change.significance.value)}</td>"
                f"<td>{_esc(change.scope)}</td>"
                f"<td>{_esc(change.subject_id)}</td>"
                f"<td>{_esc(change.detail)}</td>"
                f"</tr>"
            )
        a("</tbody>")
        a("</table>")


def _render_change_impact(
    change_impact: AuditChangeImpactResult, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Change Impact</h2>")
    cls = _status_class(change_impact.overall_impact.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Overall Impact: {_esc(change_impact.overall_impact.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Comparison Status</td>"
        f"<td>{_esc(change_impact.comparison_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Changed</td>"
        f"<td>{_esc(change_impact.decision_changed)}</td></tr>"
    )
    if change_impact.previous_decision_status is not None:
        a(
            f"<tr><td>Previous Decision Status</td>"
            f"<td>{_esc(change_impact.previous_decision_status.value)}</td></tr>"
        )
    if change_impact.current_decision_status is not None:
        a(
            f"<tr><td>Current Decision Status</td>"
            f"<td>{_esc(change_impact.current_decision_status.value)}</td></tr>"
        )
    a("</tbody>")
    a("</table>")
    if change_impact.assessed_changes:
        a("<table>")
        a(
            "<thead><tr>"
            "<th>Change Code</th><th>Impact</th><th>Reason</th>"
            "</tr></thead>"
        )
        a("<tbody>")
        for assessed in change_impact.assessed_changes:
            a(
                f"<tr>"
                f"<td>{_esc(assessed.change.code.value)}</td>"
                f"<td>{_esc(assessed.impact.value)}</td>"
                f"<td>{_esc(assessed.reason.value)}</td>"
                f"</tr>"
            )
        a("</tbody>")
        a("</table>")


def _render_disposition(
    disposition: AuditChangeDispositionResult, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Change Disposition</h2>")
    cls = _status_class(disposition.disposition.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Disposition: {_esc(disposition.disposition.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Comparison Status</td>"
        f"<td>{_esc(disposition.comparison_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Source Impact</td>"
        f"<td>{_esc(disposition.source_impact.value)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Changed</td>"
        f"<td>{_esc(disposition.decision_changed)}</td></tr>"
    )
    if disposition.previous_decision_status is not None:
        a(
            f"<tr><td>Previous Decision Status</td>"
            f"<td>{_esc(disposition.previous_decision_status.value)}</td></tr>"
        )
    if disposition.current_decision_status is not None:
        a(
            f"<tr><td>Current Decision Status</td>"
            f"<td>{_esc(disposition.current_decision_status.value)}</td></tr>"
        )
    a("</tbody>")
    a("</table>")
    if disposition.reasons:
        a("<table>")
        a(
            "<thead><tr>"
            "<th>Reason Code</th><th>Disposition</th><th>Source Impact</th>"
            "</tr></thead>"
        )
        a("<tbody>")
        for reason in disposition.reasons:
            a(
                f"<tr>"
                f"<td>{_esc(reason.code.value)}</td>"
                f"<td>{_esc(reason.disposition.value)}</td>"
                f"<td>{_esc(reason.source_impact.value)}</td>"
                f"</tr>"
            )
        a("</tbody>")
        a("</table>")


def _render_approval_readiness(
    approval_readiness: AuditApprovalReadinessResult, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Approval Readiness</h2>")
    cls = _status_class(approval_readiness.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Status: {_esc(approval_readiness.status.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Is Ready</td>"
        f"<td>{_esc(approval_readiness.is_ready)}</td></tr>"
    )
    a(
        f"<tr><td>Comparison Status</td>"
        f"<td>{_esc(approval_readiness.comparison_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Source Impact</td>"
        f"<td>{_esc(approval_readiness.source_impact.value)}</td></tr>"
    )
    a(
        f"<tr><td>Source Disposition</td>"
        f"<td>{_esc(approval_readiness.source_disposition.value)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Changed</td>"
        f"<td>{_esc(approval_readiness.decision_changed)}</td></tr>"
    )
    if approval_readiness.previous_decision_status is not None:
        a(
            f"<tr><td>Previous Decision Status</td>"
            f"<td>{_esc(approval_readiness.previous_decision_status.value)}</td></tr>"
        )
    if approval_readiness.current_decision_status is not None:
        a(
            f"<tr><td>Current Decision Status</td>"
            f"<td>{_esc(approval_readiness.current_decision_status.value)}</td></tr>"
        )
    a("</tbody>")
    a("</table>")
    a(
        '<p class="ref-label">Approval readiness is a gate result, '
        "not an approval decision.</p>"
    )


def _render_acceptance_handoff(
    acceptance_handoff: AuditAcceptanceHandoffPackage, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Acceptance Handoff</h2>")
    cls = _status_class(acceptance_handoff.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Status: {_esc(acceptance_handoff.status.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Handoff ID</td>"
        f'<td class="fingerprint">{_esc(acceptance_handoff.handoff_id)}</td></tr>'
    )
    a(
        f"<tr><td>Schema Version</td>"
        f"<td>{_esc(acceptance_handoff.schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Baseline Package ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_handoff.baseline_package_id)}</td></tr>"
    )
    a(
        f"<tr><td>Candidate Package ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_handoff.candidate_package_id)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    a(
        '<p class="ref-label">Acceptance handoff status is not an approval '
        "decision.</p>"
    )


def _render_acceptance_record(
    acceptance_record: ValidatedAuditAcceptanceRecord, parts: list[str]
) -> None:
    a = parts.append
    a("<h2>Acceptance Record</h2>")
    cls = _status_class(acceptance_record.decision.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Decision: {_esc(acceptance_record.decision.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Acceptance Record ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_record.acceptance_record_id)}</td></tr>"
    )
    a(
        f"<tr><td>Schema Version</td>"
        f"<td>{_esc(acceptance_record.schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Handoff ID</td>"
        f'<td class="fingerprint">{_esc(acceptance_record.handoff_id)}</td></tr>'
    )
    a(
        f"<tr><td>Handoff Status</td>"
        f"<td>{_esc(acceptance_record.handoff_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Authority Reference</td>"
        f"<td>{_esc(acceptance_record.authority_reference)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Reference</td>"
        f"<td>{_esc(acceptance_record.decision_reference)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    a(
        '<p class="ref-label">Authority reference is a governance reference, '
        "not an authenticated identity. Decision reference is a governance "
        "reference, not a digital signature.</p>"
    )


def _render_acceptance_verification(
    acceptance_verification: AuditAcceptanceVerificationEnvelope,
    parts: list[str],
) -> None:
    a = parts.append
    a("<h2>Acceptance Verification</h2>")
    cls = _status_class(acceptance_verification.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Status: {_esc(acceptance_verification.status.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Envelope ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_verification.envelope_id)}</td></tr>"
    )
    a(
        f"<tr><td>Schema Version</td>"
        f"<td>{_esc(acceptance_verification.schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Handoff ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_verification.handoff_id)}</td></tr>"
    )
    a(
        f"<tr><td>Acceptance Record ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_verification.acceptance_record_id)}</td></tr>"
    )
    a(
        f"<tr><td>Decision</td>"
        f"<td>{_esc(acceptance_verification.decision.value)}</td></tr>"
    )
    a(
        f"<tr><td>Authority Reference</td>"
        f"<td>{_esc(acceptance_verification.authority_reference)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Reference</td>"
        f"<td>{_esc(acceptance_verification.decision_reference)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    if acceptance_verification.verification_facts:
        a("<table>")
        a("<thead><tr><th>Verification Fact</th></tr></thead>")
        a("<tbody>")
        for fact in acceptance_verification.verification_facts:
            a(f"<tr><td>{_esc(fact.value)}</td></tr>")
        a("</tbody>")
        a("</table>")
    a(
        '<p class="ref-label">Verification status reflects structural '
        "consistency, not identity authentication.</p>"
    )


def _render_acceptance_closure(
    acceptance_closure: AuditAcceptanceClosureManifest, parts: list[str]
) -> None:
    refs = acceptance_closure.references
    a = parts.append
    a("<h2>Acceptance Closure</h2>")
    cls = _status_class(acceptance_closure.status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(cls)}">'
        f"Status: {_esc(acceptance_closure.status.value.upper())}</span>"
    )
    a("</div>")
    a("<table>")
    a("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Closure ID</td>"
        f'<td class="fingerprint">'
        f"{_esc(acceptance_closure.closure_id)}</td></tr>"
    )
    a(
        f"<tr><td>Schema Version</td>"
        f"<td>{_esc(acceptance_closure.schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Handoff ID</td>"
        f'<td class="fingerprint">{_esc(refs.handoff_id)}</td></tr>'
    )
    a(
        f"<tr><td>Acceptance Record ID</td>"
        f'<td class="fingerprint">{_esc(refs.acceptance_record_id)}</td></tr>'
    )
    a(
        f"<tr><td>Envelope ID</td>"
        f'<td class="fingerprint">{_esc(refs.envelope_id)}</td></tr>'
    )
    a(
        f"<tr><td>Decision</td>"
        f"<td>{_esc(refs.decision.value)}</td></tr>"
    )
    a(
        f"<tr><td>Authority Reference</td>"
        f"<td>{_esc(refs.authority_reference)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Reference</td>"
        f"<td>{_esc(refs.decision_reference)}</td></tr>"
    )
    a(
        f"<tr><td>Verification Status</td>"
        f"<td>{_esc(refs.verification_status.value)}</td></tr>"
    )
    a(
        f"<tr><td>Handoff Schema Version</td>"
        f"<td>{_esc(refs.handoff_schema_version)}</td></tr>"
    )
    a(
        f"<tr><td>Handoff Status</td>"
        f"<td>{_esc(refs.handoff_status.value)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")
    a(
        '<p class="ref-label">Closure manifest closes the deterministic '
        "governance artifact chain. It is not regulatory certification or "
        "release authorization.</p>"
    )


def _render_traceability(
    acceptance_handoff: AuditAcceptanceHandoffPackage,
    acceptance_record: ValidatedAuditAcceptanceRecord,
    acceptance_verification: AuditAcceptanceVerificationEnvelope,
    acceptance_closure: AuditAcceptanceClosureManifest,
    parts: list[str],
) -> None:
    refs = acceptance_closure.references
    a = parts.append
    a("<h2>Traceability References</h2>")
    a("<table>")
    a("<thead><tr><th>Name</th><th>ID (SHA-256)</th></tr></thead>")
    a("<tbody>")
    rows = [
        ("Handoff ID", acceptance_handoff.handoff_id),
        ("Baseline Package ID", acceptance_handoff.baseline_package_id),
        ("Candidate Package ID", acceptance_handoff.candidate_package_id),
        ("Acceptance Record ID", acceptance_record.acceptance_record_id),
        ("Envelope ID", acceptance_verification.envelope_id),
        ("Closure ID", acceptance_closure.closure_id),
    ]
    for name, fp in rows:
        a(
            f"<tr>"
            f"<td>{_esc(name)}</td>"
            f'<td class="fingerprint">{_esc(fp)}</td>'
            f"</tr>"
        )
    a("</tbody>")
    a("</table>")
    a("<table>")
    a("<thead><tr><th>Name</th><th>Governance Reference</th></tr></thead>")
    a("<tbody>")
    a(
        f"<tr><td>Authority Reference</td>"
        f"<td>{_esc(refs.authority_reference)}</td></tr>"
    )
    a(
        f"<tr><td>Decision Reference</td>"
        f"<td>{_esc(refs.decision_reference)}</td></tr>"
    )
    a("</tbody>")
    a("</table>")


def _render_governance_notice(parts: list[str]) -> None:
    parts.append(
        '<div class="notice">'
        "<strong>Governance Notice</strong><br>"
        "This governance report presents deterministic engineering governance "
        "artifacts. Approval readiness is not approval. Acceptance references are "
        "governance references, not authenticated identities. Verification and "
        "closure artifacts do not constitute digital signatures, regulatory "
        "certification, compliance approval, or release authorization."
        "</div>"
    )


def _render_footer(parts: list[str]) -> None:
    parts.append('<div class="footer">')
    parts.append(
        "Origlyph AI &mdash; Deterministic Engineering Governance Report"
        " &mdash; Governance HTML export is a deterministic presentation of "
        "already-generated governance and acceptance artifacts. It does not "
        "calculate, approve, authenticate, sign, certify, or authorize the "
        "engineering decision."
    )
    parts.append("</div>")
    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
