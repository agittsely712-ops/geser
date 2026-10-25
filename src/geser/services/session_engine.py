"""Mesin sesi: Processing 2, fusi body+desk, state machine, pengingat, dan skor."""
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from typing import Any

from geser.domain.models import (
    EngineEvent,
    EventKind,
    ReminderKind,
    ReminderMessage,
    Role,
    SessionSnapshot,
    Telemetry,
    WindowFeatures,
)
from geser.domain.reminder_policy import (
    ReminderRules,
    ReminderScheduler,
    compose_message,
)
from geser.domain.scoring import ScoreRules, accrue, reward_reposition
from geser.domain.states import (
    LEVEL_STATES,
    STATE_LABELS,
    STATE_REASONS,
    State,
    StateFacts,
    StateThresholds,
    transition,
)
from geser.domain.stillness import (
    NoiseFloor,
    NoiseRules,
    StillnessRules,
    StillnessTracker,
    Verdict,
)
from geser.messaging import codec
from geser.messaging.errors import PayloadError
from geser.messaging.topics import KIND_PRESENCE, TopicMap
from geser.ports import Clock, MessageBus
from geser.settings.models import Settings

log = logging.getLogger(__name__)

MS_PER_S = 1000
S_PER_MIN = 60
PRESENCE_ONLINE = b"online"
REMINDER_CLEARED_TEXT = "Posisi sudah berganti, pengingat dibatalkan."


@dataclass(frozen=True, slots=True)
class _DeskWindow:
    received_ms: int
    telemetry: Telemetry


class _Run:
    """Keadaan mutable satu sesi pemantauan."""

    def __init__(self, tracker: StillnessTracker, noise: NoiseFloor,
                 scheduler: ReminderScheduler, score: float, started_ms: int) -> None:
        self.tracker = tracker
        self.noise = noise
        self.scheduler = scheduler
        self.score = score
        self.started_ms = started_ms
        self.active = False
        self.ended = False
        self.paused = False
        self.noise_done = False
        self.disturbed = False
        self.no_data = False
        self.last_body_ms = started_ms
        self.lean_s = 0.0
        self.anchor_tilt: float | None = None
        self.repositions = 0
        self.last_reposition_ms: int | None = None
        self.longest_still_scaled_s = 0.0
        self.pending_window_min = 0.0


