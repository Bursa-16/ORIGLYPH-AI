"""Tolerance workspace persistence adapter (Stage 16D)."""

from __future__ import annotations

import copy

from origlyph.tolerance.workspace_controller import (
    TOLERANCE_WORKSPACE_SCHEMA_VERSION,
    WorkspaceAnalysisResult,
    WorkspaceState,
    workspace_configuration_fingerprint,
    workspace_result_identities,
    workspace_state_from_snapshot,
    workspace_state_to_snapshot,
    workspace_summary_values,
)

from .exceptions import InvalidProjectError
from .models import OriglyphProject, ProjectMetadata, ToleranceState, build_project

__all__ = [
    "TOLERANCE_WORKSPACE_EXTENSION_KEY",
    "build_project_with_tolerance_workspace",
    "project_with_tolerance_workspace",
    "workspace_state_from_project",
]

TOLERANCE_WORKSPACE_EXTENSION_KEY = TOLERANCE_WORKSPACE_SCHEMA_VERSION


def build_project_with_tolerance_workspace(
    workspace_state: WorkspaceState,
    *,
    result: WorkspaceAnalysisResult | None = None,
    project_name: str | None = None,
    metadata: ProjectMetadata | None = None,
    transient_ui_state: object | None = None,
) -> OriglyphProject:
    """Build a project carrying an authoritative workspace snapshot."""
    _ignore_transient_ui_state(transient_ui_state)
    if metadata is not None and project_name is not None:
        raise InvalidProjectError("project_name cannot be combined with metadata")
    return build_project(
        metadata=(
            metadata if metadata is not None else ProjectMetadata(name=project_name)
        ),
        tolerance_state=_tolerance_state(workspace_state, result),
        extensions={
            TOLERANCE_WORKSPACE_EXTENSION_KEY: workspace_state_to_snapshot(
                workspace_state
            )
        },
    )


def project_with_tolerance_workspace(
    project: OriglyphProject,
    workspace_state: WorkspaceState,
    *,
    result: WorkspaceAnalysisResult | None = None,
    transient_ui_state: object | None = None,
) -> OriglyphProject:
    """Return a copy of a project with the workspace snapshot replaced."""
    _ignore_transient_ui_state(transient_ui_state)
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    extensions = copy.deepcopy(project.extensions)
    extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY] = workspace_state_to_snapshot(
        workspace_state
    )
    return build_project(
        metadata=project.metadata,
        cad_sources=project.cad_sources,
        datum_state=project.datum_state,
        tolerance_state=_tolerance_state(workspace_state, result),
        artifact_refs=project.artifact_refs,
        extensions=extensions,
    )


def workspace_state_from_project(project: OriglyphProject) -> WorkspaceState:
    """Read and verify the authoritative workspace snapshot from a project."""
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    if TOLERANCE_WORKSPACE_EXTENSION_KEY not in project.extensions:
        raise InvalidProjectError("project does not contain tolerance workspace state")
    try:
        state = workspace_state_from_snapshot(
            project.extensions[TOLERANCE_WORKSPACE_EXTENSION_KEY]
        )
    except Exception as exc:
        raise InvalidProjectError(f"invalid tolerance workspace state: {exc}") from exc
    if project.tolerance_state is None:
        raise InvalidProjectError("project tolerance_state is required for workspace")
    fingerprint = workspace_configuration_fingerprint(state)
    if project.tolerance_state.chain_name != state.chain_name:
        raise InvalidProjectError("workspace chain_name does not match tolerance_state")
    if project.tolerance_state.configuration_fingerprint != fingerprint:
        raise InvalidProjectError(
            "workspace fingerprint does not match tolerance_state"
        )
    return state


def _tolerance_state(
    workspace_state: WorkspaceState,
    result: WorkspaceAnalysisResult | None,
) -> ToleranceState:
    return ToleranceState(
        chain_name=workspace_state.chain_name,
        configuration_fingerprint=workspace_configuration_fingerprint(workspace_state),
        result_identities=workspace_result_identities(result),
        summary_values=workspace_summary_values(result),
    )


def _ignore_transient_ui_state(transient_ui_state: object | None) -> None:
    if transient_ui_state is not None:
        # Transient UI state is intentionally outside deterministic project identity.
        return
