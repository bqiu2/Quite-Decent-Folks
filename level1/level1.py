"""Playable level-one runner and the team's required ``run_level1`` API."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict
import random
from typing import Literal

import pygame

from shared_game_data import (
    ElementType,
    Level1Result,
    PlantData,
    PlantStatus,
    PoseAction,
    apply_element,
    clamp,
)

from .collision import all_collisions
from .audio import AudioManager
from .config import (
    CAMERA_PREVIEW_HEIGHT,
    CAMERA_PREVIEW_MARGIN,
    CAMERA_PREVIEW_WIDTH,
    ITEM_OBSTACLE_CLEARANCE,
    ITEM_SIZE,
    LOWER_FLOOR_Y,
    MAX_HP,
    OBSTACLE_MIN_CLEARANCE,
    TARGET_FPS,
    TIME_LIMIT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    RANDOM_ITEM_X_OFFSET,
    PLATFORM_ITEM_LOOKAHEAD,
    scroll_speed_at,
)
from .items import (
    ELEMENT_TYPES,
    Collectible,
    ItemManager,
    draw_collect_break,
    draw_element_icon,
)
from .map import Obstacle, ObstacleManager, ScrollingMap
from .player import Player
from vision.camera_pose_input import CameraPoseInput
from vision.pose_control import GestureAction
from ui.pixel_style import (
    PALETTE,
    draw_pixel_backdrop,
    draw_pixel_panel,
    draw_pixel_plant,
    draw_pixel_runner,
    draw_power_readout,
    draw_status_hexagon,
    draw_pixel_badge,
    draw_pixel_wood_frame,
)


ActionProvider = Callable[[], PoseAction]
ControlMode = Literal["keyboard", "camera"]
STATUS_FIELDS = ("water", "light", "nitrogen", "phosphorus", "potassium")


def _horizontal_gap(
    first_x: float,
    first_width: float,
    second_x: float,
    second_width: float,
) -> float:
    first_right = first_x + first_width
    second_right = second_x + second_width
    if first_right < second_x:
        return second_x - first_right
    if second_right < first_x:
        return first_x - second_right
    return 0.0


def _status_snapshot(status: PlantStatus) -> dict[str, float]:
    return {
        "water": status.water,
        "light": status.light,
        "nitrogen": status.nitrogen,
        "phosphorus": status.phosphorus,
        "potassium": status.potassium,
        "pest": status.pest,
    }


def _state_score(values: dict[str, float]) -> float:
    nutrients = sum(values[field] for field in STATUS_FIELDS)
    pest_penalty = 1.0 - values["pest"]
    return max(0.01, nutrients - pest_penalty)


def calculate_level1_score(
    initial_status: dict[str, float],
    final_status: PlantStatus,
    remaining_hp: int,
) -> float:
    """Calculate the agreed 0..100 first-level score."""
    final_values = _status_snapshot(final_status)
    growth_ratio = _state_score(final_values) / _state_score(initial_status)
    weakest_nutrient = min(final_values[field] for field in STATUS_FIELDS)
    hp_factor = clamp(remaining_hp / MAX_HP, 0.0, 1.0)
    score = growth_ratio * weakest_nutrient * hp_factor * 100.0
    return round(clamp(score, 0.0, 100.0), 2)


class Level1Game:
    """Stateful game core that can be stepped without owning a camera."""

    def __init__(
        self,
        plant: PlantData,
        *,
        rng: random.Random | None = None,
    ) -> None:
        self.plant = plant
        self.rng = rng or random.Random()
        self.player = Player()
        # Keep the obstacle RNG contract deterministic for scripted tests and
        # let the visual platform layer own its independent random stream.
        self.world = ScrollingMap()
        self.obstacles = ObstacleManager(self.rng)
        # Item placement is intentionally independent from obstacle RNG so
        # adding randomized collectibles cannot change obstacle difficulty.
        self.items = ItemManager(random.Random(), randomized_layout=True)

        self.elapsed = 0.0
        self.power_before = plant.current_power
        self.initial_status = _status_snapshot(plant.status)
        self.pest_hits = 0
        self.collected: dict[ElementType, int] = {
            element: 0 for element in ELEMENT_TYPES
        }
        self.finished = False
        self.aborted = False
        self.audio_events: list[tuple[str, ElementType | None]] = []

    @property
    def scroll_speed(self) -> float:
        return scroll_speed_at(self.elapsed)

    def handle_action(self, action: GestureAction | str) -> bool:
        if action == "jump":
            return self.player.jump()
        if action == "big_jump":
            return self.player.big_jump()
        if action == "crouch":
            return self.player.slide()
        if action == "drop":
            return self.player.drop()
        return False

    def update(self, dt: float, actions: Iterable[GestureAction] = ()) -> None:
        if self.finished:
            return

        # A capped step keeps collision reliable after window dragging or pauses.
        dt = min(max(0.0, dt), 0.05)
        for action in actions:
            self.handle_action(action)

        self.elapsed = min(TIME_LIMIT, self.elapsed + dt)
        speed = self.scroll_speed
        self.world.update(dt, speed)
        new_obstacles = self.obstacles.update(dt, self.elapsed, speed)
        self._reject_clumped_obstacles(new_obstacles)
        item_spawn_due = self.items.spawn_remaining <= dt
        platforms = tuple(platform.rect for platform in self.world.air_platforms.platforms)
        can_spawn_item = (
            self._reserve_item_spawn_window(speed, platforms=platforms)
            if item_spawn_due
            else True
        )
        self.items.update(
            dt,
            speed,
            can_spawn=can_spawn_item,
            platforms=platforms,
        )
        self.player.update(dt, platforms)
        self._resolve_collisions()

        if self.elapsed >= TIME_LIMIT or self.player.hp <= 0:
            self.finished = True

    def _reject_clumped_obstacles(
        self,
        new_obstacles: list[Obstacle],
    ) -> None:
        accepted_obstacles: list[Obstacle] = []
        new_obstacle_ids = {id(item) for item in new_obstacles}
        existing_obstacles = [
            item
            for item in self.obstacles.obstacles
            if id(item) not in new_obstacle_ids
        ]
        rejected_obstacles: list[Obstacle] = []
        for obstacle in new_obstacles:
            conflicts_with_obstacle = any(
                _horizontal_gap(
                    obstacle.x,
                    obstacle.width,
                    other.x,
                    other.width,
                ) < OBSTACLE_MIN_CLEARANCE
                for other in (*existing_obstacles, *accepted_obstacles)
            )
            if conflicts_with_obstacle:
                rejected_obstacles.append(obstacle)
            else:
                accepted_obstacles.append(obstacle)

        if rejected_obstacles:
            rejected_ids = {id(item) for item in rejected_obstacles}
            self.obstacles.obstacles = [
                item
                for item in self.obstacles.obstacles
                if id(item) not in rejected_ids
            ]
            self.obstacles.total_spawned -= len(rejected_obstacles)
            self.obstacles.clusters_spawned -= sum(
                item.clustered for item in rejected_obstacles
            )
            if (
                self.obstacles.last_obstacle is not None
                and id(self.obstacles.last_obstacle) in rejected_ids
            ):
                self.obstacles.last_obstacle = (
                    self.obstacles.obstacles[-1]
                    if self.obstacles.obstacles
                    else None
                )

    def _reserve_item_spawn_window(
        self,
        speed: float,
        *,
        platforms: Iterable[pygame.Rect] = (),
    ) -> bool:
        candidate_x = WINDOW_WIDTH + 25.0
        spawn_bands = [
            (candidate_x, candidate_x + RANDOM_ITEM_X_OFFSET + ITEM_SIZE)
        ]
        for platform in platforms:
            if platform.right < candidate_x or platform.left > candidate_x + PLATFORM_ITEM_LOOKAHEAD:
                continue
            band_left = max(candidate_x, float(platform.left))
            band_right = min(
                candidate_x + PLATFORM_ITEM_LOOKAHEAD,
                float(platform.right - ITEM_SIZE),
            ) + ITEM_SIZE
            if band_right >= band_left:
                spawn_bands.append((band_left, band_right))

        for obstacle in self.obstacles.obstacles:
            obstacle_left = obstacle.x
            obstacle_right = obstacle.x + obstacle.width
            for spawn_left, spawn_right in spawn_bands:
                if obstacle_right >= spawn_left and obstacle_left <= spawn_right:
                    return False
                gap = spawn_left - obstacle_right if obstacle_right < spawn_left else obstacle_left - spawn_right
                if gap < ITEM_OBSTACLE_CLEARANCE:
                    return False

        future_delays = [self.obstacles.spawn_remaining]
        if self.obstacles.cluster_remaining is not None:
            future_delays.append(self.obstacles.cluster_remaining)
        required_travel = (
            ITEM_OBSTACLE_CLEARANCE
            + ITEM_SIZE
            + RANDOM_ITEM_X_OFFSET
            + (PLATFORM_ITEM_LOOKAHEAD if len(spawn_bands) > 1 else 0)
            + 2.0 * max(speed, 1.0) / TARGET_FPS
        )
        required_delay = required_travel / max(speed, 1.0)
        earliest_delay = min(future_delays)
        if earliest_delay < required_delay:
            schedule_shift = required_delay - earliest_delay
            self.obstacles.spawn_remaining += schedule_shift
            if self.obstacles.cluster_remaining is not None:
                self.obstacles.cluster_remaining += schedule_shift
        return True

    def _resolve_collisions(self) -> None:
        player_rect = self.player.rect

        for obstacle in all_collisions(player_rect, self.obstacles.obstacles):
            if obstacle.hit:
                continue
            obstacle.hit = True
            if self.player.take_damage():
                self.pest_hits += 1
                self.audio_events.append(("hurt", None))

        item_hits = [
            item
            for item in self.items.items
            if player_rect.colliderect(item.rect) and self._can_collect_item(item)
        ]
        if item_hits:
            item = item_hits[0]
            apply_element(self.plant, item.element)
            self.collected[item.element] += 1
            self.items.collect_item(item)
            self.audio_events.append(("collect", item.element))

    def _can_collect_item(self, item: Collectible) -> bool:
        """Enforce the route rule: air pickups need a jump, lane pickups do not."""
        if item.surface == "air":
            return not self.player.grounded
        if not self.player.grounded:
            return False
        if item.surface == "platform":
            return self.player.support_y is not None
        return self.player.support_y is None

    def consume_audio_events(self) -> list[tuple[str, ElementType | None]]:
        events = self.audio_events
        self.audio_events = []
        return events

    def abort(self) -> None:
        self.aborted = True
        self.finished = True

    def make_result(self) -> Level1Result:
        score = calculate_level1_score(
            self.initial_status,
            self.plant.status,
            self.player.hp,
        )
        return Level1Result(
            completed=not self.aborted,
            remaining_hp=self.player.hp,
            time_survived=round(self.elapsed, 2),
            collected_water=self.collected["water"],
            collected_light=self.collected["light"],
            collected_nitrogen=self.collected["nitrogen"],
            collected_phosphorus=self.collected["phosphorus"],
            collected_potassium=self.collected["potassium"],
            collected_pesticide=self.collected["pesticide"],
            pest_hits=self.pest_hits,
            power_before=self.power_before,
            power_after=self.plant.current_power,
            score=score,
        )

    def draw(
        self,
        surface: pygame.Surface,
        *,
        status_panel_rect: pygame.Rect | None = None,
    ) -> None:
        self.world.draw(surface)
        for obstacle in self.obstacles.obstacles:
            self._draw_obstacle(surface, obstacle)
        for item in self.items.items:
            self._draw_item(surface, item)
        for item in self.items.collecting_items:
            draw_collect_break(surface, item)
        self._draw_player(surface)
        self._draw_hud(surface)
        self._draw_objective_banner(surface)
        if status_panel_rect is not None:
            self.draw_status_panel(surface, status_panel_rect)

    def _draw_obstacle(self, surface: pygame.Surface, obstacle: Obstacle) -> None:
        rect = obstacle.rect
        if obstacle.hit:
            color = (113, 116, 108)
        elif obstacle.kind == "slide":
            color = (143, 63, 67)
        else:
            color = (105, 68, 48)

        if obstacle.kind == "slide":
            pygame.draw.rect(surface, (45, 31, 27), rect.move(4, 5))
            pygame.draw.rect(surface, (102, 59, 38), rect)
            pygame.draw.rect(surface, (213, 137, 62), (rect.left + 3, rect.top + 4, rect.width - 6, 5))
            pygame.draw.rect(surface, (246, 190, 83), (rect.left + 7, rect.top + 7, rect.width - 14, 3))
            pygame.draw.rect(surface, (57, 42, 34), (rect.left + 7, rect.top + 10, 8, rect.height - 10))
            pygame.draw.rect(surface, (57, 42, 34), (rect.right - 15, rect.top + 10, 8, rect.height - 10))
            pygame.draw.rect(surface, (156, 91, 45), (rect.left + 17, rect.top + 13, rect.width - 34, rect.height - 17))
            for x in range(rect.left + 20, rect.right - 8, 18):
                pygame.draw.rect(surface, (239, 179, 69), (x, rect.centery - 3, 7, 7))
                pygame.draw.rect(surface, (255, 227, 130), (x + 2, rect.centery - 2, 3, 3))
            return

        pygame.draw.rect(surface, (45, 31, 27), rect.move(4, 5))
        pygame.draw.rect(surface, (102, 62, 39), rect)
        pygame.draw.rect(surface, (210, 136, 61), (rect.left + 4, rect.top + 4, rect.width - 8, 7))
        pygame.draw.rect(surface, (242, 184, 78), (rect.left + 7, rect.top + 5, rect.width - 16, 3))
        pygame.draw.rect(surface, (68, 44, 33), (rect.left + 5, rect.top + 11, rect.width - 10, rect.height - 16))
        for y in range(rect.top + 15, rect.bottom - 7, 18):
            pygame.draw.rect(surface, (167, 93, 43), (rect.left + 6, y, rect.width - 12, 7))
            pygame.draw.rect(surface, (231, 160, 65), (rect.left + 9, y + 1, rect.width - 18, 3))
            pygame.draw.rect(surface, (92, 54, 34), (rect.left + 7, y + 7, rect.width - 14, 3))
        pygame.draw.rect(surface, (244, 208, 103), (rect.left + 8, rect.top + 5, 7, 4))

    def _draw_item(self, surface: pygame.Surface, item: Collectible) -> None:
        rect = item.rect
        # The pickup itself is the icon: no pale card behind it.  A few
        # animated square motes make it float like the reference sprites.
        sparkle = int(self.elapsed * 8 + item.pair_id) % 4
        for offset_x, offset_y in ((-5, 8 + sparkle), (rect.width + 2, 13 - sparkle), (rect.width // 2, -5 - sparkle)):
            pygame.draw.rect(surface, PALETTE["gold_light"], (rect.left + offset_x, rect.top + offset_y, 3, 3))
        draw_element_icon(surface, item.element, rect)

    def _draw_player(self, surface: pygame.Surface) -> None:
        if self.player.is_invincible and int(self.player.invincible_remaining * 40) % 2 == 0:
            return

        draw_pixel_runner(
            surface,
            self.player.rect,
            self.plant.plant_type,
            running_frame=round(self.elapsed * 8),
            crouching=self.player.crouching,
        )

    def _draw_plant(self, surface: pygame.Surface, center: tuple[int, int]) -> None:
        draw_pixel_plant(surface, center, self.plant.plant_type, scale=1)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        draw_pixel_wood_frame(surface, pygame.Rect(0, 0, WINDOW_WIDTH, 72), fill=(29, 31, 29))
        font = pygame.font.Font(None, 27)
        small = pygame.font.Font(None, 21)
        remaining = max(0.0, TIME_LIMIT - self.elapsed)
        time_text = font.render(f"TIME {remaining:04.1f}", False, (244, 241, 225))
        power_text = font.render(
            f"POWER {self.plant.current_power:05.1f}", False, (244, 241, 225)
        )
        surface.blit(time_text, (25, 16))
        surface.blit(power_text, (180, 16))

        for index in range(MAX_HP):
            x = 389 + index * 30
            color = PALETTE["red"] if index < self.player.hp else (80, 83, 82)
            pygame.draw.rect(surface, (45, 31, 27), (x, 13, 18, 18))
            pygame.draw.rect(surface, color, (x + 3, 15, 12, 13))
            pygame.draw.rect(surface, (246, 142, 113), (x + 5, 15, 5, 4))
            pygame.draw.rect(surface, PALETTE["gold_light"], (x + 2, 12, 4, 4))

        x = 510
        for element in ELEMENT_TYPES:
            icon_rect = pygame.Rect(x - 12, 6, 26, 26)
            draw_element_icon(surface, element, icon_rect)
            label = small.render(str(self.collected[element]), False, (244, 241, 225))
            # Keep the counter above the timber's lower trim; the previous
            # position sat directly on the frame line at the bottom of HUD.
            surface.blit(label, label.get_rect(center=(x + 1, 48)))
            x += 48

    def _draw_objective_banner(self, surface: pygame.Surface) -> None:
        """Show the first-level goal in the same timber UI language."""
        banner = pygame.Rect(14, 84, 390, 62)
        draw_pixel_wood_frame(surface, banner, fill=(29, 31, 29))
        draw_pixel_badge(surface, pygame.Rect(27, 96, 92, 22), "MISSION", fill=(88, 132, 66))
        font = pygame.font.Font(None, 18)
        line_one = font.render("COLLECT ELEMENTS / BUILD POWER", False, PALETTE["cream"])
        line_two = font.render("SPRAY BOOSTS PLANT HEALTH", False, PALETTE["muted_cream"])
        surface.blit(line_one, (132, 96))
        surface.blit(line_two, (132, 118))

    def draw_status_panel(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the live six-axis status radar in the course's open corner."""
        draw_pixel_wood_frame(
            surface,
            rect,
            fill=(29, 31, 29),
        )
        title_font = pygame.font.Font(None, 20)
        title = title_font.render("PLANT HEALTH", False, PALETTE["cream"])
        surface.blit(title, title.get_rect(midtop=(rect.centerx, rect.top + 12)))
        pygame.draw.rect(surface, (155, 99, 49), (rect.left + 18, rect.top + 34, rect.width - 36, 3))
        draw_status_hexagon(
            surface,
            (rect.centerx, rect.top + 104),
            40,
            self.plant.status,
            show_labels=True,
            show_values=False,
        )
        draw_power_readout(
            surface,
            # The readout has two lines; keep both lines comfortably inside
            # the panel instead of letting the delta touch its bottom border.
            (rect.left + 18, rect.bottom - 64),
            self.plant.current_power,
            self.power_before,
        )


