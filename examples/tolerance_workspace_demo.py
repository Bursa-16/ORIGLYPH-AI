"""Customer demo: Origlyph tolerance workspace — full feature walkthrough.

This demo uses a three-contributor bracket-mounting assembly to exercise
the complete tolerance workspace flow end-to-end without a display:

    bracket depth  (forward)  ±0.10
    pin length     (forward)  ±0.08
    shim thickness (inverse)  ±0.05

Specification: allowed WC span = 0.40, allowed combined σ = 0.15
Allocation plan: budget = 0.30, spans [0.12, 0.10, 0.08]

Run headless (prints results)::

    py examples/tolerance_workspace_demo.py --headless

Launch the interactive desktop window::

    py examples/tolerance_workspace_demo.py

Every value is entered explicitly; nothing is inferred.
"""

from __future__ import annotations

import sys

from origlyph.tolerance import (
    ToleranceWorkspaceController,
    WorkspaceAllocationEntry,
    WorkspaceAllocationPlan,
    WorkspaceSpecification,
    WorstCaseSensitivityResult,
    launch_tolerance_workspace,
)


def demo_controller() -> ToleranceWorkspaceController:
    """Build a fully seeded three-contributor demo controller."""
    controller = ToleranceWorkspaceController.empty(
        chain_name="bracket-mounting-assembly",
        analysis_mode="worst_case",
    )

    controller.add_contributor(
        identifier="bracket_depth",
        name="Bracket depth",
        nominal=25.0,
        tolerance=0.10,
        direction="forward",
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="pin_length",
        name="Pin length",
        nominal=5.0,
        tolerance=0.08,
        direction="forward",
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="shim_thickness",
        name="Shim thickness",
        nominal=2.5,
        tolerance=0.05,
        direction="inverse",
        tolerance_model="symmetric",
    )

    controller.set_specification(
        WorkspaceSpecification(
            allowed_worst_case_span=0.40,
            allowed_combined_sigma=0.15,
        )
    )

    controller.set_allocation_plan(
        WorkspaceAllocationPlan(
            allowed_budget=0.30,
            entries=(
                WorkspaceAllocationEntry(
                    contributor_id="bracket_depth", allocated_span=0.12
                ),
                WorkspaceAllocationEntry(
                    contributor_id="pin_length", allocated_span=0.10
                ),
                WorkspaceAllocationEntry(
                    contributor_id="shim_thickness", allocated_span=0.08
                ),
            ),
        )
    )

    return controller


def print_demo(controller: ToleranceWorkspaceController) -> None:
    """Run the full analysis chain and print each stage."""
    print("=" * 60)
    print("Origlyph Tolerance Workspace -- Customer Demo")
    print("=" * 60)

    spec = controller.specification
    if spec:
        print(f"\nSpecification:")
        if spec.allowed_worst_case_span is not None:
            print(f"  Allowed WC span: {spec.allowed_worst_case_span}")
        if spec.allowed_combined_sigma is not None:
            print(f"  Allowed combined sigma: {spec.allowed_combined_sigma}")

    print(f"\nContributors ({len(controller.contributors)}):")
    for c in controller.contributors:
        print(f"  [{c.identifier}]  {c.name}  "
              f"nominal={c.nominal}  tolerance=+/-{c.tolerance}  "
              f"direction={c.direction.value}")

    for mode in ("worst_case", "rss_statistical"):
        controller.set_analysis_mode(mode)
        result = controller.run_analysis()
        decision = controller.evaluate_decision()
        print(f"\n--- {mode.replace('_', ' ').title()} ---")
        for key, value in result.summary_values.items():
            print(f"  {key.replace('_', ' ')}: {value:.6g}")
        print(f"  Decision: {decision.overall_status.value}")

    print(f"\nSensitivity (worst-case):")
    controller.set_analysis_mode("worst_case")
    controller.run_analysis()
    sens = controller.run_sensitivity()
    assert isinstance(sens, WorstCaseSensitivityResult)
    for i, impact in enumerate(sens.impacts, start=1):
        print(f"  rank {i}  {impact.name:<22}  "
              f"span={impact.span:.6g}  share={impact.percentage:.1f}%")

    print(f"\nBudget (worst-case):")
    budget = controller.run_budget()
    print(f"  Status: {budget.status.value}")
    print(f"  Actual span: {budget.actual_span:.6g}  "
          f"Allowed span: {budget.allowed_span:.6g}")
    for c in budget.contributions:
        print(f"  {c.name:<22}  span={c.span:.6g}  "
              f"consumed={c.percentage_of_consumed:.1f}%")

    print(f"\nAllocation validation:")
    alloc_result = controller.validate_allocation()
    print(f"  Status: {alloc_result.status.value}")
    if alloc_result.remaining_unallocated is not None:
        print(f"  Remaining unallocated: {alloc_result.remaining_unallocated:.6g}")

    print(f"\nConfiguration fingerprint: {controller.configuration_fingerprint()}")
    print("\nDemo complete.")


def main(argv: list[str]) -> int:
    controller = demo_controller()
    if "--headless" in argv[1:]:
        print_demo(controller)
        return 0
    launch_tolerance_workspace(controller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
