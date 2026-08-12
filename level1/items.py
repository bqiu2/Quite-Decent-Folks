"""Collectible generation with adaptive pair probabilities."""

from __future__ import annotations

from dataclasses import dataclass
import random

import pygame

from shared_game_data import ElementType

from .config import (
    ITEM_HIGH_CENTER_Y,
    ITEM_LOW_CENTER_Y,
    ITEM_MIN_PROBABILITY,
    ITEM_PAIR_INTERVAL,
    ITEM_SIZE,
    ITEM_WEIGHT_DECAY,
    WINDOW_WIDTH,
)


ELEMENT_TYPES: tuple[ElementType, ...] = (
    "water",
    "light",
    "nitrogen",
    "phosphorus",
    "potassium",
    "pesticide",
)

ELEMENT_COLORS: dict[ElementType, tuple[int, int, int]] = {
    "water": (57, 150, 224),
    "light": (248, 196, 68),
    "nitrogen": (80, 178, 98),
    "phosphorus": (205, 96, 122),
    "potassium": (148, 102, 190),
    "pesticide": (235, 105, 64),
}

ELEMENT_LABELS: dict[ElementType, str] = {
    "water": "WATER",
    "light": "SUN",
    "nitrogen": "N",
    "phosphorus": "P",
    "potassium": "K",
    "pesticide": "PEST",
}


