"""Headless tolerance workspace controller (Stage 16D / 17A / 17B / 17C)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .allocation import validate_allocation as _stage15_validate_allocation
from .audit import (
    ToleranceDecisionAuditPackage,
)
from .audit import (
    audit_package_from_dict as _audit_package_from_dict,
)
from .audit import (
    build_decision_audit_package as _build_audit_package,
)
from .budget import worst_case_budget
from .change_impact import (
    AuditChangeImpactResult,
)
from .change_impact import (
    assess_audit_change_impact as _assess_change_impact,
)
from .comparison import (
    AuditPackageComparisonResult,
)
from .comparison import (
    compare_decision_audit_packages as _compare_audit_packages,
)
from .decision import evaluate_tolerance_decision
from .evidence import (
    DecisionEvidenceBundle,
    DecisionExplanation,
)
from .evidence import (
    build_decision_evidence as _build_decision_evidence,
)
from .evidence import (
    explain_tolerance_decision as _explain_tolerance_decision,
)
from .exceptions import OriglyphToleranceError
from .integrity import (
    AuditIntegrityResult,
)
from .integrity import (
    validate_decision_report_integrity as _validate_integrity,
)
from .models import (
    AllocationPlan,
    AllocationReconciliationResult,
    AllocationValidationResult,
    StackDirection,
    StatisticalAllocation,
    StatisticalAllocationPlan,
    StatisticalAllocationReconciliationResult,
    StatisticalContribution,
    StatisticalResult,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceDecisionResult,
    ToleranceStack,
    WorstCaseBudgetResult,
    WorstCaseResult,
)
from .reconciliation import reconcile_allocation as _reconcile_allocation
from .report import (
    ToleranceDecisionReport,
)
from .report import (
    build_decision_report as _build_decision_report,
)
from .sensitivity import (
    StatisticalSensitivityResult,
    WorstCaseSensitivityResult,
    statistical_sensitivity,
    worst_case_sensitivity,
)
from .statistical import statistical
from .statistical_reconciliation import (
    reconcile_statistical_allocation as _reconcile_statistical_allocation,
)
from .worst_case import worst_case

__all__ = [
    "TOLERANCE_WORKSPACE_SCHEMA_VERSION",
    "TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2",
    "TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3",
    "TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4",
    "AnalysisMode",
    "InvalidToleranceWorkspaceError",
    "WorkspaceAllocationEntry",
    "WorkspaceAllocationPlan",
    "WorkspaceAnalysisResult",
    "WorkspaceContributor",
    "WorkspaceSpecification",
    "WorkspaceState",
    "WorkspaceStatisticalAllocationEntry",
    "WorkspaceStatisticalAllocationPlan",
    "ToleranceWorkspaceController",
    "workspace_configuration_fingerprint",
    "workspace_result_identities",
    "workspace_state_from_snapshot",
    "workspace_state_to_snapshot",
    "workspace_summary_values",
]

TOLERANCE_WORKSPACE_SCHEMA_VERSION = "origlyph.tolerance.workspace.v1"
TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2 = "origlyph.tolerance.workspace.v2"
TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3 = "origlyph.tolerance.workspace.v3"
TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4 = "origlyph.tolerance.workspace.v4"
_SUPPORTED_TOLERANCE_MODEL = "symmetric"
_DEFAULT_SIGMA_MULTIPLIER = 1.0


class InvalidToleranceWorkspaceError(OriglyphToleranceError):
    """Raised when workspace input or persisted workspace state is invalid."""


class AnalysisMode(Enum):
    """Analysis modes supported by the Stage 16D workspace UI."""

    WORST_CASE = "worst_case"
    RSS_STATISTICAL = "rss_statistical"


@dataclass(frozen=True, slots=True)
class WorkspaceSpecification:
    """Immutable engineering specification limits for the workspace (Stage 17A).

    Both fields are optional.  When present each must be strictly positive and
    finite, matching the semantics of ``allowed_worst_case_span`` and
    ``allowed_combined_sigma`` in
    :func:`~origlyph.tolerance.evaluate_tolerance_decision`.

    This model carries engineering limits only.  It contains no tolerance
    calculation logic and no presentation state.
    """

    allowed_worst_case_span: float | None = None
    allowed_combined_sigma: float | None = None

    def __post_init__(self) -> None:
        if self.allowed_worst_case_span is not None:
            span = _require_finite(
                self.allowed_worst_case_span, field="allowed_worst_case_span"
            )
            if span <= 0.0:
                raise InvalidToleranceWorkspaceError(
                    "allowed_worst_case_span must be strictly positive"
                )
            object.__setattr__(self, "allowed_worst_case_span", span)
        if self.allowed_combined_sigma is not None:
            sigma = _require_finite(
                self.allowed_combined_sigma, field="allowed_combined_sigma"
            )
            if sigma <= 0.0:
                raise InvalidToleranceWorkspaceError(
                    "allowed_combined_sigma must be strictly positive"
                )
            object.__setattr__(self, "allowed_combined_sigma", sigma)

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed_worst_case_span": self.allowed_worst_case_span,
            "allowed_combined_sigma": self.allowed_combined_sigma,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceAllocationEntry:
    """One per-contributor entry in a workspace allocation plan (Stage 17E-1).

    Carries the user-supplied allocated tolerance span for a single contributor.
    ``contributor_id`` must match a :class:`WorkspaceContributor` identifier in
    the same workspace.

    This is a workspace-layer type.  It converts to
    :class:`~origlyph.tolerance.ToleranceAllocation` immediately before calling
    the Stage 15H validator.  Engine types do not appear in workspace persistence.
    """

    contributor_id: str
    allocated_span: float

    def __post_init__(self) -> None:
        _require_text(self.contributor_id, field="contributor_id")
        span = _require_finite(self.allocated_span, field="allocated_span")
        if span < 0.0:
            raise InvalidToleranceWorkspaceError(
                "allocated_span must be non-negative"
            )
        object.__setattr__(self, "allocated_span", span)

    def as_dict(self) -> dict[str, object]:
        return {
            "contributor_id": self.contributor_id,
            "allocated_span": self.allocated_span,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceAllocationPlan:
    """Authoritative per-contributor allocation plan for the workspace (Stage 17E-1).

    Carries the user-supplied total budget and a tuple of per-contributor
    allocated spans.  This is the authoritative engineering input for allocation
    validation.  It does not contain a generated or optimised allocation; the
    values are always user-supplied.

    Identity: any change to ``allowed_budget``, ``entries`` membership, or any
    ``allocated_span`` rotates the workspace configuration fingerprint and
    therefore the project identity.

    This is a workspace-layer type.  It converts to
    :class:`~origlyph.tolerance.AllocationPlan` immediately before calling the
    Stage 15H validator.  Engine types do not appear in workspace persistence.
    """

    allowed_budget: float
    entries: tuple[WorkspaceAllocationEntry, ...]

    def __post_init__(self) -> None:
        budget = _require_finite(self.allowed_budget, field="allowed_budget")
        if budget <= 0.0:
            raise InvalidToleranceWorkspaceError(
                "allowed_budget must be strictly positive"
            )
        object.__setattr__(self, "allowed_budget", budget)
        if not isinstance(self.entries, tuple):
            raise InvalidToleranceWorkspaceError("entries must be a tuple")
        seen_ids: set[str] = set()
        for index, entry in enumerate(self.entries):
            if not isinstance(entry, WorkspaceAllocationEntry):
                raise InvalidToleranceWorkspaceError(
                    f"entries[{index}] must be WorkspaceAllocationEntry"
                )
            if entry.contributor_id in seen_ids:
                raise InvalidToleranceWorkspaceError(
                    f"duplicate contributor_id in allocation entries: "
                    f"{entry.contributor_id!r}"
                )
            seen_ids.add(entry.contributor_id)

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed_budget": self.allowed_budget,
            "entries": [e.as_dict() for e in self.entries],
        }


@dataclass(frozen=True, slots=True)
class WorkspaceStatisticalAllocationEntry:
    """One per-contributor entry in a workspace statistical allocation plan (Stage 19D).

    Carries the user-supplied allocated sigma budget for a single contributor.
    ``contributor_id`` must match a :class:`WorkspaceContributor` identifier in
    the same workspace.

    This is a workspace-layer type.  It converts to
    :class:`~origlyph.tolerance.StatisticalAllocation` immediately before calling
    the Stage 15J reconciliation engine.  Engine types do not appear in workspace
    persistence.
    """

    contributor_id: str
    allocated_sigma: float

    def __post_init__(self) -> None:
        _require_text(self.contributor_id, field="contributor_id")
        sigma = _require_finite(self.allocated_sigma, field="allocated_sigma")
        if sigma < 0.0:
            raise InvalidToleranceWorkspaceError(
                "allocated_sigma must be non-negative"
            )
        object.__setattr__(self, "allocated_sigma", sigma)

    def as_dict(self) -> dict[str, object]:
        return {
            "contributor_id": self.contributor_id,
            "allocated_sigma": self.allocated_sigma,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceStatisticalAllocationPlan:
    """Authoritative statistical allocation plan for the workspace (Stage 19D).

    Carries the sigma multiplier, per-contributor allocated sigma budgets, and
    an optional total combined-sigma budget.  This is the authoritative
    engineering input for statistical reconciliation.  The values are always
    user-supplied; no optimization is performed.

    ``sigma_multiplier`` is the standard-deviation multiplier used for both
    the allocation-side variance computation and the authoritative statistical
    engine call inside reconciliation.  Common values are 1, 2, or 3.

    ``allowed_combined_sigma`` is optional.  When ``None``, the allocation-side
    combined sigma is the RSS of per-contributor allocated sigmas.

    Identity: any change to ``sigma_multiplier``, ``allowed_combined_sigma``,
    ``entries`` membership, or any ``allocated_sigma`` rotates the workspace
    configuration fingerprint and therefore the project identity.

    This is a workspace-layer type.  It converts to
    :class:`~origlyph.tolerance.StatisticalAllocationPlan` immediately before
    calling the Stage 15J engine.  Engine types do not appear in workspace
    persistence.

    V1 reconciliation: correlations are not modeled; the engine call uses
    ``correlations=None`` (explicit independence).
    """

    sigma_multiplier: float
    entries: tuple[WorkspaceStatisticalAllocationEntry, ...]
    allowed_combined_sigma: float | None = None

    def __post_init__(self) -> None:
        multiplier = _require_finite(self.sigma_multiplier, field="sigma_multiplier")
        if multiplier <= 0.0:
            raise InvalidToleranceWorkspaceError(
                "sigma_multiplier must be strictly positive"
            )
        object.__setattr__(self, "sigma_multiplier", multiplier)
        if not isinstance(self.entries, tuple):
            raise InvalidToleranceWorkspaceError("entries must be a tuple")
        seen_ids: set[str] = set()
        for index, entry in enumerate(self.entries):
            if not isinstance(entry, WorkspaceStatisticalAllocationEntry):
                raise InvalidToleranceWorkspaceError(
                    f"entries[{index}] must be WorkspaceStatisticalAllocationEntry"
                )
            if entry.contributor_id in seen_ids:
                raise InvalidToleranceWorkspaceError(
                    f"duplicate contributor_id in statistical allocation entries: "
                    f"{entry.contributor_id!r}"
                )
            seen_ids.add(entry.contributor_id)
        if self.allowed_combined_sigma is not None:
            sigma = _require_finite(
                self.allowed_combined_sigma, field="allowed_combined_sigma"
            )
            if sigma <= 0.0:
                raise InvalidToleranceWorkspaceError(
                    "allowed_combined_sigma must be strictly positive"
                )
            object.__setattr__(self, "allowed_combined_sigma", sigma)

    def as_dict(self) -> dict[str, object]:
        return {
            "sigma_multiplier": self.sigma_multiplier,
            "entries": [e.as_dict() for e in self.entries],
            "allowed_combined_sigma": self.allowed_combined_sigma,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceContributor:
    """One validated contributor row in the tolerance workspace."""

    identifier: str
    name: str
    nominal: float
    tolerance: float
    direction: StackDirection
    tolerance_model: str

    def __post_init__(self) -> None:
        _require_text(self.identifier, field="identifier")
        _require_text(self.name, field="name")
        object.__setattr__(
            self, "nominal", _require_finite(self.nominal, field="nominal")
        )
        tolerance = _require_finite(self.tolerance, field="tolerance")
        if tolerance < 0.0:
            raise InvalidToleranceWorkspaceError("tolerance must be non-negative")
        object.__setattr__(self, "tolerance", tolerance)
        object.__setattr__(self, "direction", _coerce_direction(self.direction))
        if self.tolerance_model != _SUPPORTED_TOLERANCE_MODEL:
            raise InvalidToleranceWorkspaceError(
                f"unsupported tolerance model {self.tolerance_model!r}"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "identifier": self.identifier,
            "name": self.name,
            "nominal": self.nominal,
            "tolerance": self.tolerance,
            "direction": self.direction.value,
            "tolerance_model": self.tolerance_model,
        }


def _validate_workspace_state_schema(
    schema_version: str,
    *,
    specification: object,
    allocation_plan: object,
    statistical_allocation_plan: object,
) -> None:
    _v1 = TOLERANCE_WORKSPACE_SCHEMA_VERSION
    _v2 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
    _v3 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
    _v4 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
    if schema_version not in (_v1, _v2, _v3, _v4):
        raise InvalidToleranceWorkspaceError(
            f"unsupported workspace schema {schema_version!r}"
        )
    if schema_version == _v1 and specification is not None:
        raise InvalidToleranceWorkspaceError(
            "workspace v1 does not support specification; use v2"
        )
    if schema_version in (_v1, _v2) and allocation_plan is not None:
        raise InvalidToleranceWorkspaceError(
            f"workspace {schema_version} does not support allocation_plan; use v3"
        )
    if schema_version in (_v1, _v2, _v3) and statistical_allocation_plan is not None:
        raise InvalidToleranceWorkspaceError(
            f"workspace {schema_version} does not support "
            "statistical_allocation_plan; use v4"
        )
    if specification is not None and not isinstance(
        specification, WorkspaceSpecification
    ):
        raise InvalidToleranceWorkspaceError(
            "specification must be WorkspaceSpecification or None"
        )
    if allocation_plan is not None and not isinstance(
        allocation_plan, WorkspaceAllocationPlan
    ):
        raise InvalidToleranceWorkspaceError(
            "allocation_plan must be WorkspaceAllocationPlan or None"
        )
    if statistical_allocation_plan is not None and not isinstance(
        statistical_allocation_plan, WorkspaceStatisticalAllocationPlan
    ):
        raise InvalidToleranceWorkspaceError(
            "statistical_allocation_plan must be "
            "WorkspaceStatisticalAllocationPlan or None"
        )


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    """Immutable authoritative workspace configuration.

    ``schema_version`` is one of:

    * :data:`TOLERANCE_WORKSPACE_SCHEMA_VERSION` (v1, no specification, no plan)
    * :data:`TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2` (v2, optional specification,
      no allocation plan)
    * :data:`TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3` (v3, optional specification,
      optional worst-case allocation plan)
    * :data:`TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4` (v4, optional specification,
      optional worst-case allocation plan, optional statistical allocation plan)

    V1 states always have ``specification=None`` and ``allocation_plan=None``.
    V2 states always have ``allocation_plan=None``.
    V1/V2/V3 states always have ``statistical_allocation_plan=None``.
    """

    schema_version: str
    chain_name: str
    analysis_mode: AnalysisMode
    contributors: tuple[WorkspaceContributor, ...]
    specification: WorkspaceSpecification | None = None
    allocation_plan: WorkspaceAllocationPlan | None = None
    statistical_allocation_plan: WorkspaceStatisticalAllocationPlan | None = None

    def __post_init__(self) -> None:
        _validate_workspace_state_schema(
            self.schema_version,
            specification=self.specification,
            allocation_plan=self.allocation_plan,
            statistical_allocation_plan=self.statistical_allocation_plan,
        )
        _require_text(self.chain_name, field="chain_name")
        object.__setattr__(
            self, "analysis_mode", _coerce_analysis_mode(self.analysis_mode)
        )
        if not isinstance(self.contributors, tuple):
            raise InvalidToleranceWorkspaceError("contributors must be a tuple")
        seen: set[str] = set()
        for index, item in enumerate(self.contributors):
            if not isinstance(item, WorkspaceContributor):
                raise InvalidToleranceWorkspaceError(
                    f"contributors[{index}] must be WorkspaceContributor"
                )
            if item.identifier in seen:
                raise InvalidToleranceWorkspaceError(
                    f"duplicate contributor identifier {item.identifier!r}"
                )
            seen.add(item.identifier)

    def as_dict(self) -> dict[str, object]:
        base: dict[str, object] = {
            "schema_version": self.schema_version,
            "chain_name": self.chain_name,
            "analysis_mode": self.analysis_mode.value,
            "contributors": [item.as_dict() for item in self.contributors],
        }
        _v2 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
        _v3 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
        _v4 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
        if self.schema_version in (_v2, _v3, _v4):
            spec_dict: object = (
                self.specification.as_dict() if self.specification is not None else None
            )
            base["specification"] = spec_dict
        if self.schema_version in (_v3, _v4):
            plan_dict: object = (
                self.allocation_plan.as_dict()
                if self.allocation_plan is not None
                else None
            )
            base["allocation_plan"] = plan_dict
        if self.schema_version == _v4:
            stat_plan_dict: object = (
                self.statistical_allocation_plan.as_dict()
                if self.statistical_allocation_plan is not None
                else None
            )
            base["statistical_allocation_plan"] = stat_plan_dict
        return base


@dataclass(frozen=True, slots=True)
class WorkspaceAnalysisResult:
    """Deterministic result mapping for UI presentation and project state."""

    analysis_mode: AnalysisMode
    result_id: str
    summary_values: dict[str, float]
    backend_result: WorstCaseResult | StatisticalResult

    def as_dict(self) -> dict[str, object]:
        return {
            "analysis_mode": self.analysis_mode.value,
            "result_id": self.result_id,
            "summary_values": dict(self.summary_values),
        }


class ToleranceWorkspaceController:
    """Headless controller for the tolerance workspace vertical slice."""

    def __init__(
        self,
        *,
        chain_name: str,
        analysis_mode: AnalysisMode | str,
        contributors: tuple[WorkspaceContributor, ...] = (),
        specification: WorkspaceSpecification | None = None,
    ) -> None:
        schema = (
            TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
            if specification is not None
            else TOLERANCE_WORKSPACE_SCHEMA_VERSION
        )
        self._state = WorkspaceState(
            schema_version=schema,
            chain_name=chain_name,
            analysis_mode=_coerce_analysis_mode(analysis_mode),
            contributors=contributors,
            specification=specification,
        )
        self._last_result: WorkspaceAnalysisResult | None = None
        self._last_decision: ToleranceDecisionResult | None = None
        self._last_sensitivity: (
            WorstCaseSensitivityResult | StatisticalSensitivityResult | None
        ) = None
        self._last_budget: WorstCaseBudgetResult | None = None
        self._last_allocation_validation: AllocationValidationResult | None = None
        self._last_reconciliation: AllocationReconciliationResult | None = None
        self._last_statistical_reconciliation: (
            StatisticalAllocationReconciliationResult | None
        ) = None
        self._last_evidence: DecisionEvidenceBundle | None = None
        self._last_explanation: DecisionExplanation | None = None
        self._last_decision_report: ToleranceDecisionReport | None = None
        self._last_audit_integrity: AuditIntegrityResult | None = None
        self._last_audit_package: ToleranceDecisionAuditPackage | None = None
        self._comparison_audit_package: ToleranceDecisionAuditPackage | None = None
        self._last_audit_comparison: AuditPackageComparisonResult | None = None
        self._last_change_impact: AuditChangeImpactResult | None = None

    @property
    def state(self) -> WorkspaceState:
        return self._state

    @property
    def contributors(self) -> tuple[WorkspaceContributor, ...]:
        return self._state.contributors

    @property
    def analysis_mode(self) -> AnalysisMode:
        return self._state.analysis_mode

    @property
    def specification(self) -> WorkspaceSpecification | None:
        return self._state.specification

    @property
    def last_result(self) -> WorkspaceAnalysisResult | None:
        return self._last_result

    @property
    def last_decision(self) -> ToleranceDecisionResult | None:
        return self._last_decision

    @property
    def last_sensitivity(
        self,
    ) -> WorstCaseSensitivityResult | StatisticalSensitivityResult | None:
        return self._last_sensitivity

    @property
    def last_budget(self) -> WorstCaseBudgetResult | None:
        return self._last_budget

    @property
    def last_allocation_validation(self) -> AllocationValidationResult | None:
        return self._last_allocation_validation

    @property
    def last_reconciliation(self) -> AllocationReconciliationResult | None:
        return self._last_reconciliation

    @property
    def last_statistical_reconciliation(
        self,
    ) -> StatisticalAllocationReconciliationResult | None:
        return self._last_statistical_reconciliation

    @property
    def last_evidence(self) -> DecisionEvidenceBundle | None:
        return self._last_evidence

    @property
    def last_explanation(self) -> DecisionExplanation | None:
        return self._last_explanation

    @property
    def last_decision_report(self) -> ToleranceDecisionReport | None:
        return self._last_decision_report

    @property
    def last_audit_integrity(self) -> AuditIntegrityResult | None:
        return self._last_audit_integrity

    @property
    def last_audit_package(self) -> ToleranceDecisionAuditPackage | None:
        return self._last_audit_package

    @property
    def comparison_audit_package(self) -> ToleranceDecisionAuditPackage | None:
        return self._comparison_audit_package

    @property
    def last_audit_comparison(self) -> AuditPackageComparisonResult | None:
        return self._last_audit_comparison

    @property
    def last_change_impact(self) -> AuditChangeImpactResult | None:
        return self._last_change_impact

    @property
    def statistical_allocation_plan(self) -> WorkspaceStatisticalAllocationPlan | None:
        return self._state.statistical_allocation_plan

    @classmethod
    def empty(
        cls, *, chain_name: str, analysis_mode: AnalysisMode | str
    ) -> ToleranceWorkspaceController:
        return cls(chain_name=chain_name, analysis_mode=analysis_mode)

    @classmethod
    def from_snapshot(cls, snapshot: object) -> ToleranceWorkspaceController:
        return cls.from_state(workspace_state_from_snapshot(snapshot))

    @classmethod
    def from_state(cls, state: WorkspaceState) -> ToleranceWorkspaceController:
        # Bypass __init__ to preserve the exact schema_version from the loaded state.
        # A v2 state with specification=None must not silently downgrade to v1.
        instance = cls.__new__(cls)
        instance._state = state
        instance._last_result = None
        instance._last_decision = None
        instance._last_sensitivity = None
        instance._last_budget = None
        instance._last_allocation_validation = None
        instance._last_reconciliation = None
        instance._last_statistical_reconciliation = None
        instance._last_evidence = None
        instance._last_explanation = None
        instance._last_decision_report = None
        instance._last_audit_integrity = None
        instance._last_audit_package = None
        instance._comparison_audit_package = None
        instance._last_audit_comparison = None
        instance._last_change_impact = None
        return instance

    @classmethod
    def open_project(cls, path: str | Path) -> ToleranceWorkspaceController:
        from origlyph.project.persistence import load_project
        from origlyph.project.tolerance_workspace import workspace_state_from_project

        return cls.from_state(workspace_state_from_project(load_project(path)))

    def save_project(
        self, path: str | Path, *, project_name: str | None = None
    ) -> Path:
        from origlyph.project.persistence import save_project
        from origlyph.project.tolerance_workspace import (
            build_project_with_tolerance_workspace,
        )

        project = build_project_with_tolerance_workspace(
            self._state,
            result=self._last_result,
            project_name=project_name,
        )
        return save_project(project, path)

    def snapshot(self) -> dict[str, object]:
        return workspace_state_to_snapshot(self._state)

    def configuration_fingerprint(self) -> str:
        return workspace_configuration_fingerprint(self._state)

    def set_chain_name(self, chain_name: str) -> None:
        name = _require_text(chain_name, field="chain_name")
        if name == self._state.chain_name:
            return
        self._state = replace(self._state, chain_name=name)
        self._last_result = None
        self._last_decision = None
        self._last_sensitivity = None
        self._last_budget = None
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None

    def set_analysis_mode(self, analysis_mode: AnalysisMode | str) -> None:
        mode = _coerce_analysis_mode(analysis_mode)
        if mode is self._state.analysis_mode:
            return
        self._state = replace(self._state, analysis_mode=mode)
        self._last_result = None
        self._last_decision = None
        self._last_sensitivity = None
        self._last_budget = None
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None

    def set_specification(
        self, specification: WorkspaceSpecification | None
    ) -> None:
        """Set or clear the engineering specification limits (Stage 17A).

        A change upgrades the workspace schema to v2 and invalidates any cached
        result.  Setting the same value as the current specification is a no-op.
        When ``specification`` is ``None`` the workspace retains v2 schema if it
        was already v2, or stays v1 if it was already v1 — no downgrade occurs.
        """
        if specification is not None and not isinstance(
            specification, WorkspaceSpecification
        ):
            raise InvalidToleranceWorkspaceError(
                "specification must be WorkspaceSpecification or None"
            )
        if specification == self._state.specification:
            return
        _v2 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2
        _v3 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
        _v4 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
        current = self._state.schema_version
        if specification is not None:
            # Preserve v3/v4 if already there; they carry allocation plan or
            # statistical allocation plan and cannot be downgraded to v2.
            new_schema = current if current in (_v3, _v4) else _v2
        elif current in (_v2, _v3, _v4):
            new_schema = current
        else:
            # v1 → clearing already-None spec: genuine no-op (guarded above).
            # This branch is unreachable; guard it for safety.
            return  # pragma: no cover
        self._state = replace(
            self._state, schema_version=new_schema, specification=specification
        )
        self._last_result = None
        self._last_decision = None
        self._last_budget = None
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None

    def add_contributor(
        self,
        *,
        identifier: str,
        name: str,
        nominal: object,
        tolerance: object,
        direction: StackDirection | str,
        tolerance_model: str,
    ) -> WorkspaceContributor:
        contributor = WorkspaceContributor(
            identifier=_require_text(identifier, field="identifier"),
            name=_require_text(name, field="name"),
            nominal=_require_finite(nominal, field="nominal"),
            tolerance=_require_finite(tolerance, field="tolerance"),
            direction=_coerce_direction(direction),
            tolerance_model=tolerance_model,
        )
        self._replace_contributors(self.contributors + (contributor,))
        return contributor

    def edit_contributor(
        self, identifier: str, **changes: object
    ) -> WorkspaceContributor:
        _require_text(identifier, field="identifier")
        items = list(self.contributors)
        for index, item in enumerate(items):
            if item.identifier == identifier:
                data = item.as_dict()
                data.update(changes)
                updated = _contributor_from_snapshot(data)
                items[index] = updated
                self._replace_contributors(tuple(items))
                return updated
        raise InvalidToleranceWorkspaceError(f"unknown contributor {identifier!r}")

    def remove_contributor(self, identifier: str) -> None:
        _require_text(identifier, field="identifier")
        remaining = tuple(
            item for item in self.contributors if item.identifier != identifier
        )
        if len(remaining) == len(self.contributors):
            raise InvalidToleranceWorkspaceError(f"unknown contributor {identifier!r}")
        self._replace_contributors(remaining)

    def run_analysis(self) -> WorkspaceAnalysisResult:
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor"
            )
        if self.analysis_mode is AnalysisMode.WORST_CASE:
            backend = worst_case(self._worst_case_stack())
            summary = {
                "nominal": backend.nominal,
                "minimum": backend.minimum,
                "maximum": backend.maximum,
                "lower_deviation": backend.lower_deviation,
                "upper_deviation": backend.upper_deviation,
                "total_span": backend.total_span,
            }
        elif self.analysis_mode is AnalysisMode.RSS_STATISTICAL:
            backend = statistical(
                self._statistical_stack(),
                sigma_multiplier=_DEFAULT_SIGMA_MULTIPLIER,
                correlations=(),
            )
            summary = {
                "nominal": backend.nominal,
                "combined_sigma": backend.combined_sigma,
                "sigma_multiplier": backend.sigma_multiplier,
                "lower_bound": backend.lower_bound,
                "upper_bound": backend.upper_bound,
            }
        else:  # pragma: no cover
            raise InvalidToleranceWorkspaceError(
                f"unsupported analysis mode {self.analysis_mode!r}"
            )
        _validate_summary(summary)
        result_id = _fingerprint(
            {
                "analysis_mode": self.analysis_mode.value,
                "configuration_fingerprint": self.configuration_fingerprint(),
                "summary_values": summary,
            },
            context="workspace result identity",
        )
        result = WorkspaceAnalysisResult(
            analysis_mode=self.analysis_mode,
            result_id=result_id,
            summary_values=summary,
            backend_result=backend,
        )
        self._last_result = result
        self._last_decision = None
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None
        return result

    def result_view(self) -> dict[str, object]:
        result = (
            self._last_result
            if self._last_result is not None
            else self.run_analysis()
        )
        return result.as_dict()

    def evaluate_decision(self) -> ToleranceDecisionResult:
        """Evaluate the deterministic tolerance decision using Stage 15K.

        Fail-closed: raises when analysis has not been run or when the
        applicable specification limit for the active mode is absent.
        No engineering formula is duplicated here; all calculation is
        delegated to :func:`~origlyph.tolerance.evaluate_tolerance_decision`.

        For worst-case mode: requires ``allowed_worst_case_span``.
        For RSS statistical mode: requires ``allowed_combined_sigma``
        and uses the same sigma multiplier as workspace analysis.
        """
        if self._last_result is None:
            raise InvalidToleranceWorkspaceError(
                "run analysis before evaluating a decision"
            )
        spec = self._state.specification
        mode = self._state.analysis_mode
        if mode is AnalysisMode.WORST_CASE:
            allowed_wc = spec.allowed_worst_case_span if spec is not None else None
            if allowed_wc is None:
                raise InvalidToleranceWorkspaceError(
                    "allowed_worst_case_span is required for worst-case decision"
                )
            decision = evaluate_tolerance_decision(
                worst_case_stack=self._worst_case_stack(),
                allowed_worst_case_span=allowed_wc,
            )
        elif mode is AnalysisMode.RSS_STATISTICAL:
            allowed_sigma = spec.allowed_combined_sigma if spec is not None else None
            if allowed_sigma is None:
                raise InvalidToleranceWorkspaceError(
                    "allowed_combined_sigma is required for RSS statistical decision"
                )
            decision = evaluate_tolerance_decision(
                statistical_stack=self._statistical_stack(),
                allowed_combined_sigma=allowed_sigma,
                sigma_multiplier=_DEFAULT_SIGMA_MULTIPLIER,
            )
        else:  # pragma: no cover
            raise InvalidToleranceWorkspaceError(
                f"unsupported analysis mode for decision: {mode!r}"
            )
        self._last_decision = decision
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None
        return decision

    def run_decision_evidence(
        self,
    ) -> tuple[DecisionEvidenceBundle, DecisionExplanation]:
        """Build deterministic decision evidence and explanation using Stage 15L.

        Delegates to :func:`~origlyph.tolerance.evidence.build_decision_evidence`
        and :func:`~origlyph.tolerance.evidence.explain_tolerance_decision`.
        Results are runtime-derived from the current decision snapshot; they are
        not persisted and do not affect project identity.

        Fail-closed: raises when no decision result is cached.  Call
        :meth:`evaluate_decision` first.

        No engineering math is duplicated here; evidence explains an existing
        authoritative result and does not recompute it.
        """
        if self._last_decision is None:
            raise InvalidToleranceWorkspaceError(
                "Run Decision first."
            )
        bundle = _build_decision_evidence(self._last_decision)
        explanation = _explain_tolerance_decision(self._last_decision, bundle)
        self._last_evidence = bundle
        self._last_explanation = explanation
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None
        return bundle, explanation

    def run_decision_report(self) -> ToleranceDecisionReport:
        """Build deterministic decision report using Stage 15M.

        Delegates to :func:`~origlyph.tolerance.report.build_decision_report`.
        Result is runtime-derived from the current decision, evidence and
        explanation snapshots; it is not persisted and does not affect project
        identity.

        Fail-closed: raises when decision or evidence/explanation is missing.
        Call :meth:`evaluate_decision` then :meth:`run_decision_evidence` first.

        No engineering math is duplicated here; the report organizes existing
        authoritative observations and does not recompute them.
        """
        if self._last_decision is None:
            raise InvalidToleranceWorkspaceError(
                "Run Decision first."
            )
        if self._last_evidence is None or self._last_explanation is None:
            raise InvalidToleranceWorkspaceError(
                "Generate Evidence first."
            )
        report = _build_decision_report(
            self._last_decision,
            self._last_evidence,
            self._last_explanation,
        )
        self._last_decision_report = report
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None
        return report

    def run_audit_integrity(self) -> AuditIntegrityResult:
        """Validate structural integrity of the decision report (Stage 15N).

        Delegates to
        :func:`~origlyph.tolerance.integrity.validate_decision_report_integrity`.
        Result is runtime-derived from the current report snapshot; it is not
        persisted and does not affect project identity.

        Fail-closed: raises when no decision report is cached.  Call
        :meth:`run_decision_report` first.

        No engineering math is duplicated here; integrity validation inspects
        the report envelope for structural consistency and does not recompute
        any tolerance calculation.
        """
        if self._last_decision_report is None:
            raise InvalidToleranceWorkspaceError(
                "Generate Decision Report first."
            )
        integrity = _validate_integrity(self._last_decision_report)
        self._last_audit_integrity = integrity
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None
        return integrity

    def run_audit_package(self) -> ToleranceDecisionAuditPackage:
        """Build deterministic audit package using Stage 15O.

        Delegates to
        :func:`~origlyph.tolerance.audit.build_decision_audit_package`.
        Uses cached integrity result if available; otherwise the backend
        computes it internally.  Result is runtime-derived; it is not persisted
        and does not affect project identity.

        Fail-closed: raises when no decision report is cached.  Call
        :meth:`run_decision_report` first.

        No fingerprint or hashing logic is duplicated here; all package
        construction is delegated to the Stage 15O backend.
        """
        if self._last_decision_report is None:
            raise InvalidToleranceWorkspaceError(
                "Generate Decision Report first."
            )
        package = _build_audit_package(
            self._last_decision_report,
            self._last_audit_integrity,
        )
        self._last_audit_package = package
        self._last_audit_comparison = None
        self._last_change_impact = None
        return package

    def load_comparison_audit_package(
        self, path: str | Path
    ) -> ToleranceDecisionAuditPackage:
        """Load a candidate audit package from a JSON file for comparison.

        Delegates deserialization and verification to
        :func:`~origlyph.tolerance.audit.audit_package_from_dict`.
        Fails closed for malformed or unverifiable packages
        (raises :exc:`~origlyph.tolerance.audit.InvalidDecisionAuditPackageError`).

        Clears any stale comparison result and change impact.  Does not require
        a current audit package to be cached — the two are loaded independently.

        No fingerprint or hashing logic is duplicated here.
        """
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise InvalidToleranceWorkspaceError(
                "Comparison package file must contain a JSON object."
            )
        package = _audit_package_from_dict(payload, verify=True)
        self._comparison_audit_package = package
        self._last_audit_comparison = None
        self._last_change_impact = None
        return package

    def run_audit_comparison(self) -> AuditPackageComparisonResult:
        """Compare current and candidate audit packages using Stage 15P.

        Delegates to
        :func:`~origlyph.tolerance.comparison.compare_decision_audit_packages`.
        Current package (baseline) is the cached :attr:`last_audit_package`.
        Candidate is the externally loaded :attr:`comparison_audit_package`.
        Result is runtime-derived; it is not persisted and does not affect
        project identity.

        Fail-closed: raises when either package is absent.  Call
        :meth:`run_audit_package` and :meth:`load_comparison_audit_package`
        first.

        No difference calculation is duplicated here; all comparison logic
        is delegated to the Stage 15P backend.
        """
        if self._last_audit_package is None:
            raise InvalidToleranceWorkspaceError(
                "Generate Audit Package first."
            )
        if self._comparison_audit_package is None:
            raise InvalidToleranceWorkspaceError(
                "Load Comparison Package first."
            )
        result = _compare_audit_packages(
            self._last_audit_package,
            self._comparison_audit_package,
        )
        self._last_audit_comparison = result
        self._last_change_impact = None
        return result

    def run_change_impact(self) -> AuditChangeImpactResult:
        """Assess change impact of a Stage 15P comparison result (Stage 15Q).

        Delegates to
        :func:`~origlyph.tolerance.change_impact.assess_audit_change_impact`.
        Result is runtime-derived from the cached comparison result; it is not
        persisted and does not affect project identity.

        Fail-closed: raises when no comparison result is cached.  Call
        :meth:`run_audit_comparison` first.

        No impact classification is duplicated here; all assessment logic is
        delegated to the Stage 15Q backend.
        """
        if self._last_audit_comparison is None:
            raise InvalidToleranceWorkspaceError(
                "Run Audit Comparison first."
            )
        impact = _assess_change_impact(self._last_audit_comparison)
        self._last_change_impact = impact
        return impact

    def run_sensitivity(
        self,
    ) -> WorstCaseSensitivityResult | StatisticalSensitivityResult:
        """Run deterministic sensitivity analysis using Stage 15F.

        Fail-closed: raises when there are no contributors.
        No engineering formula is duplicated here; all calculation is
        delegated to the Stage 15F sensitivity API.

        For worst-case mode: delegates to
        :func:`~origlyph.tolerance.worst_case_sensitivity`.
        For RSS statistical mode: delegates to
        :func:`~origlyph.tolerance.statistical_sensitivity`
        using the same sigma multiplier as workspace analysis.
        """
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor"
            )
        mode = self._state.analysis_mode
        if mode is AnalysisMode.WORST_CASE:
            result = worst_case_sensitivity(self._worst_case_stack())
        elif mode is AnalysisMode.RSS_STATISTICAL:
            result = statistical_sensitivity(
                self._statistical_stack(),
                sigma_multiplier=_DEFAULT_SIGMA_MULTIPLIER,
                correlations=(),
            )
        else:  # pragma: no cover
            raise InvalidToleranceWorkspaceError(
                f"unsupported analysis mode for sensitivity: {mode!r}"
            )
        self._last_sensitivity = result
        return result

    def run_budget(self) -> WorstCaseBudgetResult:
        """Run deterministic worst-case tolerance budget analysis using Stage 15G.

        Fail-closed: raises when there are no contributors, when
        ``allowed_worst_case_span`` is absent, or when the active analysis
        mode does not support budget analysis in Stage 17D.
        No engineering formula is duplicated here; all calculation is
        delegated to :func:`~origlyph.tolerance.worst_case_budget`.

        Only WORST_CASE mode is supported.  RSS statistical budget requires a
        dedicated allowed-span input not yet represented in workspace v2 and
        is deferred to a later stage.
        """
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor"
            )
        mode = self._state.analysis_mode
        if mode is AnalysisMode.RSS_STATISTICAL:
            raise InvalidToleranceWorkspaceError(
                "RSS statistical budget requires a separate allowed span input "
                "not represented in workspace v2; deferred to a later stage"
            )
        if mode is not AnalysisMode.WORST_CASE:  # pragma: no cover
            raise InvalidToleranceWorkspaceError(
                f"unsupported analysis mode for budget: {mode!r}"
            )
        spec = self._state.specification
        allowed_wc = spec.allowed_worst_case_span if spec is not None else None
        if allowed_wc is None:
            raise InvalidToleranceWorkspaceError(
                "allowed_worst_case_span is required for worst-case budget"
            )
        result = worst_case_budget(self._worst_case_stack(), allowed_wc)
        self._last_budget = result
        return result

    def validate_allocation(self) -> AllocationValidationResult:
        """Validate the workspace allocation plan (Stage 17E-2).

        Adapts the workspace v3 ``allocation_plan`` to the Stage 15 engine types,
        delegates to :func:`~origlyph.tolerance.allocation.validate_allocation`,
        and caches the result as derived runtime evidence.

        Fail-closed:

        - Raises :class:`InvalidToleranceWorkspaceError` when ``allocation_plan``
          is absent.
        - Raises :class:`InvalidToleranceWorkspaceError` when any allocation
          entry references a contributor not present in the workspace.
        - Propagates :class:`~origlyph.tolerance.InvalidAllocationError` from
          Stage 15 on completeness failure (missing contributors in the plan).

        Does not mutate the allocation plan.
        Does not perform auto-allocation or optimization.
        Running validation alone does not rotate the project identity.
        """
        plan = self._state.allocation_plan
        if plan is None:
            raise InvalidToleranceWorkspaceError(
                "allocation_plan is required to validate allocation"
            )
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor for allocation validation"
            )
        contributor_ids = {c.identifier for c in self.contributors}
        for entry in plan.entries:
            if entry.contributor_id not in contributor_ids:
                raise InvalidToleranceWorkspaceError(
                    f"allocation entry references unknown contributor "
                    f"{entry.contributor_id!r}"
                )
        stage15_plan = AllocationPlan(
            allowed_budget=plan.allowed_budget,
            allocations=tuple(
                ToleranceAllocation(
                    contributor_id=e.contributor_id,
                    allocated_span=e.allocated_span,
                )
                for e in plan.entries
            ),
        )
        result = _stage15_validate_allocation(self._worst_case_stack(), stage15_plan)
        self._last_allocation_validation = result
        return result

    def run_reconciliation(self) -> AllocationReconciliationResult:
        """Reconcile the allocation plan against actual contributor spans (Stage 15I).

        Adapts the workspace v3 ``allocation_plan`` to the Stage 15 engine types,
        delegates to :func:`~origlyph.tolerance.reconciliation.reconcile_allocation`,
        and caches the result as derived runtime evidence.

        Fail-closed:

        - Raises :class:`InvalidToleranceWorkspaceError` when ``allocation_plan``
          is absent.
        - Raises :class:`InvalidToleranceWorkspaceError` when no contributors
          are defined.
        - Raises :class:`InvalidToleranceWorkspaceError` when any allocation
          entry references a contributor not present in the workspace.
        - Propagates :class:`~origlyph.tolerance.InvalidAllocationError` from
          Stage 15 on completeness or validity failure.

        Does not mutate the allocation plan.
        Does not perform auto-allocation or optimization.
        """
        plan = self._state.allocation_plan
        if plan is None:
            raise InvalidToleranceWorkspaceError(
                "allocation_plan is required to run reconciliation"
            )
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor for reconciliation"
            )
        contributor_ids = {c.identifier for c in self.contributors}
        for entry in plan.entries:
            if entry.contributor_id not in contributor_ids:
                raise InvalidToleranceWorkspaceError(
                    f"allocation entry references unknown contributor "
                    f"{entry.contributor_id!r}"
                )
        stage15_plan = AllocationPlan(
            allowed_budget=plan.allowed_budget,
            allocations=tuple(
                ToleranceAllocation(
                    contributor_id=e.contributor_id,
                    allocated_span=e.allocated_span,
                )
                for e in plan.entries
            ),
        )
        result = _reconcile_allocation(self._worst_case_stack(), stage15_plan)
        self._last_reconciliation = result
        return result

    def set_allocation_plan(
        self, plan: WorkspaceAllocationPlan | None
    ) -> None:
        """Set or clear the authoritative allocation plan (Stage 17E-1).

        A change upgrades the workspace schema to v3 and records the new plan
        as authoritative engineering state.  Setting the same plan is a no-op.
        Clearing (``plan=None``) on a v3 workspace keeps v3 — no downgrade occurs,
        consistent with the v2 / specification precedent.

        This method carries the plan into workspace state only.  It does not
        validate the plan against the tolerance stack; that is Stage 17E-2.
        """
        if plan is not None and not isinstance(plan, WorkspaceAllocationPlan):
            raise InvalidToleranceWorkspaceError(
                "allocation_plan must be WorkspaceAllocationPlan or None"
            )
        if plan == self._state.allocation_plan:
            return
        current_schema = self._state.schema_version
        _v3 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3
        _v4 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
        if plan is not None:
            # Preserve v4 if already there; it carries statistical_allocation_plan.
            new_schema = _v4 if current_schema == _v4 else _v3
        elif current_schema in (_v3, _v4):
            new_schema = current_schema
        else:
            # v1 or v2, clearing already-None plan: guarded above (no-op).
            return  # pragma: no cover
        self._state = replace(
            self._state, schema_version=new_schema, allocation_plan=plan
        )
        self._last_allocation_validation = None
        self._last_reconciliation = None

    def clear_allocation_plan(self) -> None:
        """Clear the authoritative allocation plan (Stage 17E-1).

        Equivalent to ``set_allocation_plan(None)``.
        """
        self.set_allocation_plan(None)

    @property
    def allocation_plan(self) -> WorkspaceAllocationPlan | None:
        return self._state.allocation_plan

    def set_statistical_allocation_plan(
        self, plan: WorkspaceStatisticalAllocationPlan | None
    ) -> None:
        """Set or clear the authoritative statistical allocation plan (Stage 19D).

        A change upgrades the workspace schema to v4 and records the new plan
        as authoritative engineering state.  Setting the same plan is a no-op.
        Clearing (``plan=None``) on a v4 workspace keeps v4 — no downgrade occurs,
        consistent with the v3 / allocation_plan precedent.

        This method carries the plan into workspace state only.  It does not
        run statistical reconciliation; that is ``run_statistical_reconciliation``.
        """
        if plan is not None and not isinstance(
            plan, WorkspaceStatisticalAllocationPlan
        ):
            raise InvalidToleranceWorkspaceError(
                "statistical_allocation_plan must be "
                "WorkspaceStatisticalAllocationPlan or None"
            )
        if plan == self._state.statistical_allocation_plan:
            return
        current_schema = self._state.schema_version
        _v4 = TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4
        if plan is not None:
            new_schema = _v4
        elif current_schema == _v4:
            new_schema = _v4
        else:
            # v1/v2/v3, clearing already-None plan: guarded above (no-op).
            return  # pragma: no cover
        self._state = replace(
            self._state,
            schema_version=new_schema,
            statistical_allocation_plan=plan,
        )
        self._last_statistical_reconciliation = None

    def clear_statistical_allocation_plan(self) -> None:
        """Clear the authoritative statistical allocation plan (Stage 19D).

        Equivalent to ``set_statistical_allocation_plan(None)``.
        """
        self.set_statistical_allocation_plan(None)

    def run_statistical_reconciliation(
        self,
    ) -> StatisticalAllocationReconciliationResult:
        """Reconcile the statistical allocation plan against actual sigma (Stage 15J).

        Adapts the workspace v4 ``statistical_allocation_plan`` to the Stage 15
        engine types, delegates to
        :func:`~origlyph.tolerance.reconcile_statistical_allocation`,
        and caches the result as derived runtime evidence.

        V1 correlation model: ``correlations=None`` (all contributors independent).

        Fail-closed:

        - Raises :class:`InvalidToleranceWorkspaceError` when
          ``statistical_allocation_plan`` is absent.
        - Raises :class:`InvalidToleranceWorkspaceError` when no contributors
          are defined.
        - Raises :class:`InvalidToleranceWorkspaceError` when any entry references
          a contributor not present in the workspace.
        - Propagates :class:`~origlyph.tolerance.InvalidStatisticalAllocationError`
          from Stage 15 on plan validity failure.

        Does not mutate the statistical allocation plan.
        Does not perform auto-allocation or optimization.
        """
        plan = self._state.statistical_allocation_plan
        if plan is None:
            raise InvalidToleranceWorkspaceError(
                "statistical_allocation_plan is required to run "
                "statistical reconciliation"
            )
        if not self.contributors:
            raise InvalidToleranceWorkspaceError(
                "workspace requires at least one contributor for "
                "statistical reconciliation"
            )
        contributor_ids = {c.identifier for c in self.contributors}
        for entry in plan.entries:
            if entry.contributor_id not in contributor_ids:
                raise InvalidToleranceWorkspaceError(
                    f"statistical allocation entry references unknown contributor "
                    f"{entry.contributor_id!r}"
                )
        stage15_plan = StatisticalAllocationPlan(
            sigma_multiplier=plan.sigma_multiplier,
            allocations=tuple(
                StatisticalAllocation(
                    contributor_id=e.contributor_id,
                    allocated_sigma=e.allocated_sigma,
                )
                for e in plan.entries
            ),
            allowed_combined_sigma=plan.allowed_combined_sigma,
        )
        result = _reconcile_statistical_allocation(
            self._statistical_stack(), stage15_plan, correlations=None
        )
        self._last_statistical_reconciliation = result
        return result

    def _replace_contributors(
        self, contributors: tuple[WorkspaceContributor, ...]
    ) -> None:
        self._state = replace(self._state, contributors=contributors)
        self._last_result = None
        self._last_decision = None
        self._last_sensitivity = None
        self._last_budget = None
        self._last_allocation_validation = None
        self._last_reconciliation = None
        self._last_statistical_reconciliation = None
        self._last_evidence = None
        self._last_explanation = None
        self._last_decision_report = None
        self._last_audit_integrity = None
        self._last_audit_package = None
        self._last_audit_comparison = None
        self._last_change_impact = None

    def _worst_case_stack(self) -> ToleranceStack:
        return ToleranceStack(
            contributions=tuple(
                ToleranceContribution(
                    name=item.identifier,
                    nominal=item.nominal,
                    lower_deviation=-item.tolerance,
                    upper_deviation=item.tolerance,
                    direction=item.direction,
                )
                for item in self.contributors
            )
        )

    def _statistical_stack(self) -> StatisticalStack:
        return StatisticalStack(
            contributions=tuple(
                StatisticalContribution(
                    name=item.identifier,
                    nominal=item.nominal,
                    sigma=item.tolerance,
                    direction=item.direction,
                )
                for item in self.contributors
            )
        )


def workspace_state_to_snapshot(state: WorkspaceState) -> dict[str, object]:
    if not isinstance(state, WorkspaceState):
        raise InvalidToleranceWorkspaceError("state must be WorkspaceState")
    _canonical_json(state.as_dict(), context="workspace snapshot")
    return state.as_dict()


def workspace_state_from_snapshot(snapshot: object) -> WorkspaceState:
    data = _require_dict(snapshot, field="workspace snapshot")
    raw_schema = data.get("schema_version")
    if raw_schema == TOLERANCE_WORKSPACE_SCHEMA_VERSION:
        return _workspace_state_v1_from_dict(data)
    elif raw_schema == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V2:
        return _workspace_state_v2_from_dict(data)
    elif raw_schema == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V3:
        return _workspace_state_v3_from_dict(data)
    elif raw_schema == TOLERANCE_WORKSPACE_SCHEMA_VERSION_V4:
        return _workspace_state_v4_from_dict(data)
    else:
        raise InvalidToleranceWorkspaceError(
            f"unsupported workspace schema {raw_schema!r}"
        )


def workspace_configuration_fingerprint(state: WorkspaceState) -> str:
    return _fingerprint(
        workspace_state_to_snapshot(state), context="workspace configuration"
    )


def workspace_result_identities(
    result: WorkspaceAnalysisResult | None,
) -> tuple[str, ...]:
    if result is None:
        return ()
    _require_sha(result.result_id, field="result_id")
    return (result.result_id,)


def workspace_summary_values(
    result: WorkspaceAnalysisResult | None,
) -> dict[str, float]:
    if result is None:
        return {}
    _validate_summary(result.summary_values)
    return dict(result.summary_values)


def _workspace_state_v1_from_dict(data: dict[str, Any]) -> WorkspaceState:
    _require_exact_keys(
        data,
        {"schema_version", "chain_name", "analysis_mode", "contributors"},
        field="workspace snapshot",
    )
    raw_contributors = data["contributors"]
    if not isinstance(raw_contributors, list):
        raise InvalidToleranceWorkspaceError("contributors must be a list")
    return WorkspaceState(
        schema_version=data["schema_version"],
        chain_name=_require_text(data["chain_name"], field="chain_name"),
        analysis_mode=_coerce_analysis_mode(data["analysis_mode"]),
        contributors=tuple(
            _contributor_from_snapshot(item) for item in raw_contributors
        ),
        specification=None,
    )


def _workspace_state_v2_from_dict(data: dict[str, Any]) -> WorkspaceState:
    _require_exact_keys(
        data,
        {
            "schema_version", "chain_name", "analysis_mode",
            "contributors", "specification",
        },
        field="workspace snapshot v2",
    )
    raw_contributors = data["contributors"]
    if not isinstance(raw_contributors, list):
        raise InvalidToleranceWorkspaceError("contributors must be a list")
    raw_spec = data["specification"]
    if raw_spec is None:
        specification = None
    elif isinstance(raw_spec, dict):
        specification = _workspace_specification_from_dict(raw_spec)
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace specification must be a dict or null"
        )
    return WorkspaceState(
        schema_version=data["schema_version"],
        chain_name=_require_text(data["chain_name"], field="chain_name"),
        analysis_mode=_coerce_analysis_mode(data["analysis_mode"]),
        contributors=tuple(
            _contributor_from_snapshot(item) for item in raw_contributors
        ),
        specification=specification,
    )


def _workspace_state_v3_from_dict(data: dict[str, Any]) -> WorkspaceState:
    _require_exact_keys(
        data,
        {
            "schema_version", "chain_name", "analysis_mode",
            "contributors", "specification", "allocation_plan",
        },
        field="workspace snapshot v3",
    )
    raw_contributors = data["contributors"]
    if not isinstance(raw_contributors, list):
        raise InvalidToleranceWorkspaceError("contributors must be a list")
    raw_spec = data["specification"]
    if raw_spec is None:
        specification = None
    elif isinstance(raw_spec, dict):
        specification = _workspace_specification_from_dict(raw_spec)
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace specification must be a dict or null"
        )
    raw_plan = data["allocation_plan"]
    if raw_plan is None:
        allocation_plan = None
    elif isinstance(raw_plan, dict):
        allocation_plan = _workspace_allocation_plan_from_dict(raw_plan)
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace allocation_plan must be a dict or null"
        )
    return WorkspaceState(
        schema_version=data["schema_version"],
        chain_name=_require_text(data["chain_name"], field="chain_name"),
        analysis_mode=_coerce_analysis_mode(data["analysis_mode"]),
        contributors=tuple(
            _contributor_from_snapshot(item) for item in raw_contributors
        ),
        specification=specification,
        allocation_plan=allocation_plan,
    )


def _workspace_specification_from_dict(data: object) -> WorkspaceSpecification:
    d = _require_dict(data, field="workspace specification")
    _require_exact_keys(
        d,
        {"allowed_worst_case_span", "allowed_combined_sigma"},
        field="workspace specification",
    )
    wc = d["allowed_worst_case_span"]
    sigma = d["allowed_combined_sigma"]
    return WorkspaceSpecification(
        allowed_worst_case_span=(
            None if wc is None else _require_finite(wc, field="allowed_worst_case_span")
        ),
        allowed_combined_sigma=(
            None
            if sigma is None
            else _require_finite(sigma, field="allowed_combined_sigma")
        ),
    )


def _workspace_allocation_entry_from_dict(data: object) -> WorkspaceAllocationEntry:
    d = _require_dict(data, field="workspace allocation entry")
    _require_exact_keys(
        d,
        {"contributor_id", "allocated_span"},
        field="workspace allocation entry",
    )
    return WorkspaceAllocationEntry(
        contributor_id=_require_text(d["contributor_id"], field="contributor_id"),
        allocated_span=_require_finite(d["allocated_span"], field="allocated_span"),
    )


def _workspace_allocation_plan_from_dict(data: object) -> WorkspaceAllocationPlan:
    d = _require_dict(data, field="workspace allocation plan")
    _require_exact_keys(
        d,
        {"allowed_budget", "entries"},
        field="workspace allocation plan",
    )
    raw_entries = d["entries"]
    if not isinstance(raw_entries, list):
        raise InvalidToleranceWorkspaceError("allocation plan entries must be a list")
    return WorkspaceAllocationPlan(
        allowed_budget=_require_finite(d["allowed_budget"], field="allowed_budget"),
        entries=tuple(
            _workspace_allocation_entry_from_dict(e) for e in raw_entries
        ),
    )


def _workspace_state_v4_from_dict(data: dict[str, Any]) -> WorkspaceState:
    _require_exact_keys(
        data,
        {
            "schema_version", "chain_name", "analysis_mode",
            "contributors", "specification", "allocation_plan",
            "statistical_allocation_plan",
        },
        field="workspace snapshot v4",
    )
    raw_contributors = data["contributors"]
    if not isinstance(raw_contributors, list):
        raise InvalidToleranceWorkspaceError("contributors must be a list")
    raw_spec = data["specification"]
    if raw_spec is None:
        specification = None
    elif isinstance(raw_spec, dict):
        specification = _workspace_specification_from_dict(raw_spec)
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace specification must be a dict or null"
        )
    raw_plan = data["allocation_plan"]
    if raw_plan is None:
        allocation_plan = None
    elif isinstance(raw_plan, dict):
        allocation_plan = _workspace_allocation_plan_from_dict(raw_plan)
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace allocation_plan must be a dict or null"
        )
    raw_stat_plan = data["statistical_allocation_plan"]
    if raw_stat_plan is None:
        statistical_allocation_plan = None
    elif isinstance(raw_stat_plan, dict):
        statistical_allocation_plan = _workspace_statistical_allocation_plan_from_dict(
            raw_stat_plan
        )
    else:
        raise InvalidToleranceWorkspaceError(
            "workspace statistical_allocation_plan must be a dict or null"
        )
    return WorkspaceState(
        schema_version=data["schema_version"],
        chain_name=_require_text(data["chain_name"], field="chain_name"),
        analysis_mode=_coerce_analysis_mode(data["analysis_mode"]),
        contributors=tuple(
            _contributor_from_snapshot(item) for item in raw_contributors
        ),
        specification=specification,
        allocation_plan=allocation_plan,
        statistical_allocation_plan=statistical_allocation_plan,
    )


def _workspace_statistical_allocation_entry_from_dict(
    data: object,
) -> WorkspaceStatisticalAllocationEntry:
    d = _require_dict(data, field="workspace statistical allocation entry")
    _require_exact_keys(
        d,
        {"contributor_id", "allocated_sigma"},
        field="workspace statistical allocation entry",
    )
    return WorkspaceStatisticalAllocationEntry(
        contributor_id=_require_text(d["contributor_id"], field="contributor_id"),
        allocated_sigma=_require_finite(d["allocated_sigma"], field="allocated_sigma"),
    )


def _workspace_statistical_allocation_plan_from_dict(
    data: object,
) -> WorkspaceStatisticalAllocationPlan:
    d = _require_dict(data, field="workspace statistical allocation plan")
    _require_exact_keys(
        d,
        {"sigma_multiplier", "entries", "allowed_combined_sigma"},
        field="workspace statistical allocation plan",
    )
    raw_entries = d["entries"]
    if not isinstance(raw_entries, list):
        raise InvalidToleranceWorkspaceError(
            "statistical allocation plan entries must be a list"
        )
    raw_acs = d["allowed_combined_sigma"]
    allowed_combined_sigma = (
        None
        if raw_acs is None
        else _require_finite(raw_acs, field="allowed_combined_sigma")
    )
    return WorkspaceStatisticalAllocationPlan(
        sigma_multiplier=_require_finite(
            d["sigma_multiplier"], field="sigma_multiplier"
        ),
        entries=tuple(
            _workspace_statistical_allocation_entry_from_dict(e) for e in raw_entries
        ),
        allowed_combined_sigma=allowed_combined_sigma,
    )


def _contributor_from_snapshot(snapshot: object) -> WorkspaceContributor:
    data = _require_dict(snapshot, field="workspace contributor")
    _require_exact_keys(
        data,
        {"identifier", "name", "nominal", "tolerance", "direction", "tolerance_model"},
        field="workspace contributor",
    )
    return WorkspaceContributor(
        identifier=_require_text(data["identifier"], field="identifier"),
        name=_require_text(data["name"], field="name"),
        nominal=_require_finite(data["nominal"], field="nominal"),
        tolerance=_require_finite(data["tolerance"], field="tolerance"),
        direction=_coerce_direction(data["direction"]),
        tolerance_model=_require_text(data["tolerance_model"], field="tolerance_model"),
    )


def _canonical_json(payload: object, *, context: str) -> str:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidToleranceWorkspaceError(
            f"{context} is not finite canonical JSON: {exc}"
        ) from exc


def _fingerprint(payload: object, *, context: str) -> str:
    encoded = _canonical_json(payload, context=context).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_dict(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidToleranceWorkspaceError(f"{field} must be a dict")
    return value


def _require_exact_keys(
    data: dict[str, Any], expected: set[str], *, field: str
) -> None:
    actual = set(data)
    if actual != expected:
        raise InvalidToleranceWorkspaceError(
            f"{field} keys invalid; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip() != value:
        raise InvalidToleranceWorkspaceError(
            f"{field} must be a non-empty canonical string"
        )
    return value


def _require_finite(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise InvalidToleranceWorkspaceError(f"{field} must be numeric")
    if isinstance(value, str) and not value.strip():
        raise InvalidToleranceWorkspaceError(f"{field} must be numeric")
    try:
        numeric = float(value)
    except ValueError as exc:
        raise InvalidToleranceWorkspaceError(f"{field} must be numeric") from exc
    if not math.isfinite(numeric):
        raise InvalidToleranceWorkspaceError(f"{field} must be finite")
    return numeric


def _coerce_direction(value: StackDirection | str) -> StackDirection:
    if isinstance(value, StackDirection):
        return value
    if isinstance(value, str):
        try:
            return StackDirection(value)
        except ValueError as exc:
            raise InvalidToleranceWorkspaceError(
                f"unsupported direction {value!r}"
            ) from exc
    raise InvalidToleranceWorkspaceError("direction must be StackDirection or string")


def _coerce_analysis_mode(value: AnalysisMode | str) -> AnalysisMode:
    if isinstance(value, AnalysisMode):
        return value
    if isinstance(value, str):
        try:
            return AnalysisMode(value)
        except ValueError as exc:
            raise InvalidToleranceWorkspaceError(
                f"unsupported analysis mode {value!r}"
            ) from exc
    raise InvalidToleranceWorkspaceError("analysis_mode must be AnalysisMode or string")


def _require_sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise InvalidToleranceWorkspaceError(f"{field} must be lowercase sha256 hex")
    if any(char not in "0123456789abcdef" for char in value):
        raise InvalidToleranceWorkspaceError(f"{field} must be lowercase sha256 hex")
    return value


def _validate_summary(summary: dict[str, float]) -> None:
    if not isinstance(summary, dict):
        raise InvalidToleranceWorkspaceError("summary_values must be a dict")
    for key, value in summary.items():
        _require_text(key, field="summary key")
        _require_finite(value, field=f"summary {key}")