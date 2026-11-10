"""Deterministic decision report HTML export (Stage 21B).

This module renders a :class:`~origlyph.tolerance.report.ToleranceDecisionReport`
into a self-contained, single-file HTML engineering report.

Engineering authority boundary
-------------------------------
HTML export is a deterministic PRESENTATION of an already-generated
ToleranceDecisionReport.  It is NOT a new engineering calculation, approval,
certification, or governance decision.

Determinism contract
---------------------
Identical :class:`~origlyph.tolerance.report.ToleranceDecisionReport` input
always produces byte-identical HTML output.  The renderer includes no
timestamps, UUIDs, random values, machine names, environment paths, or other
non-deterministic values.

:class:`~origlyph.tolerance.report.DecisionProvenance` is intentionally
omitted from the rendered output because provenance fields
(``generation_timestamp``, ``audit_id``, ``generated_by``) are
environment-specific and are excluded from the deterministic report identity
per the Stage 15M contract.

Self-contained output
----------------------
The rendered HTML is a single file with inline CSS.  No external stylesheets,
fonts, scripts, CDN resources, or local filesystem references are included.
"""

from __future__ import annotations

import html
from pathlib import Path

from .report import ToleranceDecisionReport

__all__ = [
    "DecisionReportHtmlExportError",
    "render_decision_report_html",
    "write_decision_report_html",
]


class DecisionReportHtmlExportError(Exception):
    """Raised when the HTML export cannot be rendered or written."""


def render_decision_report_html(report: ToleranceDecisionReport) -> str:
    """Render a deterministic HTML report from a ToleranceDecisionReport.

    Returns a self-contained UTF-8 HTML string.  No external resources.
    Identical inputs produce byte-identical output.

    Parameters
    ----------
    report:
        An authoritative :class:`~origlyph.tolerance.report.ToleranceDecisionReport`
        to render.

    Returns
    -------
    str
        Deterministic, self-contained HTML string.

    Raises
    ------
    DecisionReportHtmlExportError
        If ``report`` is not a ``ToleranceDecisionReport``.
    """
    if not isinstance(report, ToleranceDecisionReport):
        raise DecisionReportHtmlExportError(
            f"report must be a ToleranceDecisionReport, "
            f"got {type(report).__name__}"
        )
    return _render(report)


def write_decision_report_html(
    report: ToleranceDecisionReport,
    path: str | Path,
) -> Path:
    """Render and write the deterministic HTML report to a file.

    Parameters
    ----------
    report:
        An authoritative :class:`~origlyph.tolerance.report.ToleranceDecisionReport`.
    path:
        Destination file path.

    Returns
    -------
    Path
        The resolved path of the written file.

    Raises
    ------
    DecisionReportHtmlExportError
        If the report is not a ``ToleranceDecisionReport`` or the file
        cannot be written.
    """
    html_content = render_decision_report_html(report)
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise DecisionReportHtmlExportError(
            f"HTML report could not be written to {target}: {exc}"
        ) from exc
    return target


# ---------------------------------------------------------------------------
# Internal renderer — all functions below are private
# ---------------------------------------------------------------------------


def _esc(value: object) -> str:
    """HTML-escape any value converted to string."""
    return html.escape(str(value), quote=True)


def _status_class(status_value: str) -> str:
    v = status_value.lower()
    if v == "pass":
        return "badge-pass"
    if v == "fail":
        return "badge-fail"
    if v in ("marginal", "at_boundary"):
        return "badge-marginal"
    return "badge-neutral"


def _severity_class(severity_value: str) -> str:
    v = severity_value.lower()
    if v == "failure":
        return "sev-failure"
    if v == "boundary":
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
    ".summary-text   { font-style: italic; color: #444; }\n"
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
    ".sev-failure { color: #721c24; font-weight: bold; }\n"
    ".sev-boundary { color: #856404; font-weight: bold; }\n"
    ".sev-info { color: #383d41; }\n"
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


