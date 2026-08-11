"""Tests for the second-level lane layout."""

import unittest

from level2.config import LANE_COUNT, lane_center_y
from level2.wave_manager import WaveManager


class LaneLayoutTests(unittest.TestCase):
    def test_lane_centres_are_ordered(self) -> None:
        centres = [lane_center_y(index) for index in range(LANE_COUNT)]
        self.assertEqual(centres, sorted(centres))
        self.assertEqual(len(set(centres)), LANE_COUNT)

    def test_invalid_lane_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            lane_center_y(-1)

    def test_wave_lane_schedule_is_balanced(self) -> None:
        manager = WaveManager(random_seed=7)
        lanes = list(manager._pending_lanes)
        counts = [lanes.count(index) for index in range(LANE_COUNT)]
        self.assertLessEqual(max(counts) - min(counts), 1)


if __name__ == "__main__":
    unittest.main()
