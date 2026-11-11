"""Stage 22B: CAD → Datum → Tolerance End-to-End Pipeline Integration Tests.

Covers seams (a)–(h) from the Stage 22B specification without touching any
existing source or test file.  All STL fixtures are embedded bytes; no
external CAD files are needed.

Seam map
--------
(a) STL bytes → NeutralModel entity count
(b) NeutralModel → CandidateResult counts
(c) CandidateResult → DRF construction
(d) DRF → workspace initialization (contributors use entity_id)
(e) analysis → decision determinism
(f) governance chain completion → unified HTML flag
(g) project save → reopen continuity (project_id stable)
(h) reopen → governance restore → workspace state recovery
"""
from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path
from typing import Sequence

import pytest

from origlyph.cad import (
    CadFormat,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceUnitSystem,
    StlImporter,
    bind_datum_reference_frame,
    bind_references,
)
from origlyph.cad.bridge import CandidateResult, extract_candidates
from origlyph.datum import ConstraintType, FeatureKind
from origlyph.project.persistence import load_project
from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.models import ToleranceDecisionResult
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceAnalysisResult,
    WorkspaceSpecification,
)

# ---------------------------------------------------------------------------
# Embedded STL helpers – no filesystem I/O beyond tmp_path fixture
# ---------------------------------------------------------------------------

def _facet_text(v1: str, v2: str, v3: str) -> str:
    return (
        "facet normal 0 0 1\n"
        f" outer loop\n  vertex {v1}\n  vertex {v2}\n  vertex {v3}\n"
        " endloop\nendfacet\n"
    )


def _ascii_stl(*facets: str) -> bytes:
    body = "".join(facets)
    return f"solid e2e\n{body}endsolid e2e\n".encode("ascii")


def _binary_facet(
    vertices: tuple[str, str, str],
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> bytes:
    floats = list(normal)
    for v in vertices:
        floats.extend(float(x) for x in v.split())
    return struct.pack(f"<{len(floats)}f", *floats) + struct.pack("<H", 0)


def _binary_stl(*facets: bytes) -> bytes:
    header = b"e2e".ljust(80, b"\x00")
    return header + struct.pack("<I", len(facets)) + b"".join(facets)


_V_A = ("0 0 0", "1 0 0", "0 1 0")
_V_B = ("2 0 0", "3 0 0", "2 1 0")
_V_C = ("5 0 0", "6 0 0", "5 1 0")


def _three_face_ascii() -> bytes:
    return _ascii_stl(
        _facet_text(*_V_A),
        _facet_text(*_V_B),
        _facet_text(*_V_C),
    )


def _three_face_binary() -> bytes:
    return _binary_stl(
        _binary_facet(_V_A),
        _binary_facet(_V_B),
        _binary_facet(_V_C),
    )


def _one_face_ascii() -> bytes:
    return _ascii_stl(_facet_text(*_V_A))


def _make_source_id(stl_bytes: bytes, name: str = "e2e-part") -> SourceDocumentIdentity:
    fp = hashlib.sha256(stl_bytes).hexdigest()
    return SourceDocumentIdentity(
        source_id=name,
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit="mm"),
        original_filename=f"{name}.stl",
        fingerprint=fp,
    )


def _import(stl_bytes: bytes, name: str = "e2e-part"):
    source_id = _make_source_id(stl_bytes, name)
    importer = StlImporter(bytes_loader=lambda _: stl_bytes)
    return importer.import_document(source_id), source_id


def _make_controller(
    entity_ids: Sequence[str],
    *,
    chain_name: str = "e2e-chain",
    analysis_mode: AnalysisMode | str = AnalysisMode.WORST_CASE,
    allowed_wc_span: float = 2.0,
    nominal: float = 10.0,
    tolerance: float = 0.1,
    direction: str = "forward",
) -> ToleranceWorkspaceController:
    ctrl = ToleranceWorkspaceController(
        chain_name=chain_name,
        analysis_mode=analysis_mode,
        specification=WorkspaceSpecification(allowed_worst_case_span=allowed_wc_span),
    )
    for idx, eid in enumerate(entity_ids):
        ctrl.add_contributor(
            identifier=eid,
            name=f"dim-{idx}",
            nominal=nominal,
            tolerance=tolerance,
            direction=direction,
            tolerance_model="symmetric",
        )
    return ctrl


