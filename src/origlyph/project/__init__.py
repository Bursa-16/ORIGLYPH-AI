"""Origlyph persisted project model (Stage 16B)."""

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
