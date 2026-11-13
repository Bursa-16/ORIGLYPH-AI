"""Topology revision remap engine for datum bindings (Stage 22H).

Classifies how well a stored face binding matches candidate faces in a
revised CAD topology.  No OCP objects.  All inputs/outputs are plain Python
values or Origlyph domain types.

Match classes
-------------
EXACT      – high-confidence single match; auto-remap is safe.
PROBABLE   – strong single match, minor differences; engineer confirmation
             required (MUST 11).
AMBIGUOUS  – multiple candidates, face split/merge, or identity uncertain;
             fail-closed, no auto-remap (MUST 12).
NO_MATCH   – no credible candidate found; fail-closed (MUST 13).

Thresholds (MUST 25)
---------------------
_CENTROID_PROBABLE_TOLERANCE : float
    Maximum centroid Euclidean distance (in model units after quantization)
    for a PROBABLE surface-class match.  Default: 0.01.
_AREA_PROBABLE_MAX_RATIO : float
    Maximum fractional area difference ``|a-b|/max(|a|,|b|)`` for a
    PROBABLE match.  Default: 0.05 (5 %).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Sequence

from origlyph.cad.topology import CanonicalTopologyModel
from origlyph.cad.topology_signature import TopologyFaceSignature

from .exceptions import InvalidProjectError

__all__ = [
    "RevisionMatchClass",
    "FaceRevisionMatch",
    "RevisionRemapResult",
    "remap_face_binding",
    "remap_all_face_bindings",
]

# ---------------------------------------------------------------------------
# Thresholds (MUST 25) — all documented here for auditability
# ---------------------------------------------------------------------------

#: Maximum Euclidean distance between quantized centroids for PROBABLE match.
_CENTROID_PROBABLE_TOLERANCE: float = 0.01

#: Maximum fractional area difference |a-b|/max(|a|,|b|) for PROBABLE match.
_AREA_PROBABLE_MAX_RATIO: float = 0.05


# ---------------------------------------------------------------------------
# Match class enum
# ---------------------------------------------------------------------------


class RevisionMatchClass(str, Enum):
    """Classification of a face revision match (MUST 9)."""

    EXACT = "EXACT"
    PROBABLE = "PROBABLE"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


# ---------------------------------------------------------------------------
# Result dataclasses (MUST 23)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaceRevisionMatch:
    """Result of matching one stored face binding against a revised topology.

    Parameters
    ----------
    old_persistent_id:
        :attr:`~TopologyFaceSignature.persistent_id` from the stored binding,
        or ``None`` for pre-22H bindings.
    old_entity_id:
        The stored ``entity_id`` from the original binding.
    new_candidate_id:
        ``entity_id.value`` of the winning candidate in the new topology, or
        ``None`` when no unique candidate was found.
    new_persistent_id:
        :attr:`~TopologyFaceSignature.persistent_id` of the winning candidate,
        or ``None``.
    match_class:
        :class:`RevisionMatchClass` classification.
    confidence:
        Numerical confidence in ``[0.0, 1.0]``.  1.0 for EXACT, 0.0 for
        NO_MATCH.  Used for display/logging only; policy decisions use
        ``match_class``.
    reasons:
        Tuple of human-readable evidence strings (MUST 24).
    confirmation_required:
        ``True`` unless ``match_class`` is ``EXACT``.
    auto_remapped:
        ``True`` only for ``EXACT`` matches where auto-remap is safe.
        ``False`` for PROBABLE, AMBIGUOUS, and NO_MATCH (MUST 11, MUST 12).
    candidate_count:
        Number of scored candidates before uniqueness filtering.
    """

    old_persistent_id: Optional[str]
    old_entity_id: str
    new_candidate_id: Optional[str]
    new_persistent_id: Optional[str]
    match_class: RevisionMatchClass
    confidence: float
    reasons: tuple[str, ...]
    confirmation_required: bool
    auto_remapped: bool
    candidate_count: int


@dataclass(frozen=True, slots=True)
class RevisionRemapResult:
    """Aggregated result of remapping a collection of face bindings."""

    matches: tuple[FaceRevisionMatch, ...]
    exact_count: int
    probable_count: int
    ambiguous_count: int
    no_match_count: int


# ---------------------------------------------------------------------------
# Internal scoring helpers
# ---------------------------------------------------------------------------


def _centroid_dist(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _area_similar(a: Optional[float], b: Optional[float]) -> bool:
    """Return True when areas are similar or either is unknown."""
    if a is None or b is None:
        return True
    denom = max(abs(a), abs(b))
    if denom == 0.0:
        return a == b
    return abs(a - b) / denom <= _AREA_PROBABLE_MAX_RATIO


def _score_candidate(
    old_sig: TopologyFaceSignature,
    new_sig: TopologyFaceSignature,
) -> tuple[RevisionMatchClass, float, list[str]]:
    """Score one candidate face against the stored signature.

    Returns ``(match_class, confidence, evidence_reasons)``.

    Policy rules (MUST 10, MUST 11, MUST 25):
    - persistent_id match → EXACT (confidence 1.0).
    - vertex_fingerprint + surface_type + surface_params all match → EXACT.
    - surface_type match + centroid within tolerance + area within tolerance
      → PROBABLE (confidence proportional to centroid distance).
    - Anything else → NO_MATCH from this pair.
    """
    reasons: list[str] = []

    # --- Layer 1: persistent ID (strongest signal) -------------------------
    if old_sig.persistent_id == new_sig.persistent_id:
        reasons.append("persistent_id=MATCH")
        return RevisionMatchClass.EXACT, 1.0, reasons

    # --- Layer 2: vertex fingerprint ---------------------------------------
    vfp_match = old_sig.vertex_fingerprint == new_sig.vertex_fingerprint
    reasons.append(
        "vertex_fingerprint=EXACT" if vfp_match else "vertex_fingerprint=DIFFERENT"
    )

    # --- surface type ------------------------------------------------------
    stype_match = old_sig.surface_type == new_sig.surface_type
    reasons.append(
        f"surface_type=MATCH({old_sig.surface_type})"
        if stype_match
        else (
            f"surface_type=MISMATCH(old={old_sig.surface_type!r},"
            f"new={new_sig.surface_type!r})"
        )
    )

    # --- surface params (only compared when surface type matches) ----------
    params_match = (
        stype_match and old_sig.surface_params == new_sig.surface_params
    )
    if stype_match:
        reasons.append(
            "surface_params=MATCH" if params_match else "surface_params=DIFFERENT"
        )

    # --- vertex + type + params EXACT path ---------------------------------
    if vfp_match and stype_match and params_match:
        reasons.append("verdict=EXACT_GEOMETRIC")
        return RevisionMatchClass.EXACT, 0.98, reasons

    # --- PROBABLE: surface type + centroid + area --------------------------
    cdist = _centroid_dist(
        old_sig.normalized_centroid, new_sig.normalized_centroid
    )
    reasons.append(f"centroid_distance={cdist:.4e}")

    area_ok = _area_similar(old_sig.area, new_sig.area)
    if old_sig.area is not None and new_sig.area is not None:
        delta = abs((old_sig.area or 0.0) - (new_sig.area or 0.0))
        reasons.append(f"area_delta={delta:.4e}")

    if stype_match and cdist <= _CENTROID_PROBABLE_TOLERANCE and area_ok:
        conf = max(0.6, 1.0 - (cdist / _CENTROID_PROBABLE_TOLERANCE) * 0.4)
        reasons.append("verdict=PROBABLE_SURFACE_CENTROID")
        return RevisionMatchClass.PROBABLE, conf, reasons

    reasons.append("verdict=NO_MATCH")
    return RevisionMatchClass.NO_MATCH, 0.0, reasons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def remap_face_binding(
    old_entity_id: str,
    old_signature: Optional[TopologyFaceSignature],
    new_topology: CanonicalTopologyModel,
) -> FaceRevisionMatch:
    """Attempt to remap one stored face entity to a face in the new topology.

    When *old_signature* is ``None`` (a Stage 22G-era binding with no
    embedded signature), returns NO_MATCH: signatures are required for
    revision remap (MUST 13).

    Parameters
    ----------
    old_entity_id:
        Stored ``entity_id`` value from the original binding.
    old_signature:
        Stored :class:`~origlyph.cad.topology_signature.TopologyFaceSignature`,
        or ``None`` for pre-22H bindings.
    new_topology:
        :class:`~origlyph.cad.topology.CanonicalTopologyModel` to search.
    """
    if old_signature is None:
        return FaceRevisionMatch(
            old_persistent_id=None,
            old_entity_id=old_entity_id,
            new_candidate_id=None,
            new_persistent_id=None,
            match_class=RevisionMatchClass.NO_MATCH,
            confidence=0.0,
            reasons=("no_signature_in_stored_binding",),
            confirmation_required=True,
            auto_remapped=False,
            candidate_count=0,
        )

    # Collect candidates: faces in new topology that have signatures and
    # score better than NO_MATCH.
    candidates: list[Any] = []

    for face in new_topology.faces:
        new_sig: Optional[TopologyFaceSignature] = getattr(
            face, "surface_signature", None
        )
        if new_sig is None:
            continue
        mc, conf, reasons = _score_candidate(old_signature, new_sig)
        if mc != RevisionMatchClass.NO_MATCH:
            candidates.append(
                (face.entity_id.value, new_sig, mc, conf, tuple(reasons))
            )

    candidate_count = len(candidates)

    if candidate_count == 0:
        return FaceRevisionMatch(
            old_persistent_id=old_signature.persistent_id,
            old_entity_id=old_entity_id,
            new_candidate_id=None,
            new_persistent_id=None,
            match_class=RevisionMatchClass.NO_MATCH,
            confidence=0.0,
            reasons=("no_candidate_found",),
            confirmation_required=True,
            auto_remapped=False,
            candidate_count=0,
        )

    if candidate_count > 1:
        # Multiple candidates → AMBIGUOUS, fail-closed (MUST 12)
        reason_parts: list[str] = [f"multiple_candidates={candidate_count}"]
        # Count how many are EXACT
        exact_count = sum(1 for c in candidates if c[2] == RevisionMatchClass.EXACT)
        reason_parts.append(f"exact_among_candidates={exact_count}")
        reason_parts.append("fail_closed=AMBIGUOUS")
        return FaceRevisionMatch(
            old_persistent_id=old_signature.persistent_id,
            old_entity_id=old_entity_id,
            new_candidate_id=None,
            new_persistent_id=None,
            match_class=RevisionMatchClass.AMBIGUOUS,
            confidence=0.0,
            reasons=tuple(reason_parts),
            confirmation_required=True,
            auto_remapped=False,
            candidate_count=candidate_count,
        )

    # Exactly one candidate
    cand_id, winning_sig, mc, conf, reasons = candidates[0]
    is_exact = mc == RevisionMatchClass.EXACT

    return FaceRevisionMatch(
        old_persistent_id=old_signature.persistent_id,
        old_entity_id=old_entity_id,
        new_candidate_id=cand_id,
        new_persistent_id=winning_sig.persistent_id,
        match_class=mc,
        confidence=conf,
        reasons=reasons,
        confirmation_required=not is_exact,
        auto_remapped=is_exact,
        candidate_count=1,
    )


def remap_all_face_bindings(
    face_entity_ids: Sequence[str],
    old_signatures: Sequence[Optional[TopologyFaceSignature]],
    new_topology: CanonicalTopologyModel,
) -> RevisionRemapResult:
    """Remap a list of face entity IDs against a new topology.

    ``face_entity_ids`` and ``old_signatures`` must have equal length.

    Raises
    ------
    InvalidProjectError
        When the two input sequences have different lengths.
    """
    if len(face_entity_ids) != len(old_signatures):
        raise InvalidProjectError(
            "face_entity_ids and old_signatures must have equal length; "
            f"got {len(face_entity_ids)} and {len(old_signatures)}"
        )

    matches: list[FaceRevisionMatch] = [
        remap_face_binding(eid, sig, new_topology)
        for eid, sig in zip(face_entity_ids, old_signatures, strict=False)
    ]

    return RevisionRemapResult(
        matches=tuple(matches),
        exact_count=sum(
            1 for m in matches if m.match_class == RevisionMatchClass.EXACT
        ),
        probable_count=sum(
            1 for m in matches if m.match_class == RevisionMatchClass.PROBABLE
        ),
        ambiguous_count=sum(
            1 for m in matches if m.match_class == RevisionMatchClass.AMBIGUOUS
        ),
        no_match_count=sum(
            1 for m in matches if m.match_class == RevisionMatchClass.NO_MATCH
        ),
    )
