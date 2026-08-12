"""Tests for the end-to-end launcher helpers."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from main import _parse_args
from plant_ai import plant_analyzer
from shared_game_data import FinalResult, save_game_result


class MainFlowTests(unittest.TestCase):
    def test_demo_and_runtime_options_parse(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["main.py", "--demo", "--difficulty", "hard", "--no-camera", "--no-wait"],
        ):
            args = _parse_args()
        self.assertTrue(args.demo)
        self.assertEqual(args.difficulty, "hard")
        self.assertTrue(args.no_camera)
        self.assertTrue(args.no_wait)

    def test_result_save_creates_parent_directory(self) -> None:
        result = FinalResult(
            plant_id="PLANT_TEST",
            plant_type="flower",
            initial_power=50.0,
            final_power=55.0,
            level1_score=60.0,
            level2_score=70.0,
            difficulty="normal",
            difficulty_multiplier=1.2,
            final_score=66.0,
            victory=True,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "nested" / "result.json"
            save_game_result(result, str(output))
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["victory"], True)

    def test_plant_ids_continue_from_persisted_counter(self) -> None:
        original_path = plant_analyzer._COUNTER_PATH
        original_fallback = plant_analyzer._FALLBACK_COUNTER
        with tempfile.TemporaryDirectory() as temporary_directory:
            plant_analyzer._COUNTER_PATH = Path(temporary_directory) / "counter.txt"
            plant_analyzer._FALLBACK_COUNTER = 0
            first = plant_analyzer._new_plant_id()
            second = plant_analyzer._new_plant_id()
            self.assertEqual(first, "PLANT_0001")
            self.assertEqual(second, "PLANT_0002")
            plant_analyzer._FALLBACK_COUNTER = 0
            self.assertEqual(plant_analyzer._new_plant_id(), "PLANT_0003")
        plant_analyzer._COUNTER_PATH = original_path
        plant_analyzer._FALLBACK_COUNTER = original_fallback


if __name__ == "__main__":
    unittest.main()
