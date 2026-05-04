from unittest import TestCase

from wingspan_ai.agents import (
    MonteCarloRolloutAgent,
    StrategyArchetype,
    StrategyArchetypeAgent,
)
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from wingspan_ai.state.models import BirdSlot
from fixtures import make_test_catalog


class StrategyAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_test_catalog()

    def test_egg_focus_agent_prefers_laying_eggs_when_available(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=5)
        player = state.active_player
        card = next(card for card in self.catalog.birds if card.egg_limit >= 2)
        player.habitats[next(iter(card.habitats))].append(BirdSlot(card=card))

        action = StrategyArchetypeAgent(StrategyArchetype.EGG_FOCUS).choose_action(state)

        self.assertEqual(action.action_type, ActionType.LAY_EGGS)

    def test_monte_carlo_agent_selects_legal_action(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=6)
        agent = MonteCarloRolloutAgent(rollout_count=2, rollout_depth=2, random_seed=6)

        action = agent.choose_action(state)

        self.assertIn(action, legal_actions_for_current_player(state))

    def test_archetype_agent_rejects_empty_action_list(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1"], random_seed=7)
        state.round_state.game_over = True

        with self.assertRaises(ValueError):
            StrategyArchetypeAgent(StrategyArchetype.CARD_DRAW).choose_action(state)