def _render(report: ToleranceDecisionReport) -> str:
    parts: list[str] = []
    _render_head(report, parts)
    _render_summary(report, parts)
    _render_reason_codes(report, parts)
    _render_triggered_reasons(report, parts)
    _render_contributors(report, parts)
    _render_all_metrics(report, parts)
    _render_evidence_refs(report, parts)
    _render_footer(parts)
    return "\n".join(parts)


def _render_head(report: ToleranceDecisionReport, parts: list[str]) -> None:
    a = parts.append
    a("<!DOCTYPE html>")
    a('<html lang="en">')
    a("<head>")
    a('<meta charset="UTF-8">')
    a('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    a("<title>Origlyph Decision Report</title>")
    a(f"<style>\n{_CSS}</style>")
    a("</head>")
    a("<body>")
    a('<div class="report-wrapper">')
    a("<h1>Origlyph Engineering Decision Report</h1>")
    meta_parts = [
        f"Schema: {_esc(report.schema_version)}",
        f"Equality tolerance: {_esc(report.equality_tolerance)}",
    ]
    if report.sigma_multiplier is not None:
        meta_parts.append(f"Sigma multiplier: {_esc(report.sigma_multiplier)}")
    a(f'<p class="report-meta">{" &nbsp;|&nbsp; ".join(meta_parts)}</p>')


def _render_summary(report: ToleranceDecisionReport, parts: list[str]) -> None:
    a = parts.append
    a("<h2>Decision Summary</h2>")
    status_cls = _status_class(report.final_status.value)
    a('<div class="summary-row">')
    a(
        f'<span class="badge {_esc(status_cls)}">'
        f"{_esc(report.final_status.value.upper())}</span>"
    )
    completeness = "Complete" if report.is_complete else "Incomplete"
    a(f"<span>{_esc(completeness)}</span>")
    if report.summary_text:
        a(f'<span class="summary-text">{_esc(report.summary_text)}</span>')
    a("</div>")
    if report.summary_code:
        a(f"<p>Summary code: {_esc(report.summary_code)}</p>")


_METRICS_SECTIONS = (
    ("Worst-Case Metrics", "worst_case_metrics"),
    ("Statistical Metrics", "statistical_metrics"),
    ("Correlation Metrics", "correlation_metrics"),
    ("Sensitivity Metrics", "sensitivity_metrics"),
    ("Budget Metrics", "budget_metrics"),
    ("Allocation Metrics", "allocation_metrics"),
    ("Worst-Case Reconciliation", "worst_case_reconciliation_metrics"),
    ("Statistical Reconciliation", "statistical_reconciliation_metrics"),
)


def _render_all_metrics(
    report: ToleranceDecisionReport, parts: list[str]
) -> None:
    for heading, attr in _METRICS_SECTIONS:
        metrics = getattr(report, attr)
        if metrics:
            parts.append(f"<h2>{heading}</h2>")
            _render_metrics_table(metrics, parts)


def _render_footer(parts: list[str]) -> None:
    parts.append('<div class="footer">')
    parts.append(
        "Origlyph AI &mdash; Deterministic Engineering Decision Report"
        " &mdash; HTML export is a presentation of an already-generated"
        " ToleranceDecisionReport. It is not a new engineering calculation,"
        " approval, or certification."
    )
    parts.append("</div>")
    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")


def _render_reason_codes(
    report: ToleranceDecisionReport,
    parts: list[str],
) -> None:
    if (
        not report.governing_reason_codes
        and not report.marginal_reason_codes
        and not report.supporting_reason_codes
    ):
        return
    parts.append("<h2>Reason Codes</h2>")
    parts.append("<table>")
    parts.append(
        "<thead><tr><th>Category</th><th>Code</th></tr></thead>"
    )
    parts.append("<tbody>")
    for code in report.governing_reason_codes:
        parts.append(
            f'<tr><td class="sev-failure">GOVERNING</td>'
            f"<td>{_esc(code.value)}</td></tr>"
        )
    for code in report.marginal_reason_codes:
        parts.append(
            f'<tr><td class="sev-boundary">MARGINAL</td>'
            f"<td>{_esc(code.value)}</td></tr>"
        )
    for code in report.supporting_reason_codes:
        parts.append(
            f'<tr><td class="sev-info">SUPPORTING</td>'
            f"<td>{_esc(code.value)}</td></tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")


def _render_triggered_reasons(
    report: ToleranceDecisionReport,
    parts: list[str],
) -> None:
    if not report.triggered_reasons:
        return
    parts.append("<h2>Triggered Reasons</h2>")
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        "<th>Reason Code</th><th>Severity</th>"
        "<th>Detail</th><th>Evidence IDs</th>"
        "</tr></thead>"
    )
    parts.append("<tbody>")
    for ref in report.triggered_reasons:
        sev_cls = _severity_class(ref.severity.value)
        ev_ids = ", ".join(_esc(e) for e in ref.evidence_ids)
        parts.append(
            f"<tr>"
            f"<td>{_esc(ref.reason_code.value)}</td>"
            f'<td class="{_esc(sev_cls)}">{_esc(ref.severity.value)}</td>'
            f"<td>{_esc(ref.detail)}</td>"
            f"<td>{ev_ids}</td>"
            f"</tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")


