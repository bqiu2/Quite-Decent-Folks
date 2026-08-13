"""Camera ownership for level one, separate from landmark classification."""

from __future__ import annotations

from collections import deque
import sys
import threading
import time

import cv2

from .pose_control import GestureAction, PoseController


# Keep this above common 30 FPS camera delivery rates so small timing jitter
# does not accidentally reduce pose inference to every other frame.
POSE_PROCESS_INTERVAL = 1.0 / 45.0
ACTION_DISPLAY_DURATION = 0.8


def camera_backends() -> list[tuple[str, int]]:
    if sys.platform.startswith("win"):
        return [
            ("DirectShow", cv2.CAP_DSHOW),
            ("Media Foundation", cv2.CAP_MSMF),
            ("Default", cv2.CAP_ANY),
        ]
    return [("Default", cv2.CAP_ANY)]


class CameraPoseInput:
    """Open a camera, produce pose actions, and retain the latest preview frame."""

    def __init__(self, capture, camera_index: int, backend_name: str) -> None:
        self.capture = capture
        self.camera_index = camera_index
        self.backend_name = backend_name
        self.controller = PoseController()
        self.latest_frame = None
        self.last_error: str | None = None
        self._last_process_time = -1.0
        self._frame_sequence = 0
        self._last_processed_sequence = -1
        self._frame_lock = threading.Lock()
        self._stop_capture = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._pose_thread: threading.Thread | None = None
        self._action_lock = threading.Lock()
        self._pending_actions: deque[GestureAction] = deque(maxlen=4)
        self._displayed_action: GestureAction = "none"
        self._display_action_until = 0.0

    @classmethod
    def open_first(cls, max_index: int = 4) -> CameraPoseInput | None:
        for index in range(max_index):
            for backend_name, backend in camera_backends():
                capture = cv2.VideoCapture(index, backend)
                if capture.isOpened():
                    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        camera_input = cls(capture, index, backend_name)
                        camera_input.latest_frame = frame
                        camera_input._frame_sequence = 1
                        camera_input._start_workers()
                        return camera_input
                capture.release()
        return None

    @property
    def displayed_action(self) -> GestureAction:
        with self._action_lock:
            if time.monotonic() >= self._display_action_until:
                return "none"
            return self._displayed_action

    @property
    def label(self) -> str:
        return f"CAM {self.camera_index} / {self.backend_name}"

    def read_action(self) -> GestureAction:
        """Return a queued pose event without blocking the game loop."""
        with self._action_lock:
            if not self._pending_actions:
                return "none"
            return self._pending_actions.popleft()

    def _start_workers(self) -> None:
        self._capture_thread = threading.Thread(
            target=self._capture_latest_frames,
            name=f"level1-camera-{self.camera_index}",
            daemon=True,
        )
        self._capture_thread.start()
        self._pose_thread = threading.Thread(
            target=self._process_latest_frames,
            name=f"level1-pose-{self.camera_index}",
            daemon=True,
        )
        self._pose_thread.start()

    def _capture_latest_frames(self) -> None:
        while not self._stop_capture.is_set():
            ok, frame = self.capture.read()
            if not ok or frame is None:
                self.last_error = "Camera stopped returning frames"
                return
            with self._frame_lock:
                self.latest_frame = frame
                self._frame_sequence += 1

    def _process_latest_frames(self) -> None:
        while not self._stop_capture.is_set():
            with self._frame_lock:
                frame = self.latest_frame
                frame_sequence = self._frame_sequence

            now = time.monotonic()
            no_new_frame = (
                frame is None or frame_sequence == self._last_processed_sequence
            )
            rate_limited = (
                self._last_process_time >= 0.0
                and now - self._last_process_time < POSE_PROCESS_INTERVAL
            )
            if no_new_frame or rate_limited:
                self._stop_capture.wait(0.002)
                continue

            self._last_process_time = now
            self._last_processed_sequence = frame_sequence
            action = self.controller.get_gesture(frame)
            if action == "none":
                continue
            with self._action_lock:
                self._pending_actions.append(action)
                self._displayed_action = action
                self._display_action_until = now + ACTION_DISPLAY_DURATION

    def close(self) -> None:
        self._stop_capture.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=0.5)
        self.capture.release()
        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=0.5)
        if self._pose_thread is not None:
            self._pose_thread.join(timeout=1.0)
        self.controller.close()
