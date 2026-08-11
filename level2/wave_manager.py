"""Two-wave zombie spawning and progression logic."""

from __future__ import annotations

import random

from .config import (
    LANE_COUNT,
    SPAWN_INTERVAL,
    WAVE_COUNTS,
    WAVE_INTERMISSION,
)


class WaveManager:
    """Creates two balanced-but-random zombie lane schedules."""

    def __init__(
        self,
        random_seed: int | None = None,
        count_multiplier: float = 1.0,
    ) -> None:
        self._random = random.Random(random_seed)
        self.wave_counts = tuple(
            max(1, round(count * count_multiplier)) for count in WAVE_COUNTS
        )
        self.wave_index = 0
        self._pending_lanes = self._make_lane_schedule(self.wave_counts[0])
        self._spawn_timer = 0.6
        self._intermission = WAVE_INTERMISSION
        self.finished = False

    @property
    def wave_number(self) -> int:
        return self.wave_index + 1

    @property
    def remaining_to_spawn(self) -> int:
        return len(self._pending_lanes)

    @property
    def total_zombies(self) -> int:
        return sum(self.wave_counts)

    def update(self, dt: float, active_zombies: int) -> int | None:
        """Return a lane when it is time to spawn the next zombie."""
        if self.finished:
            return None

        if self._pending_lanes:
            self._spawn_timer -= dt
            if self._spawn_timer <= 0:
                self._spawn_timer = SPAWN_INTERVAL
                return self._pending_lanes.pop()
            return None

        if active_zombies > 0:
            return None

        if self.wave_index >= len(self.wave_counts) - 1:
            self.finished = True
            return None

        self._intermission -= dt
        if self._intermission <= 0:
            self.wave_index += 1
            self._pending_lanes = self._make_lane_schedule(self.wave_counts[self.wave_index])
            self._spawn_timer = 0.5
            self._intermission = WAVE_INTERMISSION

        return None

    def _make_lane_schedule(self, zombie_count: int) -> list[int]:
        lanes = [index % LANE_COUNT for index in range(zombie_count)]
        self._random.shuffle(lanes)
        return lanes
