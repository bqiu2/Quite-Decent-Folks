"""Turn MediaPipe index-finger directions into rail movement actions."""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any

from shared_game_data import HandAction


class HandController:
    """Recognize an index finger pointing up or down from webcam frames.

    MediaPipe's LIVE_STREAM callback keeps inference outside the Pygame event
    loop.  A gesture must remain stable for several results, and each held
    gesture fires only once so the plant cannot accidentally skip many lanes.
    """

    STABLE_RESULT_COUNT = 3
    VERTICAL_DOMINANCE = 1.2
    MIN_VERTICAL_PALM_RATIO = 0.35

    def __init__(self, model_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.model_path = model_path or project_root / "assets" / "models" / "hand_landmarker.task"
        self.enabled = False
        self.status = "model missing" if not self.model_path.exists() else "ready"

        self._capture: Any = None
        self._landmarker: Any = None
        self._mp: Any = None
        self._cv2: Any = None
        self._lock = threading.Lock()
        self._hand_detected = False
        self._gesture: HandAction = "none"
        self._candidate_gesture: HandAction = "none"
        self._candidate_count = 0
        self._latched_gesture: HandAction = "none"
        self._pending_action: HandAction = "none"
        self._last_timestamp_ms = 0

    @property
    def hand_detected(self) -> bool:
        """Whether the newest completed MediaPipe result contains a hand."""
        with self._lock:
            return self._hand_detected

    @property
    def gesture(self) -> HandAction:
        """The newest stable index-finger direction for HUD feedback."""
        with self._lock:
            return self._gesture

    def start(self) -> bool:
        """Open the webcam and construct the live-stream hand landmarker."""
        if self.enabled:
            return True
        if not self.model_path.exists():
            self.status = "model missing"
            return False

        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(self.model_path)),
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6,
                result_callback=self._receive_result,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)

            self._capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self._capture.isOpened():
                self._capture.release()
                self._capture = cv2.VideoCapture(0)
            if not self._capture.isOpened():
                self._landmarker.close()
                self._landmarker = None
                self.status = "camera unavailable"
                return False

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cv2 = cv2
            self._mp = mp
            self.enabled = True
            self.status = "active"
            self._reset_tracking()
            return True
        except Exception as exc:
            self.status = f"error: {exc}"
            self.close()
            return False

    def poll_action(self) -> HandAction:
        """Submit one frame and consume a newly recognized one-step action."""
        if not self.enabled:
            return "none"

        ok, frame = self._capture.read()
        if not ok:
            self.status = "camera frame failed"
            return "none"

        rgb_frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = max(round(time.monotonic() * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        self._landmarker.detect_async(image, timestamp_ms)

        return self._consume_pending_action()

    def _consume_pending_action(self) -> HandAction:
        with self._lock:
            action = self._pending_action
            self._pending_action = "none"
        return action

    def close(self) -> None:
        """Release the camera and MediaPipe task."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self.enabled = False
        self._reset_tracking()
        if self.status == "active":
            self.status = "ready"

    def _reset_tracking(self) -> None:
        with self._lock:
            self._hand_detected = False
            self._gesture = "none"
            self._candidate_gesture = "none"
            self._candidate_count = 0
            self._latched_gesture = "none"
            self._pending_action = "none"

    def _receive_result(self, result: Any, _output_image: Any, _timestamp_ms: int) -> None:
        self._process_landmarks(result.hand_landmarks)

    def _process_landmarks(self, hand_landmarks: Any) -> None:
        if not hand_landmarks:
            with self._lock:
                self._hand_detected = False
                self._gesture = "none"
                self._candidate_gesture = "none"
                self._candidate_count = 0
                self._latched_gesture = "none"
            return

        direction = self._classify_index_direction(hand_landmarks[0])
        with self._lock:
            self._hand_detected = True
            if direction == self._candidate_gesture:
                self._candidate_count += 1
            else:
                self._candidate_gesture = direction
                self._candidate_count = 1

            if self._candidate_count < self.STABLE_RESULT_COUNT:
                return

            self._gesture = direction
            if direction == "none":
                self._latched_gesture = "none"
            elif direction != self._latched_gesture:
                self._pending_action = direction
                self._latched_gesture = direction

    def _classify_index_direction(self, landmarks: Any) -> HandAction:
        """Classify a clearly extended index finger as vertical up or down."""
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        index_pip = landmarks[6]
        index_tip = landmarks[8]

        palm_size = self._distance(wrist, middle_mcp)
        if palm_size <= 0:
            return "none"

        # The index fingertip must be farther from the wrist than its PIP joint.
        index_extended = self._distance(wrist, index_tip) > self._distance(wrist, index_pip) * 1.1
        if not index_extended:
            return "none"

        # Reject an open palm: middle, ring and little fingers should be folded.
        for pip_index, tip_index in ((10, 12), (14, 16), (18, 20)):
            if self._distance(wrist, landmarks[tip_index]) > self._distance(wrist, landmarks[pip_index]) * 1.08:
                return "none"

        delta_x = index_tip.x - index_pip.x
        delta_y = index_tip.y - index_pip.y
        if abs(delta_y) < palm_size * self.MIN_VERTICAL_PALM_RATIO:
            return "none"
        if abs(delta_y) < abs(delta_x) * self.VERTICAL_DOMINANCE:
            return "none"
        return "up" if delta_y < 0 else "down"

    @staticmethod
    def _distance(first: Any, second: Any) -> float:
        return math.hypot(second.x - first.x, second.y - first.y)


_frame_controller: HandController | None = None
_frame_landmarker: Any = None
_frame_recognizer_lock = threading.Lock()


def get_hand_action(frame: Any) -> HandAction:
    """Recognize one BGR camera frame using the team's agreed function API.

    Level 2 normally uses ``HandController`` directly because it owns the
    webcam.  This wrapper is provided for a future shared camera loop.
    """
    global _frame_controller, _frame_landmarker

    if frame is None:
        return "none"

    with _frame_recognizer_lock:
        if _frame_controller is None:
            _frame_controller = HandController()
        if not _frame_controller.model_path.exists():
            return "none"

        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        if _frame_landmarker is None:
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(
                    model_asset_path=str(_frame_controller.model_path)
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            _frame_landmarker = vision.HandLandmarker.create_from_options(options)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = _frame_landmarker.detect(image)
        _frame_controller._process_landmarks(result.hand_landmarks)
        return _frame_controller._consume_pending_action()
