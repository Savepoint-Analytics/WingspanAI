"""Tests for round-robin lineups, seat counterbalancing, and summaries."""

from unittest import TestCase

from flows.round_robin import (
    MatchupCell,
    _cell_batch_label,
    _is_seat_robust,
    _lineup_scores,
    _win_credit,
    build_matchup_cells,
    format_round_robin_report,
    summarize_round_robin,
    summarize_seat_effect,
    summarize_setup_policy_effect,
)


def make_game(*seat_scores: int, valid: bool = True) -> dict:
    return {
        "outcome": {
            "scores": {
                f"player_{index + 1}": score for index, score in enumerate(seat_scores)
            }
        },
        "replay_validation": {"is_valid": valid},
    }


class MatchupCellTests(TestCase):
    def test_two_player_pairs_run_in_both_seat_orders(self) -> None:
        cells = build_matchup_cells(["a", "b", "c"], ["control", "strategic"])

        # 3 pairs x 2 setup levels x 2 rotations
        self.assertEqual(len(cells), 12)
        self.assertEqual(len({cell.cell_label for cell in cells}), 12)

    def test_counterbalancing_is_complete_for_every_player_count(self) -> None:
        for player_count in (2, 3, 4, 5):
            roster = [f"agent_{index}" for index in range(player_count)]
            cells = build_matchup_cells(roster, ["control"], player_count)

            self.assertEqual(len(cells), player_count, player_count)
            # Every agent must occupy every seat exactly once across the cells.
            for lineup_index in range(player_count):
                seats = sorted(cell.seat_index_of(lineup_index) for cell in cells)
                self.assertEqual(seats, list(range(player_count)), player_count)

    def test_seated_lineup_applies_the_rotation(self) -> None:
        cell = MatchupCell(("a", "b", "c"), "control", seat_rotation=1)

        self.assertEqual(cell.seated_lineup, ("b", "c", "a"))
        # "a" is at lineup index 0 and sits in the third seat.
        self.assertEqual(cell.seat_index_of(0), 2)

    def test_rejects_player_counts_outside_the_supported_range(self) -> None:
        for player_count in (1, 6):
            with self.assertRaises(ValueError):
                build_matchup_cells(["a", "b", "c"], ["control"], player_count)

    def test_rejects_roster_smaller_than_player_count(self) -> None:
        with self.assertRaises(ValueError):
            build_matchup_cells(["a", "b"], ["control"], 3)