def run_level1(
    plant: PlantData,
    action_provider: ActionProvider | None = None,
    screen: pygame.Surface | None = None,
    *,
    use_camera: bool = True,
) -> Level1Result:
    """Run level one and return its integration result.

    Level one owns the camera by default because the main program only provides
    uploaded plant data. ``action_provider`` remains available for automated
    tests or alternate controllers and disables the built-in camera input.
    """
    pygame.init()
    owns_display = screen is None
    if screen is None:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Plant Runner - Level 1")

    clock = pygame.time.Clock()
    game = Level1Game(plant)

    # Give a first-time player a short chance to check the controls.  The
    # headless/surface-injected path intentionally skips this modal screen so
    # it remains usable by automated callers without a display.
    if owns_display and pygame.display.get_surface() is not None:
        control_mode = _choose_level1_control(screen, allow_camera=use_camera)
        if control_mode is None:
            game.abort()
            result = game.make_result()
            if owns_display:
                pygame.display.quit()
            return result
    else:
        control_mode = "camera" if use_camera else "keyboard"

    if owns_display and _tutorial_enabled() and pygame.display.get_surface() is not None:
        if not _show_level1_tutorial(screen, control_mode):
            game.abort()
            result = game.make_result()
            if owns_display:
                pygame.display.quit()
            return result

    audio = AudioManager()
    audio.start_music()
    camera_input = (
        CameraPoseInput.open_first()
        if control_mode == "camera" and action_provider is None
        else None
    )
    if control_mode == "camera" and camera_input is None:
        # A selected camera can disappear between the choice screen and the
        # level loop. Keep the level playable instead of silently ignoring
        # every keyboard event.
        control_mode = "keyboard"

    try:
        while not game.finished:
            dt = clock.tick(TARGET_FPS) / 1000.0
            actions: list[GestureAction] = []
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.abort()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game.abort()
                    elif event.key == pygame.K_m:
                        audio.toggle_mute()
                    elif control_mode == "keyboard":
                        if event.key == pygame.K_w:
                            actions.append("jump")
                        elif event.key == pygame.K_s:
                            actions.append("drop")
                        elif event.key == pygame.K_a:
                            actions.append("crouch")
                        elif event.key == pygame.K_d:
                            actions.append("big_jump")

            if action_provider is not None:
                action = action_provider()
                if action != "none":
                    actions.append(action)
            elif camera_input is not None:
                action = camera_input.read_action()
                if action != "none":
                    actions.append(action)

            game.update(dt, actions)
            for event_name, element in game.consume_audio_events():
                if event_name == "collect" and element is not None:
                    audio.play_collect(element)
                elif event_name == "hurt":
                    audio.play_hurt()
            # Keep the keyboard-mode panel below the top HUD; camera mode
            # stays lower because the camera preview occupies the upper right.
            status_panel_rect = pygame.Rect(568, 246 if control_mode == "camera" else 84, 222, 248)
            game.draw(screen, status_panel_rect=status_panel_rect)
            _draw_camera_overlay(screen, camera_input, control_mode == "camera")
            # ``screen`` may be an off-screen Surface supplied by a test or a
            # host application.  Only flip when Pygame owns an actual display.
            if pygame.display.get_surface() is not None:
                pygame.display.flip()
    finally:
        audio.close()
        if camera_input is not None:
            camera_input.close()

    result = game.make_result()
    if owns_display:
        pygame.display.quit()
    return result


