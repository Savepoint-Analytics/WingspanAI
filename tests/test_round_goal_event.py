"""The per-round `round_goal_scored` event.

Promised by the taxonomy since 2026-05 and emitted from 2026-09-22: until
then a goal outcome could only be recovered by replaying the game, which is
what the placement model needs at scale.
"""

from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.base_game import ROUND_GOAL_GREEN_SCORES, TOTAL_ROUNDS
from wingspan_ai.simulation import run_single_game
from wingspan_ai.telemetry.events import EventName


class RoundGoalScoredEventTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = make_sample_catalog()
        cls.result = run_single_game(
            catalog,
            [
                RandomLegalAgent(agent_id="random_legal_p1", random_seed=1),
                GreedyBaselineAgent(agent_id="greedy_immediate_p2"),
            ],
            random_seed=4,
            game_id="round_goal_event",
        )
        cls.events = [
            event for event in cls.result.events if event.event_name == EventName.ROUND_GOAL_SCORED
        ]

    def test_one_event_per_round_including_the_last(self) -> None:
        self.assertEqual(len(self.events), TOTAL_ROUNDS)
        self.assertEqual(
            [event.payload["goal_round"] for event in self.events],
            list(range(1, TOTAL_ROUNDS + 1)),
        )

    def test_points_awarded_sum_to_each_players_goal_score(self) -> None:
        totals = {player.player_id: 0 for player in self.result.state.players}
        for event in self.events:
            for player_id, points in event.payload["points_awarded"].items():
                totals[player_id] += points
        for player in self.result.state.players:
            self.assertEqual(totals[player.player_id], player.round_goal_points)

    def test_payload_describes_the_placement(self) -> None:
        for event in self.events:
            payload = event.payload
            round_number = payload["goal_round"]
            self.assertEqual(
                payload["placement_scores"], list(ROUND_GOAL_GREEN_SCORES[round_number])
            )
            counts = payload["counts"]
            ranked = sorted(counts.values(), reverse=True)
            self.assertEqual(payload["top_count"], ranked[0])
            self.assertEqual(payload["margin"], ranked[0] - ranked[1])
            self.assertEqual(payload["nobody_qualified"], ranked[0] == 0)
            winners = payload["winner_player_ids"]
            if ranked[0] > 0:
                self.assertEqual(
                    winners,
                    sorted(p for p, c in counts.items() if c == ranked[0]),
                )
                self.assertEqual(payload["contested"], len(winners) > 1)
                # A tie for first splits the top two slots, rounded down.
                if len(winners) > 1:
                    self.assertEqual(payload["margin"], 0)
                    scale = payload["placement_scores"]
                    expected = sum(scale[: len(winners)]) // len(winners)
                    for player_id in winners:
                        self.assertEqual(payload["points_awarded"][player_id], expected)
            else:
                self.assertEqual(winners, [])

    def test_counts_are_the_scoring_time_counts(self) -> None:
        # Boards do not change between goal scoring and the end of the
        # transition (the tray refresh touches decks only), so the final
        # round's counts must match the finished board.
        from wingspan_ai.rules.base_game import _count_round_goal_items

        last = self.events[-1].payload
        goal = self.result.state.round_goals[TOTAL_ROUNDS - 1]
        for player in self.result.state.players:
            self.assertEqual(
                last["counts"][player.player_id],
                _count_round_goal_items(goal.name.lower(), player),
            )
