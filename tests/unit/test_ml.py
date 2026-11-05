"""Tes unit modul AI GESER."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from geser.domain.models import Role, Telemetry, WindowFeatures
from geser.ml import FEATURE_NAMES, LABELS, PostureModel, features_vector
from geser.ml.live import PostureWatcher
from geser.ml.synthetic import build_dataset, make_example

MODEL = Path(__file__).resolve().parents[2] / "models" / "posture_mlp.json"


def _win(tilt: float | None = 5.0, rms: float = 0.05, gyro: float = 0.02) -> WindowFeatures:
    return WindowFeatures(2.0, 20, (0.0, 0.0, 1.0), tilt, 0.3, rms, gyro, tilt is not None)


def test_features_vector_order_and_missing() -> None:
    vec = features_vector(_win(tilt=None), None)
    assert len(vec) == len(FEATURE_NAMES)
    assert math.isnan(vec[0]) and math.isnan(vec[4]) and math.isnan(vec[5])


def test_dataset_is_balanced_and_valid() -> None:
    rows = build_dataset(per_class=20, seed=1)
    assert len(rows) == 80
    assert {label for _, label in rows} <= set(LABELS)
    assert all(len(vec) == len(FEATURE_NAMES) for vec, _ in rows)


def test_tiny_model_forward_pass() -> None:
    spec = {"version": 1, "classes": ["TEGAK", "CONDONG"], "features": list(FEATURE_NAMES),
            "impute": [0.0] * 6, "mean": [0.0] * 6, "scale": [1.0] * 6,
            "layers": [{"w": [[1.0, -1.0]] + [[0.0, 0.0]] * 5, "b": [0.0, 0.0]}]}
    model = PostureModel.from_dict(spec)
    probs = model.predict_proba([5.0, 0, 0, 0, 0, 0])
    assert probs[0] > 0.99 and abs(sum(probs) - 1.0) < 1e-9
    assert model.predict([-5.0, 0, 0, 0, 0, 0]).label == "CONDONG"


def test_model_rejects_wrong_feature_count() -> None:
    model = PostureModel.load(MODEL)
    with pytest.raises(ValueError):
        model.predict_proba([1.0, 2.0])


@pytest.mark.skipif(not MODEL.exists(), reason="jalankan tools/ml_train.py dulu")
def test_trained_model_meets_acceptance_criteria() -> None:
    """Data uji baru (seed lain, tanpa label salah) harus diprediksi >= 90%."""
    model = PostureModel.load(MODEL)
    rng = random.Random(2024)
    hit = total = 0
    for label in LABELS:
        for _ in range(100):
            hit += model.predict(make_example(label, rng)).label == label
            total += 1
    assert hit / total >= 0.90


@pytest.mark.skipif(not MODEL.exists(), reason="jalankan tools/ml_train.py dulu")
def test_missing_values_do_not_crash() -> None:
    model = PostureModel.load(MODEL)
    pred = model.predict([math.nan, 0.2, 0.05, 0.02, math.nan, math.nan])
    assert pred.label in LABELS and 0.0 < pred.confidence <= 1.0
    assert json.loads(MODEL.read_text())["classes"] == list(LABELS)


@pytest.mark.skipif(not MODEL.exists(), reason="jalankan tools/ml_train.py dulu")
def test_watcher_pairs_windows_and_counts_lean() -> None:
    watcher = PostureWatcher(PostureModel.load(MODEL), smooth=1)
    desk = Telemetry(Role.DESK, "r", 1, 0, _win(tilt=None, rms=0.05, gyro=0.01))
    assert watcher.on_telemetry(1000, desk) is None
    result = None
    for i in range(3):
        body = Telemetry(Role.BODY, "r", i, 0, _win(tilt=35.0, rms=0.05, gyro=0.02))
        result = watcher.on_telemetry(2000 + i * 2000, body)
    assert result is not None and result.smoothed_label == "CONDONG"
    assert result.lean_s == pytest.approx(6.0)
