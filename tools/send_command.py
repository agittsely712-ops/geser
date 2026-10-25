"""Kirim perintah kontrol ke topic geser/<PROJECT_ID>/control lewat baris perintah."""
from __future__ import annotations

import argparse
import secrets
import time

from geser.adapters.mqtt_bus import MqttBus
from geser. apps.common import configure_logging, runtime_or_exit
from geser.domain.models import Role
from geser.messaging.codec import CommandName, ControlCommand, encode_command
from geser.messaging.topics import TopicMap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kirim perintah kontrol ke GESER.")
    parser.add_argument("cmd", choices=[c.value for c in CommandName], help="Nama perintah")
    parser.add_argument("--minutes", type=int, help="Menit snooze (5 atau 10)")
    parser.add_argument("--target", choices=[r.value for r in Role], default="body",
                        help="Target perangkat untuk calibrate (default: body)")
    parser.add_argument("--value", type=float, help="Nilai skala waktu untuk time_scale")
    parser.add_argument("--config", help="Jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(False)
    runtime = runtime_or_exit(args.config, args.env_file)
    topics = TopicMap(runtime.project_id)
    name = CommandName(args.cmd)

    command = ControlCommand(
        name=name,
        minutes=args.minutes if name is CommandName.SNOOZE else None,
        target=Role(args.target) if name is CommandName.CALIBRATE else None,
        value=args.value if name is CommandName.TIME_SCALE else None,
    )
    payload = encode_command(command)

    bus = MqttBus(runtime.settings.broker, f"geser-ctl-{secrets.token_hex(3)}")
    bus.connect(None)
    if not bus.wait_connected(5.0):
        raise SystemExit("Gagal terhubung ke broker MQTT dalam 5 detik.")
    bus.publish(topics.control, payload, qos=1, retain=False)
    time.sleep(0.3)
    bus.disconnect()
    print(f"Terkirim ke {topics.control}: {payload.decode('utf-8')}")


if __name__ == "__main__":
    main()
