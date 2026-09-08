"""Origlyph tolerance analysis package.

Stage 15C-R / 15D / 15E / 15F / 15G / 15H / 15I / 15J / 15K / 15M / 15N /
15O.

Deterministic 1D tolerance stack analysis. This package provides the typed
domain model (:mod:`origlyph.tolerance.models`), the deterministic
worst-case engine (:mod:`origlyph.tolerance.worst_case`), the deterministic
statistical (RSS) engine (:mod:`origlyph.tolerance.statistical`), explicit
covariance-aware correlated statistical propagation via
:class:`~origlyph.tolerance.Correlation`, the explanatory sensitivity
and contributor-impact analysis (:mod:`origlyph.tolerance.sensitivity`),
deterministic tolerance-budget compliance analysis
(:mod:`origlyph.tolerance.budget`), deterministic tolerance allocation
validation (:mod:`origlyph.tolerance.allocation`), deterministic
worst-case allocation reconciliation (:mod:`origlyph.tolerance.reconciliation`),
deterministic statistical allocation reconciliation
(:mod:`origlyph.tolerance.statistical_reconciliation`), a
deterministic tolerance decision layer (:mod:`origlyph.tolerance.decision`),
  a deterministic decision report envelope (:mod:`origlyph.tolerance.report`),
  and deterministic audit-integrity validation
  (:mod:`origlyph.tolerance.integrity`).

Statistical tolerance analysis does not replace worst-case analysis.
Sensitivity analysis explains contribution; it does not change
authoritative tolerance results. Budget analysis evaluates compliance;
it does not automatically redistribute tolerances. Allocation validation
checks a user-supplied plan; it does not generate or optimize allocations.
Worst-case allocation reconciliation compares a validated plan against
actual worst-case consumption; it does not generate a new allocation.
Statistical allocation reconciliation compares a user-supplied sigma
allocation against actual statistical consumption; it does not generate
or optimize allocations, nor does it convert worst-case spans into sigma.
The tolerance decision layer orchestrates existing engines into one
deterministic engineering decision; it does not replace the underlying
engines, and it is not an AI recommendation engine.
The decision report is an audit envelope; it does not recompute
authoritative engineering calculations.
Audit-integrity validation checks that envelope for structural consistency;
it does not recompute or override engineering results.
The audit package adds deterministic fingerprints and structural replay
metadata without rerunning authoritative calculations.

AI does not override deterministic tolerance calculations.
"""

