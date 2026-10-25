"""Sensor simulasi untuk mencoba GESER tanpa HP (profil: still, fidget, shake)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from geser.domain.geometry import STANDARD_GRAVITY
from geser.domain.models import AccelSample, GyroSample, SensorBatch
from geser.ports import Clock

SAMPLE_HZ = 10.0
MOVE_DURATION_S = 4.0
MOVE_GYRO_RAD_S = 0.8
MOVE_ACCEL_NOISE = 1.2


@dataclass(frozen=True, slots=True)
class Profile:
    accel_noise: float
    gyro_noise: float
    move_period_s: float  # 0 berarti tidak pernah berpindah
    base_tilt_deg: float


PROFILES: dict[str, Profile] = {
    "still": Profile(0.04, 0.01, 0.0, 10.0),
    "fidget": Profile(0.04, 0.01, 90.0, 10.0),
    "shake": Profile(1.5, 0.05, 0.0, 10.0),
}


class SimulatedSensor:
    def __init__(self, profile: str, clock: Clock, rng: random.Random) -> None:
        if profile not in PROFILES:
            raise ValueError(f"profil simulasi tidak dikenal: {profile}")
        self._profile = PROFILES[profile]
        self._clock = clock
        self._rng = rng
        self._origin = clock.monotonic_s()

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._clock.sleep(duration_s)
        end = self._clock.monotonic_s()
        count = max(1, int(duration_s * SAMPLE_HZ))
        accel, gyro = [], []
        for i in range(count):
            t = end - duration_s + i / SAMPLE_HZ
            moving, cycle = self._motion(t)
            tilt = math.radians(self._profile.base_tilt_deg + (30.0 if cycle % 2 else 0.0))
            noise = MOVE_ACCEL_NOISE if moving else self._profile.accel_noise
            accel.append(AccelSample(t, (
                STANDARD_GRAVITY * math.sin(tilt) + self._rng.gauss(0, noise),
                self._rng.gauss(0, noise),
                STANDARD_GRAVITY * math.cos(tilt) + self._rng.gauss(0, noise),
            )))
            spin = MOVE_GYRO_RAD_S if moving else self._profile.gyro_noise
            gyro.append(GyroSample(t, (self._rng.gauss(0, spin), 0.0, 0.0)))
        return SensorBatch(duration_s, tuple(accel), tuple(gyro))

    def _motion(self, t: float) -> tuple[bool, int]:
        period = self._profile.move_period_s
        if period <= 0:
            return False, 0
        elapsed = t - self._origin
        return elapsed % period < MOVE_DURATION_S, int(elapsed // period)

    def close(self) -> None:
        pass
