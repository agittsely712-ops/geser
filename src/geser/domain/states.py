"""Status sesi dan fungsi transisi murni."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    SETTLING = "SETTLING"
    ACTIVE = "ACTIVE"
    STILL = "STILL"
    STILL_LONG = "STILL_LONG"
    STILL_VERY_LONG = "STILL_VERY_LONG"
    STILL_CRITICAL = "STILL_CRITICAL"
    LEAN_DRIFT = "LEAN_DRIFT"
    DISTURBED = "DISTURBED"
    ON_BREAK = "ON_BREAK"
    NO_DATA = "NO_DATA"
    ENDED = "ENDED"


LEVEL_STATES: dict[State, int] = {
    State.STILL_LONG: 1,
    State.STILL_VERY_LONG: 2,
    State.STILL_CRITICAL: 3,
}

STATE_LABELS: dict[State, str] = {
    State.IDLE: "Belum mulai",
    State.CALIBRATING: "Kalibrasi",
    State.SETTLING: "Penyesuaian awal",
    State.ACTIVE: "Aktif bergerak",
    State.STILL: "Diam",
    State.STILL_LONG: "Diam lama (L1)",
    State.STILL_VERY_LONG: "Diam sangat lama (L2)",
    State.STILL_CRITICAL: "Diam kritis (L3)",
    State.LEAN_DRIFT: "Condong lama",
    State.DISTURBED: "Meja terganggu",
    State.ON_BREAK: "Jeda",
    State.NO_DATA: "Tidak ada data",
    State.ENDED: "Sesi selesai",
}

STATE_REASONS: dict[State, str] = {
    State.IDLE: "Sesi belum dimulai.",
    State.CALIBRATING: "Menyimpan posisi duduk acuan (baseline).",
    State.SETTLING: "Mempelajari tingkat getaran normal pengguna.",
    State.ACTIVE: "Posisi baru saja berubah atau belum lama diam.",
    State.STILL: "Posisi body hampir tidak berubah.",
    State.STILL_LONG: "Posisi sama melewati ambang level 1.",
    State.STILL_VERY_LONG: "Posisi sama melewati ambang level 2.",
    State.STILL_CRITICAL: "Posisi sama melewati ambang level 3.",
    State.LEAN_DRIFT: "Kemiringan jauh dari baseline cukup lama.",
    State.DISTURBED: "Desk ikut bergerak, jendela body tidak dihitung.",
    State.ON_BREAK: "Sesi dijeda.",
    State.NO_DATA: "Data body terhenti melebihi batas celah.",
    State.ENDED: "Sesi selesai.",
}


@dataclass(frozen=True, slots=True)
class StateThresholds:
    """Ambang dalam detik skala (sudah termasuk TIME_SCALE pada pembanding)."""

    still_label_s: float
    level1_s: float
    level2_s: float
    level3_s: float
    lean_s: float


@dataclass(frozen=True, slots=True)
class StateFacts:
    """Fakta sesaat yang menentukan status."""

    active: bool
    ended: bool
    paused: bool
    calibrating: bool
    no_data: bool
    disturbed: bool
    settling: bool
    still_scaled_s: float
    lean_scaled_s: float


def transition(facts: StateFacts, th: StateThresholds) -> State:
    """Pilih status berdasarkan prioritas tetap (lihat docs/ALGORITHM.md)."""
    if facts.calibrating:
        return State.CALIBRATING
    if facts.ended:
        return State.ENDED
    if not facts.active:
        return State.IDLE
    if facts.paused:
        return State.ON_BREAK
    if facts.no_data:
        return State.NO_DATA
    if facts.disturbed:
        return State.DISTURBED
    if facts.still_scaled_s >= th.level3_s:
        return State.STILL_CRITICAL
    if facts.still_scaled_s >= th.level2_s:
        return State.STILL_VERY_LONG
    if facts.still_scaled_s >= th.level1_s:
        return State.STILL_LONG
    if facts.lean_scaled_s >= th.lean_s:
        return State.LEAN_DRIFT
    if facts.still_scaled_s >= th.still_label_s:
        return State.STILL
    if facts.settling:
        return State.SETTLING
    return State.ACTIVE
