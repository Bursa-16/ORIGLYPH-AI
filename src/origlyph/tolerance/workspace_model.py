"""Thin Tkinter tolerance workspace view (Stage 16D / 17A / 17B / 17C)."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .audit import (
    ToleranceDecisionAuditPackage,
)
from .evidence import (
    DecisionEvidenceBundle,
    DecisionExplanation,
)
from .integrity import (
    AuditIntegrityResult,
)
from .models import (
    AllocationReconciliationResult,
    AllocationValidationResult,
    StackDirection,
    StatisticalAllocationReconciliationResult,
    ToleranceDecisionEvidence,
    ToleranceDecisionResult,
    ToleranceDecisionSeverity,
    WorstCaseBudgetResult,
)
from .report import ToleranceDecisionReport
from .sensitivity import (
    StatisticalSensitivityResult,
    WorstCaseSensitivityResult,
)
from .workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceAnalysisResult,
    WorkspaceSpecification,
    WorkspaceStatisticalAllocationEntry,
    WorkspaceStatisticalAllocationPlan,
)

__all__ = ["ToleranceWorkspaceView", "WorkspaceSession", "launch_tolerance_workspace"]

_NO_RESULT_TEXT = "No result"
_NO_DECISION_TEXT = "NOT EVALUATED"
_NO_SENSITIVITY_TEXT = "NOT RUN"
_NO_BUDGET_TEXT = "NOT RUN"
_NO_ALLOCATION_VALIDATION_TEXT = "NOT VALIDATED"
_NO_RECONCILIATION_TEXT = "NOT RUN"
_NO_STAT_RECONCILIATION_TEXT = "NOT RUN"
_NO_EVIDENCE_TEXT = "NOT GENERATED"
_NO_REPORT_TEXT = "NOT GENERATED"
_NO_AUDIT_TEXT = "NOT GENERATED"
_MODE_DISPLAY_NAMES: dict[str, str] = {
    "worst_case": "Worst Case",
    "rss_statistical": "RSS Statistical",
}


def _numeric_detail_parts(
    ev: ToleranceDecisionEvidence, mode: AnalysisMode
) -> list[str]:
    """Return Actual / Limit / Margin parts for one analysis mode."""
    parts: list[str] = []
    if mode is AnalysisMode.WORST_CASE:
        if ev.worst_case_actual_span is not None:
            parts.append(f"Actual: {ev.worst_case_actual_span:.6g}")
        if ev.worst_case_allowed_span is not None:
            parts.append(f"Limit: {ev.worst_case_allowed_span:.6g}")
        if ev.worst_case_margin is not None:
            parts.append(f"Margin: {ev.worst_case_margin:.6g}")
    elif mode is AnalysisMode.RSS_STATISTICAL:
        if ev.statistical_actual_combined_sigma is not None:
            parts.append(f"Actual σ: {ev.statistical_actual_combined_sigma:.6g}")
        if ev.statistical_allowed_combined_sigma is not None:
            parts.append(f"Limit σ: {ev.statistical_allowed_combined_sigma:.6g}")
        if ev.statistical_margin is not None:
            parts.append(f"Margin: {ev.statistical_margin:.6g}")
    return parts


def _spec_field_str(spec: WorkspaceSpecification | None, attr: str) -> str:
    if spec is None:
        return ""
    val: float | None = getattr(spec, attr)
    return "" if val is None else str(val)


def _parse_opt_positive_str(value: str, label: str) -> float | None:
    """Return None for empty/blank, or a validated strictly-positive finite float."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        numeric = float(stripped)
    except ValueError as exc:
        raise InvalidToleranceWorkspaceError(
            f"{label}: enter a valid number (e.g. 1.0)"
        ) from exc
    if not math.isfinite(numeric):
        raise InvalidToleranceWorkspaceError(f"{label}: must be a finite number")
    if numeric <= 0.0:
        raise InvalidToleranceWorkspaceError(f"{label}: must be greater than zero")
    return numeric


def _parse_non_negative_str(value: str, label: str) -> float:
    """Return a validated non-negative finite float; blank is an error."""
    stripped = value.strip()
    if not stripped:
        raise InvalidToleranceWorkspaceError(
            f'Allocated span for "{label}" is required.'
        )
    try:
        numeric = float(stripped)
    except ValueError as exc:
        raise InvalidToleranceWorkspaceError(
            f'Allocated span for "{label}": enter a valid number (e.g. 0.4).'
        ) from exc
    if not math.isfinite(numeric):
        raise InvalidToleranceWorkspaceError(
            f'Allocated span for "{label}": must be a finite number.'
        )
    if numeric < 0.0:
        raise InvalidToleranceWorkspaceError(
            f'Allocated span for "{label}": must be zero or greater.'
        )
    return numeric


def _parse_non_negative_sigma_str(value: str, label: str) -> float:
    """Return a validated non-negative finite float for sigma; blank is an error."""
    stripped = value.strip()
    if not stripped:
        raise InvalidToleranceWorkspaceError(
            f'Allocated sigma for "{label}" is required.'
        )
    try:
        numeric = float(stripped)
    except ValueError as exc:
        raise InvalidToleranceWorkspaceError(
            f'Allocated sigma for "{label}": enter a valid number (e.g. 0.05).'
        ) from exc
    if not math.isfinite(numeric):
        raise InvalidToleranceWorkspaceError(
            f'Allocated sigma for "{label}": must be a finite number.'
        )
    if numeric < 0.0:
        raise InvalidToleranceWorkspaceError(
            f'Allocated sigma for "{label}": must be zero or greater.'
        )
    return numeric