def _tutorial_enabled() -> bool:
    """Return whether interactive pre-level instructions should be shown."""
    import os

    return os.environ.get("PLANT_GAME_SKIP_TUTORIAL") not in {"1", "true", "TRUE"}


def _choose_level1_control(
    surface: pygame.Surface,
    *,
    allow_camera: bool = True,
) -> ControlMode | None:
    """Let the player choose keyboard or camera control before the tutorial."""
    clock = pygame.time.Clock()
    title_font = pygame.font.Font(None, 42)
    body_font = pygame.font.Font(None, 24)
    selected = 0
    options = ("keyboard", "camera") if allow_camera else ("keyboard",)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type != pygame.KEYDOWN:
                continue
            if len(options) > 1 and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                selected = 1 - selected
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return options[selected]
            elif event.key == pygame.K_ESCAPE:
                return None

        draw_pixel_backdrop(surface, base=(92, 160, 184), horizon=540)
        pygame.draw.rect(surface, (62, 110, 70), (0, 540, WINDOW_WIDTH, 60))
        panel = pygame.Rect(64, 72, 672, 420)
        draw_pixel_wood_frame(surface, panel, fill=(29, 31, 29))
        title = title_font.render("CHOOSE CONTROL METHOD", False, PALETTE["gold_light"])
        surface.blit(title, title.get_rect(center=(400, 120)))
        hint = body_font.render("LEFT / RIGHT SELECT     ENTER CONFIRM     ESC CANCEL", False, PALETTE["muted_cream"])
        surface.blit(hint, hint.get_rect(center=(400, 158)))
        camera_lines = (
            "LEFT HAND UP  JUMP",
            "RIGHT HAND UP  CROUCH",
            "BOTH HANDS  WAIT",
            "CAMERA REQUIRED",
        ) if allow_camera else (
            "CAMERA DISABLED",
            "USE --NO-CAMERA",
            "KEYBOARD IS READY",
            "PRESS ENTER TO CONTINUE",
        )
        cards = (
            (pygame.Rect(93, 205, 282, 206), "KEYBOARD", ("W  JUMP / UP", "S  DROP / DOWN", "A  CROUCH", "D  BIG JUMP")),
            (pygame.Rect(425, 205, 282, 206), "CAMERA POSE", camera_lines),
        )
        for index, (card, label, lines) in enumerate(cards):
            active = index == selected
            card_enabled = index == 0 or allow_camera
            draw_pixel_wood_frame(
                surface,
                card,
                fill=(54, 85, 59) if active and card_enabled else (43, 49, 43),
            )
            border_color = PALETTE["gold_light"] if active else PALETTE["muted_cream"]
            pygame.draw.rect(surface, border_color, card.inflate(-10, -10), 2)
            card_title = body_font.render(label, False, PALETTE["cream"])
            surface.blit(card_title, card_title.get_rect(center=(card.centerx, card.top + 38)))
            for line_index, line in enumerate(lines):
                text_color = PALETTE["gold_light"] if active and card_enabled else PALETTE["muted_cream"]
                text = body_font.render(line, False, text_color)
                surface.blit(text, text.get_rect(center=(card.centerx, card.top + 78 + line_index * 27)))
        pygame.display.flip()
        clock.tick(30)


