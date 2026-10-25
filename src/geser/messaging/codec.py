"""Pengkodean dan validasi ketat payload JSON GESER (skema v1)."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from geser.domain.geometry import magnitude
from geser.domain.models import (
    EngineEvent,
    EventKind,
    ReminderKind,
    ReminderMessage,
    Role,
    SessionSnapshot,
    Telemetry,
    WindowFeatures,
)
from geser.domain.states import State
from geser.settings.models import Settings

from .errors import CommandRejected, PayloadError, TelemetryRejected

SCHEMA_VERSION = 1
MAX_TEXT_LEN = 240
MAX_RUN_LEN = 16
GRAVITY_NORM_TOLERANCE = 0.05
MAX_WINDOW_S = 10.0
MAX_SAMPLES = 10_000
MAX_ANGLE_DEG = 180.0
MAX_ACCEL_DEV = 100.0
MAX_GYRO_PATH = 1_000.0
MAX_EPOCH_MS = 4_102_444_800_000  # tahun 2100

_MISSING = object()
_TELEMETRY_KEYS = frozenset({
    "v", "device", "run", "n_msg", "t_ms", "window_s", "samples", "gravity",
    "tilt_deg", "tilt_step_deg", "accel_dev_rms", "gyro_path_rad", "calibrated",
})


# ---------------------------------------------------------------- helpers
def _dumps(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _loads(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PayloadError(f"bukan JSON yang valid: {exc}") from exc
    if not isinstance(data, dict):
        raise PayloadError("payload harus berupa objek JSON")
    return data


def _field(data: Mapping[str, Any], key: str) -> Any:
    value = data.get(key, _MISSING)
    if value is _MISSING:
        raise PayloadError(f"field '{key}' tidak ada")
    return value


def _number(data: Mapping[str, Any], key: str, lo: float, hi: float, *, nullable: bool = False) -> Any:
    value = _field(data, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PayloadError(f"field '{key}' harus angka")
    number = float(value)
    if not math.isfinite(number) or not lo <= number <= hi:
        raise PayloadError(f"field '{key}' di luar rentang [{lo}, {hi}]")
    return number


def _integer(data: Mapping[str, Any], key: str, lo: int, hi: int, *, nullable: bool = False) -> Any:
    value = _field(data, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise PayloadError(f"field '{key}' harus bilangan bulat dalam [{lo}, {hi}]")
    return value


def _text(data: Mapping[str, Any], key: str, max_len: int = MAX_TEXT_LEN) -> str:
    value = _field(data, key)
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise PayloadError(f"field '{key}' harus teks 1 sampai {max_len} karakter")
    return value


def _flag(data: Mapping[str, Any], key: str) -> bool:
    value = _field(data, key)
    if not isinstance(value, bool):
        raise PayloadError(f"field '{key}' harus true atau false")
    return value


def _exact_keys(data: Mapping[str, Any], expected: frozenset[str]) -> None:
    if set(data) != expected:
        raise PayloadError(f"kunci tidak sesuai skema: {sorted(set(data) ^ expected)}")


def _version(data: Mapping[str, Any]) -> None:
    if data.get("v") != SCHEMA_VERSION:
        raise PayloadError(f"versi skema harus {SCHEMA_VERSION}")


# -------------------------------------------------------------- telemetry
def encode_telemetry(t: Telemetry) -> bytes:
    f = t.features
    return _dumps({
        "v": SCHEMA_VERSION, "device": t.device.value, "run": t.run, "n_msg": t.n_msg,
        "t_ms": t.t_ms, "window_s": round(f.window_s, 3), "samples": f.samples,
        "gravity": [round(c, 4) for c in f.gravity],
        "tilt_deg": None if f.tilt_deg is None else round(f.tilt_deg, 2),
        "tilt_step_deg": round(f.tilt_step_deg, 2),
        "accel_dev_rms": round(f.accel_dev_rms, 3),
        "gyro_path_rad": round(f.gyro_path_rad, 3), "calibrated": f.calibrated,
    })


def _gravity(data: Mapping[str, Any]) -> tuple[float, float, float]:
    raw = _field(data, "gravity")
    ok = isinstance(raw, list) and len(raw) == 3 and all(
        not isinstance(c, bool) and isinstance(c, int | float) and math.isfinite(c) for c in raw
    )
    if not ok:
        raise PayloadError("field 'gravity' harus daftar 3 angka")
    vec = (float(raw[0]), float(raw[1]), float(raw[2]))
    if abs(magnitude(vec) - 1.0) > GRAVITY_NORM_TOLERANCE:
        raise PayloadError("field 'gravity' harus vektor satuan")
    return vec


def _features(data: Mapping[str, Any]) -> WindowFeatures:
    calibrated = _flag(data, "calibrated")
    tilt = _number(data, "tilt_deg", 0.0, MAX_ANGLE_DEG, nullable=True)
    if calibrated != (tilt is not None):
        raise PayloadError("tilt_deg harus ada tepat saat calibrated true")
    return WindowFeatures(
        window_s=_number(data, "window_s", 0.0, MAX_WINDOW_S),
        samples=_integer(data, "samples", 1, MAX_SAMPLES),
        gravity=_gravity(data),
        tilt_deg=tilt,
        tilt_step_deg=_number(data, "tilt_step_deg", 0.0, MAX_ANGLE_DEG),
        accel_dev_rms=_number(data, "accel_dev_rms", 0.0, MAX_ACCEL_DEV),
        gyro_path_rad=_number(data, "gyro_path_rad", 0.0, MAX_GYRO_PATH),
        calibrated=calibrated,
    )


def _decode_telemetry(
    expected: Role, raw: bytes, now_ms: int, max_skew_s: float | None
) -> Telemetry:
    data = _loads(raw)
    _exact_keys(data, _TELEMETRY_KEYS)
    _version(data)
    if _text(data, "device", 8) != expected.value:
        raise PayloadError("device tidak cocok dengan topic")
    run = _text(data, "run", MAX_RUN_LEN)
    t_ms = _integer(data, "t_ms", 1, MAX_EPOCH_MS)
    if max_skew_s is not None and abs(now_ms - t_ms) > max_skew_s * 1000:
        raise PayloadError("t_ms terlalu jauh dari waktu engine (pesan basi atau jam salah)")
    return Telemetry(expected, run, _integer(data, "n_msg", 0, 2**31), t_ms, _features(data))


def decode_telemetry(
    expected: Role, raw: bytes, *, now_ms: int, max_skew_s: float | None
) -> Telemetry:
    """Validasi ketat. `max_skew_s=None` menonaktifkan cek jam (untuk replay)."""
    try:
        return _decode_telemetry(expected, raw, now_ms, max_skew_s)
    except PayloadError as exc:
        raise TelemetryRejected(str(exc)) from exc


class SequenceGuard:
    """Menolak n_msg yang tidak naik pada run yang sama (duplikat atau mundur)."""

    def __init__(self) -> None:
        self._last: dict[tuple[Role, str], int] = {}

    def check(self, t: Telemetry) -> None:
        key = (t.device, t.run)
        last = self._last.get(key)
        if last is not None and t.n_msg <= last:
            raise TelemetryRejected(f"n_msg {t.n_msg} tidak naik (terakhir {last})")
        self._last[key] = t.n_msg


# ---------------------------------------------------------------- session
def encode_session(s: SessionSnapshot) -> bytes:
    return _dumps({
        "v": SCHEMA_VERSION, "state": s.state.value, "reason": s.reason, "active": s.active,
        "paused": s.paused, "time_scale": s.time_scale,
        "still_real_s": round(s.still_real_s, 1), "still_scaled_s": round(s.still_scaled_s, 1),
        "anchor_tilt_deg": None if s.anchor_tilt_deg is None else round(s.anchor_tilt_deg, 1),
        "reminder_level": s.reminder_level, "last_reposition_ms": s.last_reposition_ms,
        "score": s.score, "nodes_online": dict(s.nodes_online), "at_ms": s.at_ms,
        "reminders_count": s.reminders_count, "repositions": s.repositions,
        "longest_still_s": round(s.longest_still_s, 1), "lean_scaled_s": round(s.lean_scaled_s, 1),
    })


def decode_session(raw: bytes) -> SessionSnapshot:
    data = _loads(raw)
    _version(data)
    try:
        state = State(_text(data, "state", 32))
    except ValueError as exc:
        raise PayloadError("state tidak dikenal") from exc
    nodes = _field(data, "nodes_online")
    if not isinstance(nodes, dict) or not all(
        isinstance(k, str) and isinstance(v, bool) for k, v in nodes.items()
    ):
        raise PayloadError("nodes_online harus objek nama ke boolean")
    big = float(MAX_EPOCH_MS)
    return SessionSnapshot(
        state=state, reason=_text(data, "reason"), active=_flag(data, "active"),
        paused=_flag(data, "paused"), time_scale=_number(data, "time_scale", 0.0, 1e6),
        still_real_s=_number(data, "still_real_s", 0.0, big),
        still_scaled_s=_number(data, "still_scaled_s", 0.0, big),
        anchor_tilt_deg=_number(data, "anchor_tilt_deg", 0.0, MAX_ANGLE_DEG, nullable=True),
        reminder_level=_integer(data, "reminder_level", 0, 3),
        last_reposition_ms=_integer(data, "last_reposition_ms", 0, MAX_EPOCH_MS, nullable=True),
        score=_integer(data, "score", 0, 100), nodes_online=dict(nodes),
        at_ms=_integer(data, "at_ms", 0, MAX_EPOCH_MS),
        reminders_count=_integer(data, "reminders_count", 0, 10**6),
        repositions=_integer(data, "repositions", 0, 10**6),
        longest_still_s=_number(data, "longest_still_s", 0.0, big),
        lean_scaled_s=_number(data, "lean_scaled_s", 0.0, big),
    )


# --------------------------------------------------------------- reminder
def encode_reminder(m: ReminderMessage) -> bytes:
    return _dumps({
        "event": m.event.value, "level": m.level, "message": m.message,
        "still_min": round(m.still_min, 1), "issued_ms": m.issued_ms,
    })


def decode_reminder(raw: bytes) -> ReminderMessage:
    data = _loads(raw)
    try:
        kind = ReminderKind(_text(data, "event", 16))
    except ValueError as exc:
        raise PayloadError("event pengingat tidak dikenal") from exc
    return ReminderMessage(
        event=kind, level=_integer(data, "level", 1, 3), message=_text(data, "message"),
        still_min=_number(data, "still_min", 0.0, 1e6),
        issued_ms=_integer(data, "issued_ms", 0, MAX_EPOCH_MS),
    )


# ------------------------------------------------------------------ event
def encode_event(e: EngineEvent) -> bytes:
    return _dumps({
        "v": SCHEMA_VERSION, "kind": e.kind.value, "at_ms": e.at_ms,
        "message": e.message, "data": dict(e.data),
    })


def decode_event(raw: bytes) -> EngineEvent:
    data = _loads(raw)
    try:
        kind = EventKind(_text(data, "kind", 16))
    except ValueError as exc:
        raise PayloadError("jenis event tidak dikenal") from exc
    extra = _field(data, "data")
    if not isinstance(extra, dict):
        raise PayloadError("field 'data' harus objek")
    return EngineEvent(kind, _integer(data, "at_ms", 0, MAX_EPOCH_MS), _text(data, "message"), extra)


# ---------------------------------------------------------------- control
class CommandName(str, Enum):
    START = "start"
    END = "end"
    PAUSE = "pause"
    RESUME = "resume"
    SNOOZE = "snooze"
    CALIBRATE = "calibrate"
    TIME_SCALE = "time_scale"


@dataclass(frozen=True, slots=True)
class ControlCommand:
    name: CommandName
    minutes: int | None = None
    target: Role | None = None
    value: float | None = None


@dataclass(frozen=True, slots=True)
class CommandLimits:
    snooze_options: tuple[int, ...]
    scale_min: float
    scale_max: float


def limits_from_settings(settings: Settings) -> CommandLimits:
    return CommandLimits(
        snooze_options=settings.reminders.snooze_options_min,
        scale_min=settings.engine.time_scale_min,
        scale_max=settings.engine.time_scale_max,
    )


def encode_command(cmd: ControlCommand) -> bytes:
    body: dict[str, Any] = {"cmd": cmd.name.value}
    if cmd.minutes is not None:
        body["minutes"] = cmd.minutes
    if cmd.target is not None:
        body["target"] = cmd.target.value
    if cmd.value is not None:
        body["value"] = cmd.value
    return _dumps(body)


_PARAMS: dict[CommandName, frozenset[str]] = {
    CommandName.START: frozenset(), CommandName.END: frozenset(),
    CommandName.PAUSE: frozenset(), CommandName.RESUME: frozenset(),
    CommandName.SNOOZE: frozenset({"minutes"}),
    CommandName.CALIBRATE: frozenset({"target"}),
    CommandName.TIME_SCALE: frozenset({"value"}),
}


def _decode_command(raw: bytes, limits: CommandLimits) -> ControlCommand:
    data = _loads(raw)
    try:
        name = CommandName(_text(data, "cmd", 16))
    except ValueError as exc:
        raise PayloadError("perintah tidak ada di whitelist") from exc
    _exact_keys(data, frozenset({"cmd"}) | _PARAMS[name])
    if name is CommandName.SNOOZE:
        minutes = _integer(data, "minutes", 1, 1440)
        if minutes not in limits.snooze_options:
            raise PayloadError(f"minutes harus salah satu dari {limits.snooze_options}")
        return ControlCommand(name, minutes=minutes)
    if name is CommandName.CALIBRATE:
        try:
            return ControlCommand(name, target=Role(_text(data, "target", 8)))
        except ValueError as exc:
            raise PayloadError("target kalibrasi tidak dikenal") from exc
    if name is CommandName.TIME_SCALE:
        return ControlCommand(name, value=_number(data, "value", limits.scale_min, limits.scale_max))
    return ControlCommand(name)


def decode_command(raw: bytes, limits: CommandLimits) -> ControlCommand:
    try:
        return _decode_command(raw, limits)
    except PayloadError as exc:
        raise CommandRejected(str(exc)) from exc
