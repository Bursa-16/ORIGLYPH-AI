"""Tests for the Stage 21C audit package HTML export renderer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from origlyph.tolerance import (
    AuditPackageHtmlExportError,
    DecisionProvenance,
    render_audit_package_html,
    write_audit_package_html,
)
from origlyph.tolerance.audit import (
    ToleranceDecisionAuditPackage,
    build_decision_audit_package,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    ToleranceWorkspaceController,
    WorkspaceSpecification,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_package() -> ToleranceDecisionAuditPackage:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.5,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    ctrl.run_audit_package()
    package = ctrl.last_audit_package
    assert package is not None
    return package


def _make_package_with_injection_provenance() -> ToleranceDecisionAuditPackage:
    ctrl = ToleranceWorkspaceController(
        chain_name="Test chain",
        analysis_mode=AnalysisMode.WORST_CASE,
    )
    ctrl.add_contributor(
        identifier="A",
        name="Part A",
        nominal=0.0,
        tolerance=0.5,
        direction="forward",
        tolerance_model="symmetric",
    )
    ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=2.0))
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    report = ctrl.last_decision_report
    assert report is not None
    provenance = DecisionProvenance(
        generated_by="<script>alert(1)</script>",
        generation_timestamp='</td></table><img src=x onerror=alert(1)>',
        audit_id="audit-id-with-<-and->",
        metadata={"key<x>": "value&amp;"},
    )
    package = build_decision_audit_package(report, provenance=provenance)
    return package


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


def test_render_wrong_type_raises() -> None:
    with pytest.raises(AuditPackageHtmlExportError, match="ToleranceDecision"):
        render_audit_package_html("not a package")  # type: ignore[arg-type]


def test_render_none_raises() -> None:
    with pytest.raises(AuditPackageHtmlExportError):
        render_audit_package_html(None)  # type: ignore[arg-type]


def test_write_wrong_type_raises(tmp_path: Path) -> None:
    with pytest.raises(AuditPackageHtmlExportError):
        write_audit_package_html(42, tmp_path / "out.html")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Minimal valid package
# ---------------------------------------------------------------------------


def test_render_minimal_valid() -> None:
    pkg = _make_package()
    result = render_audit_package_html(pkg)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_deterministic() -> None:
    pkg = _make_package()
    assert render_audit_package_html(pkg) == render_audit_package_html(pkg)


def test_render_byte_identical() -> None:
    pkg = _make_package()
    b1 = render_audit_package_html(pkg).encode("utf-8")
    b2 = render_audit_package_html(pkg).encode("utf-8")
    assert b1 == b2


def test_write_byte_identical(tmp_path: Path) -> None:
    pkg = _make_package()
    out1 = tmp_path / "a.html"
    out2 = tmp_path / "b.html"
    write_audit_package_html(pkg, out1)
    write_audit_package_html(pkg, out2)
    assert out1.read_bytes() == out2.read_bytes()


# ---------------------------------------------------------------------------
# UTF-8
# ---------------------------------------------------------------------------


def test_write_utf8_encoding(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "out.html"
    write_audit_package_html(pkg, out)
    out.read_text(encoding="utf-8")  # must not raise


# ---------------------------------------------------------------------------
# HTML document structure
# ---------------------------------------------------------------------------


def test_doctype_present() -> None:
    html = render_audit_package_html(_make_package())
    assert "<!DOCTYPE html>" in html


def test_html_lang_en() -> None:
    html = render_audit_package_html(_make_package())
    assert '<html lang="en">' in html


def test_charset_meta() -> None:
    html = render_audit_package_html(_make_package())
    assert 'charset="UTF-8"' in html


def test_title_present() -> None:
    html = render_audit_package_html(_make_package())
    assert "<title>Origlyph Audit Package</title>" in html


def test_body_tag_present() -> None:
    html = render_audit_package_html(_make_package())
    assert "<body>" in html and "</body>" in html


def test_closing_html_tag() -> None:
    html = render_audit_package_html(_make_package())
    assert html.strip().endswith("</html>")


# ---------------------------------------------------------------------------
# Package identity
# ---------------------------------------------------------------------------


def test_package_id_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.package_id in html


def test_package_id_full_length() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert len(pkg.package_id) == 64
    assert pkg.package_id in html


def test_audit_schema_version_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.audit_schema_version in html


def test_replayability_status_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replayability_status.value in html


# ---------------------------------------------------------------------------
# Report fingerprint in binding section
# ---------------------------------------------------------------------------


def test_report_fingerprint_in_binding() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.report_fingerprint in html


# ---------------------------------------------------------------------------
# Fingerprint fidelity (full 64-char SHA-256 values)
# ---------------------------------------------------------------------------


def test_input_fingerprint_full() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.input_fingerprint in html


def test_report_fingerprint_full() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.report_fingerprint in html


def test_integrity_fingerprint_full() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.integrity_fingerprint in html


def test_fingerprints_not_truncated() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    for fp in (
        pkg.replay_manifest.input_fingerprint,
        pkg.replay_manifest.report_fingerprint,
        pkg.replay_manifest.integrity_fingerprint,
        pkg.package_id,
    ):
        assert len(fp) == 64
        assert fp in html


# ---------------------------------------------------------------------------
# Replay manifest fields
# ---------------------------------------------------------------------------


def test_manifest_package_id_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.package_id in html


def test_manifest_equality_tolerance_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert str(pkg.replay_manifest.equality_tolerance) in html


def test_manifest_policy_identifiers_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    for policy in pkg.replay_manifest.policy_identifiers:
        assert policy in html


def test_manifest_integrity_status_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.integrity_status.value in html


def test_manifest_sigma_multiplier_absent_for_worst_case() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.replay_manifest.sigma_multiplier is None
    assert "Sigma Multiplier" not in html


# ---------------------------------------------------------------------------
# Decision report binding
# ---------------------------------------------------------------------------


def test_report_schema_version_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.report.schema_version in html


def test_report_final_status_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.report.final_status.value in html


# ---------------------------------------------------------------------------
# Integrity summary
# ---------------------------------------------------------------------------


def test_integrity_status_present() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert pkg.integrity_result.status.value in html


def test_no_violations_text_when_clean() -> None:
    pkg = _make_package()
    if not pkg.integrity_result.violations:
        html = render_audit_package_html(pkg)
        assert "No integrity violations" in html


# ---------------------------------------------------------------------------
# Status fidelity
# ---------------------------------------------------------------------------


def test_replayable_status_badge() -> None:
    pkg = _make_package()
    html = render_audit_package_html(pkg)
    assert "REPLAYABLE" in html or "replayable" in html


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def test_html_escaping_lt() -> None:
    pkg = _make_package_with_injection_provenance()
    html = render_audit_package_html(pkg)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_escaping_gt() -> None:
    pkg = _make_package_with_injection_provenance()
    html = render_audit_package_html(pkg)
    assert "&gt;" in html


def test_html_escaping_amp() -> None:
    pkg = _make_package_with_injection_provenance()
    html_str = render_audit_package_html(pkg)
    assert "&amp;" in html_str


def test_script_injection_blocked() -> None:
    pkg = _make_package_with_injection_provenance()
    html = render_audit_package_html(pkg)
    assert "<script>alert(1)</script>" not in html


def test_tag_injection_blocked() -> None:
    pkg = _make_package_with_injection_provenance()
    html = render_audit_package_html(pkg)
    assert "</td></table><img src=x onerror=alert(1)>" not in html


# ---------------------------------------------------------------------------
# Non-deterministic content absent
# ---------------------------------------------------------------------------


def test_no_datetime_now() -> None:
    html = render_audit_package_html(_make_package())
    assert "datetime.now" not in html
    assert "utcnow" not in html


def test_no_uuid_pattern() -> None:
    html = render_audit_package_html(_make_package())
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    assert not uuid_pattern.search(html)


def test_no_time_import_artifacts() -> None:
    html = render_audit_package_html(_make_package())
    assert "time.time" not in html


# ---------------------------------------------------------------------------
# No hostname / username / local path
# ---------------------------------------------------------------------------


def test_no_hostname_in_output() -> None:
    import socket
    try:
        hostname = socket.gethostname()
    except Exception:
        return
    html = render_audit_package_html(_make_package())
    assert hostname not in html


def test_no_username_in_output() -> None:
    import getpass
    try:
        user = getpass.getuser()
    except Exception:
        return
    html = render_audit_package_html(_make_package())
    assert user not in html


def test_no_local_path_leak(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "out.html"
    write_audit_package_html(pkg, out)
    content = out.read_text(encoding="utf-8")
    assert str(tmp_path) not in content


# ---------------------------------------------------------------------------
# No external resources
# ---------------------------------------------------------------------------


def test_no_http_link() -> None:
    html = render_audit_package_html(_make_package())
    assert "http://" not in html
    assert "https://" not in html


def test_no_cdn_reference() -> None:
    html = render_audit_package_html(_make_package())
    assert "cdn" not in html.lower()


def test_no_script_src() -> None:
    html = render_audit_package_html(_make_package())
    assert "<script src" not in html.lower()


def test_no_link_href() -> None:
    html = render_audit_package_html(_make_package())
    assert "<link href" not in html.lower()


def test_no_external_font() -> None:
    html = render_audit_package_html(_make_package())
    assert "@import" not in html


# ---------------------------------------------------------------------------
# No JS dependency — works offline
# ---------------------------------------------------------------------------


def test_no_script_tags() -> None:
    html = render_audit_package_html(_make_package())
    assert "<script>" not in html
    assert "<script " not in html


def test_offline_readable() -> None:
    html = render_audit_package_html(_make_package())
    assert "<style>" in html
    assert "file://" not in html


# ---------------------------------------------------------------------------
# Security / governance notice
# ---------------------------------------------------------------------------


def test_governance_notice_present() -> None:
    html = render_audit_package_html(_make_package())
    assert "deterministic engineering governance artifact" in html


def test_no_certified_label() -> None:
    html = render_audit_package_html(_make_package()).lower()
    forbidden = ["certified", "digitally signed", "authenticated user",
                 "regulatory approved", "authorized release", "compliance certified"]
    for label in forbidden:
        assert label not in html


def test_security_notice_no_digital_signatures() -> None:
    html = render_audit_package_html(_make_package())
    assert "digital signatures" in html


def test_footer_disclaimer_present() -> None:
    html = render_audit_package_html(_make_package())
    assert "does not build, verify, approve, certify" in html


# ---------------------------------------------------------------------------
# Write / read fidelity
# ---------------------------------------------------------------------------


def test_write_creates_file(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "audit.html"
    result = write_audit_package_html(pkg, out)
    assert result == out
    assert out.exists()


def test_write_returns_path(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "audit.html"
    result = write_audit_package_html(pkg, out)
    assert isinstance(result, Path)


def test_write_content_matches_render(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "audit.html"
    write_audit_package_html(pkg, out)
    rendered = render_audit_package_html(pkg)
    written = out.read_text(encoding="utf-8")
    assert rendered.replace("\r\n", "\n") == written.replace("\r\n", "\n")


def test_write_accepts_str_path(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "audit.html"
    write_audit_package_html(pkg, str(out))
    assert out.exists()


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "nested" / "deep" / "audit.html"
    write_audit_package_html(pkg, out)
    assert out.exists()


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_write_invalid_path_raises(tmp_path: Path) -> None:
    pkg = _make_package()
    # Write a regular file, then try to write inside it as a directory
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(AuditPackageHtmlExportError, match="could not be written"):
        write_audit_package_html(pkg, blocker / "nested" / "audit.html")


def test_write_permission_error_wrapped(tmp_path: Path) -> None:
    pkg = _make_package()
    out = tmp_path / "audit.html"
    out.write_text("x", encoding="utf-8")
    out.chmod(0o444)
    try:
        with pytest.raises(AuditPackageHtmlExportError):
            write_audit_package_html(pkg, out)
    finally:
        out.chmod(0o644)


# ---------------------------------------------------------------------------
# Source package unchanged after render
# ---------------------------------------------------------------------------


def test_source_package_unchanged_after_render() -> None:
    pkg = _make_package()
    pkg_id_before = pkg.package_id
    replay_before = pkg.replay_manifest
    render_audit_package_html(pkg)
    assert pkg.package_id == pkg_id_before
    assert pkg.replay_manifest is replay_before


def test_package_id_unchanged_after_write(tmp_path: Path) -> None:
    pkg = _make_package()
    pkg_id_before = pkg.package_id
    write_audit_package_html(pkg, tmp_path / "audit.html")
    assert pkg.package_id == pkg_id_before


def test_fingerprints_unchanged_after_render() -> None:
    pkg = _make_package()
    before = {
        "input": pkg.replay_manifest.input_fingerprint,
        "report": pkg.replay_manifest.report_fingerprint,
        "integrity": pkg.replay_manifest.integrity_fingerprint,
    }
    render_audit_package_html(pkg)
    assert pkg.replay_manifest.input_fingerprint == before["input"]
    assert pkg.replay_manifest.report_fingerprint == before["report"]
    assert pkg.replay_manifest.integrity_fingerprint == before["integrity"]
