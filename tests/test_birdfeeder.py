"""Birdfeeder die faces, supply feasibility, and food odds.

The die was modelled as a uniform draw over five foods (0.200 each). The real
die has six faces, the sixth showing invertebrate + seed, so those two foods are
obtainable on two faces of six. These tests pin the corrected distribution and
the choice semantics that come with a combined face.
"""

from __future__ import annotations

import random
from collections import Counter
from unittest import TestCase

from wingspan_ai.content.birdfeeder import (
    BIRDFEEDER_DICE_COUNT,
    DIE_FACES,
    BirdfeederFace,
    all_faces_match,
    all_supplies,
    can_supply,
    die_probability,
    expected_useful_food,
    obtainable_foods,
    probability_any_available,
    probability_food_obtainable,
    roll_dice,
    supplying_die_index,
)
from wingspan_ai.content.schemas import FoodType

INV = FoodType.INVERTEBRATE
SEED = FoodType.SEED
FISH = FoodType.FISH
COMBO = BirdfeederFace.INVERTEBRATE_OR_SEED


class DieFaceTests(TestCase):
    def test_the_die_has_six_faces(self) -> None:
        self.assertEqual(len(DIE_FACES), 6)

    def test_invertebrate_and_seed_appear_on_two_faces(self) -> None:
        self.assertAlmostEqual(die_probability(INV), 2 / 6)
        self.assertAlmostEqual(die_probability(SEED), 2 / 6)

    def test_the_other_foods_appear_on_one_face(self) -> None:
        for food in (FISH, FoodType.RODENT, FoodType.FRUIT):
            self.assertAlmostEqual(die_probability(food), 1 / 6)

    def test_rolled_distribution_matches_the_face_model(self) -> None:
        rng = random.Random(11)
        counts: Counter[FoodType] = Counter()
        rolls = 30000
        for face in roll_dice(rng, rolls):
            counts.update(obtainable_foods([face]))
        # delta, not decimal places: 30k rolls leaves ~0.005 of sampling noise.
        self.assertAlmostEqual(counts[INV] / rolls, 2 / 6, delta=0.01)
        self.assertAlmostEqual(counts[FISH] / rolls, 1 / 6, delta=0.01)


class SupplyTests(TestCase):
    def test_a_combined_face_supplies_either_food(self) -> None:
        self.assertTrue(can_supply([COMBO], [INV]))
        self.assertTrue(can_supply([COMBO], [SEED]))

    def test_a_combined_face_cannot_supply_both_foods_at_once(self) -> None:
        """One die yields one food; counting each food separately would miss this."""

        self.assertFalse(can_supply([COMBO], [INV, SEED]))

    def test_two_combined_faces_supply_one_of_each(self) -> None:
        self.assertTrue(can_supply([COMBO, COMBO], [INV, SEED]))

    def test_matching_reassigns_a_die_when_a_greedy_pick_would_fail(self) -> None:
        """Taking the combined die for the invertebrate first must not strand the seed."""

        self.assertTrue(can_supply([COMBO, BirdfeederFace.INVERTEBRATE], [INV, SEED]))

    def test_cannot_supply_more_foods_than_dice(self) -> None:
        self.assertFalse(can_supply([BirdfeederFace.FISH], [FISH, FISH]))

    def test_spending_prefers_the_least_flexible_die(self) -> None:
        """Keep the combined die for a food only it can still cover."""

        faces = [COMBO, BirdfeederFace.INVERTEBRATE]
        self.assertEqual(supplying_die_index(faces, INV), 1)

    def test_spending_returns_none_when_no_die_qualifies(self) -> None:
        self.assertIsNone(supplying_die_index([BirdfeederFace.FISH], INV))

    def test_all_supplies_excludes_infeasible_multisets(self) -> None:
        options = all_supplies([COMBO], 1, (INV, SEED, FISH))
        self.assertIn((INV,), options)
        self.assertIn((SEED,), options)
        self.assertNotIn((FISH,), options)


class RerollTests(TestCase):
    def test_a_lone_die_trivially_matches(self) -> None:
        """One die always shows "the same face", so a reroll is legal."""

        self.assertTrue(all_faces_match([BirdfeederFace.SEED]))

    def test_mixed_faces_do_not_match(self) -> None:
        self.assertFalse(all_faces_match([BirdfeederFace.SEED, BirdfeederFace.FISH]))

    def test_a_combined_face_is_not_the_same_face_as_a_plain_one(self) -> None:
        self.assertFalse(all_faces_match([COMBO, BirdfeederFace.INVERTEBRATE]))


class OddsTests(TestCase):
    def test_food_already_showing_is_certain(self) -> None:
        self.assertEqual(probability_food_obtainable([BirdfeederFace.FISH], FISH, 1), 1.0)

    def test_a_combined_face_counts_as_showing_both_foods(self) -> None:
        self.assertEqual(probability_food_obtainable([COMBO], INV, 1), 1.0)

    def test_the_motivating_scenario(self) -> None:
        """One non-fish die, three draws: the feeder empties and refills to five.

        A naive read of the single die concludes the fish is unavailable. It is
        available roughly three times in five.
        """

        self.assertAlmostEqual(
            probability_food_obtainable([BirdfeederFace.SEED], FISH, 3),
            1 - (5 / 6) ** 5,
            places=6,
        )

    def test_no_draws_means_no_chance(self) -> None:
        self.assertEqual(probability_food_obtainable([BirdfeederFace.SEED], FISH, 0), 0.0)

    def test_predator_success_rate(self) -> None:
        """1 - (4/6)^5, not the 1 - (3/5)^5 = 0.92 the uniform die implied."""

        rate = probability_any_available((FoodType.RODENT, FISH), BIRDFEEDER_DICE_COUNT)
        self.assertAlmostEqual(rate, 1 - (4 / 6) ** 5, places=6)
        self.assertLess(rate, 0.92)


class ExpectedFoodTests(TestCase):
    def test_counts_dice_rather_than_testing_membership(self) -> None:
        """Three fish showing must be worth more than one, which `in` cannot express."""

        one = expected_useful_food([BirdfeederFace.FISH] * 1 + [BirdfeederFace.SEED] * 2, [FISH], 3)
        three = expected_useful_food([BirdfeederFace.FISH] * 3, [FISH], 3)
        self.assertEqual(one, 1.0)
        self.assertEqual(three, 3.0)

    def test_draws_beyond_the_feeder_are_credited_at_the_fresh_roll_rate(self) -> None:
        value = expected_useful_food([BirdfeederFace.FISH], [FISH], 3)
        self.assertAlmostEqual(value, 1 + 2 * (1 / 6))

    def test_no_wanted_food_is_worth_nothing(self) -> None:
        self.assertEqual(expected_useful_food([BirdfeederFace.FISH], [], 3), 0.0)
