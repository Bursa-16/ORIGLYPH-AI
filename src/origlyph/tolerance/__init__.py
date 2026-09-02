"""Origlyph tolerance analysis package.

Stage 15B — 1D Worst-Case Tolerance Engine.

Provides deterministic worst-case tolerance analysis with:
  - Signed coefficient propagation
  - Asymmetric tolerance support
  - Explicit same-unit policy (no inference)
  - Calculatable vs releasable distinction
  - Fail-closed eligibility

Public API:
  - calculate_worst_case: pure deterministic calculation
  - FunctionalRequirement: requirement specification
  - Contributor: dimensional contributor model
  - WorstCaseResult: analysis result
  - WorstCaseStatus: PASS / FAIL / INDETERMINATE
"""

from .models import (
    Contributor,
    FunctionalRequirement,
    WorstCaseResult,
    WorstCaseStatus,
)
from .worst_case import (
    ENGINE_VERSION,
    calculate_worst_case,
)

__all__ = [
    "ENGINE_VERSION",
    "Contributor",
    "FunctionalRequirement",
    "WorstCaseResult",
    "WorstCaseStatus",
    "calculate_worst_case",
]

"""Origlyph tolerance analysis package."""