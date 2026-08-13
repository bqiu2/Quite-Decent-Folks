"""Pixel-art primitives and shared plant sprite rendering for the game.

The game deliberately draws at the final window resolution with hard-edged
rectangles and a limited palette.  Keeping these primitives in one place,
including the reference-inspired plant assets, prevents the analysis screen
and the playable levels from looking like three different games.
"""

from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

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

_STARDew_MENU_BACKGROUND: pygame.Surface | None = None
_STARDew_MENU_SCALED: dict[tuple[int, int], pygame.Surface] = {}
_PLANT_ASSET_CACHE: dict[tuple[str, int], pygame.Surface | None] = {}
_RUNNER_ASSET_CACHE: dict[tuple[str, int], pygame.Surface | None] = {}
_RUNNER_SHEET_CACHE: dict[str, tuple[tuple[pygame.Surface, ...], tuple[int, int]]] = {}

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


def draw_stardew_tutorial_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    title: str,
    subtitle: str | None = None,
    accent: tuple[int, int, int] = PALETTE["green_light"],
) -> pygame.Rect:
    """Draw a warm farm noticeboard and return its parchment content rect."""
    rect = pygame.Rect(rect)
    shadow = rect.move(8, 9)
    pygame.draw.rect(surface, (38, 28, 23), shadow)
    pygame.draw.rect(surface, (77, 47, 29), rect)
    pygame.draw.rect(surface, (151, 91, 43), rect.inflate(-5, -5))
    pygame.draw.rect(surface, (224, 155, 70), rect.inflate(-9, -9))
    inner = rect.inflate(-22, -22)
    pygame.draw.rect(surface, (241, 218, 163), inner)
    pygame.draw.rect(surface, (193, 154, 93), inner, 3)
    # Pixel notches make the frame feel assembled from timber rather than a
    # smooth rectangular overlay.
    for x, y in (
        (rect.left + 5, rect.top + 5),
        (rect.right - 11, rect.top + 5),
        (rect.left + 5, rect.bottom - 11),
        (rect.right - 11, rect.bottom - 11),
    ):
        pygame.draw.rect(surface, (52, 34, 26), (x, y, 6, 6))
    # Brass pins and a tiny leaf motif establish the farm-board language.
    for x, y in (
        (inner.left + 10, inner.top + 10),
        (inner.right - 16, inner.top + 10),
    ):
        pygame.draw.rect(surface, (104, 61, 32), (x + 2, y + 2, 7, 7))
        pygame.draw.rect(surface, (248, 196, 83), (x, y, 7, 7))
        pygame.draw.rect(surface, (255, 226, 123), (x + 1, y + 1, 3, 3))
    leaf_x = inner.right - 38
    leaf_y = inner.bottom - 23
    pygame.draw.rect(surface, (75, 127, 60), (leaf_x, leaf_y, 5, 14))
    pygame.draw.rect(surface, accent, (leaf_x - 8, leaf_y - 2, 10, 6))
    pygame.draw.rect(surface, (104, 159, 69), (leaf_x + 5, leaf_y + 5, 10, 6))
    title_font = pygame.font.Font(None, max(28, min(42, rect.width // 16)))
    title_surface = title_font.render(title, False, (91, 57, 32))
    surface.blit(title_surface, title_surface.get_rect(center=(rect.centerx, inner.top + 34)))
    pygame.draw.rect(surface, (180, 126, 58), (inner.left + 24, inner.top + 57, inner.width - 48, 3))
    if subtitle:
        subtitle_font = pygame.font.Font(None, max(18, min(24, rect.width // 32)))
        subtitle_surface = subtitle_font.render(subtitle, False, (117, 82, 49))
        surface.blit(subtitle_surface, subtitle_surface.get_rect(center=(rect.centerx, inner.top + 78)))
    return pygame.Rect(
        inner.left + 24,
        inner.top + 94,
        inner.width - 48,
        max(12, inner.height - 112),
    )


def draw_stardew_action_ribbon(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    *,
    fill: tuple[int, int, int] = (91, 137, 68),
) -> None:
    """Draw a centered green farm-sign ribbon for the primary action."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (53, 37, 27), rect.move(3, 4))
    pygame.draw.rect(surface, (99, 62, 35), rect)
    pygame.draw.rect(surface, fill, rect.inflate(-6, -6))
    pygame.draw.rect(surface, (181, 214, 105), (rect.left + 8, rect.top + 6, rect.width - 16, 3))
    font = pygame.font.Font(None, max(18, min(26, rect.height - 8)))
    label = font.render(text, False, PALETTE["cream"])
    surface.blit(label, label.get_rect(center=rect.center))


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


def draw_stardew_menu_backdrop(surface: pygame.Surface) -> None:
    """Fill a menu surface with the shared pixel-art manor courtyard."""
    global _STARDew_MENU_BACKGROUND

    if _STARDew_MENU_BACKGROUND is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "ui"
            / "stardew_manor_menu_background.png"
        )
        try:
            image = pygame.image.load(str(path))
            _STARDew_MENU_BACKGROUND = image.convert() if pygame.display.get_surface() else image.copy()
        except (FileNotFoundError, pygame.error):
            _STARDew_MENU_BACKGROUND = pygame.Surface((1, 1))
            _STARDew_MENU_BACKGROUND.fill((93, 139, 91))

    size = surface.get_size()
    background = _STARDew_MENU_SCALED.get(size)
    if background is None:
        source = _STARDew_MENU_BACKGROUND
        source_width, source_height = source.get_size()
        target_ratio = size[0] / max(1, size[1])
        source_ratio = source_width / max(1, source_height)
        if source_ratio > target_ratio:
            crop_width = max(1, round(source_height * target_ratio))
            source = source.subsurface(
                pygame.Rect((source_width - crop_width) // 2, 0, crop_width, source_height)
            ).copy()
        elif source_ratio < target_ratio:
            crop_height = max(1, round(source_width / target_ratio))
            source = source.subsurface(
                pygame.Rect(0, (source_height - crop_height) // 2, source_width, crop_height)
            ).copy()
        background = pygame.transform.scale(source, size)
        _STARDew_MENU_SCALED[size] = background

    surface.blit(background, (0, 0))
    # A subtle green veil keeps the parchment cards legible while preserving
    # the manor, path, flowers, and timber textures behind them.
    veil = pygame.Surface(size, pygame.SRCALPHA)
    veil.fill((28, 52, 31, 38))
    surface.blit(veil, (0, 0))


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


def _load_plant_asset(plant_type: str, size: int) -> pygame.Surface | None:
    """Load one of the reference-inspired pixel plant sprites at native scale.

    The source PNGs are intentionally transparent cut-outs.  Cropping their
    transparent padding here lets the same detailed sprite fit both the large
    analysis card and the small in-game plant carrier without introducing a
    second, simplified icon style.
    """
    key = (plant_type.lower(), int(size))
    if key in _PLANT_ASSET_CACHE:
        cached = _PLANT_ASSET_CACHE[key]
        return cached.copy() if cached is not None else None

    asset_path = Path(__file__).resolve().parents[1] / "assets" / "plants" / f"{key[0]}.png"
    try:
        image = pygame.image.load(str(asset_path))
        if pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        else:
            image = image.copy()
    except (pygame.error, OSError):
        _PLANT_ASSET_CACHE[key] = None
        return None

    # ``Surface.get_bounding_rect`` inspects the per-pixel alpha channel;
    # ``get_alpha`` only returns the surface-wide alpha integer.
    bounds = image.get_bounding_rect(min_alpha=1)
    if bounds.width and bounds.height:
        image = image.subsurface(bounds).copy()

    ratio = min(size / image.get_width(), size / image.get_height())
    target = (
        max(1, round(image.get_width() * ratio)),
        max(1, round(image.get_height() * ratio)),
    )
    # pygame.scale is nearest-neighbour here, preserving the square pixel
    # blocks from the supplied references instead of blurring their edges.
    scaled = pygame.transform.scale(image, target)
    _PLANT_ASSET_CACHE[key] = scaled
    return scaled.copy()


def _load_runner_asset(
    plant_type: str,
    frame: int,
    target_size: tuple[int, int],
    *,
    run_cycle: bool = False,
) -> pygame.Surface | None:
    """Load one full-body farmer pose carrying the selected potted plant."""
    plant_key = plant_type.lower()
    frame_key = max(0, min(15 if run_cycle else 3, int(frame)))
    key = (f"{plant_key}_run" if run_cycle else plant_key, frame_key)
    if key in _RUNNER_ASSET_CACHE:
        cached = _RUNNER_ASSET_CACHE[key]
        return cached.copy() if cached is not None else None

    if run_cycle and plant_key in _RUNNER_SHEET_CACHE:
        image = _RUNNER_SHEET_CACHE[plant_key][0][frame_key].copy()
    else:
        if run_cycle:
            asset_path = Path(__file__).resolve().parents[1] / "assets" / "runner" / f"{plant_key}_run_sheet.png"
        else:
            asset_path = Path(__file__).resolve().parents[1] / "assets" / "runner" / f"{plant_key}_{frame_key}.png"
        try:
            image = pygame.image.load(str(asset_path))
            if pygame.display.get_surface() is not None:
                image = image.convert_alpha()
            else:
                image = image.copy()
        except (pygame.error, OSError):
            _RUNNER_ASSET_CACHE[key] = None
            return None

    if run_cycle and plant_key not in _RUNNER_SHEET_CACHE:
        # The refined sheet is a 4x4 grid.  Extract every pose once, then
        # place all poses on one shared canvas.  This prevents per-frame
        # alpha bounds from changing the runner's apparent height or stride.
        columns = 4
        rows = 4
        extracted: list[pygame.Surface] = []
        for sheet_frame in range(16):
            column = sheet_frame % columns
            row = sheet_frame // columns
            cell_left = round(image.get_width() * column / columns)
            cell_right = round(image.get_width() * (column + 1) / columns)
            cell_top = round(image.get_height() * row / rows)
            cell_bottom = round(image.get_height() * (row + 1) / rows)
            cell_width = cell_right - cell_left
            cell_height = cell_bottom - cell_top
            safe_margin = max(2, round(min(cell_width, cell_height) * 0.012))
            frame_image = image.subsurface(
                pygame.Rect(
                    cell_left + safe_margin,
                    cell_top + safe_margin,
                    cell_width - safe_margin * 2,
                    cell_height - safe_margin * 2,
                )
            ).copy()

            # Remove any isolated edge pixels that were accidentally painted
            # into a neighbouring cell by the image generator.
            mask = pygame.mask.from_surface(frame_image, 1)
            components = mask.connected_components()
            if components:
                main_component = max(components, key=lambda component: component.count())
                cleaned = pygame.Surface(frame_image.get_size(), pygame.SRCALPHA)
                for pixel_y in range(frame_image.get_height()):
                    for pixel_x in range(frame_image.get_width()):
                        if main_component.get_at((pixel_x, pixel_y)):
                            cleaned.set_at((pixel_x, pixel_y), frame_image.get_at((pixel_x, pixel_y)))
                frame_image = cleaned

            bounds = frame_image.get_bounding_rect(min_alpha=1)
            if bounds.width and bounds.height:
                frame_image = frame_image.subsurface(bounds).copy()
            extracted.append(frame_image)

        canvas_width = max(frame.get_width() for frame in extracted)
        canvas_height = max(frame.get_height() for frame in extracted)
        normalized: list[pygame.Surface] = []
        for frame_image in extracted:
            frame_canvas = pygame.Surface((canvas_width, canvas_height), pygame.SRCALPHA)
            frame_canvas.blit(
                frame_image,
                (
                    (canvas_width - frame_image.get_width()) // 2,
                    canvas_height - frame_image.get_height(),
                ),
            )
            normalized.append(frame_canvas)
        _RUNNER_SHEET_CACHE[plant_key] = (tuple(normalized), (canvas_width, canvas_height))
        image = normalized[frame_key].copy()

    if not run_cycle:
        bounds = image.get_bounding_rect(min_alpha=1)
        if bounds.width and bounds.height:
            image = image.subsurface(bounds).copy()
    ratio = min(target_size[0] / image.get_width(), target_size[1] / image.get_height())
    scaled_size = (
        max(1, round(image.get_width() * ratio)),
        max(1, round(image.get_height() * ratio)),
    )
    scaled = pygame.transform.scale(image, scaled_size)
    _RUNNER_ASSET_CACHE[key] = scaled
    return scaled.copy()


def draw_pixel_plant(
    surface: pygame.Surface,
    center: tuple[int, int],
    plant_type: str,
    *,
    scale: int = 1,
) -> None:
    """Draw the detailed reference-inspired sprite for a plant class.

    All three classes use separately illustrated terracotta-pot assets.  The
    old procedural renderer below remains as a defensive fallback for a
    missing asset, but normal game runs use the PNGs in ``assets/plants``.
    """
    scale = max(1, int(scale))
    cx, cy = center

    # ``scale=1`` is used by the two gameplay sprites; the analysis preview
    # requests ``scale=4`` and gets a larger, still crisp version of the same
    # artwork.
    asset = _load_plant_asset(plant_type, 56 if scale == 1 else 320)
    if asset is not None:
        surface.blit(asset, asset.get_rect(center=(cx, cy)))
        return

    def block(x: int, y: int, width: int, height: int, color) -> None:
        pygame.draw.rect(
            surface,
            color,
            (cx + x * scale, cy + y * scale, width * scale, height * scale),
        )

    def poly(points: tuple[tuple[int, int], ...], color) -> None:
        pygame.draw.polygon(
            surface,
            color,
            tuple((cx + x * scale, cy + y * scale) for x, y in points),
        )

    plant_type = plant_type.lower()
    outline = (43, 35, 31)
    ground_shadow = (37, 51, 38)
    soil_dark = (86, 52, 37)
    soil_mid = (132, 77, 45)
    soil_light = (198, 120, 61)

    # Shared ground tile: an irregular patch of freshly watered earth instead
    # of the old pot silhouette.  Tiny stones and sprouts give it a hand-laid
    # Stardew farm-tile feel at both 1x and 4x.
    block(-24, 25, 48, 4, ground_shadow)
    poly(((-23, 18), (-16, 13), (15, 13), (23, 18), (19, 25), (-19, 25)), outline)
    poly(((-19, 18), (-14, 15), (14, 15), (19, 18), (16, 23), (-16, 23)), soil_dark)
    block(-13, 16, 25, 4, soil_mid)
    block(-9, 16, 9, 2, soil_light)
    block(11, 19, 5, 2, (69, 43, 34))
    block(-15, 21, 4, 3, (174, 102, 54))
    block(3, 22, 5, 2, (110, 62, 41))
    block(15, 15, 3, 3, (221, 169, 84))

    if plant_type == "grass":
        # A dense tuft of individual blades, with seed heads and wind-tilted
        # highlights.  Every blade has a dark offset silhouette.
        blade_specs = (
            (-18, -8, -22, -2, (37, 91, 53), (103, 164, 70)),
            (-13, 7, -27, -7, (47, 117, 59), (138, 193, 77)),
            (-8, 4, -34, -1, (32, 86, 50), (111, 177, 71)),
            (-2, 4, -38, 4, (41, 103, 55), (151, 202, 82)),
            (4, 6, -31, 14, (50, 123, 61), (140, 195, 76)),
            (10, 9, -26, 20, (35, 94, 52), (110, 171, 68)),
            (16, 8, -20, 22, (49, 112, 58), (129, 185, 71)),
        )
        for left, base, tip_y, tip_x, dark, light in blade_specs:
            right = left + 5
            poly(((left - 2, base + 2), (right + 2, base + 2), (tip_x, tip_y)), outline)
            poly(((left, base), (right, base), (tip_x, tip_y + 3)), dark)
            block(round((left + tip_x) / 2), tip_y + 5, 2, max(2, base - tip_y - 5), light)
        # Wheat-coloured seed heads and one curled grass tip.
        for x, y in ((-4, -40), (-10, -29), (13, -26)):
            block(x, y, 3, 5, (196, 166, 79))
            block(x + 2, y - 2, 3, 3, (239, 212, 116))
        block(-6, -42, 3, 2, (245, 220, 126))
        block(-20, -10, 3, 3, (173, 205, 78))
        block(15, -17, 3, 3, (183, 211, 84))
        return

    if plant_type == "shrub":
        # Branches remain visible beneath an asymmetrical canopy, avoiding the
        # old single geometric blob.  Leaf clusters use three greens and tiny
        # berries to create depth.
        block(-5, -2, 10, 19, outline)
        block(-2, -3, 5, 19, (105, 64, 39))
        poly(((-2, 5), (-17, -7), (-15, -10), (1, 1)), outline)
        poly(((3, 4), (16, -8), (19, -7), (5, 9)), outline)
        block(-1, 1, 3, 10, (171, 96, 48))

        clusters = (
            (-21, -12, 14, 15, (36, 91, 51)),
            (-14, -25, 17, 17, (42, 111, 57)),
            (-3, -31, 18, 18, (47, 121, 60)),
            (9, -24, 16, 17, (43, 107, 55)),
            (14, -11, 11, 14, (36, 94, 51)),
            (-14, -5, 29, 13, (39, 102, 53)),
        )
        for x, y, width, height, color in clusters:
            # Stepped octagons create soft, hand-pixeled leaf masses.
            outer = (
                (x + 3, y - 2),
                (x + width - 3, y - 2),
                (x + width + 2, y + 3),
                (x + width + 2, y + height - 3),
                (x + width - 3, y + height + 2),
                (x + 3, y + height + 2),
                (x - 2, y + height - 3),
                (x - 2, y + 3),
            )
            inner = (
                (x + 3, y),
                (x + width - 3, y),
                (x + width, y + 3),
                (x + width, y + height - 3),
                (x + width - 3, y + height),
                (x + 3, y + height),
                (x, y + height - 3),
                (x, y + 3),
            )
            poly(outer, outline)
            poly(inner, color)
        # Leaf planes, dappled highlights, and warm berries.
        for x, y, width, height in (
            (-17, -16, 8, 5),
            (-7, -27, 9, 5),
            (7, -20, 8, 5),
            (-10, -7, 10, 5),
            (8, -5, 7, 4),
        ):
            block(x, y, width, height, (91, 158, 67))
            block(x + 2, y, 3, 2, (159, 202, 87))
        for x, y, color in (
            (-13, -9, (213, 83, 63)),
            (3, -19, (226, 111, 58)),
            (13, -10, (194, 71, 58)),
            (-1, -2, (219, 95, 60)),
        ):
            block(x, y, 5, 5, outline)
            block(x + 1, y + 1, 3, 3, color)
            block(x + 1, y + 1, 1, 1, (255, 174, 101))
        block(17, -25, 5, 3, (111, 172, 67))
        block(-21, -3, 4, 3, (120, 184, 72))
        return

    # Flower: one large central blossom, a small side bud, layered leaves, and
    # a visible stem.  The flower has a dark under-petal silhouette so it stays
    # legible when carried by the runner or placed on the Level 2 rail.
    block(-4, -21, 8, 35, outline)
    block(-1, -22, 4, 34, (43, 111, 56))
    poly(((-2, -6), (-20, -1), (-18, 5), (-2, 1)), outline)
    poly(((3, -4), (19, 2), (17, 8), (3, 1)), outline)
    poly(((-2, -4), (-16, 0), (-15, 3), (-2, 0)), (56, 143, 65))
    poly(((3, -2), (16, 3), (15, 5), (3, 0)), (54, 136, 62))
    block(-13, 0, 6, 3, (143, 202, 79))
    block(10, 3, 5, 3, (121, 187, 72))
    block(-8, 7, 12, 4, (30, 87, 48))

    def bloom(x: int, y: int, petal: tuple[int, int, int], highlight: tuple[int, int, int], radius: int = 1) -> None:
        dark = (105, 49, 70)
        # A stepped eight-petal silhouette, built from pixel clusters rather
        # than a single geometric polygon.
        poly(
            (
                (x - 5 - radius, y - 13),
                (x + 5 + radius, y - 13),
                (x + 5 + radius, y - 8),
                (x + 12, y - 8),
                (x + 12, y + 3),
                (x + 6, y + 3),
                (x + 6, y + 10),
                (x - 6, y + 10),
                (x - 6, y + 4),
                (x - 12, y + 4),
                (x - 12, y - 7),
                (x - 6, y - 7),
                (x - 6, y - 13),
            ),
            outline,
        )
        block(x - 5, y - 11, 10, 18, dark)
        block(x - 4, y - 9, 8, 14, petal)
        block(x - 10, y - 5, 8, 8, petal)
        block(x + 3, y - 5, 8, 8, petal)
        block(x - 3, y - 12, 6, 5, petal)
        block(x - 3, y + 3, 6, 5, (178, 63, 101))
        block(x - 3, y - 8, 4, 4, highlight)
        block(x + 4, y - 2, 3, 4, dark)
        block(x - 2, y - 2, 5, 5, outline)
        block(x - 1, y - 1, 3, 3, (240, 173, 54))
        block(x, y, 2, 2, (255, 224, 100))

    bloom(0, -29, (213, 82, 124), (248, 143, 163), radius=2)
    # A little unopened bud gives the plant a natural growth-stage detail.
    block(-22, -16, 6, 9, outline)
    block(-21, -15, 4, 7, (186, 69, 108))
    block(-20, -14, 2, 3, (244, 132, 155))
    block(-22, -7, 6, 3, (232, 174, 72))


def draw_pixel_runner(
    surface: pygame.Surface,
    rect: pygame.Rect,
    plant_type: str,
    *,
    running_frame: int = 0,
    crouching: bool = False,
    jumping: bool = False,
) -> None:
    """Draw the new detailed farmer animation carrying the matching pot.

    The sixteen source poses form a full running cycle.  Jump and crouch use
    dedicated poses, and the explicit state flags take priority while the
    player is airborne or crouching.
    """
    x, y = rect.left, rect.top

    if crouching:
        pose = 3
        run_cycle = False
    elif jumping:
        pose = 2
        run_cycle = False
    else:
        pose = int(running_frame) % 16
        run_cycle = True
    asset = _load_runner_asset(
        plant_type,
        pose,
        (rect.width + 86, max(80, rect.height + 18)),
        run_cycle=run_cycle,
    )
    if asset is not None:
        # Keep the feet on the collision rectangle's bottom edge.  This makes
        # the generated poses animate in place without changing gameplay hit
        # boxes or making the pot float during a jump.
        destination = asset.get_rect(midbottom=(rect.centerx + 16, rect.bottom + 1))
        surface.blit(asset, destination)
        return

    # Defensive fallback for installations where optional generated assets
    # have not been copied yet.
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
