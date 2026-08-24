"""Neutral imported model and source-to-neutral mapping contracts.

Stage 1C. Defines the minimal immutable neutral model produced by a CAD
importer, immutable source-to-neutral identity mapping, and the separate
non-fatal warning / unsupported-content reports returned with a model.

There is deliberately no topology tree, no B-Rep, and no persistence here.
Entities are classification + identity (+ optional canonical geometry where an
existing Origlyph geometry value object already exists).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

from origlyph.geometry import (
    BoundedPlanarFace,
    Frame,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)

from .exceptions import (
    DuplicateNeutralEntityError,
    DuplicateSourceEntityError,
)
from .identity import (
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
)

__all__ = [
    "CadWarning",
    "NeutralEntityEntry",
    "NeutralModel",
    "SourceToNeutralMapping",
    "UnsupportedContent",
]

# Existing Origlyph canonical geometry value objects that an entity entry may
# carry. Since Stage 5G the accepted set also includes the bounded planar face
# (finite extent). CURVE/SURFACE/SOLID/INSTANCE etc. carry identity only.
GeometryValue = object

_DEFAULT_METADATA: Mapping[str, object] = MappingProxyType({})
_DEFAULT_PATH: tuple[str, ...] = ()


@dataclass(frozen=True)
class NeutralEntityEntry:
    """One neutral imported entity: identity + optional canonical geometry.

    ``geometry`` is limited to existing ``origlyph.geometry`` value objects
    (the canonical primitives plus, since Stage 5G, the bounded planar face)
    or ``None``. No new primitives, no B-Rep, no topology, no kernel handle is
    introduced. ``metadata`` is exposed read-only.
    """

    identity: NeutralEntityIdentity
    geometry: Optional[GeometryValue] = None
    coordinate_frame: Optional[Frame] = None
    metadata: Mapping[str, object] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        if self.geometry is not None and not isinstance(
            self.geometry,
            (BoundedPlanarFace, Point3D, Vector3D, Line3D, Plane3D),
        ):
            raise TypeError(
                "neutral entity geometry must be an existing Origlyph "
                "geometry value object or None"
            )
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata))
        )

    @property
    def kind(self) -> NeutralEntityKind:
        """Classification kind of this entry (metadata only)."""
        return self.identity.kind


@dataclass(frozen=True)
class CadWarning:
    """A non-fatal warning raised during import.

    Warnings are intentionally separate from fatal exception types.
    """

    code: str
    message: str


@dataclass(frozen=True)
class UnsupportedContent:
    """Engineering-relevant content that could not be imported.

    Recorded so that unsupported-but-ignored content never disappears
    silently; an importer/reporter must surface it.
    """

    reason: str
    source: Optional[SourceEntityIdentity] = None
    kind: Optional[NeutralEntityKind] = None


@dataclass(frozen=True, init=False)
class SourceToNeutralMapping:
    """Immutable deterministic source-identity to neutral-identity mapping.

    Rejects duplicate source keys and duplicate neutral identities; there is
    no silent remapping. Generated neutral entities (no source) are simply not
    present in the mapping.
    """

    _source_to_neutral: Mapping[SourceEntityIdentity, NeutralEntityIdentity]
    _neutral_to_source: Mapping[NeutralEntityIdentity, SourceEntityIdentity]

    def __init__(
        self,
        pairs: Optional[
            list[tuple[SourceEntityIdentity, NeutralEntityIdentity]]
        ] = None,
    ) -> None:
        pairs = pairs or []
        source_map: dict[SourceEntityIdentity, NeutralEntityIdentity] = {}
        neutral_map: dict[NeutralEntityIdentity, SourceEntityIdentity] = {}
        for source, neutral in pairs:
            if source in source_map:
                raise DuplicateSourceEntityError(
                    f"duplicate source entity key {source.source_entity_key!r}"
                )
            if neutral in neutral_map:
                raise DuplicateNeutralEntityError(
                    f"duplicate neutral identity {neutral.neutral_entity_key!r}"
                )
            source_map[source] = neutral
            neutral_map[neutral] = source
        object.__setattr__(
            self, "_source_to_neutral", MappingProxyType(source_map)
        )
        object.__setattr__(
            self, "_neutral_to_source", MappingProxyType(neutral_map)
        )

    @property
    def pairs(
        self,
    ) -> tuple[tuple[SourceEntityIdentity, NeutralEntityIdentity], ...]:
        """Immutable snapshot of the mapping pairs."""
        return tuple(
            (source, neutral)
            for source, neutral in self._source_to_neutral.items()
        )

    def source_to_neutral(
        self, source: SourceEntityIdentity
    ) -> Optional[NeutralEntityIdentity]:
        """Return the neutral identity mapped from ``source``, if any."""
        return self._source_to_neutral.get(source)

    def neutral_to_source(
        self, neutral: NeutralEntityIdentity
    ) -> Optional[SourceEntityIdentity]:
        """Return the source identity mapped to ``neutral``, if any."""
        return self._neutral_to_source.get(neutral)
@dataclass(frozen=True, init=False)
class NeutralModel:
    """The minimal immutable neutral model produced by a CAD importer.

    Deterministic entity lookup by identity and by source, duplicate-identity
    rejection, and read-only retention of (entities, warnings, unsupported).
    No topology tree and no persistence.
    """

    source: SourceDocumentIdentity
    root_frame: Frame
    entities: tuple[NeutralEntityEntry, ...]
    source_to_neutral: SourceToNeutralMapping
    warnings: tuple[CadWarning, ...]
    unsupported: tuple[UnsupportedContent, ...]

    def __init__(
        self,
        source: SourceDocumentIdentity,
        root_frame: Frame,
        entities: Optional[list[NeutralEntityEntry]] = None,
        source_to_neutral: Optional[SourceToNeutralMapping] = None,
        warnings: Optional[list[CadWarning]] = None,
        unsupported: Optional[list[UnsupportedContent]] = None,
    ) -> None:
        entities = entities or []
        seen: list[NeutralEntityIdentity] = []
        for entity in entities:
            if entity.identity in seen:
                raise DuplicateNeutralEntityError(
                    f"duplicate neutral identity {entity.identity.neutral_entity_key!r}"
                )
            seen.append(entity.identity)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "root_frame", root_frame)
        object.__setattr__(self, "entities", tuple(entities))
        object.__setattr__(
            self,
            "source_to_neutral",
            source_to_neutral or SourceToNeutralMapping(),
        )
        object.__setattr__(self, "warnings", tuple(warnings or ()))
        object.__setattr__(self, "unsupported", tuple(unsupported or ()))

    def entity_by_identity(
        self, identity: NeutralEntityIdentity
    ) -> Optional[NeutralEntityEntry]:
        """Return the entity with ``identity`` or ``None`` if absent."""
        for entity in self.entities:
            if entity.identity == identity:
                return entity
        return None

    def entity_by_source(
        self, source: SourceEntityIdentity
    ) -> Optional[NeutralEntityEntry]:
        """Return the entity mapped from ``source`` or ``None`` if absent."""
        neutral = self.source_to_neutral.source_to_neutral(source)
        if neutral is None:
            return None
        return self.entity_by_identity(neutral)