class SessionEngine:
    def __init__(self, *, settings: Settings, topics: TopicMap, bus: MessageBus, clock: Clock,
                 desk_filter: bool | None = None) -> None:
        self._cfg = settings
        self._topics = topics
        self._bus = bus
        self._clock = clock
        self._desk_filter = settings.fusion.desk_filter if desk_filter is None else desk_filter
        self._lock = threading.RLock()
        self._guard = codec.SequenceGuard()
        self._limits = codec.limits_from_settings(settings)
        self._thresholds = self._build_thresholds()
        self._online = {Role.BODY: False, Role.DESK: False}
        self._desk: _DeskWindow | None = None
        self._time_scale = settings.engine.time_scale
        self._calibrating_until_ms = 0
        self._state = State.IDLE
        self._last_publish_ms = 0
        self._run = self._new_run(self._clock.now_ms())

    # ------------------------------------------------------------ lifecycle
    def open(self) -> None:
        """Hubungkan bus, berlangganan, dan umumkan status awal."""
        t = self._topics
        for role in Role:
            self._bus.subscribe(t.telemetry(role), self._on_edge_message)
            self._bus.subscribe(t.presence(role), self._on_edge_message)
        self._bus.subscribe(t.control, self._on_control)
        self._bus.connect(None)
        with self._lock:
            self._publish_session(self._clock.now_ms(), force=True)

    def run(self, stop: threading.Event) -> None:
        self.open()
        try:
            while not stop.is_set():
                self._clock.sleep(self._cfg.engine.tick_s)
                self.tick()
        finally:
            self._bus.disconnect()

    def tick(self) -> None:
        with self._lock:
            self._refresh(self._clock.now_ms())

    # -------------------------------------------------------------- builders
    def _build_thresholds(self) -> StateThresholds:
        r, lean, still = self._cfg.reminders, self._cfg.lean, self._cfg.stillness
        return StateThresholds(
            still_label_s=still.label_min * S_PER_MIN,
            level1_s=r.level1_min * S_PER_MIN,
            level2_s=r.level2_min * S_PER_MIN,
            level3_s=r.level3_min * S_PER_MIN,
            lean_s=lean.duration_min * S_PER_MIN,
        )

    def _new_run(self, now_ms: int) -> _Run:
        c = self._cfg
        tracker = StillnessTracker(StillnessRules(
            c.stillness.still_angle_deg, c.stillness.exit_hysteresis_deg,
            c.stillness.reposition_angle_deg, c.stillness.gyro_path_max_rad,
            c.stillness.reposition_gyro_rad, c.stillness.reposition_gyro_window_s))
        noise = NoiseFloor(NoiseRules(c.noise.k, c.noise.min_limit, c.noise.max_limit,
                                      c.stillness.accel_dev_max, c.noise.min_samples))
        th = self._thresholds
        scheduler = ReminderScheduler(ReminderRules(
            (th.level1_s, th.level2_s, th.level3_s), c.reminders.cooldown_min * S_PER_MIN))
        return _Run(tracker, noise, scheduler, c.score.start, now_ms)

    def _score_rules(self) -> ScoreRules:
        s = self._cfg.score
        return ScoreRules(s.start, s.still_penalty_per_min, s.lean_penalty_per_min,
                          s.reposition_bonus)

    # -------------------------------------------------------------- handlers
    def _on_edge_message(self, topic: str, payload: bytes) -> None:
        now = self._clock.now_ms()
        try:
            role, kind = self._topics.parse_edge(topic)
            if kind == KIND_PRESENCE:
                self._on_presence(role, payload, now)
                return
            telemetry = codec.decode_telemetry(
                role, payload, now_ms=now, max_skew_s=self._cfg.engine.max_clock_skew_s)
            self._guard.check(telemetry)
        except PayloadError as exc:
            log.warning("Pesan ditolak (%s): %s", topic, exc)
            return
        with self._lock:
            if role is Role.DESK:
                self._desk = _DeskWindow(now, telemetry)
            else:
                self._on_body_window(now, telemetry.features)
            self._refresh(now)

    def _on_presence(self, role: Role, payload: bytes, now: int) -> None:
        with self._lock:
            self._online[role] = payload.strip() == PRESENCE_ONLINE
            self._publish_session(now, force=True)

    def _on_control(self, _topic: str, payload: bytes) -> None:
        try:
            command = codec.decode_command(payload, self._limits)
        except PayloadError as exc:
            log.warning("Perintah ditolak: %s", exc)
            return
        now = self._clock.now_ms()
        with self._lock:
            actions = {
                codec.CommandName.START: self._cmd_start,
                codec.CommandName.END: self._cmd_end,
                codec.CommandName.PAUSE: self._cmd_pause,
                codec.CommandName.RESUME: self._cmd_resume,
                codec.CommandName.SNOOZE: self._cmd_snooze,
                codec.CommandName.CALIBRATE: self._cmd_calibrate,
                codec.CommandName.TIME_SCALE: self._cmd_time_scale,
            }
            actions[command.name](command, now)
            self._refresh(now, force=True)

    # -------------------------------------------------------------- commands
    def _cmd_start(self, _cmd: codec.ControlCommand, now: int) -> None:
        self._run = self._new_run(now)
        self._run.active = True
        self._emit(EventKind.SESSION, "Sesi dimulai.", now)

    def _cmd_end(self, _cmd: codec.ControlCommand, now: int) -> None:
        r = self._run
        if not r.active:
            return
        self._clear_reminders(now)
        r.active, r.ended = False, True
        self._emit(EventKind.SESSION, "Sesi selesai.", now, {
            "score": round(r.score), "repositions": r.repositions,
            "reminders": r.scheduler.count,
            "longest_still_s": round(r.longest_still_scaled_s, 1)})

    def _cmd_pause(self, _cmd: codec.ControlCommand, now: int) -> None:
        if self._run.active and not self._run.paused:
            self._run.paused = True
            self._clear_reminders(now)
            self._emit(EventKind.CONTROL, "Sesi dijeda.", now)

    def _cmd_resume(self, _cmd: codec.ControlCommand, now: int) -> None:
        r = self._run
        if r.active and r.paused:
            r.paused = False
            r.tracker.reset()
            r.lean_s = 0.0
            r.last_body_ms = now
            self._emit(EventKind.CONTROL, "Sesi dilanjutkan.", now)

    def _cmd_snooze(self, cmd: codec.ControlCommand, now: int) -> None:
        if not self._run.active or cmd.minutes is None:
            return
        until = now + int(cmd.minutes * S_PER_MIN * MS_PER_S / self._time_scale)
        previous = self._run.scheduler.snooze(until)
        if previous:
            self._publish_reminder(ReminderKind.CLEARED, previous, REMINDER_CLEARED_TEXT, now)
        self._emit(EventKind.CONTROL, f"Pengingat ditunda {cmd.minutes} menit.", now)

    def _cmd_calibrate(self, cmd: codec.ControlCommand, now: int) -> None:
        if cmd.target is not Role.BODY:
            return
        edge, r = self._cfg.edge, self._run
        hold_s = (edge.calibration_windows + 1) * edge.window_s
        self._calibrating_until_ms = now + int(hold_s * MS_PER_S)
        r.tracker.reset()
        r.lean_s = 0.0
        self._emit(EventKind.CONTROL, "Kalibrasi baseline body dimulai.", now)

    def _cmd_time_scale(self, cmd: codec.ControlCommand, now: int) -> None:
        if cmd.value is not None:
            self._time_scale = cmd.value
            self._emit(EventKind.CONTROL, f"Skala waktu menjadi x{cmd.value:g}.", now)

    # ------------------------------------------------------- body processing
    def _on_body_window(self, now: int, f: WindowFeatures) -> None:
        r = self._run
        if not r.active or r.paused:
            return
        if now < self._calibrating_until_ms:
            r.last_body_ms = now  # data tetap mengalir, hanya tidak dinilai
            return
        if r.no_data:
            r.no_data = False
            r.tracker.reset()
            r.lean_s = 0.0
        r.last_body_ms = now
        r.disturbed = self._desk_disturbed(now)
        if r.disturbed:
            return
        before_scaled_s = r.tracker.still_s * self._time_scale
        first_window = r.tracker.anchor is None
        verdict = r.tracker.observe(
            f.gravity, accel_dev_rms=f.accel_dev_rms, accel_dev_limit=r.noise.limit,
            gyro_path_rad=f.gyro_path_rad, window_s=f.window_s, at_s=now / MS_PER_S)
        if verdict is Verdict.REPOSITION:
            self._on_reposition(f, now, before_scaled_s)
        elif first_window:
            r.anchor_tilt = f.tilt_deg
        self._collect_noise(f, verdict)
        self._track_lean(f)
        r.pending_window_min = f.window_s * self._time_scale / S_PER_MIN
        r.longest_still_scaled_s = max(r.longest_still_scaled_s,
                                       r.tracker.still_s * self._time_scale)

    def _desk_disturbed(self, now: int) -> bool:
        seen = self._desk
        if not self._desk_filter or seen is None:
            return False
        close = now - seen.received_ms <= self._cfg.fusion.pair_gap_s * MS_PER_S
        return close and seen.telemetry.features.accel_dev_rms >= self._cfg.fusion.desk_disturb_accel_rms

    def _on_reposition(self, f: WindowFeatures, now: int, before_scaled_s: float) -> None:
        r = self._run
        r.anchor_tilt = f.tilt_deg
        if before_scaled_s <= 0:
            return  # gerakan berlanjut, tidak ada posisi diam yang dipatahkan
        r.repositions += 1
        r.last_reposition_ms = now
        r.score = reward_reposition(r.score, self._score_rules())
        self._clear_reminders(now)
        self._emit(EventKind.REPOSITION, "Perubahan posisi terdeteksi.", now,
                   {"diam_sebelumnya_menit": round(before_scaled_s / S_PER_MIN, 1)})

    def _collect_noise(self, f: WindowFeatures, verdict: Verdict) -> None:
        r = self._run
        calm = f.gyro_path_rad < self._cfg.stillness.gyro_path_max_rad
        if not r.noise_done and calm and verdict is not Verdict.REPOSITION:
            r.noise.add(f.accel_dev_rms)

    def _track_lean(self, f: WindowFeatures) -> None:
        r, lean = self._run, self._cfg.lean
        if f.tilt_deg is None:
            return
        if f.tilt_deg >= lean.angle_deg:
            r.lean_s += f.window_s
        elif f.tilt_deg < lean.angle_deg - self._cfg.stillness.exit_hysteresis_deg:
            r.lean_s = 0.0

    # --------------------------------------------------------------- refresh
    def _refresh(self, now: int, force: bool = False) -> None:
        r = self._run
        self._detect_gap(now)
        self._finish_settling(now)
        facts = StateFacts(
            active=r.active, ended=r.ended, paused=r.paused,
            calibrating=now < self._calibrating_until_ms, no_data=r.no_data,
            disturbed=r.disturbed, settling=r.active and not r.noise_done,
            still_scaled_s=r.tracker.still_s * self._time_scale,
            lean_scaled_s=r.lean_s * self._time_scale)
        new_state = transition(facts, self._thresholds)
        changed = new_state is not self._state
        if changed:
            self._set_state(new_state, now)
        self._accrue_score()
        self._maybe_remind(now)
        self._publish_session(now, force=force or changed)

    def _detect_gap(self, now: int) -> None:
        r = self._run
        gap_ms = self._cfg.fusion.data_gap_s * MS_PER_S
        if r.active and not r.paused and not r.no_data and now - r.last_body_ms > gap_ms:
            r.no_data = True

    def _finish_settling(self, now: int) -> None:
        r = self._run
        if r.active and not r.noise_done and now - r.started_ms >= self._cfg.noise.settle_s * MS_PER_S:
            limit = r.noise.finalize()
            r.noise_done = True
            self._emit(EventKind.SESSION, f"Ambang getaran personal: {limit:.2f} m/s^2.", now,
                       {"accel_dev_limit": round(limit, 3)})

    def _accrue_score(self) -> None:
        r = self._run
        if r.pending_window_min:
            r.score = accrue(r.score, self._state, r.pending_window_min, self._score_rules())
            r.pending_window_min = 0.0

    def _maybe_remind(self, now: int) -> None:
        r = self._run
        if self._state not in LEVEL_STATES:
            return
        still_scaled_s = r.tracker.still_s * self._time_scale
        level = r.scheduler.evaluate(still_scaled_s, now, self._time_scale)
        if level is None:
            return
        minutes = int(round(still_scaled_s / S_PER_MIN))
        text = compose_message(level, minutes, r.scheduler.count)
        self._publish_reminder(ReminderKind.REMINDER, level, text, now, minutes)
        self._emit(EventKind.REMINDER, f"Pengingat level {level}: {text}", now, {"level": level})

    def _clear_reminders(self, now: int) -> None:
        level = self._run.scheduler.reset()
        if level:
            self._publish_reminder(ReminderKind.CLEARED, level, REMINDER_CLEARED_TEXT, now)
            self._emit(EventKind.CLEARED, "Pengingat dibatalkan otomatis.", now, {"level": level})

    # ------------------------------------------------------------ publishing
    def _set_state(self, new_state: State, now: int) -> None:
        old = self._state
        self._state = new_state
        log.info("Status: %s -> %s", old.value, new_state.value)
        self._emit(EventKind.STATE, f"{STATE_LABELS[old]} -> {STATE_LABELS[new_state]}", now,
                   {"from": old.value, "to": new_state.value})

    def _publish_reminder(self, kind: ReminderKind, level: int, text: str, now: int,
                          still_min: float = 0.0) -> None:
        message = ReminderMessage(kind, level, text, still_min, now)
        self._bus.publish(self._topics.reminders, codec.encode_reminder(message), qos=1)

    def _emit(self, kind: EventKind, text: str, now: int, data: dict[str, Any] | None = None) -> None:
        event = EngineEvent(kind, now, text, data or {})
        self._bus.publish(self._topics.events, codec.encode_event(event), qos=1)

    def _snapshot(self, now: int) -> SessionSnapshot:
        r = self._run
        still_real = r.tracker.still_s
        return SessionSnapshot(
            state=self._state, reason=STATE_REASONS[self._state], active=r.active,
            paused=r.paused, time_scale=self._time_scale, still_real_s=still_real,
            still_scaled_s=still_real * self._time_scale, anchor_tilt_deg=r.anchor_tilt,
            reminder_level=r.scheduler.active_level, last_reposition_ms=r.last_reposition_ms,
            score=int(math.floor(r.score + 0.5)),
            nodes_online={role.value: up for role, up in self._online.items()}, at_ms=now,
            reminders_count=r.scheduler.count, repositions=r.repositions,
            longest_still_s=r.longest_still_scaled_s, lean_scaled_s=r.lean_s * self._time_scale)

    def _publish_session(self, now: int, *, force: bool) -> None:
        heartbeat_ms = self._cfg.engine.session_heartbeat_s * MS_PER_S
        if not force and now - self._last_publish_ms < heartbeat_ms:
            return
        self._last_publish_ms = now
        self._bus.publish(self._topics.session, codec.encode_session(self._snapshot(now)),
                          qos=1, retain=True)
