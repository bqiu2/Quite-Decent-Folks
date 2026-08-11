"""Tests for the shared Level 2 input/output contract."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from level2.level2 import Level2Game
from shared_game_data import DIFFICULTIES, Level2Result, PlantData, PlantStatus


class Level2IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plant = PlantData(
            plant_id="TEST_PLANT",
            plant_type="shrub",
            image_path="",
            status=PlantStatus(),
            initial_power=50.0,
            current_power=62.0,
        )

    def tearDown(self) -> None:
        pygame.quit()

    def test_game_uses_shared_plant_and_difficulty(self) -> None:
        game = Level2Game(self.plant, DIFFICULTIES["hard"])
        self.assertEqual(game.player.plant_type, "shrub")
        self.assertEqual(game.difficulty.name, "hard")
        self.assertEqual(game.attack_config["attack_name"], "earthquake")
        game.hand_controller.close()

    def test_result_matches_shared_dataclass(self) -> None:
        game = Level2Game(self.plant, DIFFICULTIES["normal"])
        game.result = "VICTORY"
        game.zombies_defeated = game.wave_manager.total_zombies
        result = game._build_result()
        self.assertIsInstance(result, Level2Result)
        self.assertTrue(result.victory)
        self.assertEqual(result.difficulty, "normal")
        self.assertEqual(result.score, 100.0)
        game.hand_controller.close()


if __name__ == "__main__":
    unittest.main()
