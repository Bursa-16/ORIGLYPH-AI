"""Controlled STEP/STP import entry point for Origlyph (Stage 22E).

Stage 22E introduces EXPERIMENTAL_CONTROLLED_STEP_IMPORT — an explicit,
dependency-aware path from a STEP or STP file to a :class:`CanonicalTopologyModel`.

This is not production STEP support.  Classification:
EXPERIMENTAL_CONTROLLED_STEP_IMPORT

Mandatory disclosures
---------------------
- This stage does not solve persistent topology naming across CAD revisions.
- STEP/B-Rep topology is not persisted into the Origlyph project model.
- Automatic datum selection and automatic GD&T extraction are outside Stage 22E.
- The optional brep extra (OCP/OCCT kernel) is required for this path.
  Install with: ``pip install origlyph[brep]``
"""
from __future__ import annotations

from pathlib import Path

from .exceptions import CadImportError, UnsupportedCadFormatError
from .identity import CadFormat, SourceDocumentIdentity
from .step_kernel_adapter import StepKernelAdapter, StepKernelUnavailableError
from .topology import CanonicalTopologyModel

__all__ = ["load_step_topology"]

_STEP_EXTENSIONS: frozenset[str] = frozenset({".step", ".stp"})


def load_step_topology(
    path: Path | str,
    source: SourceDocumentIdentity,
) -> CanonicalTopologyModel:
    """Import a STEP or STP file and return a :class:`CanonicalTopologyModel`.

    EXPERIMENTAL_CONTROLLED_STEP_IMPORT.  Requires the optional brep extra.
    Install with: ``pip install origlyph[brep]``

    Only ``.step`` and ``.stp`` extensions (case-insensitive) are accepted;
    all other extensions fail closed with :class:`UnsupportedCadFormatError`.

    The returned model is fully kernel-independent; no OCP objects are
    retained after this call returns.

    Snapshot topology IDs are deterministic for the same imported artifact.
    They are NOT persistent names across CAD revisions.

    Parameters
    ----------
    path:
        Filesystem path to the STEP or STP file.
    source:
        :class:`SourceDocumentIdentity` for this document.
        Must declare :data:`CadFormat.STEP`.

    Returns
    -------
    CanonicalTopologyModel
        A fully validated, kernel-independent topology model.

    Raises
    ------
    UnsupportedCadFormatError
        If the file extension is not ``.step`` or ``.stp``, or if
        ``source.format`` is not :data:`CadFormat.STEP`.
    StepKernelUnavailableError
        If the optional brep extra (OCP/OCCT kernel) is not installed.
        Install it with: ``pip install origlyph[brep]``
    CadImportError
        On any file access, reading, or B-Rep conversion failure.
    """
    file_path = Path(path)
    ext = file_path.suffix.lower()
    if ext not in _STEP_EXTENSIONS:
        raise UnsupportedCadFormatError(
            f"load_step_topology only accepts .step or .stp files; "
            f"got extension {ext!r}"
        )
    if not isinstance(source, SourceDocumentIdentity):
        raise CadImportError(
            "load_step_topology requires a SourceDocumentIdentity"
        )
    if source.format is not CadFormat.STEP:
        raise UnsupportedCadFormatError(
            f"load_step_topology requires CadFormat.STEP; "
            f"got {source.format!r}"
        )
    adapter = StepKernelAdapter(file_path)
    try:
        return adapter.to_canonical_topology(source)
    except StepKernelUnavailableError as exc:
        raise StepKernelUnavailableError(
            "STEP/STP import requires the optional brep extra. "
            "Install it with: pip install origlyph[brep]"
        ) from exc
