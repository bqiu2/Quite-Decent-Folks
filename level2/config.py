"""Configuration values for the second level."""

from shared_game_data import LEVEL2_LANE_COUNT

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

LANE_COUNT = LEVEL2_LANE_COUNT
BATTLEFIELD_TOP = 100
BATTLEFIELD_BOTTOM = 680
# The HUD is intentionally compact, while the illustrated farm starts lower
# so the first lane sits on grass instead of crossing the background fence.
LANE_TOP = 200
LANE_HEIGHT = (BATTLEFIELD_BOTTOM - LANE_TOP) // LANE_COUNT

HOUSE_WIDTH = 270
# The field edge recedes toward the upper-right in the illustrated farm.  The
# lift therefore starts farther right in the distance and leans left toward
# the viewer at the bottom of the field.
PLANT_X = 338
PLANT_X_BOTTOM = 292
PLANT_SIZE = 68
# The source illustration has a foreground fence across the lower edge.  The
# game redraws this strip after the lift so the lift reads as being behind it.
FOREGROUND_FENCE_TOP = 644
FOREGROUND_FENCE_WIDTH = HOUSE_WIDTH + 220

PROJECTILE_SPEED = 620.0
PROJECTILE_DAMAGE = 20.0
ATTACK_COOLDOWN = 0.55

ZOMBIE_SIZE = (72, 84)
ZOMBIE_SPEED = 46.0
ZOMBIE_HEALTH = 60.0
ZOMBIE_SPAWN_X = WINDOW_WIDTH + 45
ZOMBIE_GOAL_X = HOUSE_WIDTH - 5

WAVE_COUNTS = (6, 10)
SPAWN_INTERVAL = 0.9
WAVE_INTERMISSION = 2.5

BACKGROUND_COLOR = (39, 84, 61)
LANE_COLORS = ((103, 159, 91), (92, 148, 82))
LANE_LINE_COLOR = (217, 224, 176)
HOUSE_COLOR = (197, 151, 92)
HOUSE_ROOF_COLOR = (118, 69, 55)
RAIL_COLOR = (81, 67, 54)
HUD_COLOR = (28, 52, 40)
TEXT_COLOR = (246, 241, 211)
PROJECTILE_COLOR = (250, 210, 72)


def lane_center_y(lane_index: int) -> int:
    """Return the vertical centre of a lane numbered from zero."""
    if not 0 <= lane_index < LANE_COUNT:
        raise ValueError(f"lane_index must be between 0 and {LANE_COUNT - 1}")

    return LANE_TOP + lane_index * LANE_HEIGHT + LANE_HEIGHT // 2


def lane_x(lane_index: int) -> int:
    """Return the plant-lift x position along the field's perspective edge."""
    if not 0 <= lane_index < LANE_COUNT:
        raise ValueError(f"lane_index must be between 0 and {LANE_COUNT - 1}")
    if LANE_COUNT == 1:
        return PLANT_X
    progress = lane_index / (LANE_COUNT - 1)
    return round(PLANT_X + (PLANT_X_BOTTOM - PLANT_X) * progress)
