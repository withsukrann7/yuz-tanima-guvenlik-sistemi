"""Unit tests for sustained camera image anomalies and event transitions."""
import threading
from datetime import date, datetime, time

import numpy as np
import pytest

from yuz_tanima_app import config, veritabani
from yuz_tanima_app.camera_health import CameraHealthMonitor


def solid_frame(value):
    return np.full((96, 128, 3), value, dtype=np.uint8)


def detailed_frame():
    y, x = np.indices((96, 128))
    checker = np.where(((x // 4 + y // 4) % 2) == 0, 35, 215).astype(np.uint8)
    return np.repeat(checker[:, :, None], 3, axis=2)


def covered_frame(value, seed):
    rng = np.random.default_rng(seed)
    noise = rng.integers(-3, 4, size=(96, 128, 1), dtype=np.int16)
    return np.repeat(np.clip(value + noise, 0, 255).astype(np.uint8), 3, axis=2)


def test_changing_frames_do_not_raise_camera_alerts():
    monitor = CameraHealthMonitor()
    active = []
    for step in range(20):
        value = 70 + (step % 8) * 15
        active.extend(
            event for event in monitor.observe(solid_frame(value), now=step * 0.5)
            if event[1]
        )
    assert active == []
    assert not monitor.active_events


def test_sustained_dark_frames_raise_and_resolve_blocked_warning():
    monitor = CameraHealthMonitor()
    transitions = []
    for step in range(27):
        transitions.extend(monitor.observe(solid_frame(0), now=step * 0.5))

    assert ("blocked", True) in transitions
    assert monitor.active_events == {"blocked"}

    transitions.extend(monitor.observe(solid_frame(100), now=14.0))
    assert ("blocked", False) in transitions
    assert not monitor.active_events


def test_sustained_identical_frames_raise_frozen_warning_once():
    monitor = CameraHealthMonitor()
    transitions = []
    active_times = []
    for step in range(21):
        current = monitor.observe(solid_frame(100), now=step * 0.5)
        transitions.extend(current)
        if ("frozen", True) in current:
            active_times.append(step * 0.5)

    assert transitions.count(("frozen", True)) == 1
    assert active_times and active_times[0] <= 10
    assert monitor.active_events == {"frozen"}

    transitions.extend(monitor.observe(solid_frame(180), now=32.0))
    assert transitions[-1] == ("frozen", False)
    assert not monitor.active_events


def test_small_live_sensor_variation_prevents_static_room_false_alarm():
    monitor = CameraHealthMonitor()
    rng = np.random.default_rng(4)
    base = np.full((96, 128, 1), 100, dtype=np.int16)
    transitions = []
    for step in range(25):
        noise = rng.integers(-2, 3, size=(96, 128, 1), dtype=np.int16)
        frame = np.repeat(np.clip(base + noise, 0, 255).astype(np.uint8), 3, axis=2)
        transitions.extend(monitor.observe(frame, now=step * 0.5))
    assert ("frozen", True) not in transitions


def test_short_dark_or_static_period_does_not_raise_active_event():
    dark_monitor = CameraHealthMonitor()
    dark_transitions = []
    for step in range(11):
        dark_transitions.extend(dark_monitor.observe(solid_frame(0), now=step * 0.5))
    dark_transitions.extend(dark_monitor.observe(solid_frame(100), now=5.5))
    assert ("blocked", True) not in dark_transitions

    still_monitor = CameraHealthMonitor()
    still_transitions = []
    for step in range(11):
        still_transitions.extend(still_monitor.observe(solid_frame(100), now=step * 0.5))
    still_transitions.extend(still_monitor.observe(solid_frame(180), now=5.5))
    assert ("frozen", True) not in still_transitions


def test_white_cloth_or_hand_like_cover_warns_within_ten_seconds():
    for covered in (covered_frame(245, 1), covered_frame(150, 2)):
        monitor = CameraHealthMonitor()
        transitions = monitor.observe(detailed_frame(), now=0.0)
        for step in range(1, 9):
            transitions.extend(monitor.observe(covered, now=step * 0.5))

        assert ("occluded", True) in transitions
        assert "occluded" in monitor.active_events

        transitions.extend(monitor.observe(detailed_frame(), now=5.0))
        assert ("occluded", False) in transitions
        assert "occluded" not in monitor.active_events


def test_brief_scene_cover_does_not_raise_active_warning():
    monitor = CameraHealthMonitor()
    transitions = monitor.observe(detailed_frame(), now=0.0)
    for step in range(1, 5):
        transitions.extend(monitor.observe(covered_frame(245, 3), now=step * 0.5))
    transitions.extend(monitor.observe(detailed_frame(), now=2.5))
    assert ("occluded", True) not in transitions


def test_unreadable_frame_is_one_event_and_recovery_closes_it():
    monitor = CameraHealthMonitor()
    assert monitor.frame_unavailable() == [("read_failure", True)]
    assert monitor.frame_unavailable() == []
    assert monitor.frame_recovered() == [("read_failure", False)]
    assert monitor.frame_recovered() == []


def test_database_camera_event_rows_are_transition_only(monkeypatch):
    statuses = []

    def fake_run(query, params=(), *, getir=False):
        if query.startswith("SELECT durum"):
            camera_name, active_status, resolved_status = params
            matching = [
                status for name, status in statuses
                if name == camera_name and status in (active_status, resolved_status)
            ]
            return [(matching[-1],)] if matching else []
        if query.startswith("INSERT INTO giris_kayitlari"):
            statuses.append(params[:2])
            return None
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(veritabani, "calistir", fake_run)
    assert veritabani.record_camera_event_transition("Kamera 1", "blocked", True)
    assert not veritabani.record_camera_event_transition("Kamera 1", "blocked", True)
    assert veritabani.record_camera_event_transition("Kamera 1", "blocked", False)
    assert not veritabani.record_camera_event_transition("Kamera 1", "blocked", False)
    assert statuses == [
        ("Kamera 1", "CAMERA_BLK_ACTIVE"),
        ("Kamera 1", "CAMERA_BLK_RESOLVED"),
    ]
    assert all(len(status) <= 20 for _, status in statuses)


def test_camera_event_type_and_name_are_validated():
    with pytest.raises(ValueError):
        veritabani.record_camera_event_transition("Kamera 1", "arbitrary", True)
    with pytest.raises(ValueError):
        veritabani.record_camera_event_transition("", "blocked", True)


def test_camera_access_history_lists_each_daily_outage_with_duration():
    today = date(2026, 11, 13)
    rows = [
        ("Kamera 1", today, time(8, 0), "CAMERA_OCC_ACTIVE"),
        ("Kamera 1", today, time(8, 2, 30), "CAMERA_OCC_RESOLVED"),
        ("Kamera 1", today, time(11, 15), "CAMERA_READ_ACTIVE"),
        ("Kamera 1", today, time(11, 17), "CAMERA_READ_RESOLVED"),
    ]

    intervals = veritabani.camera_access_intervals(
        rows, today=today, now=datetime(2026, 11, 13, 12, 0)
    )

    assert len(intervals) == 2
    assert intervals[0]["event_type"] == "read_failure"
    assert intervals[0]["duration_seconds"] == 120
    assert intervals[0]["end"] == datetime(2026, 11, 13, 11, 17)
    assert intervals[1]["event_type"] == "occluded"
    assert intervals[1]["duration_seconds"] == 150
    assert not intervals[0]["ongoing"] and not intervals[1]["ongoing"]


def test_camera_access_history_keeps_prior_day_outage_visible_while_ongoing():
    today = date(2026, 11, 13)
    rows = [
        ("Kamera 1", date(2026, 11, 12), time(23, 59), "CAMERA_READ_ACTIVE"),
        ("Kamera 1", today, time(0, 5), "CAMERA_READ_RESOLVED"),
        ("Kamera 2", today, time(9, 0), "CAMERA_BLK_ACTIVE"),
    ]

    intervals = veritabani.camera_access_intervals(
        rows, today=today, now=datetime(2026, 11, 13, 9, 3)
    )

    assert len(intervals) == 1
    assert intervals[0]["camera_name"] == "Kamera 2"
    assert intervals[0]["end"] is None
    assert intervals[0]["duration_seconds"] == 180
    assert intervals[0]["ongoing"]


def test_camera_event_persistence_is_queued_off_the_camera_thread(monkeypatch):
    persisted = []
    finished = threading.Event()

    def fake_record(camera_name, event_type, active):
        persisted.append((camera_name, event_type, active))
        finished.set()
        return True

    monkeypatch.setattr(veritabani, "record_camera_event_transition", fake_record)
    veritabani.enqueue_camera_event_transition("Kamera 1", "read_failure", True)
    assert finished.wait(timeout=2)
    assert persisted == [("Kamera 1", "read_failure", True)]


def test_camera_health_thresholds_are_configurable():
    assert config.CAMERA_DARK_DURATION_SECONDS > config.CAMERA_HEALTH_SAMPLE_INTERVAL_SECONDS
    assert config.CAMERA_FROZEN_DURATION_SECONDS <= 10
    assert config.CAMERA_OCCLUSION_DURATION_SECONDS < config.CAMERA_DARK_DURATION_SECONDS
