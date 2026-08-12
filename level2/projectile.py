"""Grass, shrub, and flower attack projectile logic."""

import pygame

from .config import PROJECTILE_COLOR, PROJECTILE_DAMAGE, PROJECTILE_SPEED, WINDOW_WIDTH


class Projectile(pygame.sprite.Sprite):
    """A code-drawn attack that supports damage and penetration settings."""

    def __init__(
        self,
        start_position: tuple[int, int],
        lane_index: int,
        damage: float = PROJECTILE_DAMAGE,
        speed: float = PROJECTILE_SPEED,
        penetration: int = 1,
        attack_name: str = "petal_shot",
    ) -> None:
        super().__init__()
        self.lane_index = lane_index
        self.damage = damage
        self.speed = speed
        self.penetration_remaining = max(1, penetration)
        self.hit_zombie_ids: set[int] = set()
        self.precise_x = float(start_position[0])
        self.image = pygame.Surface((32, 16), pygame.SRCALPHA)
        self._render_attack(attack_name)
        self.rect = self.image.get_rect(midleft=start_position)

    def update(self, dt: float) -> None:
        self.precise_x += self.speed * dt
        self.rect.x = round(self.precise_x)
        if self.rect.left > WINDOW_WIDTH:
            self.kill()

    def can_hit(self, zombie: pygame.sprite.Sprite) -> bool:
        return (
            self.penetration_remaining > 0
            and id(zombie) not in self.hit_zombie_ids
        )

    def register_hit(self, zombie: pygame.sprite.Sprite) -> None:
        self.hit_zombie_ids.add(id(zombie))
        self.penetration_remaining -= 1
        if self.penetration_remaining <= 0:
            self.kill()

    def _render_attack(self, attack_name: str) -> None:
        if attack_name == "sword_wave":
            pygame.draw.polygon(
                self.image,
                (55, 113, 117),
                ((0, 9), (18, 0), (31, 8), (18, 16)),
            )
            pygame.draw.polygon(self.image, (174, 241, 226), ((4, 8), (19, 3), (27, 8), (18, 13)))
            pygame.draw.rect(self.image, (245, 255, 250), (8, 7, 17, 3))
        elif attack_name == "earthquake":
            pygame.draw.polygon(self.image, (88, 65, 52), ((0, 11), (5, 5), (10, 10), (16, 2), (22, 10), (28, 4), (32, 11), (32, 15), (0, 15)))
            pygame.draw.polygon(self.image, (157, 111, 71), ((2, 10), (7, 7), (11, 11), (16, 5), (22, 11), (27, 7), (30, 11), (30, 13), (2, 13)))
            pygame.draw.rect(self.image, (234, 194, 112), (5, 9, 22, 3))
        else:
            pygame.draw.polygon(
                self.image,
                PROJECTILE_COLOR,
                ((0, 8), (12, 1), (31, 8), (12, 15)),
            )
            pygame.draw.rect(self.image, (255, 244, 171), (9, 5, 15, 6))
