"""Tes unit ringkas untuk modul domain dan codec GESER.

Catatan: Tes ini disediakan agar pengguna dapat menjalankannya sendiri dengan `pytest`.
"""
from __future__ import annotations

import pytest

from geser.domain.features import WindowFeatureExtractor, accel_dev_rms, gyro_path_rad
from geser.domain.geometry import STANDARD_GRAVITY, angle_deg, normalize
from geser.domain.models import AccelSample, GyroSample, Role, SensorBatch
from geser.domain.reminder_policy import ReminderRules, ReminderScheduler, plan_for, ActuationRules
from geser.domain.scoring import ScoreRules, accrue, reward_reposition
from geser.domain.states import State, StateFacts, StateThresholds, transition
from geser.domain.stillness import NoiseFloor, NoiseRules, StillnessRules, StillnessTracker, Verdict
from geser.messaging import codec
from geser.messaging.errors import CommandRejected, TelemetryRejected


def test_geometry_angle_and_normalize() -> None:
    u = normalize((0.0, 0.0, 10.0))
    v = normalize((0.0, 10.0, 0.0))
    assert u == (0.0, 0.0, 1.0)
    assert abs(angle_deg(u, v) - 90.0) < 1e-6


def test_processing1_feature_extraction_and_calibration() -> None:
    extractor = WindowFeatureExtractor(gravity_alpha=0.9, max_gyro_dt_s=0.5)
    extractor.begin_calibration(windows=1)
    accel = tuple(AccelSample(i * 0.1, (0.0, 0.0, STANDARD_GRAVITY)) for i in range(20))
    gyro = tuple(GyroSample(i * 0.1, (0.0, 0.0, 0.0)) for i in range(20))
    batch = SensorBatch(duration_s=2.0, accel=accel, gyro=gyro)

    feat = extractor.extract(batch)
    assert feat is not None
    assert feat.calibrated is True
    assert feat.tilt_deg == 0.0
    assert feat.accel_dev_rms == 0.0
    assert feat.gyro_path_rad == 0.0


def test_processing2_stillness_and_reposition() -> None:
    rules = StillnessRules(
        still_angle_deg=10.0,
        exit_hysteresis_deg=4.0,
        reposition_angle_deg=15.0,
        gyro_path_max_rad=0.15,
        reposition_gyro_rad=0.8,
        reposition_gyro_window_s=10.0,
    )
    tracker = StillnessTracker(rules)
    v1 = tracker.observe(
        (0.0, 0.0, 1.0),
        accel_dev_rms=0.05,
        accel_dev_limit=0.25,
        gyro_path_rad=0.02,
        window_s=2.0,
        at_s=2.0,
    )
    assert v1 is Verdict.STILL
    assert tracker.still_s == 2.0

    # Miring besar (>= 15 derajat) memicu REPOSITION dan mereset durasi diam
    moved = normalize((0.5, 0.0, 0.866))
    v2 = tracker.observe(
        moved,
        accel_dev_rms=0.05,
        accel_dev_limit=0.25,
        gyro_path_rad=0.02,
        window_s=2.0,
        at_s=4.0,
    )
    assert v2 is Verdict.REPOSITION
    assert tracker.still_s == 0.0


def test_state_transition_priority() -> None:
    th = StateThresholds(still_label_s=300, level1_s=1800, level2_s=2700, level3_s=3600, lean_s=300)
    facts = StateFacts(
        active=True,
        ended=False,
        paused=False,
        calibrating=False,
        no_data=False,
        disturbed=False,
        settling=False,
        still_scaled_s=1900.0,
        lean_scaled_s=0.0,
    )
    assert transition(facts, th) is State.STILL_LONG


def test_codec_rejects_stale_and_unknown_command() -> None:
    limits = codec.CommandLimits(snooze_options=(5, 10), scale_min=1.0, scale_max=120.0)
    with pytest.raises(CommandRejected):
        codec.decode_command(b'{"cmd":"hapus_semua"}', limits)

    bad_tele = b'{"v":1,"device":"body","run":"abcd","n_msg":1,"t_ms":1000,"window_s":2.0,"samples":10,"gravity":[0,0,1],"tilt_deg":null,"tilt_step_deg":0.0,"accel_dev_rms":0.1,"gyro_path_rad":0.0,"calibrated":false}'
    with pytest.raises(TelemetryRejected):
        codec.decode_telemetry(Role.BODY, bad_tele, now_ms=1_790_000_000_000, max_skew_s=30.0)