def _render_contributors(
    report: ToleranceDecisionReport,
    parts: list[str],
) -> None:
    if not report.contributors:
        return
    parts.append("<h2>Contributors</h2>")
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        "<th>Name</th><th>Type</th>"
        "<th>Value</th><th>Sigma</th>"
        "</tr></thead>"
    )
    parts.append("<tbody>")
    for c in report.contributors:
        val = (
            f"{c.contribution_value:.6g}"
            if c.contribution_value is not None
            else "&#8212;"
        )
        sig = (
            f"{c.contribution_sigma:.6g}"
            if c.contribution_sigma is not None
            else "&#8212;"
        )
        parts.append(
            f"<tr>"
            f"<td>{_esc(c.name)}</td>"
            f"<td>{_esc(c.contribution_type)}</td>"
            f"<td>{val}</td>"
            f"<td>{sig}</td>"
            f"</tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")


def _render_metrics_table(
    metrics: tuple,
    parts: list[str],
) -> None:
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        "<th>Key</th><th>Value</th>"
        "<th>Lower Bound</th><th>Upper Bound</th>"
        "</tr></thead>"
    )
    parts.append("<tbody>")
    for m in metrics:
        lb = f"{m.lower_bound:.6g}" if m.lower_bound is not None else "&#8212;"
        ub = f"{m.upper_bound:.6g}" if m.upper_bound is not None else "&#8212;"
        parts.append(
            f"<tr>"
            f"<td>{_esc(m.key)}</td>"
            f"<td>{_esc(f'{m.value:.6g}')}</td>"
            f"<td>{lb}</td>"
            f"<td>{ub}</td>"
            f"</tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")


def _render_evidence_refs(
    report: ToleranceDecisionReport,
    parts: list[str],
) -> None:
    if not report.evidence_refs:
        return
    parts.append("<h2>Evidence References</h2>")
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        "<th>Evidence ID</th><th>Source</th>"
        "<th>Evidence Code</th><th>Reason Code</th>"
        "</tr></thead>"
    )
    parts.append("<tbody>")
    for ref in report.evidence_refs:
        parts.append(
            f"<tr>"
            f"<td>{_esc(ref.evidence_id)}</td>"
            f"<td>{_esc(ref.source)}</td>"
            f"<td>{_esc(ref.evidence_code)}</td>"
            f"<td>{_esc(ref.reason_code)}</td>"
            f"</tr>"
        )
    parts.append("</tbody>")
    parts.append("</table>")
