"""Aliran data MQTT thread-safe dan mode replay untuk dashboard Streamlit."""
from __future__ import annotations

import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from geser.adapters.mqtt_bus import MqttBus
from geser.domain.models import (
    EngineEvent,
    ReminderMessage,
    Role,
    SessionSnapshot,
    Telemetry,
)
from geser.messaging import codec, recording
from geser.messaging.errors import PayloadError
from geser.messaging.topics import KIND_PRESENCE, TopicMap
from geser.settings.models import Runtime

MAX_TELEMETRY = 360
MAX_EVENTS = 200
MAX_LOGS = 250


@dataclass(frozen=True, slots=True)
class LogEntry:
    at_ms: int
    topic: str
    summary: str


@dataclass
class FeedSnapshot:
    connected: bool
    replay_mode: bool
    session: SessionSnapshot | None
    presence: dict[Role, bool]
    body_history: list[ tuple[int, Telemetry] ]
    desk_history: list[ tuple[int, Telemetry] ]
    reminders: list[ReminderMessage]
    events: list[EngineEvent]
    logs: list[LogEntry]


class DashboardFeed:
    """Berlangganan ke seluruh topic proyek dan menyimpan riwayat terbatas di memori."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.topics = TopicMap(runtime.project_id)
        self._limits = codec.limits_from_settings(runtime.settings)
        client_id = f"geser-dash-{secrets.token_hex(3)}"
        self._bus = MqttBus(runtime.settings.broker, client_id)
        self._lock = threading.Lock()
        self._replay_mode = False
        self._session: SessionSnapshot | None = None
        self._presence: dict[Role, bool] = {Role.BODY: False, Role.DESK: False}
        self._body: deque[tuple[int, Telemetry]] = deque(maxlen=MAX_TELEMETRY)
        self._desk: deque[tuple[int, Telemetry]] = deque(maxlen=MAX_TELEMETRY)
        self._reminders: deque[ReminderMessage] = deque(maxlen=MAX_EVENTS)
        self._events: deque[EngineEvent] = deque(maxlen=MAX_EVENTS)
        self._logs: deque[LogEntry] = deque(maxlen=MAX_LOGS)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        t = self.topics
        for role in Role:
            self._bus.subscribe(t.telemetry(role), self._on_message)
            self._bus.subscribe(t.presence(role), self._on_message)
        self._bus.subscribe(t.session, self._on_message)
        self._bus.subscribe(t.reminders, self._on_message)
        self._bus.subscribe(t.events, self._on_message)
        self._bus.connect(None)
        self._started = True

    def send_command(self, cmd: codec.ControlCommand) -> None:
        raw = codec.encode_command(cmd)
        self._bus.publish(self.topics.control, raw, qos=1, retain=False)

    def snapshot(self) -> FeedSnapshot:
        with self._lock:
            return FeedSnapshot(
                connected=self._bus.is_connected,
                replay_mode=self._replay_mode,
                session=self._session,
                presence=dict(self._presence),
                body_history=list(self._body),
                desk_history=list(self._desk),
                reminders=list(self._reminders),
                events=list(self._events),
                logs=list(self._logs),
            )

    def clear_replay(self) -> None:
        with self._lock:
            self._replay_mode = False
            self._body.clear()
            self._desk.clear()

    def load_replay(self, filename: str, content: str) -> int:
        """Muat rekaman CSV atau JSON/JSONL dari tools/record_telemetry.py."""
        count = 0
        with self._lock:
            self._replay_mode = True
            self._body.clear()
            self._desk.clear()
            if filename.lower().endswith(".csv"):
                for r_ms, tele in recording.read_telemetry_csv(content):
                    target = self._body if tele.device is Role.BODY else self._desk
                    target.append((r_ms, tele))
                    count += 1
            else:
                for rec in recording.read_json_records(content):
                    self._ingest_locked(rec.topic, rec.payload, rec.received_ms, check_skew=False)
                    count += 1
        return count

    def _on_message(self, topic: str, payload: bytes) -> None:
        now_ms = time.time_ns() // 1_000_000
        with self._lock:
            if self._replay_mode:
                return
            self._ingest_locked(topic, payload, now_ms, check_skew=False)

    def _ingest_locked(self, topic: str, payload: bytes, now_ms: int, *, check_skew: bool) -> None:
        text_preview = payload.decode("utf-8", errors="replace")[:160]
        self._logs.appendleft(LogEntry(now_ms, topic, text_preview))
        t = self.topics
        try:
            if topic == t.session:
                self._session = codec.decode_session(payload)
            elif topic == t.reminders:
                self._reminders.appendleft(codec.decode_reminder(payload))
            elif topic == t.events:
                self._events.appendleft(codec.decode_event(payload))
            elif topic.startswith(f"{t.root}/edge/"):
                role, kind = t.parse_edge(topic)
                if kind == KIND_PRESENCE:
                    self._presence[role] = payload.strip() == b"online"
                else:
                    skew = self.runtime.settings.engine.max_clock_skew_s if check_skew else None
                    tele = codec.decode_telemetry(role, payload, now_ms=now_ms, max_skew_s=skew)
                    target = self._body if role is Role.BODY else self._desk
                    target.append((now_ms, tele))
        except PayloadError as exc:
            self._logs.appendleft(LogEntry(now_ms, topic, f"[DITOLAK] {exc}"))