def _show_level1_tutorial(surface: pygame.Surface, control_mode: ControlMode) -> bool:
    """Show Level 1 controls and wait for Enter/Space or Escape."""
    clock = pygame.time.Clock()
    title_font = pygame.font.Font(None, 42)
    body_font = pygame.font.Font(None, 27)
    lines = (
        "LEVEL 1  |  PLANT RUNNER",
        "KEYBOARD: W UP  /  S DOWN  /  A CROUCH  /  D BIG JUMP" if control_mode == "keyboard" else "CAMERA: LEFT HAND JUMP  /  RIGHT HAND CROUCH",
        "Collect nutrients and spray; avoid hazards.",
        "Floating platforms add a second route through the forest.",
        "Press ENTER or SPACE to start  |  ESC to quit",
    )

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return True
                if event.key == pygame.K_ESCAPE:
                    return False

        draw_pixel_backdrop(surface, base=(177, 209, 199), horizon=540)
        pygame.draw.rect(surface, (94, 145, 103), (0, 540, WINDOW_WIDTH, 60))
        for x in range(0, WINDOW_WIDTH, 56):
            pygame.draw.rect(surface, (137, 185, 103), (x + 8, 540, 25, 4))
        panel = pygame.Rect(75, 92, 650, 390)
        draw_pixel_panel(
            surface,
            panel,
            fill=PALETTE["panel"],
            border=PALETTE["gold"],
            accent=PALETTE["green"],
        )
        for index, line in enumerate(lines):
            font = title_font if index == 0 else body_font
            color = PALETTE["gold_light"] if index == 0 else PALETTE["cream"]
            text = font.render(line, False, color)
            surface.blit(text, text.get_rect(center=(400, 150 + index * 56)))
        pygame.display.flip()
        clock.tick(30)


