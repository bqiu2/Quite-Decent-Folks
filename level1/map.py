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
        surface.fill((194, 222, 224))
        pygame.draw.rect(surface, (246, 211, 119), (0, 0, WINDOW_WIDTH, 86))

        # Chunky sun and clouds keep the background pixel-shaped instead of
        # relying on smooth vector circles.
        pygame.draw.rect(surface, (248, 173, 65), (695, 42, 48, 48))
        pygame.draw.rect(surface, (255, 207, 83), (687, 52, 64, 28))
        for cloud_x, cloud_y in ((96, 98), (382, 132)):
            pygame.draw.rect(surface, (238, 248, 233), (cloud_x, cloud_y, 74, 15))
            pygame.draw.rect(surface, (238, 248, 233), (cloud_x + 14, cloud_y - 10, 28, 25))
            pygame.draw.rect(surface, (238, 248, 233), (cloud_x + 44, cloud_y - 6, 24, 21))

        # Stepped hills and tree silhouettes fill the middle distance so the
        # runner has a layered landscape instead of a flat strip of sky.
        for hill_x, hill_width, hill_height in ((-40, 300, 86), (210, 340, 112), (520, 300, 76), (760, 320, 104)):
            base_y = 255
            pygame.draw.rect(
                surface,
                (139, 184, 157),
                (hill_x, base_y - hill_height + 18, hill_width, hill_height - 18),
            )
            pygame.draw.rect(
                surface,
                (139, 184, 157),
                (hill_x + 32, base_y - hill_height, hill_width - 64, 18),
            )
            pygame.draw.rect(
                surface,
                (139, 184, 157),
                (hill_x + 70, base_y - hill_height - 12, hill_width - 140, 12),
            )
            pygame.draw.rect(surface, (103, 157, 127), (hill_x, base_y - 5, hill_width, 5))

        # Tiny tree clusters create a clear pixel-art horizon line.
        for tree_x, tree_y in ((62, 208), (174, 198), (448, 214), (676, 190), (884, 205)):
            pygame.draw.rect(surface, (92, 76, 54), (tree_x + 11, tree_y + 26, 9, 28))
            pygame.draw.rect(surface, (51, 113, 74), (tree_x, tree_y + 8, 32, 25))
            pygame.draw.rect(surface, (69, 139, 81), (tree_x + 7, tree_y, 19, 19))
            pygame.draw.rect(surface, (132, 187, 92), (tree_x + 10, tree_y + 3, 8, 5))

        # Distant city blocks provide readable motion without image assets.
        for index in range(9):
            x = int(index * 120 - (self.offset * 0.22) % 120)
            height = 55 + (index % 3) * 18
            pygame.draw.rect(surface, (119, 160, 169), (x, 255 - height, 86, height))
            pygame.draw.rect(surface, (82, 126, 139), (x + 7, 255 - height, 5, height))
            for row in range(3):
                for column in range(3):
                    window_x = x + 15 + column * 22
                    window_y = 215 - height + row * 26
                    pygame.draw.rect(surface, (242, 239, 185), (window_x, window_y, 12, 12))
                    pygame.draw.rect(surface, (94, 137, 147), (window_x, window_y + 12, 12, 4))

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
            pygame.draw.rect(surface, (42, 76, 57), (x + 50, floor_y + 5, 15, 3))
            pygame.draw.rect(surface, (42, 76, 57), (x + 55, floor_y + 1, 4, 7))
            pygame.draw.rect(surface, (185, 211, 112), (x + 20, floor_y + 16, 4, 4))
            pygame.draw.rect(surface, (74, 128, 70), (x + 22, floor_y + 10, 3, 8))
            pygame.draw.rect(surface, (235, 180, 77), (x + 25, floor_y + 9, 4, 4))
