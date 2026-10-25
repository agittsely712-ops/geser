"""Model konfigurasi bertipe. Nilai diisi dari configs/default.yaml."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrokerSettings:
    host: str
    port: int
    tls: bool
    keepalive_s: int
    ws_url: str


@dataclass(frozen=True, slots=True)
class EdgeSettings:
    window_s: float
    sample_interval_ms: int
    gravity_alpha: float
    calibration_s: float
    accel_sensor: str
    gyro_sensor: str
    max_gyro_dt_s: float

    @property
    def calibration_windows(self) -> int:
        """Jumlah jendela yang dirata-rata untuk baseline."""
        return max(1, math.ceil(self.calibration_s / self.window_s))


@dataclass(frozen=True, slots=True)
class StillnessSettings:
    still_angle_deg: float
    exit_hysteresis_deg: float
    reposition_angle_deg: float
    accel_dev_max: float
    gyro_path_max_rad: float
    reposition_gyro_rad: float
    reposition_gyro_window_s: float
    label_min: float


@dataclass(frozen=True, slots=True)
class NoiseSettings:
    settle_s: float
    k: float
    min_limit: float
    max_limit: float
    min_samples: int


@dataclass(frozen=True, slots=True)
class LeanSettings:
    angle_deg: float
    duration_min: float


@dataclass(frozen=True, slots=True)
class FusionSettings:
    desk_filter: bool
    desk_disturb_accel_rms: float
    pair_gap_s: float
    data_gap_s: float


@dataclass(frozen=True, slots=True)
class ReminderSettings:
    level1_min: float
    level2_min: float
    level3_min: float
    cooldown_min: float
    snooze_options_min: tuple[int, ...]
    vibrate_short_ms: int
    vibrate_long_ms: int
    l3_pulses: int
    l3_pause_ms: int


@dataclass(frozen=True, slots=True)
class ScoreSettings:
    start: float
    still_penalty_per_min: float
    lean_penalty_per_min: float
    reposition_bonus: float


@dataclass(frozen=True, slots=True)
class EngineSettings:
    tick_s: float
    session_heartbeat_s: float
    max_clock_skew_s: float
    time_scale: float
    time_scale_min: float
    time_scale_max: float


@dataclass(frozen=True, slots=True)
class Settings:
    broker: BrokerSettings
    edge: EdgeSettings
    stillness: StillnessSettings
    noise: NoiseSettings
    lean: LeanSettings
    fusion: FusionSettings
    reminders: ReminderSettings
    score: ScoreSettings
    engine: EngineSettings


@dataclass(frozen=True, slots=True)
class Runtime:
    """Konfigurasi algoritma ditambah identitas proyek yang sudah divalidasi."""

    settings: Settings
    project_id: str
