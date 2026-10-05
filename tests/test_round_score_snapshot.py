"""The round-boundary score snapshot.

The taxonomy asked for "cumulative score by round" and "per-round delta" from
2026-05 and neither was answerable: only the final score was emitted, so
`kpi_taxonomy_findings.md` carried both as unsupported. Differencing consecutive
snapshots gives both. It is also the one blocker for modelling score trajectory
(`docs/agents/gaussian_markov_value_agent.md`), which is why the payload is a
usable state vector rather than only a score.
"""

from __future__ import annotations

from unittest import TestCase

from wingspan_ai.agents.greedy import GreedyBaselineAgent
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.base_game import score_player
from wingspan_ai.simulation.runner import run_single_game
from wingspan_ai.telemetry.events import EventName
from wingspan_ai.telemetry.postgres import ANALYSIS_EVENT_NAMES

CATALOG = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)


def play(seed: int, players: int = 2):
    agents = [GreedyBaselineAgent(agent_id=f"greedy_p{i + 1}") for i in range(players)]
    return run_single_game(CATALOG, agents, random_seed=seed, game_id=f"snap_{seed}")


def snapshots(result):
    return [e for e in result.events if e.event_name == EventName.ROUND_SCORE_SNAPSHOT]


class EmissionTests(TestCase):
    def test_one_snapshot_per_player_per_round(self) -> None:
        result = play(3)
        rows = snapshots(result)
        self.assertEqual(len(rows), 4 * len(result.state.players))
        self.assertEqual(sorted({r.round_number for r in rows}), [1, 2, 3, 4])

    def test_round_four_is_included(self) -> None:
        """The game-over branch never reaches a new round number.

        The round-goal event had exactly this bug before 2026-09-22, so the
        snapshot is keyed off the same transition and needs the same guard.
        """

        rounds = {r.round_number for r in snapshots(play(3))}
        self.assertIn(4, rounds)

    def test_three_players_each_get_a_row(self) -> None:
        result = play(5, players=3)
        rows = snapshots(result)
        self.assertEqual(len(rows), 12)
        for round_number in (1, 2, 3, 4):
            seats = {r.player_id for r in rows if r.round_number == round_number}
            self.assertEqual(len(seats), 3)

    def test_it_is_loaded_into_the_analysis_schema(self) -> None:
        """A snapshot nobody can query is worth nothing."""

        self.assertIn("round_score_snapshot", ANALYSIS_EVENT_NAMES)


class ReconciliationTests(TestCase):
    def test_the_last_snapshot_equals_the_final_score(self) -> None:
        result = play(3)
        rows = snapshots(result)
        for player in result.state.players:
            last = max(
                (r for r in rows if r.player_id == player.player_id),
                key=lambda r: r.round_number,
            )
            self.assertEqual(
                last.payload["total_score"],
                score_player(result.state, player.player_id).total,
                f"{player.player_id}: round-4 snapshot disagrees with the final score",
            )

    def test_cumulative_score_never_decreases(self) -> None:
        """Wingspan has no scoring category that can be lost."""

        rows = snapshots(play(3))
        for player_id in {r.player_id for r in rows}:
            series = [
                r.payload["total_score"]
                for r in sorted(
                    (r for r in rows if r.player_id == player_id),
                    key=lambda r: r.round_number,
                )
            ]
            self.assertEqual(series, sorted(series), f"{player_id} score went backwards: {series}")

    def test_round_goal_points_include_the_round_just_ended(self) -> None:
        """The snapshot is emitted after the goal is scored, not before."""

        rows = snapshots(play(3))
        first = [r for r in rows if r.round_number == 1]
        self.assertTrue(
            any(r.payload["round_goal_points"] > 0 for r in first),
            "no player had goal points after round 1; the snapshot ran before scoring",
        )

    def test_categories_sum_to_the_total(self) -> None:
        categories = (
            "bird_points",
            "bonus_points",
            "round_goal_points",
            "egg_points",
            "cached_food_points",
            "tucked_card_points",
        )
        for row in snapshots(play(3)):
            self.assertEqual(
                sum(row.payload[c] for c in categories),
                row.payload["total_score"],
                f"{row.player_id} r{row.round_number}: categories do not sum to the total",
            )


class StateVectorTests(TestCase):
    def test_engine_fields_are_present_and_coherent(self) -> None:
        for row in snapshots(play(3)):
            payload = row.payload
            self.assertEqual(
                payload["birds_in_play"], sum(payload["birds_by_habitat"].values())
            )
            self.assertGreaterEqual(payload["egg_capacity_left"], 0)
            self.assertGreaterEqual(payload["food_tokens_held"], 0)
            self.assertEqual(payload["food_tokens_held"], sum(payload["food_by_type"].values()))

    def test_eggs_on_board_matches_the_egg_score(self) -> None:
        """One point an egg, so the two must agree -- a cheap scoring check."""

        for row in snapshots(play(3)):
            self.assertEqual(row.payload["eggs_on_board"], row.payload["egg_points"])


class DeterminismTests(TestCase):
    def test_snapshots_are_reproducible_from_the_seed(self) -> None:
        a = [r.payload for r in snapshots(play(7))]
        b = [r.payload for r in snapshots(play(7))]
        self.assertEqual(a, b)
