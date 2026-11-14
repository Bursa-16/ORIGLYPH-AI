"""Origlyph persisted project model (Stage 16B)."""

from .cad_source_bridge import (
    cad_source_reference_from_step,
    project_with_step_source,
)
from .datum_surface_validation import (
    SUPPORTED_VALIDATION_ENTITY_KINDS,
    DatumSurfaceValidationResult,
    DatumSurfaceValidationStatus,
    validate_datum_role_surface,
    validate_datum_surface,
)
from .datum_topology_binding import (
    BINDING_FORMAT_VERSION,
    BINDING_FORMAT_VERSION_V2,
    RESOLUTION_AMBIGUOUS,
    RESOLUTION_REMAPPED_EXACT,
    RESOLUTION_REMAPPED_PROBABLE,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNBOUND,
    RESOLUTION_UNRESOLVED_MISSING_ENTITY,
    RESOLUTION_UNRESOLVED_SOURCE_REVISION,
    SUPPORTED_DATUM_ENTITY_KINDS,
    DatumTopologyRef,
    DatumTopologyResolution,
    datum_role_assignment_with_topology,
    decode_datum_topology_ref,
    encode_datum_topology_ref,
    is_topology_binding,
    resolve_datum_topology_bindings,
)
from .exceptions import (
    InvalidProjectError,
    OriglyphProjectError,
    ProjectIntegrityError,
    UnsupportedProjectSchemaError,
)
from .models import (
    PROJECT_SCHEMA_VERSION,
    CadSourceReference,
    DatumRoleAssignment,
    DatumState,
    OriglyphProject,
    ProjectMetadata,
    ToleranceState,
    build_project,
)
from .persistence import load_project, save_project
from .serialization import (
    project_from_dict,
    project_from_json,
    project_to_canonical_json,
    project_to_json,
)
from .tolerance_workspace import (
    TOLERANCE_WORKSPACE_EXTENSION_KEY,
    build_project_with_tolerance_workspace,
    project_with_tolerance_workspace,
    workspace_state_from_project,
)
from .topology_revision_remap import (
    FaceRevisionMatch,
    RevisionMatchClass,
    RevisionRemapResult,
    remap_all_face_bindings,
    remap_face_binding,
)

__all__ = ["PROJECT_SCHEMA_VERSION", "CadSourceReference"]
__all__ += ["DatumRoleAssignment", "DatumState", "InvalidProjectError"]
__all__ += ["OriglyphProject", "OriglyphProjectError"]
__all__ += ["ProjectIntegrityError", "ProjectMetadata"]
__all__ += ["ToleranceState", "UnsupportedProjectSchemaError"]
__all__ += ["build_project", "load_project", "project_from_dict"]
__all__ += ["project_from_json", "project_to_canonical_json"]
__all__ += ["project_to_json", "save_project"]
__all__ += ["TOLERANCE_WORKSPACE_EXTENSION_KEY"]
__all__ += ["build_project_with_tolerance_workspace"]
__all__ += ["project_with_tolerance_workspace"]
__all__ += ["workspace_state_from_project"]
__all__ += ["cad_source_reference_from_step", "project_with_step_source"]
__all__ += ["BINDING_FORMAT_VERSION", "BINDING_FORMAT_VERSION_V2"]
__all__ += ["SUPPORTED_DATUM_ENTITY_KINDS"]
__all__ += ["RESOLUTION_RESOLVED", "RESOLUTION_UNBOUND"]
__all__ += ["RESOLUTION_UNRESOLVED_MISSING_ENTITY"]
__all__ += ["RESOLUTION_UNRESOLVED_SOURCE_REVISION"]
__all__ += ["RESOLUTION_REMAPPED_EXACT", "RESOLUTION_REMAPPED_PROBABLE"]
__all__ += ["RESOLUTION_AMBIGUOUS"]
__all__ += ["DatumTopologyRef", "DatumTopologyResolution"]
__all__ += ["datum_role_assignment_with_topology"]
__all__ += ["decode_datum_topology_ref", "encode_datum_topology_ref"]
__all__ += ["is_topology_binding", "resolve_datum_topology_bindings"]
__all__ += ["FaceRevisionMatch", "RevisionMatchClass", "RevisionRemapResult"]
__all__ += ["remap_all_face_bindings", "remap_face_binding"]
__all__ += ["SUPPORTED_VALIDATION_ENTITY_KINDS"]
__all__ += ["DatumSurfaceValidationStatus", "DatumSurfaceValidationResult"]
__all__ += ["validate_datum_surface", "validate_datum_role_surface"]
