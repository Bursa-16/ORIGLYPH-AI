"""Origlyph CAD import domain (Stage 1C).

Public contracts for entity identity, source-document identity, neutral
imported entities, source-to-neutral mapping, the neutral model, and the CAD
importer abstraction. Deliberately dependency-free beyond ``origlyph.geometry``
value contracts. Kernel abstraction is deferred to a later stage.
"""

from .binding import (
    BoundReference,
    bind_reference,
    bind_references,
)
from .exceptions import (
    CadImportError,
    DuplicateNeutralEntityError,
    DuplicateSourceEntityError,
    InvalidSourceIdentityError,
    OriglyphCadError,
    UnsupportedCadFormatError,
    UnsupportedSourceUnitError,
)
from .identity import (
    CadFormat,
    DomainIdentity,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceDocumentIdentity,
    SourceEntityIdentity,
    SourceUnitSystem,
)
from .importer import CadImporter
from .model import (
    CadWarning,
    NeutralEntityEntry,
    NeutralModel,
    SourceToNeutralMapping,
    UnsupportedContent,
)
from .role import bind_datum_constraint

__all__ = [
    "BoundReference",
    "bind_reference",
    "bind_references",
    "bind_datum_constraint",
    "CadFormat",
    "CadImporter",
    "CadImportError",
    "CadWarning",
    "DomainIdentity",
    "DuplicateNeutralEntityError",
    "DuplicateSourceEntityError",
    "InvalidSourceIdentityError",
    "NeutralEntityEntry",
    "NeutralEntityIdentity",
    "NeutralEntityKind",
    "NeutralModel",
    "OriglyphCadError",
    "SourceDocumentIdentity",
    "SourceEntityIdentity",
    "SourceToNeutralMapping",
    "SourceUnitSystem",
    "UnsupportedCadFormatError",
    "UnsupportedContent",
    "UnsupportedSourceUnitError",
]