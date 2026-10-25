"""Tipe data bersama lapisan domain."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .geometry import Vec3
from .states import State


class Role(str, Enum):
    BODY = "body"
    DESK = "desk"


@dataclass(frozen=True, slots=True)
class AccelSample:
    t_s: float
    xyz: Vec3  # m/s^2, termasuk gravitasi


@dataclass(frozen=True, slots=True)
class GyroSample:
    t_s: float
    xyz: Vec3  # rad/s


@dataclass(frozen=True, slots=True)
class SensorBatch:
    """Sampel mentah satu jendela. Tidak pernah dikirim ke jaringan."""

    duration_s: float
    accel: tuple[AccelSample, ...]
    gyro: tuple[GyroSample, ...]


@dataclass(frozen=True, slots=True)
class WindowFeatures:
    """Hasil Processing 1 untuk satu jendela."""

    window_s: float
    samples: int
    gravity: Vec3
    tilt_deg: float | None  # None bila belum terkalibrasi
    tilt_step_deg: float
    accel_dev_rms: float
    gyro_path_rad: float
    calibrated: bool


@dataclass(frozen=True, slots=True)
class Telemetry:
    device: Role
    run: str
    n_msg: int
    t_ms: int
    features: WindowFeatures


class ReminderKind(str, Enum):
    REMINDER = "reminder"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class ReminderMessage:
    event: ReminderKind
    level: int
    message: str
    still_min: float
    issued_ms: int


class EventKind(str, Enum):
    SESSION = "session"
    STATE = "state"
    REPOSITION = "reposition"
    REMINDER = "reminder"
    CLEARED = "cleared"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    kind: EventKind
    at_ms: int
    message: str
    data: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    state: State
    reason: str
    active: bool
    paused: bool
    time_scale: float
    still_real_s: float
    still_scaled_s: float
    anchor_tilt_deg: float | None
    reminder_level: int
    last_reposition_ms: int | None
    score: int
    nodes_online: Mapping[str, bool]
    at_ms: int
    reminders_count: int
    repositions: int
    longest_still_s: float
    lean_scaled_s: float
