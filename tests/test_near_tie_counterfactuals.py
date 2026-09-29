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