def _draw_camera_overlay(
    surface: pygame.Surface,
    camera_input: CameraPoseInput | None,
    use_camera: bool,
) -> None:
    if not use_camera:
        return

    x = WINDOW_WIDTH - CAMERA_PREVIEW_WIDTH - CAMERA_PREVIEW_MARGIN
    y = 96
    frame_rect = pygame.Rect(
        x - 3,
        y - 3,
        CAMERA_PREVIEW_WIDTH + 6,
        CAMERA_PREVIEW_HEIGHT + 28,
    )
    draw_pixel_wood_frame(surface, frame_rect, fill=(27, 37, 42))

    small = pygame.font.Font(None, 20)
    label = small.render(
        "CAM 0  /  DIRECTSHOW POSE",
        False,
        (222, 211, 163),
    )
    surface.blit(label, (x + 8, y - 23))
    if camera_input is None or camera_input.latest_frame is None:
        pygame.draw.rect(
            surface,
            (53, 57, 59),
            (x, y, CAMERA_PREVIEW_WIDTH, CAMERA_PREVIEW_HEIGHT),
        )
        status = small.render("CAMERA OFF", False, (244, 119, 94))
        surface.blit(status, status.get_rect(center=(x + 80, y + 60)))
        return

    import cv2

    preview_frame = cv2.flip(camera_input.latest_frame, 1)
    rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
    height, width = rgb_frame.shape[:2]
    preview = pygame.image.frombuffer(rgb_frame.tobytes(), (width, height), "RGB")
    preview = pygame.transform.smoothscale(
        preview,
        (CAMERA_PREVIEW_WIDTH, CAMERA_PREVIEW_HEIGHT),
    )
    surface.blit(preview, (x, y))

    action = camera_input.displayed_action
    action_color = (245, 198, 75) if action != "none" else (174, 220, 184)
    action_label = small.render(
        f"{camera_input.label}  POSE {action.upper()}",
        False,
        action_color,
    )
    surface.blit(action_label, (x + 8, y + CAMERA_PREVIEW_HEIGHT + 6))


def main() -> None:
    from .demo_data import create_demo_plant

    result = run_level1(create_demo_plant())
    print(asdict(result))


if __name__ == "__main__":
    main()
