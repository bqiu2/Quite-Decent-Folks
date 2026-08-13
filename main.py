"""End-to-end launcher for the plant game.

The game can be started with an image path::

    python main.py uploads/my_plant.jpg

When no path is supplied, a native file picker is opened.  ``--demo`` is
provided for development machines that do not have the AI model available.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import os
import sys

from shared_game_data import (
    DIFFICULTIES,
    DifficultyConfig,
    FinalResult,
    PlantData,
    calculate_final_score,
    save_game_result,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULT_DIR = PROJECT_ROOT / "data"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete plant game.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("image", nargs="?", help="Plant image to analyze.")
    source.add_argument(
        "--demo",
        action="store_true",
        help="Use the built-in demo plant and skip model inference.",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default=None,
        help="Device used by the plant model.",
    )
    parser.add_argument(
        "--difficulty",
        choices=tuple(DIFFICULTIES),
        default=None,
        help="Skip the difficulty picker and use this difficulty.",
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Use keyboard controls for Level 1 instead of the pose camera.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON result path; defaults to data/result_<plant_id>.json.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Print the final result and exit without waiting on the result screen.",
    )
    return parser.parse_args()


def _choose_image() -> Path | None:
    """Open a native image picker, returning None when the user cancels."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("Tkinter is unavailable; pass the image path on the command line.")
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            title="Choose a plant image",
            filetypes=(
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ),
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None


def _resolve_image(explicit_path: str | None) -> Path | None:
    image_path = Path(explicit_path) if explicit_path else _choose_image()
    if image_path is None:
        return None
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return image_path.resolve()


