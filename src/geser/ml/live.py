"""Menghubungkan telemetry body+desk ke model AI secara waktu nyata. Murni, tanpa I/O."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from geser.domain.models import Role, Telemetry

from .model import PostureModel, Prediction
from .schema import features_vector

PAIR_GAP_MS = 5000


@dataclass(frozen=True, slots=True)
class LiveResult:
    at_ms: int
    prediction: Prediction
    smoothed_label: str
    lean_s: float  # lama berturut-turut berstatus CONDONG (detik)


class PostureWatcher:
    """Tiap jendela body dipasangkan dengan jendela desk terbaru, lalu diprediksi AI.

    `smoothed_label` = suara terbanyak dari beberapa prediksi terakhir agar tampilan tidak
    berkedip. `lean_s` dihitung dari prediksi AI, bukan dari ambang sudut tetap.
    """

    def __init__(self, model: PostureModel, *, smooth: int = 3) -> None:
        self._model = model
        self._recent: deque[str] = deque(maxlen=max(1, smooth))
        self._desk: tuple[int, Telemetry] | None = None
        self._lean_s = 0.0

    def on_telemetry(self, received_ms: int, tele: Telemetry) -> LiveResult | None:
        if tele.device is Role.DESK:
            self._desk = (received_ms, tele)
            return None
        desk = None
        if self._desk is not None and received_ms - self._desk[0] <= PAIR_GAP_MS:
            desk = self._desk[1].features
        pred = self._model.predict(features_vector(tele.features, desk))
        self._recent.append(pred.label)
        smoothed = Counter(self._recent).most_common(1)[0][0]
        if smoothed == "CONDONG":
            self._lean_s += tele.features.window_s
        elif smoothed != "MEJA_TERGANGGU":
            self._lean_s = 0.0
        return LiveResult(received_ms, pred, smoothed, self._lean_s)
