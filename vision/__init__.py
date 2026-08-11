"""Camera-frame to game-action adapters."""

from .camera_pose_input import CameraPoseInput
from .pose_control import get_pose_action, get_pose_gesture

__all__ = ["CameraPoseInput", "get_pose_action", "get_pose_gesture"]
