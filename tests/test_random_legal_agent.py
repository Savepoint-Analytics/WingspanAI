from unittest import TestCase

from wingspan_ai.agents.random_legal import RandomLegalAgent
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from fixtures import make_test_catalog


class RandomLegalAgentTests(TestCase):
    def test_seeded_agent_selects_reproducibly_from_legal_actions(self) -> None:
        catalog = make_test_catalog()
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)
        legal_actions = legal_actions_for_current_player(state)

        first_agent = RandomLegalAgent(random_seed=99)
        second_agent = RandomLegalAgent(random_seed=99)

        self.assertEqual(
            first_agent.select_action(legal_actions),
            second_agent.select_action(legal_actions),
        )

    def test_agent_can_choose_for_active_player_state(self) -> None:
        catalog = make_test_catalog()
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)

        action = RandomLegalAgent(random_seed=1).choose_action(state)

        self.assertIn(action, legal_actions_for_current_player(state))
