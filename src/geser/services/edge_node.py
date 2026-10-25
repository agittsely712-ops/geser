"""Node edge: membaca sensor, menghitung fitur (Processing 1), mengirim telemetry,
dan menjalankan aktuator saat pengingat datang."""
from __future__ import annotations

import logging
import threading

from geser.domain.features import WindowFeatureExtractor
from geser.domain.models import ReminderKind, Role, Telemetry
from geser.domain.reminder_policy import ActuationRules, plan_for
from geser.messaging import codec
from geser.messaging.errors import PayloadError
from geser.messaging.topics import TopicMap
from geser.ports import Actuator, Clock, LastWill, MessageBus, SensorReader
from geser.settings.models import Settings

log = logging.getLogger(__name__)

PRESENCE_ONLINE = b"online"
PRESENCE_OFFLINE = b"offline"
NOTIFICATION_ID = "geser-reminder"
NOTIFICATION_TITLE = "GESER: Geser dikit, yuk"


class EdgeNode:
    def __init__(
        self,
        *,
        role: Role,
        run_id: str,
        settings: Settings,
        topics: TopicMap,
        sensor: SensorReader,
        bus: MessageBus,
        clock: Clock,
        actuator: Actuator,
    ) -> None:
        self._role = role
        self._run_id = run_id
        self._cfg = settings
        self._topics = topics
        self._sensor = sensor
        self._bus = bus
        self._clock = clock
        self._actuator = actuator
        self._limits = codec.limits_from_settings(settings)
        r = settings.reminders
        self._actuation = ActuationRules(r.vibrate_short_ms, r.vibrate_long_ms,
                                         r.l3_pulses, r.l3_pause_ms)
        self._extractor = WindowFeatureExtractor(
            settings.edge.gravity_alpha, settings.edge.max_gyro_dt_s
        )
        self._lock = threading.Lock()
        self._n_msg = 0

    def run(self, stop: threading.Event) -> None:
        """Loop utama sampai `stop` di-set."""
        self._bus.add_connect_hook(self._announce)
        self._bus.subscribe(self._topics.control, self._on_control)
        self._bus.subscribe(self._topics.reminders, self._on_reminder)
        self._bus.connect(LastWill(self._topics.presence(self._role), PRESENCE_OFFLINE))
        log.info("Edge %s berjalan (run %s)", self._role.value, self._run_id)
        try:
            while not stop.is_set():
                self.step()
        finally:
            self._shutdown()

    def step(self) -> None:
        """Satu jendela: baca sensor, hitung fitur, kirim telemetry."""
        batch = self._sensor.read_batch(self._cfg.edge.window_s)
        with self._lock:
            features = self._extractor.extract(batch)
        if features is None:
            log.warning("Tidak ada sampel akselerometer pada jendela ini")
            return
        self._n_msg += 1
        telemetry = Telemetry(self._role, self._run_id, self._n_msg, self._clock.now_ms(), features)
        self._bus.publish(self._topics.telemetry(self._role), codec.encode_telemetry(telemetry))

    def _announce(self) -> None:
        self._bus.publish(self._topics.presence(self._role), PRESENCE_ONLINE, retain=True)

    def _shutdown(self) -> None:
        self._bus.publish(self._topics.presence(self._role), PRESENCE_OFFLINE, retain=True)
        self._actuator.cancel_vibration()
        self._bus.disconnect()
        self._sensor.close()

    def _on_control(self, _topic: str, payload: bytes) -> None:
        try:
            command = codec.decode_command(payload, self._limits)
        except PayloadError as exc:
            log.warning("Perintah ditolak: %s", exc)
            return
        if command.name is codec.CommandName.CALIBRATE and command.target is self._role:
            with self._lock:
                self._extractor.begin_calibration(self._cfg.edge.calibration_windows)
            log.info("Kalibrasi dimulai: diamkan HP di posisi duduk normal")

    def _on_reminder(self, _topic: str, payload: bytes) -> None:
        try:
            message = codec.decode_reminder(payload)
        except PayloadError as exc:
            log.warning("Pengingat ditolak: %s", exc)
            return
        if message.event is ReminderKind.CLEARED:
            self._actuator.cancel_vibration()
            self._actuator.clear_notification(NOTIFICATION_ID)
            return
        plan = plan_for(self._role, message.level, self._actuation)
        if plan.vibrate_ms:
            self._actuator.vibrate(plan.vibrate_ms, plan.pause_ms)
        if plan.notify:
            self._actuator.notify(NOTIFICATION_TITLE, message.message, NOTIFICATION_ID)
