"""Fast headless playthrough checks for all three shared plant types."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from level2.level2 import Level2Game
from shared_game_data import DIFFICULTIES, PlantData, PlantStatus


class Level2PlaythroughTests(unittest.TestCase):
    def tearDown(self) -> None:
        pygame.quit()

    def test_each_plant_type_can_complete_normal_difficulty(self) -> None:
        for plant_type in ("grass", "shrub", "flower"):
            with self.subTest(plant_type=plant_type):
                plant = PlantData(
                    plant_id=f"TEST_{plant_type.upper()}",
                    plant_type=plant_type,
                    image_path="",
                    status=PlantStatus(),
                    initial_power=70.0,
                    current_power=70.0,
                )
                game = Level2Game(plant, DIFFICULTIES["normal"])

                for _ in range(7_000):
                    if game.result is not None:
                        break
                    if game.zombies:
                        nearest = min(game.zombies, key=lambda zombie: zombie.rect.x)
                        game.player.move_to_lane(nearest.lane_index)
                    game._update(1 / 60)

                result = game._build_result()
                self.assertTrue(result.victory)
                self.assertEqual(result.zombies_killed, result.zombies_total)
                game.hand_controller.close()


if __name__ == "__main__":
    unittest.main()