def _run_full_governance_chain(
    ctrl: ToleranceWorkspaceController,
) -> ToleranceWorkspaceController:
    """Run the complete 16-step governance chain, returning ctrl.

    run_audit_comparison() requires both a current audit package AND a loaded
    comparison package (a previous baseline saved to JSON). We produce the
    comparison package by running a preliminary audit on an identical controller
    and writing the resulting package JSON to a temp file, then loading it as
    the comparison baseline before running the actual comparison.
    """
    ctrl.run_analysis()
    ctrl.evaluate_decision()
    ctrl.run_decision_evidence()
    ctrl.run_decision_report()
    ctrl.run_audit_integrity()
    ctrl.run_audit_package()

    # Build a comparison baseline: same state → same content, so comparison
    # yields a MATCH result without divergence noise.
    comparison_package = ctrl.last_audit_package
    assert comparison_package is not None
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(comparison_package.to_json())
        tmp_path_str = tmp.name
    ctrl.load_comparison_audit_package(tmp_path_str)

    ctrl.run_audit_comparison()
    ctrl.run_change_impact()
    ctrl.run_change_disposition()
    ctrl.run_approval_readiness()
    handoff = ctrl.run_acceptance_handoff()
    ctrl.set_acceptance_state(
        WorkspaceAcceptanceState(
            decision=AuditAcceptanceDecision.APPROVED,
            authority_reference="DR-TEST-AUTHORITY-E2E-001",
            decision_reference="DR-TEST-DECISION-E2E-001",
            handoff_id=handoff.handoff_id,
        )
    )
    ctrl.run_acceptance_record()
    ctrl.run_acceptance_verification()
    ctrl.run_acceptance_closure()
    return ctrl


# ---------------------------------------------------------------------------
# Module-scoped immutable fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _three_ascii_bytes() -> bytes:
    return _three_face_ascii()


@pytest.fixture(scope="module")
def _three_binary_bytes() -> bytes:
    return _three_face_binary()


@pytest.fixture(scope="module")
def _model_and_source(_three_ascii_bytes):
    return _import(_three_ascii_bytes)


@pytest.fixture(scope="module")
def _model(_model_and_source):
    return _model_and_source[0]


@pytest.fixture(scope="module")
def _source_id(_model_and_source):
    return _model_and_source[1]


@pytest.fixture(scope="module")
def _candidates(_model) -> CandidateResult:
    return extract_candidates(_model)


@pytest.fixture(scope="module")
def _bound_refs(_candidates):
    return bind_references(_candidates.candidates)


@pytest.fixture(scope="module")
def _entity_ids(_bound_refs) -> list[str]:
    return [b.entity_id for b in _bound_refs]


@pytest.fixture(scope="module")
def _drf(_bound_refs):
    return bind_datum_reference_frame(
        "e2e-frame",
        [
            (_bound_refs[0], ConstraintType.PRIMARY),
            (_bound_refs[1], ConstraintType.SECONDARY),
            (_bound_refs[2], ConstraintType.TERTIARY),
        ],
    )


# ---------------------------------------------------------------------------
# Seam (a): STL bytes → NeutralModel entity count
# ---------------------------------------------------------------------------

def test_a_ascii_three_faces_produce_three_entities(_model):
    """ASCII 3-facet STL → 3 PLANE entities in the neutral model."""
    assert len(_model.entities) == 3


def test_a_ascii_three_faces_no_warnings(_model):
    """ASCII 3-facet STL → 0 warnings (all triangles are valid)."""
    assert len(_model.warnings) == 0


def test_a_ascii_three_faces_no_unsupported(_model):
    """ASCII 3-facet STL → 0 unsupported entries."""
    assert len(_model.unsupported) == 0


def test_a_binary_three_faces_produce_three_entities(_three_binary_bytes):
    """Binary 3-facet STL → 3 PLANE entities (same count as ASCII)."""
    m, _ = _import(_three_binary_bytes, "e2e-binary")
    assert len(m.entities) == 3