from .allocation import validate_allocation
from .audit import (
    AUDIT_PACKAGE_SCHEMA_VERSION,
    DecisionReplayManifest,
    InvalidDecisionAuditPackageError,
    ReplayabilityStatus,
    ToleranceDecisionAuditPackage,
    audit_package_from_dict,
    build_decision_audit_package,
    verify_decision_audit_package,
)
from .budget import (
    statistical_budget,
    worst_case_budget,
    worst_case_window_compliance,
)
from .decision import evaluate_tolerance_decision
from .evidence import (
    DecisionComparison,
    DecisionEvidenceBundle,
    DecisionEvidenceCode,
    DecisionEvidenceItem,
    DecisionEvidenceSource,
    DecisionExplanation,
    DecisionMetric,
    ReasonEvidenceLink,
    build_decision_evidence,
    explain_tolerance_decision,
)
from .exceptions import (
    InvalidAllocationError,
    InvalidBudgetError,
    InvalidCorrelationError,
    InvalidDecisionEvidenceError,
    InvalidStackError,
    InvalidStatisticalAllocationError,
    InvalidStatisticalError,
    InvalidToleranceDecisionError,
    InvalidToleranceError,
    InvalidVarianceError,
    OriglyphToleranceError,
)
from .integrity import (
    AuditIntegrityResult,
    AuditIntegritySeverity,
    AuditIntegrityStatus,
    AuditIntegrityViolation,
    AuditIntegrityViolationCode,
    InvalidAuditIntegrityError,
    validate_decision_report_integrity,
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
    StatisticalAllocation,
    StatisticalAllocationCovarianceImpact,
    StatisticalAllocationPlan,
    StatisticalAllocationReconciliationResult,
    StatisticalAllocationReconciliationStatus,
    StatisticalAllocationStatus,
    StatisticalBudgetResult,
    StatisticalContribution,
    StatisticalContributionBudget,
    StatisticalContributorCompliance,
    StatisticalResult,
    StatisticalStack,
    ToleranceAllocation,
    ToleranceContribution,
    ToleranceDecisionCovarianceEffect,
    ToleranceDecisionDimension,
    ToleranceDecisionEvaluationState,
    ToleranceDecisionEvidence,
    ToleranceDecisionReason,
    ToleranceDecisionReasonCode,
    ToleranceDecisionResult,
    ToleranceDecisionSensitivity,
    ToleranceDecisionSeverity,
    ToleranceDecisionStatus,
    ToleranceStack,
    WorstCaseBudgetResult,
    WorstCaseContributionBudget,
    WorstCaseResult,
    WorstCaseWindowResult,
)
from .reconciliation import reconcile_allocation
from .report import (
    REPORT_SCHEMA_VERSION,
    DecisionInputs,
    DecisionProvenance,
    InvalidDecisionReportError,
    ReportContributor,
    ReportEvidenceRef,
    ReportMetricValue,
    ReportReasonRef,
    ReportSection,
    ToleranceDecisionReport,
    build_decision_report,
    build_tolerance_decision_report,
    decision_report_from_dict,
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
from .statistical_reconciliation import reconcile_statistical_allocation
from .worst_case import worst_case

__all__ = [
    "AUDIT_PACKAGE_SCHEMA_VERSION",
    "AllocationComplianceStatus",
    "AllocationContributorResult",
    "AllocationPlan",
    "AllocationReconciliationResult",
    "AllocationStatus",
    "AllocationValidationResult",
    "AuditIntegrityResult",
    "AuditIntegritySeverity",
    "AuditIntegrityStatus",
    "AuditIntegrityViolation",
    "AuditIntegrityViolationCode",
    "BudgetStatus",
    "ContributorAllocationCompliance",
    "Correlation",
    "CovariancePairImpact",
    "DecisionComparison",
    "DecisionEvidenceBundle",
    "DecisionEvidenceCode",
    "DecisionEvidenceItem",
    "DecisionEvidenceSource",
    "DecisionExplanation",
    "DecisionInputs",
    "DecisionMetric",
    "DecisionProvenance",
    "DecisionReplayManifest",
    "InvalidAllocationError",
    "InvalidAuditIntegrityError",
    "InvalidBudgetError",
    "InvalidCorrelationError",
    "InvalidDecisionEvidenceError",
    "InvalidDecisionAuditPackageError",
    "InvalidDecisionReportError",
    "InvalidStackError",
    "InvalidStatisticalAllocationError",
    "InvalidStatisticalError",
    "InvalidToleranceDecisionError",
    "InvalidToleranceError",
    "InvalidVarianceError",
    "OriglyphToleranceError",
    "REPORT_SCHEMA_VERSION",
    "ReconciliationStatus",
    "ReplayabilityStatus",
    "ReasonEvidenceLink",
    "ReportContributor",
    "ReportEvidenceRef",
    "ReportMetricValue",
    "ReportReasonRef",
    "ReportSection",
    "StackDirection",
    "StatisticalAllocation",
    "StatisticalAllocationCovarianceImpact",
    "StatisticalAllocationPlan",
    "StatisticalAllocationReconciliationResult",
    "StatisticalAllocationReconciliationStatus",
    "StatisticalAllocationStatus",
    "StatisticalBudgetResult",
    "StatisticalContribution",
    "StatisticalContributionBudget",
    "StatisticalContributorCompliance",
    "StatisticalContributionImpact",
    "StatisticalResult",
    "StatisticalSensitivityResult",
    "StatisticalStack",
    "ToleranceAllocation",
    "ToleranceContribution",
    "ToleranceDecisionCovarianceEffect",
    "ToleranceDecisionDimension",
    "ToleranceDecisionEvaluationState",
    "ToleranceDecisionEvidence",
    "ToleranceDecisionReason",
    "ToleranceDecisionReasonCode",
    "ToleranceDecisionReport",
    "ToleranceDecisionAuditPackage",
    "ToleranceDecisionResult",
    "ToleranceDecisionSensitivity",
    "ToleranceDecisionSeverity",
    "ToleranceDecisionStatus",
    "ToleranceStack",
    "WorstCaseBudgetResult",
    "WorstCaseContributionBudget",
    "WorstCaseContributionImpact",
    "WorstCaseResult",
    "WorstCaseSensitivityResult",
    "WorstCaseWindowResult",
    "build_decision_evidence",
    "build_decision_audit_package",
    "build_decision_report",
    "build_tolerance_decision_report",
    "decision_report_from_dict",
    "evaluate_tolerance_decision",
    "explain_tolerance_decision",
    "reconcile_allocation",
    "reconcile_statistical_allocation",
    "statistical",
    "statistical_budget",
    "statistical_sensitivity",
    "validate_allocation",
    "validate_decision_report_integrity",
    "verify_decision_audit_package",
    "worst_case",
    "worst_case_budget",
    "worst_case_sensitivity",
    "worst_case_window_compliance",
    "audit_package_from_dict",
]
