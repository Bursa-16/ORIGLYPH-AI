"""Deterministic STL importer (Stage 12C/12D).

Concrete :class:`CadImporter` for the STL (stereolithography) format. It parses
ASCII and binary STL into a :class:`NeutralModel` of planar faces, honoring the
contract locked at Stage 12C:

* bytes are obtained only through an injected ``bytes_loader`` callable -- the
  importer itself performs no filesystem I/O (``CadImporter.import_document``
  remains the single entry point, unchanged);
* ASCII/binary detection is deterministic -- a payload whose binary layout
  matches ``84 + 50 * facet_count`` bytes is binary, even when its 80-byte
  header begins with the ASCII bytes ``solid``;
* STL has no units: the only accepted declaration is
  ``source_document.unit_system.length_unit == "mm"``. No geometry-scale
  inference and no implicit conversion of any kind;
* the stored STL facet normal is diagnostics-only. A facet is stored as
  vertices **verbatim in file order** (never reordered or flipped to match the
  stored normal), and ``BoundedPlanarFace.plane.normal`` (winding-derived) is
  what downstream consumers use;
* a document-fatal condition (truncated binary, malformed ASCII, size/count
  mismatch, NaN/Inf, unsupported unit) raises ``CadImportError`` /
  ``UnsupportedSourceUnitError``; a facet-local degenerate geometry (duplicate
  vertices, collinear vertices, zero area) is recorded in both
  ``NeutralModel.warnings`` and ``NeutralModel.unsupported`` -- never silently
  dropped.

Zero external dependencies (standard library ``struct``/``math`` only). No
numpy, no mesh library, no geometry kernel.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Callable

from origlyph._version import __version__ as _origlyph_version
from origlyph.geometry import BoundedPlanarFace, Frame, Point3D

from .exceptions import (
    CadImportError,
    InvalidSourceIdentityError,
    UnsupportedCadFormatError,
    UnsupportedSourceUnitError,
)
from .identity import (
    CadFormat,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
)
from .model import (
    CadWarning,
    NeutralEntityEntry,
    NeutralModel,
    SourceToNeutralMapping,
    UnsupportedContent,
)

__all__ = ["StlImporter"]

BytesLoader = Callable[[SourceDocumentIdentity], bytes]

_KEYWORDS = frozenset(
    {
        "solid",
        "endsolid",
        "facet",
        "normal",
        "outer",
        "loop",
        "vertex",
        "endloop",
        "endfacet",
    }
)

_BINARY_HEADER_SIZE = 84
_FACET_BYTES = 50


class StlImporter:
    """Import ASCII or binary STL bytes into a :class:`NeutralModel`.

    Construct with a ``bytes_loader`` that, given a
    :class:`~origlyph.cad.identity.SourceDocumentIdentity`, returns the STL
    payload as ``bytes``. The loader is the only I/O / bytes touchpoint; when
    it is not supplied, ``import_document`` fails closed with
    :class:`CadImportError`.
    """

    importer_id = "origlyph.stl"
    importer_version = _origlyph_version
    supported_formats = frozenset({CadFormat.STL})

    def __init__(self, bytes_loader: BytesLoader | None = None) -> None:
        self._bytes_loader = bytes_loader

    def can_import(self, source_document: object) -> bool:
        if not isinstance(source_document, SourceDocumentIdentity):
            return False
        return (
            source_document.format is CadFormat.STL
            and source_document.unit_system.length_unit == "mm"
        )

    def import_document(
        self, source_document: SourceDocumentIdentity
    ) -> NeutralModel:
        if not isinstance(source_document, SourceDocumentIdentity):
            raise InvalidSourceIdentityError(
                "import_document requires a SourceDocumentIdentity"
            )
        if source_document.format is not CadFormat.STL:
            raise UnsupportedCadFormatError(
                f"StlImporter imports STL only; got {source_document.format!r}"
            )
        if source_document.unit_system.length_unit != "mm":
            raise UnsupportedSourceUnitError(
                "STL is unitless; StlImporter requires the declared source "
                "'length_unit' to be 'mm' and performs no scale inference"
            )
        if self._bytes_loader is None:
            raise CadImportError("no bytes loader configured for StlImporter")
        payload = self._bytes_loader(source_document)
        if not isinstance(payload, bytes):
            raise CadImportError("bytes loader must return bytes")
        if _looks_binary(payload):
            facets = self._parse_binary(payload)
        else:
            facets = self._parse_ascii(payload)
        entries: list[NeutralEntityEntry] = []
        pairs: list[tuple[SourceEntityIdentity, NeutralEntityIdentity]] = []
        warnings: list[CadWarning] = []
        unsupported: list[UnsupportedContent] = []
        for index, (facet_normal, vertices) in enumerate(facets):
            key = f"facet-{index}"
            source_identity = SourceEntityIdentity(
                source_document=source_document, source_entity_key=key
            )
            v1 = Point3D(
                float(vertices[0][0]), float(vertices[0][1]), float(vertices[0][2])
            )
            v2 = Point3D(
                float(vertices[1][0]), float(vertices[1][1]), float(vertices[1][2])
            )
            v3 = Point3D(
                float(vertices[2][0]), float(vertices[2][1]), float(vertices[2][2])
            )
            try:
                face = BoundedPlanarFace((v1, v2, v3))
            except (ValueError, TypeError):
                warnings.append(
                    CadWarning(
                        code="DEGENERATE_FACET",
                        message=(
                            f"facet-{index}: degenerate facet (duplicate/collinear "
                            "vertices or zero area), skipped"
                        ),
                    )
                )
                unsupported.append(
                    UnsupportedContent(
                        reason="degenerate facet",
                        source=source_identity,
                        kind=NeutralEntityKind.PLANE,
                    )
                )
                continue
            normal = (
                float(facet_normal[0]),
                float(facet_normal[1]),
                float(facet_normal[2]),
            )
            entry = NeutralEntityEntry(
                identity=NeutralEntityIdentity(
                    neutral_entity_key=key,
                    kind=NeutralEntityKind.PLANE,
                    source_identity=source_identity,
                ),
                geometry=face,
                coordinate_frame=None,
                metadata={"stl_normal": normal},
            )
            entries.append(entry)
            pairs.append((source_identity, entry.identity))
        mapping = SourceToNeutralMapping(pairs=pairs)
        return NeutralModel(
            source=source_document,
            root_frame=Frame.world(),
            entities=entries,
            source_to_neutral=mapping,
            warnings=warnings,
            unsupported=unsupported,
        )

    # ------------------------------------------------------------------ #
    # ASCII grammar
    # ------------------------------------------------------------------ #
    def _parse_ascii(self, payload: bytes) -> list[list]:
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError as exc:
            raise CadImportError("invalid ASCII STL (non-ASCII bytes)") from exc
        tokens = text.split()
        if not tokens:
            raise CadImportError("empty STL payload; no solid found")
        facets: list[list] = []
        pos = 0
        total = len(tokens)
        while pos < total:
            pos = self._require(tokens, pos, "solid", "'solid'")
            pos = self._skip_optional_name(tokens, pos)
            while True:
                if pos >= total:
                    raise CadImportError(
                        "unexpected end of ASCII STL; unterminated 'solid' block"
                    )
                if tokens[pos].lower() == "endsolid":
                    pos = self._skip_optional_name(tokens, pos + 1)
                    break
                pos, facet = self._parse_ascii_facet(tokens, pos)
                facets.append(facet)
        return facets

    @staticmethod
    def _skip_optional_name(tokens: list[str], pos: int) -> int:
        """Consume one optional non-keyword name token (after solid/endsolid)."""
        if pos < len(tokens) and not _is_keyword(tokens[pos]):
            return pos + 1
        return pos

    def _parse_ascii_facet(
        self, tokens: list[str], pos: int
    ) -> tuple[int, list]:
        """Parse one ``facet ... endfacet`` block starting at ``pos``.

        Returns ``(new_pos, [normal, vertices])`` with the three vertices in
        file order (verbatim winding, never reordered).
        """
        pos = self._require(tokens, pos, "facet", "'facet'")
        pos = self._require(tokens, pos, "normal", "'facet normal'")
        normal = self._read_floats3(tokens, pos)
        pos += 3
        pos = self._require(tokens, pos, "outer", "'outer loop'")
        pos = self._require(tokens, pos, "loop", "'outer loop'")
        vertices = []
        for _ in range(3):
            pos = self._require(tokens, pos, "vertex", "'vertex'")
            vertices.append(self._read_floats3(tokens, pos))
            pos += 3
        pos = self._require(tokens, pos, "endloop", "'endloop'")
        pos = self._require(tokens, pos, "endfacet", "'endfacet'")
        return pos, [normal, vertices]

    def _require(self, tokens: list[str], pos: int, word: str, what: str) -> int:
        if pos >= len(tokens):
            raise CadImportError(
                f"unexpected end of ASCII STL; expected {what}"
            )
        if tokens[pos].lower() != word:
            raise CadImportError(
                f"expected {what} but found {tokens[pos]!r}"
            )
        return pos + 1

    def _read_floats3(
        self, tokens: list[str], pos: int
    ) -> tuple[float, float, float]:
        values: list[float] = []
        for offset in range(3):
            if pos + offset >= len(tokens):
                raise CadImportError(
                    "unexpected end of ASCII STL; expected a float"
                )
            raw = tokens[pos + offset]
            try:
                value = float(raw)
            except ValueError as exc:
                raise CadImportError(
                    f"unparseable float {raw!r} in ASCII STL"
                ) from exc
            if not math.isfinite(value):
                raise CadImportError(
                    f"non-finite float {raw!r} in ASCII STL"
                )
            values.append(value)
        return (values[0], values[1], values[2])

    # ------------------------------------------------------------------ #
    # Binary grammar
    # ------------------------------------------------------------------ #
    def _parse_binary(self, payload: bytes) -> list[list]:
        if len(payload) < _BINARY_HEADER_SIZE:
            raise CadImportError(
                "truncated binary STL (shorter than 84-byte header)"
            )
        count = struct.unpack_from("<I", payload, 80)[0]
        expected = _BINARY_HEADER_SIZE + _FACET_BYTES * count
        if len(payload) != expected:
            raise CadImportError(
                f"binary STL size mismatch: expected {expected} bytes for "
                f"{count} facet(s), got {len(payload)}"
            )
        facets: list[list] = []
        offset = _BINARY_HEADER_SIZE
        for index in range(count):
            floats = struct.unpack_from("<12f", payload, offset)
            # 2-byte attribute count follows the 12 floats; consumed, ignored.
            attribute_count = struct.unpack_from("<H", payload, offset + 48)[0]
            if not all(math.isfinite(value) for value in floats):
                raise CadImportError(
                    f"non-finite float in binary STL facet {index}"
                )
            facet_normal = (floats[0], floats[1], floats[2])
            v1 = (floats[3], floats[4], floats[5])
            v2 = (floats[6], floats[7], floats[8])
            v3 = (floats[9], floats[10], floats[11])
            facets.append([facet_normal, [v1, v2, v3]])
            offset += _FACET_BYTES
            # attribute_count is intentionally unused; documented as ignored.
            _ = attribute_count
        return facets


def _looks_binary(payload: bytes) -> bool:
    """Return whether ``payload`` has an exact binary-STL byte layout.

    The 80-byte header is arbitrary; the layout is binary when the declared
    little-endian uint32 facet count at offset 80 satisfies
    ``len(payload) == 84 + 50 * count``. A header region that happens to begin
    with the ASCII bytes ``solid`` is therefore still detected as binary.
    """
    if len(payload) < _BINARY_HEADER_SIZE:
        return False
    count = struct.unpack_from("<I", payload, 80)[0]
    return len(payload) == _BINARY_HEADER_SIZE + _FACET_BYTES * count


def _is_keyword(token: str) -> bool:
    return token.lower() in _KEYWORDS