def test_a_binary_entity_kinds_are_plane(_three_binary_bytes):
    """Binary STL entities are all PLANE kind (each facet is a planar face)."""
    m, _ = _import(_three_binary_bytes, "e2e-binary-kinds")
    for entity in m.entities:
        assert entity.identity.kind is NeutralEntityKind.PLANE


def test_a_ascii_entity_kinds_are_plane(_model):
    """ASCII STL entities are all PLANE kind."""
    for entity in _model.entities:
        assert entity.identity.kind is NeutralEntityKind.PLANE


def test_a_one_face_ascii_produces_one_entity():
    """Single-facet STL → 1 PLANE entity."""
    m, _ = _import(_one_face_ascii(), "single")
    assert len(m.entities) == 1


def test_a_fingerprint_in_source_id_is_sha256_hex(_source_id):
    """Source identity carries a 64-hex SHA-256 fingerprint."""
    fp = _source_id.fingerprint
    assert fp is not None
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_a_ascii_binary_produce_same_entity_count(
    _three_ascii_bytes, _three_binary_bytes
):
    """ASCII and binary 3-facet STL produce the same entity count."""
    m_ascii, _ = _import(_three_ascii_bytes, "ascii-cmp")
    m_binary, _ = _import(_three_binary_bytes, "binary-cmp")
    assert len(m_ascii.entities) == len(m_binary.entities)


# ---------------------------------------------------------------------------
# Seam (b): NeutralModel → CandidateResult counts
# ---------------------------------------------------------------------------

def test_b_three_entities_produce_three_candidates(_candidates):
    """3 PLANE entities → 3 bridged candidates."""
    assert len(_candidates.candidates) == 3


def test_b_zero_entities_skipped(_candidates):
    """All 3 valid planar entities pass the bridge filter."""
    assert len(_candidates.skipped) == 0


def test_b_all_candidates_have_references(_candidates):
    """Every candidate has a ReferenceSurface (PLANE kind produces one)."""
    for cand in _candidates.candidates:
        assert cand.reference is not None


def test_b_candidate_entity_ids_are_non_empty_strings(_candidates):
    """Entity IDs are non-empty strings."""
    for cand in _candidates.candidates:
        assert isinstance(cand.entity_id, str)
        assert cand.entity_id.strip()


def test_b_candidate_entity_ids_are_unique(_candidates):
    """Entity IDs are distinct across all 3 candidates."""
    ids = [c.entity_id for c in _candidates.candidates]
    assert len(set(ids)) == len(ids)


def test_b_candidate_datum_features_are_plane_kind(_candidates):
    """Datum features lifted from planar entities are FeatureKind.PLANE."""
    for cand in _candidates.candidates:
        assert cand.datum_feature.kind is FeatureKind.PLANE


def test_b_identity_chain_is_complete(_candidates):
    """identity_chain() returns non-None neutral and domain identities."""
    from origlyph.cad.bridge import identity_chain
    for cand in _candidates.candidates:
        source, neutral, domain = identity_chain(cand)
        assert neutral is not None
        assert domain is not None


def test_b_binary_stl_produces_same_candidate_count(_three_binary_bytes):
    """Binary STL also yields 3 candidates with 0 skipped."""
    m, _ = _import(_three_binary_bytes, "b-candidates")
    result = extract_candidates(m)
    assert len(result.candidates) == 3
    assert len(result.skipped) == 0


# ---------------------------------------------------------------------------
# Seam (c): CandidateResult → DRF construction
# ---------------------------------------------------------------------------

def test_c_drf_has_three_constraints(_drf):
    """Full 3-2-1 DRF has exactly 3 constraints."""
    assert len(_drf.constraints) == 3


def test_c_drf_sequences_are_ordered_1_2_3(_drf):
    """Constraints are ordered 1 → 2 → 3 (3-2-1 canonical order)."""
    sequences = [c.sequence for c in _drf.constraints]
    assert sequences == [1, 2, 3]


def test_c_drf_is_fully_located(_drf):
    """3 plane features in 3-2-1 → 6 DOF constrained → fully located."""
    assert _drf.is_fully_located is True


