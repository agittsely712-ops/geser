"""Format rekaman telemetry untuk tools/record_telemetry.py dan mode replay."""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from geser.domain.models import Role, Telemetry, WindowFeatures

from .errors import PayloadError

TELEMETRY_COLUMNS = (
    "received_ms", "device", "run", "n_msg", "t_ms", "window_s", "samples",
    "gravity_x", "gravity_y", "gravity_z", "tilt_deg", "tilt_step_deg",
    "accel_dev_rms", "gyro_path_rad", "calibrated",
)


@dataclass(frozen=True, slots=True)
class Record:
    topic: str
    received_ms: int
    payload: bytes


def to_json_line(record: Record) -> str:
    """Satu baris JSON; payload non-JSON (misal 'online') disimpan sebagai teks."""
    text = record.payload.decode("utf-8", errors="replace")
    try:
        body: Any = json.loads(text)
    except ValueError:
        body = text
    return json.dumps({"topic": record.topic, "received_ms": record.received_ms, "payload": body})


def _from_obj(obj: Any) -> Record:
    if not isinstance(obj, dict) or not {"topic", "received_ms", "payload"} <= set(obj):
        raise PayloadError("baris rekaman harus memuat topic, received_ms, payload")
    payload = obj["payload"]
    raw = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload).encode()
    return Record(str(obj["topic"]), int(obj["received_ms"]), raw)


def read_json_records(text: str) -> Iterator[Record]:
    """Baca JSONL (satu objek per baris) atau satu larik JSON."""
    stripped = text.strip()
    if stripped.startswith("["):
        for obj in json.loads(stripped):
            yield _from_obj(obj)
        return
    for line in stripped.splitlines():
        if line.strip():
            yield _from_obj(json.loads(line))


def telemetry_to_row(received_ms: int, t: Telemetry) -> list[Any]:
    f = t.features
    return [received_ms, t.device.value, t.run, t.n_msg, t.t_ms, f.window_s, f.samples,
            *f.gravity, f.tilt_deg if f.tilt_deg is not None else "", f.tilt_step_deg,
            f.accel_dev_rms, f.gyro_path_rad, f.calibrated]


def telemetry_csv(rows: Iterable[tuple[int, Telemetry]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(TELEMETRY_COLUMNS)
    for received_ms, tele in rows:
        writer.writerow(telemetry_to_row(received_ms, tele))
    return out.getvalue()


def read_telemetry_csv(text: str) -> Iterator[tuple[int, Telemetry]]:
    for row in csv.DictReader(io.StringIO(text)):
        try:
            tilt = row["tilt_deg"]
            features = WindowFeatures(
                window_s=float(row["window_s"]), samples=int(row["samples"]),
                gravity=(float(row["gravity_x"]), float(row["gravity_y"]), float(row["gravity_z"])),
                tilt_deg=float(tilt) if tilt != "" else None,
                tilt_step_deg=float(row["tilt_step_deg"]),
                accel_dev_rms=float(row["accel_dev_rms"]),
                gyro_path_rad=float(row["gyro_path_rad"]),
                calibrated=row["calibrated"].strip().lower() == "true",
            )
            yield int(row["received_ms"]), Telemetry(
                Role(row["device"]), row["run"], int(row["n_msg"]), int(row["t_ms"]), features
            )
        except (KeyError, ValueError) as exc:
            raise PayloadError(f"baris CSV tidak valid: {exc}") from exc
