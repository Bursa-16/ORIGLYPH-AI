"""Origlyph tolerance analysis package (Stage 15C-R / 15D / 15E / 15F / 15G).

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), the deterministic
statistical (RSS) engine (:mod:`origlyph.tolerance.statistical`), explicit
covariance-aware correlated statistical propagation via
:class:`~origlyph.tolerance.Correlation`, the explanatory sensitivity
and contributor-impact analysis (:mod:`origlyph.tolerance.sensitivity`),
and deterministic tolerance-budget compliance analysis
(:mod:`origlyph.tolerance.budget`).

Statistical tolerance analysis does not replace worst-case analysis.
Sensitivity analysis explains contribution; it does not change
authoritative tolerance results. Budget analysis evaluates compliance;
it does not automatically redistribute tolerances.

AI does not override deterministic tolerance calculations.
"""

from .budget import (
    statistical_budget,
    worst_case_budget,
    worst_case_window_compliance,
)
from .exceptions import (
    InvalidBudgetError,
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
    InvalidVarianceError,
    OriglyphToleranceError,
)
from .models import (
    BudgetStatus,
    Correlation,
    StackDirection,
    StatisticalBudgetResult,
    StatisticalContribution,
    StatisticalContributionBudget,
    StatisticalResult,
    StatisticalStack,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseBudgetResult,
    WorstCaseContributionBudget,
    WorstCaseResult,
    WorstCaseWindowResult,
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
    "BudgetStatus",
    "Correlation",
    "CovariancePairImpact",
    "InvalidBudgetError",
    "InvalidCorrelationError",
    "InvalidStackError",
    "InvalidStatisticalError",
    "InvalidToleranceError",
    "InvalidVarianceError",
    "OriglyphToleranceError",
    "StackDirection",
    "StatisticalBudgetResult",
    "StatisticalContribution",
    "StatisticalContributionBudget",
    "StatisticalContributionImpact",
    "StatisticalResult",
    "StatisticalSensitivityResult",
    "StatisticalStack",
    "ToleranceContribution",
    "ToleranceStack",
    "WorstCaseBudgetResult",
    "WorstCaseContributionBudget",
    "WorstCaseContributionImpact",
    "WorstCaseResult",
    "WorstCaseSensitivityResult",
    "WorstCaseWindowResult",
    "statistical",
    "statistical_budget",
    "statistical_sensitivity",
    "worst_case",
    "worst_case_budget",
    "worst_case_sensitivity",
    "worst_case_window_compliance",
]