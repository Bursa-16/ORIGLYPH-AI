"""Unit tests for origlyph.cad.stl (Stage 12D STL importer)."""
import struct

import pytest

from origlyph.cad import (
    CadFormat,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
    StlImporter,
)
from origlyph.cad.binding import bind_reference
from origlyph.cad.bridge import (
    BridgedCandidate,
    CandidateResult,
    extract_candidates,
)
from origlyph.cad.exceptions import (
    CadImportError,
    UnsupportedCadFormatError,
    UnsupportedSourceUnitError,
)
from origlyph.cad.role import bind_datum_constraint, bind_datum_reference_frame
from origlyph.datum import ConstraintType, FeatureKind, ReferenceSurface
from origlyph.geometry import BoundedPlanarFace, Point3D, Vector3D


def _doc() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="test.stl",
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit="mm"),
    )


def _doc_m() -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id="test.stl",
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit="m"),
    )


def _facet_text(v1: str, v2: str, v3: str) -> str:
    return (
        "facet normal 0 0 1\n"
        f" outer loop\n  vertex {v1}\n  vertex {v2}\n  vertex {v3}\n"
        " endloop\nendfacet\n"
    )


def _ascii_payload(*facets: str, solid_name: str = "test") -> bytes:
    body = "".join(facets)
    return f"solid {solid_name}\n{body}endsolid {solid_name}\n".encode("ascii")


_UP_Z = (0.0, 0.0, 1.0)
_TRI_A = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
_TRI_B = ((2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.0, 1.0, 0.0))
_TRI_C = ((5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0))


def _binary_facet(
    vertices: tuple[tuple[float, float, float], ...],
    normal: tuple[float, float, float],
) -> bytes:
    floats = struct.pack(
        "<12f",
        normal[0],
        normal[1],
        normal[2],
        vertices[0][0],
        vertices[0][1],
        vertices[0][2],
        vertices[1][0],
        vertices[1][1],
        vertices[1][2],
        vertices[2][0],
        vertices[2][1],
        vertices[2][2],
    )
    return floats + struct.pack("<H", 0)


def _binary_payload(*facets: bytes, tag: bytes = b"solid") -> bytes:
    header = tag + b"\x00" * (80 - len(tag))
    return header + struct.pack("<I", len(facets)) + b"".join(facets)


# --------------------------------------------------------------------------- #
# 1. ASCII one/multiple facets
# --------------------------------------------------------------------------- #
def test_ascii_single_facet_import() -> None:
    payload = _ascii_payload(_facet_text("0 0 0", "1 0 0", "0 1 0"))
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert len(model.entities) == 1
    assert model.entities[0].identity.neutral_entity_key == "facet-0"


def test_ascii_multi_facet_order_preserved() -> None:
    payload = _ascii_payload(
        _facet_text("0 0 0", "1 0 0", "0 1 0"),
        _facet_text("2 0 0", "3 0 0", "2 1 0"),
    )
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert [e.identity.neutral_entity_key for e in model.entities] == [
        "facet-0",
        "facet-1",
    ]


def test_ascii_multi_solid_blocks() -> None:
    text = (
        "solid first\n"
        + _facet_text("0 0 0", "1 0 0", "0 1 0")
        + "endsolid first\n"
        + "solid second\n"
        + _facet_text("2 0 0", "3 0 0", "2 1 0")
        + "endsolid second\n"
    )
    importer = StlImporter(bytes_loader=lambda _: text.encode("ascii"))
    model = importer.import_document(_doc())
    assert [e.identity.neutral_entity_key for e in model.entities] == [
        "facet-0",
        "facet-1",
    ]


# --------------------------------------------------------------------------- #
# 2. Binary one/multiple facets
# --------------------------------------------------------------------------- #
def test_binary_single_facet_import() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert len(model.entities) == 1
    assert model.entities[0].identity.neutral_entity_key == "facet-0"


def test_binary_multi_facet_order_preserved() -> None:
    payload = _binary_payload(
        _binary_facet(_TRI_A, _UP_Z),
        _binary_facet(_TRI_B, _UP_Z),
    )
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert [e.identity.neutral_entity_key for e in model.entities] == [
        "facet-0",
        "facet-1",
    ]


# --------------------------------------------------------------------------- #
# 3. Binary header beginning with "solid" stays binary (size+count rule)
# --------------------------------------------------------------------------- #
def test_binary_header_starts_solid_detected_as_binary() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z), tag=b"solid")
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert len(model.entities) == 1
    assert isinstance(model.entities[0].geometry, BoundedPlanarFace)


# --------------------------------------------------------------------------- #
# 4. Deterministic re-import
# --------------------------------------------------------------------------- #
def test_deterministic_re_import() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    importer = StlImporter(bytes_loader=lambda _: payload)
    m1 = importer.import_document(_doc())
    m2 = importer.import_document(_doc())
    assert m1.entities == m2.entities
    assert [e.identity for e in m1.entities] == [e.identity for e in m2.entities]
    assert m1.warnings == m2.warnings


