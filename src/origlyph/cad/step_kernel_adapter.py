"""Experimental STEP/B-Rep kernel adapter for Origlyph (Stage 22D spike).

This module is a TECHNICAL FEASIBILITY SPIKE only.  It does NOT constitute
production STEP support in Origlyph.

Canonical snapshot identifiers produced here do NOT solve persistent topology
naming across CAD revisions.

No STEP/B-Rep topology is persisted into the Origlyph project model in
Stage 22D.

OCP/OCCT kernel objects are fully isolated behind this module.  None of the
OCP types appear in the returned :class:`CanonicalTopologyModel` or in any
Origlyph domain contract.

Requires optional package ``cadquery-ocp-novtk`` or ``cadquery-ocp``.
If neither is installed, all operations raise :class:`StepKernelUnavailableError`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional

from origlyph.geometry import Point3D

from .exceptions import CadImportError, OriglyphCadError
from .identity import SourceDocumentIdentity
from .topology import (
    CanonicalTopologyModel,
    TopologyEdge,
    TopologyEntityId,
    TopologyFace,
    TopologyOrientation,
    TopologyShell,
    TopologySolid,
    TopologyVertex,
    TopologyWire,
)

__all__ = [
    "StepKernelAdapter",
    "StepKernelUnavailableError",
]

_OCP_SPEC: Optional[bool] = None


def _ocp_available() -> bool:
    global _OCP_SPEC
    if _OCP_SPEC is None:
        _OCP_SPEC = importlib.util.find_spec("OCP") is not None
    return _OCP_SPEC


class StepKernelUnavailableError(OriglyphCadError):
    """Raised when OCP/OCCT kernel is not installed.

    Install ``cadquery-ocp-novtk`` as an optional development dependency to
    enable the experimental STEP adapter.  It is not and must not be a
    production dependency of Origlyph.
    """


class StepKernelAdapter:
    """Experimental STEP file → canonical topology adapter (Stage 22D spike).

    Implements the :class:`~origlyph.cad.topology_adapter.CadTopologyAdapter`
    protocol using OCP (OpenCASCADE Python bindings) as the backend kernel.

    OCP objects are never stored after :meth:`to_canonical_topology` returns.
    The returned :class:`CanonicalTopologyModel` is fully kernel-independent.

    This adapter is intentionally NOT registered as a production importer.
    STEP is not a supported production format in Stage 22D.

    Parameters
    ----------
    step_path:
        Path to the STEP file to convert.
    """

    def __init__(self, step_path: Path) -> None:
        self._step_path = Path(step_path)

    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel:
        """Convert the STEP file to a :class:`CanonicalTopologyModel`.

        Raises
        ------
        StepKernelUnavailableError
            If the OCP package is not installed.
        CadImportError
            On any file access, reading, or B-Rep conversion error.
        """
        if not _ocp_available():
            raise StepKernelUnavailableError(
                "OCP/OCCT kernel is not installed. "
                "Install 'cadquery-ocp-novtk' (optional dev dependency) to enable "
                "the experimental STEP adapter."
            )

        if not self._step_path.exists():
            raise CadImportError(
                f"STEP file not found: {self._step_path.name!r}"
            )
        if not self._step_path.is_file():
            raise CadImportError(
                f"STEP path is not a regular file: {self._step_path.name!r}"
            )

        return _read_and_convert(self._step_path, source)


# ---------------------------------------------------------------------------
# Internal conversion — all OCP imports are local to this function so that
# importing this module never fails even when OCP is absent.
# ---------------------------------------------------------------------------


def _read_and_convert(
    step_path: Path,
    source: SourceDocumentIdentity,
) -> CanonicalTopologyModel:
    """Read a STEP file via OCP and produce a CanonicalTopologyModel."""
    # --- lazy OCP imports (type: ignore because OCP is an optional dep) ------
    from OCP.IFSelect import IFSelect_RetDone  # type: ignore[import-not-found]
    from OCP.STEPControl import STEPControl_Reader  # type: ignore[import-not-found]
    from OCP.TopAbs import TopAbs_SOLID  # type: ignore[import-not-found]
    from OCP.TopExp import TopExp_Explorer  # type: ignore[import-not-found]

    # --- STEP reading -------------------------------------------------------
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        raise CadImportError(
            f"STEP reader failed on {step_path.name!r}: "
            f"IFSelect status={status!r}"
        )

    nb_roots = reader.NbRootsForTransfer()
    if nb_roots == 0:
        raise CadImportError(
            f"STEP file {step_path.name!r} has no transferable roots; "
            f"file may be empty or contain no usable geometry"
        )

    for i in range(1, nb_roots + 1):
        ok = reader.TransferRoot(i)
        if not ok:
            raise CadImportError(
                f"STEP transfer of root {i} failed in {step_path.name!r}"
            )

    compound = reader.OneShape()
    if compound is None or compound.IsNull():
        raise CadImportError(
            f"STEP file {step_path.name!r} produced a null shape after transfer"
        )

    # Require at least one solid body
    exp_solid = TopExp_Explorer(compound, TopAbs_SOLID)
    if not exp_solid.More():
        raise CadImportError(
            f"STEP file {step_path.name!r} contains no solid bodies; "
            f"open-shell STEP files are not supported in this spike"
        )

    # --- topology conversion ------------------------------------------------
    return _build_canonical(compound, source)


def _build_canonical(  # noqa: C901, PLR0912, PLR0914, PLR0915
    compound: object,
    source: SourceDocumentIdentity,
) -> CanonicalTopologyModel:
    """Core conversion: OCC compound → CanonicalTopologyModel.

    Uses traversal-order numbering for all entity IDs.  IDs are deterministic
    for the same STEP file; they are NOT stable across CAD revisions.
    All OCP imports are local to keep the module importable without OCP.
    """
    # fmt: off  # isort cannot sort imports with type-ignore comments on grouped blocks
    from OCP.BRep import BRep_Tool as _BRep_Tool  # type: ignore[import-not-found]  # noqa: I001
    from OCP.BRepTools import BRepTools as _BRepTools  # type: ignore[import-not-found]
    from OCP.TopAbs import TopAbs_REVERSED as _REVERSED  # type: ignore[import-not-found]
    from OCP.TopAbs import TopAbs_SHELL as _SHELL  # type: ignore[import-not-found]
    from OCP.TopAbs import TopAbs_SOLID as _SOLID  # type: ignore[import-not-found]
    from OCP.TopExp import TopExp_Explorer as _TopExp_Explorer  # type: ignore[import-not-found]
    from OCP.TopoDS import TopoDS as _TopoDS  # type: ignore[import-not-found]
    from OCP.TopoDS import TopoDS_Iterator as _Iterator  # type: ignore[import-not-found]
    # fmt: on

    # Registries: list[(occ_shape, domain_entity)]
    # deduplication via occ_shape.IsSame()
    vertex_reg: list[tuple[object, TopologyVertex]] = []
    edge_reg: list[tuple[object, TopologyEdge]] = []
    wire_reg: list[tuple[object, TopologyWire]] = []
    face_reg: list[tuple[object, TopologyFace]] = []
    shell_reg: list[tuple[object, TopologyShell]] = []
    solid_list: list[TopologySolid] = []

    counters: dict[str, int] = {
        "v": 0, "e": 0, "w": 0, "f": 0, "s": 0, "b": 0,
    }

    def next_id(prefix: str) -> TopologyEntityId:
        counters[prefix] += 1
        return TopologyEntityId(f"{prefix}:{counters[prefix]:04d}")

    def _orient(occ_orient: object) -> TopologyOrientation:
        if occ_orient == _REVERSED:
            return TopologyOrientation.REVERSED
        return TopologyOrientation.FORWARD

    def _get_or_add_vertex(shape: object) -> TopologyEntityId:
        for s, v in vertex_reg:
            if shape.IsSame(s):  # type: ignore[union-attr]
                return v.entity_id
        tv = _TopoDS.Vertex(shape)  # type: ignore[union-attr]
        p = _BRep_Tool.Pnt_s(tv)  # type: ignore[union-attr]
        vid = next_id("v")
        vertex = TopologyVertex(
            entity_id=vid,
            point=Point3D(x=p.X(), y=p.Y(), z=p.Z()),
        )
        vertex_reg.append((shape, vertex))
        return vid

    def _get_or_add_edge(shape: object) -> TopologyEntityId:
        for s, e in edge_reg:
            if shape.IsSame(s):  # type: ignore[union-attr]
                return e.entity_id
        # Collect child vertices; REVERSED = start, FORWARD = end (OCC convention)
        it = _Iterator(shape)  # type: ignore[call-arg]
        v_shapes: list[object] = []
        while it.More():  # type: ignore[union-attr]
            v_shapes.append(it.Value())  # type: ignore[union-attr]
            it.Next()  # type: ignore[union-attr]
        if len(v_shapes) < 2:
            raise CadImportError(
                f"edge has {len(v_shapes)} child vertex (expected 2); "
                f"degenerate or self-closing edge"
            )
        start_shape = v_shapes[0]
        end_shape = v_shapes[1]
        for vs in v_shapes:
            if vs.Orientation() == _REVERSED:  # type: ignore[union-attr]
                start_shape = vs
            else:
                end_shape = vs
        start_vid = _get_or_add_vertex(start_shape)
        end_vid = _get_or_add_vertex(end_shape)
        eid = next_id("e")
        edge = TopologyEdge(
            entity_id=eid,
            start_vertex_id=start_vid,
            end_vertex_id=end_vid,
            orientation=_orient(shape.Orientation()),  # type: ignore[union-attr]
        )
        edge_reg.append((shape, edge))
        return eid

    def _get_or_add_wire(shape: object) -> TopologyEntityId:
        for s, w in wire_reg:
            if shape.IsSame(s):  # type: ignore[union-attr]
                return w.entity_id
        it = _Iterator(shape)  # type: ignore[call-arg]
        edge_ids: list[TopologyEntityId] = []
        while it.More():  # type: ignore[union-attr]
            edge_ids.append(_get_or_add_edge(it.Value()))  # type: ignore[union-attr]
            it.Next()  # type: ignore[union-attr]
        if not edge_ids:
            raise CadImportError("wire has no edges; degenerate wire")
        wid = next_id("w")
        wire = TopologyWire(
            entity_id=wid,
            edge_ids=tuple(edge_ids),
            orientation=_orient(shape.Orientation()),  # type: ignore[union-attr]
        )
        wire_reg.append((shape, wire))
        return wid

    def _get_or_add_face(shape: object) -> TopologyEntityId:
        for s, f in face_reg:
            if shape.IsSame(s):  # type: ignore[union-attr]
                return f.entity_id
        topo_face = _TopoDS.Face(shape)  # type: ignore[union-attr]
        outer_shape = _BRepTools.OuterWire_s(topo_face)  # type: ignore[union-attr]

        outer_wid: Optional[TopologyEntityId] = None
        inner_wids: list[TopologyEntityId] = []

        it = _Iterator(shape)  # type: ignore[call-arg]
        while it.More():  # type: ignore[union-attr]
            w = it.Value()  # type: ignore[union-attr]
            wid = _get_or_add_wire(w)
            if outer_shape is not None and w.IsSame(outer_shape):  # type: ignore[union-attr]
                outer_wid = wid
            else:
                inner_wids.append(wid)
            it.Next()  # type: ignore[union-attr]

        if outer_wid is None:
            # Fallback: single wire → outer; multi-wire first → outer
            if inner_wids:
                outer_wid = inner_wids.pop(0)
            else:
                raise CadImportError("face has no wires; cannot construct topology")

        fid = next_id("f")
        face = TopologyFace(
            entity_id=fid,
            outer_wire_id=outer_wid,
            inner_wire_ids=tuple(inner_wids),
            orientation=_orient(shape.Orientation()),  # type: ignore[union-attr]
        )
        face_reg.append((shape, face))
        return fid

    def _get_or_add_shell(shape: object) -> TopologyEntityId:
        for s, sh in shell_reg:
            if shape.IsSame(s):  # type: ignore[union-attr]
                return sh.entity_id
        it = _Iterator(shape)  # type: ignore[call-arg]
        face_ids: list[TopologyEntityId] = []
        while it.More():  # type: ignore[union-attr]
            face_ids.append(_get_or_add_face(it.Value()))  # type: ignore[union-attr]
            it.Next()  # type: ignore[union-attr]
        if not face_ids:
            raise CadImportError("shell has no faces; degenerate shell")
        sid = next_id("s")
        shell = TopologyShell(entity_id=sid, face_ids=tuple(face_ids))
        shell_reg.append((shape, shell))
        return sid

    # --- traverse all solids ------------------------------------------------
    exp = _TopExp_Explorer(compound, _SOLID)  # type: ignore[call-arg]
    while exp.More():  # type: ignore[union-attr]
        solid_shape = exp.Current()  # type: ignore[union-attr]
        it = _Iterator(solid_shape)  # type: ignore[call-arg]
        outer_sid: Optional[TopologyEntityId] = None
        inner_sids: list[TopologyEntityId] = []
        idx = 0
        while it.More():  # type: ignore[union-attr]
            ch = it.Value()  # type: ignore[union-attr]
            if ch.ShapeType() == _SHELL:  # type: ignore[union-attr]
                sid = _get_or_add_shell(ch)
                if idx == 0:
                    outer_sid = sid
                else:
                    inner_sids.append(sid)
                idx += 1
            it.Next()  # type: ignore[union-attr]

        if outer_sid is None:
            raise CadImportError("solid has no shells; degenerate solid body")

        bid = next_id("b")
        solid = TopologySolid(
            entity_id=bid,
            outer_shell_id=outer_sid,
            inner_shell_ids=tuple(inner_sids),
        )
        solid_list.append(solid)
        exp.Next()  # type: ignore[union-attr]

    if not solid_list:
        raise CadImportError(
            "conversion produced no solids; STEP file may contain only open shells"
        )

    return CanonicalTopologyModel(
        source=source,
        vertices=[v for _, v in vertex_reg],
        edges=[e for _, e in edge_reg],
        wires=[w for _, w in wire_reg],
        faces=[f for _, f in face_reg],
        shells=[sh for _, sh in shell_reg],
        solids=solid_list,
    )
