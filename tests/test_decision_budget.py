"""The anytime decision budget on potential_points: K, then depth, then one-ply."""

from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from wingspan_ai.simulation.runner import run_single_game


class DecisionBudgetTests(TestCase):
    def setUp(self) -> None:
        self.catalog = make_sample_catalog()
        self.state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=5)
        self.legal = legal_actions_for_current_player(self.state)
        self.kwargs = dict(search_depth=2, final_search_turns=8, determinization_samples=2)

    def test_a_generous_budget_reproduces_the_unbudgeted_decision(self) -> None:
        unbudgeted = PotentialPointsAgent(**self.kwargs)
        budgeted = PotentialPointsAgent(max_decision_time_ms=60_000, **self.kwargs)
        self.assertIsNone(unbudgeted.last_budget_report)
        self.assertEqual(
            budgeted.select_action(self.state, self.legal),
            unbudgeted.select_action(self.state, self.legal),
        )
        report = budgeted.last_budget_report
        self.assertEqual((report["depth_used"], report["samples_used"]), (2, 2))
        self.assertFalse(report["cut_short"])
        self.assertEqual(report["full_depth"], 2)

    def test_a_tiny_budget_degrades_to_the_one_ply_evaluator(self) -> None:
        agent = PotentialPointsAgent(max_decision_time_ms=0.001, **self.kwargs)
        action = agent.select_action(self.state, self.legal)
        self.assertIn(action, self.legal)
        report = agent.last_budget_report
        self.assertEqual(report["depth_used"], 0)
        self.assertTrue(report["cut_short"])
        # One-ply on the true state is exactly what determinization_samples=0 does.
        one_ply = PotentialPointsAgent(determinization_samples=0, final_search_turns=0)
        self.assertEqual(action, one_ply.select_action(self.state, self.legal))

    def test_budget_is_validated_and_recorded(self) -> None:
        with self.assertRaises(ValueError):
            PotentialPointsAgent(max_decision_time_ms=0)
        agent = PotentialPointsAgent(agent_id="pp", max_decision_time_ms=500, **self.kwargs)
        result = run_single_game(
            self.catalog,
            [agent, GreedyBaselineAgent(agent_id="g")],
            random_seed=3,
            max_turns=4,
        )
        decision = next(
            e
            for e in result.events
            if e.event_name == "agent_decision_summary" and e.agent_id == "pp"
        )
        self.assertEqual(decision.payload["max_decision_time_ms"], 500)
        budget = decision.payload["budget"]
        self.assertEqual(budget["budget_ms"], 500)
        self.assertEqual(budget["ladder"], "v2")
        self.assertIn("depth_used", budget)
        self.assertLessEqual(budget["depth_used"], 2)

    def test_deadline_between_root_actions_abandons_a_level(self) -> None:
        agent = PotentialPointsAgent(**self.kwargs)
        from time import perf_counter

        self.assertIsNone(
            agent._score_actions(self.state, self.legal, depth=2, deadline=perf_counter() - 1)
        )
        scores = agent._score_actions(self.state, self.legal, depth=2, deadline=perf_counter() + 60)
        self.assertEqual(len(scores), len(self.legal))

    def test_depth_is_bought_before_samples(self) -> None:
        """With time for the deepest level once but not four times, v2 keeps the depth."""

        probe = PotentialPointsAgent(max_decision_time_ms=60_000, **self.kwargs)
        probe.select_action(self.state, self.legal)
        full_ms = probe.last_budget_report["elapsed_ms"]
        # Roughly enough for the ladder plus one or two deep samples, not all of them.
        agent = PotentialPointsAgent(max_decision_time_ms=full_ms * 0.65, **self.kwargs)
        agent.select_action(self.state, self.legal)
        report = agent.last_budget_report
        self.assertEqual(report["depth_used"], 2)
        self.assertLess(report["samples_used"], 2)
        self.assertTrue(report["cut_short"])
