"""Operasi vektor 3D dasar tanpa dependensi luar."""
from __future__ import annotations

import math
from collections.abc import Iterable

Vec3 = tuple[float, float, float]
STANDARD_GRAVITY = 9.81


def dot(u: Vec3, v: Vec3) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def magnitude(v: Vec3) -> float:
    return math.sqrt(dot(v, v))


def normalize(v: Vec3) -> Vec3:
    size = magnitude(v)
    if size == 0.0:
        raise ValueError("vektor nol tidak bisa dinormalkan")
    return (v[0] / size, v[1] / size, v[2] / size)


def angle_deg(u: Vec3, v: Vec3) -> float:
    """Sudut antar dua vektor satuan, dalam derajat."""
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(u, v)))))


def mean_direction(vectors: Iterable[Vec3]) -> Vec3:
    """Arah rata-rata (ternormalisasi) dari sekumpulan vektor."""
    sx = sy = sz = 0.0
    for x, y, z in vectors:
        sx, sy, sz = sx + x, sy + y, sz + z
    return normalize((sx, sy, sz))
