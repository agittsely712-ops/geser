"""Jalankan 7 skenario pengujian secara deterministik di memori (tanpa broker jaringan)."""
from __future__ import annotations

from dataclasses import replace

from geser.adapters.memory_bus import MemoryBroker, MemoryBus
from geser.adapters.system_clock import ManualClock
from geser.domain.geometry import Vec3, normalize
from geser.domain.models import Role, SessionSnapshot, Telemetry, WindowFeatures
from geser.messaging import codec
from geser.messaging.topics import TopicMap
from geser.services.session_engine import SessionEngine
from geser.settings import load_settings


def _send_win(
    bus: MemoryBus,
    topics: TopicMap,
    clock: ManualClock,
    role: Role,
    n_msg: int,
    gravity: Vec3,
    *,
    tilt_deg: float | None = 5.0,
    accel_rms: float = 0.05,
    gyro_rad: float = 0.01,
) -> None:
    feat = WindowFeatures(
        window_s=2.0,
        samples=20,
        gravity=normalize(gravity),
        tilt_deg=tilt_deg,
        tilt_step_deg=0.5,
        accel_dev_rms=accel_rms,
        gyro_path_rad=gyro_rad,
        calibrated=tilt_deg is not None,
    )
    tele = Telemetry(role, "simrun01", n_msg, clock.now_ms(), feat)
    bus.publish(topics.telemetry(role), codec.encode_telemetry(tele))


def main() -> None:
    settings = load_settings()
    settings = replace(settings, engine=replace(settings.engine, time_scale=30.0))
    topics = TopicMap("geser-kelompok-sim0")
    broker = MemoryBroker()
    clock = ManualClock()
    engine_bus = MemoryBus(broker)
    edge_bus = MemoryBus(broker)

    snapshots: list[SessionSnapshot] = []
    reminders: list[codec.ReminderMessage] = []

    engine_bus.subscribe(topics.session, lambda _t, raw: snapshots.append(codec.decode_session(raw)))
    engine_bus.subscribe(topics.reminders, lambda _t, raw: reminders.append(codec.decode_reminder(raw)))

    engine = SessionEngine(settings=settings, topics=topics, bus=engine_bus, clock=clock)
    engine.open()

    def cmd(name: codec.CommandName) -> None:
        edge_bus.publish(topics.control, codec.encode_command(codec.ControlCommand(name)))

    cmd(codec.CommandName.START)
    msg_id = 0

    print("Skenario 1: Diam sampai Level 1 dan Level 2 (TIME_SCALE=30x)...")
    for _ in range(46):
        clock.advance(2.0)
        msg_id += 1
        _send_win(edge_bus, topics, clock, Role.DESK, msg_id, (0.0, 0.0, 1.0), accel_rms=0.03)
        _send_win(edge_bus, topics, clock, Role.BODY, msg_id, (0.0, 0.08, 0.996), accel_rms=0.05)
    print(f"  -> Status: {snapshots[-1].state.value}, Level Pengingat: {snapshots[-1].reminder_level}")

    print("Skenario 2: Ganti posisi (reposition >= 15 deg) memicu Auto-Clear...")
    clock.advance(2.0)
    msg_id += 1
    _send_win(edge_bus, topics, clock, Role.BODY, msg_id, (0.45, 0.0, 0.89), tilt_deg=26.0, gyro_rad=0.9)
    print(f"  -> Status: {snapshots[-1].state.value}, Event Pengingat Terakhir: {reminders[-1].event.value}")

    print("Skenario 3: Gerak kecil (< 10 deg) tidak mereset posisi...")
    for _ in range(6):
        clock.advance(2.0)
        msg_id += 1
        _send_win(edge_bus, topics, clock, Role.BODY, msg_id, (0.46, 0.02, 0.88), tilt_deg=8.0, accel_rms=0.06)
    print(f"  -> Status: {snapshots[-1].state.value}, Durasi diam skala: {snapshots[-1].still_scaled_s:.0f}s")

    print("Skenario 4: Meja diguncang (desk accel_dev_rms >= 0.6) -> DISTURBED...")
    clock.advance(2.0)
    msg_id += 1
    _send_win(edge_bus, topics, clock, Role.DESK, msg_id, (0.0, 0.0, 1.0), accel_rms=0.85)
    _send_win(edge_bus, topics, clock, Role.BODY, msg_id, (0.46, 0.02, 0.88), accel_rms=0.35)
    print(f"  -> Status: {snapshots[-1].state.value}")

    print("Skenario 5: Condong lama (>= 25 deg dari baseline) -> LEAN_DRIFT...")
    for _ in range(6):
        clock.advance(2.0)
        msg_id += 1
        _send_win(edge_bus, topics, clock, Role.DESK, msg_id, (0.0, 0.0, 1.0), accel_rms=0.02)
        _send_win(edge_bus, topics, clock, Role.BODY, msg_id, (0.46, 0.02, 0.88), tilt_deg=28.0, accel_rms=0.30)
    print(f"  -> Status: {snapshots[-1].state.value}")

    print("Skenario 6: Data body terputus > 6 detik -> NO_DATA...")
    clock.advance(8.0)
    engine.tick()
    print(f"  -> Status: {snapshots[-1].state.value}")

    cmd(codec.CommandName.END)
    print(f"Skenario 7: Sesi diakhiri -> Status: {snapshots[-1].state.value}, Skor akhir: {snapshots[-1].score}")


if __name__ == "__main__":
    main()
