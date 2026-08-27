from tempfile import NamedTemporaryFile
from unittest import TestCase

from wingspan_ai.agents import (
    ActionGuardrailEvaluator,
    GuardrailConfig,
    GuardrailedAgent,
    PolicyGuardrail,
    load_guardrail_config,
)
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from wingspan_ai.simulation import run_single_game
from wingspan_ai.state.models import GameState
from wingspan_ai.telemetry.events import EventName


class FirstCandidateAgent:
    agent_id = "first_candidate"

    def select_action(self, _state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        return legal_actions[0]

    def choose_action(self, state: GameState) -> LegalAction:
        return legal_actions_for_current_player(state)[0]

    def summarize_decision(
        self,
        _state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        return {
            "policy": "first_candidate",
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
        }


class GuardrailAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_guardrail_config_loads_from_yaml(self) -> None:
        with NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8") as handle:
            handle.write(
                """schema_version: wingspan.guardrails.v1
name: test_guardrails
rules:
  - id: boost_gain_food
    action:
      type: gain_food
    guardrail:
      boost: 2
      reason: Prefer food here.
"""
            )
            handle.flush()

            config = load_guardrail_config(handle.name)

        self.assertEqual(config.name, "test_guardrails")
        self.assertEqual(config.rules[0].action.action_type, ActionType.GAIN_FOOD)
        self.assertEqual(config.rules[0].guardrail.boost, 2)

    def test_food_deficit_guardrail_prunes_to_needed_food(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        player = state.active_player
        player.hand = [self.catalog.birds[0]]
        player.food_tokens[FoodType.SEED] = 0

        seed_action = LegalAction(
            action_type=ActionType.GAIN_FOOD,
            player_id=player.player_id,
            food_type=FoodType.SEED,
        )
        fish_action = LegalAction(
            action_type=ActionType.GAIN_FOOD,
            player_id=player.player_id,
            food_type=FoodType.FISH,
        )
        evaluator = ActionGuardrailEvaluator(
            GuardrailConfig(
                name="food_deficit_test",
                rules=[
                    PolicyGuardrail.model_validate(
                        {
                            "id": "prefer_needed_food",
                            "when": {"hand_has_playable_bird_missing_food": True},
                            "action": {"type": "gain_food"},
                            "guardrail": {
                                "boost_if_food_matches_hand_deficit": 10,
                                "penalize_if_food_unneeded": 5,
                            },
                        }
                    )
                ],
            )
        )

        evaluation = evaluator.evaluate(state, [fish_action, seed_action])

        self.assertEqual(evaluation.candidate_actions(), [seed_action])
        self.assertEqual(evaluation.evaluation_for_action(seed_action).score_modifier, 10)
        self.assertEqual(evaluation.evaluation_for_action(fish_action).score_modifier, -5)

    def test_guardrails_fail_open_when_every_action_is_excluded(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        action = LegalAction(
            action_type=ActionType.GAIN_FOOD,
            player_id=state.active_player.player_id,
            food_type=FoodType.SEED,
        )
        evaluator = ActionGuardrailEvaluator(
            GuardrailConfig(
                name="fail_open_test",
                rules=[
                    PolicyGuardrail.model_validate(
                        {
                            "id": "exclude_food",
                            "action": {"type": "gain_food"},
                            "guardrail": {"exclude": True},
                        }
                    )
                ],
            )
        )

        evaluation = evaluator.evaluate(state, [action])

        self.assertTrue(evaluation.fail_open)
        self.assertEqual(evaluation.allowed_actions, [action])
        self.assertEqual(evaluation.excluded_action_count, 1)

    def test_guardrailed_agent_emits_selection_telemetry(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        config = GuardrailConfig(
            name="telemetry_test",
            rules=[
                PolicyGuardrail.model_validate(
                    {
                        "id": "boost_play_bird",
                        "action": {"type": "play_bird"},
                        "guardrail": {"boost": 3, "reason": "Build the board."},
                    }
                )
            ],
        )
        agent = GuardrailedAgent(FirstCandidateAgent(), config, agent_id="guardrailed_first")
        legal_actions = legal_actions_for_current_player(state)

        selected_action = agent.choose_action(state)
        summary = agent.summarize_decision(state, legal_actions, selected_action)

        self.assertEqual(summary["policy"], "guardrailed_policy")
        self.assertEqual(summary["guardrail_config_name"], "telemetry_test")
        self.assertIn("guardrail_rule_hit_counts", summary)
        self.assertIn("base_decision_summary", summary)
        self.assertLessEqual(
            summary["guardrail_candidate_action_count"],
            summary["legal_action_count"],
        )


    def test_runner_emits_guardrail_decision_summary(self) -> None:
        config = GuardrailConfig(
            name="runner_telemetry_test",
            rules=[
                PolicyGuardrail.model_validate(
                    {
                        "id": "boost_play_bird",
                        "action": {"type": "play_bird"},
                        "guardrail": {"boost": 3, "reason": "Build the board."},
                    }
                )
            ],
        )
        result = run_single_game(
            self.catalog,
            [
                GuardrailedAgent(
                    FirstCandidateAgent(),
                    config,
                    agent_id="guardrailed_first",
                ),
                FirstCandidateAgent(),
            ],
            random_seed=2,
            max_turns=2,
        )

        guardrail_events = [
            event
            for event in result.events
            if event.event_name == EventName.AGENT_DECISION_SUMMARY
            and event.agent_id == "guardrailed_first"
        ]

        self.assertTrue(guardrail_events)
        self.assertEqual(guardrail_events[0].payload["policy"], "guardrailed_policy")
        self.assertEqual(
            guardrail_events[0].payload["guardrail_config_name"],
            "runner_telemetry_test",
        )

