"""Inferensi model AI tanpa dependensi luar (Python murni), cocok untuk edge/Termux.

Model dilatih di laptop dengan scikit-learn (tools/ml_train.py), lalu bobotnya
diekspor ke JSON. Berkas JSON itulah yang dibaca di sini.
"""
from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import FEATURE_NAMES, LABELS

SPEC_VERSION = 1


@dataclass(frozen=True, slots=True)
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True, slots=True)
class _Layer:
    weights: tuple[tuple[float, ...], ...]  # [input][output]
    bias: tuple[float, ...]


class PostureModel:
    """Jaringan saraf kecil: impute -> standarisasi -> ReLU -> ... -> softmax."""

    def __init__(self, *, classes: Sequence[str], features: Sequence[str],
                 impute: Sequence[float], mean: Sequence[float], scale: Sequence[float],
                 layers: Sequence[_Layer], meta: dict[str, Any] | None = None) -> None:
        if tuple(features) != FEATURE_NAMES:
            raise ValueError("urutan fitur model tidak sama dengan skema GESER")
        if not set(classes) <= set(LABELS):
            raise ValueError("label model tidak dikenal")
        self.classes = tuple(classes)
        self.features = tuple(features)
        self.meta = dict(meta or {})
        self._impute = tuple(impute)
        self._mean = tuple(mean)
        self._scale = tuple(scale)
        self._layers = tuple(layers)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PostureModel:
        if data.get("version") != SPEC_VERSION:
            raise ValueError("versi berkas model tidak didukung")
        layers = [
            _Layer(tuple(tuple(float(v) for v in row) for row in layer["w"]),
                   tuple(float(v) for v in layer["b"]))
            for layer in data["layers"]
        ]
        return cls(classes=data["classes"], features=data["features"], impute=data["impute"],
                   mean=data["mean"], scale=data["scale"], layers=layers, meta=data.get("meta"))

    @classmethod
    def load(cls, path: str | Path) -> PostureModel:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def predict_proba(self, vector: Sequence[float]) -> list[float]:
        if len(vector) != len(self.features):
            raise ValueError(f"butuh {len(self.features)} fitur, diterima {len(vector)}")
        x = [
            ((self._impute[i] if math.isnan(v) else v) - self._mean[i]) / self._scale[i]
            for i, v in enumerate(vector)
        ]
        for index, layer in enumerate(self._layers):
            out = list(layer.bias)
            for i, xi in enumerate(x):
                row = layer.weights[i]
                for j in range(len(out)):
                    out[j] += xi * row[j]
            last = index == len(self._layers) - 1
            x = _softmax(out) if last else [max(0.0, v) for v in out]
        return x

    def predict(self, vector: Sequence[float]) -> Prediction:
        probs = self.predict_proba(vector)
        best = max(range(len(probs)), key=probs.__getitem__)
        named = dict(zip(self.classes, probs, strict=True))
        return Prediction(self.classes[best], probs[best], named)


def _softmax(values: Sequence[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [e / total for e in exps]
