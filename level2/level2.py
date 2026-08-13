"""Coordinates the complete second-level game session."""

from __future__ import annotations

import os

import pygame

from shared_game_data import (
    ATTACK_CONFIG,
    DIFFICULTIES,
    DifficultyConfig,
    Level2Result,
    PlantData,
    PlantStatus,
    calculate_attack_damage,
    calculate_power,
)

from .config import (
    BACKGROUND_COLOR,
    BATTLEFIELD_BOTTOM,
    BATTLEFIELD_TOP,
    FPS,
    HOUSE_COLOR,
    HOUSE_ROOF_COLOR,
    HOUSE_WIDTH,
    HUD_COLOR,
    LANE_COLORS,
    LANE_COUNT,
    LANE_HEIGHT,
    LANE_LINE_COLOR,
    RAIL_COLOR,
    TEXT_COLOR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZOMBIE_GOAL_X,
    lane_center_y,
)
from .plant_player import PlantPlayer
from .projectile import Projectile
from .wave_manager import WaveManager
from .zombie import Zombie
from vision.hand_control import HandController
from ui.pixel_style import PALETTE, draw_pixel_badge, draw_pixel_panel


class Level2Game:
    """Playable Level 2 connected to the team's shared data contract."""

    def __init__(
        self,
        plant: PlantData | None = None,
        difficulty: DifficultyConfig | None = None,
    ) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Plant Guardian - Level 2")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 21)
        self.plant_data = plant or self._make_demo_plant()
        self.difficulty = difficulty or DIFFICULTIES["normal"]
        self.attack_config = ATTACK_CONFIG[self.plant_data.plant_type]
        self.player = PlantPlayer(plant_type=self.plant_data.plant_type)
        self.zombies = pygame.sprite.Group()
        self.projectiles = pygame.sprite.Group()
        self.wave_manager = WaveManager(
            count_multiplier=self.difficulty.zombie_count_multiplier
        )
        self.hand_controller = HandController()
        self.attack_timer = 0.0
        self.zombies_defeated = 0
        self.zombies_escaped = 0
        self.elapsed_time = 0.0
        self.battle_time = 0.0
        self.tutorial_until = 8.0
        self.result: str | None = None
        self.running = True

    def run(self, max_frames: int | None = None) -> Level2Result:
        """Run the game and return the result required by shared_game_data."""
        frame_count = 0

        if max_frames is None and self._tutorial_enabled() and not self._show_start_tutorial():
            self.running = False

        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                self._handle_events()
                self._update(dt)
                self._draw()
                pygame.display.flip()

                frame_count += 1
                if max_frames is not None and frame_count >= max_frames:
                    self.running = False
        finally:
            self.hand_controller.close()
            pygame.quit()
        return self._build_result()

    @staticmethod
    def _tutorial_enabled() -> bool:
        return os.environ.get("PLANT_GAME_SKIP_TUTORIAL") not in {"1", "true", "TRUE"}

    def _show_start_tutorial(self) -> bool:
        """Show Level 2 controls before the first wave starts."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return True
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return False

            self._draw()
            overlay = pygame.Surface((820, 210), pygame.SRCALPHA)
            overlay.fill((12, 25, 19, 232))
            pygame.draw.rect(overlay, PALETTE["gold"], overlay.get_rect(), 3)
            pygame.draw.rect(overlay, PALETTE["panel_light"], (3, 3, 814, 4))
            title = self.font.render("LEVEL 2  |  PLANT GUARDIAN", False, (255, 222, 96))
            body = self.small_font.render(
                "W/S or arrow keys move between rails. Press H to enable hand control.",
                False,
                TEXT_COLOR,
            )
            hint = self.small_font.render(
                "Destroy both zombie waves before they reach the house.",
                False,
                (181, 224, 205),
            )
            start = self.small_font.render(
                "Press ENTER or SPACE to start  |  ESC to quit",
                False,
                (255, 220, 92),
            )
            overlay.blit(title, (24, 24))
            overlay.blit(body, (24, 78))
            overlay.blit(hint, (24, 112))
            overlay.blit(start, (24, 166))
            self.screen.blit(
                overlay,
                (
                    WINDOW_WIDTH // 2 - overlay.get_width() // 2,
                    WINDOW_HEIGHT // 2 - overlay.get_height() // 2,
                ),
            )
            pygame.display.flip()
            self.clock.tick(30)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.player.move_up()
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.player.move_down()
                elif event.key == pygame.K_h:
                    if self.hand_controller.enabled:
                        self.hand_controller.close()
                    else:
                        if self.hand_controller.start():
                            self.tutorial_until = self.elapsed_time + 5.0
                elif event.key == pygame.K_r and self.result is not None:
                    self._reset_battle()

    def _update(self, dt: float) -> None:
        self.elapsed_time += dt
        self.player.update(dt)
        if self.result is not None:
            return
        self.battle_time += dt

        hand_action = self.hand_controller.poll_action()
        if hand_action == "up":
            self.player.move_up()
        elif hand_action == "down":
            self.player.move_down()

        spawn_lane = self.wave_manager.update(dt, len(self.zombies))
        if spawn_lane is not None:
            speed_multiplier = self.difficulty.zombie_speed_multiplier * (
                1.0 + self.wave_manager.wave_index * 0.2
            )
            self.zombies.add(
                Zombie(
                    spawn_lane,
                    speed_multiplier=speed_multiplier,
                    health_multiplier=self.difficulty.zombie_hp_multiplier,
                )
            )

        self.attack_timer -= dt
        target_in_lane = any(
            zombie.lane_index == self.player.lane_index for zombie in self.zombies
        )
        if target_in_lane and self.attack_timer <= 0:
            projectile_count = int(self.attack_config["projectile_count"])
            damage = calculate_attack_damage(
                self.plant_data,
                float(self.attack_config["base_damage"]),
            )
            for index in range(projectile_count):
                vertical_offset = round((index - (projectile_count - 1) / 2) * 12)
                start = (
                    self.player.rect.right + 6,
                    self.player.rect.centery + vertical_offset,
                )
                self.projectiles.add(
                    Projectile(
                        start,
                        self.player.lane_index,
                        damage=damage,
                        speed=float(self.attack_config["projectile_speed"]) * 55.0,
                        penetration=int(self.attack_config["penetration"]),
                        attack_name=str(self.attack_config["attack_name"]),
                    )
                )
            self.attack_timer = float(self.attack_config["cooldown"])

        self.zombies.update(dt)
        self.projectiles.update(dt)
        self._resolve_projectile_hits()

        escaped = [zombie for zombie in self.zombies if zombie.rect.left <= ZOMBIE_GOAL_X]
        if escaped:
            self.zombies_escaped += len(escaped)
            self.result = "DEFEAT"
        elif self.wave_manager.finished and not self.zombies:
            self.result = "VICTORY"

    def _resolve_projectile_hits(self) -> None:
        collisions = pygame.sprite.groupcollide(
            self.zombies,
            self.projectiles,
            False,
            False,
            collided=pygame.sprite.collide_rect,
        )
        for zombie, projectiles in collisions.items():
            new_hits = [
                projectile
                for projectile in projectiles
                if projectile.can_hit(zombie)
            ]
            if not new_hits:
                continue
            damage = sum(projectile.damage for projectile in new_hits)
            for projectile in new_hits:
                projectile.register_hit(zombie)
            if zombie.take_damage(damage):
                self.zombies_defeated += 1

    def _reset_battle(self) -> None:
        self.zombies.empty()
        self.projectiles.empty()
        self.wave_manager = WaveManager(
            count_multiplier=self.difficulty.zombie_count_multiplier
        )
        self.player.move_to_lane(LANE_COUNT // 2)
        self.zombies_defeated = 0
        self.zombies_escaped = 0
        self.attack_timer = 0.0
        self.battle_time = 0.0
        self.result = None

    def _draw(self) -> None:
        self.screen.fill(BACKGROUND_COLOR)
        self._draw_hud()
        self._draw_battlefield()
        self._draw_house()
        self._draw_rail()
        self._draw_hand_target()
        self.projectiles.draw(self.screen)
        self.zombies.draw(self.screen)
        for zombie in self.zombies:
            zombie.draw_health_bar(self.screen)
        self.player.draw(self.screen)
        if self.elapsed_time < self.tutorial_until and self.result is None:
            self._draw_tutorial()
        if self.result is not None:
            self._draw_result_overlay()

    def _draw_hud_legacy_old(self) -> None:
        pygame.draw.rect(self.screen, PALETTE["deep_ink"], (0, 0, WINDOW_WIDTH, BATTLEFIELD_TOP))
        pygame.draw.rect(self.screen, HUD_COLOR, (0, 4, WINDOW_WIDTH, BATTLEFIELD_TOP - 8))
        pygame.draw.rect(self.screen, PALETTE["gold"], (0, BATTLEFIELD_TOP - 4, WINDOW_WIDTH, 4))
        pygame.draw.rect(self.screen, PALETTE["panel_light"], (0, 4, WINDOW_WIDTH, 3))
        title = self.font.render("LEVEL 2  |  PLANT GUARDIAN", False, TEXT_COLOR)
        instructions = self.small_font.render(
            "ARROWS / W-S  MOVE    H  HAND CONTROL    ESC  QUIT",
            False,
            TEXT_COLOR,
        )
        lane_text = self.font.render(
            f"WAVE {min(self.wave_manager.wave_number, len(self.wave_manager.wave_counts))}/"
            f"{len(self.wave_manager.wave_counts)}    KILLS {self.zombies_defeated}    "
            f"LANE {self.player.lane_index + 1}/{LANE_COUNT}    {self.difficulty.name.upper()}",
            False,
            (255, 220, 92),
        )
        hand_text = self.small_font.render(
            f"HAND: {self._hand_status_text()}",
            False,
            (126, 235, 176) if self.hand_controller.hand_detected else (181, 224, 205),
        )
        hand_text = self.small_font.render(
            f"HAND: {self._hand_status_text()}",
            False,
            (126, 235, 176) if self.hand_controller.hand_detected else (181, 224, 205),
        )
        self.screen.blit(title, (34, 22))
        self.screen.blit(instructions, (35, 69))
        self.screen.blit(lane_text, (WINDOW_WIDTH - lane_text.get_width() - 38, 35))
        self.screen.blit(hand_text, (WINDOW_WIDTH - hand_text.get_width() - 38, 78))

        indicator_x = WINDOW_WIDTH - 184
        for lane_index in range(LANE_COUNT):
            selected = self.hand_controller.hand_detected and self.player.lane_index == lane_index
            color = (126, 235, 176) if selected else (86, 117, 98)
            pygame.draw.rect(
                self.screen,
                color,
                (indicator_x + lane_index * 24 - 5, 103, 10, 10),
            )
        draw_pixel_badge(
            self.screen,
            pygame.Rect(34, 88, 112, 24),
            self.plant_data.plant_type.upper(),
            fill=PALETTE["green"],
        )

    def _draw_hud_legacy_old(self) -> None:
        """Deprecated duplicate retained only for source compatibility."""
        pygame.draw.rect(self.screen, PALETTE["deep_ink"], (0, 0, WINDOW_WIDTH, BATTLEFIELD_TOP))
        pygame.draw.rect(self.screen, HUD_COLOR, (0, 4, WINDOW_WIDTH, BATTLEFIELD_TOP - 8))
        pygame.draw.rect(self.screen, PALETTE["panel_light"], (0, 4, WINDOW_WIDTH, 3))
        pygame.draw.rect(self.screen, PALETTE["gold"], (0, BATTLEFIELD_TOP - 4, WINDOW_WIDTH, 4))
        title = self.font.render("LEVEL 2  |  PLANT GUARDIAN", False, TEXT_COLOR)
        instructions = self.small_font.render(
            "ARROWS / W-S  MOVE    H  HAND CONTROL    ESC  QUIT",
            False,
            TEXT_COLOR,
        )
        lane_text = self.font.render(
            f"WAVE {min(self.wave_manager.wave_number, len(self.wave_manager.wave_counts))}/"
            f"{len(self.wave_manager.wave_counts)}    KILLS {self.zombies_defeated}    "
            f"LANE {self.player.lane_index + 1}/{LANE_COUNT}    {self.difficulty.name.upper()}",
            False,
            (255, 220, 92),
        )
        hand_text = self.small_font.render(
            f"HAND: {self._hand_status_text()}",
            False,
            (126, 235, 176) if self.hand_controller.hand_detected else (181, 224, 205),
        )
        self.screen.blit(title, (34, 22))
        self.screen.blit(instructions, (35, 69))
        self.screen.blit(lane_text, (WINDOW_WIDTH - lane_text.get_width() - 38, 35))
        self.screen.blit(hand_text, (WINDOW_WIDTH - hand_text.get_width() - 38, 78))
        draw_pixel_badge(
            self.screen,
            pygame.Rect(34, 88, 112, 24),
            self.plant_data.plant_type.upper(),
            fill=PALETTE["green"],
        )
        indicator_x = WINDOW_WIDTH - 184
        for lane_index in range(LANE_COUNT):
            selected = self.hand_controller.hand_detected and self.player.lane_index == lane_index
            color = (126, 235, 176) if selected else (86, 117, 98)
            pygame.draw.rect(self.screen, PALETTE["deep_ink"], (indicator_x + lane_index * 24 - 7, 101, 14, 14))
            pygame.draw.rect(self.screen, color, (indicator_x + lane_index * 24 - 5, 103, 10, 10))

    def _draw_hud(self) -> None:
        """Render the compact English HUD with a layered pixel hierarchy."""
        pygame.draw.rect(self.screen, PALETTE["deep_ink"], (0, 0, WINDOW_WIDTH, BATTLEFIELD_TOP))
        pygame.draw.rect(self.screen, HUD_COLOR, (0, 4, WINDOW_WIDTH, BATTLEFIELD_TOP - 8))
        pygame.draw.rect(self.screen, PALETTE["panel_light"], (0, 4, WINDOW_WIDTH, 3))
        pygame.draw.rect(self.screen, PALETTE["gold"], (0, BATTLEFIELD_TOP - 4, WINDOW_WIDTH, 4))
        title = self.font.render("LEVEL 2  |  PLANT GUARDIAN", False, TEXT_COLOR)
        instructions = self.small_font.render(
            "ARROWS / W-S  MOVE    H  HAND CONTROL    ESC  QUIT",
            False,
            TEXT_COLOR,
        )
        lane_text = self.font.render(
            f"WAVE {min(self.wave_manager.wave_number, len(self.wave_manager.wave_counts))}/"
            f"{len(self.wave_manager.wave_counts)}    KILLS {self.zombies_defeated}    "
            f"LANE {self.player.lane_index + 1}/{LANE_COUNT}    {self.difficulty.name.upper()}",
            False,
            (255, 220, 92),
        )
        hand_text = self.small_font.render(
            f"HAND: {self._hand_status_text()}",
            False,
            (126, 235, 176) if self.hand_controller.hand_detected else (181, 224, 205),
        )
        self.screen.blit(title, (34, 22))
        self.screen.blit(instructions, (35, 69))
        self.screen.blit(lane_text, (WINDOW_WIDTH - lane_text.get_width() - 38, 35))
        self.screen.blit(hand_text, (WINDOW_WIDTH - hand_text.get_width() - 38, 78))
        draw_pixel_badge(self.screen, pygame.Rect(34, 88, 112, 24), self.plant_data.plant_type.upper(), fill=PALETTE["green"])
        indicator_x = WINDOW_WIDTH - 184
        for lane_index in range(LANE_COUNT):
            selected = self.hand_controller.hand_detected and self.player.lane_index == lane_index
            color = (126, 235, 176) if selected else (86, 117, 98)
            pygame.draw.rect(self.screen, PALETTE["deep_ink"], (indicator_x + lane_index * 24 - 7, 101, 14, 14))
            pygame.draw.rect(self.screen, color, (indicator_x + lane_index * 24 - 5, 103, 10, 10))

    def _draw_battlefield(self) -> None:
        battlefield_width = WINDOW_WIDTH - HOUSE_WIDTH

        for lane_index in range(LANE_COUNT):
            lane_rect = pygame.Rect(
                HOUSE_WIDTH,
                BATTLEFIELD_TOP + lane_index * LANE_HEIGHT,
                battlefield_width,
                LANE_HEIGHT,
            )
            pygame.draw.rect(self.screen, LANE_COLORS[lane_index % 2], lane_rect)
            pygame.draw.rect(self.screen, (113, 170, 94), (lane_rect.left, lane_rect.top, lane_rect.width, 4))
            pygame.draw.rect(self.screen, (67, 117, 70), (lane_rect.left, lane_rect.bottom - 5, lane_rect.width, 5))

            # Show the plant's current lane while gesture control is active.
            selected_lane = self.player.lane_index if self.hand_controller.hand_detected else None
            if selected_lane == lane_index:
                glow = pygame.Surface((lane_rect.width, lane_rect.height), pygame.SRCALPHA)
                glow.fill((131, 244, 171, 35))
                self.screen.blit(glow, lane_rect)

            # Small deterministic grass marks add texture without external art.
            for x in range(HOUSE_WIDTH + 65, WINDOW_WIDTH, 150):
                tuft_x = x + (lane_index % 2) * 28
                tuft_y = lane_rect.centery + ((x // 150 + lane_index) % 3 - 1) * 24
                pygame.draw.line(self.screen, (68, 127, 70), (tuft_x, tuft_y), (tuft_x - 4, tuft_y - 7), 2)
                pygame.draw.line(self.screen, (68, 127, 70), (tuft_x, tuft_y), (tuft_x + 4, tuft_y - 7), 2)
                pygame.draw.rect(self.screen, (74, 132, 70), (tuft_x + 16, lane_rect.top + 18 + (x // 75) % 28, 5, 3))
                # Alternating seedling clumps add a little garden life behind
                # the moving zombies without competing with their silhouettes.
                if (x // 150 + lane_index) % 2 == 0:
                    crop_x = x + 52
                    crop_y = lane_rect.bottom - 25
                    pygame.draw.rect(self.screen, (58, 112, 66), (crop_x, crop_y, 4, 16))
                    pygame.draw.rect(self.screen, (91, 165, 72), (crop_x - 7, crop_y + 4, 10, 5))
                    pygame.draw.rect(self.screen, (91, 165, 72), (crop_x + 3, crop_y - 1, 10, 5))
                    pygame.draw.rect(self.screen, (235, 177, 73), (crop_x + 1, crop_y - 7, 5, 5))
            pygame.draw.line(
                self.screen,
                LANE_LINE_COLOR,
                lane_rect.bottomleft,
                lane_rect.bottomright,
                2,
            )

    def _draw_house(self) -> None:
        house_body = pygame.Rect(18, BATTLEFIELD_TOP + 145, 112, 220)
        pygame.draw.rect(self.screen, PALETTE["deep_ink"], house_body.move(5, 5))
        pygame.draw.rect(self.screen, HOUSE_COLOR, house_body)
        pygame.draw.polygon(
            self.screen,
            HOUSE_ROOF_COLOR,
            ((9, house_body.top), (74, house_body.top - 65), (139, house_body.top)),
        )
        pygame.draw.polygon(
            self.screen,
            (153, 89, 63),
            ((18, house_body.top - 2), (74, house_body.top - 55), (130, house_body.top - 2)),
            4,
        )
        for x in range(22, 128, 20):
            pygame.draw.line(self.screen, (91, 53, 49), (x, house_body.top - 8), (x + 58, house_body.top - 58), 3)
        door = pygame.Rect(55, house_body.bottom - 85, 40, 85)
        pygame.draw.rect(self.screen, (82, 55, 43), door)
        pygame.draw.rect(self.screen, (173, 108, 62), (door.left + 5, door.top + 5, 4, door.height - 10))
        pygame.draw.rect(self.screen, (225, 187, 82), (door.right - 12, door.centery - 3, 6, 6))
        window = pygame.Rect(47, house_body.top + 34, 54, 48)
        pygame.draw.rect(self.screen, (134, 205, 218), window)
        pygame.draw.rect(self.screen, (79, 72, 62), window, 5)
        pygame.draw.line(self.screen, (79, 72, 62), window.midtop, window.midbottom, 4)
        pygame.draw.line(self.screen, (79, 72, 62), window.midleft, window.midright, 4)
        for row in range(5):
            pygame.draw.rect(
                self.screen,
                (170, 117, 73),
                (house_body.left + 8, house_body.top + 104 + row * 19, 17, 5),
            )
            pygame.draw.rect(
                self.screen,
                (170, 117, 73),
                (house_body.left + 85, house_body.top + 104 + row * 19, 17, 5),
            )

    def _draw_rail(self) -> None:
        x = self.player.rect.centerx
        pygame.draw.line(
            self.screen,
            (44, 53, 43),
            (x + 5, lane_center_y(0)),
            (x + 5, lane_center_y(LANE_COUNT - 1)),
            14,
        )
        pygame.draw.line(
            self.screen,
            RAIL_COLOR,
            (x, lane_center_y(0)),
            (x, lane_center_y(LANE_COUNT - 1)),
            10,
        )
        for lane_index in range(LANE_COUNT):
            pygame.draw.rect(
                self.screen,
                (52, 43, 39),
                (x - 12, lane_center_y(lane_index) - 12, 24, 24),
            )
            pygame.draw.rect(
                self.screen,
                (219, 199, 137),
                (x - 8, lane_center_y(lane_index) - 8, 16, 16),
            )
            pygame.draw.rect(self.screen, (247, 227, 161), (x - 5, lane_center_y(lane_index) - 5, 6, 3))

    def _draw_hand_target(self) -> None:
        """Show the currently recognized index-finger direction."""
        gesture = self.hand_controller.gesture
        if gesture == "none":
            return
        x = self.player.rect.centerx - 52
        y = self.player.rect.centery
        if gesture == "up":
            points = ((x, y - 24), (x - 13, y - 7), (x - 5, y - 7), (x - 5, y + 19), (x + 5, y + 19), (x + 5, y - 7), (x + 13, y - 7))
        else:
            points = ((x, y + 24), (x - 13, y + 7), (x - 5, y + 7), (x - 5, y - 19), (x + 5, y - 19), (x + 5, y + 7), (x + 13, y + 7))
        pygame.draw.polygon(self.screen, (126, 235, 176), points)
        pygame.draw.polygon(self.screen, (219, 255, 231), points, 2)

    def _draw_tutorial_legacy(self) -> None:
        """Display a short beginner-friendly control hint."""
        panel = pygame.Surface((640, 76), pygame.SRCALPHA)
        panel.fill((20, 41, 31, 218))
        pygame.draw.rect(panel, (126, 235, 176), panel.get_rect(), 2)
        if self.hand_controller.enabled:
            line1 = "HAND CONTROL ON: keep only your index finger extended."
            line2 = "Point up or down to move one rail; relax to trigger again."
        else:
            line1 = "Press H to enable hand control."
            line2 = "Keyboard arrows or W/S are always available."
        text1 = self.small_font.render(line1, True, TEXT_COLOR)
        text2 = self.small_font.render(line2, True, (181, 224, 205))
        panel.blit(text1, (20, 12))
        panel.blit(text2, (20, 43))
        self.screen.blit(panel, (WINDOW_WIDTH // 2 - panel.get_width() // 2, BATTLEFIELD_TOP + 16))

    def _draw_tutorial(self) -> None:
        """Display a short beginner-friendly control hint."""
        panel = pygame.Surface((640, 76), pygame.SRCALPHA)
        panel.fill((20, 41, 31, 218))
        pygame.draw.rect(panel, (126, 235, 176), panel.get_rect(), 2)
        if self.hand_controller.enabled:
            line1 = "HAND CONTROL ON: keep only your index finger extended."
            line2 = "Point up or down to move one rail; relax to trigger again."
        else:
            line1 = "Press H to enable hand control."
            line2 = "Keyboard arrows or W/S are always available."
        text1 = self.small_font.render(line1, False, TEXT_COLOR)
        text2 = self.small_font.render(line2, False, (181, 224, 205))
        panel.blit(text1, (20, 12))
        panel.blit(text2, (20, 43))
        self.screen.blit(panel, (WINDOW_WIDTH // 2 - panel.get_width() // 2, BATTLEFIELD_TOP + 16))

    def _hand_status_text_legacy(self) -> str:
        if self.hand_controller.enabled and self.hand_controller.hand_detected:
            gestures = {
                "up": "INDEX UP",
                "down": "INDEX DOWN",
                "none": "HAND DETECTED",
            }
            return gestures[self.hand_controller.gesture]
        labels = {
            "ready": "READY / PRESS H",
            "active": "ACTIVE / WAITING",
            "model missing": "MODEL MISSING",
            "camera unavailable": "CAMERA UNAVAILABLE",
            "camera frame failed": "CAMERA READ ERROR",
        }
        return labels.get(self.hand_controller.status, self.hand_controller.status)

    def _hand_status_text(self) -> str:
        if self.hand_controller.enabled and self.hand_controller.hand_detected:
            return {
                "up": "INDEX UP",
                "down": "INDEX DOWN",
                "none": "HAND DETECTED",
            }[self.hand_controller.gesture]
        return {
            "ready": "READY / PRESS H",
            "active": "ACTIVE / WAITING",
            "model missing": "MODEL MISSING",
            "camera unavailable": "CAMERA UNAVAILABLE",
            "camera frame failed": "CAMERA READ ERROR",
        }.get(self.hand_controller.status, self.hand_controller.status.upper())

    def _draw_result_overlay(self) -> None:
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((12, 25, 19, 205))
        self.screen.blit(overlay, (0, 0))

        color = (255, 222, 96) if self.result == "VICTORY" else (235, 104, 85)
        card = pygame.Rect(330, 260, 620, 170)
        draw_pixel_panel(self.screen, card, fill=PALETTE["panel"], border=color, accent=color)
        result_text = self.font.render(self.result, False, color)
        restart_text = self.small_font.render("Press R to restart or ESC to quit", False, TEXT_COLOR)
        self.screen.blit(
            result_text,
            result_text.get_rect(center=(WINDOW_WIDTH // 2, 310)),
        )
        self.screen.blit(
            restart_text,
            restart_text.get_rect(center=(WINDOW_WIDTH // 2, 370)),
        )

    def _build_result(self) -> Level2Result:
        total = self.wave_manager.total_zombies
        kill_ratio = self.zombies_defeated / total if total else 0.0
        score = min(100.0, round(kill_ratio * 70.0 + (30.0 if self.result == "VICTORY" else 0.0), 2))
        return Level2Result(
            victory=self.result == "VICTORY",
            difficulty=self.difficulty.name,
            zombies_total=total,
            zombies_killed=self.zombies_defeated,
            zombies_escaped=self.zombies_escaped,
            wave_reached=min(
                self.wave_manager.wave_number,
                len(self.wave_manager.wave_counts),
            ),
            battle_time=round(self.battle_time, 2),
            score=score,
        )

    @staticmethod
    def _make_demo_plant() -> PlantData:
        status = PlantStatus(
            water=0.75,
            light=0.75,
            nitrogen=0.70,
            phosphorus=0.70,
            potassium=0.70,
            pest=0.90,
        )
        power = calculate_power(status)
        return PlantData(
            plant_id="LEVEL2_DEMO",
            plant_type="flower",
            image_path="",
            status=status,
            initial_power=power,
            current_power=power,
        )


def run_level2(
    plant: PlantData,
    difficulty: DifficultyConfig,
) -> Level2Result:
    """Run Level 2 using the input and output types agreed by the team."""
    smoke_test_frames = 5 if os.environ.get("PLANT_GAME_SMOKE_TEST") == "1" else None
    return Level2Game(plant, difficulty).run(max_frames=smoke_test_frames)