def test_c_drf_total_constrained_is_six(_drf):
    """total_constrained == 6 (3 translational + 3 rotational)."""
    assert _drf.total_constrained == 6


def test_c_drf_remaining_free_is_zero(_drf):
    """remaining_free == 0 for a fully located part."""
    assert _drf.remaining_free == 0


def test_c_drf_primary_constraint_type(_drf):
    """First constraint is PRIMARY."""
    assert _drf.constraints[0].constraint_type is ConstraintType.PRIMARY


def test_c_drf_secondary_constraint_type(_drf):
    """Second constraint is SECONDARY."""
    assert _drf.constraints[1].constraint_type is ConstraintType.SECONDARY


def test_c_drf_tertiary_constraint_type(_drf):
    """Third constraint is TERTIARY."""
    assert _drf.constraints[2].constraint_type is ConstraintType.TERTIARY


def test_c_drf_name_is_preserved(_drf):
    """DRF name is the name passed to bind_datum_reference_frame."""
    assert _drf.name == "e2e-frame"


def test_c_drf_entity_ids_match_candidates(_drf, _candidates):
    """DRF datum-feature entity_ids map back to bridge entity_ids."""
    candidate_ids = {c.entity_id for c in _candidates.candidates}
    drf_ids = {c.datum_feature.entity_id for c in _drf.constraints}
    assert drf_ids == candidate_ids


# ---------------------------------------------------------------------------
# Seam (d): DRF + workspace initialization — contributors use entity_ids
# ---------------------------------------------------------------------------

def test_d_contributor_identifiers_match_entity_ids(_entity_ids):
    """WorkspaceContributor identifiers are the bridge entity_ids verbatim."""
    ctrl = _make_controller(_entity_ids)
    ctrl_ids = {c.identifier for c in ctrl.contributors}
    assert ctrl_ids == set(_entity_ids)


def test_d_workspace_has_correct_contributor_count(_entity_ids):
    """Workspace contributor count equals candidate count (3)."""
    ctrl = _make_controller(_entity_ids)
    assert len(ctrl.contributors) == 3


def test_d_workspace_chain_name_is_set(_entity_ids):
    """chain_name is stored verbatim in workspace state."""
    ctrl = _make_controller(_entity_ids, chain_name="seam-d-chain")
    assert ctrl.state.chain_name == "seam-d-chain"


def test_d_workspace_analysis_mode_worst_case(_entity_ids):
    """Default analysis mode is WORST_CASE."""
    ctrl = _make_controller(_entity_ids)
    assert ctrl.state.analysis_mode is AnalysisMode.WORST_CASE


def test_d_workspace_analysis_mode_rss(_entity_ids):
    """RSS analysis mode is accepted."""
    ctrl = ToleranceWorkspaceController(
        chain_name="rss-chain",
        analysis_mode=AnalysisMode.RSS_STATISTICAL,
    )
    for eid in _entity_ids:
        ctrl.add_contributor(
            identifier=eid,
            name="dim",
            nominal=10.0,
            tolerance=0.1,
            direction="forward",
            tolerance_model="symmetric",
        )
    assert ctrl.state.analysis_mode is AnalysisMode.RSS_STATISTICAL


def test_d_contributor_nominal_is_stored(_entity_ids):
    """Contributor nominals are stored as supplied."""
    ctrl = _make_controller(_entity_ids, nominal=25.0)
    for contrib in ctrl.contributors:
        assert contrib.nominal == 25.0


def test_d_contributor_tolerance_is_stored(_entity_ids):
    """Contributor tolerances are stored as supplied."""
    ctrl = _make_controller(_entity_ids, tolerance=0.05)
    for contrib in ctrl.contributors:
        assert contrib.tolerance == 0.05


def test_d_configuration_fingerprint_is_sha256_hex(_entity_ids):
    """configuration_fingerprint() returns a 64-hex SHA-256 string."""
    ctrl = _make_controller(_entity_ids)
    fp = ctrl.configuration_fingerprint()
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_d_duplicate_entity_id_raises(_entity_ids):
    """Duplicate contributor identifier raises InvalidToleranceWorkspaceError."""
    ctrl = _make_controller(_entity_ids)
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.add_contributor(
            identifier=_entity_ids[0],
            name="duplicate",
            nominal=1.0,
            tolerance=0.01,
            direction="forward",
            tolerance_model="symmetric",
        )


