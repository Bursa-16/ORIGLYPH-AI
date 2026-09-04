"""Origlyph tolerance analysis package.

Stage 15C-R / 15D / 15E / 15F / 15G / 15H / 15I.

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), the deterministic
statistical (RSS) engine (:mod:`origlyph.tolerance.statistical`), explicit
covariance-aware correlated statistical propagation via
:class:`~origlyph.tolerance.Correlation`, the explanatory sensitivity
and contributor-impact analysis (:mod:`origlyph.tolerance.sensitivity`),
deterministic tolerance-budget compliance analysis
(:mod:`origlyph.tolerance.budget`), deterministic tolerance allocation
validation (:mod:`origlyph.tolerance.allocation`), and deterministic
allocation reconciliation (:mod:`origlyph.tolerance.reconciliation`).

Statistical tolerance analysis does not replace worst-case analysis.
Sensitivity analysis explains contribution; it does not change
authoritative tolerance results. Budget analysis evaluates compliance;
it does not automatically redistribute tolerances. Allocation validation
checks a user-supplied plan; it does not generate or optimize allocations.
Allocation reconciliation compares a validated plan against actual
consumption; it does not generate a new allocation.

AI does not override deterministic tolerance calculations.
"""

from .allocation import validate_allocation
from .budget import (
    statistical_budget,
    worst_case_budget,
    worst_case_window_compliance,
)
from .exceptions import (
    InvalidAllocationError,
    InvalidBudgetError,
    InvalidCorrelationError,
    InvalidStackError,
    InvalidStatisticalError,
    InvalidToleranceError,
    InvalidVarianceError,
    OriglyphToleranceError,
)
from .models import (
    AllocationComplianceStatus,
    AllocationContributorResult,
    AllocationPlan,
    AllocationReconciliationResult,
    AllocationStatus,
    AllocationValidationResult,
    BudgetStatus,
    ContributorAllocationCompliance,
    Correlation,
    ReconciliationStatus,
    StackDirection,
    StatisticalBudgetResult,
    StatisticalContribution,
    StatisticalContributionBudget,
    StatisticalResult,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseBudgetResult,
    WorstCaseContributionBudget,
    WorstCaseResult,
    WorstCaseWindowResult,
)
from .reconciliation import reconcile_allocation
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
    "AllocationComplianceStatus",
    "AllocationContributorResult",
    "AllocationPlan",
    "AllocationReconciliationResult",
    "AllocationStatus",
    "AllocationValidationResult",
    "BudgetStatus",
    "ContributorAllocationCompliance",
    "Correlation",
    "CovariancePairImpact",
    "InvalidAllocationError",
    "InvalidBudgetError",
    "InvalidCorrelationError",
    "InvalidStackError",
    "InvalidStatisticalError",
    "InvalidToleranceError",
    "InvalidVarianceError",
    "OriglyphToleranceError",
    "ReconciliationStatus",
    "StackDirection",
    "StatisticalBudgetResult",
    "StatisticalContribution",
    "StatisticalContributionBudget",
    "StatisticalContributionImpact",
    "StatisticalResult",
    "StatisticalSensitivityResult",
    "StatisticalStack",
    "ToleranceAllocation",
    "ToleranceContribution",
    "ToleranceStack",
    "WorstCaseBudgetResult",
    "WorstCaseContributionBudget",
    "WorstCaseContributionImpact",
    "WorstCaseResult",
    "WorstCaseSensitivityResult",
    "WorstCaseWindowResult",
    "reconcile_allocation",
    "statistical",
    "statistical_budget",
    "statistical_sensitivity",
    "validate_allocation",
    "worst_case",
    "worst_case_budget",
    "worst_case_sensitivity",
    "worst_case_window_compliance",
]