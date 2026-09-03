"""Origlyph tolerance analysis package (Stage 15C-R / 15D / 15E).

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), the deterministic
statistical (RSS) engine (:mod:`origlyph.tolerance.statistical`), and
explicit covariance-aware correlated statistical propagation via
:class:`~origlyph.tolerance.Correlation`.

Statistical tolerance analysis does not replace worst-case analysis.

AI does not override deterministic tolerance calculations.
"""

from .exceptions import (
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
    InvalidVarianceError,
    OriglyphToleranceError,
)
from .models import (
    Correlation,
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
    "Correlation",
    "InvalidCorrelationError",
    "InvalidStackError",
    "InvalidStatisticalError",
    "InvalidToleranceError",
    "InvalidVarianceError",
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