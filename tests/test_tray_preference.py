"""Tests that agents can express a preference between face-up tray cards.

Seven of nine agents previously scored every tray card identically — measured
100% blind across 30 seeded openings while the options differed by a mean 3.0
victory points. With all options tied they took whichever action was enumerated
first, which is always tray index 0.
"""

from unittest import TestCase, skipIf

from wingspan_ai.agents.archetypes import StrategyArchetype, _score_action_for_archetype
from wingspan_ai.agents.greedy import _heuristic_tiebreaker
from wingspan_ai.agents.tray_preference import (
    base_card_affinity,
    can_afford,
    drawn_tray_cards,
    egg_focus_affinity,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import (
    legal_actions_for_current_player,
    score_player,
    setup_base_game,
)
from wingspan_ai.state.models import BirdSlot


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class TrayBlindnessTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)

    def _tray_draws(self, seed: int):
        state = setup_base_game(
            self.catalog, player_ids=["player_1", "player_2"], random_seed=seed
        )
        draws = [
            action
            for action in legal_actions_for_current_player(state)
            if action.action_type == ActionType.DRAW_CARDS and action.tray_indices
        ]
        return state, draws

    def test_no_agent_is_indifferent_across_every_tray_card(self) -> None:
        blind_states = {archetype.value: 0 for archetype in StrategyArchetype}
        blind_states["greedy_immediate"] = 0
        examined = 0

        for seed in range(1, 21):
            state, draws = self._tray_draws(seed)
            if len(draws) < 2:
                continue
            examined += 1
            before = score_player(state, "player_1").total
            for archetype in StrategyArchetype:
                values = {
                    round(_score_action_for_archetype(state, a, archetype, before), 6)
                    for a in draws
                }
                if len(values) == 1:
                    blind_states[archetype.value] += 1
            greedy_values = {round(_heuristic_tiebreaker(state, a), 6) for a in draws}
            if len(greedy_values) == 1:
                blind_states["greedy_immediate"] += 1

        self.assertGreater(examined, 10)
        for agent, blind in blind_states.items():
            # Allow the rare genuine tie, but not systematic indifference.
            self.assertLess(blind, examined * 0.25, f"{agent} blind in {blind}/{examined}")

    def test_greedy_card_quality_never_outranks_a_real_score_difference(self) -> None:
        """The tie-break must order equal draws, not beat a scoring action."""

        state, draws = self._tray_draws(1)
        self.assertTrue(draws)
        for action in draws:
            self.assertLess(_heuristic_tiebreaker(state, action), 11.0)
            self.assertGreaterEqual(_heuristic_tiebreaker(state, action), 10.0)

    def test_archetypes_disagree_about_which_tray_card_is_best(self) -> None:
        """Distinct strategies should not all converge on the same pick."""

        picks = set()
        for seed in range(1, 16):
            state, draws = self._tray_draws(seed)
            if len(draws) < 2:
                continue
            before = score_player(state, "player_1").total
            chosen = {
                max(
                    draws,
                    key=lambda a, arc=archetype: _score_action_for_archetype(
                        state, a, arc, before
                    ),
                ).tray_indices
                for archetype in StrategyArchetype
            }
            picks.add(len(chosen))

        self.assertIn(True, [count > 1 for count in picks], "archetypes never disagreed")


class AffinityTests(TestCase):
    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_unplayable_card_scores_zero(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(
            catalog, player_ids=["player_1", "player_2"], random_seed=1
        )
        player = state.players[0]
        card = catalog.birds[0]
        for habitat in card.habitats:
            player.habitats[habitat] = [
                BirdSlot(card=catalog.birds[1]) for _ in range(5)
            ]

        self.assertEqual(base_card_affinity(card, player), 0.0)

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_egg_focus_prefers_higher_egg_capacity(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(
            catalog, player_ids=["player_1", "player_2"], random_seed=1
        )
        player = state.players[0]
        player.food_tokens = {food: 5 for food in player.food_tokens}
        low, high = sorted(
            (b for b in catalog.birds if b.egg_limit in (1, 5)),
            key=lambda b: b.egg_limit,
        )[:1] + sorted(
            (b for b in catalog.birds if b.egg_limit == 5), key=lambda b: b.common_name
        )[:1]

        self.assertGreater(
            egg_focus_affinity(high, player), egg_focus_affinity(low, player)
        )

    def test_drawn_tray_cards_ignores_deck_draws(self) -> None:
        from wingspan_ai.rules.actions import LegalAction

        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(
            catalog, player_ids=["player_1", "player_2"], random_seed=1
        )
        deck_only = LegalAction(
            action_type=ActionType.DRAW_CARDS,
            player_id="player_1",
            draw_from_deck=True,
            draw_from_deck_count=1,
        )

        self.assertEqual(drawn_tray_cards(state, deck_only), [])

    def test_can_afford_respects_wild_costs(self) -> None:
        from wingspan_ai.content.schemas import FoodCost, FoodType

        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(
            catalog, player_ids=["player_1", "player_2"], random_seed=1
        )
        player = state.players[0]
        player.food_tokens = {food: 0 for food in player.food_tokens}
        player.food_tokens[FoodType.SEED] = 2

        self.assertTrue(can_afford(player, FoodCost(wild_food_count=2)))
        self.assertFalse(can_afford(player, FoodCost(wild_food_count=3)))