# ---------------------------------------------------------------------------
# Seam (e): analysis → decision determinism
# ---------------------------------------------------------------------------

def test_e_run_analysis_returns_workspace_analysis_result(_entity_ids):
    """run_analysis() returns a WorkspaceAnalysisResult."""
    ctrl = _make_controller(_entity_ids)
    result = ctrl.run_analysis()
    assert isinstance(result, WorkspaceAnalysisResult)


def test_e_analysis_result_id_is_sha256_hex(_entity_ids):
    """result_id is a 64-hex SHA-256 string."""
    ctrl = _make_controller(_entity_ids)
    result = ctrl.run_analysis()
    assert len(result.result_id) == 64
    assert all(c in "0123456789abcdef" for c in result.result_id)


def test_e_analysis_result_has_nominal_key(_entity_ids):
    """Worst-case analysis summary contains 'nominal'."""
    ctrl = _make_controller(_entity_ids)
    result = ctrl.run_analysis()
    assert "nominal" in result.summary_values


def test_e_analysis_result_has_total_span_key(_entity_ids):
    """Worst-case analysis summary contains 'total_span'."""
    ctrl = _make_controller(_entity_ids)
    result = ctrl.run_analysis()
    assert "total_span" in result.summary_values


def test_e_analysis_is_deterministic_same_result_id(_entity_ids):
    """Identical inputs produce identical result_id on independent runs."""
    ctrl_a = _make_controller(_entity_ids, chain_name="det-a")
    ctrl_b = _make_controller(_entity_ids, chain_name="det-a")
    assert ctrl_a.run_analysis().result_id == ctrl_b.run_analysis().result_id


def test_e_analysis_is_deterministic_same_summary(_entity_ids):
    """Identical inputs produce identical summary_values on independent runs."""
    ctrl_a = _make_controller(_entity_ids, chain_name="det-sv-a")
    ctrl_b = _make_controller(_entity_ids, chain_name="det-sv-a")
    assert (
        ctrl_a.run_analysis().summary_values
        == ctrl_b.run_analysis().summary_values
    )


def test_e_different_nominal_changes_result_id(_entity_ids):
    """Changing nominal rotates the result_id (not equal)."""
    ctrl_a = _make_controller(_entity_ids, nominal=10.0)
    ctrl_b = _make_controller(_entity_ids, nominal=20.0)
    assert ctrl_a.run_analysis().result_id != ctrl_b.run_analysis().result_id


def test_e_evaluate_decision_returns_decision_result(_entity_ids):
    """evaluate_decision() returns a ToleranceDecisionResult."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    decision = ctrl.evaluate_decision()
    assert isinstance(decision, ToleranceDecisionResult)


@pytest.mark.parametrize(
    "mode,spec_kwargs",
    [
        (AnalysisMode.WORST_CASE, {"allowed_worst_case_span": 2.0}),
        (AnalysisMode.RSS_STATISTICAL, {"allowed_combined_sigma": 5.0}),
    ],
)
def test_e_analysis_runs_in_both_modes(_entity_ids, mode, spec_kwargs):
    """Both WORST_CASE and RSS_STATISTICAL modes complete without error."""
    ctrl = ToleranceWorkspaceController(
        chain_name=f"mode-{mode.value}",
        analysis_mode=mode,
        specification=WorkspaceSpecification(**spec_kwargs),
    )
    for eid in _entity_ids:
        ctrl.add_contributor(
            identifier=eid,
            name="dim",
            nominal=10.0,
            tolerance=0.1,
            direction="forward",
            tolerance_model="symmetric",
        )
    result = ctrl.run_analysis()
    assert isinstance(result, WorkspaceAnalysisResult)


# ---------------------------------------------------------------------------
# Seam (f): governance chain completion → unified HTML flag
# ---------------------------------------------------------------------------

def test_f_full_governance_chain_completes_without_error(_entity_ids):
    """All 15 governance steps complete without raising."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    _run_full_governance_chain(ctrl)


