"""Movement Score 0 sampai 100."""
from __future__ import annotations

from dataclasses import dataclass

from .states import LEVEL_STATES, State

SCORE_MIN = 0.0
SCORE_MAX = 100.0


@dataclass(frozen=True, slots=True)
class ScoreRules:
    start: float
    still_penalty_per_min: float
    lean_penalty_per_min: float
    reposition_bonus: float


def _clamp(value: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def accrue(score: float, state: State, scaled_minutes: float, rules: ScoreRules) -> float:
    """Kurangi skor sesuai lama berada di status berisiko (menit skala)."""
    if state in LEVEL_STATES:
        return _clamp(score - rules.still_penalty_per_min * scaled_minutes)
    if state is State.LEAN_DRIFT:
        return _clamp(score - rules.lean_penalty_per_min * scaled_minutes)
    return score


def reward_reposition(score: float, rules: ScoreRules) -> float:
    return _clamp(score + rules.reposition_bonus)
