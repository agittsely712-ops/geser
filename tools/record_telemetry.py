"""Rekam pesan MQTT GESER ke berkas JSONL atau CSV untuk analisis dan mode replay."""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from geser.adapters.mqtt_bus import MqttBus
from geser.adapters.system_clock import SystemClock
from geser.apps.common import configure_logging, runtime_or_exit, stop_on_signal
from geser.domain.models import Telemetry
from geser.messaging import codec, recording
from geser.messaging.errors import PayloadError, TopicError
from geser.messaging.topics import KIND_TELEMETRY, TopicMap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rekam paket telemetry GESER ke CSV atau JSONL.")
    parser.add_argument("--out", default="recordings/sesi.jsonl",
                        help="Berkas keluaran (.jsonl atau .csv)")
    parser.add_argument("--duration", type=float, default=60.0,
                        help="Lama perekaman dalam detik (default: 60)")
    parser.add_argument("--config", help="Jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(False)
    runtime = runtime_or_exit(args.config, args.env_file)
    topics = TopicMap(runtime.project_id)
    clock = SystemClock()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_records: list[recording.Record] = []
    tele_rows: list[tuple[int, Telemetry]] = []

    def on_message(topic: str, payload: bytes) -> None:
        now_ms = clock.now_ms()
        raw_records.append(recording.Record(topic, now_ms, payload))
        try:
            role, kind = topics.parse_edge(topic)
            if kind == KIND_TELEMETRY:
                tele = codec.decode_telemetry(role, payload, now_ms=now_ms, max_skew_s=None)
                tele_rows.append((now_ms, tele))
                print(f"[{role.value}] n={tele.n_msg} rms={tele.features.accel_dev_rms:.3f}")
        except (TopicError, PayloadError):
            pass

    bus = MqttBus(runtime.settings.broker, f"geser-rec-{secrets.token_hex(3)}")
    for t in topics.all_topics():
        bus.subscribe(t, on_message)
    bus.connect(None)

    stop = stop_on_signal()
    print(f"Merekam topic {topics.root}/# selama {args.duration:g} detik ke {out_path}...")
    stop.wait(args.duration)
    bus.disconnect()

    if out_path.suffix.lower() == ".csv":
        out_path.write_text(recording.telemetry_csv(tele_rows), encoding="utf-8")
        print(f"Selesai. {len(tele_rows)} baris telemetry disimpan di {out_path}")
    else:
        lines = "\n".join(recording.to_json_line(r) for r in raw_records) + ("\n" if raw_records else "")
        out_path.write_text(lines, encoding="utf-8")
        print(f"Selesai. {len(raw_records)} rekaman pesan disimpan di {out_path}")


if __name__ == "__main__":
    main()
