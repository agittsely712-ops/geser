"""Processing 1: fitur per jendela dari sampel IMU. Murni, tanpa I/O."""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from .geometry import STANDARD_GRAVITY, Vec3, angle_deg, magnitude, mean_direction, normalize
from .models import AccelSample, GyroSample, SensorBatch, WindowFeatures


class GravityFilter:
    """Low-pass eksponensial; hasilnya arah gravitasi (vektor satuan)."""

    def __init__(self, alpha: float) -> None:
        self._alpha = alpha
        self._state: Vec3 | None = None

    def feed(self, vectors: Iterable[Vec3]) -> Vec3 | None:
        keep = self._alpha
        for x, y, z in vectors:
            if self._state is None:
                self._state = (x, y, z)
                continue
            sx, sy, sz = self._state
            self._state = (keep * sx + (1 - keep) * x,
                           keep * sy + (1 - keep) * y,
                           keep * sz + (1 - keep) * z)
        if self._state is None or magnitude(self._state) == 0.0:
            return None
        return normalize(self._state)


def accel_dev_rms(samples: Sequence[AccelSample]) -> float:
    """Akar rata-rata kuadrat dari (|a| - g): ukuran getaran di luar gravitasi."""
    if not samples:
        return 0.0
    total = sum((magnitude(s.xyz) - STANDARD_GRAVITY) ** 2 for s in samples)
    return math.sqrt(total / len(samples))


def gyro_path_rad(samples: Sequence[GyroSample], max_dt_s: float) -> float:
    """Jumlah |omega| x dt; celah lebih besar dari max_dt_s tidak diintegrasi."""
    path = 0.0
    for before, current in zip(samples, samples[1:], strict=False):
        dt = current.t_s - before.t_s
        if 0.0 < dt <= max_dt_s:
            path += magnitude(current.xyz) * dt
    return path


class WindowFeatureExtractor:
    """Mengubah SensorBatch menjadi WindowFeatures dan mengelola baseline."""

    def __init__(self, gravity_alpha: float, max_gyro_dt_s: float) -> None:
        self._filter = GravityFilter(gravity_alpha)
        self._max_gyro_dt_s = max_gyro_dt_s
        self._previous: Vec3 | None = None
        self._baseline: Vec3 | None = None
        self._calibration: list[Vec3] = []
        self._calibration_left = 0

    @property
    def calibrating(self) -> bool:
        return self._calibration_left > 0

    def begin_calibration(self, windows: int) -> None:
        """Rata-ratakan gravitasi dari `windows` jendela berikutnya sebagai baseline."""
        self._calibration = []
        self._calibration_left = max(1, windows)

    def extract(self, batch: SensorBatch) -> WindowFeatures | None:
        """None bila tidak ada sampel akselerometer yang valid."""
        if not batch.accel:
            return None
        gravity = self._filter.feed(s.xyz for s in batch.accel)
        if gravity is None:
            return None
        self._advance_calibration(gravity)
        step = angle_deg(gravity, self._previous) if self._previous else 0.0
        self._previous = gravity
        tilt = angle_deg(gravity, self._baseline) if self._baseline else None
        return WindowFeatures(
            window_s=batch.duration_s,
            samples=len(batch.accel),
            gravity=gravity,
            tilt_deg=tilt,
            tilt_step_deg=step,
            accel_dev_rms=accel_dev_rms(batch.accel),
            gyro_path_rad=gyro_path_rad(batch.gyro, self._max_gyro_dt_s),
            calibrated=self._baseline is not None,
        )

    def _advance_calibration(self, gravity: Vec3) -> None:
        if self._calibration_left == 0:
            return
        self._calibration.append(gravity)
        self._calibration_left -= 1
        if self._calibration_left == 0:
            self._baseline = mean_direction(self._calibration)
