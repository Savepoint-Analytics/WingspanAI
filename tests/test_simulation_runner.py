from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import legal_actions_for_current_player, score_player
from wingspan_ai.simulation import (
    run_single_game,
    validate_simulation_replay,
    write_simulation_artifacts,
)
from wingspan_ai.telemetry.events import EventName


class SimulationRunnerTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_single_game_runner_completes_random_vs_greedy_game(self) -> None:
        result = run_single_game(
            self.catalog,
            [
                RandomLegalAgent(agent_id="random_legal_p1", random_seed=1),
                GreedyBaselineAgent(agent_id="greedy_p2"),
            ],
            random_seed=1,
        )

        self.assertEqual(result.outcome.terminal_reason, "game_over")
        self.assertEqual(result.outcome.turns_played, 52)
        self.assertEqual(len(result.outcome.scores), 2)
        self.assertTrue(result.public_state_snapshots)
        self.assertEqual(result.events[0].event_name, EventName.SIMULATION_RUN_STARTED)
        self.assertEqual(result.events[-1].event_name, EventName.GAME_ENDED)

    def test_greedy_agent_prefers_immediate_score_gain(self) -> None:
        state = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=3), RandomLegalAgent(random_seed=4)],
            random_seed=3,
            max_turns=1,
        ).state
        player = state.active_player
        playable_card = next(card for card in self.catalog.birds if card.habitats)
        player.hand = [playable_card]
        for food_type in player.food_tokens:
            player.food_tokens[food_type] = 3

        legal_actions = legal_actions_for_current_player(state)
        action = GreedyBaselineAgent().select_action(state, legal_actions)

        self.assertEqual(action.action_type, ActionType.PLAY_BIRD)
        next_score = score_player(state, player.player_id).total
        self.assertGreaterEqual(playable_card.victory_points, next_score)

    def test_runner_rejects_illegal_agent_action(self) -> None:
        class BadAgent:
            agent_id = "bad_agent"

            def choose_action(self, _state):
                return LegalAction(action_type=ActionType.LAY_EGGS, player_id="wrong_player")

        with self.assertRaises(ValueError):
            run_single_game(self.catalog, [BadAgent()], random_seed=1, max_turns=1)

    def test_simulation_artifacts_write_public_snapshots(self) -> None:
        result = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=8), GreedyBaselineAgent()],
            random_seed=8,
            max_turns=2,
        )

        with TemporaryDirectory() as tmp_dir:
            output_dir = write_simulation_artifacts(result, tmp_dir)

            self.assertTrue((output_dir / "outcome.json").exists())
            self.assertTrue((output_dir / "events.jsonl").exists())
            self.assertTrue((output_dir / "public_state_snapshots.json").exists())
            self.assertTrue((output_dir / "replay_debug.json").exists())

    def test_runner_emits_setup_selection_decision_summary_and_replay_hashes(self) -> None:
        result = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=9), GreedyBaselineAgent()],
            random_seed=9,
            max_turns=1,
        )

        event_names = [event.event_name for event in result.events]

        self.assertIn(EventName.SETUP_SELECTION_APPLIED, event_names)
        self.assertIn(EventName.AGENT_DECISION_SUMMARY, event_names)
        decision_event = next(
            event
            for event in result.events
            if event.event_name == EventName.AGENT_DECISION_SUMMARY
        )
        self.assertIn("action_selection_elapsed_ms", decision_event.payload)
        self.assertIn("decision_summary_elapsed_ms", decision_event.payload)
        self.assertIn("decision_total_elapsed_ms", decision_event.payload)
        self.assertGreaterEqual(decision_event.payload["decision_total_elapsed_ms"], 0)
        resolved_event = next(
            event for event in result.events if event.event_name == EventName.ACTION_RESOLVED
        )
        self.assertIn("state_hash_before", resolved_event.payload)
        self.assertIn("state_hash_after", resolved_event.payload)
        setup_event = next(
            event
            for event in result.events
            if event.event_name == EventName.SETUP_SELECTION_APPLIED
        )
        self.assertTrue(setup_event.private_state_included)

    def test_runner_round_turn_counts_match_base_game_action_cubes(self) -> None:
        result = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=12), GreedyBaselineAgent()],
            random_seed=12,
        )

        selected_events = [
            event for event in result.events if event.event_name == EventName.ACTION_SELECTED
        ]
        resolved_events = [
            event for event in result.events if event.event_name == EventName.ACTION_RESOLVED
        ]
        round_counts = {
            round_number: sum(1 for event in selected_events if event.round_number == round_number)
            for round_number in range(1, 5)
        }
        max_turns_by_round = {
            round_number: max(
                event.turn_number or 0
                for event in selected_events
                if event.round_number == round_number
            )
            for round_number in range(1, 5)
        }
        max_round_actions = {
            round_number: max(
                event.round_action_number or 0
                for event in selected_events
                if event.round_number == round_number
            )
            for round_number in range(1, 5)
        }

        self.assertEqual(round_counts, {1: 16, 2: 14, 3: 12, 4: 10})
        self.assertEqual(max_turns_by_round, {1: 8, 2: 7, 3: 6, 4: 5})
        self.assertEqual(max_round_actions, round_counts)
        self.assertEqual(len(selected_events), 52)
        for selected_event, resolved_event in zip(selected_events, resolved_events, strict=True):
            self.assertEqual(resolved_event.turn_number, selected_event.turn_number)
            self.assertEqual(resolved_event.round_action_number, selected_event.round_action_number)
            self.assertEqual(resolved_event.global_turn_number, selected_event.global_turn_number)
            self.assertIn("action_label", selected_event.payload)
            self.assertIn("next_turn_number", resolved_event.payload)
            self.assertIn("next_round_action_number", resolved_event.payload)
            self.assertIn("next_global_turn_number", resolved_event.payload)

    def test_replay_validator_reconstructs_smoke_game_hashes(self) -> None:
        result = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=10), GreedyBaselineAgent()],
            random_seed=10,
            max_turns=4,
        )

        replay_result = validate_simulation_replay(self.catalog, result.events)

        self.assertTrue(replay_result.is_valid, replay_result.errors)
        self.assertEqual(replay_result.checked_transitions, result.outcome.turns_played)

    def test_action_resolved_includes_deck_draw_records(self) -> None:
        result = run_single_game(
            self.catalog,
            [RandomLegalAgent(random_seed=11), GreedyBaselineAgent()],
            random_seed=11,
            max_turns=2,
        )

        resolved_events = [
            event for event in result.events if event.event_name == EventName.ACTION_RESOLVED
        ]

        self.assertTrue(any("rng_draws" in event.payload for event in resolved_events))


