"""Player-controlled plant and lane movement logic."""

import pygame

from .config import LANE_COUNT, PLANT_SIZE, PLANT_X, lane_center_y


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

        pot = pygame.Rect(0, 0, 36, 26)
        pot.midbottom = (PLANT_SIZE // 2, PLANT_SIZE)
        pygame.draw.rect(surface, (140, 82, 48), pot)
        pygame.draw.rect(surface, (91, 54, 38), pot, 4)
        pygame.draw.line(surface, (201, 126, 69), (pot.left + 5, pot.top + 6), (pot.right - 5, pot.top + 6), 3)

        if self.plant_type == "grass":
            for offset, height in ((-17, 28), (-9, 36), (0, 43), (9, 35), (17, 27)):
                start = (PLANT_SIZE // 2 + offset, pot.top + 3)
                end = (PLANT_SIZE // 2 + offset // 2, pot.top + 3 - height)
                pygame.draw.line(surface, (54, 150, 68), start, end, 7)
                pygame.draw.line(surface, (116, 203, 91), start, end, 2)
            return

        if self.plant_type == "shrub":
            for center, radius in (((22, 30), 15), ((45, 30), 16), ((34, 18), 18)):
                pygame.draw.circle(surface, (46, 124, 64), center, radius)
                pygame.draw.circle(surface, (91, 173, 78), (center[0] - 4, center[1] - 4), max(4, radius // 3))
            return

        # Flower art.
        pygame.draw.ellipse(surface, (58, 139, 70), (8, 29, 29, 17))
        pygame.draw.ellipse(surface, (42, 111, 61), (33, 31, 29, 17))
        stem_start = (PLANT_SIZE // 2, pot.top)
        stem_end = (PLANT_SIZE // 2, 20)
        pygame.draw.line(surface, (48, 116, 55), stem_start, stem_end, 8)

        flower_center = (PLANT_SIZE // 2, 18)
        petal_color = (247, 191, 80)
        for offset_x, offset_y in ((0, -12), (12, 0), (0, 12), (-12, 0)):
            pygame.draw.circle(
                surface,
                petal_color,
                (flower_center[0] + offset_x, flower_center[1] + offset_y),
                10,
            )
        pygame.draw.circle(surface, (111, 71, 42), flower_center, 9)
        pygame.draw.circle(surface, (255, 226, 116), (flower_center[0] - 3, flower_center[1] - 3), 3)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the plant at its current lane position."""
        shadow = pygame.Rect(0, 0, 54, 14)
        shadow.center = (self.rect.centerx, self.rect.bottom - 2)
        pygame.draw.ellipse(surface, (43, 73, 49), shadow)
        surface.blit(self.image, self.rect)
