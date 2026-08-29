from unittest import TestCase

from wingspan_ai.agents import NetValueOpponentResponseAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import (
    BirdCard,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
)
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game


class NetValueOpponentResponseAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_agent_selects_legal_action_and_reports_net_value(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=41)
        agent = NetValueOpponentResponseAgent(
            max_candidate_actions=4,
            max_opponent_response_actions=3,
        )
        legal_actions = legal_actions_for_current_player(state)

        action = agent.select_action(state, legal_actions)
        summary = agent.summarize_decision(state, legal_actions, action)

        self.assertIn(action, legal_actions)
        self.assertEqual(summary["policy"], "net_value_opponent_response")
        self.assertEqual(summary["opponent_model"], "full_state_oracle_v0")
        self.assertLessEqual(summary["evaluated_action_count"], 4)
        self.assertEqual(summary["max_opponent_response_actions"], 3)
        self.assertIn("net_margin_delta", summary["selected_breakdown"])
        self.assertIn("selected_opponent_response", summary)

    def test_tray_card_draw_carries_shared_denial_value(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=42)
        state.bird_tray = [
            _bird("High Threat Wetland Engine", points=8),
            _bird("Plain Low Bird", points=1),
        ]
        legal_actions = [
            action
            for action in legal_actions_for_current_player(state)
            if action.action_type == ActionType.DRAW_CARDS and action.tray_index == 0
        ]

        evaluation = NetValueOpponentResponseAgent().evaluate_actions(state, legal_actions)[0]

        self.assertGreater(evaluation.breakdown.shared_denial_value, 0)


def _bird(name: str, *, points: int) -> BirdCard:
    return BirdCard(
        common_name=name,
        scientific_name=f"{name} scientific",
        content_pack=ContentPack.CORE,
        habitats={Habitat.WETLAND},
        food_cost=FoodCost(fixed={FoodType.FISH: 1}),
        victory_points=points,
        nest_type=NestType.BOWL,
        egg_limit=4,
        wingspan_cm=40,
        power=Power(
            color=PowerColor.BROWN,
            text="Tuck 1 [card] from your hand behind this bird.",
            implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
            handler_key="tuck_card",
        ),
    )
