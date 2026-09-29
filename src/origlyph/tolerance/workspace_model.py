"""Thin Tkinter tolerance workspace view (Stage 16D)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import StackDirection
from .workspace_controller import (
    AnalysisMode,
    InvalidToleranceWorkspaceError,
    ToleranceWorkspaceController,
    WorkspaceAnalysisResult,
)

__all__ = ["ToleranceWorkspaceView", "WorkspaceSession", "launch_tolerance_workspace"]

_NO_RESULT_TEXT = "No result"


class WorkspaceSession:
    """Headless view seam owning header sync and result presentation.

    The Tkinter view binds its widgets onto this session so header sync, save,
    and result labelling stay testable without a display.
    """

    def __init__(self, controller: ToleranceWorkspaceController) -> None:
        self.controller = controller
        self.chain_name: str = controller.state.chain_name
        self.analysis_mode: str = controller.analysis_mode.value

    @property
    def result_text(self) -> str:
        """Label text mirroring the controller cache; never a dropped result."""
        result = self.controller.last_result
        if result is None:
            return _NO_RESULT_TEXT
        values = ", ".join(
            f"{key}={value:.6g}" for key, value in result.summary_values.items()
        )
        return f"{result.analysis_mode.value}: {values}"

    def sync_header(self) -> None:
        """Push header fields into the controller without rebuilding it.

        A header-only no-op keeps the cached result; an authoritative change
        invalidates it through the controller setters.
        """
        self.controller.set_chain_name(self.chain_name)
        self.controller.set_analysis_mode(self.analysis_mode)

    def run_analysis(self) -> WorkspaceAnalysisResult:
        return self.controller.run_analysis()

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
        self.root.title("Origlyph Tolerance Workspace")
        self._chain_name = tk.StringVar(value=self.controller.state.chain_name)
        self._analysis_mode = tk.StringVar(
            value=self.controller.analysis_mode.value
        )
        self._identifier = tk.StringVar()
        self._name = tk.StringVar()
        self._nominal = tk.StringVar()
        self._tolerance = tk.StringVar()
        self._direction = tk.StringVar(value=StackDirection.FORWARD.value)
        self._result = tk.StringVar(value=self._session.result_text)
        self._build()
        self._refresh_rows()

    @property
    def controller(self) -> ToleranceWorkspaceController:
        return self._session.controller

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        ttk = self._ttk
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
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

        editor = ttk.Labelframe(main, text="Tolerance chain editor", padding=8)
        editor.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
        control.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(control, text="Run", command=self._run_analysis).pack(side="left")

        results = ttk.Labelframe(main, text="Results", padding=8)
        results.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        results.columnconfigure(0, weight=1)
        ttk.Label(results, textvariable=self._result).grid(
            row=0, column=0, sticky="w"
        )

        storage = ttk.Labelframe(main, text="Save / load", padding=8)
        storage.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(storage, text="Open", command=self._open).pack(side="left")
        ttk.Button(storage, text="Save", command=self._save).pack(
            side="left", padx=(8, 0)
        )

    def _sync_header(self) -> None:
        """Push header widgets into the controller, keeping the same instance.

        Rebuilding the controller here would drop its cached result, so a Save
        after a Run could persist no evidence at all.
        """
        session = self._session
        session.chain_name = self._chain_name.get()
        session.analysis_mode = self._analysis_mode.get()
        session.sync_header()
        self._refresh_result()

    def _refresh_result(self) -> None:
        """Keep the Results label in step with the controller cache."""
        self._result.set(self._session.result_text)

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
