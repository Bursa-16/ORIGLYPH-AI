"""Origlyph tolerance analysis package (Stage 15C-R / 15D / 15E / 15F).

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), the deterministic
statistical (RSS) engine (:mod:`origlyph.tolerance.statistical`), explicit
covariance-aware correlated statistical propagation via
:class:`~origlyph.tolerance.Correlation`, and the explanatory sensitivity
and contributor-impact analysis (:mod:`origlyph.tolerance.sensitivity`).

Statistical tolerance analysis does not replace worst-case analysis.
Sensitivity analysis explains contribution; it does not change
authoritative tolerance results.

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
from .sensitivity import (
    CovariancePairImpact,
    StatisticalContributionImpact,
    StatisticalSensitivityResult,
    WorstCaseContributionImpact,
    WorstCaseSensitivityResult,
    statistical_sensitivity,
    worst_case_sensitivity,
)
from .statistical import statistical
from .worst_case import worst_case

__all__ = [
    "Correlation",
    "CovariancePairImpact",
    "InvalidCorrelationError",
    "InvalidStackError",
    "InvalidStatisticalError",
    "InvalidToleranceError",
    "InvalidVarianceError",
    "OriglyphToleranceError",
    "StackDirection",
    "StatisticalContribution",
    "StatisticalContributionImpact",
    "StatisticalResult",
    "StatisticalSensitivityResult",
    "StatisticalStack",
    "ToleranceContribution",
    "ToleranceStack",
    "WorstCaseContributionImpact",
    "WorstCaseResult",
    "WorstCaseSensitivityResult",
    "statistical",
    "statistical_sensitivity",
    "worst_case",
    "worst_case_sensitivity",
]