"""Animated pest entities for the second level.

The public ``Zombie`` name is retained as a compatibility alias for older
callers, but the game now spawns locusts, aphids, caterpillars, and
leafhoppers through the ``Pest`` class.
"""

from __future__ import annotations

from pathlib import Path
import random

import pygame

from .config import (
    BATTLEFIELD_TOP,
    LANE_COUNT,
    PEST_GOAL_X,
    PEST_SIZE,
    PEST_SPAWN_X,
    WINDOW_WIDTH,
    lane_center_y,
)


PEST_TYPES = ("locust", "aphid", "caterpillar", "leafhopper")
APHID_STAGES = ("adult", "egg", "nymph")


class Pest(pygame.sprite.Sprite):
    """A single animated pest with optional aphid lifecycle state."""

    def __init__(
        self,
        lane_index: int,
        pest_type: str = "caterpillar",
        *,
        speed_multiplier: float = 1.0,
        health_multiplier: float = 1.0,
        stage: str = "adult",
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self.lane_index = max(0, min(LANE_COUNT - 1, lane_index))
        self.pest_type = pest_type if pest_type in PEST_TYPES else "caterpillar"
        self.stage = stage if stage in APHID_STAGES else "adult"
        self.rng = rng or random.Random()
        self.speed_multiplier = speed_multiplier
        self._age = 0.0
        self._hop_timer = 0.0
        self._hop_offset = 0.0
        self._frame_time = 0.0
        self._frame = 0
        self.flying = self.pest_type == "locust"
        self.landed = not self.flying
        # Locusts appear over the field near the right edge and descend on a
        # fixed x coordinate.  Other pests enter from the horizontal spawn
        # point and are placed directly on their assigned row.
        self.precise_x = float(WINDOW_WIDTH - 118 if self.flying else PEST_SPAWN_X)
        self.precise_y = float(BATTLEFIELD_TOP + 18 if self.flying else lane_center_y(self.lane_index) - 8)
        self.max_health = self._base_health() * health_multiplier
        self.health = self.max_health
        self.speed = self._base_speed() * speed_multiplier
        self.image = pygame.Surface(PEST_SIZE, pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        if self.flying:
            self.rect.center = (round(self.precise_x), round(self.precise_y))
        else:
            self.rect.midbottom = (PEST_SPAWN_X, lane_center_y(self.lane_index))
        self._render()

    def _base_health(self) -> float:
        if self.pest_type == "locust":
            return 55.0
        if self.pest_type == "aphid":
            return {"adult": 28.0, "egg": 5.0, "nymph": 18.0}[self.stage]
        if self.pest_type == "leafhopper":
            return 10.0
        return 38.0

    def _base_speed(self) -> float:
        if self.pest_type == "locust":
            return 82.0 if self.flying else 58.0
        if self.pest_type == "aphid":
            return {"adult": 30.0, "egg": 0.0, "nymph": 54.0}[self.stage]
        if self.pest_type == "leafhopper":
            return 72.0
        return 34.0

    @property
    def is_aphid_adult(self) -> bool:
        return self.pest_type == "aphid" and self.stage == "adult"

    @property
    def is_aphid_egg(self) -> bool:
        return self.pest_type == "aphid" and self.stage == "egg"

    @property
    def is_aphid_nymph(self) -> bool:
        return self.pest_type == "aphid" and self.stage == "nymph"

    @property
    def can_be_hit_by_ground_attack(self) -> bool:
        return not self.flying

    @property
    def escaped(self) -> bool:
        return self.rect.left <= PEST_GOAL_X

    def update(self, dt: float) -> None:
        dt = max(0.0, dt)
        self._age += dt
        self._frame_time += dt
        if self._frame_time >= 0.075:
            self._frame_time = 0.0
            self._frame += 1

        if self.flying:
            # Locusts enter vertically from the upper-right.  Their x position
            # deliberately never changes during this phase: they are immune
            # to ground attacks until their feet reach the selected grass row.
            self.precise_y += 260.0 * dt
            target_y = lane_center_y(self.lane_index) - 8
            if self.precise_y >= target_y:
                self.precise_y = float(target_y)
                self.flying = False
                self.landed = True
                self.speed = 58.0 * self.speed_multiplier
            self.rect.center = (round(self.precise_x), round(self.precise_y))
            self._render()
            return

        if self.is_aphid_egg:
            # Eggs remain still while the manager checks their incubation age.
            self.rect.centerx = round(self.precise_x)
            self._render()
            return

        if self.pest_type == "leafhopper":
            self._hop_timer -= dt
            if self._hop_timer <= 0:
                self._hop_timer = 0.42
                self._hop_offset = -8.0
            self._hop_offset = min(0.0, self._hop_offset + 42.0 * dt)

        self.precise_x -= self.speed * dt
        self.rect.centerx = round(self.precise_x)
        self.rect.centery = round(lane_center_y(self.lane_index) - 8 + self._hop_offset)
        self._render()

    def take_damage(self, damage: float) -> bool:
        """Apply damage and return True when this pest is defeated."""
        self.health -= damage
        if self.health <= 0:
            self.kill()
            return True
        return False

    def should_hatch(self) -> bool:
        return self.is_aphid_egg and self._age >= 3.0

    def should_mature(self) -> bool:
        return self.is_aphid_nymph and self._age >= 8.0

    def draw_health_bar(self, surface: pygame.Surface) -> None:
        if self.is_aphid_egg:
            return
        width = max(24, self.rect.width - 12)
        ratio = max(0.0, self.health / self.max_health)
        background = pygame.Rect(self.rect.centerx - width // 2, self.rect.top - 9, width, 5)
        foreground = pygame.Rect(background.left, background.top, round(width * ratio), 5)
        pygame.draw.rect(surface, (35, 39, 34), background.move(2, 2))
        pygame.draw.rect(surface, (69, 45, 43), background)
        pygame.draw.rect(surface, (188, 77, 58), foreground)
        pygame.draw.rect(surface, (247, 148, 84), (foreground.left, foreground.top, foreground.width, 2))

    def _render(self) -> None:
        frame_count = 32 if self.pest_type in ("locust", "aphid") else 16
        if self.pest_type == "locust":
            row = 0 if self.flying else (1 if self.landed else 2)
            frame = self._frame % 8
            sheet_frame = row * 8 + frame
        elif self.pest_type == "aphid":
            row = {"adult": 0, "egg": 2, "nymph": 3}[self.stage]
            sheet_frame = row * 8 + (self._frame % 8)
        elif self.pest_type == "caterpillar":
            sheet_frame = self._frame % 16
        else:
            sheet_frame = self._frame % 16

        image = _load_frame(self.pest_type, sheet_frame, self.is_aphid_egg)
        self.image = image
        old_bottom = self.rect.bottom
        old_center = self.rect.center
        self.rect = self.image.get_rect()
        if self.flying:
            self.rect.center = old_center
        else:
            self.rect.midbottom = (round(self.precise_x), lane_center_y(self.lane_index))


_FRAME_CACHE: dict[tuple[str, int, bool], pygame.Surface] = {}


def _load_frame(pest_type: str, frame: int, egg: bool) -> pygame.Surface:
    key = (pest_type, frame, egg)
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    path = Path(__file__).resolve().parents[1] / "assets" / "level2" / "pests" / f"{pest_type}_sheet.png"
    try:
        sheet = pygame.image.load(str(path)).convert_alpha()
        columns = 8
        rows = 4 if pest_type in ("locust", "aphid") else 2
        cell = sheet.subsurface(
            pygame.Rect(
                (frame % columns) * sheet.get_width() // columns,
                (frame // columns) * sheet.get_height() // rows,
                sheet.get_width() // columns,
                sheet.get_height() // rows,
            )
        ).copy()
        bounds = cell.get_bounding_rect(min_alpha=1)
        if bounds.width and bounds.height:
            cell = cell.subsurface(bounds).copy()
        target_width = 82 if pest_type == "locust" else (64 if not egg else 26)
        target_height = 70 if pest_type == "locust" else (54 if not egg else 26)
        ratio = min(target_width / cell.get_width(), target_height / cell.get_height())
        cell = pygame.transform.scale(
            cell,
            (max(1, round(cell.get_width() * ratio)), max(1, round(cell.get_height() * ratio))),
        )
        # The supplied animation sheets face right, while every pest enters
        # from the right and advances left toward the farmhouse.  Mirror only
        # directional actors so their head, legs, wings, and antennae all
        # point naturally into their movement direction.  Eggs have no facing.
        if not egg:
            cell = pygame.transform.flip(cell, True, False)
    except (pygame.error, OSError):
        cell = pygame.Surface((44, 32), pygame.SRCALPHA)
        pygame.draw.rect(cell, (67, 101, 42), (8, 9, 28, 13))
        pygame.draw.rect(cell, (33, 48, 27), (8, 9, 28, 13), 2)
    _FRAME_CACHE[key] = cell
    return cell.copy()


# Compatibility name used by the original Level 2 tests and external callers.
Zombie = Pest