def test_f_unified_html_export_produces_file(_entity_ids, tmp_path):
    """export_unified_html_report writes a non-empty HTML file."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    _run_full_governance_chain(ctrl)
    out_path = tmp_path / "unified.html"
    result_path = ctrl.export_unified_html_report(out_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_f_unified_html_content_contains_html_tag(_entity_ids, tmp_path):
    """Unified HTML report content contains an HTML root tag."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    _run_full_governance_chain(ctrl)
    out_path = tmp_path / "unified_check.html"
    ctrl.export_unified_html_report(out_path)
    content = out_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content or "<html" in content


def test_f_export_unified_html_before_full_chain_raises(_entity_ids, tmp_path):
    """export_unified_html_report raises when chain is not complete."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    ctrl.run_analysis()
    with pytest.raises(InvalidToleranceWorkspaceError):
        ctrl.export_unified_html_report(tmp_path / "early.html")


def test_f_governance_chain_decision_report_is_cached(_entity_ids):
    """After full chain, decision_report is cached."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    _run_full_governance_chain(ctrl)
    assert ctrl._last_decision_report is not None


def test_f_governance_chain_acceptance_closure_is_cached(_entity_ids):
    """After full chain, acceptance_closure is cached."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    _run_full_governance_chain(ctrl)
    assert ctrl._last_acceptance_closure is not None


# ---------------------------------------------------------------------------
# Seam (g): project save → reopen continuity (project_id stable)
# ---------------------------------------------------------------------------

def test_g_save_project_creates_file(_entity_ids, tmp_path):
    """save_project() creates a JSON file at the specified path."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    path = tmp_path / "test.json"
    ctrl.save_project(path)
    assert path.exists()


def test_g_open_project_returns_controller(_entity_ids, tmp_path):
    """open_project() returns a ToleranceWorkspaceController."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    path = tmp_path / "roundtrip.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    assert isinstance(reopened, ToleranceWorkspaceController)


def test_g_chain_name_survives_roundtrip(_entity_ids, tmp_path):
    """chain_name is preserved through save → reopen."""
    ctrl = _make_controller(_entity_ids, chain_name="persistence-chain-g")
    ctrl.run_analysis()
    path = tmp_path / "cn_roundtrip.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    assert reopened.state.chain_name == "persistence-chain-g"


def test_g_contributor_count_survives_roundtrip(_entity_ids, tmp_path):
    """Contributor count is preserved through save → reopen."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    path = tmp_path / "cc_roundtrip.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    assert len(reopened.contributors) == len(ctrl.contributors)


def test_g_project_id_is_deterministic(_entity_ids, tmp_path):
    """Identical workspace state → identical project_id on two saves."""
    def _save_and_read_id(out_path: Path) -> str:
        ctrl = _make_controller(_entity_ids, chain_name="det-id-chain")
        ctrl.run_analysis()
        ctrl.save_project(out_path)
        return load_project(out_path).project_id

    id1 = _save_and_read_id(tmp_path / "det_id_1.json")
    id2 = _save_and_read_id(tmp_path / "det_id_2.json")
    assert id1 == id2


def test_g_project_id_changes_with_different_chain_name(_entity_ids, tmp_path):
    """Different chain_name → different project_id."""
    def _save_id(name: str, out: Path) -> str:
        ctrl = _make_controller(_entity_ids, chain_name=name)
        ctrl.run_analysis()
        ctrl.save_project(out)
        return load_project(out).project_id

    id_a = _save_id("chain-alpha", tmp_path / "alpha.json")
    id_b = _save_id("chain-beta", tmp_path / "beta.json")
    assert id_a != id_b


