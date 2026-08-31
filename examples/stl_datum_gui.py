"""Minimal Tkinter desktop GUI shell for the Origlyph STL -> datum workflow.

Stage 14B. A thin GUI over the exact deterministic production pipeline used by
the Stage 13A CLI demo:

    StlImporter.import_document
    extract_candidates
    bind_reference
    bind_datum_constraint / bind_datum_reference_frame

Architecture
------------
* :class:`DatumGuiController` holds the pure, testable orchestration logic and
  the minimal GUI state. It never imports ``tkinter`` and never touches a
  display, so every behavioural test can run headless.
* :class:`StlDatumTk` is a thin Tk view over the controller. It imports
  ``tkinter`` lazily inside the constructor so the controller stays
  display-free.

Honest, non-inferring guarantees kept identical to the production pipeline:

* STL has no units: the GUI *declares* millimetres explicitly and never
  performs unit inference or unit conversion.
* The STL stored facet normal is diagnostics only and is always labelled
  ``Authority: NON-AUTHORITATIVE``; the winding-derived
  ``BoundedPlanarFace.plane.normal`` is the geometry authority.
* Every PRIMARY / SECONDARY / TERTIARY assignment is an explicit user action.
  The same candidate can never occupy two roles simultaneously, and the
  controller shows every release/replacement change. There is no ranking,
  scoring, or automatic datum recommendation of any kind.
* Skipped / degenerate / unsupported content is always surfaced, never hidden.

Usage:
    py examples/stl_datum_gui.py

Security / engineering boundaries: local files only, no network, no
telemetry, no cloud, no AI, no mesh repair, no topology inference, no
GD&T-compliance claim, no engineering-tolerance acceptance.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Optional

from origlyph._version import __version__
from origlyph.cad import (
    CadFormat,
    SourceDocumentIdentity,
    SourceUnitSystem,
    StlImporter,
    bind_datum_reference_frame,
    bind_reference,
)
from origlyph.cad.bridge import (
    BridgedCandidate,
    CandidateResult,
    extract_candidates,
)
from origlyph.cad.exceptions import OriglyphCadError
from origlyph.cad.model import NeutralModel
from origlyph.datum import ConstraintType, DatumReferenceFrame
from origlyph.geometry.bounded import BoundedPlanarFace

__all__ = ["DatumGuiController", "StlDatumTk", "DISCLAIMER_TEXT", "main"]

DECLARED_LENGTH_UNIT = "mm"
FRAME_NAME = "gui-demo-3-2-1"

DISCLAIMER_TEXT = (
    "Manual assignment only - Origlyph does not automatically rank or "
    "recommend datum features."
)

NO_RANKING_TEXT = (
    "No ranking, scoring, or automatic datum recommendation is performed: "
    "every role assignment is an explicit user choice."
)

_ERROR_NO_SELECTION = "no candidate row selected"
_ERROR_INVALID_INDEX = "candidate index out of range"
_ERROR_INCOMPLETE = (
    "complete 3-2-1 DRF requires three distinct explicit assignments "
    "(PRIMARY, SECONDARY, TERTIARY)"
)

def _fmt_vector3(x, y, z) -> str:
    return f"({x}, {y}, {z})"


def _fmt_point(value) -> str:
    return _fmt_vector3(value.x, value.y, value.z)


def _fmt_stl_normal(value) -> Optional[str]:
    """Format the stored STL normal as a diagnostic string, if present.

    The stored normal is a plain ``(nx, ny, nz)`` tuple in the importer
    metadata and is diagnostics-only; the winding-derived face normal is the
    geometry authority.
    """
    if value is None:
        return None
    x, y, z = (float(component) for component in value)
    return f"{_fmt_vector3(x, y, z)} Authority: NON-AUTHORITATIVE"


class DatumGuiController:
    """Pure orchestration + minimal state for the GUI.

    Provides every behaviour the view needs while staying completely
    independent of Tk. All roles are explicit user choices; nothing is ever
    inferred, ranked, or recommended.
    """

    def __init__(self) -> None:
        self.selected_file: Optional[str] = None
        self.neutral_model: Optional[NeutralModel] = None
        self.candidate_result: Optional[CandidateResult] = None
        self.candidate_rows: list[tuple[str, str, str, str, str, Optional[str]]] = []
        self._candidates: dict[int, BridgedCandidate] = {}
        self.selected_candidate_index: Optional[int] = None
        self.primary_candidate: Optional[int] = None
        self.secondary_candidate: Optional[int] = None
        self.tertiary_candidate: Optional[int] = None
        self.drf_result: Optional[DatumReferenceFrame] = None
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Clear every piece of GUI/controller state (no persistence)."""
        self.selected_file = None
        self.neutral_model = None
        self.candidate_result = None
        self.candidate_rows = []
        self._candidates = {}
        self.selected_candidate_index = None
        self.primary_candidate = None
        self.secondary_candidate = None
        self.tertiary_candidate = None
        self.drf_result = None
        self.last_error = None

    # ------------------------------------------------------------------ #
    # Import
    # ------------------------------------------------------------------ #
    def load_path(self, path: str | Path) -> bool:
        """Validate, read and import one local ``.stl`` file.

        The filesystem boundary lives here (in the GUI), exactly as it does in
        the CLI demo; the importer itself stays filesystem-free.
        """
        candidate_path = Path(path)
        if not candidate_path.exists():
            self._fail(f"path does not exist: {candidate_path}")
            return False
        if not candidate_path.is_file():
            self._fail(
                f"not a regular file (is it a directory?): {candidate_path}"
            )
            return False
        if candidate_path.suffix.lower() != ".stl":
            self._fail(
                f"unsupported file extension {candidate_path.suffix!r}; "
                "expected '.stl'"
            )
            return False
        try:
            payload = candidate_path.read_bytes()
        except OSError as exc:
            self._fail(f"could not read STL file: {exc}")
            return False
        return self.load_payload(candidate_path, payload)

    def load_payload(self, path: str | Path, payload: bytes) -> bool:
        """Import ``payload`` through the production pipeline, refresh rows."""
        source_path = Path(path)
        document = SourceDocumentIdentity(
            source_id=source_path.name,
            format=CadFormat.STL,
            unit_system=SourceUnitSystem(length_unit=DECLARED_LENGTH_UNIT),
            original_filename=source_path.name,
            fingerprint=hashlib.sha256(payload).hexdigest(),
        )
        importer = StlImporter(bytes_loader=lambda _document: payload)
        try:
            model = importer.import_document(document)
        except OriglyphCadError as exc:
            self._fail(f"STL import failed: {exc}")
            return False

        result = extract_candidates(model)
        rows: list[tuple[str, str, str, str, str, Optional[str]]] = []
        candidates: dict[int, BridgedCandidate] = {}
        for index, candidate in enumerate(result.candidates):
            entry = model.entity_by_identity(candidate.neutral_identity)
            geometry = entry.geometry if entry is not None else None
            centroid = (
                _fmt_point(geometry.centroid)
                if isinstance(geometry, BoundedPlanarFace)
                else "-"
            )
            winding = (
                _fmt_vector3(
                    geometry.plane.normal.x,
                    geometry.plane.normal.y,
                    geometry.plane.normal.z,
                )
                if isinstance(geometry, BoundedPlanarFace)
                else "-"
            )
            stl_normal = (
                _fmt_stl_normal(entry.metadata.get("stl_normal"))
                if entry is not None
                else None
            )
            kind = (
                candidate.datum_feature.kind.value
                if candidate.datum_feature is not None
                and candidate.datum_feature.kind is not None
                else "-"
            )
            rows.append(
                (
                    candidate.neutral_identity.source_identity.source_entity_key
                    if candidate.neutral_identity.source_identity is not None
                    else "unknown",
                    kind,
                    candidate.domain_identity.value,
                    centroid,
                    winding,
                    stl_normal,
                )
            )
            candidates[index] = candidate

        # A new file always resets prior assignment and DRF state.
        self.selected_file = str(source_path)
        self.neutral_model = model
        self.candidate_result = result
        self.candidate_rows = rows
        self._candidates = candidates
        self.selected_candidate_index = None
        self.primary_candidate = None
        self.secondary_candidate = None
        self.tertiary_candidate = None
        self.drf_result = None
        self.last_error = None
        return True

    # ------------------------------------------------------------------ #
    # Import summary
    # ------------------------------------------------------------------ #
    @property
    def valid_facets(self) -> int:
        return len(self.neutral_model.entities) if self.neutral_model else 0

    @property
    def warnings(self) -> list[str]:
        if self.neutral_model is None:
            return []
        return [
            f"[{warning.code}] {warning.message}"
            for warning in self.neutral_model.warnings
        ]

    @property
    def unsupported_facets(self) -> int:
        return len(self.neutral_model.unsupported) if self.neutral_model else 0

    @property
    def candidate_count(self) -> int:
        return len(self.candidate_rows)

    # ------------------------------------------------------------------ #
    # Explicit role assignment (single ownership per candidate)
    # ------------------------------------------------------------------ #
    def assign(self, role: ConstraintType, index: Optional[int]) -> None:
        """Explicitly assign ``index`` to ``role``.

        Single-ownership policy, applied visibly and deterministically:

        * if ``index`` already owns another role, that previous role is
          released before the new assignment;
        * if the target role already holds a different candidate, that old
          holder is replaced;
        * a candidate can therefore never occupy two roles at once.
        """
        if index is None:
            self._fail(_ERROR_NO_SELECTION)
            return
        if index not in self._candidates:
            self._fail(_ERROR_INVALID_INDEX)
            return
        if self.primary_candidate == index:
            self.primary_candidate = None
        if self.secondary_candidate == index:
            self.secondary_candidate = None
        if self.tertiary_candidate == index:
            self.tertiary_candidate = None
        if role is ConstraintType.PRIMARY:
            self.primary_candidate = index
        elif role is ConstraintType.SECONDARY:
            self.secondary_candidate = index
        elif role is ConstraintType.TERTIARY:
            self.tertiary_candidate = index
        else:  # pragma: no cover - only three roles exist
            self._fail(f"unknown role {role!r}")
            return
        self.drf_result = None
        self.last_error = None

    def clear_assignments(self) -> None:
        self.primary_candidate = None
        self.secondary_candidate = None
        self.tertiary_candidate = None
        self.drf_result = None
        self.last_error = None

    @property
    def has_three_distinct_roles(self) -> bool:
        return (
            self.primary_candidate is not None
            and self.secondary_candidate is not None
            and self.tertiary_candidate is not None
            and len(
                {
                    self.primary_candidate,
                    self.secondary_candidate,
                    self.tertiary_candidate,
                }
            )
            == 3
        )

    # ------------------------------------------------------------------ #
    # DRF construction (fail-closed; existing production APIs only)
    # ------------------------------------------------------------------ #
    def build_drf(self) -> bool:
        """Build a demo 3-2-1 DRF from the three explicit assignments.

        Uses the existing ``bind_reference`` + ``bind_datum_reference_frame``
        pipeline (which internally applies ``bind_datum_constraint``) and
        re-checks fail-closed regardless of the caller.
        """
        if not self.has_three_distinct_roles:
            self._fail(_ERROR_INCOMPLETE)
            return False
        role_indexes = {
            ConstraintType.PRIMARY: self.primary_candidate,
            ConstraintType.SECONDARY: self.secondary_candidate,
            ConstraintType.TERTIARY: self.tertiary_candidate,
        }
        ordered_roles = (
            ConstraintType.PRIMARY,
            ConstraintType.SECONDARY,
            ConstraintType.TERTIARY,
        )
        assignments = []
        for role in ordered_roles:
            index = role_indexes[role]
            assert index is not None  # guarded by has_three_distinct_roles
            candidate = self._candidates[index]
            assignments.append((bind_reference(candidate), role))
        try:
            frame = bind_datum_reference_frame(FRAME_NAME, assignments)
        except (OriglyphCadError, TypeError, ValueError) as exc:
            self._fail(f"DRF construction failed: {exc}")
            return False
        self.drf_result = frame
        self.last_error = None
        return True

    # ------------------------------------------------------------------ #
    # Presentation helpers
    # ------------------------------------------------------------------ #
    def role_holder(self, role: ConstraintType) -> Optional[int]:
        if role is ConstraintType.PRIMARY:
            return self.primary_candidate
        if role is ConstraintType.SECONDARY:
            return self.secondary_candidate
        return self.tertiary_candidate

    def drf_sequence_text(self) -> str:
        if self.drf_result is None:
            return ""
        return " -> ".join(
            str(constraint.sequence)
            for constraint in self.drf_result.constraints
        )

    def _fail(self, message: str) -> None:
        self.last_error = message
        # DRF stays cleared on any failure; retaining a previous frame would
        # hide the failing state from the user.
        self.drf_result = None


