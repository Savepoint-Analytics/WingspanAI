"""The near-tie selection logic, which decides what counts as a natural experiment.

Getting this wrong quietly changes what the instrument measures, so the cases
below pin the three things that are easy to get wrong: the chosen entry is
flagged rather than assumed to be first, the runner-up is the best *other*
entry, and epsilon is a two-sided bound on the margin.
"""

from __future__ import annotations

from unittest import TestCase

from analysis.near_tie_counterfactuals import decision_key, near_tie, paired, rankings_by_decision


def entry(label: str, value: float, *, chosen: bool = False, kind: str = "play_bird") -> dict:
    return {"action_label": label, "action_type": kind, "value": value, "chosen": chosen}


class NearTieTests(TestCase):
    def test_returns_chosen_and_runner_up_inside_epsilon(self) -> None:
        ranking = {"top": [entry("a", 10.0, chosen=True), entry("b", 9.9)]}
        pair = near_tie(ranking, 0.2)
        assert pair is not None
        chosen, runner = pair
        self.assertEqual(chosen["action_label"], "a")
        self.assertEqual(runner["action_label"], "b")

    def test_rejects_a_margin_outside_epsilon(self) -> None:
        ranking = {"top": [entry("a", 10.0, chosen=True), entry("b", 9.0)]}
        self.assertIsNone(near_tie(ranking, 0.2))

    def test_the_chosen_entry_is_not_assumed_to_be_the_top_valued_one(self) -> None:
        """The agent breaks ties on a secondary key and an action priority.

        So the highest-valued candidate is not always the one taken, and reading
        ``top[0]`` as "chosen" would silently flip the sign of realized_delta on
        exactly the decisions this instrument exists to study.
        """

        ranking = {"top": [entry("a", 10.0), entry("b", 10.0, chosen=True)]}
        pair = near_tie(ranking, 0.2)
        assert pair is not None
        chosen, runner = pair
        self.assertEqual(chosen["action_label"], "b")
        self.assertEqual(runner["action_label"], "a")

    def test_margin_is_two_sided(self) -> None:
        """A chosen action valued *below* its runner-up is still a near tie."""

        ranking = {"top": [entry("a", 10.0), entry("b", 9.85, chosen=True)]}
        self.assertIsNotNone(near_tie(ranking, 0.2))
        ranking = {"top": [entry("a", 10.0), entry("b", 9.0, chosen=True)]}
        self.assertIsNone(near_tie(ranking, 0.2))

    def test_runner_up_is_the_best_other_entry_not_the_next_listed(self) -> None:
        ranking = {
            "top": [entry("a", 10.0, chosen=True), entry("b", 5.0), entry("c", 9.95)]
        }
        pair = near_tie(ranking, 0.2)
        assert pair is not None
        self.assertEqual(pair[1]["action_label"], "c")

    def test_no_chosen_flag_is_skipped_rather_than_guessed(self) -> None:
        ranking = {"top": [entry("a", 10.0), entry("b", 9.9)]}
        self.assertIsNone(near_tie(ranking, 0.2))

    def test_a_lone_candidate_is_not_a_tie(self) -> None:
        self.assertIsNone(near_tie({"top": [entry("a", 1.0, chosen=True)]}, 0.2))


class RankingIndexTests(TestCase):
    def test_indexes_only_the_requested_policy_and_ranked_decisions(self) -> None:
        events = [
            {
                "event_name": "agent_decision_summary",
                "player_id": "player_1",
                "round_number": 1,
                "round_action_number": 1,
                "global_turn_number": 1,
                "payload": {
                    "policy": "potential_points",
                    "search_ranking": {"top": [entry("a", 1.0, chosen=True), entry("b", 0.9)]},
                },
            },
            {  # another policy
                "event_name": "agent_decision_summary",
                "player_id": "player_2",
                "round_number": 1,
                "round_action_number": 2,
                "global_turn_number": 2,
                "payload": {"policy": "strategy_archetype", "search_ranking": {"top": []}},
            },
            {  # right policy, only one candidate ranked
                "event_name": "agent_decision_summary",
                "player_id": "player_1",
                "round_number": 1,
                "round_action_number": 3,
                "global_turn_number": 3,
                "payload": {
                    "policy": "potential_points",
                    "search_ranking": {"top": [entry("a", 1.0, chosen=True)]},
                },
            },
        ]
        index = rankings_by_decision(events, "potential_points")
        self.assertEqual(list(index), [("player_1", 1, 1, 1)])

    def test_decision_key_matches_across_event_families(self) -> None:
        """``action_resolved`` and ``agent_decision_summary`` must align."""

        summary = {
            "event_name": "agent_decision_summary",
            "player_id": "player_2",
            "round_number": 3,
            "round_action_number": 4,
            "global_turn_number": 21,
        }
        resolved = dict(summary, event_name="action_resolved")
        self.assertEqual(decision_key(summary), decision_key(resolved))


