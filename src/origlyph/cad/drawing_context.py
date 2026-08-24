"""Drawing/source declaration naming a source entity as a datum feature.

Stage 7C. A :class:`DatumFeatureDeclaration` records exactly one attributed
statement: the identified drawing/source explicitly declares the target
source CAD entity as datum feature ``label``.

The datum feature label is NOT a datum role and carries no precedence. The
record does not make a candidate eligible, assign PRIMARY/SECONDARY/TERTIARY,
create a datum constraint or reference frame, rank or score anything, accept
a recommendation, or interpret ASME/ISO semantics. Standards-specific
interpretation is deferred to the governed standards-provider layer.

Identity contract: the target is the durable :class:`SourceEntityIdentity`.
Generated neutral entities have no source identity and are structurally
outside this record's scope.

Provenance is reached through ``target`` only; drawing-side attribution is
carried as plain attributed strings until a typed drawing-document identity
exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import SourceEntityIdentity

__all__ = ["DatumFeatureDeclaration"]


@dataclass(frozen=True)
class DatumFeatureDeclaration:
    """An attributed declaration naming a source entity as a datum feature.

    Stored state is exactly ``(target, label, transcriber, drawing_reference,
    location)``. See the module docstring for the complete semantic boundary.
    """

    target: SourceEntityIdentity
    label: str
    transcriber: str
    drawing_reference: str
    location: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, SourceEntityIdentity):
            raise TypeError("declaration target must be a SourceEntityIdentity")
        object.__setattr__(
            self, "label", _normalized_required_text(self.label, "label")
        )
        object.__setattr__(
            self,
            "transcriber",
            _normalized_required_text(self.transcriber, "transcriber"),
        )
        object.__setattr__(
            self,
            "drawing_reference",
            _normalized_required_text(self.drawing_reference, "drawing_reference"),
        )
        object.__setattr__(
            self, "location", _normalized_optional_text(self.location, "location")
        )


def _normalized_required_text(value: object, field_name: str) -> str:
    """Strip ``value``, requiring a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


def _normalized_optional_text(value: object, field_name: str) -> str | None:
    """Strip ``value``; ``None`` stays ``None``, blank normalizes to ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    stripped = value.strip()
    return stripped if stripped else None