"""Player-controlled plant and lane movement logic."""

import pygame

from .config import LANE_COUNT, PLANT_SIZE, PLANT_X, lane_center_y
from ui.pixel_style import draw_pixel_plant


class PlantPlayer(pygame.sprite.Sprite):
    """A flower defender that glides between five rail stops."""

    def __init__(self, plant_type: str = "flower") -> None:
        super().__init__()
        self.plant_type = plant_type
        self.lane_index = LANE_COUNT // 2
        self.image = pygame.Surface((PLANT_SIZE, PLANT_SIZE), pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.center = (PLANT_X, lane_center_y(self.lane_index))
        self.target_y = float(self.rect.centery)
        self._render_image()

    def move_up(self) -> None:
        """Move the plant up by one lane."""
        self.move_to_lane(self.lane_index - 1)

    def move_down(self) -> None:
        """Move the plant down by one lane."""
        self.move_to_lane(self.lane_index + 1)

    def move_to_lane(self, lane_index: int) -> None:
        """Select a lane, clamping camera or keyboard input to valid stops."""
        self.lane_index = max(0, min(LANE_COUNT - 1, lane_index))
        self.target_y = float(lane_center_y(self.lane_index))

    def update(self, dt: float) -> None:
        """Animate the pot along the rail instead of teleporting between lanes."""
        distance = self.target_y - self.rect.centery
        maximum_step = 720.0 * dt
        if abs(distance) <= maximum_step:
            self.rect.centery = round(self.target_y)
        elif distance > 0:
            self.rect.centery += round(maximum_step)
        else:
            self.rect.centery -= round(maximum_step)

    def _render_image(self) -> None:
        """Create an original code-drawn sprite for the detected plant type."""
        surface = self.image
        surface.fill((0, 0, 0, 0))
        draw_pixel_plant(surface, (PLANT_SIZE // 2, 43), self.plant_type, scale=1)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the plant at its current lane position."""
        shadow = pygame.Rect(0, 0, 54, 10)
        shadow.center = (self.rect.centerx, self.rect.bottom - 2)
        pygame.draw.rect(surface, (43, 73, 49), shadow)
        pygame.draw.rect(surface, (66, 105, 62), shadow.inflate(-12, -5))
        surface.blit(self.image, self.rect)
