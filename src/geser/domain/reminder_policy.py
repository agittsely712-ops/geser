"""Kebijakan pengingat bertahap, snooze, pesan, dan rencana aktuasi."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Role

MAX_LEVEL = 3
MS_PER_S = 1000

_MESSAGES: dict[int, tuple[str, ...]] = {
    1: (
        "Sudah {m} menit di posisi yang sama. Coba ganti posisi atau berdiri sebentar.",
        "Posisimu hampir tidak berubah selama {m} menit. Geser dikit, yuk.",
        "Sekitar {m} menit tanpa perubahan posisi. Coba ganti cara duduk.",
    ),
    2: (
        "Sudah {m} menit tanpa ganti posisi. Berdiri dan regangkan badan sebentar.",
        "{m} menit di posisi yang sama. Waktunya bangun sebentar, lalu lanjut lagi.",
        "Posisi belum berubah selama {m} menit. Coba berjalan sebentar.",
    ),
    3: (
        "Sudah {m} menit tanpa perubahan posisi. Sebaiknya istirahat dari tempat dudukmu.",
        "{m} menit di posisi yang sama. Berdiri dan bergerak sebentar, ya.",
        "Posisi sama selama {m} menit. Ambil jeda singkat untuk berpindah.",
    ),
}


def compose_message(level: int, still_min: int, variant: int) -> str:
    pool = _MESSAGES[level]
    return pool[variant % len(pool)].format(m=still_min)


@dataclass(frozen=True, slots=True)
class ReminderRules:
    level_s: tuple[float, float, float]  # detik skala untuk L1, L2, L3
    cooldown_s: float  # detik skala


def level_for(still_scaled_s: float, level_s: tuple[float, float, float]) -> int:
    level = 0
    for index, threshold in enumerate(level_s, start=1):
        if still_scaled_s >= threshold:
            level = index
    return level


class ReminderScheduler:
    """Memutuskan kapan pengingat baru dikirim. Waktu dalam ms jam dinding."""

    def __init__(self, rules: ReminderRules) -> None:
        self._rules = rules
        self._issued = 0
        self._count = 0
        self._last_ms: int | None = None
        self._snooze_until_ms = 0
        self._reissue = False

    @property
    def active_level(self) -> int:
        return self._issued

    @property
    def count(self) -> int:
        return self._count

    def evaluate(self, still_scaled_s: float, now_ms: int, time_scale: float) -> int | None:
        """Level yang harus dikirim sekarang, atau None."""
        target = level_for(still_scaled_s, self._rules.level_s)
        if target == 0 or now_ms < self._snooze_until_ms:
            return None
        cooldown_ms = self._rules.cooldown_s / time_scale * MS_PER_S
        cooled = self._last_ms is None or now_ms - self._last_ms >= cooldown_ms
        escalated = target > self._issued
        repeat_l3 = target == MAX_LEVEL and self._issued == MAX_LEVEL
        if self._reissue or ((escalated or repeat_l3) and cooled):
            return self._issue(target, now_ms)
        return None

    def snooze(self, until_ms: int) -> int:
        """Tunda pengingat; kembalikan level aktif sebelumnya."""
        previous = self._issued
        self._issued = 0
        self._snooze_until_ms = until_ms
        self._reissue = previous > 0
        return previous

    def reset(self) -> int:
        """Batalkan semua (posisi berganti, jeda, selesai); kembalikan level aktif."""
        previous = self._issued
        self._issued = 0
        self._last_ms = None
        self._snooze_until_ms = 0
        self._reissue = False
        return previous

    def _issue(self, level: int, now_ms: int) -> int:
        self._issued = level
        self._last_ms = now_ms
        self._count += 1
        self._reissue = False
        return level


@dataclass(frozen=True, slots=True)
class ActuationRules:
    short_ms: int
    long_ms: int
    pulses: int
    pause_ms: int


@dataclass(frozen=True, slots=True)
class ActuationPlan:
    vibrate_ms: tuple[int, ...]
    pause_ms: int
    notify: bool


def plan_for(role: Role, level: int, rules: ActuationRules) -> ActuationPlan:
    """Desk selalu menampilkan notifikasi; body bergetar mulai level 2."""
    if role is Role.DESK:
        return ActuationPlan((), 0, True)
    if level >= MAX_LEVEL:
        return ActuationPlan((rules.long_ms,) * rules.pulses, rules.pause_ms, False)
    if level == 2:
        return ActuationPlan((rules.short_ms,), 0, False)
    return ActuationPlan((), 0, False)
