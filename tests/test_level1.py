from __future__ import annotations

from dataclasses import dataclass
import random
import unittest

import pygame

from shared_game_data import PlantData, PlantStatus, calculate_power

from level1.audio import _collect_pcm, _hurt_pcm, _music_pcm
from level1.config import (
    FINAL_OBSTACLE_CLUSTER_CHANCE,
    FINAL_SCROLL_SPEED,
    INITIAL_OBSTACLE_CLUSTER_CHANCE,
    INITIAL_OBSTACLE_INTERVAL,
    INITIAL_OBSTACLE_JITTER,
    INITIAL_SCROLL_SPEED,
    ITEM_HIGH_CENTER_Y,
    ITEM_LOW_CENTER_Y,
    ITEM_OBSTACLE_CLEARANCE,
    LOWER_FLOOR_Y,
    MIN_OBSTACLE_INTERVAL,
    MIN_OBSTACLE_JITTER,
    OBSTACLE_MIN_CLEARANCE,
    SLIDE_OBSTACLE_HEIGHT,
    TIME_LIMIT,
    obstacle_cluster_chance_at,
    obstacle_interval_at,
    scroll_speed_at,
)
from level1.demo_data import DEMO_STATUS, create_demo_plant
from level1.items import AdaptiveElementSampler, Collectible, ItemManager
from level1.level1 import Level1Game, calculate_level1_score
from level1.map import Obstacle
from level1.map import ObstacleManager
from level1.player import Player
from vision.camera_pose_input import CameraPoseInput
from vision.pose_control import GestureDebouncer, classify_landmarks


def make_plant() -> PlantData:
    status = PlantStatus(
        water=0.5,
        light=0.5,
        nitrogen=0.5,
        phosphorus=0.5,
        potassium=0.5,
        pest=1.0,
    )
    power = calculate_power(status)
    return PlantData(
        plant_id="TEST",
        plant_type="grass",
        image_path="",
        status=status,
        initial_power=power,
        current_power=power,
    )


class ConfigTests(unittest.TestCase):
    def test_scroll_speed_endpoints(self) -> None:
        self.assertEqual(TIME_LIMIT, 40.0)
        self.assertEqual(scroll_speed_at(0.0), INITIAL_SCROLL_SPEED)
        self.assertEqual(scroll_speed_at(TIME_LIMIT), FINAL_SCROLL_SPEED)
        self.assertEqual(scroll_speed_at(TIME_LIMIT * 2), FINAL_SCROLL_SPEED)

    def test_obstacle_density_starts_easier_and_reaches_dense_endpoint(self) -> None:
        self.assertEqual(
            obstacle_interval_at(0.0),
            (INITIAL_OBSTACLE_INTERVAL, INITIAL_OBSTACLE_JITTER),
        )
        end_interval, end_jitter = obstacle_interval_at(TIME_LIMIT)
        self.assertAlmostEqual(end_interval, MIN_OBSTACLE_INTERVAL)
        self.assertAlmostEqual(end_jitter, MIN_OBSTACLE_JITTER)
        start_spacing = INITIAL_SCROLL_SPEED * INITIAL_OBSTACLE_INTERVAL
        end_spacing = FINAL_SCROLL_SPEED * MIN_OBSTACLE_INTERVAL
        self.assertAlmostEqual(start_spacing, 504.0)
        self.assertAlmostEqual(end_spacing, 432.0)
        self.assertGreater(start_spacing, end_spacing)
        self.assertEqual(
            obstacle_cluster_chance_at(0.0),
            INITIAL_OBSTACLE_CLUSTER_CHANCE,
        )
        self.assertEqual(
            obstacle_cluster_chance_at(TIME_LIMIT),
            FINAL_OBSTACLE_CLUSTER_CHANCE,
        )

    def test_obstacle_manager_follows_reduced_40_second_curve(self) -> None:
        manager = ObstacleManager(random.Random(77))
        elapsed = 0.0
        for _ in range(round(TIME_LIMIT * 60)):
            elapsed += 1.0 / 60.0
            manager.update(1.0 / 60.0, elapsed, scroll_speed_at(elapsed))
        self.assertGreaterEqual(manager.total_spawned, 25)
        self.assertLessEqual(manager.total_spawned, 40)
        self.assertGreaterEqual(manager.clusters_spawned, 5)

    def test_clustered_obstacles_always_alternate_actions(self) -> None:
        manager = ObstacleManager(random.Random(19))
        previous = manager.spawn(30.0)
        for _ in range(30):
            clustered = manager.spawn_clustered(30.0)
            self.assertNotEqual(clustered.kind, previous.kind)
            previous = clustered

    def test_demo_input_has_complete_consistent_values(self) -> None:
        plant = create_demo_plant()
        self.assertEqual(plant.plant_id, "PLANT_LEVEL1_DEMO")
        self.assertEqual(plant.initial_power, plant.current_power)
        self.assertEqual(plant.status.water, DEMO_STATUS["water"])
        self.assertEqual(plant.status.pest, DEMO_STATUS["pest"])


