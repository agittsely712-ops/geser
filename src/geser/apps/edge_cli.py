"""geser-edge: menjalankan satu edge (body atau desk) di HP atau laptop."""
from __future__ import annotations

import argparse
import logging
import random
import secrets

from dataclasses import replace

from geser.adapters.console_actuator import ConsoleActuator
from geser.adapters.mqtt_bus import MqttBus
from geser.adapters.simulated_sensor import PROFILES, SimulatedSensor
from geser.adapters.system_clock import SystemClock
from geser.adapters.termux_actuator import TermuxActuator
from geser.adapters.termux_sensor import TermuxSensor
from geser.domain.models import Role
from geser.messaging.topics import TopicMap
from geser.ports import SensorReader, SensorUnavailable
from geser.services.edge_node import EdgeNode

from .common import configure_logging, runtime_or_exit, stop_on_signal

log = logging.getLogger(__name__)
RUN_ID_BYTES = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geser-edge", description="Jalankan edge GESER.")
    parser.add_argument("--role", required=True, choices=[r.value for r in Role],
                        help="body: di saku baju dada. desk: di meja.")
    parser.add_argument("--simulate", choices=sorted(PROFILES),
                        help="pakai sensor simulasi (tanpa HP) dengan profil ini")
    parser.add_argument("--accel-sensor", help="nama sensor akselerometer (misal: lsm6dsoq_acc)")
    parser.add_argument("--gyro-sensor", help="nama sensor giroskop (misal: lsm6dsoq_gyro)")
    parser.add_argument("--config", help="jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    role, clock = Role(args.role), SystemClock()
    run_id = secrets.token_hex(RUN_ID_BYTES)
    edge_settings = runtime.settings.edge
    if args.accel_sensor:
        edge_settings = replace(edge_settings, accel_sensor=args.accel_sensor)
    if args.gyro_sensor:
        edge_settings = replace(edge_settings, gyro_sensor=args.gyro_sensor)
    settings = replace(runtime.settings, edge=edge_settings)
    sensor: SensorReader
    if args.simulate:
        sensor = SimulatedSensor(args.simulate, clock, random.Random())
    else:
        sensor = TermuxSensor(edge_settings, clock)
    console = ConsoleActuator()
    actuator = console if args.simulate else TermuxActuator(console)
    topics = TopicMap(runtime.project_id)
    node = EdgeNode(
        role=role, run_id=run_id, settings=settings, topics=topics, sensor=sensor,
        bus=MqttBus(settings.broker, f"geser-{role.value}-{run_id}"),
        clock=clock, actuator=actuator,
    )
    log.info("PROJECT_ID=%s, topic dasar: %s", runtime.project_id, topics.root)
    try:
        node.run(stop_on_signal())
    except SensorUnavailable as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
