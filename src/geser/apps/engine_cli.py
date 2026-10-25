"""geser-engine: menjalankan mesin sesi (Processing 2, state machine, pengingat)."""
from __future__ import annotations

import argparse
import logging
import secrets
from dataclasses import replace

from geser.adapters.mqtt_bus import MqttBus
from geser.adapters.system_clock import SystemClock
from geser.messaging.topics import TopicMap
from geser.services.session_engine import SessionEngine

from .common import configure_logging, runtime_or_exit, stop_on_signal

log = logging.getLogger(__name__)
CLIENT_SUFFIX_BYTES = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geser-engine", description="Jalankan engine GESER.")
    parser.add_argument("--time-scale", type=float, help="skala waktu demo (default dari .env)")
    parser.add_argument("--no-desk-filter", action="store_true",
                        help="matikan filter gangguan desk (untuk eksperimen pembanding)")
    parser.add_argument("--config", help="jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    settings = runtime.settings
    if args.time_scale is not None:
        settings = replace(settings, engine=replace(settings.engine, time_scale=args.time_scale))
    topics = TopicMap(runtime.project_id)
    bus = MqttBus(settings.broker, f"geser-engine-{secrets.token_hex(CLIENT_SUFFIX_BYTES)}")
    engine = SessionEngine(settings=settings, topics=topics, bus=bus, clock=SystemClock(),
                           desk_filter=False if args.no_desk_filter else None)
    log.info("PROJECT_ID=%s, TIME_SCALE=x%g, filter desk=%s", runtime.project_id,
             settings.engine.time_scale, not args.no_desk_filter and settings.fusion.desk_filter)
    engine.run(stop_on_signal())


if __name__ == "__main__":
    main()
