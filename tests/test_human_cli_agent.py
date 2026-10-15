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


class HumanCliSetupVisibilityTests(TestCase):
    """The setup screen shows the public table; the post-setup summary stays public."""

    def _game(self):
        from wingspan_ai.agents import GreedyBaselineAgent
        from wingspan_ai.simulation.runner import _initial_selection_context

        catalog = make_sample_catalog()
        state = setup_base_game(
            catalog,
            player_ids=["player_1", "player_2"],
            random_seed=21,
            apply_initial_selection=False,
        )
        state.players[0].agent_id = "human_cli_p1"
        state.players[1].agent_id = GreedyBaselineAgent().agent_id
        return state, _initial_selection_context(state)

    def test_setup_table_shows_goals_feeder_tray_and_seats(self) -> None:
        from wingspan_ai.agents.human_cli import setup_table_lines

        state, context = self._game()
        text = "\n".join(setup_table_lines(state.players[0], context))

        for goal in state.round_goals:
            self.assertIn(goal.name, text)
        for face in state.birdfeeder.dice:
            self.assertIn(face.value, text)
        for card in state.bird_tray:
            self.assertIn(card.common_name, text)
        self.assertIn(state.players[1].agent_id, text)
        self.assertEqual(len(context.birdfeeder_faces), len(state.birdfeeder.dice))

    def test_setup_summary_hides_opponent_card_names(self) -> None:
        import io
        from contextlib import redirect_stdout

        from wingspan_ai.rules.base_game import (
            apply_initial_selection_choice,
            choose_default_initial_selection,
        )

        state, _context = self._game()
        opponent_hand = [card.common_name for card in state.players[1].hand]
        for player in state.players:
            apply_initial_selection_choice(player, choose_default_initial_selection(player))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            HumanCliAgent(use_default_setup=False).observe_setup_complete(state)
        text = buffer.getvalue()

        self.assertIn(f"kept {len(state.players[1].hand)} bird", text)
        for name in opponent_hand:
            self.assertNotIn(name, text)
