"""Scrolling level geometry and obstacle generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

import pygame

from .config import (
    FLOOR_HEIGHT,
    AIR_PLATFORM_MIN_GAP,
    AIR_PLATFORM_WIDTHS,
    AIR_PLATFORM_Y,
    LOWER_FLOOR_Y,
    OBSTACLE_CLUSTER_GAP,
    SLIDE_OBSTACLE_BOTTOM,
    SLIDE_OBSTACLE_HEIGHT,
    WINDOW_WIDTH,
    obstacle_cluster_chance_at,
    obstacle_interval_at,
)


@dataclass
class Obstacle:
    x: float
    kind: str
    width: int
    height: int
    hit: bool = False
    clustered: bool = False

    @property
    def rect(self) -> pygame.Rect:
        if self.kind == "slide":
            return pygame.Rect(
                round(self.x),
                SLIDE_OBSTACLE_BOTTOM - self.height,
                self.width,
                self.height,
            )
        return pygame.Rect(
            round(self.x), LOWER_FLOOR_Y - self.height, self.width, self.height
        )

    def update(self, dt: float, speed: float) -> None:
        self.x -= speed * dt

    @property
    def is_offscreen(self) -> bool:
        return self.x + self.width < 0


@dataclass
class AirPlatform:
    x: float
    y: int
    width: int
    height: int = 12

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x), self.y, self.width, self.height)

    def update(self, dt: float, speed: float) -> None:
        self.x -= speed * dt

    @property
    def is_offscreen(self) -> bool:
        return self.x + self.width < 0


class AirPlatformManager:
    """Generate spaced, moving ledges for the richer sky route."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.platforms: list[AirPlatform] = []
        self.platforms.extend(
            (
                AirPlatform(255.0, 382, 118),
                AirPlatform(520.0, 330, 94),
                AirPlatform(760.0, 432, 142),
            )
        )
        self.spawn_remaining = 1.8

    def update(self, dt: float, speed: float) -> list[AirPlatform]:
        self.spawn_remaining -= dt
        spawned: list[AirPlatform] = []
        if self.spawn_remaining <= 0.0:
            platform = self.spawn()
            spawned.append(platform)
            self.spawn_remaining = self.rng.uniform(1.9, 3.0)
        for platform in self.platforms:
            platform.update(dt, speed)
        self.platforms = [item for item in self.platforms if not item.is_offscreen]
        return spawned

    def spawn(self) -> AirPlatform:
        width = self.rng.choice(AIR_PLATFORM_WIDTHS)
        y = self.rng.choice(AIR_PLATFORM_Y)
        x = float(WINDOW_WIDTH + self.rng.randint(AIR_PLATFORM_MIN_GAP, AIR_PLATFORM_MIN_GAP + 150))
        platform = AirPlatform(x, y, width)
        self.platforms.append(platform)
        return platform


