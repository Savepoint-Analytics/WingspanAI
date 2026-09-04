"""Policy-side feeder valuation and its ablation switch."""

from __future__ import annotations

from unittest import TestCase, mock

from wingspan_ai.agents import feeder_odds
from wingspan_ai.agents.feeder_odds import (
    food_power_availability_multiplier,
    hand_food_deficits,
)
from wingspan_ai.content.schemas import FoodType


class AvailabilityMultiplierTests(TestCase):
    def test_common_foods_are_weighted_above_rare_ones(self) -> None:
        """Seed shows on two die faces of six, fish on one."""

        self.assertGreater(
            food_power_availability_multiplier(FoodType.SEED),
            food_power_availability_multiplier(FoodType.FISH),
        )

    def test_a_seed_power_is_worth_about_twice_a_fish_power(self) -> None:
        ratio = food_power_availability_multiplier(FoodType.SEED) / (
            food_power_availability_multiplier(FoodType.FISH)
        )
        self.assertAlmostEqual(ratio, 2.0, places=6)

    def test_an_unspecified_food_is_unweighted(self) -> None:
        """Wild and [die] powers take whatever shows, so they need no weighting."""

        self.assertEqual(food_power_availability_multiplier(None), 1.0)

    def test_the_switch_disables_weighting(self) -> None:
        with mock.patch.object(feeder_odds, "VALUE_FEEDER_ODDS", False):
            self.assertEqual(food_power_availability_multiplier(FoodType.FISH), 1.0)

    def test_the_weight_scale_moves_the_multiplier(self) -> None:
        with mock.patch.object(feeder_odds, "FEEDER_ODDS_WEIGHT_SCALE", 0.0):
            self.assertEqual(food_power_availability_multiplier(FoodType.FISH), 1.0)


class HandDeficitTests(TestCase):
    def test_only_unmet_costs_count(self) -> None:
        class _Cost:
            fixed = {FoodType.FISH: 2, FoodType.SEED: 1}

        class _Card:
            food_cost = _Cost()

        class _Player:
            hand = [_Card()]
            food_tokens = {FoodType.FISH: 1}

        deficits = hand_food_deficits(_Player())
        self.assertEqual(deficits[FoodType.FISH], 1)
        self.assertEqual(deficits[FoodType.SEED], 1)

    def test_a_fully_funded_hand_has_no_deficit(self) -> None:
        class _Cost:
            fixed = {FoodType.SEED: 1}

        class _Card:
            food_cost = _Cost()

        class _Player:
            hand = [_Card()]
            food_tokens = {FoodType.SEED: 3}

        self.assertEqual(hand_food_deficits(_Player()), {})
