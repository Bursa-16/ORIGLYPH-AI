"""Centralized computational tolerance policy for the Origlyph geometry domain.

This policy exists ONLY for numerical robustness of floating-point geometry
comparisons. It is NOT an engineering/design/manufacturing tolerance and must
never be used to accept or reject a designed or manufactured feature.

Engineering tolerances come exclusively from drawings, GD&T, specifications,
process requirements, or explicit user input.
"""

from __future__ import annotations

from .exceptions import InvalidGeometryError

# Provisional computational defaults. They are justified analytically as
# orders of magnitude above float64 rounding error for automotive/defense-scale
# coordinates while remaining far below any realistic engineering tolerance.


class GeometryTolerancePolicy:
    """Computational floating-point tolerance policy (not an engineering one).

    Defaults (computational robustness only; never acceptance criteria):

    * ``ABS_TOL = 1e-6`` — absolute length tolerance in millimetres.
    * ``REL_TOL = 1e-9`` — relative, scale-aware tolerance.

    All deterministic geometry comparisons in the domain must route through a
    policy helper; per-module hidden epsilons are forbidden.
    """

    ABS_TOL: float = 1e-6
    REL_TOL: float = 1e-9

    # ------------------------------------------------------------------ #
    # Scalar helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def nearly_equal(cls, a: float, b: float) -> bool:
        """True if ``a`` and ``b`` differ within absolute+relative tolerance."""
        return abs(a - b) <= cls.ABS_TOL + cls.REL_TOL * max(abs(a), abs(b))

    @classmethod
    def near_zero(cls, x: float) -> bool:
        """True if ``x`` is effectively zero under the computational policy."""
        return abs(x) <= cls.ABS_TOL

    # ------------------------------------------------------------------ #
    # Vector helpers (duck-typed: operate on any vector-like object exposing
    # magnitude/dot/cross, avoiding a circular import with primitives).
    # ------------------------------------------------------------------ #
    @classmethod
    def vectors_parallel(cls, a, b) -> bool:
        """True if ``a`` and ``b`` are parallel (0 or 180 degrees apart)."""
        mag_a = a.magnitude()
        mag_b = b.magnitude()
        if cls.near_zero(mag_a) or cls.near_zero(mag_b):
            raise InvalidGeometryError(
                "parallelism is undefined for a zero vector"
            )
        sin_theta = a.cross(b).magnitude() / (mag_a * mag_b)
        return cls.near_zero(sin_theta)

    @classmethod
    def vectors_perpendicular(cls, a, b) -> bool:
        """True if ``a`` and ``b`` are perpendicular (90 degrees apart)."""
        mag_a = a.magnitude()
        mag_b = b.magnitude()
        if cls.near_zero(mag_a) or cls.near_zero(mag_b):
            raise InvalidGeometryError(
                "perpendicularity is undefined for a zero vector"
            )
        cos_theta = abs(a.dot(b)) / (mag_a * mag_b)
        return cls.near_zero(cos_theta)

    @classmethod
    def points_collinear(cls, a, b, c) -> bool:
        """True if points ``a``, ``b``, ``c`` lie on a single line."""
        ab = b - a
        ac = c - a
        if cls.near_zero(ab.magnitude()) or cls.near_zero(ac.magnitude()):
            return True  # coincident with the anchor point.
        return cls.vectors_parallel(ab, ac)

    @classmethod
    def points_coplanar(cls, a, b, c, d) -> bool:
        """True if points ``a``, ``b``, ``c``, ``d`` lie in a single plane."""
        ab = b - a
        ac = c - a
        ad = d - a
        scale = ab.magnitude() * ac.magnitude() * ad.magnitude()
        if cls.near_zero(scale):
            return True  # degenerate (coincident); trivially coplanar.
        triple = ab.dot(ac.cross(ad))
        return cls.near_zero(abs(triple) / scale)