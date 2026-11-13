"""Portable deterministic face signatures for topology revision matching (Stage 22H).

No OCP objects are stored or referenced.  All fields are plain Python data.
Canonical face identity survives STEP re-export (same geometry, new entity
numbers) via centroid-normalised, order-independent vertex fingerprinting.

Tolerance constants (MUST 25 / MUST 4)
---------------------------------------
QUANTIZE_PRECISION:
    Coordinate quantization step.  Values that differ by less than this
    amount after centroid normalisation produce the same fingerprint.
    Default: 1e-6 (sub-micron for typical CAD models in millimetres).

The persistent_id is a SHA-256 of the canonical signature payload (vertex
fingerprint + surface_type + quantized surface_params).  It does NOT use
Python's id(), memory addresses, or traversal order.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

__all__ = [
    "FaceSurfaceType",
    "TopologyFaceSignature",
    "QUANTIZE_PRECISION",
    "build_face_signature",
    "compute_persistent_face_id",
    "compute_vertex_fingerprint",
]

# ---------------------------------------------------------------------------
# Tolerance constants (documented per MUST 4 / MUST 25)
# ---------------------------------------------------------------------------

#: Coordinate quantization precision (model units, typically millimetres).
#: Coordinates within this tolerance of each other hash identically.
QUANTIZE_PRECISION: float = 1e-6


# ---------------------------------------------------------------------------
# Surface type enum
# ---------------------------------------------------------------------------


class FaceSurfaceType(str, Enum):
    """Canonical surface classification for signature purposes.

    ``UNKNOWN`` is the safe fallback for any surface the kernel cannot
    classify.  It is never an error to produce ``UNKNOWN``.
    """

    PLANE = "PLANE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    SPHERE = "SPHERE"
    TORUS = "TORUS"
    REVOLUTION = "REVOLUTION"
    EXTRUSION = "EXTRUSION"
    OFFSET = "OFFSET"
    BSPLINE = "BSPLINE"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# TopologyFaceSignature
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TopologyFaceSignature:
    """Compact portable signature for deterministic face identity across revisions.

    **No OCP objects are stored.**  Every field is a plain Python value
    (str, float, int, tuple of those).

    Parameters
    ----------
    persistent_id:
        SHA-256 hex of the canonical signature payload (vertex_fingerprint +
        surface_type + surface_params).  Stable across STEP re-export of
        unchanged geometry.  NOT stable across geometry changes.
    source_entity_id:
        STEP/source-format entity identifier if captured, else ``None``.
        Used as the strongest available lineage signal (MUST 5).
    surface_type:
        :attr:`FaceSurfaceType` value string.
    surface_params:
        Canonical quantized surface parameters (type-dependent).

        * PLANE:    ``(nx, ny, nz, offset)`` — unit normal + signed distance
          from origin in model units.
        * CYLINDER: ``(ax, ay, az, radius)`` — unit axis direction + radius.
        * CONE:     ``(ax, ay, az, half_angle_rad, apex_offset)``
        * Others:   empty tuple ``()``.
    normalized_centroid:
        Quantized centroid of the face vertex positions.  Provides a coarse
        spatial filter for PROBABLE matching.
    vertex_fingerprint:
        SHA-256 hex of the centroid-normalised, sorted, quantized vertex
        coordinate list.  Order-independent.
    area:
        Quantized face area, or ``None`` when unavailable.
    normal_signature:
        Quantized unit face normal ``(nx, ny, nz)``, or ``None``.
    adjacency_signature:
        ``(adjacent_face_count, edge_count)`` — coarse neighbourhood evidence
        (MUST 7).
    """

    persistent_id: str
    source_entity_id: Optional[str]
    surface_type: str
    surface_params: tuple[float, ...]
    normalized_centroid: tuple[float, float, float]
    vertex_fingerprint: str
    area: Optional[float]
    normal_signature: Optional[tuple[float, float, float]]
    adjacency_signature: tuple[int, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a canonical JSON-serialisable representation."""
        return {
            "persistent_id": self.persistent_id,
            "source_entity_id": self.source_entity_id,
            "surface_type": self.surface_type,
            "surface_params": list(self.surface_params),
            "normalized_centroid": list(self.normalized_centroid),
            "vertex_fingerprint": self.vertex_fingerprint,
            "area": self.area,
            "normal_signature": (
                list(self.normal_signature)
                if self.normal_signature is not None
                else None
            ),
            "adjacency_signature": list(self.adjacency_signature),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _quantize(x: float, precision: float = QUANTIZE_PRECISION) -> float:
    """Round *x* to the nearest multiple of *precision*."""
    return round(x / precision) * precision


def _safe_finite(x: float) -> float:
    """Return *x* if finite; 0.0 otherwise."""
    return x if math.isfinite(x) else 0.0


def _unit_normal(
    n: tuple[float, float, float],
) -> Optional[tuple[float, float, float]]:
    """Normalise *n*; return ``None`` for near-zero vectors."""
    mag = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if mag < 1e-12:
        return None
    return (
        _quantize(_safe_finite(n[0] / mag)),
        _quantize(_safe_finite(n[1] / mag)),
        _quantize(_safe_finite(n[2] / mag)),
    )


# ---------------------------------------------------------------------------
# Public computation functions
# ---------------------------------------------------------------------------


def compute_vertex_fingerprint(
    points: Sequence[tuple[float, float, float]],
) -> str:
    """Compute a centroid-normalised, order-independent vertex fingerprint.

    Algorithm (MUST 4 / MUST 6 / MUST 28)
    ---------------------------------------
    1. Compute centroid of all points.
    2. Subtract centroid (translation-invariant).
    3. Quantize each coordinate to :data:`QUANTIZE_PRECISION`.
    4. Sort all translated points lexicographically (order-independent).
    5. SHA-256 of compact canonical JSON.

    Returns the 64-character lowercase SHA-256 hex digest.
    """
    if not points:
        return hashlib.sha256(b"empty-vertex-set").hexdigest()

    pts = [(float(x), float(y), float(z)) for x, y, z in points]
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(p[2] for p in pts) / n

    normalised = sorted(
        (
            _quantize(_safe_finite(x - cx)),
            _quantize(_safe_finite(y - cy)),
            _quantize(_safe_finite(z - cz)),
        )
        for x, y, z in pts
    )

    payload = json.dumps(
        [[v[0], v[1], v[2]] for v in normalised],
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_persistent_face_id(
    vertex_fingerprint: str,
    surface_type: str,
    surface_params: tuple[float, ...],
) -> str:
    """Derive the stable persistent face ID from canonical signature data.

    Uses a deterministic SHA-256 of the canonical JSON payload.  Does NOT
    use Python object identity, memory addresses, or traversal order (MUST 8).

    Returns the 64-character lowercase SHA-256 hex digest.
    """
    payload = json.dumps(
        {
            "vertex_fingerprint": vertex_fingerprint,
            "surface_type": surface_type,
            "surface_params": list(surface_params),
        },
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_face_signature(
    *,
    vertex_points: Sequence[tuple[float, float, float]],
    surface_type: FaceSurfaceType | str = FaceSurfaceType.UNKNOWN,
    surface_params: tuple[float, ...] = (),
    source_entity_id: Optional[str] = None,
    area: Optional[float] = None,
    normal: Optional[tuple[float, float, float]] = None,
    adjacent_face_count: int = 0,
    edge_count: int = 0,
) -> TopologyFaceSignature:
    """Construct a :class:`TopologyFaceSignature` from canonical Python values.

    All inputs must be plain Python data; no OCP objects are permitted.

    Parameters
    ----------
    vertex_points:
        Vertex coordinate triples ``(x, y, z)`` for the face boundary.
        May be from :attr:`~origlyph.cad.topology.TopologyVertex.point` or
        from OCC coordinate extraction.  Order does not matter (MUST 28).
    surface_type:
        :class:`FaceSurfaceType` member or its string value.
    surface_params:
        Type-dependent canonical surface parameters (see
        :class:`TopologyFaceSignature`).
    source_entity_id:
        STEP source entity identifier if available, else ``None``.
    area:
        Face area in model units, or ``None``.
    normal:
        Face normal direction ``(nx, ny, nz)`` (need not be a unit vector),
        or ``None``.
    adjacent_face_count:
        Number of faces sharing an edge with this face.
    edge_count:
        Number of edges in the face boundary.
    """
    stype_str = (
        surface_type.value
        if isinstance(surface_type, FaceSurfaceType)
        else str(surface_type)
    )
    q_params: tuple[float, ...] = tuple(
        _quantize(_safe_finite(p)) for p in surface_params
    )
    pts = list(vertex_points)
    vfp = compute_vertex_fingerprint(pts)
    pid = compute_persistent_face_id(vfp, stype_str, q_params)

    # centroid
    if pts:
        n_pts = len(pts)
        cx = sum(float(p[0]) for p in pts) / n_pts
        cy = sum(float(p[1]) for p in pts) / n_pts
        cz = sum(float(p[2]) for p in pts) / n_pts
        centroid: tuple[float, float, float] = (
            _quantize(_safe_finite(cx)),
            _quantize(_safe_finite(cy)),
            _quantize(_safe_finite(cz)),
        )
    else:
        centroid = (0.0, 0.0, 0.0)

    q_normal: Optional[tuple[float, float, float]] = (
        _unit_normal(normal) if normal is not None else None
    )
    q_area: Optional[float] = (
        _quantize(_safe_finite(area))
        if area is not None and math.isfinite(area)
        else None
    )

    return TopologyFaceSignature(
        persistent_id=pid,
        source_entity_id=source_entity_id,
        surface_type=stype_str,
        surface_params=q_params,
        normalized_centroid=centroid,
        vertex_fingerprint=vfp,
        area=q_area,
        normal_signature=q_normal,
        adjacency_signature=(adjacent_face_count, edge_count),
    )
