"""Playable level-one runner and the team's required ``run_level1`` API."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict
import math
import random

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
    scroll_speed_at,
)
from .items import ELEMENT_TYPES, Collectible, ItemManager, draw_element_icon
from .map import Obstacle, ObstacleManager, ScrollingMap
from .player import Player
from vision.camera_pose_input import CameraPoseInput
from vision.pose_control import GestureAction


ActionProvider = Callable[[], PoseAction]
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
        self.world = ScrollingMap()
        self.obstacles = ObstacleManager(self.rng)
        self.items = ItemManager(self.rng)

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

    def handle_action(self, action: GestureAction) -> bool:
        if action == "jump":
            return self.player.jump()
        if action == "crouch":
            return self.player.slide()
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
        can_spawn_item = (
            self._reserve_item_spawn_window(speed)
            if item_spawn_due
            else True
        )
        self.items.update(
            dt,
            speed,
            can_spawn=can_spawn_item,
        )
        self.player.update(dt)
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

    def _reserve_item_spawn_window(self, speed: float) -> bool:
        candidate_x = WINDOW_WIDTH + 25.0
        if any(
            _horizontal_gap(
                candidate_x,
                ITEM_SIZE,
                obstacle.x,
                obstacle.width,
            ) < ITEM_OBSTACLE_CLEARANCE
            for obstacle in self.obstacles.obstacles
        ):
            return False

        future_delays = [self.obstacles.spawn_remaining]
        if self.obstacles.cluster_remaining is not None:
            future_delays.append(self.obstacles.cluster_remaining)
        required_travel = (
            ITEM_OBSTACLE_CLEARANCE
            + ITEM_SIZE
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

        item_hits = all_collisions(player_rect, self.items.items)
        if item_hits:
            item = item_hits[0]
            apply_element(self.plant, item.element)
            self.collected[item.element] += 1
            self.items.remove_pair(item.pair_id)
            self.audio_events.append(("collect", item.element))

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

    def draw(self, surface: pygame.Surface) -> None:
        self.world.draw(surface)
        for obstacle in self.obstacles.obstacles:
            self._draw_obstacle(surface, obstacle)
        for item in self.items.items:
            self._draw_item(surface, item)
        self._draw_player(surface)
        self._draw_hud(surface)

    def _draw_obstacle(self, surface: pygame.Surface, obstacle: Obstacle) -> None:
        rect = obstacle.rect
        if obstacle.hit:
            color = (133, 124, 114)
        elif obstacle.kind == "slide":
            color = (148, 63, 61)
        else:
            color = (104, 69, 50)

        if obstacle.kind == "slide":
            pygame.draw.rect(surface, color, rect, border_radius=3)
            pygame.draw.line(surface, (66, 48, 43), rect.bottomleft, rect.topleft, 5)
            pygame.draw.line(surface, (66, 48, 43), rect.bottomright, rect.topright, 5)
            for x in range(rect.left + 10, rect.right, 18):
                pygame.draw.circle(surface, (238, 178, 63), (x, rect.centery), 4)
            return

        pygame.draw.rect(surface, color, rect, border_radius=3)
        stripe = (229, 178, 71)
        for y in range(rect.top + 9, rect.bottom, 24):
            pygame.draw.rect(surface, stripe, (rect.left, y, rect.width, 7))
        pygame.draw.rect(surface, (54, 44, 40), rect, width=3, border_radius=3)

    def _draw_item(self, surface: pygame.Surface, item: Collectible) -> None:
        rect = item.rect
        center = rect.center
        pygame.draw.circle(surface, (250, 248, 235), center, 24)
        pygame.draw.circle(surface, (255, 255, 255), center, 21)
        draw_element_icon(surface, item.element, rect.inflate(-8, -8))

    def _draw_player(self, surface: pygame.Surface) -> None:
        if self.player.is_invincible and int(self.player.invincible_remaining * 40) % 2 == 0:
            return

        rect = self.player.rect
        line_color = (35, 39, 43)
        skin = (245, 194, 136)
        phase = self.elapsed * 11.0
        running_swing = int(math.sin(phase) * 11) if self.player.grounded else 0

        if self.player.crouching:
            head = (rect.left + 12, rect.top + 9)
            shoulder = (rect.left + 22, rect.top + 18)
            hip = (rect.left + 25, rect.top + 28)
            front_foot = (rect.right - 2, rect.bottom - 2)
            back_foot = (rect.left + 5, rect.bottom - 2)
        else:
            head = (rect.centerx, rect.top + 10)
            shoulder = (rect.centerx, rect.top + 22)
            hip = (rect.centerx, rect.top + 48)
            front_foot = (rect.centerx + running_swing, rect.bottom - 2)
            back_foot = (rect.centerx - running_swing, rect.bottom - 2)

        pygame.draw.line(surface, line_color, shoulder, hip, 5)
        pygame.draw.line(surface, line_color, hip, front_foot, 5)
        pygame.draw.line(surface, line_color, hip, back_foot, 5)
        pygame.draw.line(
            surface,
            line_color,
            shoulder,
            (shoulder[0] + 16, shoulder[1] + 15),
            5,
        )
        pygame.draw.line(
            surface,
            line_color,
            shoulder,
            (shoulder[0] - 13, shoulder[1] + 13),
            5,
        )
        pygame.draw.circle(surface, skin, head, 9)
        pygame.draw.circle(surface, line_color, head, 9, width=2)
        self._draw_plant(surface, (shoulder[0] + 16, shoulder[1] + 12))

    def _draw_plant(self, surface: pygame.Surface, center: tuple[int, int]) -> None:
        pot = pygame.Rect(center[0] - 8, center[1] + 1, 16, 11)
        pygame.draw.rect(surface, (173, 91, 57), pot, border_radius=2)
        plant_type = self.plant.plant_type
        if plant_type == "grass":
            for dx in (-6, -2, 3, 7):
                pygame.draw.line(
                    surface, (52, 135, 71), (center[0], center[1] + 2),
                    (center[0] + dx, center[1] - 12 - abs(dx)), 3,
                )
        elif plant_type == "shrub":
            for dx, dy in ((-6, -2), (0, -7), (7, -2)):
                pygame.draw.circle(
                    surface, (54, 137, 72), (center[0] + dx, center[1] + dy), 6
                )
        else:
            pygame.draw.line(
                surface, (58, 137, 72), (center[0], center[1] + 3),
                (center[0], center[1] - 8), 3,
            )
            for angle in range(0, 360, 72):
                radians = math.radians(angle)
                petal = (
                    round(center[0] + math.cos(radians) * 6),
                    round(center[1] - 9 + math.sin(radians) * 6),
                )
                pygame.draw.circle(surface, (225, 91, 135), petal, 4)
            pygame.draw.circle(surface, (246, 190, 60), (center[0], center[1] - 9), 3)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (28, 38, 43), (0, 0, WINDOW_WIDTH, 52))
        font = pygame.font.Font(None, 27)
        small = pygame.font.Font(None, 21)
        remaining = max(0.0, TIME_LIMIT - self.elapsed)
        time_text = font.render(f"TIME {remaining:04.1f}", True, (244, 241, 225))
        power_text = font.render(
            f"POWER {self.plant.current_power:05.1f}", True, (244, 241, 225)
        )
        surface.blit(time_text, (18, 15))
        surface.blit(power_text, (174, 15))

        for index in range(MAX_HP):
            x = 390 + index * 27
            color = (222, 74, 67) if index < self.player.hp else (80, 83, 82)
            pygame.draw.circle(surface, color, (x, 23), 8)
            pygame.draw.circle(surface, color, (x + 9, 23), 8)
            pygame.draw.polygon(surface, color, ((x - 8, 25), (x + 17, 25), (x + 5, 40)))

        x = 500
        for element in ELEMENT_TYPES:
            icon_rect = pygame.Rect(x - 9, 8, 18, 18)
            draw_element_icon(surface, element, icon_rect)
            label = small.render(str(self.collected[element]), True, (244, 241, 225))
            surface.blit(label, (x - 5, 31))
            x += 48


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
    if owns_display and _tutorial_enabled() and pygame.display.get_surface() is not None:
        if not _show_level1_tutorial(screen):
            game.abort()
            result = game.make_result()
            if owns_display:
                pygame.display.quit()
            return result

    audio = AudioManager()
    audio.start_music()
    camera_input = (
        CameraPoseInput.open_first()
        if use_camera and action_provider is None
        else None
    )

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
                    elif event.key == pygame.K_UP:
                        actions.append("jump")
                    elif event.key == pygame.K_DOWN:
                        actions.append("crouch")
                    elif event.key == pygame.K_m:
                        audio.toggle_mute()

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
            game.draw(screen)
            _draw_camera_overlay(screen, camera_input, use_camera)
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


def _show_level1_tutorial(surface: pygame.Surface) -> bool:
    """Show Level 1 controls and wait for Enter/Space or Escape."""
    clock = pygame.time.Clock()
    title_font = pygame.font.Font(None, 42)
    body_font = pygame.font.Font(None, 27)
    lines = (
        "LEVEL 1  |  PLANT RUNNER",
        "UP / raise only left hand: jump",
        "DOWN / raise only right hand: slide",
        "Collect the elements your plant needs; avoid pests.",
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

        surface.fill((28, 38, 43))
        panel = pygame.Rect(75, 92, 650, 390)
        pygame.draw.rect(surface, (54, 76, 73), panel, border_radius=12)
        pygame.draw.rect(surface, (244, 198, 75), panel, width=3, border_radius=12)
        for index, line in enumerate(lines):
            font = title_font if index == 0 else body_font
            color = (255, 220, 112) if index == 0 else (244, 241, 225)
            text = font.render(line, True, color)
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
    y = 62
    frame_rect = pygame.Rect(
        x - 3,
        y - 3,
        CAMERA_PREVIEW_WIDTH + 6,
        CAMERA_PREVIEW_HEIGHT + 28,
    )
    pygame.draw.rect(surface, (27, 37, 42), frame_rect, border_radius=4)

    small = pygame.font.Font(None, 20)
    if camera_input is None or camera_input.latest_frame is None:
        pygame.draw.rect(
            surface,
            (53, 57, 59),
            (x, y, CAMERA_PREVIEW_WIDTH, CAMERA_PREVIEW_HEIGHT),
        )
        status = small.render("CAMERA OFF", True, (244, 119, 94))
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
    label = small.render(
        f"{camera_input.label}  POSE {action.upper()}",
        True,
        action_color,
    )
    surface.blit(label, (x + 3, y + CAMERA_PREVIEW_HEIGHT + 5))


def main() -> None:
    from .demo_data import create_demo_plant

    result = run_level1(create_demo_plant())
    print(asdict(result))


if __name__ == "__main__":
    main()
