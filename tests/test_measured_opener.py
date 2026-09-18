"""The measured opener: K=4 bird play values choose the kept birds."""

from collections import Counter
from unittest import TestCase, skipIf

from wingspan_ai.agents.bird_values import BirdPlayValues, load_bird_play_values
from wingspan_ai.agents.setup import (
    InitialSelectionContext,
    PotentialPointsSetupPolicy,
    _measured_selection_score,
    _pay_from_pool,
    is_potential_points_setup_policy_id,
    potential_points_setup_policy,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.base_game import setup_base_game


class PolicyIdTests(TestCase):
    def test_measured_mode_gets_the_v3_id_with_its_keep_count(self) -> None:
        self.assertEqual(
            PotentialPointsSetupPolicy(bird_scoring="measured").policy_id,
            "potential_points_setup_v3",
        )
        policy = potential_points_setup_policy("potential_points_setup_v3_keep3")
        self.assertEqual(policy.policy_id, "potential_points_setup_v3_keep3")
        self.assertEqual((policy.bird_scoring, policy.target_keep_count), ("measured", 3))
        self.assertEqual(
            potential_points_setup_policy("potential_points_setup_v2").policy_id,
            "potential_points_setup_v2",
        )
        # Existing ids are unchanged.
        self.assertEqual(PotentialPointsSetupPolicy().policy_id, "potential_points_setup_v2")
        self.assertTrue(is_potential_points_setup_policy_id("potential_points_setup_v3_keep3"))
        self.assertFalse(is_potential_points_setup_policy_id("control"))
        with self.assertRaises(ValueError):
            potential_points_setup_policy("potential_points_setup_v9")
        with self.assertRaises(ValueError):
            PotentialPointsSetupPolicy(bird_scoring="vibes")


class ScoringTests(TestCase):
    def test_table_has_every_base_bird_and_falls_back_to_the_intercept(self) -> None:
        values = load_bird_play_values()
        self.assertEqual(values.version, "bird_play_values_k4")
        self.assertGreater(len(values.values), 150)
        self.assertEqual(values.value("Not A Bird"), values.intercept)
        self.assertGreater(values.value("Barn Swallow"), values.intercept + 5)

    @skipIf(not DEFAULT_WORKBOOK_PATH.exists(), "workbook required")
    def test_birds_are_paid_greedily_from_the_starting_food(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        by_name = {card.common_name: card for card in catalog.birds}
        owl = by_name["Burrowing Owl"]  # invertebrate + rodent
        canvasback = by_name["Canvasback"]  # seed
        pool = Counter({FoodType.INVERTEBRATE: 1, FoodType.RODENT: 1})
        self.assertTrue(_pay_from_pool(pool, owl))
        self.assertEqual(sum(pool.values()), 0)
        self.assertFalse(_pay_from_pool(pool, canvasback))
        values = BirdPlayValues("t", 4.0, {"Burrowing Owl": 8.0, "Canvasback": 3.0})
        food = (FoodType.INVERTEBRATE, FoodType.RODENT)
        score = _measured_selection_score(
            (owl, canvasback), food, values, food_value=2.5, unaffordable_discount=0.5
        )
        # owl affordable (8) + canvasback not (1.5) + two food (5)
        self.assertAlmostEqual(score, 8.0 + 1.5 + 5.0)

    @skipIf(not DEFAULT_WORKBOOK_PATH.exists(), "workbook required")
    def test_keep3_variant_keeps_three_birds_and_prefers_measured_value(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        values = load_bird_play_values()
        policy = potential_points_setup_policy("potential_points_setup_v3_keep3")
        control_total = policy_total = 0.0
        for seed in range(1, 21):
            state = setup_base_game(
                catalog, player_ids=["p1", "p2"], random_seed=seed, apply_initial_selection=False
            )
            player = state.players[0]
            selection = policy.choose_initial_selection(player, InitialSelectionContext())
            self.assertEqual(len(selection.kept_bird_names), 3)
            self.assertEqual(len(selection.starting_food), 2)
            self.assertEqual(len(selection.kept_bonus_card_names), 1)
            ranked = sorted(player.hand, key=lambda c: -values.value(c.common_name))
            control_total += sum(values.value(c.common_name) for c in ranked[-3:])
            policy_total += sum(values.value(n) for n in selection.kept_bird_names)
        self.assertGreater(policy_total, control_total)
