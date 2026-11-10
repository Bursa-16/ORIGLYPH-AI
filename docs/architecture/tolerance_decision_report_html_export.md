# Tolerance Decision Report — HTML Export (Stage 21B)

## Purpose

Stage 21B introduces a deterministic, stdlib-only HTML renderer for
`ToleranceDecisionReport` (Stage 15M).  The rendered output is a
self-contained single-file engineering report suitable for archive,
review, and customer delivery without requiring any third-party
toolchain.

## Engineering authority boundary

HTML export is a **presentation** of an already-generated
`ToleranceDecisionReport`.  It is **not** a new engineering calculation,
re-analysis, approval, certification, or governance decision.

The renderer never calls `run_decision_report()`, `evaluate_decision()`,
or any engineering engine.  It only formats the report's existing fields
into HTML.

## Determinism contract

Identical `ToleranceDecisionReport` input always produces byte-identical
HTML output.  The renderer guarantees:

- No timestamps or wall-clock values
- No UUIDs or random identifiers
- No machine names, usernames, or environment paths
- No session-specific state
- No external CDN, stylesheet, font, image, or script references

`DecisionProvenance` is intentionally excluded from the rendered output
because its fields (`generation_timestamp`, `audit_id`, `generated_by`)
are environment-specific and are excluded from the deterministic report
identity per the Stage 15M contract.

## Module structure

```
src/origlyph/tolerance/html_export.py
```

### Public API

| Symbol | Description |
|--------|-------------|
| `render_decision_report_html(report)` | Render to an in-memory HTML string |
| `write_decision_report_html(report, path)` | Render and write to a file; returns resolved `Path` |
| `DecisionReportHtmlExportError` | Raised on invalid input or file I/O failure |

Both public functions validate that `report` is a `ToleranceDecisionReport`
instance and raise `DecisionReportHtmlExportError` otherwise.

### Internal structure

The renderer uses a `list[str]` accumulator pattern for efficient string
assembly.  Output is produced by calling `"\n".join(parts)` once at the
end of `_render()`.

Internal helper functions are intentionally separated by concern to keep
cyclomatic complexity below the ruff C901 threshold:

| Helper | Responsibility |
|--------|---------------|
| `_render_head` | HTML document shell, `<head>`, title, metadata row |
| `_render_summary` | Decision status badge, completeness, summary text/code |
| `_render_reason_codes` | Governing / marginal / supporting reason code table |
| `_render_triggered_reasons` | Triggered reason ref table with severity and detail |
| `_render_contributors` | Contributor name / type / value / sigma table |
| `_render_all_metrics` | Iterates `_METRICS_SECTIONS` and renders each non-empty section |
| `_render_metrics_table` | Generic key / value / bounds table |
| `_render_evidence_refs` | Evidence reference table |
| `_render_footer` | Footer disclaimer and closing HTML tags |

### HTML escaping

All user-derived text is passed through `html.escape(str(value), quote=True)`
before insertion into the output.  This covers: chain names, contributor
names, reason detail text, evidence IDs, evidence source strings, metric
keys, and any enum `.value` strings.

### Self-contained output

The renderer embeds all styles in a `<style>` tag within `<head>`.  No
external stylesheets, fonts, scripts, or CDN references are present.  The
file is a valid, standalone HTML5 document.

## Workspace integration

### Controller (`workspace_controller.py`)

`ToleranceWorkspaceController.export_html_report(path)`:

- Requires `self._last_decision_report` to be non-None (i.e.
  `run_decision_report()` must have been called since the last state
  mutation).
- Raises `InvalidToleranceWorkspaceError` if no report is cached.
- Delegates to `write_decision_report_html` via a lazy local import.
- Does **not** mutate workspace state, project identity, or any
  engineering cache.
- Accepts `str | Path`; returns the resolved `Path` of the written file.

### Session (`workspace_model.py — WorkspaceSession`)

`WorkspaceSession.html_report_available` — boolean property; `True` when
the controller has a cached decision report.

`WorkspaceSession.export_html_report(path)` — delegates to the controller.

### View (`workspace_model.py — ToleranceWorkspaceView`)

An "Export HTML Report" button is added to the Decision Report labelframe
at `row=3`.  The button handler follows the existing `_guard()` pattern:

```
_export_html_report()  →  _guard(lambda: _export_html_report_impl())
```

`_export_html_report_impl()` opens a save-file dialog
(`asksaveasfilename`) with `.html` as the default extension and
`origlyph_decision_report.html` as the default filename, then calls
`self._session.export_html_report(path)` and shows an info dialog on
success.

## Tests

| File | Coverage |
|------|---------|
| `tests/unit/tolerance/test_html_export.py` | Renderer unit tests: type validation, output contract, determinism, no non-deterministic content, no external resources, status rendering, contributor/metric/reason/evidence rendering, HTML escaping, file writer, sigma multiplier, footer |
| `tests/unit/tolerance/test_workspace_html_export.py` | Workspace integration tests: controller `export_html_report` (happy path, error path, determinism, state reset), session `html_report_available` and `export_html_report` |

## Invariants

1. `render_decision_report_html` and `write_decision_report_html` have no
   side effects on the report object.
2. The rendered HTML contains no `<script>` tags, no `<link>` tags, and
   no `http://` or `https://` URLs.
3. `export_html_report` on the controller raises
   `InvalidToleranceWorkspaceError` when `last_decision_report is None`;
   it never calls `run_decision_report()` implicitly.
4. The file writer creates intermediate directories via `mkdir(parents=True,
   exist_ok=True)` before writing.
5. All file writes use `encoding="utf-8", newline="\n"` for cross-platform
   reproducibility.
