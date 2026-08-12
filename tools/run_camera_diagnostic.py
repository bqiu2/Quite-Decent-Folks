"""Probe local cameras independently from the game and preview pose actions."""

from __future__ import annotations

import sys
import time

import cv2

from vision.pose_control import (
    DEFAULT_MODEL_PATH,
    MIN_VISIBILITY,
    REQUIRED_CONSECUTIVE_FRAMES,
    WRIST_SHOULDER_TOLERANCE,
    get_pose_gesture,
    pose_model_available,
)


def camera_backends() -> list[tuple[str, int]]:
    if sys.platform.startswith("win"):
        return [
            ("DirectShow", cv2.CAP_DSHOW),
            ("Media Foundation", cv2.CAP_MSMF),
            ("Default", cv2.CAP_ANY),
        ]
    return [("Default", cv2.CAP_ANY)]


def find_camera(max_index: int = 4):
    results: list[tuple[int, str, bool, bool]] = []
    for index in range(max_index):
        for backend_name, backend in camera_backends():
            capture = cv2.VideoCapture(index, backend)
            opened = capture.isOpened()
            read_ok = False
            if opened:
                for _ in range(8):
                    read_ok, _ = capture.read()
                    if read_ok:
                        break
            results.append((index, backend_name, opened, read_ok))
            if opened and read_ok:
                return capture, index, backend_name, results
            capture.release()
    return None, None, None, results


def main() -> int:
    print(f"OpenCV: {cv2.__version__}")
    print(f"Pose model: {DEFAULT_MODEL_PATH}")
    print(f"Pose model available: {pose_model_available()}")
    print(
        "Fast pose profile: "
        f"wrist_tolerance={WRIST_SHOULDER_TOLERANCE}, "
        f"visibility={MIN_VISIBILITY}, "
        f"confirm_frames={REQUIRED_CONSECUTIVE_FRAMES}"
    )
    print("Probing camera indexes 0-3 ...")

    capture, index, backend_name, results = find_camera()
    for camera_index, backend, opened, read_ok in results:
        print(
            f"  index={camera_index} backend={backend:<16} "
            f"opened={opened} read={read_ok}"
        )

    if capture is None:
        print("\nNo readable camera was found.")
        print("Check the physical privacy shutter, Windows Camera app, Device Manager,")
        print("and close programs such as OBS, browsers, Teams, WeChat, or Zoom.")
        return 1

    print(f"\nUsing camera {index} through {backend_name}.")
    if not pose_model_available():
        print("Camera preview will work, but pose actions need pose_landmarker.task.")
    print("Press Q or Escape in the preview window to stop.")

    displayed_action = "none"
    display_action_until = 0.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Camera opened but stopped returning frames.")
                return 2
            action = get_pose_gesture(frame) if pose_model_available() else "none"
            if action != "none":
                displayed_action = action
                display_action_until = time.monotonic() + 0.8
                print(f"Pose action triggered: {action}")
            elif time.monotonic() >= display_action_until:
                displayed_action = "none"

            # Mirror only the preview so it behaves like a familiar camera view.
            frame = cv2.flip(frame, 1)
            cv2.putText(
                frame,
                f"Camera {index} / {backend_name}",
                (18, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (40, 230, 90),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"Pose action: {displayed_action}",
                (18, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (40, 230, 230),
                2,
                cv2.LINE_AA,
            )
            if not pose_model_available():
                cv2.putText(
                    frame,
                    "MODEL MISSING",
                    (18, 98),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.72,
                    (40, 40, 235),
                    2,
                    cv2.LINE_AA,
                )
            cv2.imshow("QDF Camera Diagnostic", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                return 0
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
