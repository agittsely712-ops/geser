"""Processing 2: pelacak diam terhadap anchor dan noise floor adaptif.

Modul ini generik: tidak tahu soal MQTT, HP, atau pengingat. Ia hanya menerima
arah gravitasi dan ukuran gerakan per jendela, lalu menilai diam atau berpindah.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from enum import Enum

from .geometry import Vec3, angle_deg


class Verdict(str, Enum):
    STILL = "still"
    NEUTRAL = "neutral"  # bergerak kecil: tidak dihitung, tidak mereset
    REPOSITION = "reposition"


@dataclass(frozen=True, slots=True)
class StillnessRules:
    still_angle_deg: float
    exit_hysteresis_deg: float
    reposition_angle_deg: float
    gyro_path_max_rad: float
    reposition_gyro_rad: float
    reposition_gyro_window_s: float


class StillnessTracker:
    """Menghitung lama diam relatif terhadap posisi acuan (anchor)."""

    def __init__(self, rules: StillnessRules) -> None:
        self._rules = rules
        self._anchor: Vec3 | None = None
        self._still_s = 0.0
        self._was_still = False
        self._gyro: deque[tuple[float, float]] = deque()

    @property
    def anchor(self) -> Vec3 | None:
        return self._anchor

    @property
    def still_s(self) -> float:
        return self._still_s

    def reset(self) -> None:
        self._anchor = None
        self._rebase(None)

    def observe(
        self,
        gravity: Vec3,
        *,
        accel_dev_rms: float,
        accel_dev_limit: float,
        gyro_path_rad: float,
        window_s: float,
        at_s: float,
    ) -> Verdict:
        rules = self._rules
        if self._anchor is None:
            self._anchor = gravity
        angle = angle_deg(gravity, self._anchor)
        self._remember_gyro(at_s, gyro_path_rad)
        if angle >= rules.reposition_angle_deg or self._gyro_sum() >= rules.reposition_gyro_rad:
            self._rebase(gravity)
            return Verdict.REPOSITION
        angle_limit = rules.still_angle_deg
        if self._was_still:
            angle_limit += rules.exit_hysteresis_deg
        self._was_still = (
            angle < angle_limit
            and accel_dev_rms < accel_dev_limit
            and gyro_path_rad < rules.gyro_path_max_rad
        )
        if self._was_still:
            self._still_s += window_s
            return Verdict.STILL
        return Verdict.NEUTRAL

    def _rebase(self, gravity: Vec3 | None) -> None:
        if gravity is not None:
            self._anchor = gravity
        self._still_s = 0.0
        self._was_still = False
        self._gyro.clear()

    def _remember_gyro(self, at_s: float, path: float) -> None:
        self._gyro.append((at_s, path))
        horizon = at_s - self._rules.reposition_gyro_window_s
        while self._gyro and self._gyro[0][0] <= horizon:
            self._gyro.popleft()

    def _gyro_sum(self) -> float:
        return sum(path for _, path in self._gyro)


@dataclass(frozen=True, slots=True)
class NoiseRules:
    k: float
    min_limit: float
    max_limit: float
    default_limit: float
    min_samples: int


class NoiseFloor:
    """Ambang accel_dev_rms personal: rata-rata + k x simpangan baku, dibatasi."""

    def __init__(self, rules: NoiseRules) -> None:
        self._rules = rules
        self._samples: list[float] = []
        self._limit = rules.default_limit

    @property
    def limit(self) -> float:
        return self._limit

    def add(self, accel_dev_rms: float) -> None:
        self._samples.append(accel_dev_rms)

    def finalize(self) -> float:
        rules = self._rules
        if len(self._samples) >= rules.min_samples:
            raw = statistics.fmean(self._samples) + rules.k * statistics.pstdev(self._samples)
            self._limit = max(rules.min_limit, min(rules.max_limit, raw))
        return self._limit
