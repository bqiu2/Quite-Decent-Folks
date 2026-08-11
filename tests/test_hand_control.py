"""Tests for index-finger direction recognition."""

import unittest
from types import SimpleNamespace

from vision.hand_control import HandController


def point(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def pointing_hand(direction: str, open_palm: bool = False) -> list[SimpleNamespace]:
    """Build the small subset of 21 landmarks used by the classifier."""
    wrist_y = 0.70 if direction != "down" else 0.30
    landmarks = [point(0.50, wrist_y) for _ in range(21)]
    landmarks[0] = point(0.50, wrist_y)
    landmarks[9] = point(0.50, 0.55 if direction != "down" else 0.45)

    if direction == "up":
        landmarks[6] = point(0.50, 0.47)
        landmarks[8] = point(0.50, 0.25)
    elif direction == "down":
        landmarks[6] = point(0.50, 0.53)
        landmarks[8] = point(0.50, 0.75)
    else:
        landmarks[6] = point(0.50, 0.47)
        landmarks[8] = point(0.75, 0.47)

    for pip_index, tip_index in ((10, 12), (14, 16), (18, 20)):
        away_y = wrist_y - 0.18 if direction != "down" else wrist_y + 0.18
        folded_y = wrist_y - 0.07 if direction != "down" else wrist_y + 0.07
        landmarks[pip_index] = point(0.50, away_y)
        landmarks[tip_index] = point(0.50, away_y - 0.12 if open_palm else folded_y)

    return landmarks


class IndexDirectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = HandController()

    def test_index_pointing_up(self) -> None:
        self.assertEqual(self.controller._classify_index_direction(pointing_hand("up")), "up")

    def test_index_pointing_down(self) -> None:
        self.assertEqual(self.controller._classify_index_direction(pointing_hand("down")), "down")

    def test_horizontal_index_is_neutral(self) -> None:
        self.assertEqual(self.controller._classify_index_direction(pointing_hand("side")), "none")

    def test_open_palm_is_not_a_pointing_gesture(self) -> None:
        self.assertEqual(
            self.controller._classify_index_direction(pointing_hand("up", open_palm=True)),
            "none",
        )


if __name__ == "__main__":
    unittest.main()
