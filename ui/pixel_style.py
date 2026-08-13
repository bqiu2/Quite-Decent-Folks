"""Small, asset-free pixel-art primitives shared by the game screens.

The game deliberately draws at the final window resolution with hard-edged
rectangles and a limited palette.  Keeping these primitives in one place
prevents the analysis screen and the playable levels from looking like three
different games.
"""

from __future__ import annotations

from math import cos, pi, sin

import pygame


PALETTE = {
    "ink": (38, 43, 42),
    "deep_ink": (27, 31, 31),
    "cream": (250, 239, 196),
    "muted_cream": (207, 198, 158),
    "panel": (63, 78, 70),
    "panel_light": (111, 132, 98),
    "panel_shadow": (25, 32, 30),
    "gold": (222, 166, 69),
    "gold_light": (255, 222, 112),
    "green": (78, 157, 83),
    "green_light": (143, 207, 105),
    "red": (208, 75, 68),
    "blue": (71, 164, 213),
    "purple": (151, 109, 199),
    "wood": (132, 82, 54),
    "wood_light": (190, 119, 66),
    "soil": (91, 61, 47),
    "sky": (172, 209, 207),
    "sky_light": (226, 236, 205),
}

STATUS_KEYS = ("water", "light", "nitrogen", "phosphorus", "potassium", "pest")
STATUS_LABELS = ("WATER", "LIGHT", "N", "P", "K", "PEST")
STATUS_COLORS = (
    (68, 172, 225),
    (248, 197, 68),
    (88, 184, 101),
    (213, 101, 128),
    (157, 111, 202),
    (235, 105, 64),
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def draw_pixel_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    fill: tuple[int, int, int] = PALETTE["panel"],
    border: tuple[int, int, int] = PALETTE["gold"],
    shadow: bool = True,
    accent: tuple[int, int, int] | None = None,
) -> None:
    """Draw a layered, notched panel inspired by hand-made game menus."""
    rect = pygame.Rect(rect)
    if shadow:
        pygame.draw.rect(
            surface,
            PALETTE["panel_shadow"],
            rect.move(6, 6),
        )
    pygame.draw.rect(surface, border, rect)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, fill, inner)
    pygame.draw.rect(surface, PALETTE["panel_light"], (inner.left, inner.top, inner.width, 3))
    pygame.draw.rect(surface, PALETTE["panel_light"], (inner.left, inner.top, 3, inner.height))
    pygame.draw.rect(surface, PALETTE["deep_ink"], (inner.left, inner.bottom - 3, inner.width, 3))
    pygame.draw.rect(surface, PALETTE["deep_ink"], (inner.right - 3, inner.top, 3, inner.height))
    pygame.draw.rect(surface, (87, 104, 82), inner, 1)
    # Square corner notches and tiny brass-like fasteners add detail without
    # introducing anti-aliased shapes.
    notch = max(3, min(6, rect.width // 24))
    for corner_x, corner_y in (
        (rect.left, rect.top),
        (rect.right - notch, rect.top),
        (rect.left, rect.bottom - notch),
        (rect.right - notch, rect.bottom - notch),
    ):
        pygame.draw.rect(surface, PALETTE["deep_ink"], (corner_x, corner_y, notch, notch))
    for bolt_x, bolt_y in (
        (rect.left + 8, rect.top + 8),
        (rect.right - 12, rect.top + 8),
        (rect.left + 8, rect.bottom - 12),
        (rect.right - 12, rect.bottom - 12),
    ):
        pygame.draw.rect(surface, PALETTE["gold_light"], (bolt_x, bolt_y, 3, 3))
    if accent is not None:
        pygame.draw.rect(surface, accent, (rect.left + 2, rect.top + 9, 5, rect.height - 18))


def draw_pixel_wood_frame(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    fill: tuple[int, int, int] = PALETTE["deep_ink"],
) -> None:
    """Draw a warm timber-framed panel for the first-level HUD and overlays."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (39, 29, 27), rect.move(5, 6))
    pygame.draw.rect(surface, (61, 39, 29), rect)
    pygame.draw.rect(surface, (177, 113, 54), rect.inflate(-4, -4))
    inner = rect.inflate(-12, -12)
    pygame.draw.rect(surface, fill, inner)
    pygame.draw.rect(surface, (229, 166, 75), (inner.left, inner.top, inner.width, 3))
    pygame.draw.rect(surface, (104, 62, 39), (inner.left, inner.bottom - 4, inner.width, 4))
    pygame.draw.rect(surface, (82, 49, 35), (inner.left, inner.top, 4, inner.height))
    pygame.draw.rect(surface, (221, 151, 64), (inner.right - 4, inner.top, 4, inner.height))
    pygame.draw.rect(surface, (42, 31, 27), rect, 2)
    for x, y in (
        (rect.left + 8, rect.top + 8),
        (rect.right - 12, rect.top + 8),
        (rect.left + 8, rect.bottom - 12),
        (rect.right - 12, rect.bottom - 12),
    ):
        pygame.draw.rect(surface, (247, 207, 111), (x, y, 3, 3))


def draw_pixel_backdrop(
    surface: pygame.Surface,
    *,
    base: tuple[int, int, int] = PALETTE["sky"],
    horizon: int | None = None,
) -> None:
    """Paint a quiet tiled backdrop used by menus and result cards."""
    width, height = surface.get_size()
    surface.fill(base)
    horizon = horizon if horizon is not None else height
    for y in range(0, min(horizon, height), 32):
        shade = PALETTE["sky_light"] if (y // 32) % 2 == 0 else base
        pygame.draw.rect(surface, shade, (0, y, width, 32))
    for x in range(-32, width + 32, 64):
        pygame.draw.rect(surface, (198, 222, 194), (x, max(0, horizon - 42), 32, 4))
        pygame.draw.rect(surface, (151, 190, 158), (x + 36, max(0, horizon - 30), 12, 3))


def draw_pixel_badge(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    *,
    fill: tuple[int, int, int] = PALETTE["wood"],
    text_color: tuple[int, int, int] = PALETTE["cream"],
) -> None:
    """Draw a compact label plate with a crisp pixel border."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, PALETTE["deep_ink"], rect.move(2, 3))
    pygame.draw.rect(surface, fill, rect)
    pygame.draw.rect(surface, PALETTE["wood_light"], rect.inflate(-4, -4), 2)
    font = pygame.font.Font(None, max(16, min(24, rect.height - 7)))
    text = font.render(label, False, text_color)
    surface.blit(text, text.get_rect(center=rect.center))


def _hex_points(center: tuple[int, int], radius: float, value: float = 1.0) -> list[tuple[int, int]]:
    cx, cy = center
    scaled = radius * clamp01(value)
    return [
        (
            round(cx + cos(-pi / 2 + index * pi / 3) * scaled),
            round(cy + sin(-pi / 2 + index * pi / 3) * scaled),
        )
        for index in range(6)
    ]


def draw_status_hexagon(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    status,
    *,
    show_labels: bool = True,
    show_values: bool = False,
    title: str | None = None,
) -> None:
    """Draw the six-dimensional plant status radar chart."""
    cx, cy = center
    for level, color in (
        (1.0, (120, 139, 108)),
        (2 / 3, (91, 113, 92)),
        (1 / 3, (70, 91, 79)),
    ):
        pygame.draw.polygon(surface, color, _hex_points(center, radius, level), width=1)

    outer = _hex_points(center, radius)
    for point in outer:
        pygame.draw.line(surface, (70, 94, 92), center, point, 1)

    values = [clamp01(getattr(status, key, 0.0)) for key in STATUS_KEYS]
    fill_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    # Fill the actual data shape with a translucent green so the grid remains
    # visible underneath it.
    pygame.draw.polygon(
        fill_surface,
        (64, 190, 111, 145),
        [
            (
                round(cx + cos(-pi / 2 + index * pi / 3) * radius * values[index]),
                round(cy + sin(-pi / 2 + index * pi / 3) * radius * values[index]),
            )
            for index in range(6)
        ],
    )
    surface.blit(fill_surface, (0, 0))
    data_points = [
        (
            round(cx + cos(-pi / 2 + index * pi / 3) * radius * values[index]),
            round(cy + sin(-pi / 2 + index * pi / 3) * radius * values[index]),
        )
        for index in range(6)
    ]
    pygame.draw.polygon(surface, PALETTE["deep_ink"], data_points, width=4)
    pygame.draw.polygon(surface, PALETTE["gold_light"], data_points, width=2)
    for point, color in zip(data_points, STATUS_COLORS):
        pygame.draw.rect(surface, PALETTE["deep_ink"], (point[0] - 4, point[1] - 4, 9, 9))
        pygame.draw.rect(surface, color, (point[0] - 3, point[1] - 3, 7, 7))
    pygame.draw.rect(surface, PALETTE["cream"], (cx - 2, cy - 2, 5, 5))

    if title is not None:
        font = pygame.font.Font(None, 22)
        label = font.render(title, True, PALETTE["cream"])
        surface.blit(label, label.get_rect(center=(cx, cy - radius - 25)))

    if show_labels:
        label_font = pygame.font.Font(None, 16 if radius < 90 else 19)
        value_font = pygame.font.Font(None, 15)
        for index, (label_text, color, value) in enumerate(
            zip(STATUS_LABELS, STATUS_COLORS, values)
        ):
            angle = -pi / 2 + index * pi / 3
            label_center = (
                round(cx + cos(angle) * (radius + 21)),
                round(cy + sin(angle) * (radius + 21)),
            )
            label = label_font.render(label_text, False, color)
            surface.blit(label, label.get_rect(center=label_center))
            if show_values:
                value_text = value_font.render(f"{value:.2f}", False, PALETTE["muted_cream"])
                surface.blit(
                    value_text,
                    value_text.get_rect(center=(label_center[0], label_center[1] + 13)),
                )


def draw_power_readout(
    surface: pygame.Surface,
    position: tuple[int, int],
    current_power: float,
    initial_power: float | None = None,
    *,
    large: bool = False,
) -> None:
    """Draw a consistent power label and optional change indicator."""
    font = pygame.font.Font(None, 36 if large else 24)
    small_font = pygame.font.Font(None, 19)
    current = font.render(f"POWER  {current_power:05.1f}", False, PALETTE["gold_light"])
    surface.blit(current, position)
    if initial_power is not None:
        delta = current_power - initial_power
        color = PALETTE["green_light"] if delta >= 0 else PALETTE["red"]
        delta_text = small_font.render(
            f"START {initial_power:05.1f}   {delta:+.1f}",
            False,
            color,
        )
        surface.blit(delta_text, (position[0], position[1] + current.get_height() - 2))


def draw_pixel_plant(
    surface: pygame.Surface,
    center: tuple[int, int],
    plant_type: str,
    *,
    scale: int = 1,
) -> None:
    """Draw the three plant classes as chunky pixel sprites."""
    scale = max(1, int(scale))
    cx, cy = center

    def block(x: int, y: int, width: int, height: int, color) -> None:
        pygame.draw.rect(
            surface,
            color,
            (cx + x * scale, cy + y * scale, width * scale, height * scale),
        )

    # Shadow, pot rim, pot body, soil, and tiny ceramic highlights.
    block(-20, 25, 40, 5, (31, 42, 35))
    block(-15, 5, 30, 21, PALETTE["wood"])
    block(-17, 3, 34, 6, PALETTE["wood_light"])
    block(-13, 8, 26, 4, PALETTE["soil"])
    block(-10, 12, 3, 10, (158, 87, 54))
    block(7, 13, 3, 9, (82, 49, 42))
    block(-11, 23, 22, 3, (76, 45, 39))

    if plant_type == "grass":
        for x, top, width in ((-14, -18, 4), (-8, -28, 5), (-1, -36, 5), (7, -26, 5), (14, -18, 4)):
            block(x, top, width, 27 - top, (39, 106, 59))
            block(x + 1, top + 2, 2, 18 - top, (132, 199, 83))
            block(x + width - 1, top + 5, 2, 13, (27, 77, 51))
        block(-4, -37, 3, 4, (183, 218, 103))
        return

    if plant_type == "shrub":
        for x, y, width, height in (
            (-16, -15, 15, 15),
            (-4, -24, 18, 17),
            (9, -14, 15, 14),
            (-11, -5, 26, 11),
        ):
            block(x, y, width, height, (43, 119, 62))
            block(x + 2, y + 2, max(3, width // 3), 3, (96, 173, 74))
        for x, y in ((-11, -12), (2, -20), (14, -10), (-3, -4)):
            block(x, y, 5, 4, (137, 198, 82))
        block(7, -18, 4, 4, (28, 86, 53))
        return

    # Flower: stem, leaves, four block petals and a gold centre.
    block(-2, -24, 4, 28, (38, 111, 57))
    block(-14, -7, 14, 6, (51, 143, 67))
    block(2, -3, 14, 6, (51, 143, 67))
    block(-11, -5, 5, 3, (133, 202, 85))
    petal = (215, 83, 126)
    petal_light = (243, 124, 153)
    petal_dark = (151, 58, 91)
    block(-7, -42, 14, 12, petal)
    block(-18, -32, 13, 13, petal)
    block(5, -32, 13, 13, petal)
    block(-7, -20, 14, 10, petal)
    block(-4, -40, 7, 5, petal_light)
    block(-16, -30, 5, 5, petal_light)
    block(8, -30, 5, 5, petal_dark)
    block(-4, -32, 8, 10, (246, 186, 57))
    block(-2, -30, 4, 4, (255, 228, 111))


def draw_pixel_runner(
    surface: pygame.Surface,
    rect: pygame.Rect,
    plant_type: str,
    *,
    running_frame: int = 0,
    crouching: bool = False,
) -> None:
    """Draw a detailed farmer runner carrying the generated plant sprite."""
    x, y = rect.left, rect.top
    ink = (48, 37, 31)
    skin = (238, 177, 119)
    skin_light = (255, 211, 147)
    hair = (76, 48, 34)
    hat = (205, 143, 67)
    hat_light = (247, 196, 101)
    shirt = (53, 111, 74)
    shirt_light = (101, 165, 84)
    pants = (65, 67, 70)
    boot = (55, 42, 36)
    accent = (238, 177, 66)
    if crouching:
        pygame.draw.rect(surface, ink, (x + 3, y + 34, 40, 8))
        pygame.draw.rect(surface, pants, (x + 6, y + 30, 32, 10))
        pygame.draw.rect(surface, boot, (x + 4, y + 38, 15, 6))
        pygame.draw.rect(surface, boot, (x + 27, y + 37, 15, 6))
        pygame.draw.rect(surface, ink, (x + 5, y + 14, 31, 20))
        pygame.draw.rect(surface, shirt, (x + 7, y + 15, 28, 17))
        pygame.draw.rect(surface, shirt_light, (x + 10, y + 17, 8, 7))
        pygame.draw.rect(surface, skin, (x + 2, y + 8, 15, 12))
        pygame.draw.rect(surface, skin_light, (x + 5, y + 10, 9, 6))
        pygame.draw.rect(surface, hair, (x + 2, y + 6, 16, 5))
        pygame.draw.rect(surface, skin, (x + 29, y + 21, 10, 6))
        pygame.draw.rect(surface, accent, (x + 21, y + 19, 8, 4))
        draw_pixel_plant(surface, (x + 43, y + 42), plant_type, scale=1)
        return

    swing = 4 if running_frame % 2 == 0 else -4
    pygame.draw.rect(surface, ink, (x + 9 + swing, y + 43, 11, 26))
    pygame.draw.rect(surface, pants, (x + 12 + swing, y + 44, 7, 22))
    pygame.draw.rect(surface, ink, (x + 24 - swing, y + 43, 11, 26))
    pygame.draw.rect(surface, pants, (x + 25 - swing, y + 44, 7, 22))
    pygame.draw.rect(surface, boot, (x + 6 + swing, y + 66, 17, 7))
    pygame.draw.rect(surface, boot, (x + 21 - swing, y + 66, 17, 7))
    pygame.draw.rect(surface, ink, (x + 8, y + 18, 27, 29))
    pygame.draw.rect(surface, shirt, (x + 11, y + 21, 21, 24))
    pygame.draw.rect(surface, shirt_light, (x + 13, y + 24, 5, 12))
    pygame.draw.rect(surface, accent, (x + 26, y + 23, 4, 15))
    pygame.draw.rect(surface, ink, (x + 4, y + 21, 9, 22))
    pygame.draw.rect(surface, skin, (x + 3, y + 39, 10, 6))
    pygame.draw.rect(surface, skin_light, (x + 4, y + 40, 6, 3))
    pygame.draw.rect(surface, ink, (x + 31, y + 22, 9, 20))
    pygame.draw.rect(surface, skin, (x + 37, y + 37, 8, 6))
    pygame.draw.rect(surface, ink, (x + 11, y + 3, 22, 18))
    pygame.draw.rect(surface, skin, (x + 14, y + 6, 16, 13))
    pygame.draw.rect(surface, skin_light, (x + 16, y + 8, 9, 5))
    pygame.draw.rect(surface, hair, (x + 13, y + 3, 19, 6))
    pygame.draw.rect(surface, ink, (x + 8, y + 1, 30, 7))
    pygame.draw.rect(surface, hat, (x + 12, y - 3, 22, 8))
    pygame.draw.rect(surface, hat_light, (x + 15, y - 5, 15, 5))
    pygame.draw.rect(surface, (168, 105, 48), (x + 8, y + 4, 30, 4))
    pygame.draw.rect(surface, (246, 212, 119), (x + 13, y + 5, 18, 2))
    pygame.draw.rect(surface, ink, (x + 27, y + 12, 3, 3))
    # Keep the carried plant at the farmer's side so the face, hat, and
    # running pose remain readable against the busy forest backdrop.
    draw_pixel_plant(surface, (x + 46, y + 57), plant_type, scale=1)
