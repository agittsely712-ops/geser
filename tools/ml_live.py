"""AI waktu nyata: dengarkan telemetry HP body + desk lewat MQTT, tampilkan prediksi AI.

Jalankan SETELAH kedua edge menyala (geser-edge --role body / --role desk):

  python tools/ml_live.py --model models/posture_mlp.json --lean-alert-s 20

Hanya membaca (subscribe); tidak mengubah apa pun pada engine yang sudah berjalan.
"""
from __future__ import annotations

import argparse
import secrets

from geser.adapters.mqtt_bus import MqttBus
from geser.adapters.system_clock import SystemClock
from geser.apps.common import configure_logging, runtime_or_exit, stop_on_signal
from geser.domain.models import Role
from geser.messaging import codec
from geser.messaging.errors import PayloadError, TopicError
from geser.messaging.topics import KIND_TELEMETRY, TopicMap
from geser.ml import PostureModel
from geser.ml.live import PostureWatcher
from geser.ml.schema import LABEL_TEXT


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="models/posture_mlp.json")
    p.add_argument("--lean-alert-s", type=float, default=20.0,
                   help="beri saran bila AI menilai CONDONG terus selama N detik")
    p.add_argument("--config")
    p.add_argument("--env-file", default=".env")
    args = p.parse_args()

    configure_logging(False)
    runtime = runtime_or_exit(args.config, args.env_file)
    topics = TopicMap(runtime.project_id)
    clock = SystemClock()
    watcher = PostureWatcher(PostureModel.load(args.model))

    def on_message(topic: str, payload: bytes) -> None:
        now_ms = clock.now_ms()
        try:
            role, kind = topics.parse_edge(topic)
            if kind != KIND_TELEMETRY:
                return
            tele = codec.decode_telemetry(role, payload, now_ms=now_ms, max_skew_s=30.0)
        except (TopicError, PayloadError):
            return
        res = watcher.on_telemetry(now_ms, tele)
        if res is None:
            return
        line = (f"AI: {res.smoothed_label:<15} ({res.prediction.confidence:5.1%})  "
                f"{LABEL_TEXT[res.smoothed_label]}")
        if res.lean_s >= args.lean_alert_s:
            line += f"  >> condong {res.lean_s:.0f} dtk, tegakkan badan!"
        print(line)

    bus = MqttBus(runtime.settings.broker, f"geser-ai-{secrets.token_hex(3)}")
    for role in Role:
        bus.subscribe(topics.telemetry(role), on_message)
    bus.connect(None)
    print("AI GESER aktif. Ctrl+C untuk berhenti.")
    stop_on_signal().wait()
    bus.disconnect()


if __name__ == "__main__":
    main()
