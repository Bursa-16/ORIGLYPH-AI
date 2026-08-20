"""CAD importer abstraction (Protocol) for Origlyph.

Stage 1C. Defines the minimal contract that all future CAD importers must
satisfy: ``import_document`` accepts a :class:`SourceDocumentIdentity` and
returns a :class:`NeutralModel`, or raises a fatal :class:`CadImportError`.

There is **no concrete importer, no parser, no SDK, no filesystem behavior,
and no geometry-kernel dependency** here. This is Protocol-only so that
vendor adapters can be added behind the contract later without touching domain
code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .identity import CadFormat, SourceDocumentIdentity
from .model import NeutralModel

__all__ = ["CadImporter"]


@runtime_checkable
class CadImporter(Protocol):
    """Contract for a CAD document importer.

    Attributes:

    * ``importer_id`` — stable identity of this importer.
    * ``importer_version`` — version string of this importer.
    * ``supported_formats`` — the non-empty set of :class:`CadFormat` values
      this importer can import.
    """

    importer_id: str
    importer_version: str
    supported_formats: frozenset[CadFormat]

    def can_import(self, source_document: SourceDocumentIdentity) -> bool:
        """Return whether this importer can import ``source_document``.

        Must return ``False`` (never raise) for a source document whose format
        is not in ``supported_formats`` or whose identity is unusable.
        """
        ...

    def import_document(
        self, source_document: SourceDocumentIdentity
    ) -> NeutralModel:
        """Import ``source_document`` into a :class:`NeutralModel`.

        Must raise a fatal :class:`CadImportError` on failure and must never
        return a partially-unsupported model without recording it in
        ``NeutralModel.warnings``/``NeutralModel.unsupported``.
        """
        ...