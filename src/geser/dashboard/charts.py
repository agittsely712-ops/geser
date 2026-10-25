"""Konversi riwayat telemetry dan event ke DataFrame pandas untuk visualisasi."""
from __future__ import annotations

import pandas as pd

from geser.domain.models import EngineEvent, Telemetry
from geser.dashboard.feed import LogEntry


def telemetry_frame(rows: list[tuple[int, Telemetry]], accel_threshold: float) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["waktu", "tilt_deg", "tilt_step_deg", "accel_dev_rms", "ambang_rms", "gyro_path_rad"]
        )
    records = []
    for _received_ms, tele in rows:
        f = tele.features
        records.append({
            "waktu": pd.to_datetime(tele.t_ms, unit="ms"),
            "tilt_deg": f.tilt_deg if f.tilt_deg is not None else 0.0,
            "tilt_step_deg": f.tilt_step_deg,
            "accel_dev_rms": f.accel_dev_rms,
            "ambang_rms": accel_threshold,
            "gyro_path_rad": f.gyro_path_rad,
        })
    return pd.DataFrame.from_records(records).sort_values("waktu")


def events_frame(events: list[EngineEvent]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame(columns=["waktu", "jenis", "pesan", "detail"])
    return pd.DataFrame.from_records([
        {
            "waktu": pd.to_datetime(e.at_ms, unit="ms"),
            "jenis": e.kind.value,
            "pesan": e.message,
            "detail": str(dict(e.data)) if e.data else "-",
        }
        for e in events
    ])


def logs_frame(logs: list[LogEntry]) -> pd.DataFrame:
    if not logs:
        return pd.DataFrame(columns=["waktu", "topic", "ringkasan"])
    return pd.DataFrame.from_records([
        {
            "waktu": pd.to_datetime(item.at_ms, unit="ms"),
            "topic": item.topic,
            "ringkasan": item.summary,
        }
        for item in logs
    ])