def _show_analysis_preview(plant: PlantData) -> bool:
    """Show the analyzed plant before handing control to Level 1."""
    import pygame

    from ui.pixel_style import (
        PALETTE,
        STATUS_COLORS,
        STATUS_KEYS,
        STATUS_LABELS,
        draw_pixel_backdrop,
        draw_pixel_badge,
        draw_pixel_panel,
        draw_pixel_plant,
        draw_power_readout,
        draw_status_hexagon,
    )

    pygame.init()
    # The analysis view has six labels, values, a power readout, and a
    # generated sprite.  Give those elements their own vertical breathing
    # room instead of forcing the legend against the card edge.
    screen = pygame.display.set_mode((1120, 720))
    pygame.display.set_caption("Plant Game - Analysis Complete")
    title_font = pygame.font.Font(None, 48)
    body_font = pygame.font.Font(None, 25)
    small_font = pygame.font.Font(None, 21)
    clock = pygame.time.Clock()

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return True
                    if event.key == pygame.K_ESCAPE:
                        return False

            draw_pixel_backdrop(screen, base=(188, 216, 205), horizon=665)
            pygame.draw.rect(screen, (153, 190, 153), (0, 665, 1120, 55))
            for x in range(0, 1120, 48):
                pygame.draw.rect(screen, (111, 157, 112), (x + 8, 665, 22, 4))

            header = pygame.Rect(24, 20, 1072, 108)
            draw_pixel_panel(
                screen,
                header,
                fill=PALETTE["deep_ink"],
                border=PALETTE["gold"],
                shadow=True,
                accent=PALETTE["green"],
            )
            title = title_font.render("PLANT ANALYSIS COMPLETE", False, PALETTE["gold_light"])
            screen.blit(title, (52, 36))
            subtitle = body_font.render(
                f"ID  {plant.plant_id}    CLASS  {plant.plant_type.upper()}",
                False,
                PALETTE["cream"],
            )
            subtitle_box = pygame.Rect(575, 39, 320, 62)
            pygame.draw.rect(screen, PALETTE["panel"], subtitle_box)
            pygame.draw.rect(screen, PALETTE["panel_light"], subtitle_box, 2)
            screen.blit(subtitle, subtitle.get_rect(center=subtitle_box.center))
            draw_pixel_badge(screen, pygame.Rect(918, 52, 150, 30), "SCAN READY", fill=PALETTE["green"])

            left_card = pygame.Rect(35, 150, 510, 500)
            right_card = pygame.Rect(575, 150, 510, 500)
            draw_pixel_panel(screen, left_card, fill=PALETTE["panel"], accent=PALETTE["blue"])
            draw_pixel_panel(screen, right_card, fill=PALETTE["panel"], accent=PALETTE["green"])

            left_title = body_font.render("HEALTH RADAR  /  6 DIMENSIONS", False, PALETTE["cream"])
            screen.blit(left_title, (62, 177))
            pygame.draw.rect(screen, (101, 125, 94), (62, 207, 456, 2))
            draw_status_hexagon(
                screen,
                (290, 315),
                92,
                plant.status,
                show_labels=True,
                show_values=True,
            )
            draw_power_readout(screen, (82, 480), plant.initial_power, large=True)
            power_note = small_font.render(
                "Initial power = weakest nutrient x pest health",
                False,
                PALETTE["muted_cream"],
            )
            screen.blit(power_note, (82, 538))

            right_title = body_font.render("GENERATED PIXEL FORM", False, PALETTE["cream"])
            screen.blit(right_title, (602, 177))
            pygame.draw.rect(screen, (101, 125, 94), (602, 207, 456, 2))
            draw_pixel_plant(screen, (830, 350), plant.plant_type, scale=4)
            form_label = title_font.render(plant.plant_type.upper(), False, PALETTE["gold_light"])
            screen.blit(form_label, form_label.get_rect(center=(830, 480)))
            detail = small_font.render(
                "YOUR HERO FORM / READY FOR LEVEL 1",
                False,
                PALETTE["muted_cream"],
            )
            screen.blit(detail, detail.get_rect(center=(830, 514)))
            pygame.draw.rect(screen, (101, 125, 94), (602, 545, 456, 2))

            # A compact color key makes the radar readable at a glance.
            for index, (label, color, key) in enumerate(
                zip(STATUS_LABELS, STATUS_COLORS, STATUS_KEYS)
            ):
                x = 62 + (index % 3) * 150
                y = 570 + (index // 3) * 27
                pygame.draw.rect(screen, PALETTE["deep_ink"], (x - 2, y, 12, 12))
                pygame.draw.rect(screen, color, (x, y + 2, 8, 8))
                value = getattr(plant.status, key)
                text = small_font.render(f"{label} {value:.2f}", False, PALETTE["cream"])
                screen.blit(text, (x + 13, y - 2))

            hint = small_font.render(
                "ENTER / SPACE  START RUNNER     ESC  CANCEL",
                False,
                PALETTE["deep_ink"],
            )
            screen.blit(hint, hint.get_rect(center=(560, 694)))
            pygame.display.flip()
            clock.tick(30)
    finally:
        pygame.display.quit()


def _difficulty_picker() -> DifficultyConfig | None:
    """Let the player choose easy/normal/hard before Level 2."""
    import pygame

    from ui.pixel_style import PALETTE, draw_pixel_backdrop, draw_pixel_badge, draw_pixel_panel

    pygame.init()
    screen = pygame.display.set_mode((820, 520))
    pygame.display.set_caption("Plant Game - Choose Difficulty")
    title_font = pygame.font.Font(None, 46)
    body_font = pygame.font.Font(None, 28)
    small_font = pygame.font.Font(None, 23)
    names = ("easy", "normal", "hard")
    selected = 1
    clock = pygame.time.Clock()

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    selected = (selected - 1) % len(names)
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    selected = (selected + 1) % len(names)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    selected = event.key - pygame.K_1
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return DIFFICULTIES[names[selected]]
                elif event.key == pygame.K_ESCAPE:
                    return None

            draw_pixel_backdrop(screen, base=(177, 210, 198), horizon=460)
            pygame.draw.rect(screen, (103, 157, 111), (0, 460, 820, 60))
            header = pygame.Rect(24, 20, 772, 125)
            draw_pixel_panel(screen, header, fill=PALETTE["deep_ink"], accent=PALETTE["gold"])
            title = title_font.render("CHOOSE DIFFICULTY", False, PALETTE["gold_light"])
            screen.blit(title, title.get_rect(center=(410, 68)))
            hint = body_font.render(
                "Use 1/2/3 or arrow keys, then press Enter", False, PALETTE["cream"]
            )
            screen.blit(hint, hint.get_rect(center=(410, 112)))

            for index, name in enumerate(names):
                rect = pygame.Rect(55 + index * 255, 180, 210, 170)
                active = index == selected
                draw_pixel_panel(
                    screen,
                    rect,
                    fill=(74, 132, 84) if active else PALETTE["panel"],
                    border=PALETTE["gold_light"] if active else PALETTE["panel_light"],
                    accent=PALETTE["green_light"] if active else PALETTE["wood"],
                )
                draw_pixel_badge(screen, pygame.Rect(rect.left + 12, rect.top + 12, 30, 24), str(index + 1), fill=PALETTE["wood"])
                label = title_font.render(name.upper(), False, PALETTE["cream"])
                screen.blit(label, label.get_rect(center=(rect.centerx, rect.top + 51)))
                config = DIFFICULTIES[name]
                detail = small_font.render(
                    f"HP x{config.zombie_hp_multiplier:.1f}  "
                    f"speed x{config.zombie_speed_multiplier:.1f}",
                    False,
                    PALETTE["muted_cream"],
                )
                screen.blit(detail, detail.get_rect(center=(rect.centerx, rect.top + 112)))
                detail2 = small_font.render(
                    f"count x{config.zombie_count_multiplier:.1f}  "
                    f"score x{config.score_multiplier:.1f}",
                    False,
                    PALETTE["muted_cream"],
                )
                screen.blit(detail2, detail2.get_rect(center=(rect.centerx, rect.top + 141)))

            pygame.display.flip()
            clock.tick(30)
    finally:
        pygame.display.quit()


def _show_final_result(result: FinalResult) -> None:
    """Display the final score until the player closes the result screen."""
    import pygame

    from ui.pixel_style import PALETTE, draw_pixel_backdrop, draw_pixel_badge, draw_pixel_panel

    pygame.init()
    screen = pygame.display.set_mode((800, 560))
    pygame.display.set_caption("Plant Game - Final Result")
    title_font = pygame.font.Font(None, 48)
    body_font = pygame.font.Font(None, 28)
    small_font = pygame.font.Font(None, 23)
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)
            ):
                pygame.quit()
                return

        draw_pixel_backdrop(screen, base=(178, 208, 197), horizon=490)
        pygame.draw.rect(screen, (102, 151, 108), (0, 490, 800, 70))
        color = (255, 222, 96) if result.victory else (235, 104, 85)
        card = pygame.Rect(75, 28, 650, 450)
        draw_pixel_panel(screen, card, fill=PALETTE["deep_ink"], border=color, accent=color)
        draw_pixel_badge(screen, pygame.Rect(100, 52, 112, 28), "RUN COMPLETE", fill=PALETTE["green"])
        title = title_font.render("VICTORY" if result.victory else "DEFEAT", False, color)
        screen.blit(title, title.get_rect(center=(400, 72)))
        rows = (
            f"Plant ID: {result.plant_id}   Type: {result.plant_type}",
            f"Initial power: {result.initial_power:.2f}",
            f"Final power: {result.final_power:.2f}",
            f"Level 1 score: {result.level1_score:.2f}",
            f"Level 2 score: {result.level2_score:.2f}",
            f"Difficulty: {result.difficulty.upper()} (x{result.difficulty_multiplier:.1f})",
        )
        for index, row in enumerate(rows):
            text = body_font.render(row, False, PALETTE["cream"])
            screen.blit(text, text.get_rect(center=(400, 145 + index * 42)))
        pygame.draw.rect(screen, PALETTE["panel_light"], (145, 382, 510, 3))
        final_text = title_font.render(f"FINAL SCORE  {result.final_score:.2f}", False, color)
        screen.blit(final_text, final_text.get_rect(center=(400, 410)))
        hint = small_font.render("Press Enter, Space or Escape to close", False, PALETTE["muted_cream"])
        screen.blit(hint, hint.get_rect(center=(400, 530)))
        pygame.display.flip()
        clock.tick(30)


