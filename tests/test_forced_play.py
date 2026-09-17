"""Forced keep-and-play instrument: injection, setup keep, forced play, replay."""

from unittest import TestCase, skipIf

from wingspan_ai.agents import GreedyBaselineAgent
from wingspan_ai.agents.archetypes import StrategyArchetype, StrategyArchetypeAgent
from wingspan_ai.agents.forced_play import (
    ForcedPlayAgent,
    KeepBirdsSetupPolicy,
    inject_opening_cards,
)
from wingspan_ai.agents.setup import DefaultSetupPolicy, InitialSelectionContext
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import (
    apply_initial_selection_choice,
    legal_actions_for_current_player,
    setup_base_game,
)
from wingspan_ai.simulation.replay import validate_simulation_replay
from wingspan_ai.simulation.runner import run_single_game

PAIR = ("Baird's Sparrow", "Northern Mockingbird")


@skipIf(not DEFAULT_WORKBOOK_PATH.exists(), "workbook required")
class ForcedPlayTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)

    def _dealt(self, seed: int = 1):
        return setup_base_game(
            self.catalog,
            player_ids=["player_1", "player_2"],
            random_seed=seed,
            apply_initial_selection=False,
        )

    def test_injection_swaps_from_the_deck_and_preserves_deck_size(self) -> None:
        state = self._dealt()
        deck_before = len(state.decks.bird_deck)
        hand_before = [c.common_name for c in state.players[0].hand]
        missing = inject_opening_cards(state, "player_1", list(PAIR))
        self.assertEqual(missing, [])
        hand_after = [c.common_name for c in state.players[0].hand]
        self.assertEqual(len(hand_after), len(hand_before))
        self.assertTrue(set(PAIR) <= set(hand_after))
        self.assertEqual(len(state.decks.bird_deck), deck_before)
        for name in PAIR:
            self.assertFalse(any(c.common_name == name for c in state.decks.bird_deck))
        # The displaced hand cards went into the deck, nowhere else.
        displaced = [n for n in hand_before if n not in hand_after]
        for name in displaced:
            self.assertTrue(any(c.common_name == name for c in state.decks.bird_deck))

    def test_injection_reports_birds_it_cannot_reach(self) -> None:
        state = self._dealt()
        other_hand = state.players[1].hand[0].common_name
        missing = inject_opening_cards(state, "player_1", [other_hand])
        self.assertEqual(missing, [other_hand])

    def test_keep_policy_keeps_forced_birds_and_the_base_food(self) -> None:
        state = self._dealt()
        inject_opening_cards(state, "player_1", list(PAIR))
        player = state.players[0]
        base = DefaultSetupPolicy().choose_initial_selection(player, InitialSelectionContext())
        forced = KeepBirdsSetupPolicy(DefaultSetupPolicy(), PAIR).choose_initial_selection(
            player, InitialSelectionContext()
        )
        self.assertTrue(set(PAIR) <= set(forced.kept_bird_names))
        self.assertEqual(len(forced.kept_bird_names), max(len(base.kept_bird_names), 2))
        self.assertEqual(len(forced.kept_bird_names) + len(forced.starting_food), 5)
        self.assertEqual(
            KeepBirdsSetupPolicy(DefaultSetupPolicy(), PAIR).policy_id,
            "keep_birds:default_setup_v1",
        )

    def test_forced_agent_plays_the_pair_into_a_shared_row(self) -> None:
        state = self._dealt()
        inject_opening_cards(state, "player_1", list(PAIR))
        base = StrategyArchetypeAgent(StrategyArchetype.ENGINE_BUILDER, agent_id="eb")
        base.setup_policy = DefaultSetupPolicy()
        agent = ForcedPlayAgent(base, PAIR)
        self.assertEqual(agent.agent_id, "eb")
        selection = agent.choose_initial_selection(state.players[0])
        apply_initial_selection_choice(state.players[0], selection)
        # Enough food for both birds, so neither play starves the other.
        state.players[0].food_tokens.update(
            {FoodType.INVERTEBRATE: 2, FoodType.SEED: 1, FoodType.FRUIT: 1}
        )
        choice = agent.select_action(state, legal_actions_for_current_player(state))
        self.assertEqual(choice.action_type, ActionType.PLAY_BIRD)
        self.assertIn(choice.bird_common_name, PAIR)
        # Both birds can only share grassland.
        self.assertEqual(choice.habitat.value, "grassland")

    def test_forced_agent_does_not_split_the_pair_when_the_row_is_not_enterable(self) -> None:
        state = self._dealt()
        inject_opening_cards(state, "player_1", list(PAIR))
        base = StrategyArchetypeAgent(StrategyArchetype.ENGINE_BUILDER, agent_id="eb")
        base.setup_policy = DefaultSetupPolicy()
        agent = ForcedPlayAgent(base, PAIR)
        apply_initial_selection_choice(
            state.players[0], agent.choose_initial_selection(state.players[0])
        )
        # Put the sparrow on the grassland row by hand; the mockingbird now
        # needs an egg to enter that row, which the player does not have.
        from wingspan_ai.content.schemas import Habitat
        from wingspan_ai.state.models import BirdSlot

        player = state.players[0]
        sparrow = next(c for c in player.hand if c.common_name == PAIR[0])
        player.hand.remove(sparrow)
        player.habitats[Habitat.GRASSLAND].append(BirdSlot(card=sparrow))
        player.food_tokens.update({FoodType.INVERTEBRATE: 1, FoodType.FRUIT: 1})
        legal = legal_actions_for_current_player(state)
        wrong_row = [
            a
            for a in legal
            if a.action_type == ActionType.PLAY_BIRD and a.bird_common_name == PAIR[1]
        ]
        self.assertTrue(wrong_row)
        self.assertTrue(all(a.habitat != Habitat.GRASSLAND for a in wrong_row))
        choice = agent.select_action(state, legal)
        self.assertFalse(
            choice.action_type == ActionType.PLAY_BIRD and choice.bird_common_name == PAIR[1]
        )

    def test_injected_game_replays(self) -> None:
        base = StrategyArchetypeAgent(StrategyArchetype.ENGINE_BUILDER, agent_id="eb")
        base.setup_policy = DefaultSetupPolicy()
        result = run_single_game(
            self.catalog,
            [ForcedPlayAgent(base, PAIR), GreedyBaselineAgent(agent_id="g")],
            random_seed=4,
            opening_hand_overrides={"player_1": list(PAIR)},
        )
        started = next(e for e in result.events if e.event_name == "game_started")
        self.assertEqual(started.payload["opening_hand_overrides"], {"player_1": list(PAIR)})
        self.assertTrue(validate_simulation_replay(self.catalog, result.events).is_valid)
        summary = next(
            e
            for e in result.events
            if e.event_name == "agent_decision_summary" and e.player_id == "player_1"
        )
        self.assertEqual(summary.payload["forced_play_birds"], list(PAIR))
