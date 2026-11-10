"""Unit tests for deterministic governance chain HTML export (Stage 21D)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.governance_html_export import (
    GovernanceHtmlExportError,
    render_governance_chain_html,
    write_governance_chain_html,
)
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceSpecification,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_complete_chain() -> ToleranceWorkspaceController:
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
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            fp=f,
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="AUTH-REF-001",
            decision_reference="DEC-REF-001",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


def _chain_kwargs(ctrl: ToleranceWorkspaceController) -> dict:
    return {
        "comparison": ctrl.last_audit_comparison,
        "change_impact": ctrl.last_change_impact,
        "disposition": ctrl.last_change_disposition,
        "approval_readiness": ctrl.last_approval_readiness,
        "acceptance_handoff": ctrl.last_acceptance_handoff,
        "acceptance_record": ctrl.last_acceptance_record,
        "acceptance_verification": ctrl.last_acceptance_verification,
        "acceptance_closure": ctrl.last_acceptance_closure,
    }


def _make_injection_ctrl() -> ToleranceWorkspaceController:
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
    pkg = ctrl.last_audit_package
    assert pkg is not None
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            fp=f,
        )
        tmp_path = f.name
    ctrl.load_comparison_audit_package(tmp_path)
    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="<script>alert(1)</script>",
            decision_reference="</td></table><img src=x onerror=alert(1)>",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


def test_render_requires_comparison() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["comparison"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="comparison"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_change_impact() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["change_impact"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="change_impact"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_disposition() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["disposition"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="disposition"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_approval_readiness() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["approval_readiness"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="approval_readiness"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_acceptance_handoff() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["acceptance_handoff"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="acceptance_handoff"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_acceptance_record() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["acceptance_record"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="acceptance_record"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_acceptance_verification() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["acceptance_verification"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="acceptance_verification"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


def test_render_requires_acceptance_closure() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    kwargs["acceptance_closure"] = object()
    with pytest.raises(GovernanceHtmlExportError, match="acceptance_closure"):
        render_governance_chain_html(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def test_render_returns_string() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert isinstance(result, str)


def test_render_contains_doctype() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<!DOCTYPE html>" in result


def test_render_contains_html_root() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<html" in result
    assert "</html>" in result


def test_render_contains_head() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<head>" in result
    assert "</head>" in result


def test_render_contains_body() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<body>" in result
    assert "</body>" in result


def test_render_contains_charset() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert 'charset="UTF-8"' in result


def test_render_contains_viewport() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "viewport" in result


def test_render_non_empty() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert len(result) > 1000


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_deterministic() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    first = render_governance_chain_html(**kwargs)
    second = render_governance_chain_html(**kwargs)
    assert first == second


def test_render_byte_identical() -> None:
    ctrl = _make_complete_chain()
    kwargs = _chain_kwargs(ctrl)
    a = render_governance_chain_html(**kwargs).encode("utf-8")
    b = render_governance_chain_html(**kwargs).encode("utf-8")
    assert a == b


def test_render_utf8_encodable() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    result.encode("utf-8")


# ---------------------------------------------------------------------------
# Section presence
# ---------------------------------------------------------------------------


def test_render_contains_governance_summary() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Governance Chain Summary" in result


def test_render_contains_audit_comparison() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Audit Comparison" in result


def test_render_contains_change_impact() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Change Impact" in result


def test_render_contains_change_disposition() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Change Disposition" in result


def test_render_contains_approval_readiness() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Approval Readiness" in result


def test_render_contains_acceptance_handoff() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Acceptance Handoff" in result


def test_render_contains_acceptance_record() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Acceptance Record" in result


def test_render_contains_acceptance_verification() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Acceptance Verification" in result


def test_render_contains_acceptance_closure() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Acceptance Closure" in result


def test_render_contains_traceability() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Traceability" in result


# ---------------------------------------------------------------------------
# Identifier fidelity
# ---------------------------------------------------------------------------


def test_render_contains_handoff_id() -> None:
    ctrl = _make_complete_chain()
    handoff = ctrl.last_acceptance_handoff
    assert handoff is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert handoff.handoff_id in result


def test_render_contains_acceptance_record_id() -> None:
    ctrl = _make_complete_chain()
    record = ctrl.last_acceptance_record
    assert record is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert record.acceptance_record_id in result


def test_render_contains_envelope_id() -> None:
    ctrl = _make_complete_chain()
    verification = ctrl.last_acceptance_verification
    assert verification is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert verification.envelope_id in result


def test_render_contains_closure_id() -> None:
    ctrl = _make_complete_chain()
    closure = ctrl.last_acceptance_closure
    assert closure is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert closure.closure_id in result


def test_render_contains_baseline_package_id() -> None:
    ctrl = _make_complete_chain()
    comparison = ctrl.last_audit_comparison
    assert comparison is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert comparison.baseline_package_id in result


def test_render_contains_candidate_package_id() -> None:
    ctrl = _make_complete_chain()
    comparison = ctrl.last_audit_comparison
    assert comparison is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert comparison.candidate_package_id in result


def test_render_full_fingerprints_not_truncated() -> None:
    ctrl = _make_complete_chain()
    handoff = ctrl.last_acceptance_handoff
    assert handoff is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert len(handoff.handoff_id) == 64
    assert handoff.handoff_id in result


def test_render_contains_authority_reference() -> None:
    ctrl = _make_complete_chain()
    record = ctrl.last_acceptance_record
    assert record is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert record.authority_reference in result


def test_render_contains_decision_reference() -> None:
    ctrl = _make_complete_chain()
    record = ctrl.last_acceptance_record
    assert record is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert record.decision_reference in result


def test_render_contains_decision_value() -> None:
    ctrl = _make_complete_chain()
    record = ctrl.last_acceptance_record
    assert record is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert record.decision.value in result


def test_render_contains_verification_facts() -> None:
    ctrl = _make_complete_chain()
    verification = ctrl.last_acceptance_verification
    assert verification is not None
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    for fact in verification.verification_facts:
        assert fact.value in result


def test_render_contains_closure_references() -> None:
    ctrl = _make_complete_chain()
    closure = ctrl.last_acceptance_closure
    assert closure is not None
    refs = closure.references
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert refs.handoff_id in result
    assert refs.acceptance_record_id in result
    assert refs.envelope_id in result


# ---------------------------------------------------------------------------
# HTML escaping / injection protection
# ---------------------------------------------------------------------------


def test_render_escapes_script_in_authority_reference() -> None:
    ctrl = _make_injection_ctrl()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_render_escapes_img_in_decision_reference() -> None:
    ctrl = _make_injection_ctrl()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<img" not in result
    assert "&lt;" in result


def test_render_no_raw_injection_tags() -> None:
    ctrl = _make_injection_ctrl()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<img" not in result


# ---------------------------------------------------------------------------
# No non-deterministic content
# ---------------------------------------------------------------------------


def test_render_no_datetime_import() -> None:
    import sys

    import origlyph.tolerance.governance_html_export as mod

    assert "datetime" not in sys.modules.get(
        "origlyph.tolerance.governance_html_export", type(sys)
    ).__dict__
    assert not hasattr(mod, "datetime")


def test_render_no_uuid_import() -> None:
    import origlyph.tolerance.governance_html_export as mod

    assert not hasattr(mod, "uuid")


def test_render_no_random_import() -> None:
    import origlyph.tolerance.governance_html_export as mod

    assert not hasattr(mod, "random")


# ---------------------------------------------------------------------------
# Self-contained / offline
# ---------------------------------------------------------------------------


def test_render_no_external_http() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "http://" not in result
    assert "https://" not in result


def test_render_no_cdn() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "cdn" not in result.lower()


def test_render_no_script_src() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<script src" not in result
    assert "<script>" not in result


def test_render_no_link_href() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<link" not in result


def test_render_has_inline_style() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "<style>" in result


# ---------------------------------------------------------------------------
# Semantic safety / governance notice
# ---------------------------------------------------------------------------


def test_render_contains_governance_notice() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Governance Notice" in result


def test_render_governance_notice_text() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Approval readiness is not approval" in result


def test_render_governance_notice_no_certification_claim() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "regulatory certification" in result.lower()
    assert "not constitute" in result or "do not constitute" in result


def test_render_no_certified_label() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Certified\n" not in result
    assert ">Certified<" not in result


def test_render_no_digitally_signed_label() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "Digitally Signed" not in result


def test_render_approval_readiness_disclaimer() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "not an approval decision" in result or "not approval" in result


def test_render_authority_reference_disclaimer() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "governance reference" in result


def test_render_footer_disclaimer() -> None:
    ctrl = _make_complete_chain()
    result = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert "does not calculate, approve, authenticate" in result


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def test_writer_creates_file(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "governance.html"
    write_governance_chain_html(**_chain_kwargs(ctrl), path=out)
    assert out.exists()


def test_writer_returns_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "governance.html"
    result = write_governance_chain_html(**_chain_kwargs(ctrl), path=out)
    assert isinstance(result, Path)
    assert result == out


def test_writer_content_matches_renderer(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "governance.html"
    write_governance_chain_html(**_chain_kwargs(ctrl), path=out)
    written = out.read_text(encoding="utf-8")
    rendered = render_governance_chain_html(**_chain_kwargs(ctrl))
    assert written.replace("\r\n", "\n") == rendered.replace("\r\n", "\n")


def test_writer_repeated_identical(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out1 = tmp_path / "a.html"
    out2 = tmp_path / "b.html"
    write_governance_chain_html(**_chain_kwargs(ctrl), path=out1)
    write_governance_chain_html(**_chain_kwargs(ctrl), path=out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_writer_accepts_str_path(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "governance.html"
    write_governance_chain_html(**_chain_kwargs(ctrl), path=str(out))
    assert out.exists()


def test_writer_creates_parent_dirs(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    out = tmp_path / "nested" / "deep" / "governance.html"
    write_governance_chain_html(**_chain_kwargs(ctrl), path=out)
    assert out.exists()


def test_writer_invalid_path_raises(tmp_path: Path) -> None:
    ctrl = _make_complete_chain()
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(GovernanceHtmlExportError):
        write_governance_chain_html(
            **_chain_kwargs(ctrl), path=blocker / "nested" / "governance.html"
        )


# ---------------------------------------------------------------------------
# Source objects unchanged after render
# ---------------------------------------------------------------------------


def test_comparison_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_audit_comparison
    render_governance_chain_html(**_chain_kwargs(ctrl))
    assert ctrl.last_audit_comparison is before


def test_closure_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    before = ctrl.last_acceptance_closure
    render_governance_chain_html(**_chain_kwargs(ctrl))
    assert ctrl.last_acceptance_closure is before


def test_all_chain_objects_unchanged_after_render() -> None:
    ctrl = _make_complete_chain()
    before = _chain_kwargs(ctrl)
    render_governance_chain_html(**_chain_kwargs(ctrl))
    after = _chain_kwargs(ctrl)
    for key in before:
        assert before[key] is after[key]