# --------------------------------------------------------------------------- #
# 5. Identities / mapping
# --------------------------------------------------------------------------- #
def test_reverse_lookup_resolves_exact_source_identity() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    src = SourceEntityIdentity(
        source_document=_doc(), source_entity_key="facet-0"
    )
    neutral = model.reverse_lookup(src)
    assert neutral.neutral_entity_key == "facet-0"
    assert neutral.source_identity == src


def test_entity_identity_chain_preserved() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    entry = model.entities[0]
    assert entry.identity.source_identity is not None
    assert entry.identity.source_identity.source_entity_key == "facet-0"
    assert entry.identity.source_identity.source_document.source_id == "test.stl"
    assert entry.identity.kind is NeutralEntityKind.PLANE


# --------------------------------------------------------------------------- #
# 6. Winding preservation (vertices verbatim in file order)
# --------------------------------------------------------------------------- #
def test_winding_preserved_verbatim() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    face = model.entities[0].geometry
    assert isinstance(face, BoundedPlanarFace)
    assert face.vertices == (
        Point3D(0.0, 0.0, 0.0),
        Point3D(1.0, 0.0, 0.0),
        Point3D(0.0, 1.0, 0.0),
    )


# --------------------------------------------------------------------------- #
# 7. STL stored normal is diagnostics-only (never authoritative)
# --------------------------------------------------------------------------- #
def test_stored_normal_is_diagnostics_only() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, (0.0, 0.0, -1.0)))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    entry = model.entities[0]
    assert entry.metadata["stl_normal"] == (0.0, 0.0, -1.0)
    face = entry.geometry
    assert isinstance(face, BoundedPlanarFace)
    # Winding-derived normal stays +Z; the stored -Z never reorients it.
    assert face.plane.normal == Vector3D(0.0, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# 8. Malformed ASCII (document-fatal)
# --------------------------------------------------------------------------- #
def test_ascii_missing_endfacet_fails() -> None:
    payload = (
        "solid test\n"
        "facet normal 0 0 1\n"
        " outer loop\n  vertex 0 0 0\n  vertex 1 0 0\n  vertex 0 1 0\n"
        " endloop\n"
        "endsolid test\n"
    ).encode("ascii")
    importer = StlImporter(bytes_loader=lambda _: payload)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_ascii_bad_float_fails() -> None:
    payload = _ascii_payload(_facet_text("0 0 0", "1 0 0", "0 x 0"))
    importer = StlImporter(bytes_loader=lambda _: payload)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_ascii_trailing_content_fails() -> None:
    text = (
        _ascii_payload(_facet_text("0 0 0", "1 0 0", "0 1 0")).decode("ascii")
        + "garbage data\n"
    )
    importer = StlImporter(bytes_loader=lambda _: text.encode("ascii"))
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_empty_payload_fails() -> None:
    importer = StlImporter(bytes_loader=lambda _: b"")
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_non_stl_payload_fails() -> None:
    importer = StlImporter(bytes_loader=lambda _: b"not an stl file")
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


# --------------------------------------------------------------------------- #
# 9. Truncated / oversized binary (document-fatal)
# --------------------------------------------------------------------------- #
def test_truncated_binary_payload_fails() -> None:
    importer = StlImporter(bytes_loader=lambda _: b"\x00" * 50)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_binary_partial_facet_fails() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))[:-5]
    importer = StlImporter(bytes_loader=lambda _: payload)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_binary_trailing_bytes_rejected() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z)) + b"\x00\x00"
    importer = StlImporter(bytes_loader=lambda _: payload)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


# --------------------------------------------------------------------------- #
# 10. Degenerate facets: facet-local, recorded, never silent
# --------------------------------------------------------------------------- #
def test_degenerate_facet_collinear_recorded_not_silent() -> None:
    payload = _ascii_payload(
        _facet_text("0 0 0", "1 0 0", "0 1 0"),
        _facet_text("5 0 0", "6 0 0", "7 0 0"),
    )
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert len(model.entities) == 1
    assert len(model.warnings) == 1
    assert model.warnings[0].code == "DEGENERATE_FACET"
    assert len(model.unsupported) == 1
    assert model.unsupported[0].source is not None
    assert model.unsupported[0].source.source_entity_key == "facet-1"


def test_degenerate_facet_duplicate_vertices_recorded() -> None:
    payload = _ascii_payload(_facet_text("1 1 1", "1 1 1", "0 1 0"))
    importer = StlImporter(bytes_loader=lambda _: payload)
    model = importer.import_document(_doc())
    assert len(model.entities) == 0
    assert len(model.warnings) == 1
    assert len(model.unsupported) == 1