class ObstacleManager:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.obstacles: list[Obstacle] = []
        self.spawn_remaining = self._next_interval(0.0)
        self.cluster_remaining: float | None = None
        self.last_obstacle: Obstacle | None = None
        self.total_spawned = 0
        self.clusters_spawned = 0

    def _next_interval(self, elapsed: float) -> float:
        interval, jitter = obstacle_interval_at(elapsed)
        return self.rng.uniform(interval - jitter, interval + jitter)

    def update(self, dt: float, elapsed: float, speed: float) -> list[Obstacle]:
        spawned: list[Obstacle] = []
        self.spawn_remaining -= dt
        if self.cluster_remaining is not None:
            self.cluster_remaining -= dt
            if self.cluster_remaining <= 0.0:
                spawned.append(self.spawn_clustered(elapsed))
                self.cluster_remaining = None

        if self.spawn_remaining <= 0.0:
            spawned.append(self.spawn(elapsed))
            self.spawn_remaining = self._next_interval(elapsed)
            if self.rng.random() < obstacle_cluster_chance_at(elapsed):
                cluster_delay = OBSTACLE_CLUSTER_GAP / max(speed, 1.0)
                self.cluster_remaining = cluster_delay
                self.spawn_remaining += cluster_delay

        for obstacle in self.obstacles:
            obstacle.update(dt, speed)
        self.obstacles = [item for item in self.obstacles if not item.is_offscreen]
        return spawned

    def spawn(self, elapsed: float) -> Obstacle:
        kind = self.rng.choices(("jump", "slide"), weights=(0.56, 0.44), k=1)[0]
        dimensions = {
            "jump": (44, 55),
            "slide": (64, SLIDE_OBSTACLE_HEIGHT),
        }
        width, height = dimensions[kind]
        obstacle = Obstacle(
            x=float(WINDOW_WIDTH + 30),
            kind=kind,
            width=width,
            height=height,
        )
        self.obstacles.append(obstacle)
        self.last_obstacle = obstacle
        self.total_spawned += 1
        return obstacle

    def spawn_clustered(self, elapsed: float) -> Obstacle:
        previous = self.last_obstacle
        if previous is None:
            return self.spawn(elapsed)

        kind = "slide" if previous.kind == "jump" else "jump"

        dimensions = {
            "jump": (44, 55),
            "slide": (64, SLIDE_OBSTACLE_HEIGHT),
        }
        width, height = dimensions[kind]
        obstacle = Obstacle(
            x=float(WINDOW_WIDTH + 30),
            kind=kind,
            width=width,
            height=height,
            clustered=True,
        )
        self.obstacles.append(obstacle)
        self.last_obstacle = obstacle
        self.total_spawned += 1
        self.clusters_spawned += 1
        return obstacle


