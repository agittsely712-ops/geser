"""Memuat YAML dan variabel lingkungan menjadi Settings yang tervalidasi."""
from __future__ import annotations

import os
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

import yaml

from .errors import ConfigError
from .identity import validate_project_id
from .models import Runtime, Settings

_ENV_KEYS = (
    "PROJECT_ID",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_TLS",
    "TIME_SCALE",
    "GESER_CONFIG",
    "ACCEL_SENSOR",
    "GYRO_SENSOR",
)
_TRUE_WORDS = {"1", "true", "yes", "ya"}
_FALSE_WORDS = {"0", "false", "no", "tidak"}


def read_env(env_file: str | Path = ".env") -> dict[str, str]:
    """Baca berkas .env sederhana; variabel lingkungan proses menang."""
    values: dict[str, str] = {}
    path = Path(env_file)
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in _ENV_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def find_config(explicit: str | None, env: dict[str, str]) -> Path:
    repo_default = Path(__file__).resolve().parents[3] / "configs" / "default.yaml"
    candidates = [explicit, env.get("GESER_CONFIG"), "configs/default.yaml", repo_default]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ConfigError("configs/default.yaml tidak ditemukan. Jalankan dari akar repo.")


def _convert(value: Any, hint: Any, path: str) -> Any:
    if is_dataclass(hint):
        return _build(hint, value, path)
    if get_origin(hint) is tuple:
        if not isinstance(value, list):
            raise ConfigError(f"{path}: harus berupa daftar")
        return tuple(_convert(item, get_args(hint)[0], path) for item in value)
    if hint is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"{path}: harus true atau false")
        return value
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{path}: harus bilangan bulat")
        return value
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{path}: harus angka")
        return float(value)
    if hint is str:
        if not isinstance(value, str):
            raise ConfigError(f"{path}: harus teks")
        return value
    raise ConfigError(f"{path}: tipe {hint} tidak didukung")


def _build(cls: Any, data: Any, path: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: harus berupa objek")
    hints = get_type_hints(cls)
    names = {f.name for f in fields(cls)}
    unknown, missing = set(data) - names, names - set(data)
    if unknown or missing:
        raise ConfigError(f"{path}: kunci tak dikenal {sorted(unknown)}, kurang {sorted(missing)}")
    return cls(**{n: _convert(data[n], hints[n], f"{path}.{n}") for n in names})


def validate(s: Settings) -> None:
    """Periksa keterkaitan antar nilai; lempar ConfigError bila janggal."""
    r, st = s.reminders, s.stillness
    checks = [
        (s.edge.window_s > 0, "edge.window_s harus > 0"),
        (0 < s.edge.gravity_alpha < 1, "edge.gravity_alpha harus di antara 0 dan 1"),
        (r.level1_min < r.level2_min < r.level3_min, "level1_min < level2_min < level3_min"),
        (r.cooldown_min > 0, "reminders.cooldown_min harus > 0"),
        (all(m > 0 for m in r.snooze_options_min), "snooze_options_min harus positif"),
        (st.still_angle_deg + st.exit_hysteresis_deg < st.reposition_angle_deg,
         "sudut diam + histeresis harus lebih kecil dari sudut reposisi"),
        (s.noise.min_limit <= s.noise.max_limit, "noise.min_limit <= noise.max_limit"),
        (1 <= s.engine.time_scale_min <= s.engine.time_scale <= s.engine.time_scale_max,
         "engine.time_scale harus di dalam rentang min dan max"),
    ]
    for ok, message in checks:
        if not ok:
            raise ConfigError(message)


def _apply_overrides(settings: Settings, env: dict[str, str]) -> Settings:
    broker, engine, edge = settings.broker, settings.engine, settings.edge
    try:
        if "MQTT_HOST" in env:
            broker = replace(broker, host=env["MQTT_HOST"])
        if "MQTT_PORT" in env:
            broker = replace(broker, port=int(env["MQTT_PORT"]))
        if "MQTT_TLS" in env:
            word = env["MQTT_TLS"].lower()
            if word not in _TRUE_WORDS | _FALSE_WORDS:
                raise ConfigError("MQTT_TLS harus true atau false")
            broker = replace(broker, tls=word in _TRUE_WORDS)
        if "TIME_SCALE" in env:
            engine = replace(engine, time_scale=float(env["TIME_SCALE"]))
        if "ACCEL_SENSOR" in env:
            edge = replace(edge, accel_sensor=env["ACCEL_SENSOR"])
        if "GYRO_SENSOR" in env:
            edge = replace(edge, gyro_sensor=env["GYRO_SENSOR"])
    except ValueError as exc:
        raise ConfigError(f"Nilai .env tidak valid: {exc}") from exc
    return replace(settings, broker=broker, engine=engine, edge=edge)


def load_settings(config_path: str | None = None, env: dict[str, str] | None = None) -> Settings:
    env = env if env is not None else read_env()
    path = find_config(config_path, env)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings = _apply_overrides(_build(Settings, raw, "config"), env)
    validate(settings)
    return settings


def load_runtime(config_path: str | None = None, env_file: str = ".env") -> Runtime:
    """Muat konfigurasi dan PROJECT_ID; menolak placeholder."""
    env = read_env(env_file)
    settings = load_settings(config_path, env)
    return Runtime(settings=settings, project_id=validate_project_id(env.get("PROJECT_ID")))
