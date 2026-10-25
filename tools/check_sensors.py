"""Periksa kesiapan termux-sensor dan baca satu jendela uji."""
from __future__ import annotations

import shutil
import subprocess
import sys

from geser.adapters.system_clock import SystemClock
from geser.adapters.termux_sensor import TermuxSensor
from geser.ports import SensorUnavailable
from geser.settings import load_settings


def main() -> int:
    if shutil.which("termux-sensor") is None:
        print("termux-sensor tidak ditemukan di sistem ini.")
        print("- Di Laptop: jalankan edge memakai flag '--simulate still|fidget|shake'.")
        print("- Di HP Termux: jalankan 'pkg install termux-api' dan pasang APK Termux:API dari F-Droid.")
        return 1

    print("1. Memeriksa daftar sensor (termux-sensor -l):")
    listed = subprocess.run(["termux-sensor", "-l"], capture_output=True, text=True, timeout=8)
    print(listed.stdout or listed.stderr)

    import argparse
    from dataclasses import replace

    parser = argparse.ArgumentParser(description="Periksa kesiapan termux-sensor.")
    parser.add_argument("--accel-sensor", help="nama sensor akselerometer")
    parser.add_argument("--gyro-sensor", help="nama sensor giroskop")
    args = parser.parse_args()

    settings = load_settings()
    edge_settings = settings.edge
    if args.accel_sensor:
        edge_settings = replace(edge_settings, accel_sensor=args.accel_sensor)
    if args.gyro_sensor:
        edge_settings = replace(edge_settings, gyro_sensor=args.gyro_sensor)

    print(
        f"2. Membaca sampel uji selama 2 detik "
        f"(accel='{edge_settings.accel_sensor}', gyro='{edge_settings.gyro_sensor}')..."
    )
    sensor = TermuxSensor(edge_settings, SystemClock())
    try:
        batch = sensor.read_batch(edge_settings.window_s)
    except SensorUnavailable as exc:
        print(f"Gagal membaca sensor: {exc}")
        return 1
    finally:
        sensor.close()

    print(f"Berhasil! Sampel akselerometer: {len(batch.accel)}, giroskop: {len(batch.gyro)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
