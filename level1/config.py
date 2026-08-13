"""Configuration shared by the level-one modules."""

from __future__ import annotations

from shared_game_data import LEVEL1_MAX_HP, LEVEL1_TIME_LIMIT


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
TARGET_FPS = 60

PLAYER_X = 130
PLAYER_WIDTH = 42
PLAYER_HEIGHT = 78
PLAYER_CROUCH_HEIGHT = 42

LOWER_FLOOR_Y = 520
FLOOR_HEIGHT = 18
SLIDE_OBSTACLE_TOP = 250
SLIDE_OBSTACLE_BOTTOM = LOWER_FLOOR_Y - PLAYER_CROUCH_HEIGHT - 4
SLIDE_OBSTACLE_HEIGHT = SLIDE_OBSTACLE_BOTTOM - SLIDE_OBSTACLE_TOP

GRAVITY = 1900.0
JUMP_SPEED = -740.0
MAX_FALL_SPEED = 1250.0

SLIDE_DURATION = 0.72
INVINCIBILITY_DURATION = 0.25

INITIAL_SCROLL_SPEED = 240.0
FINAL_SCROLL_SPEED = 480.0

INITIAL_OBSTACLE_INTERVAL = 2.10
INITIAL_OBSTACLE_JITTER = 0.30
MIN_OBSTACLE_INTERVAL = 0.90
MIN_OBSTACLE_JITTER = 0.15
INITIAL_OBSTACLE_CLUSTER_CHANCE = 0.18
FINAL_OBSTACLE_CLUSTER_CHANCE = 0.30
OBSTACLE_CLUSTER_GAP = 430.0
OBSTACLE_MIN_CLEARANCE = 360.0

ITEM_PAIR_INTERVAL = 2.4
ITEM_WEIGHT_DECAY = 0.75
ITEM_MIN_PROBABILITY = 0.05
ITEM_LOW_CENTER_Y = 486
ITEM_HIGH_CENTER_Y = 360
ITEM_SIZE = 42
ITEM_OBSTACLE_CLEARANCE = 360.0

# Collectibles can appear on the ground, on a low ledge, or high in the air.
# The old high/low constants remain available for compatibility with tests and
# scripted callers; the live game enables the randomized layout.
RANDOM_ITEM_Y = (332, 382, 438, 486)
RANDOM_ITEM_X_OFFSET = 24
# Air-route pickups sit above the running lane.  Both heights are reachable
# with a jump, while remaining clearly separated from the ground pickup.
AIR_ITEM_CENTER_Y = (332, 382)
PLATFORM_ITEM_CHANCE = 0.62
PLATFORM_ITEM_LOOKAHEAD = 180
ITEM_COLLECT_ANIMATION_DURATION = 0.38

# Floating ledges add a second traversal layer without changing the floor
# collision contract used by the existing runner.
AIR_PLATFORM_Y = (330, 382, 432, 462)
AIR_PLATFORM_WIDTHS = (94, 118, 142)
AIR_PLATFORM_MIN_GAP = 115

AUDIO_SAMPLE_RATE = 44100
SOUND_EFFECT_VOLUME = 0.48
MUSIC_VOLUME = 0.18

CAMERA_PREVIEW_WIDTH = 160
CAMERA_PREVIEW_HEIGHT = 120
CAMERA_PREVIEW_MARGIN = 12

MAX_HP = LEVEL1_MAX_HP
TIME_LIMIT = LEVEL1_TIME_LIMIT


def progress_at(elapsed: float) -> float:
    """Return level progress clamped to 0..1."""
    return max(0.0, min(1.0, elapsed / TIME_LIMIT))


def scroll_speed_at(elapsed: float) -> float:
    """Linearly accelerate from 240 px/s to 480 px/s over the level."""
    progress = progress_at(elapsed)
    return INITIAL_SCROLL_SPEED + (
        FINAL_SCROLL_SPEED - INITIAL_SCROLL_SPEED
    ) * progress


def obstacle_interval_at(elapsed: float) -> tuple[float, float]:
    """Return the current base interval and symmetric random jitter."""
    progress = progress_at(elapsed)
    interval = INITIAL_OBSTACLE_INTERVAL + (
        MIN_OBSTACLE_INTERVAL - INITIAL_OBSTACLE_INTERVAL
    ) * progress
    jitter = INITIAL_OBSTACLE_JITTER + (
        MIN_OBSTACLE_JITTER - INITIAL_OBSTACLE_JITTER
    ) * progress
    return interval, jitter


def obstacle_cluster_chance_at(elapsed: float) -> float:
    """Ramp close obstacle pairs in after the easier opening section."""
    progress = progress_at(elapsed)
    return INITIAL_OBSTACLE_CLUSTER_CHANCE + (
        FINAL_OBSTACLE_CLUSTER_CHANCE - INITIAL_OBSTACLE_CLUSTER_CHANCE
    ) * progress
