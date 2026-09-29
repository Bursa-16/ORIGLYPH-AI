"""Headless tolerance workspace controller (Stage 16D)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import OriglyphToleranceError
from .models import (
    StackDirection,
    StatisticalContribution,
    StatisticalResult,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
)
from .statistical import statistical
from .worst_case import worst_case

__all__ = [
    "TOLERANCE_WORKSPACE_SCHEMA_VERSION",
    "AnalysisMode",
    "InvalidToleranceWorkspaceError",
    "WorkspaceAnalysisResult",
    "WorkspaceContributor",
    "WorkspaceState",
    "ToleranceWorkspaceController",
    "workspace_configuration_fingerprint",
    "workspace_result_identities",
    "workspace_state_from_snapshot",
    "workspace_state_to_snapshot",
    "workspace_summary_values",
]

TOLERANCE_WORKSPACE_SCHEMA_VERSION = "origlyph.tolerance.workspace.v1"
_SUPPORTED_TOLERANCE_MODEL = "symmetric"
_DEFAULT_SIGMA_MULTIPLIER = 1.0


class InvalidToleranceWorkspaceError(OriglyphToleranceError):
    """Raised when workspace input or persisted workspace state is invalid."""


class AnalysisMode(Enum):
    """Analysis modes supported by the Stage 16D workspace UI."""

    WORST_CASE = "worst_case"
    RSS_STATISTICAL = "rss_statistical"


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


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    """Immutable authoritative workspace configuration."""

    schema_version: str
    chain_name: str
    analysis_mode: AnalysisMode
    contributors: tuple[WorkspaceContributor, ...]

    def __post_init__(self) -> None:
        if self.schema_version != TOLERANCE_WORKSPACE_SCHEMA_VERSION:
            raise InvalidToleranceWorkspaceError(
                f"unsupported workspace schema {self.schema_version!r}"
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
        return {
            "schema_version": self.schema_version,
            "chain_name": self.chain_name,
            "analysis_mode": self.analysis_mode.value,
            "contributors": [item.as_dict() for item in self.contributors],
        }


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
    ) -> None:
        self._state = WorkspaceState(
            schema_version=TOLERANCE_WORKSPACE_SCHEMA_VERSION,
            chain_name=chain_name,
            analysis_mode=_coerce_analysis_mode(analysis_mode),
            contributors=contributors,
        )
        self._last_result: WorkspaceAnalysisResult | None = None

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
    def last_result(self) -> WorkspaceAnalysisResult | None:
        return self._last_result

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
        return cls(
            chain_name=state.chain_name,
            analysis_mode=state.analysis_mode,
            contributors=state.contributors,
        )

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

    def set_analysis_mode(self, analysis_mode: AnalysisMode | str) -> None:
        mode = _coerce_analysis_mode(analysis_mode)
        if mode is self._state.analysis_mode:
            return
        self._state = replace(self._state, analysis_mode=mode)
        self._last_result = None

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
        return result

    def result_view(self) -> dict[str, object]:
        result = (
            self._last_result
            if self._last_result is not None
            else self.run_analysis()
        )
        return result.as_dict()

    def _replace_contributors(
        self, contributors: tuple[WorkspaceContributor, ...]
    ) -> None:
        self._state = replace(self._state, contributors=contributors)
        self._last_result = None

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