from tempfile import TemporaryDirectory
from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content import make_sample_catalog
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
