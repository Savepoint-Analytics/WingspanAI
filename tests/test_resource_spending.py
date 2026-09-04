"""Choosing which food, which egg, and which card to give up.

These paths were resolved positionally: wild costs walked BASE_FOOD_TYPES so
invertebrate was always spent first, eggs were taken habitat-by-habitat in enum
order, and discards ranked on printed points alone. The egg case could spend the
exact egg an active round goal was counting.
"""

from __future__ import annotations

from collections import Counter
from unittest import TestCase, mock

from wingspan_ai.content.schemas import (
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    RoundGoal,
)
from wingspan_ai.rules import resource_spending
from wingspan_ai.rules.resource_spending import (
    discard_priority,
    egg_spend_order,
    flexible_food_spend_order,
    food_replacement_cost,
)

INV, SEED, FISH = FoodType.INVERTEBRATE, FoodType.SEED, FoodType.FISH


class _Card:
    def __init__(self, name, points=1, tags=(), habitats=(Habitat.FOREST,), cost=None, nest=None):
        self.common_name = name
        self.victory_points = points
        self.bonus_card_tags = list(tags)
        self.habitats = list(habitats)
        self.food_cost = cost or FoodCost()
        self.nest_type = nest
        self.egg_limit = 3


class _Slot:
    """Minimal stand-in: BirdSlot is a Pydantic model and rejects stub cards."""

    def __init__(self, card, eggs=0):
        self.card = card
        self.eggs = eggs


class _Player:
    def __init__(self, hand=(), food=None, bonus=(), habitats=None):
        self.hand = list(hand)
        self.food_tokens = dict(food or {})
        self.bonus_cards = list(bonus)
        self.habitats = habitats or {h: [] for h in Habitat}


class ReplacementCostTests(TestCase):
    def test_rare_food_costs_more_to_give_up_than_common(self) -> None:
        """Fish shows on one die face of six, invertebrate on two."""

        demand: Counter[FoodType] = Counter()
        self.assertGreater(food_replacement_cost(FISH, demand), food_replacement_cost(INV, demand))

    def test_needed_food_costs_more_than_spare_food_of_equal_rarity(self) -> None:
        demand = Counter({FISH: 2})
        self.assertGreater(
            food_replacement_cost(FISH, demand),
            food_replacement_cost(FoodType.RODENT, demand),
        )


class FoodSpendOrderTests(TestCase):
    def test_spends_the_most_replaceable_token_first(self) -> None:
        player = _Player(
            hand=[_Card("Needs fish", cost=FoodCost(fixed={FISH: 1}))],
            food={INV: 1, FISH: 1},
        )
        order = flexible_food_spend_order(player, FoodCost(wild_food_count=1))
        self.assertLess(
            order.index(INV), order.index(FISH), "should not spend the fish it still needs"
        )

    def test_no_flexible_cost_means_no_choice(self) -> None:
        self.assertEqual(flexible_food_spend_order(_Player(), FoodCost(fixed={INV: 1})), [])

    def test_ablation_restores_declaration_order(self) -> None:
        player = _Player(hand=[_Card("Needs inv", cost=FoodCost(fixed={INV: 3}))], food={INV: 3})
        with mock.patch.object(resource_spending, "VALUE_RESOURCE_SPENDING", False):
            order = flexible_food_spend_order(player, FoodCost(wild_food_count=1))
        self.assertEqual(order[0], INV)


class EggSpendOrderTests(TestCase):
    def _state(self, goal_name: str):
        class _RoundState:
            round_number = 1

        class _State:
            round_goals = [RoundGoal(name=goal_name, content_pack=ContentPack.CORE)]
            round_state = _RoundState()

        return _State()

    def _player_with_eggs(self):
        return _Player(
            habitats={
                Habitat.FOREST: [_Slot(_Card("F", nest=NestType.BOWL), eggs=1)],
                Habitat.GRASSLAND: [_Slot(_Card("G", nest=NestType.CAVITY), eggs=1)],
                Habitat.WETLAND: [],
            }
        )

    def test_eggs_counted_by_the_round_goal_are_spent_last(self) -> None:
        player = self._player_with_eggs()
        order = egg_spend_order(player, self._state("[egg] in [forest]"))
        self.assertEqual(order[0][0], Habitat.GRASSLAND, "must not spend the scoring forest egg")

    def test_nest_type_goals_also_protect(self) -> None:
        player = self._player_with_eggs()
        order = egg_spend_order(player, self._state("[egg] in [bowl]"))
        self.assertEqual(order[0][0], Habitat.GRASSLAND)

    def test_slots_without_eggs_are_not_offered(self) -> None:
        player = self._player_with_eggs()
        self.assertTrue(all(habitat != Habitat.WETLAND for habitat, _ in egg_spend_order(player)))

    def test_ablation_restores_enum_order(self) -> None:
        player = self._player_with_eggs()
        with mock.patch.object(resource_spending, "VALUE_RESOURCE_SPENDING", False):
            order = egg_spend_order(player, self._state("[egg] in [forest]"))
        self.assertEqual(order[0][0], Habitat.FOREST)


class DiscardPriorityTests(TestCase):
    def test_a_bonus_completing_card_is_kept_over_a_higher_point_one(self) -> None:
        """The old rule ranked on printed points and would discard the wrong card."""

        class _Bonus:
            name = "Forester"

        player = _Player(bonus=[_Bonus()], food={INV: 5})
        keeper = _Card("Cheap fit", points=2, tags=("Forester",))
        big = _Card("Expensive", points=6)
        self.assertGreater(discard_priority(keeper, player), discard_priority(big, player))

    def test_an_unplayable_card_is_discarded_before_a_playable_one(self) -> None:
        full = {h: [_Slot(_Card(f"x{i}")) for i in range(5)] for h in Habitat}
        player = _Player(food={INV: 5}, habitats=full)
        no_room = _Card("No room", points=5, habitats=(Habitat.FOREST,))
        player.habitats[Habitat.WETLAND] = []
        has_room = _Card("Has room", points=1, habitats=(Habitat.WETLAND,))
        self.assertLess(discard_priority(no_room, player), discard_priority(has_room, player))

    def test_ablation_restores_points_only_ranking(self) -> None:
        class _Bonus:
            name = "Forester"

        player = _Player(bonus=[_Bonus()], food={INV: 5})
        fit = _Card("Cheap fit", points=2, tags=("Forester",))
        big = _Card("Expensive", points=6)
        with mock.patch.object(resource_spending, "VALUE_RESOURCE_SPENDING", False):
            self.assertLess(discard_priority(fit, player), discard_priority(big, player))
