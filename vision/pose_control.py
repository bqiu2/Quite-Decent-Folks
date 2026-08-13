"""MediaPipe Pose adapter for level-one jump and crouch actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Literal, Protocol, Sequence

from shared_game_data import PoseAction


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_DIR / "assets" / "models" / "pose_landmarker.task"

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_WRIST = 15
RIGHT_WRIST = 16
WRIST_SHOULDER_TOLERANCE = 0.03
MIN_VISIBILITY = 0.35
REQUIRED_CONSECUTIVE_FRAMES = 1
ACTION_COOLDOWN_SECONDS = 0.10

GestureAction = Literal["jump", "crouch", "none"]


class Landmark(Protocol):
    x: float
    y: float
    visibility: float


def classify_landmarks(landmarks: Sequence[Landmark]) -> GestureAction:
    """Classify one pose without applying temporal debouncing."""
    if len(landmarks) <= RIGHT_WRIST:
        return "none"

    left_shoulder = landmarks[LEFT_SHOULDER]
    right_shoulder = landmarks[RIGHT_SHOULDER]
    left_wrist = landmarks[LEFT_WRIST]
    right_wrist = landmarks[RIGHT_WRIST]

    left_visible = min(left_shoulder.visibility, left_wrist.visibility) >= MIN_VISIBILITY
    right_visible = min(right_shoulder.visibility, right_wrist.visibility) >= MIN_VISIBILITY
    left_raised = (
        left_visible
        and left_wrist.y < left_shoulder.y + WRIST_SHOULDER_TOLERANCE
    )
    right_raised = (
        right_visible
        and right_wrist.y < right_shoulder.y + WRIST_SHOULDER_TOLERANCE
    )

    if left_raised == right_raised:
        return "none"
    return "jump" if left_raised else "crouch"


@dataclass
class GestureDebouncer:
    candidate: GestureAction = "none"
    candidate_frames: int = 0
    latched: GestureAction = "none"
    last_emit_time: float = -1.0

    def update(self, raw_action: GestureAction, now: float) -> GestureAction:
        if raw_action == "none":
            self.candidate = "none"
            self.candidate_frames = 0
            self.latched = "none"
            return "none"

        if raw_action != self.candidate:
            self.candidate = raw_action
            self.candidate_frames = 1
        else:
            self.candidate_frames += 1

        cooled_down = (
            self.last_emit_time < 0.0
            or now - self.last_emit_time >= ACTION_COOLDOWN_SECONDS
        )
        if (
            self.candidate_frames >= REQUIRED_CONSECUTIVE_FRAMES
            and self.latched != raw_action
            and cooled_down
        ):
            self.latched = raw_action
            self.last_emit_time = now
            return raw_action
        return "none"


class PoseController:
    """Lazy MediaPipe Tasks controller; it never opens a camera itself."""

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = model_path
        self.debouncer = GestureDebouncer()
        self._landmarker = None
        self._last_timestamp_ms = 0

    @property
    def available(self) -> bool:
        return self.model_path.is_file()

    def _ensure_landmarker(self):
        if self._landmarker is not None:
            return self._landmarker
        if not self.available:
            return None

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.4,
            min_pose_presence_confidence=0.4,
            min_tracking_confidence=0.4,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def get_gesture(self, frame) -> GestureAction:
        landmarker = self._ensure_landmarker()
        if landmarker is None or frame is None:
            return "none"

        import cv2
        import mediapipe as mp

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = max(self._last_timestamp_ms + 1, int(time.monotonic() * 1000))
        self._last_timestamp_ms = timestamp_ms
        result = landmarker.detect_for_video(image, timestamp_ms)
        if not result.pose_landmarks:
            raw_action: GestureAction = "none"
        else:
            raw_action = classify_landmarks(result.pose_landmarks[0])
        return self.debouncer.update(raw_action, time.monotonic())

    def get_action(self, frame) -> PoseAction:
        """Return the three-value action required by the shared team contract."""
        return self.get_gesture(frame)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


_DEFAULT_CONTROLLER = PoseController()


def get_pose_action(frame) -> PoseAction:
    """Convert one OpenCV BGR frame to jump/crouch/none."""
    return _DEFAULT_CONTROLLER.get_action(frame)


def get_pose_gesture(frame) -> GestureAction:
    """Return the richer gesture name used internally by level one."""
    return _DEFAULT_CONTROLLER.get_gesture(frame)


def pose_model_available() -> bool:
    return _DEFAULT_CONTROLLER.available
