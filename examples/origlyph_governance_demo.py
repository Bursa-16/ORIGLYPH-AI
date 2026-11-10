"""Origlyph governance restore demo (Stage 21G).

Demonstrates the full governance chain, project save/reload cycle, and
deterministic governance state restoration.

Run:
    python examples/origlyph_governance_demo.py

No timestamps, no machine-local paths, no external dependencies.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from origlyph.tolerance.acceptance_record import AuditAcceptanceDecision
from origlyph.tolerance.workspace_controller import (
    AnalysisMode,
    ToleranceWorkspaceController,
    WorkspaceAcceptanceState,
    WorkspaceSpecification,
)


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _write_audit_package(ctrl: ToleranceWorkspaceController, dest: Path) -> None:
    pkg = ctrl.last_audit_package
    assert pkg is not None
    dest.write_text(
        json.dumps(
            pkg.as_dict(),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as _tmp:
        tmp = Path(_tmp)
        project_path = tmp / "demo_project.json"
        comparison_path = tmp / "comparison_pkg.json"

        # ------------------------------------------------------------------
        # Step 1: Build a workspace and run the full governance chain.
        # ------------------------------------------------------------------
        _separator("Step 1: Build workspace and run governance chain")

        ctrl = ToleranceWorkspaceController(
            chain_name="Demo tolerance chain",
            analysis_mode=AnalysisMode.WORST_CASE,
        )
        ctrl.add_contributor(
            identifier="shaft_od",
            name="Shaft outer diameter",
            nominal=25.0,
            tolerance=0.05,
            direction="forward",
            tolerance_model="symmetric",
        )
        ctrl.add_contributor(
            identifier="housing_id",
            name="Housing inner diameter",
            nominal=25.0,
            tolerance=0.05,
            direction="reverse",
            tolerance_model="symmetric",
        )
        ctrl.add_contributor(
            identifier="bearing_clearance",
            name="Bearing running clearance",
            nominal=0.0,
            tolerance=0.02,
            direction="forward",
            tolerance_model="symmetric",
        )
        ctrl.set_specification(WorkspaceSpecification(allowed_worst_case_span=0.5))

        ctrl.run_analysis()
        ctrl.evaluate_decision()
        ctrl.run_decision_evidence()
        ctrl.run_decision_report()
        ctrl.run_audit_integrity()
        ctrl.run_audit_package()

        print(f"  Contributors : {len(ctrl.contributors)}")
        print(f"  Decision     : {ctrl.last_decision.verdict.value}")  # type: ignore[union-attr]
        print(f"  Audit pkg    : fingerprint={ctrl.last_audit_package.fingerprint!r}")  # type: ignore[union-attr]

        # Write audit package for comparison
        _write_audit_package(ctrl, comparison_path)

        # Run comparison-dependent chain
        ctrl.load_comparison_audit_package(comparison_path)
        ctrl.run_audit_comparison()
        ctrl.run_change_impact()
        ctrl.run_change_disposition()
        ctrl.run_approval_readiness()
        handoff = ctrl.run_acceptance_handoff()

        print(f"  Handoff ID   : {handoff.handoff_id!r}")

        # Set acceptance inputs and complete chain
        ctrl.set_acceptance_state(
            WorkspaceAcceptanceState(
                decision=AuditAcceptanceDecision.APPROVED,
                authority_reference="AUTHORITY-2026-001",
                decision_reference="DECISION-2026-001",
                handoff_id=handoff.handoff_id,
            )
        )
        ctrl.run_acceptance_record()
        ctrl.run_acceptance_verification()
        ctrl.run_acceptance_closure()

        print("  Acceptance closure: COMPLETE")
        assert ctrl.last_acceptance_closure is not None

        # ------------------------------------------------------------------
        # Step 2: Save project.
        # ------------------------------------------------------------------
        _separator("Step 2: Save project")

        ctrl.save_project(project_path, project_name="Demo tolerance chain")
        print(f"  Saved to     : {project_path.name}")

        # ------------------------------------------------------------------
        # Step 3: Reload project — prove all derived state is absent.
        # ------------------------------------------------------------------
        _separator("Step 3: Reload project — derived state absent")

        reloaded = ToleranceWorkspaceController.open_project(project_path)
        print(f"  Chain name   : {reloaded.state.chain_name!r}")
        print(f"  Contributors : {len(reloaded.contributors)}")
        print(f"  last_decision_report  : {reloaded.last_decision_report}")
        print(f"  last_audit_package    : {reloaded.last_audit_package}")
        print(f"  last_acceptance_closure: {reloaded.last_acceptance_closure}")

        assert reloaded.last_decision_report is None
        assert reloaded.last_audit_package is None
        assert reloaded.last_acceptance_closure is None
        print("  CONFIRMED: all governance artifacts absent after reload.")

        # ------------------------------------------------------------------
        # Step 4: Restore governance state.
        # ------------------------------------------------------------------
        _separator("Step 4: Restore governance state")

        fp_before = reloaded.configuration_fingerprint()
        reloaded.restore_governance_state(comparison_path=comparison_path)
        fp_after = reloaded.configuration_fingerprint()

        print(f"  Fingerprint before : {fp_before!r}")
        print(f"  Fingerprint after  : {fp_after!r}")
        assert fp_before == fp_after, "Configuration fingerprint must be unchanged"
        print("  CONFIRMED: project identity unchanged after restore.")

        assert reloaded.last_decision_report is not None
        assert reloaded.last_audit_package is not None
        assert reloaded.last_audit_comparison is not None
        assert reloaded.last_acceptance_handoff is not None
        assert reloaded.last_acceptance_record is not None
        assert reloaded.last_acceptance_verification is not None
        assert reloaded.last_acceptance_closure is not None
        print("  CONFIRMED: full governance chain restored.")

        # ------------------------------------------------------------------
        # Step 5: Prove determinism — restored IDs match original IDs.
        # ------------------------------------------------------------------
        _separator("Step 5: Prove determinism")

        orig_hid = handoff.handoff_id
        rest_hid = reloaded.last_acceptance_handoff.handoff_id  # type: ignore[union-attr]
        print(f"  Original handoff_id  : {orig_hid!r}")
        print(f"  Restored handoff_id  : {rest_hid!r}")
        assert orig_hid == rest_hid, "Handoff ID must be identical after restore"
        print("  CONFIRMED: restored handoff_id matches original.")

        orig_fp = ctrl.last_audit_package.fingerprint  # type: ignore[union-attr]
        rest_fp = reloaded.last_audit_package.fingerprint  # type: ignore[union-attr]
        print(f"  Original pkg fingerprint: {orig_fp!r}")
        print(f"  Restored pkg fingerprint: {rest_fp!r}")
        assert orig_fp == rest_fp, "Audit package fingerprint must be identical"
        print("  CONFIRMED: restored audit package fingerprint matches original.")

        # ------------------------------------------------------------------
        # Step 6: Prove authoritative acceptance inputs unchanged.
        # ------------------------------------------------------------------
        _separator("Step 6: Authoritative acceptance inputs preserved")

        acc_orig = ctrl.state.acceptance_state
        acc_rest = reloaded.state.acceptance_state
        assert acc_orig == acc_rest
        print(f"  Decision  : {acc_rest.decision.value}")  # type: ignore[union-attr]
        print(f"  Authority : {acc_rest.authority_reference!r}")  # type: ignore[union-attr]
        print("  CONFIRMED: acceptance inputs unchanged after restore.")

        # ------------------------------------------------------------------
        # Step 7: Export unified HTML report from restored state.
        # ------------------------------------------------------------------
        _separator("Step 7: Export unified HTML report from restored state")

        html_path = tmp / "origlyph_engineering_report.html"
        reloaded.export_unified_html_report(html_path)
        html_size = html_path.stat().st_size
        print(f"  HTML report  : {html_path.name} ({html_size:,} bytes)")
        assert html_size > 0
        print("  CONFIRMED: unified HTML report exported successfully.")

        _separator("Demo complete — all assertions passed")
        print()


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as exc:
        print(f"\nDEMO FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
