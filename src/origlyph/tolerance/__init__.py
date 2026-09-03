"""Origlyph tolerance analysis package (Stage 15C-R / Stage 15D).

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), and the
deterministic statistical (RSS) engine
(:mod:`origlyph.tolerance.statistical`).

Statistical tolerance analysis does not replace worst-case analysis.

AI does not override deterministic tolerance calculations.
"""

from .exceptions import (
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
    OriglyphToleranceError,
)
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
    "InvalidStackError",
    "InvalidStatisticalError",
    "InvalidToleranceError",
    "OriglyphToleranceError",
    "StackDirection",
    "StatisticalContribution",
    "StatisticalResult",
    "StatisticalStack",
    "ToleranceContribution",
    "ToleranceStack",
    "WorstCaseResult",
    "statistical",
    "worst_case",
]