class AudioTests(unittest.TestCase):
    def test_procedural_audio_buffers_are_nonempty(self) -> None:
        sample_rate = 8000
        collect = _collect_pcm("water", sample_rate, 1)
        hurt = _hurt_pcm(sample_rate, 1)
        music = _music_pcm(sample_rate, 1)
        self.assertGreater(len(collect), sample_rate // 4)
        self.assertGreater(len(hurt), sample_rate // 3)
        self.assertGreater(len(music), sample_rate * 10)


class PlayerTests(unittest.TestCase):
    def test_down_crouches_on_the_floor(self) -> None:
        player = Player()
        self.assertTrue(player.drop())
        self.assertTrue(player.crouching)
        self.assertTrue(player.grounded)

    def test_big_jump_has_more_vertical_velocity_than_normal_jump(self) -> None:
        normal = Player()
        large = Player()
        self.assertTrue(normal.jump())
        self.assertTrue(large.big_jump())
        self.assertLess(large.velocity_y, normal.velocity_y)

    def test_player_can_land_on_and_drop_from_air_platform(self) -> None:
        player = Player()
        platform = pygame.Rect(player.x - 5, 382, 100, 12)
        self.assertTrue(player.big_jump())
        for _ in range(90):
            player.update(1.0 / 60.0, (platform,))
            if player.grounded and player.support_y == platform.top:
                break
        self.assertEqual(player.support_y, platform.top)
        self.assertTrue(player.drop())
        self.assertIsNone(player.support_y)

    def test_airborne_player_cannot_jump_again(self) -> None:
        player = Player()
        self.assertTrue(player.jump())
        self.assertFalse(player.jump())

    def test_jump_has_longer_controlled_air_time(self) -> None:
        player = Player()
        self.assertTrue(player.jump())
        frames = 0
        while not player.grounded and frames < 120:
            player.update(1.0 / 60.0)
            frames += 1
        air_time = frames / 60.0
        self.assertGreaterEqual(air_time, 0.72)
        self.assertLessEqual(air_time, 0.85)

    def test_slide_locks_jump_until_it_finishes(self) -> None:
        player = Player()
        self.assertTrue(player.slide())
        self.assertFalse(player.jump())
        player.update(0.71)
        self.assertFalse(player.jump())
        player.update(0.02)
        self.assertTrue(player.jump())

    def test_slide_obstacle_cannot_be_bypassed_with_a_high_jump(self) -> None:
        player = Player()
        obstacle = Obstacle(
            player.x,
            "slide",
            64,
            SLIDE_OBSTACLE_HEIGHT,
        )
        self.assertTrue(player.jump())
        while player.velocity_y < 0.0:
            player.update(1.0 / 60.0)
        self.assertTrue(player.rect.colliderect(obstacle.rect))

    def test_slide_passes_under_slide_obstacle(self) -> None:
        player = Player()
        obstacle = Obstacle(
            player.x,
            "slide",
            64,
            SLIDE_OBSTACLE_HEIGHT,
        )
        self.assertTrue(player.slide())
        self.assertFalse(player.rect.colliderect(obstacle.rect))

    def test_damage_has_invincibility_window(self) -> None:
        player = Player()
        self.assertTrue(player.take_damage())
        self.assertFalse(player.take_damage())
        self.assertEqual(player.hp, 2)
        player.update(0.26)
        self.assertTrue(player.take_damage())
        self.assertEqual(player.hp, 1)


class ItemTests(unittest.TestCase):
    def test_pair_is_unique_and_probabilities_stay_valid(self) -> None:
        sampler = AdaptiveElementSampler(random.Random(12))
        first, second = sampler.draw_pair()
        self.assertNotEqual(first, second)
        self.assertAlmostEqual(sum(sampler.probabilities.values()), 1.0)
        self.assertGreaterEqual(min(sampler.probabilities.values()), 0.05)
        self.assertLess(sampler.probabilities[first], 1.0 / 6.0)
        self.assertLess(sampler.probabilities[second], 1.0 / 6.0)

        for _ in range(500):
            first, second = sampler.draw_pair()
            self.assertNotEqual(first, second)
        self.assertAlmostEqual(sum(sampler.probabilities.values()), 1.0)
        self.assertGreaterEqual(min(sampler.probabilities.values()), 0.05 - 1e-12)

    def test_pair_uses_separate_high_and_low_positions(self) -> None:
        high, low = ItemManager(random.Random(5)).spawn_pair()
        self.assertEqual(high.center_y, ITEM_HIGH_CENTER_Y)
        self.assertEqual(low.center_y, ITEM_LOW_CENTER_Y)
        self.assertEqual(high.x, low.x)
        self.assertLess(high.rect.bottom + 78, low.rect.top)

    def test_randomized_pair_uses_different_spawn_positions(self) -> None:
        high, low = ItemManager(random.Random(5), randomized_layout=True).spawn_pair()
        self.assertIn(high.center_y, (332, 382, 438, 486))
        self.assertIn(low.center_y, (332, 382, 438, 486))
        self.assertNotEqual((high.x, high.center_y), (low.x, low.center_y))

    def test_live_pair_has_one_air_route_and_one_ground_route(self) -> None:
        high, low = ItemManager(random.Random(9), randomized_layout=True).spawn_pair()
        self.assertIn(high.surface, {"ground", "platform"})
        self.assertEqual(low.surface, "air")

    def test_live_pair_can_attach_lane_pickup_to_a_floating_platform(self) -> None:
        platform = pygame.Rect(850, 382, 118, 12)
        high, low = ItemManager(random.Random(0), randomized_layout=True).spawn_pair((platform,))
        self.assertEqual(high.surface, "platform")
        self.assertEqual(high.rect.bottom, platform.top)
        self.assertEqual(low.surface, "air")

    def test_collect_animation_expires_without_removing_other_items(self) -> None:
        manager = ItemManager(random.Random(3))
        first, second = manager.spawn_pair()
        self.assertTrue(manager.collect_item(first))
        self.assertEqual(manager.items, [second])
        manager.update(0.39, 240.0)
        self.assertEqual(manager.collecting_items, [])

    def test_due_pair_waits_until_spawn_window_is_clear(self) -> None:
        manager = ItemManager(random.Random(6))
        manager.spawn_remaining = 0.0
        self.assertIsNone(manager.update(0.01, 240.0, can_spawn=False))
        self.assertEqual(manager.items, [])
        pair = manager.update(0.01, 240.0, can_spawn=True)
        self.assertIsNotNone(pair)


class GameStateTests(unittest.TestCase):
    def test_score_matches_agreed_normalized_scale(self) -> None:
        plant = make_plant()
        initial = {
            "water": 0.5,
            "light": 0.5,
            "nitrogen": 0.5,
            "phosphorus": 0.5,
            "potassium": 0.5,
            "pest": 1.0,
        }
        self.assertEqual(calculate_level1_score(initial, plant.status, 3), 50.0)
        self.assertEqual(calculate_level1_score(initial, plant.status, 0), 0.0)

    def test_collecting_one_item_removes_its_pair(self) -> None:
        plant = make_plant()
        game = Level1Game(plant, rng=random.Random(2))
        rect = game.player.rect
        first = Collectible(
            float(rect.left), ITEM_LOW_CENTER_Y, "water", pair_id=99
        )
        second = Collectible(
            float(rect.left), ITEM_HIGH_CENTER_Y, "light", pair_id=99
        )
        game.items.items = [first, second]
        game._resolve_collisions()
        self.assertEqual(game.collected["water"], 1)
        self.assertEqual(len(game.items.items), 1)
        self.assertEqual(len(game.items.collecting_items), 1)
        self.assertGreater(plant.status.water, 0.5)
        self.assertEqual(game.consume_audio_events(), [("collect", "water")])
        self.assertEqual(game.consume_audio_events(), [])

    def test_jump_collects_high_item_without_touching_low_item(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(8))
        high = Collectible(
            game.player.x, ITEM_HIGH_CENTER_Y, "light", pair_id=100
        )
        low = Collectible(
            game.player.x, ITEM_LOW_CENTER_Y, "water", pair_id=100
        )
        game.items.items = [high, low]
        self.assertTrue(game.player.jump())
        for _ in range(60):
            game.player.update(1.0 / 60.0)
            if game.player.rect.colliderect(high.rect):
                break
        self.assertTrue(game.player.rect.colliderect(high.rect))
        self.assertFalse(game.player.rect.colliderect(low.rect))
        game._resolve_collisions()
        self.assertEqual(game.collected["light"], 1)
        self.assertEqual(len(game.items.items), 1)
        self.assertEqual(len(game.items.collecting_items), 1)

    def test_route_rules_block_wrong_collection_state(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(13))
        ground = Collectible(game.player.x, ITEM_LOW_CENTER_Y, "water", 201, surface="ground")
        air = Collectible(game.player.x, ITEM_HIGH_CENTER_Y, "light", 202, surface="air")
        game.items.items = [ground, air]
        game.player.jump()
        for _ in range(60):
            game.player.update(1.0 / 60.0)
            if game.player.rect.colliderect(air.rect):
                break
        game._resolve_collisions()
        self.assertEqual(game.collected["water"], 0)
        self.assertEqual(game.collected["light"], 1)
        game.player._land()
        game.items.items = [ground]
        game._resolve_collisions()
        self.assertEqual(game.collected["water"], 1)

    def test_item_pair_does_not_spawn_beside_obstacle(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(10))
        obstacle = Obstacle(825.0, "jump", 44, 55)
        game.obstacles.obstacles = [obstacle]
        game.obstacles.spawn_remaining = 10.0
        self.assertFalse(game._reserve_item_spawn_window(240.0))

    def test_item_slot_delays_whole_obstacle_schedule_equally(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(12))
        game.obstacles.spawn_remaining = 0.30
        game.obstacles.cluster_remaining = 0.55
        original_difference = (
            game.obstacles.cluster_remaining - game.obstacles.spawn_remaining
        )
        self.assertTrue(game._reserve_item_spawn_window(240.0))
        self.assertAlmostEqual(
            game.obstacles.cluster_remaining - game.obstacles.spawn_remaining,
            original_difference,
        )

    def test_new_obstacle_clumping_with_obstacle_is_cancelled(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(11))
        existing = Obstacle(600.0, "jump", 44, 55)
        new = Obstacle(825.0, "slide", 64, 34)
        game.obstacles.obstacles = [existing, new]
        game.obstacles.total_spawned = 2
        game.obstacles.last_obstacle = new
        game._reject_clumped_obstacles([new])
        self.assertEqual(game.obstacles.obstacles, [existing])
        self.assertEqual(game.obstacles.total_spawned, 1)

    def test_full_course_never_clumps_obstacles(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(17))
        elapsed = 0.0
        for _ in range(round(TIME_LIMIT * 60)):
            elapsed += 1.0 / 60.0
            speed = scroll_speed_at(elapsed)
            new_obstacles = game.obstacles.update(
                1.0 / 60.0, elapsed, speed
            )
            game._reject_clumped_obstacles(new_obstacles)
            item_spawn_due = game.items.spawn_remaining <= 1.0 / 60.0
            can_spawn_item = (
                game._reserve_item_spawn_window(speed)
                if item_spawn_due
                else True
            )
            game.items.update(
                1.0 / 60.0,
                speed,
                can_spawn=can_spawn_item,
            )
            obstacles = sorted(game.obstacles.obstacles, key=lambda item: item.x)
            for left, right in zip(obstacles, obstacles[1:]):
                edge_gap = right.x - (left.x + left.width)
                self.assertGreaterEqual(edge_gap, OBSTACLE_MIN_CLEARANCE)
            for obstacle in obstacles:
                for item in game.items.items:
                    if obstacle.x + obstacle.width < item.x:
                        gap = item.x - (obstacle.x + obstacle.width)
                    elif item.x + item.size < obstacle.x:
                        gap = obstacle.x - (item.x + item.size)
                    else:
                        gap = 0.0
                    self.assertGreaterEqual(gap, ITEM_OBSTACLE_CLEARANCE)
        self.assertGreaterEqual(game.obstacles.total_spawned, 18)
        self.assertGreaterEqual(game.obstacles.clusters_spawned, 3)
        self.assertGreaterEqual(game.items._next_pair_id - 1, 10)

    def test_overlapping_obstacles_only_cost_one_hp_while_invincible(self) -> None:
        game = Level1Game(make_plant(), rng=random.Random(3))
        rect = game.player.rect
        first = Obstacle(float(rect.left), "jump", rect.width, 55)
        second = Obstacle(float(rect.left), "jump", rect.width, 55)
        game.obstacles.obstacles = [first, second]
        game._resolve_collisions()
        self.assertEqual(game.player.hp, 2)
        self.assertEqual(game.pest_hits, 1)
        self.assertEqual(game.consume_audio_events(), [("hurt", None)])


@dataclass
class FakeLandmark:
    x: float = 0.5
    y: float = 0.8
    visibility: float = 1.0


class PoseTests(unittest.TestCase):
    def make_landmarks(self) -> list[FakeLandmark]:
        points = [FakeLandmark() for _ in range(17)]
        points[11].y = 0.5
        points[12].y = 0.5
        return points

    def test_left_hand_is_jump_and_right_hand_is_crouch(self) -> None:
        points = self.make_landmarks()
        points[15].y = 0.3
        self.assertEqual(classify_landmarks(points), "jump")
        points[15].y = 0.8
        points[16].y = 0.3
        self.assertEqual(classify_landmarks(points), "crouch")

    def test_right_hand_near_shoulder_triggers_fast_crouch(self) -> None:
        points = self.make_landmarks()
        points[16].y = 0.52
        points[16].visibility = 0.36
        self.assertEqual(classify_landmarks(points), "crouch")

    def test_both_hands_do_not_trigger_an_action(self) -> None:
        points = self.make_landmarks()
        points[15].y = 0.3
        points[16].y = 0.3
        self.assertEqual(classify_landmarks(points), "none")

    def test_action_triggers_in_one_frame_and_release_rearms_it(self) -> None:
        debouncer = GestureDebouncer()
        self.assertEqual(debouncer.update("jump", 0.00), "jump")
        self.assertEqual(debouncer.update("jump", 0.02), "none")
        self.assertEqual(debouncer.update("jump", 0.20), "none")
        self.assertEqual(debouncer.update("none", 0.21), "none")
        self.assertEqual(debouncer.update("jump", 0.22), "jump")

    def test_left_hand_near_shoulder_triggers_fast_jump(self) -> None:
        points = self.make_landmarks()
        points[15].y = 0.52
        points[15].visibility = 0.36
        self.assertEqual(classify_landmarks(points), "jump")

    def test_camera_action_read_does_not_run_pose_inference(self) -> None:
        camera = CameraPoseInput(None, 0, "test")

        def fail_if_called(_frame):
            raise AssertionError("pose inference must stay off the game thread")

        camera.controller.get_gesture = fail_if_called
        camera._pending_actions.append("jump")
        self.assertEqual(camera.read_action(), "jump")
        self.assertEqual(camera.read_action(), "none")

    def test_holding_crouch_does_not_repeat(self) -> None:
        debouncer = GestureDebouncer()
        self.assertEqual(debouncer.update("crouch", 0.00), "crouch")
        self.assertEqual(debouncer.update("crouch", 0.02), "none")
        self.assertEqual(debouncer.update("crouch", 0.50), "none")

    def test_single_jump_returns_to_the_track(self) -> None:
        player = Player()
        self.assertTrue(player.jump())
        for _ in range(120):
            player.update(1.0 / 60.0)
            if player.grounded:
                break
        self.assertTrue(player.grounded)
        self.assertEqual(player.rect.bottom, LOWER_FLOOR_Y)


if __name__ == "__main__":
    unittest.main()