class WorkspaceSession:
    """Headless view seam owning header sync and result presentation.

    The Tkinter view binds its widgets onto this session so header sync, save,
    and result labelling stay testable without a display.
    """

    def __init__(self, controller: ToleranceWorkspaceController) -> None:
        self.controller = controller
        self.chain_name: str = controller.state.chain_name
        self.analysis_mode: str = controller.analysis_mode.value
        self.allowed_wc_span: str = _spec_field_str(
            controller.specification, "allowed_worst_case_span"
        )
        self.allowed_sigma: str = _spec_field_str(
            controller.specification, "allowed_combined_sigma"
        )
        self.allocation_budget: str = ""
        self._allocation_spans: dict[str, str] = {}
        self.load_allocation_plan_fields()
        self.stat_sigma_multiplier: str = ""
        self.stat_allocation_budget: str = ""
        self._stat_allocation_sigmas: dict[str, str] = {}
        self.load_statistical_allocation_plan_fields()

    @property
    def result_text(self) -> str:
        """Label text mirroring the controller cache; never a dropped result."""
        result = self.controller.last_result
        if result is None:
            return _NO_RESULT_TEXT
        mode_label = _MODE_DISPLAY_NAMES.get(
            result.analysis_mode.value, result.analysis_mode.value
        )
        values = "  |  ".join(
            f"{key.replace('_', ' ')}: {value:.6g}"
            for key, value in result.summary_values.items()
        )
        return f"{mode_label}  —  {values}"

    def sync_header(self) -> None:
        """Push header fields into the controller without rebuilding it.

        A header-only no-op keeps the cached result; an authoritative change
        invalidates it through the controller setters.
        """
        self.controller.set_chain_name(self.chain_name)
        self.controller.set_analysis_mode(self.analysis_mode)

    def sync_specification(self) -> None:
        """Push specification string fields to the controller (Stage 17A).

        Empty strings mean unspecified — not zero.  Invalid values propagate as
        :class:`~origlyph.tolerance.InvalidToleranceWorkspaceError`.
        No analysis is triggered.
        """
        wc = _parse_opt_positive_str(self.allowed_wc_span, "allowed worst-case span")
        sigma = _parse_opt_positive_str(self.allowed_sigma, "allowed combined sigma")
        spec = (
            WorkspaceSpecification(
                allowed_worst_case_span=wc, allowed_combined_sigma=sigma
            )
            if wc is not None or sigma is not None
            else None
        )
        self.controller.set_specification(spec)

    @property
    def decision_text(self) -> str:
        """Presentation text for the current decision state; never stale."""
        decision = self.controller.last_decision
        if decision is None:
            return _NO_DECISION_TEXT
        return decision.overall_status.value.upper()

    @property
    def decision_detail_text(self) -> str:
        """Compact detail line with Actual / Limit / Margin / Reason."""
        decision = self.controller.last_decision
        if decision is None:
            return ""
        parts = _numeric_detail_parts(decision.evidence, self.controller.analysis_mode)
        for reason in decision.reasons:
            if reason.severity is ToleranceDecisionSeverity.FAILURE:
                parts.append(f"Reason: {reason.code.value}")
                break
        return "  ".join(parts) if parts else ""

    def evaluate_decision(self) -> ToleranceDecisionResult:
        """Delegate decision evaluation to the controller."""
        return self.controller.evaluate_decision()

    def sensitivity_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the sensitivity table; empty when not run."""
        sensitivity = self.controller.last_sensitivity
        if sensitivity is None:
            return []
        rows: list[dict[str, object]] = []
        if isinstance(sensitivity, WorstCaseSensitivityResult):
            for rank, impact in enumerate(sensitivity.impacts, start=1):
                rows.append({
                    "rank": rank,
                    "name": impact.name,
                    "impact": impact.span,
                    "share_pct": impact.percentage,
                })
        else:
            for rank, contribution in enumerate(sensitivity.contributions, start=1):
                rows.append({
                    "rank": rank,
                    "name": contribution.name,
                    "impact": contribution.variance,
                    "share_pct": contribution.percentage,
                })
        return rows

    def run_sensitivity(
        self,
    ) -> WorstCaseSensitivityResult | StatisticalSensitivityResult:
        """Delegate sensitivity execution to the controller."""
        return self.controller.run_sensitivity()

    def run_analysis(self) -> WorkspaceAnalysisResult:
        return self.controller.run_analysis()

    @property
    def budget_status_text(self) -> str:
        """Presentation text for the current budget state; never stale."""
        budget = self.controller.last_budget
        if budget is None:
            return _NO_BUDGET_TEXT
        return budget.status.value.upper()

    @property
    def budget_summary_text(self) -> str:
        """Compact summary: Budget / Consumed / Remaining / Utilization."""
        budget = self.controller.last_budget
        if budget is None:
            return ""
        return (
            f"Budget: {budget.allowed_span:.6g}  "
            f"Consumed: {budget.actual_span:.6g}  "
            f"Remaining: {budget.remaining_margin:.6g}  "
            f"Utilization: {budget.utilization_percentage:.1f}%"
        )

    def budget_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the budget contribution table; empty when not run."""
        budget = self.controller.last_budget
        if budget is None:
            return []
        rows: list[dict[str, object]] = []
        for rank, contrib in enumerate(budget.contributions, start=1):
            rows.append({
                "rank": rank,
                "name": contrib.name,
                "span": contrib.span,
                "pct_consumed": contrib.percentage_of_consumed,
                "pct_allowed": contrib.percentage_of_allowed,
            })
        return rows

    def run_budget(self) -> WorstCaseBudgetResult:
        """Delegate budget execution to the controller."""
        return self.controller.run_budget()

    def load_allocation_plan_fields(self) -> None:
        """Populate transient allocation editor fields from the authoritative plan."""
        plan = self.controller.allocation_plan
        if plan is None:
            self.allocation_budget = ""
            self._allocation_spans = {}
        else:
            self.allocation_budget = repr(plan.allowed_budget)
            self._allocation_spans = {
                e.contributor_id: repr(e.allocated_span) for e in plan.entries
            }

    def pending_span(self, contributor_id: str) -> str:
        """Return the pending allocated span string for a contributor."""
        return self._allocation_spans.get(contributor_id, "")

    def set_pending_span(self, contributor_id: str, span_str: str) -> None:
        """Set the pending allocated span string for a contributor."""
        self._allocation_spans[contributor_id] = span_str

    def sync_allocation_plan(self) -> None:
        """Parse editor fields and apply the allocation plan to the controller.

        Fail-closed: raises InvalidToleranceWorkspaceError on blank or invalid
        budget, or missing/invalid span for any current contributor.
        Does not call validate_allocation.
        """
        budget = _parse_opt_positive_str(self.allocation_budget, "allocation budget")
        if budget is None:
            raise InvalidToleranceWorkspaceError(
                "Allocation budget is required. Enter a positive number."
            )
        entries = []
        for c in self.controller.contributors:
            span_str = self._allocation_spans.get(c.identifier, "")
            span = _parse_non_negative_str(span_str, c.identifier)
            entries.append(
                WorkspaceAllocationEntry(
                    contributor_id=c.identifier, allocated_span=span
                )
            )
        plan = WorkspaceAllocationPlan(
            allowed_budget=budget,
            entries=tuple(entries),
        )
        self.controller.set_allocation_plan(plan)

    def clear_allocation_plan(self) -> None:
        """Clear the allocation plan and reset transient editor fields."""
        self.controller.clear_allocation_plan()
        self.allocation_budget = ""
        self._allocation_spans = {}

    def load_statistical_allocation_plan_fields(self) -> None:
        """Populate transient statistical allocation editor fields from the plan."""
        plan = self.controller.statistical_allocation_plan
        if plan is None:
            self.stat_sigma_multiplier = ""
            self.stat_allocation_budget = ""
            self._stat_allocation_sigmas = {}
        else:
            self.stat_sigma_multiplier = repr(plan.sigma_multiplier)
            self.stat_allocation_budget = (
                repr(plan.allowed_combined_sigma)
                if plan.allowed_combined_sigma is not None
                else ""
            )
            self._stat_allocation_sigmas = {
                e.contributor_id: repr(e.allocated_sigma) for e in plan.entries
            }

    def pending_sigma(self, contributor_id: str) -> str:
        """Return the pending allocated sigma string for a contributor."""
        return self._stat_allocation_sigmas.get(contributor_id, "")

    def set_pending_sigma(self, contributor_id: str, sigma_str: str) -> None:
        """Set the pending allocated sigma string for a contributor."""
        self._stat_allocation_sigmas[contributor_id] = sigma_str

    def sync_statistical_allocation_plan(self) -> None:
        """Parse editor fields and apply the statistical allocation plan.

        Fail-closed: raises InvalidToleranceWorkspaceError on blank or invalid
        sigma multiplier, or missing/invalid sigma for any current contributor.
        Does not call run_statistical_reconciliation.
        """
        multiplier = _parse_opt_positive_str(
            self.stat_sigma_multiplier, "sigma multiplier"
        )
        if multiplier is None:
            raise InvalidToleranceWorkspaceError(
                "Sigma multiplier is required. Enter a positive number."
            )
        allowed_combined = _parse_opt_positive_str(
            self.stat_allocation_budget, "allowed combined sigma"
        )
        entries = []
        for c in self.controller.contributors:
            sigma_str = self._stat_allocation_sigmas.get(c.identifier, "")
            sigma = _parse_non_negative_sigma_str(sigma_str, c.identifier)
            entries.append(
                WorkspaceStatisticalAllocationEntry(
                    contributor_id=c.identifier, allocated_sigma=sigma
                )
            )
        plan = WorkspaceStatisticalAllocationPlan(
            sigma_multiplier=multiplier,
            entries=tuple(entries),
            allowed_combined_sigma=allowed_combined,
        )
        self.controller.set_statistical_allocation_plan(plan)

    def clear_statistical_allocation_plan(self) -> None:
        """Clear the statistical allocation plan and reset transient editor fields."""
        self.controller.clear_statistical_allocation_plan()
        self.stat_sigma_multiplier = ""
        self.stat_allocation_budget = ""
        self._stat_allocation_sigmas = {}

    def statistical_allocation_editor_rows(self) -> list[dict[str, object]]:
        """Rows for the statistical plan editor table; one per current contributor."""
        rows: list[dict[str, object]] = []
        for c in self.controller.contributors:
            rows.append({
                "contributor_id": c.identifier,
                "contributor_name": c.name,
                "current_sigma": c.tolerance,
                "allocated_sigma_str": self._stat_allocation_sigmas.get(
                    c.identifier, ""
                ),
            })
        return rows

    @property
    def last_statistical_reconciliation(
        self,
    ) -> StatisticalAllocationReconciliationResult | None:
        """Current statistical reconciliation result; None when not yet run."""
        return self.controller.last_statistical_reconciliation

    def run_statistical_reconciliation(
        self,
    ) -> StatisticalAllocationReconciliationResult:
        """Delegate statistical reconciliation to the controller (Stage 15J)."""
        return self.controller.run_statistical_reconciliation()

    @property
    def statistical_reconciliation_status_text(self) -> str:
        """Presentation text for the current statistical reconciliation state."""
        rec = self.controller.last_statistical_reconciliation
        if rec is None:
            return _NO_STAT_RECONCILIATION_TEXT
        return rec.allocation_plan_status.value.upper()

    @property
    def statistical_reconciliation_summary_text(self) -> str:
        """Compact summary: Multiplier / Allocated σ / Actual σ / Margin."""
        rec = self.controller.last_statistical_reconciliation
        if rec is None:
            return ""
        return (
            f"k={rec.sigma_multiplier:.6g}  "
            f"Alloc σ: {rec.allocated_combined_sigma:.6g}  "
            f"Actual σ: {rec.actual_combined_sigma:.6g}  "
            f"Margin: {rec.combined_sigma_margin:.6g}"
        )

    def statistical_reconciliation_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the statistical reconciliation table."""
        rec = self.controller.last_statistical_reconciliation
        if rec is None:
            return []
        rows: list[dict[str, object]] = []
        for rank, cc in enumerate(rec.contributor_compliances, start=1):
            rows.append({
                "rank": rank,
                "contributor_id": cc.contributor_id,
                "allocated_sigma": cc.allocated_sigma,
                "actual_sigma": cc.actual_sigma,
                "margin": cc.sigma_margin,
                "utilization_pct": cc.utilization_percentage,
                "status": cc.status.value,
            })
        return rows

    @property
    def last_evidence(self) -> DecisionEvidenceBundle | None:
        """Current decision evidence bundle; None before Generate Evidence is called."""
        return self.controller.last_evidence

    @property
    def last_explanation(self) -> DecisionExplanation | None:
        """Current decision explanation; None before Generate Evidence is called."""
        return self.controller.last_explanation

    def generate_evidence(
        self,
    ) -> tuple[DecisionEvidenceBundle, DecisionExplanation]:
        """Delegate evidence generation to the controller (Stage 15L)."""
        return self.controller.run_decision_evidence()

    @property
    def evidence_status_text(self) -> str:
        """Presentation text for the current evidence state; never stale."""
        evidence = self.controller.last_evidence
        if evidence is None:
            return _NO_EVIDENCE_TEXT
        return evidence.decision_status.value.upper()

    @property
    def explanation_summary_text(self) -> str:
        """Compact deterministic explanation summary; empty when not generated."""
        explanation = self.controller.last_explanation
        if explanation is None:
            return ""
        return explanation.summary

    def evidence_items_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the evidence items treeview; empty when not run."""
        evidence = self.controller.last_evidence
        if evidence is None:
            return []
        rows: list[dict[str, object]] = []
        for item in evidence.evidence_items:
            rows.append({
                "evidence_code": item.evidence_code,
                "source": item.source.value,
                "scope": item.scope if item.scope is not None else "—",
                "observed_value": item.observed_value,
                "reference_value": item.reference_value,
                "severity": item.severity.value,
                "detail": item.detail,
            })
        return rows

    @property
    def last_decision_report(self) -> ToleranceDecisionReport | None:
        """Current decision report; None before Generate Decision Report is called."""
        return self.controller.last_decision_report

    def generate_decision_report(self) -> ToleranceDecisionReport:
        """Delegate decision report generation to the controller (Stage 15M)."""
        return self.controller.run_decision_report()

    @property
    def report_status_text(self) -> str:
        """Presentation text for the current report state; never stale."""
        report = self.controller.last_decision_report
        if report is None:
            return _NO_REPORT_TEXT
        return report.final_status.value.upper()

    @property
    def report_summary_text(self) -> str:
        """Compact deterministic report summary text; empty when not generated."""
        report = self.controller.last_decision_report
        if report is None:
            return ""
        return report.summary_text

    def report_contributors_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the report contributors treeview."""
        report = self.controller.last_decision_report
        if report is None:
            return []
        rows: list[dict[str, object]] = []
        for c in report.contributors:
            val = (
                f"{c.contribution_value:.6g}"
                if c.contribution_value is not None
                else "—"
            )
            sig = (
                f"{c.contribution_sigma:.6g}"
                if c.contribution_sigma is not None
                else "—"
            )
            rows.append({
                "name": c.name,
                "type": c.contribution_type,
                "value": val,
                "sigma": sig,
            })
        return rows

    def report_evidence_refs_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the report evidence-refs treeview."""
        report = self.controller.last_decision_report
        if report is None:
            return []
        rows: list[dict[str, object]] = []
        for ref in report.evidence_refs:
            rows.append({
                "evidence_id": ref.evidence_id,
                "evidence_code": ref.evidence_code,
                "source": ref.source,
                "reason_code": ref.reason_code,
            })
        return rows

    # --- Audit Integrity + Audit Package (Stage 20D) ---

    @property
    def last_audit_integrity(self) -> AuditIntegrityResult | None:
        """Current audit integrity result; None before Generate Audit Package."""
        return self.controller.last_audit_integrity

    @property
    def last_audit_package(self) -> ToleranceDecisionAuditPackage | None:
        """Current audit package; None before Generate Audit Package."""
        return self.controller.last_audit_package

    def run_audit_integrity(self) -> AuditIntegrityResult:
        """Delegate audit integrity validation to the controller (Stage 15N)."""
        return self.controller.run_audit_integrity()

    def generate_audit_package(self) -> ToleranceDecisionAuditPackage:
        """Delegate audit package generation to the controller (Stage 15O)."""
        return self.controller.run_audit_package()

    @property
    def audit_integrity_status_text(self) -> str:
        """Presentation text for the current audit integrity state."""
        integrity = self.controller.last_audit_integrity
        if integrity is None:
            return _NO_AUDIT_TEXT
        return integrity.status.value.upper()

    @property
    def audit_package_status_text(self) -> str:
        """Presentation text for the current audit package replayability."""
        package = self.controller.last_audit_package
        if package is None:
            return _NO_AUDIT_TEXT
        return package.replayability_status.value.upper()

    @property
    def audit_package_id_text(self) -> str:
        """Short display of the audit package_id; empty when not generated."""
        package = self.controller.last_audit_package
        if package is None:
            return ""
        return package.package_id[:16] + "…"

    def audit_integrity_violations_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the integrity violations treeview."""
        integrity = self.controller.last_audit_integrity
        if integrity is None:
            return []
        rows: list[dict[str, object]] = []
        for v in integrity.violations:
            rows.append({
                "severity": v.severity.value,
                "code": v.code.value,
                "scope": v.scope,
                "subject": v.subject,
                "detail": v.detail,
            })
        return rows

    def audit_manifest_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the replay manifest treeview."""
        package = self.controller.last_audit_package
        if package is None:
            return []
        manifest = package.replay_manifest
        rows: list[dict[str, object]] = [
            {"field": "Package ID", "value": manifest.package_id[:24] + "…"},
            {"field": "Decision ID", "value": manifest.decision_id[:24] + "…"},
            {"field": "Integrity", "value": manifest.integrity_status.value},
            {
                "field": "Replayable",
                "value": package.replayability_status.value,
            },
            {"field": "Complete", "value": str(manifest.is_complete)},
            {
                "field": "Equality ε",
                "value": f"{manifest.equality_tolerance:.6g}",
            },
        ]
        if manifest.sigma_multiplier is not None:
            rows.append(
                {"field": "σ multiplier", "value": f"{manifest.sigma_multiplier:.6g}"}
            )
        rows.append(
            {"field": "Input FP", "value": manifest.input_fingerprint[:16] + "…"}
        )
        rows.append(
            {"field": "Report FP", "value": manifest.report_fingerprint[:16] + "…"}
        )
        return rows

    def allocation_editor_rows(self) -> list[dict[str, object]]:
        """Rows for the allocation plan editor table; one per current contributor."""
        rows: list[dict[str, object]] = []
        for c in self.controller.contributors:
            rows.append({
                "contributor_id": c.identifier,
                "contributor_name": c.name,
                "current_span": c.tolerance * 2.0,
                "allocated_span_str": self._allocation_spans.get(c.identifier, ""),
            })
        return rows

    @property
    def last_allocation_validation(self) -> AllocationValidationResult | None:
        """Current allocation validation result; None when not yet run."""
        return self.controller.last_allocation_validation

    def validate_allocation(self) -> AllocationValidationResult:
        """Delegate allocation validation to the controller (Stage 17E-2)."""
        return self.controller.validate_allocation()

    @property
    def last_reconciliation(self) -> AllocationReconciliationResult | None:
        """Current reconciliation result; None when not yet run."""
        return self.controller.last_reconciliation

    def run_reconciliation(self) -> AllocationReconciliationResult:
        """Delegate reconciliation to the controller (Stage 15I)."""
        return self.controller.run_reconciliation()

    @property
    def reconciliation_status_text(self) -> str:
        """Presentation text for the current reconciliation state."""
        rec = self.controller.last_reconciliation
        if rec is None:
            return _NO_RECONCILIATION_TEXT
        return rec.reconciliation_status.value.upper()

    @property
    def reconciliation_summary_text(self) -> str:
        """Compact summary: Budget / Allocated / Actual / Margin."""
        rec = self.controller.last_reconciliation
        if rec is None:
            return ""
        return (
            f"Budget: {rec.allowed_budget:.6g}  "
            f"Allocated: {rec.allocated_total:.6g}  "
            f"Actual: {rec.actual_total_span:.6g}  "
            f"Margin: {rec.total_allocation_margin:.6g}"
        )

    def reconciliation_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the reconciliation table; empty when not run."""
        rec = self.controller.last_reconciliation
        if rec is None:
            return []
        rows: list[dict[str, object]] = []
        for rank, cc in enumerate(rec.contributor_compliances, start=1):
            rows.append({
                "rank": rank,
                "contributor_id": cc.contributor_id,
                "allocated_span": cc.allocated_span,
                "actual_span": cc.actual_span,
                "margin": cc.margin,
                "utilization_pct": cc.utilization_percentage,
                "status": cc.status.value,
            })
        return rows

    @property
    def allocation_validation_status_text(self) -> str:
        """Presentation text for the current allocation validation state."""
        validation = self.controller.last_allocation_validation
        if validation is None:
            return _NO_ALLOCATION_VALIDATION_TEXT
        return validation.status.value.upper()

    @property
    def allocation_validation_summary_text(self) -> str:
        """Compact summary: Budget / Allocated / Remaining / Utilization."""
        validation = self.controller.last_allocation_validation
        if validation is None:
            return ""
        complete = "complete" if validation.is_complete else "incomplete"
        return (
            f"Budget: {validation.allowed_budget:.6g}  "
            f"Allocated: {validation.allocated_total:.6g}  "
            f"Remaining: {validation.remaining_unallocated:.6g}  "
            f"Utilization: {validation.utilization_percentage:.1f}%  "
            f"({complete})"
        )

    def allocation_validation_rows(self) -> list[dict[str, object]]:
        """Presentation rows for the allocation validation table; empty when not run."""
        validation = self.controller.last_allocation_validation
        if validation is None:
            return []
        rows: list[dict[str, object]] = []
        for rank, cr in enumerate(validation.contributor_results, start=1):
            rows.append({
                "rank": rank,
                "contributor_id": cr.contributor_id,
                "allocated_span": cr.allocated_span,
                "current_span": cr.current_span,
                "delta_from_current": cr.delta_from_current,
                "fraction_pct": 100.0 * cr.fraction_of_allowed_budget,
            })
        return rows

    def save_project(
        self, path: str | Path, *, project_name: str | None = None
    ) -> Path:
        return self.controller.save_project(path, project_name=project_name)


class ToleranceWorkspaceView:
    """Tkinter view backed by :class:`ToleranceWorkspaceController`."""

    def __init__(
        self,
        controller: ToleranceWorkspaceController | None = None,
        *,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self._tk = tk
        self._ttk = ttk
        self._filedialog = filedialog
        self._messagebox = messagebox
        self._session = WorkspaceSession(
            controller
            or ToleranceWorkspaceController.empty(
                chain_name="Tolerance chain",
                analysis_mode=AnalysisMode.WORST_CASE,
            )
        )
        self._on_error = on_error
        self.root = tk.Tk()
        self.root.title("Origlyph  ·  Tolerance Workspace")
        self.root.minsize(820, 640)
        self.root.geometry("960x800")
        self._chain_name = tk.StringVar(value=self.controller.state.chain_name)
        self._analysis_mode = tk.StringVar(
            value=self.controller.analysis_mode.value
        )
        self._identifier = tk.StringVar()
        self._name = tk.StringVar()
        self._nominal = tk.StringVar()
        self._tolerance = tk.StringVar()
        self._direction = tk.StringVar(value=StackDirection.FORWARD.value)
        spec = self.controller.specification
        self._allowed_wc_span = tk.StringVar(
            value=_spec_field_str(spec, "allowed_worst_case_span")
        )
        self._allowed_sigma = tk.StringVar(
            value=_spec_field_str(spec, "allowed_combined_sigma")
        )
        self._result = tk.StringVar(value=self._session.result_text)
        self._decision_status = tk.StringVar(value=_NO_DECISION_TEXT)
        self._decision_detail = tk.StringVar(value="")
        self._sensitivity_tree: Any = None
        self._budget_status = tk.StringVar(value=_NO_BUDGET_TEXT)
        self._budget_summary = tk.StringVar(value="")
        self._budget_tree: Any = None
        self._allocation_budget_var = tk.StringVar(
            value=self._session.allocation_budget
        )
        self._alloc_span_entry_var = tk.StringVar()
        self._alloc_selected_id: str | None = None
        self._allocation_validation_status = tk.StringVar(
            value=self._session.allocation_validation_status_text
        )
        self._allocation_validation_summary = tk.StringVar(
            value=self._session.allocation_validation_summary_text
        )
        self._allocation_plan_tree: Any = None
        self._allocation_result_tree: Any = None
        self._reconciliation_status = tk.StringVar(
            value=self._session.reconciliation_status_text
        )
        self._reconciliation_summary = tk.StringVar(
            value=self._session.reconciliation_summary_text
        )
        self._reconciliation_tree: Any = None
        self._stat_alloc_sigma_multiplier_var = tk.StringVar(
            value=self._session.stat_sigma_multiplier
        )
        self._stat_alloc_budget_var = tk.StringVar(
            value=self._session.stat_allocation_budget
        )
        self._stat_alloc_sigma_entry_var = tk.StringVar()
        self._stat_alloc_selected_id: str | None = None
        self._stat_reconciliation_status = tk.StringVar(
            value=self._session.statistical_reconciliation_status_text
        )
        self._stat_reconciliation_summary = tk.StringVar(
            value=self._session.statistical_reconciliation_summary_text
        )
        self._stat_alloc_plan_tree: Any = None
        self._stat_reconciliation_tree: Any = None
        self._evidence_status = tk.StringVar(
            value=self._session.evidence_status_text
        )
        self._explanation_summary = tk.StringVar(value="")
        self._evidence_tree: Any = None
        self._report_status = tk.StringVar(value=self._session.report_status_text)
        self._report_summary = tk.StringVar(value="")
        self._report_tree: Any = None
        self._audit_integrity_status = tk.StringVar(
            value=self._session.audit_integrity_status_text
        )
        self._audit_package_status = tk.StringVar(
            value=self._session.audit_package_status_text
        )
        self._audit_package_id = tk.StringVar(
            value=self._session.audit_package_id_text
        )
        self._audit_violations_tree: Any = None
        self._audit_manifest_tree: Any = None
        self._build()
        self._refresh_rows()
        self._refresh_allocation_plan()
        self._refresh_allocation_validation()
        self._refresh_reconciliation()
        self._refresh_statistical_allocation_plan()
        self._refresh_statistical_reconciliation()
        self._refresh_evidence()
        self._refresh_report()
        self._refresh_audit()

    @property
    def controller(self) -> ToleranceWorkspaceController:
        return self._session.controller

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        tk = self._tk
        ttk = self._ttk
        _canvas = tk.Canvas(self.root, highlightthickness=0)
        _sb = ttk.Scrollbar(self.root, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_sb.set)
        _sb.pack(side="right", fill="y")
        _canvas.pack(side="left", fill="both", expand=True)
        main = ttk.Frame(_canvas, padding=12)
        _win = _canvas.create_window((0, 0), window=main, anchor="nw")
        main.columnconfigure(0, weight=1)
        main.bind(
            "<Configure>",
            lambda _e: _canvas.configure(scrollregion=_canvas.bbox("all")),
        )
        _canvas.bind(
            "<Configure>",
            lambda _e: _canvas.itemconfigure(_win, width=_e.width),
        )
        _canvas.bind(
            "<MouseWheel>",
            lambda _e: _canvas.yview_scroll(int(-1 * (_e.delta / 120)), "units"),
        )
        fields = (
            ("Id", self._identifier),
            ("Name", self._name),
            ("Nominal", self._nominal),
            ("Tolerance", self._tolerance),
        )
        modes = [mode.value for mode in AnalysisMode]
        context = ttk.Labelframe(main, text="Project context", padding=8)
        context.grid(row=0, column=0, sticky="ew")
        context.columnconfigure(1, weight=1)
        ttk.Label(context, text="Chain").grid(row=0, column=0, sticky="w")
        chain = ttk.Entry(context, textvariable=self._chain_name)
        chain.grid(row=0, column=1, sticky="ew")
        chain.bind("<FocusOut>", lambda _event: self._guard(self._sync_header))
        chain.bind("<Return>", lambda _event: self._guard(self._sync_header))
        ttk.Label(context, text="Mode").grid(row=0, column=2, sticky="w")
        mode = ttk.Combobox(
            context,
            textvariable=self._analysis_mode,
            values=modes,
            state="readonly",
        )
        mode.grid(row=0, column=3, sticky="ew", padx=(8, 0))
        mode.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._guard(self._sync_header),
        )

        spec_frame = ttk.Labelframe(main, text="Specification limits", padding=8)
        spec_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(spec_frame, text="Allowed WC Span").grid(row=0, column=0, sticky="w")
        wc_entry = ttk.Entry(spec_frame, textvariable=self._allowed_wc_span, width=14)
        wc_entry.grid(row=0, column=1, sticky="ew", padx=(4, 16))
        wc_entry.bind(
            "<FocusOut>", lambda _event: self._guard(self._sync_specification)
        )
        wc_entry.bind("<Return>", lambda _event: self._guard(self._sync_specification))
        ttk.Label(spec_frame, text="Allowed σ").grid(row=0, column=2, sticky="w")
        sigma_entry = ttk.Entry(
            spec_frame, textvariable=self._allowed_sigma, width=14
        )
        sigma_entry.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        sigma_entry.bind(
            "<FocusOut>", lambda _event: self._guard(self._sync_specification)
        )
        sigma_entry.bind(
            "<Return>", lambda _event: self._guard(self._sync_specification)
        )
        ttk.Label(spec_frame, text="(leave blank = unspecified)").grid(
            row=1, column=0, columnspan=4, sticky="w"
        )

        editor = ttk.Labelframe(main, text="Tolerance chain editor", padding=8)
        editor.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        editor.columnconfigure(5, weight=1)
        for column, (label, var) in enumerate(fields):
            ttk.Label(editor, text=label).grid(row=0, column=column, sticky="w")
            ttk.Entry(editor, textvariable=var, width=12).grid(
                row=1, column=column, sticky="ew", padx=(0, 6)
            )
        ttk.Label(editor, text="Direction").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            editor,
            textvariable=self._direction,
            values=[item.value for item in StackDirection],
            state="readonly",
            width=10,
        ).grid(row=1, column=4, sticky="ew", padx=(0, 6))
        ttk.Button(editor, text="Add", command=self._add).grid(
            row=1, column=5, sticky="ew"
        )
        ttk.Button(editor, text="Update", command=self._edit).grid(
            row=1, column=6, sticky="ew", padx=(6, 0)
        )
        self._rows = ttk.Treeview(
            editor,
            columns=("id", "name", "nominal", "tolerance", "direction"),
            show="headings",
            height=9,
        )
        headings = (
            ("id", "Id"),
            ("name", "Name"),
            ("nominal", "Nominal"),
            ("tolerance", "Tolerance"),
            ("direction", "Direction"),
        )
        for key, label in headings:
            self._rows.heading(key, text=label)
            self._rows.column(key, width=120, stretch=True)
        self._rows.grid(row=2, column=0, columnspan=7, sticky="nsew", pady=(8, 0))
        self._rows.bind(
            "<<TreeviewSelect>>", lambda _event: self._guard(self._populate_form)
        )
        editor.rowconfigure(2, weight=1)
        row_actions = ttk.Frame(editor)
        row_actions.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(6, 0))
        ttk.Button(row_actions, text="Remove", command=self._remove_selected).pack(
            side="left"
        )

        control = ttk.Labelframe(main, text="Analysis control", padding=8)
        control.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            control, text="Run Analysis", command=self._run_analysis
        ).pack(side="left")

        results = ttk.Labelframe(main, text="Results", padding=8)
        results.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        results.columnconfigure(0, weight=1)
        ttk.Label(results, textvariable=self._result).grid(
            row=0, column=0, sticky="w"
        )

        decision = ttk.Labelframe(main, text="Decision", padding=8)
        decision.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        decision.columnconfigure(1, weight=1)
        ttk.Button(
            decision, text="Evaluate Decision", command=self._run_decision
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            decision,
            textvariable=self._decision_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(decision, textvariable=self._decision_detail).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        sensitivity = ttk.Labelframe(main, text="Sensitivity", padding=8)
        sensitivity.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        sensitivity.columnconfigure(0, weight=1)
        ttk.Button(
            sensitivity, text="Run Sensitivity", command=self._run_sensitivity
        ).pack(side="top", anchor="w")
        self._sensitivity_tree = ttk.Treeview(
            sensitivity,
            columns=("rank", "name", "impact", "share"),
            show="headings",
            height=5,
        )
        _sens_cols = (("rank", "Rank", 50), ("name", "Contributor", 160),
                      ("impact", "Impact", 110), ("share", "Share %", 80))
        for key, label, width in _sens_cols:
            self._sensitivity_tree.heading(key, text=label)
            self._sensitivity_tree.column(key, width=width, stretch=True)
        self._sensitivity_tree.pack(side="top", fill="x", pady=(6, 0))

        budget_frame = ttk.Labelframe(main, text="Budget", padding=8)
        budget_frame.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        budget_frame.columnconfigure(0, weight=1)
        ttk.Button(
            budget_frame, text="Run Budget", command=self._run_budget
        ).pack(side="top", anchor="w")
        ttk.Label(
            budget_frame,
            textvariable=self._budget_status,
            font=("", 10, "bold"),
        ).pack(side="top", anchor="w", pady=(4, 0))
        ttk.Label(
            budget_frame, textvariable=self._budget_summary
        ).pack(side="top", anchor="w", pady=(2, 0))
        self._budget_tree = ttk.Treeview(
            budget_frame,
            columns=("rank", "name", "span", "pct_consumed", "pct_allowed"),
            show="headings",
            height=4,
        )
        _budget_cols = (
            ("rank", "Rank", 50),
            ("name", "Contributor", 160),
            ("span", "Span", 110),
            ("pct_consumed", "% Consumed", 90),
            ("pct_allowed", "% Budget", 90),
        )
        for key, label, width in _budget_cols:
            self._budget_tree.heading(key, text=label)
            self._budget_tree.column(key, width=width, stretch=True)
        self._budget_tree.pack(side="top", fill="x", pady=(6, 0))

        recon_frame = ttk.Labelframe(main, text="Reconciliation", padding=8)
        recon_frame.grid(row=10, column=0, sticky="ew", pady=(8, 0))
        recon_frame.columnconfigure(1, weight=1)
        ttk.Button(
            recon_frame, text="Run Reconciliation", command=self._run_reconciliation
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            recon_frame,
            textvariable=self._reconciliation_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            recon_frame, textvariable=self._reconciliation_summary
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._reconciliation_tree = ttk.Treeview(
            recon_frame,
            columns=("contributor", "allocated", "actual", "margin", "utilization",
                     "status"),
            show="headings",
            height=4,
        )
        _recon_cols = (
            ("contributor", "Contributor", 140),
            ("allocated", "Allocated", 90),
            ("actual", "Actual Span", 90),
            ("margin", "Margin", 80),
            ("utilization", "Utiliz. %", 80),
            ("status", "Status", 110),
        )
        for key, label, width in _recon_cols:
            self._reconciliation_tree.heading(key, text=label)
            self._reconciliation_tree.column(key, width=width, stretch=True)
        self._reconciliation_tree.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )

        self._build_evidence_frame(main)

        stat_alloc_plan = ttk.Labelframe(
            main, text="Statistical Allocation Plan", padding=8
        )
        stat_alloc_plan.grid(row=12, column=0, sticky="ew", pady=(8, 0))
        stat_alloc_plan.columnconfigure(3, weight=1)
        ttk.Label(stat_alloc_plan, text="Sigma Multiplier (k)").grid(
            row=0, column=0, sticky="w"
        )
        stat_mult_entry = ttk.Entry(
            stat_alloc_plan,
            textvariable=self._stat_alloc_sigma_multiplier_var,
            width=10,
        )
        stat_mult_entry.grid(row=0, column=1, sticky="ew", padx=(4, 16))
        ttk.Label(stat_alloc_plan, text="Allowed Combined σ (opt.)").grid(
            row=0, column=2, sticky="w"
        )
        stat_budget_entry = ttk.Entry(
            stat_alloc_plan, textvariable=self._stat_alloc_budget_var, width=14
        )
        stat_budget_entry.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self._stat_alloc_plan_tree = ttk.Treeview(
            stat_alloc_plan,
            columns=("contributor", "current_sigma", "allocated_sigma"),
            show="headings",
            height=4,
        )
        _stat_alloc_cols = (
            ("contributor", "Contributor", 160),
            ("current_sigma", "Current σ", 110),
            ("allocated_sigma", "Allocated σ", 110),
        )
        for key, label, width in _stat_alloc_cols:
            self._stat_alloc_plan_tree.heading(key, text=label)
            self._stat_alloc_plan_tree.column(key, width=width, stretch=True)
        self._stat_alloc_plan_tree.grid(
            row=1, column=0, columnspan=4, sticky="nsew", pady=(8, 0)
        )
        self._stat_alloc_plan_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._guard(self._stat_alloc_tree_select),
        )
        ttk.Label(stat_alloc_plan, text="Allocated σ for Selected:").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        stat_sigma_entry = ttk.Entry(
            stat_alloc_plan, textvariable=self._stat_alloc_sigma_entry_var, width=14
        )
        stat_sigma_entry.grid(row=2, column=1, sticky="ew", padx=(4, 16), pady=(6, 0))
        ttk.Button(
            stat_alloc_plan, text="Set σ", command=self._set_stat_alloc_sigma
        ).grid(row=2, column=2, sticky="ew", pady=(6, 0))
        stat_alloc_btn_row = ttk.Frame(stat_alloc_plan)
        stat_alloc_btn_row.grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0)
        )
        ttk.Button(
            stat_alloc_btn_row,
            text="Apply Statistical Plan",
            command=self._apply_statistical_allocation_plan,
        ).pack(side="left")
        ttk.Button(
            stat_alloc_btn_row,
            text="Clear Statistical Plan",
            command=self._clear_statistical_allocation_plan_action,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            stat_alloc_btn_row,
            text="Run Statistical Reconciliation",
            command=self._run_statistical_reconciliation,
        ).pack(side="left", padx=(8, 0))

        stat_recon_frame = ttk.Labelframe(
            main, text="Statistical Reconciliation", padding=8
        )
        stat_recon_frame.grid(row=13, column=0, sticky="ew", pady=(8, 0))
        stat_recon_frame.columnconfigure(1, weight=1)
        ttk.Label(
            stat_recon_frame,
            textvariable=self._stat_reconciliation_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            stat_recon_frame, textvariable=self._stat_reconciliation_summary
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._stat_reconciliation_tree = ttk.Treeview(
            stat_recon_frame,
            columns=("contributor", "alloc_sigma", "actual_sigma", "margin",
                     "utilization", "status"),
            show="headings",
            height=4,
        )
        _stat_recon_cols = (
            ("contributor", "Contributor", 140),
            ("alloc_sigma", "Alloc σ", 80),
            ("actual_sigma", "Actual σ", 80),
            ("margin", "Margin σ", 80),
            ("utilization", "Utiliz. %", 80),
            ("status", "Status", 120),
        )
        for key, label, width in _stat_recon_cols:
            self._stat_reconciliation_tree.heading(key, text=label)
            self._stat_reconciliation_tree.column(key, width=width, stretch=True)
        self._stat_reconciliation_tree.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )

        self._build_report_frame(main)
        self._build_audit_frame(main)

        storage = ttk.Labelframe(main, text="Project File", padding=8)
        storage.grid(row=16, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(storage, text="Open Project", command=self._open).pack(side="left")
        ttk.Button(storage, text="Save Project", command=self._save).pack(
            side="left", padx=(8, 0)
        )

        alloc_plan = ttk.Labelframe(main, text="Allocation Plan", padding=8)
        alloc_plan.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        alloc_plan.columnconfigure(3, weight=1)
        ttk.Label(alloc_plan, text="Allocation Budget").grid(
            row=0, column=0, sticky="w"
        )
        alloc_budget_entry = ttk.Entry(
            alloc_plan, textvariable=self._allocation_budget_var, width=14
        )
        alloc_budget_entry.grid(row=0, column=1, sticky="ew", padx=(4, 16))
        ttk.Label(alloc_plan, text="(required, > 0)").grid(
            row=0, column=2, sticky="w"
        )
        self._allocation_plan_tree = ttk.Treeview(
            alloc_plan,
            columns=("contributor", "current_span", "allocated_span"),
            show="headings",
            height=4,
        )
        _alloc_plan_cols = (
            ("contributor", "Contributor", 160),
            ("current_span", "Current Span", 110),
            ("allocated_span", "Allocated Span", 110),
        )
        for key, label, width in _alloc_plan_cols:
            self._allocation_plan_tree.heading(key, text=label)
            self._allocation_plan_tree.column(key, width=width, stretch=True)
        self._allocation_plan_tree.grid(
            row=1, column=0, columnspan=4, sticky="nsew", pady=(8, 0)
        )
        self._allocation_plan_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._guard(self._alloc_tree_select),
        )
        ttk.Label(alloc_plan, text="Allocated Span for Selected:").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        span_entry = ttk.Entry(
            alloc_plan, textvariable=self._alloc_span_entry_var, width=14
        )
        span_entry.grid(row=2, column=1, sticky="ew", padx=(4, 16), pady=(6, 0))
        ttk.Button(
            alloc_plan, text="Set Span", command=self._set_alloc_span
        ).grid(row=2, column=2, sticky="ew", pady=(6, 0))
        alloc_btn_row = ttk.Frame(alloc_plan)
        alloc_btn_row.grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0)
        )
        ttk.Button(
            alloc_btn_row,
            text="Apply Allocation Plan",
            command=self._apply_allocation_plan,
        ).pack(side="left")
        ttk.Button(
            alloc_btn_row,
            text="Clear Allocation Plan",
            command=self._clear_allocation_plan_action,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            alloc_btn_row,
            text="Validate Allocation",
            command=self._run_validate_allocation,
        ).pack(side="left", padx=(8, 0))

        alloc_result = ttk.Labelframe(
            main, text="Allocation Validation Result", padding=8
        )
        alloc_result.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        alloc_result.columnconfigure(1, weight=1)
        ttk.Label(alloc_result, text="Status:").grid(row=0, column=0, sticky="w")
        ttk.Label(
            alloc_result,
            textvariable=self._allocation_validation_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            alloc_result, textvariable=self._allocation_validation_summary
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._allocation_result_tree = ttk.Treeview(
            alloc_result,
            columns=("contributor", "allocated", "current", "delta", "fraction"),
            show="headings",
            height=4,
        )
        _alloc_result_cols = (
            ("contributor", "Contributor", 140),
            ("allocated", "Allocated", 90),
            ("current", "Current Span", 100),
            ("delta", "Delta", 80),
            ("fraction", "% of Budget", 90),
        )
        for key, label, width in _alloc_result_cols:
            self._allocation_result_tree.heading(key, text=label)
            self._allocation_result_tree.column(key, width=width, stretch=True)
        self._allocation_result_tree.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )

    def _sync_header(self) -> None:
        """Push header widgets into the controller, keeping the same instance."""
        session = self._session
        session.chain_name = self._chain_name.get()
        session.analysis_mode = self._analysis_mode.get()
        session.sync_header()
        self._refresh_result()

    def _sync_specification(self) -> None:
        """Push specification entry fields to the controller (Stage 17A).

        Empty field means unspecified — not zero.  Invalid values are routed
        through the guard and surfaced without updating state.  No analysis is
        triggered here.
        """
        session = self._session
        session.allowed_wc_span = self._allowed_wc_span.get()
        session.allowed_sigma = self._allowed_sigma.get()
        session.sync_specification()
        self._refresh_decision()

    def _refresh_result(self) -> None:
        """Keep the Results label in step with the controller cache."""
        self._result.set(self._session.result_text)
        self._refresh_decision()
        self._refresh_sensitivity()
        self._refresh_budget()
        self._refresh_allocation_plan()
        self._refresh_allocation_validation()
        self._refresh_reconciliation()
        self._refresh_statistical_allocation_plan()
        self._refresh_statistical_reconciliation()
        self._refresh_evidence()
        self._refresh_report()

    def _refresh_decision(self) -> None:
        """Keep the Decision labels in step with the controller cache."""
        self._decision_status.set(self._session.decision_text)
        self._decision_detail.set(self._session.decision_detail_text)

    def _run_decision(self) -> None:
        self._guard(lambda: self._run_decision_impl())

    def _run_decision_impl(self) -> None:
        self._sync_header()
        self._session.evaluate_decision()
        self._refresh_decision()
        self._refresh_evidence()
        self._refresh_report()

    def _refresh_sensitivity(self) -> None:
        """Keep the Sensitivity treeview in step with the controller cache."""
        tree = self._sensitivity_tree
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.sensitivity_rows():
            tree.insert(
                "",
                "end",
                values=(
                    row["rank"],
                    row["name"],
                    f"{row['impact']:.6g}",
                    f"{row['share_pct']:.1f}%",
                ),
            )

    def _run_sensitivity(self) -> None:
        self._guard(lambda: self._run_sensitivity_impl())

    def _run_sensitivity_impl(self) -> None:
        self._sync_header()
        self._session.run_sensitivity()
        self._refresh_sensitivity()

    def _clear_form(self) -> None:
        for var in (self._identifier, self._name, self._nominal, self._tolerance):
            var.set("")

    def _add(self) -> None:
        self._guard(lambda: self._add_impl())

    def _add_impl(self) -> None:
        self._sync_header()
        self.controller.add_contributor(
            identifier=self._identifier.get(),
            name=self._name.get(),
            nominal=self._nominal.get(),
            tolerance=self._tolerance.get(),
            direction=self._direction.get(),
            tolerance_model="symmetric",
        )
        self._clear_form()
        self._refresh_rows()
        self._refresh_result()

    def _edit(self) -> None:
        self._guard(lambda: self._edit_impl())

    def _edit_impl(self) -> None:
        self._sync_header()
        selected = self._rows.selection()
        if not selected:
            raise InvalidToleranceWorkspaceError("select a contributor to update")
        self.controller.edit_contributor(
            str(selected[0]),
            name=self._name.get(),
            nominal=self._nominal.get(),
            tolerance=self._tolerance.get(),
            direction=self._direction.get(),
        )
        self._clear_form()
        self._refresh_rows()
        self._refresh_result()

    def _populate_form(self) -> None:
        selected = self._rows.selection()
        if not selected:
            return
        row = self._rows.item(str(selected[0]))["values"]
        self._identifier.set(str(row[0]))
        self._name.set(str(row[1]))
        self._nominal.set(str(row[2]))
        self._tolerance.set(str(row[3]))
        self._direction.set(str(row[4]))

    def _remove_selected(self) -> None:
        self._guard(lambda: self._remove_impl())

    def _remove_impl(self) -> None:
        selected = self._rows.selection()
        if not selected:
            raise InvalidToleranceWorkspaceError("select a contributor to remove")
        self.controller.remove_contributor(str(selected[0]))
        self._refresh_rows()
        self._refresh_result()

    def _run_analysis(self) -> None:
        self._guard(lambda: self._run_impl())

    def _run_impl(self) -> None:
        self._sync_header()
        self._session.run_analysis()
        self._refresh_result()

    def _open(self) -> None:
        self._guard(lambda: self._open_impl())

    def _open_impl(self) -> None:
        path = self._filedialog.askopenfilename(
            filetypes=[("Origlyph project", "*.json")]
        )
        if not path:
            return
        self._session.controller = ToleranceWorkspaceController.open_project(path)
        self._session.chain_name = self.controller.state.chain_name
        self._session.analysis_mode = self.controller.analysis_mode.value
        self._chain_name.set(self.controller.state.chain_name)
        self._analysis_mode.set(self.controller.analysis_mode.value)
        spec = self.controller.specification
        self._allowed_wc_span.set(
            _spec_field_str(spec, "allowed_worst_case_span")
        )
        self._allowed_sigma.set(
            _spec_field_str(spec, "allowed_combined_sigma")
        )
        self._session.allowed_wc_span = self._allowed_wc_span.get()
        self._session.allowed_sigma = self._allowed_sigma.get()
        self._session.load_allocation_plan_fields()
        self._allocation_budget_var.set(self._session.allocation_budget)
        self._alloc_span_entry_var.set("")
        self._alloc_selected_id = None
        self._session.load_statistical_allocation_plan_fields()
        self._stat_alloc_sigma_multiplier_var.set(self._session.stat_sigma_multiplier)
        self._stat_alloc_budget_var.set(self._session.stat_allocation_budget)
        self._stat_alloc_sigma_entry_var.set("")
        self._stat_alloc_selected_id = None
        self._refresh_rows()
        self._refresh_result()

    def _save(self) -> None:
        self._guard(lambda: self._save_impl())

    def _save_impl(self) -> None:
        self._sync_header()
        path = self._filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Origlyph project", "*.json")],
        )
        if not path:
            return
        self._session.save_project(Path(path), project_name=self._chain_name.get())

    def _refresh_rows(self) -> None:
        selected = self._rows.selection()
        previous = str(selected[0]) if selected else None
        for row_id in self._rows.get_children():
            self._rows.delete(row_id)
        for item in self.controller.contributors:
            self._rows.insert(
                "",
                "end",
                iid=item.identifier,
                values=(
                    item.identifier,
                    item.name,
                    item.nominal,
                    item.tolerance,
                    item.direction.value,
                ),
            )
        if previous is not None and self._rows.exists(previous):
            self._rows.selection_set(previous)
            self._rows.see(previous)

    def _run_budget(self) -> None:
        self._guard(lambda: self._run_budget_impl())

    def _run_budget_impl(self) -> None:
        self._sync_header()
        self._session.run_budget()
        self._refresh_budget()

    def _refresh_budget(self) -> None:
        """Keep the Budget panel in step with the controller cache."""
        self._budget_status.set(self._session.budget_status_text)
        self._budget_summary.set(self._session.budget_summary_text)
        tree = self._budget_tree
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.budget_rows():
            tree.insert(
                "",
                "end",
                values=(
                    row["rank"],
                    row["name"],
                    f"{row['span']:.6g}",
                    f"{row['pct_consumed']:.1f}%",
                    f"{row['pct_allowed']:.1f}%",
                ),
            )

    def _alloc_tree_select(self) -> None:
        selected = self._allocation_plan_tree.selection()
        if not selected:
            self._alloc_selected_id = None
            return
        iid = str(selected[0])
        self._alloc_selected_id = iid
        self._alloc_span_entry_var.set(self._session.pending_span(iid))

    def _set_alloc_span(self) -> None:
        self._guard(lambda: self._set_alloc_span_impl())

    def _set_alloc_span_impl(self) -> None:
        if self._alloc_selected_id is None:
            raise InvalidToleranceWorkspaceError(
                "select a contributor to set its allocated span"
            )
        self._session.set_pending_span(
            self._alloc_selected_id, self._alloc_span_entry_var.get()
        )
        self._refresh_allocation_plan()

    def _apply_allocation_plan(self) -> None:
        self._guard(lambda: self._apply_allocation_plan_impl())

    def _apply_allocation_plan_impl(self) -> None:
        self._session.allocation_budget = self._allocation_budget_var.get()
        self._session.sync_allocation_plan()
        self._refresh_allocation_plan()
        self._refresh_allocation_validation()

    def _clear_allocation_plan_action(self) -> None:
        self._guard(lambda: self._clear_allocation_plan_impl())

    def _clear_allocation_plan_impl(self) -> None:
        self._session.clear_allocation_plan()
        self._allocation_budget_var.set("")
        self._alloc_span_entry_var.set("")
        self._alloc_selected_id = None
        self._refresh_allocation_plan()
        self._refresh_allocation_validation()

    def _run_validate_allocation(self) -> None:
        self._guard(lambda: self._run_validate_allocation_impl())

    def _run_validate_allocation_impl(self) -> None:
        self._session.validate_allocation()
        self._refresh_allocation_validation()

    def _refresh_allocation_plan(self) -> None:
        tree = self._allocation_plan_tree
        if tree is None:
            return
        selected = tree.selection()
        previous_iid = str(selected[0]) if selected else None
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.allocation_editor_rows():
            iid = str(row["contributor_id"])
            span_str = str(row["allocated_span_str"])
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    str(row["contributor_name"]),
                    f"{row['current_span']:.6g}",
                    span_str if span_str else "—",
                ),
            )
        if previous_iid is not None and tree.exists(previous_iid):
            tree.selection_set(previous_iid)
            tree.see(previous_iid)

    def _refresh_allocation_validation(self) -> None:
        self._allocation_validation_status.set(
            self._session.allocation_validation_status_text
        )
        self._allocation_validation_summary.set(
            self._session.allocation_validation_summary_text
        )
        tree = self._allocation_result_tree
        if tree is None:
            return
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.allocation_validation_rows():
            tree.insert(
                "",
                "end",
                values=(
                    str(row["contributor_id"]),
                    f"{row['allocated_span']:.6g}",
                    f"{row['current_span']:.6g}",
                    f"{row['delta_from_current']:.6g}",
                    f"{row['fraction_pct']:.1f}%",
                ),
            )

    def _run_reconciliation(self) -> None:
        self._guard(lambda: self._run_reconciliation_impl())

    def _run_reconciliation_impl(self) -> None:
        self._session.run_reconciliation()
        self._refresh_reconciliation()

    def _refresh_reconciliation(self) -> None:
        """Keep the Reconciliation panel in step with the controller cache."""
        self._reconciliation_status.set(self._session.reconciliation_status_text)
        self._reconciliation_summary.set(self._session.reconciliation_summary_text)
        tree = self._reconciliation_tree
        if tree is None:
            return
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.reconciliation_rows():
            util = row["utilization_pct"]
            util_str = f"{util:.1f}%" if util is not None else "—"
            tree.insert(
                "",
                "end",
                values=(
                    str(row["contributor_id"]),
                    f"{row['allocated_span']:.6g}",
                    f"{row['actual_span']:.6g}",
                    f"{row['margin']:.6g}",
                    util_str,
                    str(row["status"]),
                ),
            )

    def _stat_alloc_tree_select(self) -> None:
        selected = self._stat_alloc_plan_tree.selection()
        if not selected:
            self._stat_alloc_selected_id = None
            return
        iid = str(selected[0])
        self._stat_alloc_selected_id = iid
        self._stat_alloc_sigma_entry_var.set(self._session.pending_sigma(iid))

    def _set_stat_alloc_sigma(self) -> None:
        self._guard(lambda: self._set_stat_alloc_sigma_impl())

    def _set_stat_alloc_sigma_impl(self) -> None:
        if self._stat_alloc_selected_id is None:
            raise InvalidToleranceWorkspaceError(
                "select a contributor to set its allocated sigma"
            )
        self._session.set_pending_sigma(
            self._stat_alloc_selected_id, self._stat_alloc_sigma_entry_var.get()
        )
        self._refresh_statistical_allocation_plan()

    def _apply_statistical_allocation_plan(self) -> None:
        self._guard(lambda: self._apply_statistical_allocation_plan_impl())

    def _apply_statistical_allocation_plan_impl(self) -> None:
        self._session.stat_sigma_multiplier = (
            self._stat_alloc_sigma_multiplier_var.get()
        )
        self._session.stat_allocation_budget = self._stat_alloc_budget_var.get()
        self._session.sync_statistical_allocation_plan()
        self._refresh_statistical_allocation_plan()
        self._refresh_statistical_reconciliation()

    def _clear_statistical_allocation_plan_action(self) -> None:
        self._guard(lambda: self._clear_statistical_allocation_plan_impl())

    def _clear_statistical_allocation_plan_impl(self) -> None:
        self._session.clear_statistical_allocation_plan()
        self._stat_alloc_sigma_multiplier_var.set("")
        self._stat_alloc_budget_var.set("")
        self._stat_alloc_sigma_entry_var.set("")
        self._stat_alloc_selected_id = None
        self._refresh_statistical_allocation_plan()
        self._refresh_statistical_reconciliation()

    def _run_statistical_reconciliation(self) -> None:
        self._guard(lambda: self._run_statistical_reconciliation_impl())

    def _run_statistical_reconciliation_impl(self) -> None:
        self._session.run_statistical_reconciliation()
        self._refresh_statistical_reconciliation()

    def _refresh_statistical_allocation_plan(self) -> None:
        tree = self._stat_alloc_plan_tree
        if tree is None:
            return
        selected = tree.selection()
        previous_iid = str(selected[0]) if selected else None
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.statistical_allocation_editor_rows():
            iid = str(row["contributor_id"])
            sigma_str = str(row["allocated_sigma_str"])
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    str(row["contributor_name"]),
                    f"{row['current_sigma']:.6g}",
                    sigma_str if sigma_str else "—",
                ),
            )
        if previous_iid is not None and tree.exists(previous_iid):
            tree.selection_set(previous_iid)
            tree.see(previous_iid)

    def _refresh_statistical_reconciliation(self) -> None:
        """Keep the Statistical Reconciliation panel in step with the cache."""
        self._stat_reconciliation_status.set(
            self._session.statistical_reconciliation_status_text
        )
        self._stat_reconciliation_summary.set(
            self._session.statistical_reconciliation_summary_text
        )
        tree = self._stat_reconciliation_tree
        if tree is None:
            return
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.statistical_reconciliation_rows():
            util = row["utilization_pct"]
            util_str = f"{util:.1f}%" if util is not None else "—"
            tree.insert(
                "",
                "end",
                values=(
                    str(row["contributor_id"]),
                    f"{row['allocated_sigma']:.6g}",
                    f"{row['actual_sigma']:.6g}",
                    f"{row['margin']:.6g}",
                    util_str,
                    str(row["status"]),
                ),
            )

    def _build_evidence_frame(self, main: Any) -> None:
        ttk = self._ttk
        evidence_frame = ttk.Labelframe(
            main, text="Decision Evidence & Explanation", padding=8
        )
        evidence_frame.grid(row=11, column=0, sticky="ew", pady=(8, 0))
        evidence_frame.columnconfigure(1, weight=1)
        ttk.Button(
            evidence_frame, text="Generate Evidence", command=self._generate_evidence
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            evidence_frame,
            textvariable=self._evidence_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            evidence_frame, textvariable=self._explanation_summary
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._evidence_tree = ttk.Treeview(
            evidence_frame,
            columns=("code", "source", "scope", "observed", "reference",
                     "severity", "detail"),
            show="headings",
            height=5,
        )
        _evidence_cols = (
            ("code", "Evidence Code", 160),
            ("source", "Source", 100),
            ("scope", "Scope", 90),
            ("observed", "Observed", 90),
            ("reference", "Reference", 90),
            ("severity", "Severity", 75),
            ("detail", "Detail", 200),
        )
        for key, label, width in _evidence_cols:
            self._evidence_tree.heading(key, text=label)
            self._evidence_tree.column(key, width=width, stretch=True)
        self._evidence_tree.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )

    def _generate_evidence(self) -> None:
        self._guard(lambda: self._generate_evidence_impl())

    def _generate_evidence_impl(self) -> None:
        self._session.generate_evidence()
        self._refresh_evidence()

    def _refresh_evidence(self) -> None:
        """Keep the Evidence panel in step with the controller cache."""
        self._evidence_status.set(self._session.evidence_status_text)
        self._explanation_summary.set(self._session.explanation_summary_text)
        tree = self._evidence_tree
        if tree is None:
            return
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.evidence_items_rows():
            obs = row["observed_value"]
            ref = row["reference_value"]
            obs_str = f"{obs:.6g}" if obs is not None else "—"
            ref_str = f"{ref:.6g}" if ref is not None else "—"
            tree.insert(
                "",
                "end",
                values=(
                    str(row["evidence_code"]),
                    str(row["source"]),
                    str(row["scope"]),
                    obs_str,
                    ref_str,
                    str(row["severity"]),
                    str(row["detail"]),
                ),
            )

    def _build_report_frame(self, main: Any) -> None:
        ttk = self._ttk
        report_frame = ttk.Labelframe(
            main, text="Decision Report", padding=8
        )
        report_frame.grid(row=14, column=0, sticky="ew", pady=(8, 0))
        report_frame.columnconfigure(1, weight=1)
        ttk.Button(
            report_frame, text="Generate Decision Report", command=self._generate_report
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            report_frame,
            textvariable=self._report_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            report_frame, textvariable=self._report_summary
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._report_tree = ttk.Treeview(
            report_frame,
            columns=("name", "type", "value", "sigma"),
            show="headings",
            height=4,
        )
        _report_cols = (
            ("name", "Contributor", 160),
            ("type", "Type", 100),
            ("value", "Value", 90),
            ("sigma", "Sigma", 90),
        )
        for key, label, width in _report_cols:
            self._report_tree.heading(key, text=label)
            self._report_tree.column(key, width=width, stretch=True)
        self._report_tree.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )

    def _generate_report(self) -> None:
        self._guard(lambda: self._generate_report_impl())

    def _generate_report_impl(self) -> None:
        self._session.generate_decision_report()
        self._refresh_report()

    def _refresh_report(self) -> None:
        """Keep the Decision Report panel in step with the controller cache."""
        self._report_status.set(self._session.report_status_text)
        self._report_summary.set(self._session.report_summary_text)
        tree = self._report_tree
        if tree is None:
            return
        for row_id in tree.get_children():
            tree.delete(row_id)
        for row in self._session.report_contributors_rows():
            tree.insert("", "end", values=(
                str(row["name"]), str(row["type"]),
                str(row["value"]), str(row["sigma"]),
            ))

    def _build_audit_frame(self, main: Any) -> None:
        ttk = self._ttk
        audit_frame = ttk.Labelframe(main, text="Audit Package", padding=8)
        audit_frame.grid(row=15, column=0, sticky="ew", pady=(8, 0))
        audit_frame.columnconfigure(1, weight=1)
        ttk.Button(
            audit_frame,
            text="Generate Audit Package",
            command=self._run_audit_package,
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            audit_frame,
            textvariable=self._audit_package_status,
            font=("", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            audit_frame, text="Integrity:", font=("", 9, "bold")
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(
            audit_frame, textvariable=self._audit_integrity_status
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(
            audit_frame, text="Package ID:", font=("", 9, "bold")
        ).grid(row=2, column=0, sticky="w")
        ttk.Label(
            audit_frame, textvariable=self._audit_package_id
        ).grid(row=2, column=1, sticky="w")
        self._audit_violations_tree = ttk.Treeview(
            audit_frame,
            columns=("severity", "code", "scope", "subject", "detail"),
            show="headings",
            height=3,
        )
        _violations_cols = (
            ("severity", "Severity", 70),
            ("code", "Code", 140),
            ("scope", "Scope", 90),
            ("subject", "Subject", 90),
            ("detail", "Detail", 180),
        )
        for key, label, width in _violations_cols:
            self._audit_violations_tree.heading(key, text=label)
            self._audit_violations_tree.column(key, width=width, stretch=True)
        self._audit_violations_tree.grid(
            row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )
        self._audit_manifest_tree = ttk.Treeview(
            audit_frame,
            columns=("field", "value"),
            show="headings",
            height=5,
        )
        self._audit_manifest_tree.heading("field", text="Manifest Field")
        self._audit_manifest_tree.column("field", width=120, stretch=False)
        self._audit_manifest_tree.heading("value", text="Value")
        self._audit_manifest_tree.column("value", width=320, stretch=True)
        self._audit_manifest_tree.grid(
            row=4, column=0, columnspan=2, sticky="nsew", pady=(4, 0)
        )

    def _run_audit_package(self) -> None:
        self._guard(lambda: self._run_audit_package_impl())

    def _run_audit_package_impl(self) -> None:
        self._session.generate_audit_package()
        self._refresh_audit()

    def _refresh_audit(self) -> None:
        """Keep the Audit Package panel in step with the controller cache."""
        self._audit_integrity_status.set(self._session.audit_integrity_status_text)
        self._audit_package_status.set(self._session.audit_package_status_text)
        self._audit_package_id.set(self._session.audit_package_id_text)
        vtree = self._audit_violations_tree
        if vtree is not None:
            for row_id in vtree.get_children():
                vtree.delete(row_id)
            for row in self._session.audit_integrity_violations_rows():
                vtree.insert("", "end", values=(
                    str(row["severity"]), str(row["code"]),
                    str(row["scope"]), str(row["subject"]), str(row["detail"]),
                ))
        mtree = self._audit_manifest_tree
        if mtree is not None:
            for row_id in mtree.get_children():
                mtree.delete(row_id)
            for row in self._session.audit_manifest_rows():
                mtree.insert("", "end", values=(
                    str(row["field"]), str(row["value"]),
                ))

    def _guard(self, action: Callable[[], Any]) -> None:
        try:
            action()
        except Exception as exc:
            if self._on_error is not None:
                self._on_error(exc)
                return
            self._messagebox.showerror(
                "Origlyph Tolerance Workspace", str(exc)
            )


def launch_tolerance_workspace(
    controller: ToleranceWorkspaceController | None = None,
) -> None:
    ToleranceWorkspaceView(controller).run()
