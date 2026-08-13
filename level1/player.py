"""Stick-figure movement and animation state for level one."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

import pygame

from .config import (
    GRAVITY,
    INVINCIBILITY_DURATION,
    JUMP_SPEED,
    LOWER_FLOOR_Y,
    MAX_FALL_SPEED,
    MAX_HP,
    PLAYER_CROUCH_HEIGHT,
    PLAYER_HEIGHT,
    PLAYER_WIDTH,
    PLAYER_X,
    SLIDE_DURATION,
)


@dataclass
class Player:
    x: float = float(PLAYER_X)
    y: float = float(LOWER_FLOOR_Y - PLAYER_HEIGHT)
    velocity_y: float = 0.0
    grounded: bool = True
    slide_remaining: float = 0.0
    invincible_remaining: float = 0.0
    hp: int = MAX_HP
    support_y: int | None = None

    @property
    def crouching(self) -> bool:
        return self.slide_remaining > 0.0

    @property
    def height(self) -> int:
        return PLAYER_CROUCH_HEIGHT if self.crouching else PLAYER_HEIGHT

    @property
    def rect(self) -> pygame.Rect:
        if self.grounded:
            top = (self.support_y if self.support_y is not None else LOWER_FLOOR_Y) - self.height
        else:
            standing_bottom = self.y + PLAYER_HEIGHT
            top = standing_bottom - self.height
        return pygame.Rect(round(self.x), round(top), PLAYER_WIDTH, self.height)

    @property
    def is_invincible(self) -> bool:
        return self.invincible_remaining > 0.0

    def jump(self) -> bool:
        """Start the single jump permitted on the one-floor course."""
        if self.crouching or not self.grounded:
            return False
        self.grounded = False
        self.velocity_y = JUMP_SPEED
        self.support_y = None
        self.y = (self.support_y if self.support_y is not None else LOWER_FLOOR_Y) - PLAYER_HEIGHT
        return True

    def big_jump(self) -> bool:
        """Start the stronger keyboard jump assigned to the D key."""
        if self.crouching or not self.grounded:
            return False
        self.grounded = False
        self.support_y = None
        self.velocity_y = -980.0
        self.y = LOWER_FLOOR_Y - PLAYER_HEIGHT
        return True

    def slide(self) -> bool:
        """Start a slide while grounded."""
        if not self.grounded or self.crouching:
            return False
        self.slide_remaining = SLIDE_DURATION
        return True

    def drop(self) -> bool:
        """Move down: crouch on the floor or drop through a floating platform."""
        if not self.grounded:
            return False
        if self.support_y is None:
            return self.slide()
        self.grounded = False
        self.support_y = None
        self.y += 5.0
        self.velocity_y = 180.0
        return True

    def take_damage(self) -> bool:
        if self.is_invincible or self.hp <= 0:
            return False
        self.hp = max(0, self.hp - 1)
        self.invincible_remaining = INVINCIBILITY_DURATION
        return True

    def update(self, dt: float, platforms: Iterable[pygame.Rect] = ()) -> None:
        dt = max(0.0, dt)
        self.slide_remaining = max(0.0, self.slide_remaining - dt)
        self.invincible_remaining = max(0.0, self.invincible_remaining - dt)

        if self.grounded:
            support_y = self.support_y if self.support_y is not None else LOWER_FLOOR_Y
            if self.support_y is not None and not any(
                platform.left <= self.x + PLAYER_WIDTH // 2 <= platform.right
                for platform in platforms
            ):
                self.grounded = False
                self.support_y = None
            else:
                self.y = support_y - PLAYER_HEIGHT
                self.velocity_y = 0.0
                return

        previous_bottom = self.y + PLAYER_HEIGHT
        self.velocity_y = min(MAX_FALL_SPEED, self.velocity_y + GRAVITY * dt)
        self.y += self.velocity_y * dt
        new_bottom = self.y + PLAYER_HEIGHT

        landing_y = LOWER_FLOOR_Y
        for platform in platforms:
            if (
                previous_bottom <= platform.top <= new_bottom
                and self.x + PLAYER_WIDTH > platform.left
                and self.x < platform.right
            ):
                landing_y = min(landing_y, platform.top)
        if previous_bottom <= landing_y <= new_bottom:
            self._land(landing_y, landing_y != LOWER_FLOOR_Y)

    def _land(self, surface_y: int = LOWER_FLOOR_Y, on_platform: bool = False) -> None:
        self.y = surface_y - PLAYER_HEIGHT
        self.velocity_y = 0.0
        self.grounded = True
        self.support_y = surface_y if on_platform else None