class PairedTests(TestCase):
    def test_zero_spread_is_not_significant(self) -> None:
        """Identical deltas give no evidence, however many there are."""

        delta, p = paired([2.0] * 50)
        self.assertEqual(delta, 2.0)
        self.assertEqual(p, 1.0)

    def test_a_clear_offset_is_detected(self) -> None:
        delta, p = paired([1.0, 1.1, 0.9, 1.2, 0.8] * 8)
        self.assertAlmostEqual(delta, 1.0, places=6)
        self.assertLess(p, 0.001)

    def test_symmetric_noise_is_null(self) -> None:
        delta, p = paired([1.0, -1.0] * 20)
        self.assertAlmostEqual(delta, 0.0, places=9)
        self.assertEqual(p, 1.0)


class RerollPenaltyTests(TestCase):
    """The switch registered 2026-09-30 from the near-tie reroll nomination.

    It must be inert by default, must only bite when a non-reroll alternative
    exists, and must reach the agent through the batch flow -- an evaluator
    switch that silently fails to thread is the worst outcome, because the arm
    then reads as a null.
    """

    @staticmethod
    def actions(*reroll_flags: bool) -> list:
        class Action:
            def __init__(self, reroll: bool) -> None:
                self.reroll_birdfeeder = reroll

        return [Action(flag) for flag in reroll_flags]

    def agent(self, **kwargs):
        from wingspan_ai.agents.potential_points import PotentialPointsAgent

        return PotentialPointsAgent(agent_id="test", **kwargs)

    def test_default_is_inert(self) -> None:
        self.assertEqual(
            self.agent()._root_reroll_penalties(self.actions(True, False)), [0.0, 0.0]
        )

    def test_penalises_only_the_reroll_actions(self) -> None:
        penalties = self.agent(reroll_penalty=2.0)._root_reroll_penalties(
            self.actions(True, False, True)
        )
        self.assertEqual(penalties, [-2.0, 0.0, -2.0])

    def test_is_inert_when_every_action_rerolls(self) -> None:
        """With no alternative the penalty shifts all candidates equally."""

        penalties = self.agent(reroll_penalty=2.0)._root_reroll_penalties(
            self.actions(True, True)
        )
        self.assertEqual(penalties, [0.0, 0.0])

    def test_rejects_a_negative_penalty(self) -> None:
        with self.assertRaises(ValueError):
            self.agent(reroll_penalty=-1.0)

    def test_threads_from_the_search_config_through_the_batch_flow(self) -> None:
        from flows.simulation_batch import _make_agent
        from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

        config = PotentialPointsSearchConfig(reroll_penalty=2.0)
        effective, _applied = config.resolve_effective(
            random_seed=1, lineup=["potential_points", "greedy_immediate"], lineup_position=0
        )
        self.assertEqual(effective["reroll_penalty"], 2.0)
        agent = _make_agent(
            "potential_points", seat="p1", random_seed=1, potential_points_search=config
        )
        self.assertEqual(agent.reroll_penalty, 2.0)

    def test_appears_in_the_manifest_payload(self) -> None:
        """Otherwise the arm's provenance would not record what was tested."""

        from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

        payload = PotentialPointsSearchConfig(reroll_penalty=2.0).as_manifest_payload()
        self.assertEqual(payload["reroll_penalty"], 2.0)