class ScoreIntegrityTests(TestCase):
    """Guard that reported totals are actually the sum of earned categories.

    `GameOutcome.scores` and the per-category breakdown are produced by separate
    calls and persisted into separate columns. Nothing previously asserted they
    agree, so a scoring bug could inflate a total without any category showing
    where the points came from — or vice versa.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def _finished_games(self, seeds=(1, 2, 3)):
        for seed in seeds:
            yield run_single_game(
                self.catalog,
                [
                    RandomLegalAgent(agent_id="p1", random_seed=seed),
                    GreedyBaselineAgent(agent_id="p2"),
                ],
                random_seed=seed,
                game_id=f"score_integrity_{seed}",
            )

    def test_reported_total_equals_sum_of_categories(self) -> None:
        for result in self._finished_games():
            for player in result.state.players:
                breakdown = score_player(result.state, player.player_id)
                category_sum = (
                    breakdown.bird_points
                    + breakdown.bonus_points
                    + breakdown.round_goal_points
                    + breakdown.egg_points
                    + breakdown.cached_food_points
                    + breakdown.tucked_card_points
                )
                self.assertEqual(
                    category_sum,
                    breakdown.total,
                    f"{result.outcome.game_id}/{player.player_id}",
                )
                self.assertEqual(
                    breakdown.total,
                    result.outcome.scores[player.player_id],
                    f"outcome disagrees with breakdown for {player.player_id}",
                )

    def test_game_ended_telemetry_matches_the_outcome(self) -> None:
        """The persisted breakdown and total come from different payload fields."""

        for result in self._finished_games(seeds=(4,)):
            ended = next(e for e in result.events if e.event_name == "game_ended")
            scores = ended.payload["outcome"]["scores"]
            for player_id, breakdown in ended.payload["score_breakdowns"].items():
                category_sum = sum(
                    value for key, value in breakdown.items() if key != "player_id"
                )
                self.assertEqual(category_sum, scores[player_id], player_id)

    def _categories_ever_scored(self, catalog, seeds) -> set[str]:
        categories = {
            "bird_points",
            "bonus_points",
            "round_goal_points",
            "egg_points",
            "cached_food_points",
            "tucked_card_points",
        }
        seen: set[str] = set()
        for seed in seeds:
            result = run_single_game(
                catalog,
                [
                    RandomLegalAgent(agent_id="p1", random_seed=seed),
                    GreedyBaselineAgent(agent_id="p2"),
                ],
                random_seed=seed,
                game_id=f"reachability_{seed}",
            )
            for player in result.state.players:
                breakdown = score_player(result.state, player.player_id)
                seen |= {c for c in categories if getattr(breakdown, c) > 0}
        return seen

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_every_scoring_category_is_reachable_on_real_content(self) -> None:
        """A category never scored is more likely unimplemented than unused.

        Silently removes a whole scoring path from every strategy conclusion.
        """

        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        seen = self._categories_ever_scored(catalog, range(1, 9))

        unreachable = sorted(
            {
                "bird_points",
                "bonus_points",
                "round_goal_points",
                "egg_points",
                "cached_food_points",
                "tucked_card_points",
            }
            - seen
        )
        self.assertEqual(unreachable, [], f"never scored across 8 workbook games: {unreachable}")

    def test_sample_catalog_cannot_exercise_power_based_scoring(self) -> None:
        """Documents a real limitation of the synthetic catalog.

        `make_sample_catalog` builds birds with `PowerColor.NONE`, so nothing
        caches food or tucks cards, and its placeholder bonus cards never score.
        Any smoke run or test using it is blind to three of the six scoring
        categories. Asserted so the limitation cannot be forgotten, and so this
        test starts failing if the sample catalog gains powered birds.
        """

        seen = self._categories_ever_scored(self.catalog, range(1, 13))

        self.assertIn("bird_points", seen)
        self.assertIn("egg_points", seen)
        self.assertNotIn("cached_food_points", seen)
        self.assertNotIn("tucked_card_points", seen)
        self.assertNotIn("bonus_points", seen)
