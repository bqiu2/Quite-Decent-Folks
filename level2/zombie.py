"""Zombie entities and movement behaviour."""

import pygame

from .config import (
    ZOMBIE_HEALTH,
    ZOMBIE_SIZE,
    ZOMBIE_SPAWN_X,
    ZOMBIE_SPEED,
    lane_center_y,
)


class Zombie(pygame.sprite.Sprite):
    """A friendly-looking pixel zombie that walks toward the house."""

    def __init__(
        self,
        lane_index: int,
        speed_multiplier: float = 1.0,
        health_multiplier: float = 1.0,
    ) -> None:
        super().__init__()
        self.lane_index = lane_index
        self.max_health = ZOMBIE_HEALTH * health_multiplier
        self.health = self.max_health
        self.speed = ZOMBIE_SPEED * speed_multiplier
        self.precise_x = float(ZOMBIE_SPAWN_X)
        self.image = self._build_image()
        self.rect = self.image.get_rect(
            midbottom=(ZOMBIE_SPAWN_X, lane_center_y(lane_index) + 38)
        )

    def update(self, dt: float) -> None:
        self.precise_x -= self.speed * dt
        self.rect.centerx = round(self.precise_x)

    def take_damage(self, damage: float) -> bool:
        """Apply damage and return True when this hit defeats the zombie."""
        self.health -= damage
        if self.health <= 0:
            self.kill()
            return True
        return False

    def draw_health_bar(self, surface: pygame.Surface) -> None:
        width = self.rect.width
        ratio = max(0.0, self.health / self.max_health)
        background = pygame.Rect(self.rect.left, self.rect.top - 9, width, 6)
        foreground = pygame.Rect(self.rect.left, self.rect.top - 9, round(width * ratio), 6)
        pygame.draw.rect(surface, (69, 45, 43), background)
        pygame.draw.rect(surface, (214, 83, 66), foreground)

    @staticmethod
    def _build_image() -> pygame.Surface:
        """Draw an original non-scary pixel zombie without external assets."""
        width, height = ZOMBIE_SIZE
        image = pygame.Surface((width, height), pygame.SRCALPHA)

        # Watering can strapped to the back.
        pygame.draw.rect(image, (92, 130, 137), (46, 29, 20, 28))
        pygame.draw.rect(image, (48, 74, 77), (46, 29, 20, 28), 3)
        pygame.draw.line(image, (92, 130, 137), (65, 34), (71, 27), 5)

        # Legs, body, and patched gardening overalls.
        pygame.draw.rect(image, (74, 82, 58), (24, 63, 13, 20))
        pygame.draw.rect(image, (74, 82, 58), (43, 63, 13, 20))
        pygame.draw.rect(image, (101, 79, 63), (20, 39, 39, 31))
        pygame.draw.rect(image, (68, 91, 105), (23, 45, 33, 25))
        pygame.draw.rect(image, (182, 135, 68), (43, 54, 10, 8))

        # Arms point left toward the house.
        pygame.draw.rect(image, (124, 158, 103), (4, 42, 28, 11))
        pygame.draw.rect(image, (78, 111, 75), (4, 42, 28, 11), 3)

        # Oversized head and goofy face.
        pygame.draw.rect(image, (124, 158, 103), (15, 6, 43, 38))
        pygame.draw.rect(image, (78, 111, 75), (15, 6, 43, 38), 4)
        pygame.draw.rect(image, (240, 224, 161), (22, 17, 8, 8))
        pygame.draw.rect(image, (240, 224, 161), (43, 17, 8, 8))
        pygame.draw.rect(image, (42, 46, 39), (25, 20, 4, 4))
        pygame.draw.rect(image, (42, 46, 39), (43, 20, 4, 4))
        pygame.draw.rect(image, (67, 67, 53), (29, 32, 18, 4))

        return image
