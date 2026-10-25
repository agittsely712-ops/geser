"""Pembaca sensor lewat `termux-sensor` (Termux:API).

Aliran JSON dibaca di thread latar; read_batch() hanya mengambil sampel yang
sudah terkumpul selama jendela.
"""
from __future__ import annotations

import json
import logging
import os
import select
import subprocess
import threading
from typing import IO, Any

try:
    import pty
except ImportError:
    pty = None

from geser.domain.models import AccelSample, GyroSample, SensorBatch
from geser.ports import Clock, SensorUnavailable
from geser.settings.models import EdgeSettings

log = logging.getLogger(__name__)

VECTOR_SIZE = 3


class TermuxSensor:
    def __init__(self, settings: EdgeSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock
        self._lock = threading.Lock()
        self._accel: list[AccelSample] = []
        self._gyro: list[GyroSample] = []
        self._proc: subprocess.Popen[str] | None = None
        self._closed = False

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._ensure_started()
        self._clock.sleep(duration_s)
        with self._lock:
            batch = SensorBatch(duration_s, tuple(self._accel), tuple(self._gyro))
            self._accel, self._gyro = [], []
        return batch

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None
        self._cleanup()

    def _cleanup(self) -> None:
        try:
            subprocess.run(
                ["termux-sensor", "-c"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._cleanup()
        names = f"{self._settings.accel_sensor},{self._settings.gyro_sensor}"
        command = ["termux-sensor", "-s", names, "-d", str(self._settings.sample_interval_ms)]
        try:
            if pty is not None:
                master_fd, slave_fd = pty.openpty()
                self._proc = subprocess.Popen(
                    command,
                    stdout=slave_fd,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    close_fds=True,
                )
                os.close(slave_fd)
                stream = os.fdopen(master_fd, "r", encoding="utf-8")
            else:
                self._proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                assert self._proc.stdout is not None
                stream = self._proc.stdout
        except OSError as exc:
            raise SensorUnavailable(
                "termux-sensor tidak bisa dijalankan. Pasang: pkg install termux-api "
                "dan aplikasi Termux:API (lihat docs/SETUP.md)."
            ) from exc
        threading.Thread(target=self._pump, args=(stream,), daemon=True).start()

    def _pump(self, stream: IO[str]) -> None:
        decoder = json.JSONDecoder()
        buffer = ""
        try:
            for line in iter(stream.readline, ""):
                buffer = (buffer + line).lstrip()
                while buffer:
                    try:
                        obj, end = decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        break  # objek belum lengkap, tunggu baris berikutnya
                    self._ingest(obj)
                    buffer = buffer[end:].lstrip()
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _ingest(self, obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        stamp = self._clock.monotonic_s()
        for name, body in obj.items():
            values = body.get("values") if isinstance(body, dict) else None
            if not isinstance(values, list) or len(values) < VECTOR_SIZE:
                continue
            xyz = (float(values[0]), float(values[1]), float(values[2]))
            lowered = str(name).lower()
            with self._lock:
                if self._settings.accel_sensor.lower() in lowered:
                    self._accel.append(AccelSample(stamp, xyz))
                elif self._settings.gyro_sensor.lower() in lowered:
                    self._gyro.append(GyroSample(stamp, xyz))