def _load_plant(args: argparse.Namespace) -> PlantData:
    if args.demo:
        from level1.demo_data import create_demo_plant

        plant = create_demo_plant()
        print("Using demo plant:", plant.plant_id)
        return plant

    image_path = _resolve_image(args.image)
    if image_path is None:
        raise RuntimeError("No image selected; the game was cancelled.")

    print(f"Analyzing plant image: {image_path}")
    from plant_ai import analyze_plant

    plant = analyze_plant(str(image_path), device=args.device)
    print(
        f"Plant {plant.plant_id}: {plant.plant_type}, "
        f"initial power {plant.initial_power:.2f}"
    )
    return plant


def run_game(args: argparse.Namespace) -> int:
    if args.no_wait:
        os.environ["PLANT_GAME_SKIP_TUTORIAL"] = "1"

    plant = _load_plant(args)

    if not args.no_wait and not _show_analysis_preview(plant):
        print("Plant analysis was cancelled.")
        return 1

    from level1 import run_level1

    print("Starting Level 1...")
    level1_result = run_level1(plant, use_camera=not args.no_camera)
    if not level1_result.completed:
        print("Level 1 was cancelled; no final result was created.")
        return 1

    difficulty = (
        DIFFICULTIES[args.difficulty]
        if args.difficulty is not None
        else _difficulty_picker()
    )
    if difficulty is None:
        print("Difficulty selection was cancelled.")
        return 1

    from level2 import run_level2

    print(f"Starting Level 2 ({difficulty.name})...")
    level2_result = run_level2(plant, difficulty)
    final_result = calculate_final_score(
        plant,
        level1_result,
        level2_result,
        difficulty,
    )

    output_path = args.output or (
        DEFAULT_RESULT_DIR / f"result_{final_result.plant_id}.json"
    )
    save_game_result(final_result, str(output_path))
    print("Final result:")
    print(asdict(final_result))
    print(f"Saved to: {output_path.resolve()}")

    if not args.no_wait:
        _show_final_result(final_result)
    return 0


def main() -> int:
    args = _parse_args()
    try:
        return run_game(args)
    except KeyboardInterrupt:
        print("\nGame interrupted.")
        return 130
    except Exception as exc:
        print(f"Game could not start: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