def draw_element_icon(
    surface: pygame.Surface,
    element: ElementType,
    rect: pygame.Rect,
) -> None:
    """Draw a recognizable icon that also works at HUD size."""
    color = ELEMENT_COLORS[element]
    center_x, center_y = rect.center
    scale = max(0.45, rect.width / 42.0)
    unit = max(1, round(3 * scale))

    if element == "water":
        points = (
            (center_x, center_y - round(13 * scale)),
            (center_x - round(8 * scale), center_y),
            (center_x - round(5 * scale), center_y + round(8 * scale)),
            (center_x + round(6 * scale), center_y + round(8 * scale)),
            (center_x + round(9 * scale), center_y),
        )
        pygame.draw.polygon(surface, (31, 75, 113), points)
        pygame.draw.polygon(surface, color, tuple((x, y - unit) for x, y in points))
        pygame.draw.rect(surface, (187, 235, 245), (center_x - unit, center_y - round(3 * scale), unit, round(5 * scale)))
        return

    if element == "light":
        ray = round(13 * scale)
        pygame.draw.rect(surface, color, (center_x - round(7 * scale), center_y - round(7 * scale), round(14 * scale), round(14 * scale)))
        pygame.draw.rect(surface, (255, 238, 128), (center_x - round(4 * scale), center_y - round(4 * scale), round(8 * scale), round(8 * scale)))
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            if dx == 0:
                ray_rect = (center_x - unit // 2, center_y + dy * ray, unit, round(5 * scale))
            elif dy == 0:
                ray_rect = (center_x + dx * ray, center_y - unit // 2, round(5 * scale), unit)
            else:
                ray_rect = (center_x + dx * ray - unit // 2, center_y + dy * ray - unit // 2, unit, unit)
            pygame.draw.rect(surface, color, ray_rect)
        return

    if element == "pesticide":
        body = pygame.Rect(
            center_x - round(7 * scale),
            center_y - round(5 * scale),
            round(14 * scale),
            round(17 * scale),
        )
        pygame.draw.rect(surface, (64, 70, 54), body.move(2, 2))
        pygame.draw.rect(surface, color, body)
        pygame.draw.rect(surface, (248, 190, 83), (body.left + unit, body.top + unit, max(unit, body.width // 3), unit))
        pygame.draw.rect(
            surface,
            (46, 55, 55),
            (center_x - round(3 * scale), center_y - round(10 * scale), round(7 * scale), round(5 * scale)),
        )
        pygame.draw.rect(
            surface,
            (46, 55, 55),
            (center_x + round(4 * scale), center_y - round(11 * scale), round(9 * scale), max(1, round(2 * scale))),
        )
        return

    # N/P/K remain standard nutrient symbols, framed as fertilizer badges.
    points = [
        (center_x, center_y - round(13 * scale)),
        (center_x + round(11 * scale), center_y - round(6 * scale)),
        (center_x + round(11 * scale), center_y + round(7 * scale)),
        (center_x, center_y + round(13 * scale)),
        (center_x - round(11 * scale), center_y + round(7 * scale)),
        (center_x - round(11 * scale), center_y - round(6 * scale)),
    ]
    pygame.draw.polygon(surface, color, points)
    font = pygame.font.Font(None, max(14, round(24 * scale)))
    label = font.render(ELEMENT_LABELS[element], True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=rect.center))


class AdaptiveElementSampler:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        equal = 1.0 / len(ELEMENT_TYPES)
        self.probabilities: dict[ElementType, float] = {
            element: equal for element in ELEMENT_TYPES
        }

    def draw_pair(self) -> tuple[ElementType, ElementType]:
        first = self._draw_from(ELEMENT_TYPES)
        remaining = tuple(item for item in ELEMENT_TYPES if item != first)
        second = self._draw_from(remaining)
        pair = (first, second)
        self._decay_appeared(pair)
        return pair

    def _draw_from(self, choices: tuple[ElementType, ...]) -> ElementType:
        weights = [self.probabilities[item] for item in choices]
        return self.rng.choices(choices, weights=weights, k=1)[0]

    def _decay_appeared(self, appeared: tuple[ElementType, ElementType]) -> None:
        appeared_set = set(appeared)
        removed = 0.0
        for element in appeared:
            old = self.probabilities[element]
            new = old * ITEM_WEIGHT_DECAY
            self.probabilities[element] = new
            removed += old - new

        recipients = [item for item in ELEMENT_TYPES if item not in appeared_set]
        for element in recipients:
            self.probabilities[element] += removed / len(recipients)
        self._apply_floor_and_normalize()

    def _apply_floor_and_normalize(self) -> None:
        values = dict(self.probabilities)
        low = {item for item, value in values.items() if value < ITEM_MIN_PROBABILITY}
        while low:
            for item in low:
                values[item] = ITEM_MIN_PROBABILITY
            flexible = [item for item in ELEMENT_TYPES if item not in low]
            available = 1.0 - ITEM_MIN_PROBABILITY * len(low)
            total = sum(values[item] for item in flexible)
            if total <= 0.0:
                for item in flexible:
                    values[item] = available / len(flexible)
            else:
                for item in flexible:
                    values[item] = values[item] / total * available
            new_low = {
                item for item in flexible if values[item] < ITEM_MIN_PROBABILITY
            }
            if not new_low:
                break
            low.update(new_low)
        self.probabilities = values


@dataclass
class Collectible:
    x: float
    center_y: int
    element: ElementType
    pair_id: int
    size: int = ITEM_SIZE

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.x),
            round(self.center_y - self.size / 2),
            self.size,
            self.size,
        )

    def update(self, dt: float, speed: float) -> None:
        self.x -= speed * dt

    @property
    def is_offscreen(self) -> bool:
        return self.x + self.size < 0


class ItemManager:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.sampler = AdaptiveElementSampler(self.rng)
        self.items: list[Collectible] = []
        self.spawn_remaining = ITEM_PAIR_INTERVAL * 0.65
        self._next_pair_id = 1

    def update(
        self,
        dt: float,
        speed: float,
        *,
        can_spawn: bool = True,
    ) -> tuple[Collectible, Collectible] | None:
        for item in self.items:
            item.update(dt, speed)
        self.items = [item for item in self.items if not item.is_offscreen]

        spawned_pair = None
        self.spawn_remaining -= dt
        if self.spawn_remaining <= 0.0 and can_spawn:
            spawned_pair = self.spawn_pair()
            self.spawn_remaining = ITEM_PAIR_INTERVAL
        elif self.spawn_remaining < 0.0:
            self.spawn_remaining = 0.0
        return spawned_pair

    def spawn_pair(self) -> tuple[Collectible, Collectible]:
        high_element, low_element = self.sampler.draw_pair()
        pair_id = self._next_pair_id
        self._next_pair_id += 1
        high = Collectible(
            float(WINDOW_WIDTH + 25), ITEM_HIGH_CENTER_Y, high_element, pair_id
        )
        low = Collectible(
            float(WINDOW_WIDTH + 25), ITEM_LOW_CENTER_Y, low_element, pair_id
        )
        self.items.extend((high, low))
        return high, low

    def remove_pair(self, pair_id: int) -> None:
        self.items = [item for item in self.items if item.pair_id != pair_id]