class SeedMatchingTests(TestCase):
    """Cells must share one `batch_id` and differ only by `batch_label`.

    `game_id` feeds RNG seed material and is derived from `batch_id`. If a future
    change gives cells their own `batch_id`, cells stop being seed-matched and
    the round robin silently becomes an unmatched comparison.
    """

    def test_cell_labels_are_unique_and_path_safe(self) -> None:
        cells = build_matchup_cells(["greedy_immediate", "potential_points"], ["control"])
        labels = [_cell_batch_label(cell) for cell in cells]

        self.assertEqual(len(set(labels)), len(labels))
        for label in labels:
            self.assertRegex(label, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    def test_cell_label_encodes_rotation_not_batch_id(self) -> None:
        cells = build_matchup_cells(["a", "b"], ["control"])
        labels = [_cell_batch_label(cell) for cell in cells]

        self.assertTrue(all("rot" in label for label in labels))


class ScoreMappingTests(TestCase):
    def test_scores_map_back_to_lineup_order(self) -> None:
        game = make_game(10, 20, 30)

        normal = MatchupCell(("a", "b", "c"), "control", seat_rotation=0)
        rotated = MatchupCell(("a", "b", "c"), "control", seat_rotation=1)

        self.assertEqual(_lineup_scores(game, normal), [10, 20, 30])
        # Rotation 1 seats b, c, a -> a scored 30, b scored 10, c scored 20.
        self.assertEqual(_lineup_scores(game, rotated), [30, 10, 20])

    def test_win_credit_splits_across_ties(self) -> None:
        self.assertEqual(_win_credit([10, 20]), [0.0, 1.0])
        self.assertEqual(_win_credit([20, 20]), [0.5, 0.5])
        self.assertEqual(_win_credit([20, 20, 10]), [0.5, 0.5, 0.0])


class SeatRobustnessTests(TestCase):
    def test_consistent_lead_in_every_seat_is_robust(self) -> None:
        self.assertTrue(_is_seat_robust([1.0, 0.75]))
        self.assertTrue(_is_seat_robust([0.0, 0.25]))
        self.assertTrue(_is_seat_robust([0.8, 0.6, 0.7]))

    def test_contradictory_seats_are_not_robust(self) -> None:
        self.assertFalse(_is_seat_robust([1.0, 0.0]))
        self.assertFalse(_is_seat_robust([0.25, 0.75]))
        self.assertFalse(_is_seat_robust([0.9, 0.9, 0.1]))

    def test_all_even_seats_are_not_robust(self) -> None:
        self.assertFalse(_is_seat_robust([0.5, 0.5]))


class SeatEffectTests(TestCase):
    def test_pure_seat_advantage_is_reported_with_its_magnitude(self) -> None:
        cells = build_matchup_cells(["alpha", "beta"], ["control"])
        # Seat one wins by 30 points in both rotations.
        results = [[make_game(50, 20)], [make_game(50, 20)]]

        effect = summarize_seat_effect(cells, results)["2"]

        self.assertEqual(effect["seats"][0]["win_rate"], 1.0)
        self.assertEqual(effect["seats"][1]["win_rate"], 0.0)
        self.assertEqual(effect["win_rate_spread"], 1.0)
        self.assertEqual(effect["avg_score_spread"], 30.0)
        self.assertEqual(effect["best_seat"], 1)
        self.assertEqual(effect["worst_seat"], 2)

    def test_no_seat_advantage_reports_zero_spread(self) -> None:
        cells = build_matchup_cells(["alpha", "beta"], ["control"])
        # The same agent wins regardless of seat, so seats are balanced.
        results = [[make_game(50, 20)], [make_game(20, 50)]]

        effect = summarize_seat_effect(cells, results)["2"]

        self.assertEqual(effect["win_rate_spread"], 0.0)
        self.assertEqual(effect["avg_score_spread"], 0.0)
        self.assertEqual(effect["fair_share_win_rate"], 0.5)

    def test_seat_effect_is_reported_per_player_count(self) -> None:
        cells = build_matchup_cells(["a", "b", "c"], ["control"], 3)
        results = [[make_game(30, 20, 10)] for _ in cells]

        effect = summarize_seat_effect(cells, results)

        self.assertEqual(set(effect), {"3"})
        self.assertEqual(effect["3"]["player_count"], 3)
        self.assertEqual(effect["3"]["fair_share_win_rate"], 0.3333)
        self.assertEqual(len(effect["3"]["seats"]), 3)


class SummaryTests(TestCase):
    def setUp(self) -> None:
        self.cells = build_matchup_cells(["alpha", "beta"], ["control"])

    def test_seat_swap_cancels_a_pure_seat_advantage(self) -> None:
        results = [[make_game(50, 20)], [make_game(50, 20)]]

        summary = summarize_round_robin(self.cells, results)

        row = summary["matchups"][0]
        self.assertEqual(row["agent_a_win_rate"], 0.5)
        self.assertFalse(row["seat_robust"])

    def test_genuine_agent_advantage_survives_seat_swap(self) -> None:
        # alpha wins from seat one and from seat two.
        results = [[make_game(50, 20)], [make_game(20, 50)]]

        summary = summarize_round_robin(self.cells, results)

        row = summary["matchups"][0]
        self.assertEqual(row["agent_a_win_rate"], 1.0)
        self.assertTrue(row["seat_robust"])
        self.assertEqual(row["avg_margin_for_agent_a"], 30.0)
        self.assertEqual(summary["standings"][0]["agent"], "alpha")

    def test_ties_split_win_credit(self) -> None:
        results = [[make_game(40, 40)], [make_game(40, 40)]]

        summary = summarize_round_robin(self.cells, results)

        self.assertEqual(summary["matchups"][0]["agent_a_win_rate"], 0.5)
        self.assertEqual(summary["standings"][0]["win_rate"], 0.5)

    def test_invalid_replays_are_counted_not_silently_dropped(self) -> None:
        results = [[make_game(50, 20, valid=False)], [make_game(20, 50)]]

        summary = summarize_round_robin(self.cells, results)

        self.assertEqual(summary["matchups"][0]["invalid_replays"], 1)

    def test_three_player_summary_reports_pairwise_matchups(self) -> None:
        cells = build_matchup_cells(["a", "b", "c"], ["control"], 3)
        results = [[make_game(30, 20, 10)] for _ in cells]

        summary = summarize_round_robin(cells, results)

        self.assertEqual(summary["player_counts"], [3])
        # Three pairwise matchups from one three-agent lineup.
        self.assertEqual(len(summary["matchups"]), 3)
        self.assertEqual(summary["total_games"], 3)

    def test_setup_policy_effect_contrasts_control_and_strategic(self) -> None:
        cells = build_matchup_cells(["alpha", "beta"], ["control", "strategic"])
        by_label = {(cell.setup_policy_kind, cell.seat_rotation): index
                    for index, cell in enumerate(cells)}
        results = [None] * len(cells)
        # alpha loses both control rotations and wins both strategic rotations.
        results[by_label[("control", 0)]] = [make_game(20, 50)]
        results[by_label[("control", 1)]] = [make_game(50, 20)]
        results[by_label[("strategic", 0)]] = [make_game(50, 20)]
        results[by_label[("strategic", 1)]] = [make_game(20, 50)]

        summary = summarize_round_robin(cells, results)
        effects = {row["agent"]: row for row in summarize_setup_policy_effect(summary)}

        self.assertEqual(effects["alpha"]["control_win_rate"], 0.0)
        self.assertEqual(effects["alpha"]["strategic_win_rate"], 1.0)
        self.assertEqual(effects["alpha"]["strategic_minus_control"], 1.0)
        self.assertEqual(effects["beta"]["strategic_minus_control"], -1.0)

    def test_report_renders_all_sections(self) -> None:
        results = [[make_game(50, 20)], [make_game(20, 50)]]
        summary = summarize_round_robin(self.cells, results)
        summary.update(
            {
                "batch_id": "test",
                "batch_label": "test",
                "seeds": [1],
                "roster": ["alpha", "beta"],
                "player_count": 2,
                "setup_policy_kinds": ["control"],
                "seat_counterbalanced": True,
                "setup_policy_effect": summarize_setup_policy_effect(summary),
            }
        )

        report = format_round_robin_report(summary)

        self.assertIn("## Standings", report)
        self.assertIn("## Matchups", report)
        self.assertIn("## Seat effect", report)
        self.assertIn("## Setup-policy effect", report)
        self.assertIn("win-rate spread", report)
        self.assertIn("`alpha`", report)


class GuardrailedRosterTests(TestCase):
    """Guardrailed variants must be selectable as first-class competitors.

    Guardrails were previously a seat-level batch setting, so an agent could not
    face its own guardrailed twin in a round robin. The `guardrailed:` roster
    prefix makes that possible.
    """

    def test_prefixed_kind_validates(self) -> None:
        from flows.simulation_batch import _validate_player_two_agent_kind

        self.assertEqual(
            _validate_player_two_agent_kind("guardrailed:potential_points"),
            "guardrailed:potential_points",
        )

    def test_unknown_base_kind_is_rejected_even_when_prefixed(self) -> None:
        from flows.simulation_batch import _validate_player_two_agent_kind

        with self.assertRaises(ValueError):
            _validate_player_two_agent_kind("guardrailed:not_an_agent")

    def test_prefixed_kind_produces_a_wrapped_agent(self) -> None:
        from flows.simulation_batch import _make_agent

        plain = _make_agent("potential_points", seat="p1")
        guarded = _make_agent("guardrailed:potential_points", seat="p1")

        self.assertFalse(hasattr(plain, "base_agent"))
        self.assertTrue(hasattr(guarded, "base_agent"))
        self.assertNotEqual(plain.agent_id, guarded.agent_id)

    def test_setup_policy_is_applied_to_the_base_agent_not_the_wrapper(self) -> None:
        """GuardrailedAgent delegates opening choice, so the wrapper's own
        setup_policy would never be consulted."""

        from flows.simulation_batch import _make_agent

        guarded = _make_agent(
            "guardrailed:potential_points", seat="p1", setup_policy_kind="strategic"
        )

        self.assertEqual(
            guarded.base_agent.setup_policy.policy_id, "potential_points_setup_v1"
        )

    def test_guardrailed_cell_labels_are_path_safe(self) -> None:
        """The `guardrailed:` colon is not a legal path segment character."""

        cells = build_matchup_cells(
            ["potential_points", "guardrailed:potential_points"], ["control"]
        )

        for cell in cells:
            label = _cell_batch_label(cell)
            self.assertNotIn(":", label)
            self.assertRegex(label, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    def test_an_agent_and_its_guardrailed_twin_are_distinct_competitors(self) -> None:
        cells = build_matchup_cells(
            ["potential_points", "guardrailed:potential_points"], ["control"]
        )

        self.assertEqual(len(cells), 2)  # one pair, two rotations
        self.assertEqual(len({cell.cell_label for cell in cells}), 2)
