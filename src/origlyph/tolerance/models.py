"""Data models for the Origlyph 1D Worst-Case Tolerance Engine.

Stage 15B — deterministic, UI-independent, filesystem-independent,
network-independent, persistence-independent, AI-independent.

These models implement the locked Stage 15A contract:
  - FunctionalRequirement: the engineering requirement specification
  - Contributor: a single dimensional contributor with signed coefficient
  - WorstCaseResult: the deterministic analysis result
  - WorstCaseStatus: PASS / FAIL / INDETERMINATE

Invariants:
  - All models are frozen dataclasses (immutable, hashable, value-comparable)
  - All validation happens at construction time (fail-fast)
  - Invalid states are unrepresentable
  - Unit inference is forbidden — units must be explicit

Reused existing contracts:
  - SourceEntityIdentity: source/evidence reference for contributors
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from origlyph.cad.identity import SourceEntityIdentity

__all__ = [
    "FunctionalRequirement",
    "Contributor",
    "WorstCaseResult",
    "WorstCaseStatus",
]


class WorstCaseStatus(str, Enum):
    """Status of a 1D worst-case tolerance analysis result.

    Three states only — no approval/release lifecycle states here.

    Meanings (locked by the Stage 15A contract):

        PASS
            All eligibility/evidence gates satisfied AND worst-case interval
            lies entirely within requirement bounds.
        FAIL
            All eligibility/evidence gates satisfied AND worst-case interval
            violates at least one requirement bound.
        INDETERMINATE
            Calculation may be numerically possible but blocking engineering
            evidence/eligibility conditions are resolved. No authoritative
            PASS/FAIL can be determined.
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class FunctionalRequirement:
    """Authoritative requirement specification for 1D worst-case analysis.

    Represents the engineering requirement that the analyzed characteristic
    must satisfy. This is a value object carrying only the requirement
    specification — it does not perform calculations.

    Invariants (enforced in __post_init__):
      - lower_limit <= upper_limit (valid interval)
      - unit must be explicit and non-empty
      - bounds must be finite (no NaN, no Infinity)
      - If nominal_target provided: lower_limit <= nominal_target <= upper_limit
    """

    lower_limit: float
    upper_limit: float
    unit: str
    nominal_target: Optional[float] = None
    requirement_id: Optional[str] = None
    direction: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("requirement unit must be an explicit non-empty string")
        if math.isnan(self.lower_limit) or math.isinf(self.lower_limit):
            raise ValueError("lower_limit must be finite")
        if math.isnan(self.upper_limit) or math.isinf(self.upper_limit):
            raise ValueError("upper_limit must be finite")
        if self.lower_limit > self.upper_limit:
            raise ValueError(
                f"lower_limit ({self.lower_limit}) must be "
                f"<= upper_limit ({self.upper_limit})"
            )
        if self.nominal_target is not None:
            if math.isnan(self.nominal_target) or math.isinf(self.nominal_target):
                raise ValueError("nominal_target must be finite")
            if self.nominal_target < self.lower_limit:
                raise ValueError("nominal_target must be >= lower_limit")
            if self.nominal_target > self.upper_limit:
                raise ValueError("nominal_target must be <= upper_limit")


@dataclass(frozen=True)
class Contributor:
    """A single dimensional contributor to the worst-case stack.

    Represents one feature/dimension in the tolerance chain with its
    nominal value and deviation bounds. Asymmetric tolerance is natively
    supported via independent lower_deviation and upper_deviation.

    Storage model: nominal + lower_deviation / upper_deviation
      - nominal is the engineering reference value
      - deviations are explicitly signed relative to nominal
      - lower = nominal + lower_deviation
      - upper = nominal + upper_deviation

    Invariants (enforced in __post_init__):
      - all numeric values are finite (no NaN, no Infinity)
      - derived lower <= derived upper
      - unit is explicit and non-empty

    Zero coefficient behavior:
      - coefficient = 0 means zero contribution to all terms
      - contributor is still validated for data quality
      - does not affect calculation result
    """

    nominal: float
    lower_deviation: float
    upper_deviation: float
    coefficient: float = 1.0
    unit: str = "mm"
    source_identity: Optional[SourceEntityIdentity] = None
    contributor_id: Optional[str] = None
    feature_ref: Optional[str] = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("contributor unit must be an explicit non-empty string")
        if math.isnan(self.nominal) or math.isinf(self.nominal):
            raise ValueError("nominal must be finite")
        if math.isnan(self.lower_deviation) or math.isinf(self.lower_deviation):
            raise ValueError("lower_deviation must be finite")
        if math.isnan(self.upper_deviation) or math.isinf(self.upper_deviation):
            raise ValueError("upper_deviation must be finite")
        if math.isnan(self.coefficient) or math.isinf(self.coefficient):
            raise ValueError("coefficient must be finite")
        lower = self.nominal + self.lower_deviation
        upper = self.nominal + self.upper_deviation
        if lower > upper:
            raise ValueError(
                f"derived lower ({lower}) must be <= derived upper ({upper}): "
                f"lower_deviation ({self.lower_deviation}) and "
                f"upper_deviation ({self.upper_deviation}) "
                f"create invalid bounds for nominal ({self.nominal})"
            )

    @property
    def lower(self) -> float:
        """Derived lower bound: nominal + lower_deviation."""
        return self.nominal + self.lower_deviation

    @property
    def upper(self) -> float:
        """Derived upper bound: nominal + upper_deviation."""
        return self.nominal + self.upper_deviation


@dataclass(frozen=True)
class WorstCaseResult:
    """Deterministic result of a 1D worst-case tolerance analysis.

    Frozen, immutable, hashable. Contains the complete analysis result
    including margins, status, and traceability.

    Margin semantics (locked):
      margin >= 0  →  within requirement (safe)
      margin < 0   →  violates requirement (violation)

      lower_margin = Y_min - requirement_lower_limit
      upper_margin = requirement_upper_limit - Y_max
    """

    nominal_result: float
    minimum_result: float
    maximum_result: float
    lower_margin: float
    upper_margin: float
    status: WorstCaseStatus
    calculatable: bool
    releasable: bool
    warnings: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    input_snapshot_id: Optional[str] = None
    engine_version: str = "15B.0.1"

