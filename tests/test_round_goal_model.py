"""The placement model for end-of-round goals.

Registered 2026-09-22 (`docs/experiments/round_goal_placement_model.md`).
The properties that matter are the ones the old heuristic got wrong: the
round's own placement scale, the opponent's remaining turns, and ties.
"""

from unittest import TestCase

from wingspan_ai.agents.potential_points import (
    ROUND_GOAL_MODELS,
    PotentialPointsAgent,
    PotentialPointsSearchConfig,
    evaluate_state_potential,
)
from wingspan_ai.agents.round_goal_model import (
    expected_placement_points,
    final_count_distribution,
    load_progress_rates,
)
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.base_game import (
    ROUND_GOAL_GREEN_SCORES,
    legal_actions_for_current_player,
    setup_base_game,
)

ROUND_1 = ROUND_GOAL_GREEN_SCORES[1]  # 4 / 1
ROUND_4 = ROUND_GOAL_GREEN_SCORES[4]  # 7 / 4 / 3


class PlacementArithmeticTests(TestCase):
    def test_settled_positions_score_exactly_what_the_rules_award(self) -> None:
        # No turns left: the placement is decided, so the expectation is the
        # award itself, including the tie split rounded down.
        self.assertAlmostEqual(expected_placement_points(2, 0, [1], [0], ROUND_1, 0.3), 4.0)
        self.assertAlmostEqual(expected_placement_points(1, 0, [2], [0], ROUND_1, 0.3), 1.0)
        self.assertAlmostEqual(expected_placement_points(1, 0, [1], [0], ROUND_1, 0.3), 2.0)
        # A player with no items never qualifies, whatever the others do.
        self.assertAlmostEqual(expected_placement_points(0, 0, [0], [0], ROUND_1, 0.3), 0.0)

    def test_three_player_tie_splits_the_top_two_slots(self) -> None:
        # Two level at the top of a 5/2/1 round: (5 + 2) // 2 = 3 each.
        value = expected_placement_points(2, 0, [2, 1], [0, 0], ROUND_GOAL_GREEN_SCORES[2], 0.3)
        self.assertAlmostEqual(value, 3.0)
        # Third place still scores in rounds 2-4.
        third = expected_placement_points(1, 0, [3, 2], [0, 0], ROUND_GOAL_GREEN_SCORES[2], 0.3)
        self.assertAlmostEqual(third, 1.0)

    def test_the_round_scale_changes_the_value_of_the_same_position(self) -> None:
        early = expected_placement_points(3, 2, [3], [2], ROUND_1, 0.5)
        late = expected_placement_points(3, 2, [3], [2], ROUND_4, 0.5)
        self.assertGreater(late, early + 2.0)

    def test_opponent_turns_left_matter(self) -> None:
        exposed = expected_placement_points(2, 0, [1], [4], ROUND_1, 0.5)
        safe = expected_placement_points(2, 0, [1], [0], ROUND_1, 0.5)
        self.assertLess(exposed, safe)
        self.assertGreater(safe - exposed, 0.5)

    def test_my_turns_left_help_from_behind(self) -> None:
        stuck = expected_placement_points(1, 0, [2], [0], ROUND_1, 0.5)
        chasing = expected_placement_points(1, 5, [2], [0], ROUND_1, 0.5)
        self.assertGreater(chasing, stuck)

    def test_distribution_is_a_distribution(self) -> None:
        distribution = final_count_distribution(2, 4, 0.3)
        self.assertAlmostEqual(sum(distribution.values()), 1.0, places=6)
        self.assertTrue(all(count >= 2 for count in distribution))
        settled = final_count_distribution(2, 0, 0.3)
        self.assertEqual(settled, {2: 1.0})


class ProgressRatesTests(TestCase):
    def test_measured_rates_load_and_are_plausible(self) -> None:
        rates = load_progress_rates()
        self.assertGreater(rates.pooled_rate, 0.0)
        self.assertLess(rates.pooled_rate, 1.0)
        # An unknown goal (an expansion goal, say) falls back to the pool.
        self.assertEqual(rates.rate_for("no such goal"), rates.pooled_rate)
        # Egg goals accrue faster than bird-in-habitat goals: a lay-eggs
        # action yields several eggs, a play-bird action yields one bird.
        self.assertGreater(
            rates.rate_for("[egg] in [forest]"), rates.rate_for("[bird] in [forest]")
        )


class SwitchTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = setup_base_game(make_sample_catalog(), player_ids=["p1", "p2"], random_seed=5)

    def test_placement_is_the_default_with_the_heuristic_held_out(self) -> None:
        # Adopted 2026-09-22 on the registered rule; the losing side stays
        # alive at 5% like every decided switch.
        from wingspan_ai.agents.potential_points import DEFAULT_HOLDOUTS

        self.assertEqual(ROUND_GOAL_MODELS, ("heuristic", "placement"))
        self.assertEqual(PotentialPointsSearchConfig().round_goal_model, "placement")
        self.assertEqual(PotentialPointsAgent(agent_id="a").round_goal_model, "placement")
        self.assertIn(
            ("round_goal_model", "heuristic"),
            [(holdout.field, holdout.value) for holdout in DEFAULT_HOLDOUTS],
        )

    def test_the_switch_changes_the_term_and_nothing_else(self) -> None:
        heuristic = evaluate_state_potential(self.state, "p1", goal_model="heuristic")
        placement = evaluate_state_potential(self.state, "p1", goal_model="placement")
        self.assertNotAlmostEqual(
            heuristic.round_goal_potential, placement.round_goal_potential, places=3
        )
        for field in (
            "realized_score",
            "playable_bird_potential",
            "engine_power_potential",
            "bonus_card_potential",
            "endgame_conversion_potential",
        ):
            self.assertAlmostEqual(getattr(heuristic, field), getattr(placement, field))

    def test_agent_runs_and_records_the_model(self) -> None:
        agent = PotentialPointsAgent(
            agent_id="potential_points_p1",
            search_depth=2,
            final_search_turns=8,
            determinization_samples=0,
            round_goal_model="placement",
        )
        actions = legal_actions_for_current_player(self.state)
        selected = agent.select_action(self.state, actions)
        self.assertIn(selected, actions)
        summary = agent.summarize_decision(self.state, actions, selected)
        self.assertEqual(summary["round_goal_model"], "placement")

    def test_unknown_model_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PotentialPointsAgent(agent_id="a", round_goal_model="vibes")


class SetupGoalHorizonTests(TestCase):
    def test_policy_ids_round_trip_with_the_all_goals_suffix(self) -> None:
        from wingspan_ai.agents.setup import (
            PotentialPointsSetupPolicy,
            is_potential_points_setup_policy_id,
            potential_points_setup_policy,
        )

        for kwargs in (
            {},
            {"goal_horizon": "all"},
            {"goal_horizon": "all", "target_keep_count": 3},
            {"bird_scoring": "measured", "bonus_scoring": "expected_points", "goal_horizon": "all"},
        ):
            policy = PotentialPointsSetupPolicy(**kwargs)
            self.assertTrue(is_potential_points_setup_policy_id(policy.policy_id))
            rebuilt = potential_points_setup_policy(policy.policy_id)
            self.assertEqual(rebuilt.policy_id, policy.policy_id)
            self.assertEqual(rebuilt.goal_horizon, policy.goal_horizon)
        self.assertEqual(PotentialPointsSetupPolicy().goal_horizon, "first")
        with self.assertRaises(ValueError):
            PotentialPointsSetupPolicy(goal_horizon="someday")

    def test_all_goals_reads_the_later_goals(self) -> None:
        from wingspan_ai.agents.setup import InitialSelectionContext, _round_goal_setup_score

        catalog = make_sample_catalog()
        cards = tuple(catalog.birds[:3])
        goals = tuple(goal.name for goal in catalog.round_goals[:4])
        context = InitialSelectionContext(round_goal_names=goals)
        first = _round_goal_setup_score(cards, context, "first")
        every = _round_goal_setup_score(cards, context, "all")
        self.assertGreaterEqual(every, first)
        # Round 1's contribution is unweighted in both.
        one_goal = InitialSelectionContext(round_goal_names=goals[:1])
        self.assertAlmostEqual(_round_goal_setup_score(cards, one_goal, "all"), first)
