"""End-of-game bird scorecards and the activation counter behind them."""

from unittest import TestCase, skipIf

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.simulation.replay import state_hash, validate_simulation_replay
from wingspan_ai.simulation.runner import run_single_game
from wingspan_ai.state.models import BirdSlot


class BirdScorecardTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()
        cls.result = run_single_game(
            cls.catalog,
            [
                GreedyBaselineAgent(agent_id="greedy"),
                RandomLegalAgent(agent_id="rnd", random_seed=1),
            ],
            random_seed=5,
        )

    def test_one_scorecard_per_player_listing_every_played_bird(self) -> None:
        cards = [e for e in self.result.events if e.event_name == "bird_scorecard"]
        self.assertEqual([c.payload["player_id"] for c in cards], ["player_1", "player_2"])
        for card, player in zip(cards, self.result.state.players, strict=True):
            on_board = sorted(
                slot.card.common_name for habitat in player.habitats.values() for slot in habitat
            )
            self.assertEqual(sorted(b["common_name"] for b in card.payload["birds"]), on_board)
            self.assertEqual(card.payload["agent_id"], player.agent_id)
            for bird in card.payload["birds"]:
                self.assertIn(bird["round_played"], {1, 2, 3, 4})
                self.assertGreaterEqual(bird["activations"], 0)
                for key in ("eggs", "cached_food", "tucked_cards", "victory_points", "habitat"):
                    self.assertIn(key, bird)

    def test_scorecards_precede_game_ended(self) -> None:
        names = [e.event_name for e in self.result.events]
        self.assertLess(names.index("bird_scorecard"), names.index("game_ended"))

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(), "workbook required: the sample catalog has no powers"
    )
    def test_activations_are_counted_for_brown_birds(self) -> None:
        result = run_single_game(
            load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH),
            [GreedyBaselineAgent(agent_id="greedy"), GreedyBaselineAgent(agent_id="greedy_2")],
            random_seed=3,
        )
        cards = [e for e in result.events if e.event_name == "bird_scorecard"]
        brown = [b for c in cards for b in c.payload["birds"] if b["power_color"] == "brown"]
        self.assertTrue(brown)
        self.assertGreater(sum(b["activations"] for b in brown), 0)
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        self.assertTrue(validate_simulation_replay(catalog, result.events).is_valid)

    def test_activation_counter_does_not_touch_state_hash_or_replay(self) -> None:
        self.assertTrue(validate_simulation_replay(self.catalog, self.result.events).is_valid)
        state = self.result.state
        slot = next(
            slot
            for player in state.players
            for habitat in player.habitats.values()
            for slot in habitat
        )
        before = state_hash(state)
        slot.activations += 7
        self.assertEqual(state_hash(state), before)
        self.assertNotIn("activations", slot.model_dump())
        self.assertEqual(BirdSlot(card=slot.card).activations, 0)
