"""Scrolling level geometry and obstacle generation."""

from __future__ import annotations

from dataclasses import dataclass
import random

import pygame

from .config import (
    FLOOR_HEIGHT,
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
    def __init__(self) -> None:
        self.offset = 0.0

    def update(self, dt: float, speed: float) -> None:
        self.offset = (self.offset + speed * dt) % 80.0

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((210, 235, 238))
        pygame.draw.rect(surface, (245, 214, 126), (0, 0, WINDOW_WIDTH, 86))
        pygame.draw.circle(surface, (248, 173, 65), (710, 66), 31)

        # Distant city blocks provide readable motion without image assets.
        for index in range(9):
            x = int(index * 120 - (self.offset * 0.22) % 120)
            height = 55 + (index % 3) * 18
            pygame.draw.rect(surface, (126, 166, 174), (x, 255 - height, 86, height))
            pygame.draw.rect(surface, (242, 239, 185), (x + 15, 215 - height, 12, 12))

        self._draw_floor(surface, LOWER_FLOOR_Y, (56, 91, 73))

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
