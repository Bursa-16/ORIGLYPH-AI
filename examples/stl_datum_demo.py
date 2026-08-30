"""Executable STL -> datum demo runner (Stage 13A).

The smallest honest end-to-end Origlyph demo: it reads one STL file from
disk (the demo is the only I/O boundary), runs it through the existing
deterministic production pipeline, and prints every result:

    StlImporter.import_document        (origlyph.cad, Stage 12C/12D)
    extract_candidates                 (origlyph.cad.bridge, Stage 1D)
    bind_reference                     (origlyph.cad.binding, Stage 2B)
    bind_datum_constraint              (origlyph.cad.role, Stage 3B)
    bind_datum_reference_frame         (origlyph.cad.role, Stage 3B)

No production implementation is duplicated or parallel-tracked; this script
only feeds real user input into existing production APIs and prints them.

Honest, non-inferring guarantees enforced by this demo:

* STL has no units: the demo *declares* millimetres explicitly and never
  performs unit inference or unit conversion;
* the STL stored facet normal is diagnostics only and is always printed
  with ``Authority: NON-AUTHORITATIVE``; the winding-derived
  ``BoundedPlanarFace.plane.normal`` is the geometry authority;
* the demo DRF assigns PRIMARY/SECONDARY/TERTIARY to the first three valid
  planar candidates in file order purely to exercise the deterministic
  binding APIs. This is demo selection only -- no ranking, scoring,
  recommendation, or automatic datum selection of any kind;
* skipped/degenerate/unsupported content is always surfaced, never hidden.

Usage:
    py examples/stl_datum_demo.py path/to/part.stl

Exit codes: 0 on a successful import (with or without a complete demo DRF),
1 on any fatal input or import error.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path

from origlyph._version import __version__
from origlyph.cad import (
    CadFormat,
    SourceDocumentIdentity,
    SourceUnitSystem,
    StlImporter,
    bind_datum_constraint,
    bind_datum_reference_frame,
    bind_reference,
)
from origlyph.cad.bridge import (
    BridgedCandidate,
    CandidateResult,
    extract_candidates,
)
from origlyph.cad.exceptions import OriglyphCadError
from origlyph.cad.model import NeutralEntityEntry, NeutralModel
from origlyph.datum import ConstraintType, DatumConstraint
from origlyph.geometry import BoundedPlanarFace

__all__ = ["main"]

# ruff: noqa: T201 (printing the report is the entire purpose of this demo)

DECLARED_LENGTH_UNIT = "mm"

# Explicit demo roles, applied in file order. Demo convenience only; this is
# never a ranking, scoring, or recommendation of any kind.
_DEMO_ROLES: tuple[ConstraintType, ...] = (
    ConstraintType.PRIMARY,
    ConstraintType.SECONDARY,
    ConstraintType.TERTIARY,
)


def _fail(message: str) -> int:
    """Print a concise user-facing error and return the failure code."""
    print(f"error: {message}", file=sys.stderr)
    return 1


def _print_summary(model: NeutralModel, path: Path) -> None:
    print("Origlyph STL Datum Demo")
    print("=======================")
    print()
    print(f"File: {path}")
    print(f"Origlyph version: {__version__}")
    print(f"Declared STL units: {DECLARED_LENGTH_UNIT}")
    print("No automatic unit inference or conversion is performed.")
    print()
    print(f"Valid planar facets: {len(model.entities)}")
    print(f"Warnings: {len(model.warnings)}")
    for warning in model.warnings:
        print(f"  - [{warning.code}] {warning.message}")
    print(f"Unsupported facets: {len(model.unsupported)}")
    for content in model.unsupported:
        key = (
            content.source.source_entity_key
            if content.source is not None
            else "(unknown source)"
        )
        print(f"  - {content.reason} ({key})")
    print()
    print(
        "Note: any datum roles shown below are assigned by this demo only "
        "to exercise the deterministic API. Origlyph performed no ranking, "
        "scoring, recommendation, or automatic datum selection."
    )


def _print_candidates(model: NeutralModel) -> CandidateResult:
    result = extract_candidates(model)
    print()
    print(
        f"Candidates: {len(result.candidates)} "
        f"(skipped: {len(result.skipped)})"
    )
    kinds = ", ".join(
        candidate.datum_feature.kind.value for candidate in result.candidates
    )
    print(f"Feature kinds: {kinds if kinds else '(none)'}")
    for skipped in result.skipped:
        key = skipped.neutral_identity.neutral_entity_key
    for skipped in result.skipped:
        key = skipped.neutral_identity.neutral_entity_key
        print(f"  skipped: {key}: {skipped.reason}")
    return result


def _print_candidate_details(
    model: NeutralModel, result: CandidateResult
) -> None:
    for index, candidate in enumerate(result.candidates, start=1):
        entry: NeutralEntityEntry | None = model.entity_by_identity(
            candidate.neutral_identity
        )
        geometry = entry.geometry if entry is not None else None
        source = candidate.neutral_identity.source_identity
        source_key = source.source_entity_key if source else "(none)"
        reference_type = (
            type(candidate.reference).__name__
            if candidate.reference is not None
            else "(none)"
        )
        print()
        print(f"Candidate {index}")
        print(f"  source facet key: {source_key}")
        print(f"  feature kind: {candidate.datum_feature.kind.value}")
        print(f"  reference type: {reference_type}")
        if isinstance(geometry, BoundedPlanarFace):
            print(f"  centroid (derived): {geometry.centroid}")
            print(f"  winding-derived face normal: {geometry.plane.normal}")
        if candidate.reference is not None:
            frame = candidate.reference.frame
            print(f"  origin (bound frame): {frame.origin}")
        stored_normal = (
            entry.metadata.get("stl_normal") if entry is not None else None
        )
        if isinstance(stored_normal, tuple) and len(stored_normal) == 3:
            print(
                "  STL diagnostic normal (stored in file): "
                f"{stored_normal}"
            )
            print("  Authority: NON-AUTHORITATIVE")


def _print_first_binding(candidate: BridgedCandidate) -> None:
    bound = bind_reference(candidate)
    source = bound.source_identity
    print()
    print("Bound reference (first valid planar candidate)")
    print("----------------------------------------------")
    print(
        "  source document: "
        + (source.source_document.source_id if source else "(no source)")
    )
    print(
        "  source entity key: "
        + (source.source_entity_key if source else "(no source)")
    )
    print(f"  neutral entity key: {bound.neutral_identity.neutral_entity_key}")
    print(f"  domain entity id: {bound.entity_id}")
    print(f"  feature kind: {bound.datum_feature.kind.value}")
    if bound.reference is not None:
        print(f"  reference type: {type(bound.reference).__name__}")
        print(f"  bound frame origin: {bound.reference.frame.origin}")


def _print_datum_reference_frame(
    candidates: tuple[BridgedCandidate, ...],
) -> None:
    selected = list(candidates[:3])
    bounds = [bind_reference(candidate) for candidate in selected]
    assignments = list(zip(bounds, _DEMO_ROLES, strict=True))
    print()
    print("Datum Reference Frame Demo")
    print("--------------------------")
    labels = ("PRIMARY", "SECONDARY", "TERTIARY")
    for label, bound, role in zip(labels, bounds, _DEMO_ROLES, strict=True):
        key = bound.neutral_identity.neutral_entity_key
        print(f"{label}: {key} (entity {bound.entity_id}, role {role.value})")
    constraints: list[DatumConstraint] = [
        bind_datum_constraint(bound, role) for bound, role in assignments
    ]
    for constraint in constraints:
        axes = ", ".join(
            sorted(axis.value for axis in constraint.dof.constrained)
        )
        feature = constraint.datum_feature.entity_id
        print(
            f"  sequence {constraint.sequence} "
            f"({constraint.constraint_type.value}): {feature} "
            f"-> constrained: {axes}"
        )
    frame = bind_datum_reference_frame("demo-3-2-1", assignments)
    sequence = " -> ".join(
        str(constraint.sequence) for constraint in frame.constraints
    )
    print(f"Sequence: {sequence} (3-2-1)")
    print(f"Frame name: {frame.name}")
    print(f"Constrained DOF: {frame.total_constrained} of 6")
    print(f"Fully located: {frame.is_fully_located}")
    print()
    print(
        "Demo selection only -- Origlyph did not rank or recommend these "
        "datum features."
    )
    print(
        "The first three valid planar candidates were used only to "
        "exercise the deterministic binding APIs."
    )
    print("This is NOT automatic datum selection or recommendation.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the demo for one STL path and return the process exit code."""
    arguments = list(sys.argv[1:]) if argv is None else list(argv)
    if len(arguments) != 1:
        return _fail("usage: py examples/stl_datum_demo.py <file.stl>")
    path = Path(arguments[0])
    if not path.exists():
        return _fail(f"path does not exist: {path}")
    if not path.is_file():
        return _fail(f"not a regular file (is it a directory?): {path}")
    if path.suffix.lower() != ".stl":
        return _fail(
            f"unsupported file extension {path.suffix!r}; expected '.stl'"
        )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        return _fail(f"could not read STL file: {exc}")

    # Deterministic source identity via the simplest existing convention:
    # the file name plus the SHA-256 digest of the file bytes. No
    # geometry-based identity is derived anywhere in this demo.
    document = SourceDocumentIdentity(
        source_id=path.name,
        format=CadFormat.STL,
        unit_system=SourceUnitSystem(length_unit=DECLARED_LENGTH_UNIT),
        original_filename=path.name,
        fingerprint=hashlib.sha256(payload).hexdigest(),
    )
    # Filesystem boundary: bytes are read here, in the demo only, and are
    # injected into the unmodified production importer via bytes_loader.
    importer = StlImporter(bytes_loader=lambda _document: payload)
    try:
        model = importer.import_document(document)
    except OriglyphCadError as exc:
        return _fail(f"STL import failed: {exc}")

    _print_summary(model, path)
    result = _print_candidates(model)
    _print_candidate_details(model, result)
    if result.candidates:
        _print_first_binding(result.candidates[0])
    if len(result.candidates) >= 3:
        _print_datum_reference_frame(result.candidates)
    else:
        print()
        print(
            "Complete 3-2-1 demo DRF cannot be constructed: fewer than 3 "
            "valid planar candidates."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
