"""Camera-frame health checks without camera, database, or UI dependencies."""
import time

import cv2
import numpy as np

from . import config


class CameraHealthMonitor:
    """Detect sustained dark or nearly identical camera frames.

    Returns `(event_type, active)` transitions only. A stationary scene is
    treated as suspicious, not as proof of camera tampering.
    """

    _FRAME_SIZE = (64, 48)

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._last_sample_at = None
        self._previous_gray = None
        self._reference_gray = None
        self._condition_since = {}
        self._last_condition = {}
        self._active = set()
        self._read_state_known = False

    @property
    def active_events(self):
        return frozenset(self._active)

    def observe(self, frame, now=None):
        """Analyze a BGR frame and return state transitions, if any."""
        now = self._clock() if now is None else float(now)
        if (self._last_sample_at is not None
                and now - self._last_sample_at < config.CAMERA_HEALTH_SAMPLE_INTERVAL_SECONDS):
            return []
        self._last_sample_at = now

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, self._FRAME_SIZE, interpolation=cv2.INTER_AREA)
        mean_intensity = float(np.mean(gray))
        dark_pixel_ratio = float(np.mean(gray <= config.CAMERA_DARK_PIXEL_MAX))
        is_dark = (
            mean_intensity <= config.CAMERA_DARK_MEAN_MAX
            and dark_pixel_ratio >= config.CAMERA_DARK_PIXEL_RATIO_MIN
        )
        edges = cv2.Canny(gray, 40, 80)
        low_detail_ratio = self._low_detail_tile_ratio(gray, edges)
        low_detail = low_detail_ratio >= config.CAMERA_OCCLUSION_LOW_DETAIL_RATIO_MIN

        is_occluded = False
        if self._reference_gray is not None and low_detail and not is_dark:
            reference_delta = np.abs(gray.astype(np.int16) - self._reference_gray.astype(np.int16))
            reference_changed_ratio = float(np.mean(reference_delta > 8))
            is_occluded = (
                float(np.mean(reference_delta)) >= config.CAMERA_OCCLUSION_CHANGE_MEAN_MIN
                and reference_changed_ratio >= config.CAMERA_OCCLUSION_CHANGED_RATIO_MIN
            )

        transitions = []
        self._update_condition(
            "blocked", is_dark, config.CAMERA_DARK_DURATION_SECONDS, now, transitions
        )
        self._update_condition(
            "occluded", is_occluded, config.CAMERA_OCCLUSION_DURATION_SECONDS,
            now, transitions,
        )

        if self._previous_gray is not None:
            delta = np.abs(gray.astype(np.int16) - self._previous_gray.astype(np.int16))
            mean_delta = float(np.mean(delta))
            changed_pixel_ratio = float(np.mean(delta > config.CAMERA_FROZEN_CHANGED_PIXEL_THRESHOLD))
            is_frozen = (
                not is_dark
                and mean_delta <= config.CAMERA_FROZEN_MEAN_DIFF_MAX
                and changed_pixel_ratio <= config.CAMERA_FROZEN_CHANGED_RATIO_MAX
            )
            self._update_condition(
                "frozen", is_frozen, config.CAMERA_FROZEN_DURATION_SECONDS,
                now, transitions,
            )

        self._previous_gray = gray
        if self._reference_gray is None or not low_detail:
            self._reference_gray = gray.copy()
        return transitions

    @staticmethod
    def _low_detail_tile_ratio(gray, edges):
        low_detail_tiles = 0
        tile_count = 0
        gray_rows = np.array_split(gray, 4, axis=0)
        edge_rows = np.array_split(edges, 4, axis=0)
        for gray_row, edge_row in zip(gray_rows, edge_rows):
            gray_tiles = np.array_split(gray_row, 4, axis=1)
            edge_tiles = np.array_split(edge_row, 4, axis=1)
            for tile, edge_tile in zip(gray_tiles, edge_tiles):
                tile_count += 1
                if (float(np.std(tile)) <= config.CAMERA_OCCLUSION_TILE_STD_MAX
                        and float(np.mean(edge_tile > 0))
                        <= config.CAMERA_OCCLUSION_TILE_EDGE_RATIO_MAX):
                    low_detail_tiles += 1
        return low_detail_tiles / tile_count if tile_count else 0.0

    def frame_unavailable(self):
        """Mark an unreadable frame as an active camera event once."""
        self._read_state_known = True
        if "read_failure" in self._active:
            return []
        self._active.add("read_failure")
        return [("read_failure", True)]

    def frame_recovered(self):
        """Close a prior read failure when a new frame is available."""
        if self._read_state_known and "read_failure" not in self._active:
            return []
        self._read_state_known = True
        self._active.discard("read_failure")
        return [("read_failure", False)]

    def _update_condition(self, event_type, condition, duration, now, transitions):
        previous = self._last_condition.get(event_type)
        self._last_condition[event_type] = condition

        if condition:
            if previous is not True:
                self._condition_since[event_type] = now
            started_at = self._condition_since.get(event_type, now)
            if now - started_at >= duration and event_type not in self._active:
                self._active.add(event_type)
                transitions.append((event_type, True))
            return

        self._condition_since.pop(event_type, None)
        if event_type in self._active:
            self._active.remove(event_type)
            transitions.append((event_type, False))
        elif previous is None or previous is True:
            # One initial/changed-to-normal transition reconciles a prior run.
            transitions.append((event_type, False))