# ---------------------------------------------------------------------- #
# View
# ---------------------------------------------------------------------- #
class StlDatumTk:
    """Thin Tkinter view over :class:`DatumGuiController`.

    ``tkinter`` is imported lazily so importing this module never touches a
    display; a real Tcl/Tk interpreter is required only when a window is
    actually created.
    """

    def __init__(self, root, controller: DatumGuiController) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.controller = controller
        root.title(f"Origlyph {__version__}")

        # TOP BAR
        bar = ttk.Frame(root, padding=(8, 6))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar, text="Origlyph", font=("Segoe UI", 14, "bold")).pack(
            side=tk.LEFT
        )
        self.version_var = tk.StringVar(value=f"v{__version__}")
        ttk.Label(
            bar, textvariable=self.version_var, foreground="#606060"
        ).pack(side=tk.LEFT, padx=(8, 12))
        ttk.Button(bar, text="Open STL", command=self._open_stl).pack(
            side=tk.LEFT
        )
        self.file_var = tk.StringVar(value="(no file)")
        ttk.Label(bar, textvariable=self.file_var).pack(side=tk.LEFT, padx=12)

        # BODY
        body = ttk.Frame(root, padding=(8, 6))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # LEFT - Import summary
        left = ttk.LabelFrame(body, text="Import Summary", padding=8)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        self.summary_var = tk.StringVar(value="")
        ttk.Label(
            left,
            textvariable=self.summary_var,
            justify=tk.LEFT,
            wraplength=210,
        ).pack(anchor=tk.W)

        # CENTER - Candidates table
        center = ttk.Frame(body)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        columns = ("index", "facet", "kind", "centroid", "normal")
        self.tree = ttk.Treeview(center, columns=columns, show="headings")
        for column_id, heading, width in (
            ("index", "IDX", 40),
            ("facet", "Facet", 90),
            ("kind", "Kind", 70),
            ("centroid", "Centroid / origin", 170),
            ("normal", "Winding normal", 170),
        ):
            self.tree.heading(column_id, text=heading)
            self.tree.column(column_id, width=width, anchor=tk.W)
        scroll = ttk.Scrollbar(
            center, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # RIGHT - Datum assignment
        right = ttk.LabelFrame(body, text="Datum Assignment", padding=8)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        self.role_vars: dict[ConstraintType, tk.StringVar] = {}
        for role in (
            ConstraintType.PRIMARY,
            ConstraintType.SECONDARY,
            ConstraintType.TERTIARY,
        ):
            self.role_vars[role] = tk.StringVar(value="(none)")
            ttk.Label(right, text=f"{role.value}:").pack(anchor=tk.W, pady=(2, 0))
            ttk.Label(right, textvariable=self.role_vars[role]).pack(
                anchor=tk.W
            )
            ttk.Button(
                right,
                text=f"Assign {role.value.title()}",
                command=lambda r=role: self._assign(r),
            ).pack(anchor=tk.W, pady=(2, 0))
        ttk.Button(
            right, text="Clear assignments", command=self._clear_roles
        ).pack(anchor=tk.W, pady=(6, 2))
        self.build_button = ttk.Button(
            right, text="Build DRF", state="disabled", command=self._build_drf
        )
        self.build_button.pack(anchor=tk.W, pady=(2, 0))

        # BOTTOM - Result / Messages
        bottom = ttk.LabelFrame(root, text="Result / Messages", padding=8)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))
        self.result_var = tk.StringVar(value="")
        ttk.Label(
            bottom,
            textvariable=self.result_var,
            justify=tk.LEFT,
            wraplength=760,
        ).pack(anchor=tk.W)
        self.detail_var = tk.StringVar(value="")
        ttk.Label(
            bottom,
            textvariable=self.detail_var,
            justify=tk.LEFT,
            wraplength=760,
        ).pack(anchor=tk.W)

        # PERMANENT DISCLAIMER
        ttk.Label(
            root, text=DISCLAIMER_TEXT, foreground="#a04040"
        ).pack(side=tk.BOTTOM, anchor=tk.W, padx=8, pady=(0, 6))

        self._refresh()

    # -- events ------------------------------------------------- #
    def _open_stl(self) -> None:
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Open STL",
            filetypes=[("STL mesh", "*.stl"), ("All files", "*.*")],
        )
        if not path:  # cancel = silent no-op, state unchanged
            return
        self.controller.load_path(path)
        self._refresh()

    def _on_select(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            self.controller.selected_candidate_index = None
            return
        row_index = int(selection[0])
        self.controller.selected_candidate_index = row_index
        self._refresh_detail()

    def _assign(self, role: ConstraintType) -> None:
        self.controller.assign(role, self.controller.selected_candidate_index)
        self._refresh()

    def _clear_roles(self) -> None:
        self.controller.clear_assignments()
        self._refresh()

    def _build_drf(self) -> None:
        self.controller.build_drf()
        self._refresh()

    # -- rendering ------------------------------------------------ #
    def _refresh(self) -> None:
        controller = self.controller
        self.file_var.set(controller.selected_file or "(no file)")
        summary_lines = [
            f"Declared units: {DECLARED_LENGTH_UNIT}",
            f"Valid planar facets: {controller.valid_facets}",
            f"Warnings: {len(controller.warnings)}",
            *controller.warnings,
            f"Unsupported facets: {controller.unsupported_facets}",
            f"Candidate count: {controller.candidate_count}",
        ]
        self.summary_var.set("\n".join(summary_lines))

        for row in self.tree.get_children():
            self.tree.delete(row)
        for index, row in enumerate(controller.candidate_rows):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(index, row[0], row[1], row[3], row[4]),
            )

        for role in (
            ConstraintType.PRIMARY,
            ConstraintType.SECONDARY,
            ConstraintType.TERTIARY,
        ):
            holder = controller.role_holder(role)
            self.role_vars[role].set(
                f"candidate {holder}" if holder is not None else "(none)"
            )

        can_build = controller.has_three_distinct_roles
        self.build_button.configure(
            state="normal" if can_build else "disabled"
        )

        if controller.last_error:
            self.result_var.set(f"error: {controller.last_error}")
        elif controller.drf_result is not None:
            frame = controller.drf_result
            self.result_var.set(
                "\n".join(
                    [
                        "Datum Reference Frame Demo",
                        f"Sequence: {controller.drf_sequence_text()} (3-2-1)",
                        f"Frame name: {frame.name}",
                        f"Constrained DOF: {frame.total_constrained} of 6",
                        f"Fully located: {frame.is_fully_located}",
                        NO_RANKING_TEXT,
                    ]
                )
            )
        elif can_build:
            self.result_var.set(
                "Assignments complete. Press Build DRF to assemble the "
                "3-2-1 frame."
            )
        else:
            self.result_var.set(
                "Explicitly assign PRIMARY, SECONDARY and TERTIARY to three "
                "distinct candidates to build a demo DRF."
            )

        self._refresh_detail()

    def _refresh_detail(self) -> None:
        index = self.controller.selected_candidate_index
        if (
            index is None
            or not (0 <= index < len(self.controller.candidate_rows))
        ):
            self.detail_var.set("")
            return
        row = self.controller.candidate_rows[index]
        detail = f"Source facet key: {row[0]}"
        if row[5] is not None:
            detail += f"\nSTL diagnostic normal (stored in file): {row[5]}"
        self.detail_var.set(detail)


def main(argv: Optional[list[str]] = None) -> int:
    """Launch the GUI; accepts an optional argv only for test symmetry."""
    if argv is not None and len(argv) > 0:  # pragma: no cover - defensive
        return 2
    import tkinter as tk

    root = tk.Tk()
    StlDatumTk(root, DatumGuiController())
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())