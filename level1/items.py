"""Collectible generation with adaptive pair probabilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import random
from typing import Literal

import pygame

from shared_game_data import ElementType

from .config import (
    ITEM_HIGH_CENTER_Y,
    ITEM_LOW_CENTER_Y,
    AIR_ITEM_CENTER_Y,
    ITEM_COLLECT_ANIMATION_DURATION,
    ITEM_MIN_PROBABILITY,
    ITEM_PAIR_INTERVAL,
    ITEM_SIZE,
    ITEM_WEIGHT_DECAY,
    PLATFORM_ITEM_CHANCE,
    PLATFORM_ITEM_LOOKAHEAD,
    RANDOM_ITEM_X_OFFSET,
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
    "pesticide": "SPRAY",
}

PickupSurface = Literal["ground", "platform", "air"]


def _draw_element_icon_legacy(
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


def _draw_element_icon_previous(
    surface: pygame.Surface,
    element: ElementType,
    rect: pygame.Rect,
) -> None:
    """Draw a warm, hand-crafted farming-RPG collectible icon.

    The sprite is authored on a 32x32 pixel canvas and then scaled with
    nearest-neighbour sampling.  That keeps the large collectible cards and
    the tiny HUD icons on the same crisp pixel grid while leaving enough room
    for material highlights, shadows, and small decorative marks.
    """
    palette = {
        "outline": (49, 45, 42),
        "deep": (69, 57, 48),
        "cream": (255, 237, 177),
        "cream_shadow": (201, 154, 82),
        "water": (56, 153, 205),
        "water_light": (142, 219, 236),
        "water_shadow": (35, 86, 143),
        "sun": (244, 173, 55),
        "sun_light": (255, 226, 109),
        "sun_shadow": (188, 101, 43),
        "leaf": (74, 151, 75),
        "leaf_light": (143, 198, 91),
        "leaf_shadow": (42, 96, 59),
        "pink": (206, 91, 122),
        "pink_light": (239, 145, 151),
        "pink_shadow": (133, 57, 84),
        "purple": (137, 93, 183),
        "purple_light": (194, 143, 216),
        "purple_shadow": (79, 55, 128),
        "bottle": (80, 135, 112),
        "bottle_light": (154, 200, 132),
        "bottle_shadow": (43, 86, 75),
        "orange": (235, 105, 57),
    }

    icon = pygame.Surface((32, 32), pygame.SRCALPHA)

    def block(color: tuple[int, int, int], x: int, y: int, width: int, height: int) -> None:
        pygame.draw.rect(icon, color, (x, y, width, height))

    def polygon(color: tuple[int, int, int], points: tuple[tuple[int, int], ...]) -> None:
        pygame.draw.polygon(icon, color, points)

    def glyph(letter: str, x: int, y: int, color: tuple[int, int, int]) -> None:
        patterns = {
            "N": ("10001", "11001", "10101", "10011", "10001"),
            "P": ("11110", "10001", "11110", "10000", "10000"),
            "K": ("10001", "10010", "11100", "10010", "10001"),
        }
        for row, pattern in enumerate(patterns[letter]):
            for column, value in enumerate(pattern):
                if value == "1":
                    block(color, x + column * 2, y + row * 3, 2, 3)

    # A small grounding shadow makes each object read as a physical pickup,
    # especially against the pale item card in the runner course.
    block((72, 61, 49), 7, 27, 18, 3)
    block((130, 95, 57), 10, 29, 12, 1)

    if element == "water":
        outline = ((16, 10), (12, 14), (9, 14), (7, 19), (8, 25), (12, 28), (20, 28), (24, 24), (25, 18), (21, 13))
        polygon(palette["outline"], outline)
        polygon(palette["water_shadow"], ((16, 4), (11, 12), (9, 16), (10, 23), (14, 26), (19, 26), (22, 22), (22, 16), (19, 11)))
        polygon(palette["water"], ((16, 5), (12, 13), (10, 17), (11, 22), (14, 25), (19, 25), (21, 21), (21, 16), (18, 11)))
        block(palette["water_light"], 13, 12, 3, 7)
        block((210, 241, 245), 14, 10, 2, 3)
        block(palette["water_shadow"], 18, 23, 3, 2)
        block(palette["cream"], 5, 14, 2, 2)
        block(palette["cream"], 25, 18, 2, 2)

    elif element == "light":
        # Eight chunky rays and a stepped sun disk read clearly even at 18px.
        ray_color = palette["sun_shadow"]
        block(ray_color, 14, 1, 4, 5)
        block(ray_color, 14, 26, 4, 5)
        block(ray_color, 1, 14, 5, 4)
        block(ray_color, 26, 14, 5, 4)
        block(ray_color, 5, 5, 4, 4)
        block(ray_color, 23, 5, 4, 4)
        block(ray_color, 5, 23, 4, 4)
        block(ray_color, 23, 23, 4, 4)
        polygon(palette["outline"], ((11, 8), (21, 8), (25, 12), (25, 21), (21, 25), (11, 25), (7, 21), (7, 12)))
        polygon(palette["sun"], ((12, 9), (20, 9), (23, 12), (23, 20), (20, 23), (12, 23), (9, 20), (9, 12)))
        block(palette["sun_light"], 12, 11, 7, 7)
        block((255, 246, 157), 13, 11, 3, 3)
        block(palette["sun_shadow"], 19, 18, 4, 4)
        block(palette["cream"], 4, 10, 2, 2)

    elif element in {"nitrogen", "phosphorus", "potassium"}:
        nutrient_colors = {
            "nitrogen": (palette["leaf"], palette["leaf_light"], palette["leaf_shadow"], "N"),
            "phosphorus": (palette["pink"], palette["pink_light"], palette["pink_shadow"], "P"),
            "potassium": (palette["purple"], palette["purple_light"], palette["purple_shadow"], "K"),
        }
        main, highlight, shadow, letter = nutrient_colors[element]
        # Fertilizer pouch with a folded top, stitched bottom, and a colored
        # seal; each nutrient stays distinct while sharing one item language.
        polygon(palette["outline"], ((7, 7), (25, 7), (27, 11), (25, 26), (21, 29), (10, 29), (5, 25), (5, 11)))
        block(shadow, 7, 11, 18, 15)
        block(main, 8, 10, 16, 15)
        block(highlight, 9, 11, 5, 3)
        block(shadow, 8, 24, 16, 3)
        block(palette["cream_shadow"], 9, 27, 14, 1)
        block(palette["outline"], 9, 6, 14, 4)
        block(highlight, 11, 7, 10, 2)
        block(palette["cream"], 13, 5, 6, 2)
        block(palette["outline"], 13, 18, 7, 2)
        glyph(letter, 12, 12, palette["cream"])
        block(palette["cream"], 4, 15, 2, 2)
        block(palette["cream"], 26, 20, 2, 2)

    else:  # pesticide
        # A little spray bottle with a nozzle, trigger, liquid window, and
        # three square droplets gives the negative pickup a unique silhouette.
        block(palette["outline"], 8, 10, 15, 18)
        block(palette["bottle_shadow"], 10, 12, 12, 14)
        block(palette["bottle"], 10, 11, 11, 14)
        block(palette["bottle_light"], 11, 13, 4, 8)
        block(palette["orange"], 14, 19, 6, 5)
        block(palette["cream"], 15, 20, 4, 2)
        block(palette["outline"], 12, 7, 7, 5)
        block(palette["bottle_light"], 13, 8, 5, 2)
        block(palette["outline"], 18, 5, 8, 3)
        block(palette["bottle"], 23, 6, 6, 2)
        block(palette["cream"], 25, 3, 2, 2)
        block(palette["cream"], 28, 1, 2, 2)
        block(palette["orange"], 4, 21, 3, 3)
        block(palette["orange"], 1, 25, 2, 2)

    scaled = pygame.transform.scale(icon, pygame.Rect(rect).size)
    surface.blit(scaled, pygame.Rect(rect).topleft)


def _reference_points(center: tuple[int, int], radius: int) -> tuple[tuple[int, int], ...]:
    """Return a stepped octagon used by the new floating pickups."""
    cx, cy = center
    return (
        (cx - radius // 2, cy - radius),
        (cx + radius // 2, cy - radius),
        (cx + radius, cy - radius // 2),
        (cx + radius, cy + radius // 2),
        (cx + radius // 2, cy + radius),
        (cx - radius // 2, cy + radius),
        (cx - radius, cy + radius // 2),
        (cx - radius, cy - radius // 2),
    )


def _draw_reference_glyph(
    surface: pygame.Surface,
    letter: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    shadow: tuple[int, int, int],
) -> None:
    """Draw a chunky 5x7 nutrient letter without a smooth system font."""
    patterns = {
        "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
        "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
        "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    }
    pattern = patterns[letter]
    for row, line in enumerate(pattern):
        for column, value in enumerate(line):
            if value == "1":
                pygame.draw.rect(surface, shadow, (x + column * 3 + 1, y + row * 3 + 1, 3, 3))
                pygame.draw.rect(surface, color, (x + column * 3, y + row * 3, 3, 3))


def draw_element_icon(
    surface: pygame.Surface,
    element: ElementType,
    rect: pygame.Rect,
) -> None:
    """Draw the reference-style floating pickup sprites.

    These are a new visual language rather than a restyle of the former
    card/bag icons: pale pixel halos, octagonal colored badges, and one-off
    silhouettes for water, sunlight, nutrients, and pests.
    """
    colors = {
        "ink": (45, 38, 35),
        "halo": (255, 239, 171),
        "halo_shadow": (185, 143, 75),
        "water": (65, 155, 219),
        "water_light": (173, 227, 239),
        "water_dark": (32, 76, 135),
        "sun": (239, 166, 45),
        "sun_light": (255, 222, 91),
        "sun_dark": (170, 83, 35),
        "n": (89, 166, 88),
        "n_light": (173, 217, 111),
        "n_dark": (42, 97, 57),
        "p": (214, 98, 127),
        "p_light": (247, 158, 164),
        "p_dark": (126, 54, 82),
        "k": (145, 101, 190),
        "k_light": (201, 153, 222),
        "k_dark": (77, 51, 124),
        "pest": (102, 75, 52),
        "pest_light": (181, 145, 81),
        "pest_dark": (46, 44, 39),
        "pest_red": (222, 92, 57),
    }
    sprite = pygame.Surface((48, 48), pygame.SRCALPHA)
    center = (24, 24)

    def block(color: tuple[int, int, int], x: int, y: int, width: int, height: int) -> None:
        pygame.draw.rect(sprite, color, (x, y, width, height))

    def polygon(color: tuple[int, int, int], points: tuple[tuple[int, int], ...]) -> None:
        pygame.draw.polygon(sprite, color, points)

    def halo() -> None:
        polygon(colors["halo_shadow"], _reference_points(center, 22))
        polygon(colors["halo"], _reference_points(center, 19))
        # Four clipped pixels sell the glow as a hand-placed sprite rather
        # than a smooth vector circle.
        block(colors["halo"], 3, 22, 3, 4)
        block(colors["halo"], 42, 22, 3, 4)
        block(colors["halo"], 22, 3, 4, 3)
        block(colors["halo"], 22, 42, 4, 3)

    if element == "water":
        halo()
        polygon(colors["ink"], ((24, 7), (14, 21), (12, 31), (16, 38), (23, 41), (31, 39), (36, 32), (35, 23)))
        polygon(colors["water_dark"], ((24, 9), (16, 22), (14, 30), (18, 36), (24, 38), (30, 36), (34, 30), (33, 24)))
        polygon(colors["water"], ((24, 10), (18, 23), (16, 29), (19, 35), (24, 37), (29, 35), (32, 29), (31, 24)))
        block(colors["water_light"], 20, 18, 4, 11)
        block((224, 248, 246), 21, 16, 3, 4)
        block(colors["water_dark"], 28, 32, 4, 3)

    elif element == "light":
        halo()
        # Separate rays make the sun read clearly at the tiny HUD size.
        for x, y, width, height in (
            (22, 1, 4, 7), (22, 40, 4, 7), (1, 22, 7, 4), (40, 22, 7, 4),
            (7, 7, 5, 5), (36, 7, 5, 5), (7, 36, 5, 5), (36, 36, 5, 5),
        ):
            block(colors["sun_dark"], x, y, width, height)
        polygon(colors["ink"], _reference_points(center, 14))
        polygon(colors["sun_dark"], _reference_points(center, 12))
        polygon(colors["sun"], _reference_points(center, 10))
        block(colors["sun_light"], 18, 17, 12, 12)
        block((255, 244, 147), 19, 16, 6, 5)
        block(colors["sun_dark"], 28, 28, 6, 5)

    elif element in {"nitrogen", "phosphorus", "potassium"}:
        key = {"nitrogen": "n", "phosphorus": "p", "potassium": "k"}[element]
        halo()
        polygon(colors["ink"], _reference_points(center, 16))
        polygon(colors[f"{key}_dark"], _reference_points(center, 14))
        polygon(colors[key], _reference_points(center, 12))
        polygon(colors[f"{key}_light"], ((18, 13), (28, 13), (33, 18), (33, 23), (18, 23)))
        block(colors[f"{key}_dark"], 15, 32, 18, 3)
        _draw_reference_glyph(sprite, {"n": "N", "p": "P", "k": "K"}[key], 17, 15, (255, 242, 193), colors[f"{key}_dark"])
        block(colors["halo"], 10, 10, 3, 3)
        block(colors["halo"], 35, 34, 3, 3)

    else:  # pesticide: a clearly readable spray bottle for plant health.
        halo()
        # Bottle body, liquid window, shoulder, trigger, nozzle, and spray
        # droplets.  The orange cross makes the health purpose unambiguous.
        block(colors["pest_dark"], 12, 15, 23, 24)
        block(colors["pest"], 14, 17, 18, 20)
        block(colors["pest_light"], 16, 19, 5, 12)
        block(colors["pest_dark"], 14, 12, 16, 6)
        block(colors["pest_light"], 17, 13, 10, 2)
        block(colors["pest_dark"], 19, 8, 9, 6)
        block(colors["pest_light"], 21, 9, 5, 2)
        block(colors["pest_dark"], 27, 6, 12, 4)
        block(colors["pest"], 34, 7, 8, 2)
        block(colors["pest_dark"], 25, 15, 6, 9)
        block(colors["pest_light"], 27, 16, 3, 5)
        block(colors["pest_red"], 20, 22, 9, 3)
        block(colors["pest_red"], 23, 19, 3, 9)
        block(colors["halo"], 38, 13, 3, 3)
        block(colors["halo"], 42, 10, 2, 2)
        block(colors["halo"], 44, 7, 2, 2)

    target = pygame.Rect(rect)
    scaled = pygame.transform.scale(sprite, target.size)
    surface.blit(scaled, target.topleft)


def draw_collect_break(surface: pygame.Surface, item: "Collectible") -> None:
    """Draw a short pixel-shard burst for a collected element."""
    progress = 1.0 - item.collect_remaining / ITEM_COLLECT_ANIMATION_DURATION
    progress = max(0.0, min(1.0, progress))
    rect = item.rect
    sprite = pygame.Surface(rect.size, pygame.SRCALPHA)
    draw_element_icon(sprite, item.element, sprite.get_rect())

    # Four pieces of the original sprite fly away from the pickup's center.
    half = rect.width // 2
    pieces = (
        (pygame.Rect(0, 0, half, half), (-1.0, -0.7)),
        (pygame.Rect(half, 0, rect.width - half, half), (1.0, -0.9)),
        (pygame.Rect(0, half, half, rect.height - half), (-1.2, 0.9)),
        (pygame.Rect(half, half, rect.width - half, rect.height - half), (1.2, 0.8)),
    )
    if progress < 0.22:
        surface.blit(sprite, rect.topleft)
    else:
        alpha = round(255 * (1.0 - progress))
        for area, (direction_x, direction_y) in pieces:
            fragment = pygame.Surface(area.size, pygame.SRCALPHA)
            fragment.blit(sprite, (0, 0), area)
            fragment.set_alpha(alpha)
            distance = 5.0 + progress * 18.0
            destination = (
                round(rect.left + area.left + direction_x * distance),
                round(rect.top + area.top + direction_y * distance),
            )
            surface.blit(fragment, destination)

    burst_color = (255, 238, 169, alpha if progress >= 0.22 else 255)
    center_x, center_y = rect.center
    burst_distance = 8 + round(progress * 18)
    for direction_x, direction_y, width, height in (
        (-1, -1, 3, 3), (1, -1, 4, 3), (-1, 1, 3, 4), (1, 1, 3, 3),
    ):
        burst = pygame.Surface((width, height), pygame.SRCALPHA)
        burst.fill(burst_color)
        surface.blit(
            burst,
            (
                center_x + direction_x * burst_distance - width // 2,
                center_y + direction_y * burst_distance - height // 2,
            ),
        )


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
    surface: PickupSurface | None = None
    collect_remaining: float = 0.0

    def __post_init__(self) -> None:
        # Keep direct/scripted construction compatible with the old high/low
        # item API while making the live game route explicit.
        if self.surface is None:
            self.surface = "air" if self.center_y <= ITEM_HIGH_CENTER_Y else "ground"

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
    def __init__(
        self,
        rng: random.Random | None = None,
        *,
        randomized_layout: bool = False,
    ) -> None:
        self.rng = rng or random.Random()
        self.randomized_layout = randomized_layout
        self.sampler = AdaptiveElementSampler(self.rng)
        self.items: list[Collectible] = []
        self.collecting_items: list[Collectible] = []
        self.spawn_remaining = ITEM_PAIR_INTERVAL * 0.65
        self._next_pair_id = 1

    def update(
        self,
        dt: float,
        speed: float,
        *,
        can_spawn: bool = True,
        platforms: Iterable[pygame.Rect] = (),
    ) -> tuple[Collectible, Collectible] | None:
        platforms = tuple(platforms)
        for item in self.items:
            item.update(dt, speed)
        self.items = [item for item in self.items if not item.is_offscreen]
        for item in self.collecting_items:
            item.update(dt, speed)
            item.collect_remaining = max(0.0, item.collect_remaining - dt)
        self.collecting_items = [
            item for item in self.collecting_items if item.collect_remaining > 0.0
        ]

        spawned_pair = None
        self.spawn_remaining -= dt
        if self.spawn_remaining <= 0.0 and can_spawn:
            spawned_pair = self.spawn_pair(platforms)
            self.spawn_remaining = ITEM_PAIR_INTERVAL
        elif self.spawn_remaining < 0.0:
            self.spawn_remaining = 0.0
        return spawned_pair

    def spawn_pair(
        self,
        platforms: Iterable[pygame.Rect] = (),
    ) -> tuple[Collectible, Collectible]:
        high_element, low_element = self.sampler.draw_pair()
        pair_id = self._next_pair_id
        self._next_pair_id += 1
        if self.randomized_layout:
            base_x = float(WINDOW_WIDTH + 25)
            air_x = base_x + self.rng.randint(0, RANDOM_ITEM_X_OFFSET)
            air_y = self.rng.choice(AIR_ITEM_CENTER_Y)
            platform_choices = [
                platform
                for platform in platforms
                if platform.right >= base_x
                and platform.left <= base_x + PLATFORM_ITEM_LOOKAHEAD
                and platform.right - ITEM_SIZE >= base_x
                and platform.width >= ITEM_SIZE
            ]
            if platform_choices and self.rng.random() < PLATFORM_ITEM_CHANCE:
                platform = self.rng.choice(platform_choices)
                min_x = max(round(base_x), platform.left)
                max_x = min(
                    round(base_x + PLATFORM_ITEM_LOOKAHEAD),
                    platform.right - ITEM_SIZE,
                )
                platform_x = self.rng.randint(min_x, max_x)
                first = Collectible(
                    float(platform_x),
                    platform.top - ITEM_SIZE // 2,
                    high_element,
                    pair_id,
                    surface="platform",
                )
            else:
                first = Collectible(
                    base_x + self.rng.randint(0, RANDOM_ITEM_X_OFFSET),
                    ITEM_LOW_CENTER_Y,
                    high_element,
                    pair_id,
                    surface="ground",
                )
            second = Collectible(
                float(air_x),
                air_y,
                low_element,
                pair_id,
                surface="air",
            )
        else:
            first = Collectible(
                float(WINDOW_WIDTH + 25),
                ITEM_HIGH_CENTER_Y,
                high_element,
                pair_id,
                surface="air",
            )
            second = Collectible(
                float(WINDOW_WIDTH + 25),
                ITEM_LOW_CENTER_Y,
                low_element,
                pair_id,
                surface="ground",
            )
        high, low = first, second
        self.items.extend((high, low))
        return high, low

    def collect_item(self, item: Collectible) -> bool:
        """Remove only the selected item and keep its pair visible."""
        if item not in self.items:
            return False
        self.items.remove(item)
        item.collect_remaining = ITEM_COLLECT_ANIMATION_DURATION
        self.collecting_items.append(item)
        return True

    def remove_pair(self, pair_id: int) -> None:
        self.items = [item for item in self.items if item.pair_id != pair_id]