class ScrollingMap:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.offset = 0.0
        self.background = self._load_background()
        self.air_platforms = AirPlatformManager(rng)

    @staticmethod
    def _load_background() -> pygame.Surface | None:
        """Load the illustrated first-level environment when available."""
        path = Path(__file__).resolve().parents[1] / "assets" / "level1" / "forest_runner_background.png"
        try:
            image = pygame.image.load(str(path))
            if pygame.display.get_surface() is not None:
                image = image.convert()
            else:
                image = image.copy()
        except (FileNotFoundError, pygame.error):
            return None

        source_width, source_height = image.get_size()
        target_ratio = WINDOW_WIDTH / 600
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            crop_width = round(source_height * target_ratio)
            image = image.subsurface(
                pygame.Rect((source_width - crop_width) // 2, 0, crop_width, source_height)
            ).copy()
        return pygame.transform.scale(image, (WINDOW_WIDTH, 600))

    def update(self, dt: float, speed: float) -> None:
        self.offset = (self.offset + speed * dt) % 80.0
        self.air_platforms.update(dt, speed)

    def draw(self, surface: pygame.Surface) -> None:
        if self.background is not None:
            surface.blit(self.background, (0, 0))
        else:
            surface.fill((69, 157, 202))
            self._draw_fallback_hills(surface)
        self._draw_playable_floor(surface, LOWER_FLOOR_Y)
        for platform in self.air_platforms.platforms:
            self._draw_air_platform(surface, platform)

    @staticmethod
    def _draw_air_platform(surface: pygame.Surface, platform: AirPlatform) -> None:
        rect = platform.rect
        pygame.draw.rect(surface, (45, 31, 27), rect.move(4, 5))
        pygame.draw.rect(surface, (84, 49, 34), (rect.left, rect.top + 7, rect.width, rect.height + 13))
        pygame.draw.rect(surface, (108, 65, 39), (rect.left + 7, rect.top + 10, rect.width - 14, 10))
        pygame.draw.rect(surface, (93, 162, 67), (rect.left, rect.top, rect.width, 11))
        pygame.draw.rect(surface, (186, 222, 104), (rect.left + 4, rect.top, rect.width - 8, 4))
        for x in range(rect.left + 12, rect.right - 8, 24):
            pygame.draw.rect(surface, (142, 194, 79), (x, rect.top + 5, 9, 3))
            pygame.draw.rect(surface, (154, 96, 54), (x + 3, rect.top + 14, 7, 5))

    def _draw_fallback_hills(self, surface: pygame.Surface) -> None:
        for hill_x, hill_width, hill_height in ((-40, 300, 86), (210, 340, 112), (520, 300, 76), (760, 320, 104)):
            base_y = 255
            pygame.draw.rect(surface, (79, 145, 137), (hill_x, base_y - hill_height + 18, hill_width, hill_height - 18))
            pygame.draw.rect(surface, (79, 145, 137), (hill_x + 32, base_y - hill_height, hill_width - 64, 18))
            pygame.draw.rect(surface, (47, 111, 104), (hill_x, base_y - 5, hill_width, 5))

    def _draw_playable_floor(self, surface: pygame.Surface, floor_y: int) -> None:
        """Add the collision lane as a richly textured foreground."""
        pygame.draw.rect(surface, (33, 53, 40), (0, floor_y + 18, WINDOW_WIDTH, 12))
        pygame.draw.rect(surface, (75, 44, 33), (0, floor_y + 30, WINDOW_WIDTH, 70))
        pygame.draw.rect(surface, (43, 31, 28), (0, floor_y + 100, WINDOW_WIDTH, 5))
        pygame.draw.rect(surface, (119, 182, 76), (0, floor_y - 2, WINDOW_WIDTH, 12))
        pygame.draw.rect(surface, (192, 224, 105), (0, floor_y - 2, WINDOW_WIDTH, 4))
        marker_offset = int(self.offset) % 64
        for x in range(-marker_offset, WINDOW_WIDTH + 64, 64):
            pygame.draw.rect(surface, (68, 133, 66), (x + 5, floor_y + 6, 18, 5))
            pygame.draw.rect(surface, (143, 202, 88), (x + 27, floor_y + 1, 22, 5))
            pygame.draw.rect(surface, (108, 66, 45), (x + 10, floor_y + 41, 9, 7))
            pygame.draw.rect(surface, (146, 91, 54), (x + 12, floor_y + 43, 5, 3))
            pygame.draw.rect(surface, (102, 67, 49), (x + 42, floor_y + 64, 12, 8))
            pygame.draw.rect(surface, (163, 113, 69), (x + 44, floor_y + 64, 6, 3))
        for x, height in ((88, 18), (302, 13), (536, 22), (714, 15)):
            pygame.draw.rect(surface, (46, 105, 53), (x, floor_y - height - 3, 4, height + 5))
            pygame.draw.rect(surface, (84, 163, 67), (x - 7, floor_y - height, 16, 5))
            pygame.draw.rect(surface, (135, 194, 76), (x + 3, floor_y - height - 4, 7, 4))

    def _draw_floor(
        self,
        surface: pygame.Surface,
        floor_y: int,
        color: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(surface, color, (0, floor_y, WINDOW_WIDTH, FLOOR_HEIGHT))
        pygame.draw.rect(
            surface,
            (105, 71, 52),
            (0, floor_y + FLOOR_HEIGHT, WINDOW_WIDTH, 12),
        )
        marker_offset = int(self.offset) % 80
        for x in range(-marker_offset, WINDOW_WIDTH + 80, 80):
            pygame.draw.rect(surface, (151, 198, 113), (x, floor_y + 3, 42, 5))
            pygame.draw.rect(surface, (42, 76, 57), (x + 50, floor_y + 5, 15, 3))
            pygame.draw.rect(surface, (42, 76, 57), (x + 55, floor_y + 1, 4, 7))
            pygame.draw.rect(surface, (185, 211, 112), (x + 20, floor_y + 16, 4, 4))
            pygame.draw.rect(surface, (74, 128, 70), (x + 22, floor_y + 10, 3, 8))
            pygame.draw.rect(surface, (235, 180, 77), (x + 25, floor_y + 9, 4, 4))