# --------------------------------------------------------------------------- #
# 11. NaN / Inf (document-fatal in both grammars)
# --------------------------------------------------------------------------- #
def test_ascii_non_finite_float_fails() -> None:
    payload = _ascii_payload(_facet_text("0 0 0", "1 0 0", "0 nan 0"))
    importer = StlImporter(bytes_loader=lambda _: payload)
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


def test_binary_non_finite_float_fails() -> None:
    payload = bytearray(_binary_payload(_binary_facet(_TRI_A, _UP_Z)))
    payload[84:88] = struct.pack("<f", float("nan"))
    importer = StlImporter(bytes_loader=lambda _: bytes(payload))
    with pytest.raises(CadImportError):
        importer.import_document(_doc())


# --------------------------------------------------------------------------- #
# 12. Unit policy: declared mm only, no inference, no conversion
# --------------------------------------------------------------------------- #
def test_import_rejects_non_mm_declaration() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    importer = StlImporter(bytes_loader=lambda _: payload)
    assert importer.can_import(_doc_m()) is False
    with pytest.raises(UnsupportedSourceUnitError):
        importer.import_document(_doc_m())


def test_can_import_accepts_mm_stl() -> None:
    assert StlImporter().can_import(_doc()) is True


def test_can_import_rejects_non_stl_format() -> None:
    step_doc = SourceDocumentIdentity(
        source_id="test.step",
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )
    assert StlImporter().can_import(step_doc) is False
    with pytest.raises(UnsupportedCadFormatError):
        StlImporter().import_document(step_doc)


# --------------------------------------------------------------------------- #
# 13. Integration: extract_candidates lifts imported STL faces
# --------------------------------------------------------------------------- #
def test_extract_candidates_lifts_stl_faces() -> None:
    payload = _binary_payload(
        _binary_facet(_TRI_A, _UP_Z),
        _binary_facet(_TRI_B, _UP_Z),
    )
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    result = extract_candidates(model)
    assert isinstance(result, CandidateResult)
    assert len(result.candidates) == 2
    assert result.skipped == ()
    first = result.candidates[0]
    assert isinstance(first, BridgedCandidate)
    assert first.neutral_identity.neutral_entity_key == "facet-0"
    assert first.datum_feature.kind == FeatureKind.PLANE
    assert isinstance(first.reference, ReferenceSurface)


def test_extract_candidates_is_deterministic() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    assert extract_candidates(model) == extract_candidates(model)


# --------------------------------------------------------------------------- #
# 14. Integration: bind_reference preserves provenance
# --------------------------------------------------------------------------- #
def test_bind_reference_from_stl_face() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    bound = bind_reference(extract_candidates(model).candidates[0])
    assert bound.neutral_identity.neutral_entity_key == "facet-0"
    assert bound.source_identity is not None
    assert bound.source_identity.source_entity_key == "facet-0"
    assert bound.source_identity.source_document.source_id == "test.stl"


# --------------------------------------------------------------------------- #
# 15. Integration: explicit role binding from an STL face
# --------------------------------------------------------------------------- #
def test_bind_datum_constraint_primary_from_stl_face() -> None:
    payload = _binary_payload(_binary_facet(_TRI_A, _UP_Z))
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    bound = bind_reference(extract_candidates(model).candidates[0])
    constraint = bind_datum_constraint(bound, ConstraintType.PRIMARY)
    assert constraint.sequence == 1


# --------------------------------------------------------------------------- #
# 16. Integration: full chain STL faces -> DRF (3-2-1 from real facets)
# --------------------------------------------------------------------------- #
def test_full_datum_chain_from_stl_faces() -> None:
    payload = _binary_payload(
        _binary_facet(_TRI_A, _UP_Z),
        _binary_facet(_TRI_B, _UP_Z),
        _binary_facet(_TRI_C, _UP_Z),
    )
    model = StlImporter(bytes_loader=lambda _: payload).import_document(_doc())
    bounds = [bind_reference(c) for c in extract_candidates(model).candidates]
    roles = (
        ConstraintType.PRIMARY,
        ConstraintType.SECONDARY,
        ConstraintType.TERTIARY,
    )
    constraints = [
        bind_datum_constraint(bound, role)
        for bound, role in zip(bounds, roles, strict=True)
    ]
    assert [c.sequence for c in constraints] == [1, 2, 3]
    drf = bind_datum_reference_frame(
        "WCS", list(zip(bounds, roles, strict=True))
    )
    assert [c.sequence for c in drf.constraints] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# 17. Fail-closed construction / loader contract
# --------------------------------------------------------------------------- #
def test_import_without_loader_fails_closed() -> None:
    with pytest.raises(CadImportError):
        StlImporter().import_document(_doc())


def test_loader_returning_non_bytes_fails_closed() -> None:
    importer = StlImporter(bytes_loader=lambda _: "not bytes")  # type: ignore[arg-type]
    with pytest.raises(CadImportError):
        importer.import_document(_doc())
