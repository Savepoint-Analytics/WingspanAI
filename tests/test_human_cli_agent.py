from unittest import TestCase

from wingspan_ai.agents import HumanCliAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import setup_base_game


class HumanCliAgentTests(TestCase):
    def test_human_cli_agent_can_use_default_setup_selection(self) -> None:
        catalog = make_sample_catalog()
        state = setup_base_game(
            catalog,
            player_ids=["p1"],
            random_seed=21,
            apply_initial_selection=False,
        )
        agent = HumanCliAgent(use_default_setup=True)

        selection = agent.choose_initial_selection(state.players[0])

        self.assertEqual(selection.player_id, "p1")
        self.assertEqual(len(selection.kept_bonus_card_names), 1)

    def test_human_cli_agent_decision_summary_is_telemetry_safe(self) -> None:
        agent = HumanCliAgent()
        action = LegalAction(action_type="draw_cards", player_id="p1", draw_from_deck=True)

        summary = agent.summarize_decision(None, [action], action)  # type: ignore[arg-type]

        self.assertEqual(summary["policy"], "human_cli")

    def test_human_action_renderer_describes_concrete_choices(self) -> None:
        action = LegalAction(
            action_type=ActionType.GAIN_FOOD,
            player_id="p1",
            food_types=(FoodType.SEED, FoodType.FISH),
            reroll_birdfeeder=True,
            spend_card_for_extra_food=True,
            discard_card_common_name="Canada Goose",
        )

        rendered = render_action(action)

        self.assertEqual(
            rendered,
            "Gain seed and fish if rolled, after rerolling the birdfeeder "
            "by discarding a card (Canada Goose)",
        )
