"""Generator dataset simulasi. Fitur dihitung oleh WindowFeatureExtractor ASLI GESER,
sehingga kolom dataset identik dengan yang dikirim HP sungguhan.

Dipakai saat data nyata belum cukup. Ganti/gabungkan dengan data rekaman HP (lihat
tools/ml_label_recording.py) untuk hasil yang mewakili kondisi sebenarnya.
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable

from geser.domain.features import WindowFeatureExtractor
from geser.domain.geometry import STANDARD_GRAVITY, Vec3
from geser.domain.models import AccelSample, GyroSample, SensorBatch, WindowFeatures

from .schema import LABELS, features_vector

HZ = 10.0
WINDOW_S = 2.0
N = int(HZ * WINDOW_S)
CALIBRATION_WINDOWS = 3
SETTLE_WINDOWS = 3  # filter gravitasi perlu beberapa jendela agar stabil
LABEL_NOISE = 0.03
MISSING_TILT = 0.02
MISSING_DESK = 0.01


def _gravity(theta_deg: float, phi: float) -> Vec3:
    t = math.radians(theta_deg)
    return (math.sin(t) * math.cos(phi), math.sin(t) * math.sin(phi), math.cos(t))


def _batch(rng: random.Random, t0: float, theta0: float, theta1: float, phi: float,
           accel_sigma: float, gyro_sigma: float) -> SensorBatch:
    accel, gyro = [], []
    for i in range(N):
        theta = theta0 + (theta1 - theta0) * i / (N - 1)
        gx, gy, gz = _gravity(theta, phi)
        t = t0 + i / HZ
        accel.append(AccelSample(t, (STANDARD_GRAVITY * gx + rng.gauss(0, accel_sigma),
                                     STANDARD_GRAVITY * gy + rng.gauss(0, accel_sigma),
                                     STANDARD_GRAVITY * gz + rng.gauss(0, accel_sigma))))
        gyro.append(GyroSample(t, (rng.gauss(0, gyro_sigma), rng.gauss(0, gyro_sigma),
                                   rng.gauss(0, gyro_sigma))))
    return SensorBatch(WINDOW_S, tuple(accel), tuple(gyro))


def _extractor() -> WindowFeatureExtractor:
    return WindowFeatureExtractor(gravity_alpha=0.9, max_gyro_dt_s=0.5)


def _desk_features(rng: random.Random, accel_sigma: float, gyro_sigma: float) -> WindowFeatures:
    feats = _extractor().extract(_batch(rng, 0.0, 0.0, 0.0, 0.0, accel_sigma, gyro_sigma))
    assert feats is not None
    return feats


# Profil mengembalikan: (theta_awal, theta_akhir, aksel_sigma, gyro_sigma, desk_aksel, desk_gyro)
Profile = Callable[[random.Random], tuple[float, float, float, float, float, float]]


def _quiet_desk(rng: random.Random) -> tuple[float, float]:
    return rng.uniform(0.02, 0.12), rng.uniform(0.003, 0.02)


def _tegak(rng: random.Random) -> tuple[float, float, float, float, float, float]:
    theta = abs(rng.gauss(6.0, 4.0))
    d_a, d_g = _quiet_desk(rng)
    return theta, theta, rng.uniform(0.02, 0.10), rng.uniform(0.003, 0.02), d_a, d_g


def _condong(rng: random.Random) -> tuple[float, float, float, float, float, float]:
    theta = min(75.0, max(10.0, rng.gauss(32.0, 9.0)))
    d_a, d_g = _quiet_desk(rng)
    return theta, theta, rng.uniform(0.03, 0.14), rng.uniform(0.004, 0.025), d_a, d_g


def _bergerak(rng: random.Random) -> tuple[float, float, float, float, float, float]:
    d_a, d_g = _quiet_desk(rng)
    start = abs(rng.gauss(15.0, 12.0))
    if rng.random() < 0.75:  # gerakan jelas
        end = max(0.0, start + rng.gauss(0.0, 15.0))
        return start, end, rng.uniform(0.3, 1.6), rng.uniform(0.15, 0.6), d_a, d_g
    end = max(0.0, start + rng.gauss(0.0, 5.0))  # gerakan kecil (gelisah)
    return start, end, rng.uniform(0.1, 0.35), rng.uniform(0.04, 0.15), d_a, d_g


def _meja(rng: random.Random) -> tuple[float, float, float, float, float, float]:
    base = _tegak(rng) if rng.random() < 0.6 else _condong(rng)
    return base[0], base[1], base[2], base[3], rng.uniform(0.35, 2.5), rng.uniform(0.02, 0.5)


PROFILES: dict[str, Profile] = {
    "TEGAK": _tegak, "CONDONG": _condong, "BERGERAK": _bergerak, "MEJA_TERGANGGU": _meja,
}


def make_example(label: str, rng: random.Random) -> list[float]:
    """Satu contoh Input (A) untuk kondisi `label`, melalui pipeline fitur GESER."""
    t0, t1, a_sigma, g_sigma, d_a, d_g = PROFILES[label](rng)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    extractor = _extractor()
    extractor.begin_calibration(CALIBRATION_WINDOWS)
    now = 0.0
    for _ in range(CALIBRATION_WINDOWS):
        extractor.extract(_batch(rng, now, abs(rng.gauss(2.0, 1.5)), 0.0, phi, 0.05, 0.01))
        now += WINDOW_S
    features: WindowFeatures | None = None
    for _ in range(SETTLE_WINDOWS):
        features = extractor.extract(_batch(rng, now, t0, t1, phi, a_sigma, g_sigma))
        now += WINDOW_S
    assert features is not None
    return features_vector(features, _desk_features(rng, d_a, d_g))


def build_dataset(per_class: int, seed: int) -> list[tuple[list[float], str]]:
    """Dataset seimbang + masalah data nyata: label salah (3%) dan nilai hilang."""
    rng = random.Random(seed)
    rows: list[tuple[list[float], str]] = []
    for label in LABELS:
        for _ in range(per_class):
            vec = make_example(label, rng)
            if rng.random() < MISSING_TILT:
                vec[0] = float("nan")
            if rng.random() < MISSING_DESK:
                vec[4] = vec[5] = float("nan")
            shown = label
            if rng.random() < LABEL_NOISE:
                shown = rng.choice([c for c in LABELS if c != label])
            rows.append((vec, shown))
    rng.shuffle(rows)
    return rows