def test_g_project_id_is_sha256_hex(_entity_ids, tmp_path):
    """project_id is a 64-hex SHA-256 string."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    path = tmp_path / "sha_check.json"
    ctrl.save_project(path)
    pid = load_project(path).project_id
    assert len(pid) == 64
    assert all(c in "0123456789abcdef" for c in pid)


# ---------------------------------------------------------------------------
# Seam (h): reopen → governance restore → workspace state recovery
# ---------------------------------------------------------------------------

def test_h_configuration_fingerprint_stable_after_reopen(_entity_ids, tmp_path):
    """configuration_fingerprint() is identical before and after reopen."""
    ctrl = _make_controller(_entity_ids, chain_name="fp-stable")
    ctrl.run_analysis()
    fp_before = ctrl.configuration_fingerprint()
    path = tmp_path / "fp_stable.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    assert reopened.configuration_fingerprint() == fp_before


def test_h_contributor_identifiers_restored(_entity_ids, tmp_path):
    """Contributor identifiers (entity_ids) are identical after reopen."""
    ctrl = _make_controller(_entity_ids)
    ctrl.run_analysis()
    path = tmp_path / "id_restore.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    orig_ids = {c.identifier for c in ctrl.contributors}
    rest_ids = {c.identifier for c in reopened.contributors}
    assert rest_ids == orig_ids


def test_h_contributor_nominals_restored(_entity_ids, tmp_path):
    """Contributor nominals are restored exactly after reopen."""
    ctrl = _make_controller(_entity_ids, nominal=15.0)
    ctrl.run_analysis()
    path = tmp_path / "nominal_restore.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    for orig, rest in zip(
        sorted(ctrl.contributors, key=lambda c: c.identifier),
        sorted(reopened.contributors, key=lambda c: c.identifier),
        strict=True,
    ):
        assert rest.nominal == orig.nominal


def test_h_contributor_tolerances_restored(_entity_ids, tmp_path):
    """Contributor tolerances are restored exactly after reopen."""
    ctrl = _make_controller(_entity_ids, tolerance=0.025)
    ctrl.run_analysis()
    path = tmp_path / "tol_restore.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    for orig, rest in zip(
        sorted(ctrl.contributors, key=lambda c: c.identifier),
        sorted(reopened.contributors, key=lambda c: c.identifier),
        strict=True,
    ):
        assert rest.tolerance == orig.tolerance


def test_h_analysis_rerun_after_reopen_produces_same_result_id(
    _entity_ids, tmp_path
):
    """run_analysis() after reopen produces the same result_id."""
    ctrl = _make_controller(_entity_ids, nominal=8.0, tolerance=0.08)
    original_result = ctrl.run_analysis()
    path = tmp_path / "rerun_result.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    reopened_result = reopened.run_analysis()
    assert reopened_result.result_id == original_result.result_id


def test_h_analysis_rerun_after_reopen_produces_same_summary(
    _entity_ids, tmp_path
):
    """run_analysis() after reopen produces identical summary_values."""
    ctrl = _make_controller(_entity_ids, nominal=8.0, tolerance=0.08)
    original_result = ctrl.run_analysis()
    path = tmp_path / "rerun_summary.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    reopened_result = reopened.run_analysis()
    assert reopened_result.summary_values == original_result.summary_values


def test_h_full_governance_chain_reruns_after_reopen(_entity_ids, tmp_path):
    """Full governance chain can be re-executed after reopen."""
    ctrl = _make_controller(_entity_ids, allowed_wc_span=2.0)
    ctrl.run_analysis()
    path = tmp_path / "chain_rerun.json"
    ctrl.save_project(path)
    reopened = ToleranceWorkspaceController.open_project(path)
    _run_full_governance_chain(reopened)


def test_h_project_id_stable_across_reopen_with_reanalysis(_entity_ids, tmp_path):
    """project_id is unchanged after reopen → re-run analysis → resave.

    The analysis result (result_id) enters the project identity; since
    analysis is deterministic, re-running it after reopen produces the same
    result_id, keeping the project_id stable.
    """
    ctrl = _make_controller(_entity_ids, chain_name="id-stable-h")
    ctrl.run_analysis()
    path1 = tmp_path / "orig.json"
    ctrl.save_project(path1)
    orig_id = load_project(path1).project_id

    reopened = ToleranceWorkspaceController.open_project(path1)
    reopened.run_analysis()  # re-run is deterministic → same result_id
    path2 = tmp_path / "resaved.json"
    reopened.save_project(path2)
    resaved_id = load_project(path2).project_id

    assert resaved_id == orig_id
