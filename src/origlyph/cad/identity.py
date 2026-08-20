"""Entity identity contracts for the Origlyph CAD import domain.

Stage 1C. These contracts make a sharp, explicit distinction between four
kinds of identity that must never be collapsed into a single string:

* **domain identity** — an opaque, analysis/domain-scoped handle;
* **source document identity** — identity of the originating CAD document;
* **source entity identity** — the CAD-native entity key within that document;
* **neutral imported entity identity** — the import-result-scoped identity
  Origlyph uses for the imported entity.

There is deliberately **no** persistent application/database identity and no
global-persistence claim: neutral identities are scoped to one import result
and must never pretend to survive arbitrary CAD revisions.

This module is dependency-free apart from ``origlyph.geometry`` (used only to
reuse the existing explicit unit contracts for source-unit validation). It
never carries binary file contents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from origlyph.geometry import Angle, Length, UnitError

from .exceptions import (
    InvalidSourceIdentityError,
    UnsupportedSourceUnitError,
)

__all__ = [
    "CadFormat",
    "DomainIdentity",
    "NeutralEntityIdentity",
    "NeutralEntityKind",
    "SourceDocumentIdentity",
    "SourceEntityIdentity",
    "SourceUnitSystem",
]


class CadFormat(str, Enum):
    """A deliberately modeled CAD document format identity.

    Only formats the contract explicitly models are members. There is no
    ``UNKNOWN`` member: an unknown format is a fail-closed condition at the
    importer boundary, never an importable value.
    """

    STEP = "step"
    IGES = "iges"
    STL = "stl"
    DXF = "dxf"


class NeutralEntityKind(str, Enum):
    """Classification-only category of a neutral imported entity.

    This is classification/metadata only: it carries no topology or B-Rep
    behavior. ``SOLID_BODY``, ``COMPONENT_INSTANCE`` etc. are identity and
    metadata placeholders until later stages provide real geometry.
    """

    POINT = "point"
    LINE = "line"
    AXIS = "axis"
    PLANE = "plane"
    CURVE = "curve"
    SURFACE = "surface"
    SOLID_BODY = "solid_body"
    COMPONENT_INSTANCE = "component_instance"
    ANNOTATION_REFERENCE = "annotation_reference"


@dataclass(frozen=True)
class SourceUnitSystem:
    """Explicit units declared by a source document.

    Length/angle unit names are stored verbatim as source metadata and are
    validated against the existing Origlyph unit contracts so that unknown
    source units fail closed instead of silently assuming millimetres.
    """

    length_unit: str = "mm"
    angle_unit: str = "rad"

    def __post_init__(self) -> None:
        for raw, kind in ((self.length_unit, "length"), (self.angle_unit, "angle")):
            if not raw.strip():
                raise UnsupportedSourceUnitError(
                    f"source {kind} unit must not be empty"
                )
        try:
            Length.of(1.0, self.length_unit)
        except UnitError as exc:
            raise UnsupportedSourceUnitError(
                f"unsupported source length unit {self.length_unit!r}"
            ) from exc
        try:
            Angle.of(1.0, self.angle_unit)
        except UnitError as exc:
            raise UnsupportedSourceUnitError(
                f"unsupported source angle unit {self.angle_unit!r}"
            ) from exc
@dataclass(frozen=True)
class DomainIdentity:
    """Opaque, analysis/domain-scoped identity handle.

    Carries no CAD/source semantics and makes no persistence claim. It is
    purely a stable, non-empty normalized label valid within one domain
    computation.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("domain identity value must not be empty")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class SourceDocumentIdentity:
    """Identity and metadata of one source CAD document.

    Recorded before/independent of any parsing, and does not include binary
    file contents or any persistence/database semantics.
    """

    source_id: str
    format: CadFormat
    unit_system: SourceUnitSystem
    original_filename: Optional[str] = None
    source_revision: Optional[str] = None
    fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        source_id = self.source_id.strip()
        if not source_id:
            raise InvalidSourceIdentityError(
                "source document source_id must not be empty"
            )
        if not isinstance(self.format, CadFormat):
            raise InvalidSourceIdentityError(
                f"unsupported source format {self.format!r}; CadFormat required"
            )
        object.__setattr__(self, "source_id", source_id)
        if self.original_filename is not None:
            name = self.original_filename.strip()
            object.__setattr__(self, "original_filename", name or None)
        if self.source_revision is not None:
            rev = self.source_revision.strip()
            object.__setattr__(self, "source_revision", rev or None)
        if self.fingerprint is not None:
            fp = self.fingerprint.strip()
            object.__setattr__(self, "fingerprint", fp or None)


@dataclass(frozen=True)
class SourceEntityIdentity:
    """Identity of an entity as it originates in the source CAD document.

    Scoped to its :class:`SourceDocumentIdentity`. It records the CAD-native
    key and an optional path within the model/assembly hierarchy, and must not
    pretend to survive arbitrary CAD revisions.
    """

    source_document: SourceDocumentIdentity
    source_entity_key: str
    path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        key = self.source_entity_key.strip()
        if not key:
            raise InvalidSourceIdentityError("source entity key must not be empty")
        object.__setattr__(self, "source_entity_key", key)
        object.__setattr__(self, "path", tuple(self.path))


@dataclass(frozen=True)
class NeutralEntityIdentity:
    """Import-result-scoped identity for a neutral imported entity.

    Equality/hash are deterministic. A neutral identity never claims global
    persistence across CAD revisions. Entities that have no genuine source
    entity must be explicitly marked ``generated=True``; otherwise a source
    identity is required.
    """

    neutral_entity_key: str
    kind: NeutralEntityKind
    source_identity: Optional[SourceEntityIdentity] = None
    generated: bool = False
    entity_path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        key = self.neutral_entity_key.strip()
        if not key:
            raise ValueError("neutral entity key must not be empty")
        if not isinstance(self.kind, NeutralEntityKind):
            raise ValueError(f"unsupported neutral entity kind {self.kind!r}")
        if self.source_identity is None and not self.generated:
            raise ValueError(
                "a neutral entity must be source-derived or explicitly generated"
            )
        if self.source_identity is not None and self.generated:
            raise ValueError(
                "generated neutral entities cannot also carry a source identity"
            )
        object.__setattr__(self, "neutral_entity_key", key)
        object.__setattr__(self, "entity_path", tuple(self.entity_path))