"""Coordinate frames and rigid transforms for the Origlyph geometry domain.

Defines immutable ``Frame`` (origin + orthonormal right-handed basis) and
``Transform`` (rigid translation + rotation, internally a homogeneous 4x4
matrix). No mirror, no non-uniform scaling. Standard library only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .exceptions import InvalidGeometryError
from .primitives import Point3D, Vector3D
from .tolerance import GeometryTolerancePolicy
from .units import Angle

_I3 = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _mat_from_rt(
    rot: tuple[tuple[float, float, float], ...],
    trans: tuple[float, float, float],
) -> tuple[tuple[float, float, float, float], ...]:
    """Build a 4x4 homogeneous matrix from a 3x3 rotation and translation."""
    tx, ty, tz = trans
    return (
        (rot[0][0], rot[0][1], rot[0][2], tx),
        (rot[1][0], rot[1][1], rot[1][2], ty),
        (rot[2][0], rot[2][1], rot[2][2], tz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _mat4_mul(
    a: tuple[tuple[float, float, float, float], ...],
    b: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], ...]:
    """Multiply two 4x4 matrices."""
    return (
        (
            a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0]
            + a[0][3] * b[3][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1]
            + a[0][3] * b[3][1],
            a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2]
            + a[0][3] * b[3][2],
            a[0][0] * b[0][3] + a[0][1] * b[1][3] + a[0][2] * b[2][3]
            + a[0][3] * b[3][3],
        ),
        (
            a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0]
            + a[1][3] * b[3][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1]
            + a[1][3] * b[3][1],
            a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2]
            + a[1][3] * b[3][2],
            a[1][0] * b[0][3] + a[1][1] * b[1][3] + a[1][2] * b[2][3]
            + a[1][3] * b[3][3],
        ),
        (
            a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0]
            + a[2][3] * b[3][0],
            a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1]
            + a[2][3] * b[3][1],
            a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2]
            + a[2][3] * b[3][2],
            a[2][0] * b[0][3] + a[2][1] * b[1][3] + a[2][2] * b[2][3]
            + a[2][3] * b[3][3],
        ),
        (
            a[3][0] * b[0][0] + a[3][1] * b[1][0] + a[3][2] * b[2][0]
            + a[3][3] * b[3][0],
            a[3][0] * b[0][1] + a[3][1] * b[1][1] + a[3][2] * b[2][1]
            + a[3][3] * b[3][1],
            a[3][0] * b[0][2] + a[3][1] * b[1][2] + a[3][2] * b[2][2]
            + a[3][3] * b[3][2],
            a[3][0] * b[0][3] + a[3][1] * b[1][3] + a[3][2] * b[2][3]
            + a[3][3] * b[3][3],
        ),
    )


def _mat4_vec4(
    m: tuple[tuple[float, float, float, float], ...],
    x: float,
    y: float,
    z: float,
    w: float,
) -> tuple[float, float, float, float]:
    """Apply a 4x4 matrix to a homogeneous vector."""
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3] * w,
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3] * w,
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3] * w,
        m[3][0] * x + m[3][1] * y + m[3][2] * z + m[3][3] * w,
    )


def _mat4_identity() -> tuple[tuple[float, float, float, float], ...]:
    """Return the 4x4 identity matrix."""
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


@dataclass(frozen=True)
class Transform:
    """An immutable rigid transform (rotation + translation).

    Stored as a homogeneous 4x4 matrix (row-major). ``apply_point(p)`` applies
    the full transform; ``apply_vector(v)`` applies rotation only.
    """

    matrix: tuple[tuple[float, float, float, float], ...]

    @classmethod
    def identity(cls) -> "Transform":
        """The identity transform."""
        return cls(_mat4_identity())

    @classmethod
    def translation(
        cls, x: float = 0.0, y: float = 0.0, z: float = 0.0
    ) -> "Transform":
        """A pure translation by (x, y, z) in canonical millimetres."""
        return cls(_mat_from_rt(_I3, (float(x), float(y), float(z))))

    @classmethod
    def rotation(cls, axis: Vector3D, angle: Angle) -> "Transform":
        """Rotation about ``axis`` by ``angle`` (Rodrigues' formula)."""
        if axis.is_zero():
            raise InvalidGeometryError("rotation requires a non-zero axis")
        k = axis.normalize()
        c = math.cos(angle.rad)
        s = math.sin(angle.rad)
        t = 1.0 - c
        kx, ky, kz = k.x, k.y, k.z
        rot = (
            (c + kx * kx * t, kx * ky * t - kz * s, kx * kz * t + ky * s),
            (ky * kx * t + kz * s, c + ky * ky * t, ky * kz * t - kx * s),
            (kz * kx * t - ky * s, kz * ky * t + kx * s, c + kz * kz * t),
        )
        return cls(_mat_from_rt(rot, (0.0, 0.0, 0.0)))

    def compose(self, other: "Transform") -> "Transform":
        """Compose so that ``other`` applies first, then this transform."""
        return Transform(_mat4_mul(self.matrix, other.matrix))

    def inverse(self) -> "Transform":
        """Inverse of this rigid transform."""
        m = self.matrix
        rot = (
            (m[0][0], m[1][0], m[2][0]),
            (m[0][1], m[1][1], m[2][1]),
            (m[0][2], m[1][2], m[2][2]),
        )
        t = m[0][3], m[1][3], m[2][3]
        t_inv = (
            -(rot[0][0] * t[0] + rot[0][1] * t[1] + rot[0][2] * t[2]),
            -(rot[1][0] * t[0] + rot[1][1] * t[1] + rot[1][2] * t[2]),
            -(rot[2][0] * t[0] + rot[2][1] * t[1] + rot[2][2] * t[2]),
        )
        return Transform(_mat_from_rt(rot, t_inv))

    def apply_point(self, p: Point3D) -> Point3D:
        """Apply the full transform (rotation + translation) to a point."""
        x, y, z, _ = _mat4_vec4(self.matrix, p.x, p.y, p.z, 1.0)
        return Point3D(x, y, z)

    def apply_vector(self, v: Vector3D) -> Vector3D:
        """Apply the rotation part only to a direction vector."""
        x, y, z, _ = _mat4_vec4(self.matrix, v.x, v.y, v.z, 0.0)
        return Vector3D(x, y, z)


@dataclass(frozen=True)
class Frame:
    """An orthonormal right-handed coordinate frame.

    Axes are stored normalized; the basis must be right-handed
    (x_axis cross y_axis == z_axis) within computational tolerance.
    """

    origin: Point3D
    x_axis: Vector3D
    y_axis: Vector3D
    z_axis: Vector3D

    def __post_init__(self) -> None:
        x = self.x_axis.normalize()
        y = self.y_axis.normalize()
        z = self.z_axis.normalize()
        tol = GeometryTolerancePolicy
        if not tol.near_zero(abs(x.dot(y))):
            raise InvalidGeometryError("frame x/y axes are not perpendicular")
        if not tol.near_zero(abs(x.dot(z))):
            raise InvalidGeometryError("frame x/z axes are not perpendicular")
        if not tol.near_zero(abs(y.dot(z))):
            raise InvalidGeometryError("frame y/z axes are not perpendicular")
        cross_xy = x.cross(y)
        if not (
            tol.nearly_equal(cross_xy.x, z.x)
            and tol.nearly_equal(cross_xy.y, z.y)
            and tol.nearly_equal(cross_xy.z, z.z)
        ):
            raise InvalidGeometryError(
                "frame is not right-handed (x cross y != z)"
            )
        object.__setattr__(self, "x_axis", x)
        object.__setattr__(self, "y_axis", y)
        object.__setattr__(self, "z_axis", z)

    @classmethod
    def world(cls) -> "Frame":
        """The canonical world frame at the origin with axis-aligned basis."""
        return cls(
            origin=Point3D(0.0, 0.0, 0.0),
            x_axis=Vector3D(1.0, 0.0, 0.0),
            y_axis=Vector3D(0.0, 1.0, 0.0),
            z_axis=Vector3D(0.0, 0.0, 1.0),
        )