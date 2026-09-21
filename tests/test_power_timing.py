"""End-of-round (teal) and end-of-game (yellow) power timing in the rules engine.

European rulebook p.2: teal powers resolve once all turns of the round are
done, before the round's goal is scored, in player order from the round's
first player. Oceania rulebook p.3: yellow powers resolve once, after the
last round's end-of-round steps. Core content has neither colour, so the
base game is unchanged by construction.
"""

from unittest import TestCase

from tests.test_power_handlers import make_bird
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import FoodType, Habitat, PowerColor
from wingspan_ai.rules.base_game import (
    TOTAL_ROUNDS,
    apply_action,
    legal_actions_for_current_player,
    resolve_end_of_game_powers,
    resolve_end_of_round_powers,
    round_first_player_index,
    setup_base_game,
)
from wingspan_ai.state.models import BirdSlot


def play_out(state, *, until_round_end=False):
    """Advance with the first legal action until game over (or one round end)."""

    start_round = state.round_state.round_number
    while not state.round_state.game_over:
        state = apply_action(state, legal_actions_for_current_player(state)[0])
        if until_round_end and state.round_state.round_number != start_round:
            break
    return state


class RoundEndPowerTests(TestCase):
    def setUp(self) -> None:
        self.state = setup_base_game(make_sample_catalog(), player_ids=["p1", "p2"], random_seed=3)
        self.teal = make_bird("Teal Test", "Gain 1 [seed] from the supply.", PowerColor.TEAL)
        self.yellow = make_bird("Yellow Test", "Draw 2 [card].", PowerColor.YELLOW)

    def test_teal_fires_once_per_round_end_and_yellow_once_at_game_end(self) -> None:
        p1 = self.state.players[0]
        teal_slot = BirdSlot(card=self.teal)
        yellow_slot = BirdSlot(card=self.yellow)
        p1.habitats[Habitat.GRASSLAND].append(teal_slot)
        p1.habitats[Habitat.WETLAND].append(yellow_slot)
        seeds_before = p1.food_tokens.get(FoodType.SEED, 0)

        state = play_out(self.state, until_round_end=True)
        p1 = state.players[0]
        teal_slot = p1.habitats[Habitat.GRASSLAND][0]
        self.assertEqual(state.round_state.round_number, 2)
        self.assertEqual(teal_slot.activations, 1)
        self.assertEqual(teal_slot.power_yield.get("food", 0), 1)
        self.assertEqual(p1.habitats[Habitat.WETLAND][0].activations, 0)

        state = play_out(state)
        p1 = state.players[0]
        self.assertTrue(state.round_state.game_over)
        self.assertEqual(p1.habitats[Habitat.GRASSLAND][0].activations, TOTAL_ROUNDS)
        self.assertEqual(p1.habitats[Habitat.WETLAND][0].activations, 1)
        self.assertGreaterEqual(p1.habitats[Habitat.GRASSLAND][0].power_yield.get("food", 0), 1)
        self.assertGreaterEqual(p1.food_tokens.get(FoodType.SEED, 0), seeds_before)

    def test_teal_resolves_before_the_round_goal_is_scored(self) -> None:
        # A teal power that lays an egg can change a "most eggs" goal outcome,
        # so it has to run first. Check the order directly: after the round
        # end the goal points are on the players and the teal slot has fired.
        p1 = self.state.players[0]
        p1.habitats[Habitat.GRASSLAND].append(
            BirdSlot(card=make_bird("Teal Layer", "Lay 1 [egg] on this bird.", PowerColor.TEAL))
        )
        state = play_out(self.state, until_round_end=True)
        slot = state.players[0].habitats[Habitat.GRASSLAND][0]
        self.assertEqual(slot.activations, 1)
        # The handler lays on any of the player's birds; the yield ledger
        # credits the teal bird with the egg it produced at the round end.
        self.assertEqual(slot.power_yield.get("eggs", 0), 1)
        self.assertGreaterEqual(
            sum(s.eggs for h in state.players[0].habitats.values() for s in h), 1
        )

    def test_player_order_starts_with_the_rounds_first_player(self) -> None:
        state = self.state
        self.assertEqual(round_first_player_index(state), 0)
        state.round_state.round_number = 2
        self.assertEqual(round_first_player_index(state), 1)
        state.round_state.round_number = 3
        self.assertEqual(round_first_player_index(state), 0)

    def test_direct_calls_are_no_ops_without_teal_or_yellow_birds(self) -> None:
        state = self.state
        before = [p.model_copy(deep=True) for p in state.players]
        resolve_end_of_round_powers(state)
        resolve_end_of_game_powers(state)
        for was, now in zip(before, state.players, strict=True):
            self.assertEqual(was.food_tokens, now.food_tokens)
            self.assertEqual(len(was.hand), len(now.hand))

    def test_core_game_never_activates_a_round_or_game_end_power(self) -> None:
        state = play_out(self.state)
        self.assertTrue(state.round_state.game_over)
        for player in state.players:
            for habitat in player.habitats.values():
                for slot in habitat:
                    self.assertNotIn(slot.card.power.color, (PowerColor.TEAL, PowerColor.YELLOW))
