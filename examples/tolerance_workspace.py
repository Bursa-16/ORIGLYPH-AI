"""Launch the Origlyph tolerance workspace UI (Stage 16D).

The desktop workspace is a thin Tk view over
:class:`origlyph.tolerance.ToleranceWorkspaceController`. The controller owns
the validated state, delegates the calculation to the existing deterministic
tolerance engines, and is fully usable without a display.

Run with a display to open the workspace window::

    py examples/tolerance_workspace.py

Run headless to print the same deterministic result the view would show::

    py examples/tolerance_workspace.py --headless

The seeded chain below is example input, not a measured part. Every value is
entered explicitly and nothing is inferred.
"""

from __future__ import annotations

import sys

from origlyph.tolerance import (
    ToleranceWorkspaceController,
    launch_tolerance_workspace,
)


def demo_controller() -> ToleranceWorkspaceController:
    """Build a controller holding the two-contributor demo chain."""
    controller = ToleranceWorkspaceController.empty(
        chain_name="cover-plate",
        analysis_mode="worst_case",
    )
    controller.add_contributor(
        identifier="cover",
        name="Cover thickness",
        nominal=10.0,
        tolerance=0.20,
        direction="forward",
        tolerance_model="symmetric",
    )
    controller.add_contributor(
        identifier="shim",
        name="Shim thickness",
        nominal=2.5,
        tolerance=0.05,
        direction="inverse",
        tolerance_model="symmetric",
    )
    return controller


def print_result(controller: ToleranceWorkspaceController) -> None:
    """Print the analysis for both supported modes without opening a window."""
    for mode in ("worst_case", "rss_statistical"):
        controller.set_analysis_mode(mode)
        result = controller.run_analysis()
        print(f"mode: {mode}")
        for key, value in result.summary_values.items():
            print(f"  {key}: {value}")
        print(f"  result_id: {result.result_id}")
    print(f"configuration_fingerprint: {controller.configuration_fingerprint()}")


def main(argv: list[str]) -> int:
    if "--headless" in argv[1:]:
        print_result(demo_controller())
        return 0
    launch_tolerance_workspace(demo_controller())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
