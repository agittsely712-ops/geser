"""Definisi Input (A) dan Output (B) model AI GESER. Murni, tanpa I/O."""
from __future__ import annotations

from geser.domain.models import WindowFeatures

NAN = float("nan")

# Output (B): kondisi duduk pada satu jendela 2 detik.
LABELS: tuple[str, ...] = ("TEGAK", "CONDONG", "BERGERAK", "MEJA_TERGANGGU")

LABEL_TEXT: dict[str, str] = {
    "TEGAK": "Duduk tegak, posisi baik",
    "CONDONG": "Badan condong dari posisi acuan",
    "BERGERAK": "Pengguna sedang bergerak / ganti posisi",
    "MEJA_TERGANGGU": "Meja terguncang, bukan gerakan tubuh",
}

# Input (A): 6 fitur dari 2 HP (body = saku dada, desk = meja).
FEATURE_NAMES: tuple[str, ...] = (
    "body_tilt_deg",
    "body_tilt_step_deg",
    "body_accel_dev_rms",
    "body_gyro_path_rad",
    "desk_accel_dev_rms",
    "desk_gyro_path_rad",
)


def features_vector(body: WindowFeatures, desk: WindowFeatures | None) -> list[float]:
    """Susun vektor Input (A). Nilai yang tidak ada (belum kalibrasi / desk offline) = NaN."""
    return [
        body.tilt_deg if body.tilt_deg is not None else NAN,
        body.tilt_step_deg,
        body.accel_dev_rms,
        body.gyro_path_rad,
        desk.accel_dev_rms if desk is not None else NAN,
        desk.gyro_path_rad if desk is not None else NAN,
    ]
