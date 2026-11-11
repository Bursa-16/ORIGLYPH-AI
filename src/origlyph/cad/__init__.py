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
from .context import (
    FunctionalRelevanceDeclaration,
)
from .drawing_context import (
    DatumFeatureDeclaration,
    DrawingDatumReferenceFrameDeclaration,
)
from .evaluation import (
    CandidateEvaluation,
    evaluate_candidates,
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
from .role import (
    bind_datum_constraint,
    bind_datum_reference_frame,
)
from .stl import StlImporter
from .topology import (
    CanonicalTopologyModel,
    DanglingTopologyReferenceError,
    DuplicateTopologyIdError,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyOrientation,
    TopologyShell,
    TopologySolid,
    TopologyValidationError,
    TopologyVertex,
    TopologyWire,
)
from .topology_adapter import (
    CadTopologyAdapter,
    UnsupportedCadTopologyBackendError,
)

__all__ = [
    "BoundReference",
    "bind_reference",
    "bind_references",
    "bind_datum_constraint",
    "bind_datum_reference_frame",
    "evaluate_candidates",
    "CadFormat",
    "CadImporter",
    "CadImportError",
    "CadWarning",
    "CandidateEvaluation",
    "DatumFeatureDeclaration",
    "DomainIdentity",
    "DrawingDatumReferenceFrameDeclaration",
    "DuplicateNeutralEntityError",
    "DuplicateSourceEntityError",
    "FunctionalRelevanceDeclaration",
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
    "StlImporter",
    "UnsupportedCadFormatError",
    "UnsupportedCadTopologyBackendError",
    "UnsupportedContent",
    "UnsupportedSourceUnitError",
    "CanonicalTopologyModel",
    "CadTopologyAdapter",
    "DanglingTopologyReferenceError",
    "DuplicateTopologyIdError",
    "TopologyEdge",
    "TopologyEntityId",
    "TopologyFace",
    "TopologyOrientation",
    "TopologyShell",
    "TopologySolid",
    "TopologyValidationError",
    "TopologyVertex",
    "TopologyWire",
]