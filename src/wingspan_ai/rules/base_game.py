"""Base-game setup, legal actions, transitions, and scoring skeleton."""

from __future__ import annotations

import random
from dataclasses import dataclass

from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import (
    ContentCatalog,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    RulesModule,
    RulesetMetadata,
)
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.state.models import (
    BirdSlot,
    BirdfeederState,
    DeckState,
    GameState,
    PlayerState,
    RoundState,
)

STARTING_HAND_SIZE = 5
STARTING_BONUS_CARD_COUNT = 2
BIRD_TRAY_SIZE = 3
BIRDFEEDER_DICE_COUNT = 5


@dataclass(frozen=True)
class FinalScoreBreakdown:
    """Current scoring categories for final-score regression tests."""

    player_id: str
    bird_points: int
    bonus_points: int
    round_goal_points: int
    egg_points: int
    cached_food_points: int
    tucked_card_points: int

    @property
    def total(self) -> int:
        return (
            self.bird_points
            + self.bonus_points
            + self.round_goal_points
            + self.egg_points
            + self.cached_food_points
            + self.tucked_card_points
        )


def setup_base_game(
    catalog: ContentCatalog,
    *,
    player_ids: list[str],
    random_seed: int,
    game_id: str = "game_1",
) -> GameState:
    """Create a deterministic base-game state from a content catalog."""

    if len(player_ids) < 1:
        raise ValueError("setup requires at least one player")

    rng = random.Random(random_seed)
    bird_deck = list(catalog.birds)
    bonus_deck = list(catalog.bonus_cards)
    round_goals = list(catalog.round_goals)
    rng.shuffle(bird_deck)
    rng.shuffle(bonus_deck)
    rng.shuffle(round_goals)

    players: list[PlayerState] = []
    for player_id in player_ids:
        hand = _draw_many(bird_deck, STARTING_HAND_SIZE)
        bonus_cards = _draw_many(bonus_deck, STARTING_BONUS_CARD_COUNT)
        players.append(PlayerState(player_id=player_id, hand=hand, bonus_cards=bonus_cards))

    bird_tray = _draw_many(bird_deck, BIRD_TRAY_SIZE)
    ruleset = (
        catalog.rulesets[0]
        if catalog.rulesets
        else _default_ruleset(len(player_ids), random_seed)
    )

    return GameState(
        game_id=game_id,
        ruleset=ruleset.model_copy(
            update={"player_count": len(player_ids), "random_seed": random_seed}
        ),
        random_seed=random_seed,
        players=players,
        decks=DeckState(bird_deck=bird_deck, bonus_deck=bonus_deck),
        bird_tray=bird_tray,
        birdfeeder=BirdfeederState(dice=_roll_birdfeeder(rng)),
        round_goals=round_goals[:4],
        round_state=RoundState(),
    )


def legal_actions_for_current_player(state: GameState) -> list[LegalAction]:
    """Generate legal actions for the active player."""

    return legal_actions_for_player(state, state.active_player.player_id)


def legal_actions_for_player(state: GameState, player_id: str) -> list[LegalAction]:
    """Generate currently legal base-game actions for a player."""

    player = _get_player(state, player_id)
    if state.round_state.game_over or player.action_cubes_available <= 0:
        return []

    actions: list[LegalAction] = []
    actions.extend(_legal_play_bird_actions(player))
    actions.extend(_legal_gain_food_actions(player, state.birdfeeder))
    actions.extend(_legal_lay_eggs_actions(player))
    actions.extend(_legal_draw_cards_actions(player, state))
    return actions


def apply_action(state: GameState, action: LegalAction) -> GameState:
    """Apply one legal action and advance the turn pointer."""

    legal_actions = legal_actions_for_player(state, action.player_id)
    if action not in legal_actions:
        raise ValueError(f"illegal action for {action.player_id}: {action.model_dump()}")

    next_state = state.model_copy(deep=True)
    player = _get_player(next_state, action.player_id)

    if action.action_type == ActionType.PLAY_BIRD:
        _apply_play_bird(player, action)
    elif action.action_type == ActionType.GAIN_FOOD:
        _apply_gain_food(player, next_state.birdfeeder, action)
    elif action.action_type == ActionType.LAY_EGGS:
        _apply_lay_eggs(player, action)
    elif action.action_type == ActionType.DRAW_CARDS:
        _apply_draw_cards(player, next_state, action)
    else:
        raise ValueError(f"unsupported action type: {action.action_type}")

    _advance_turn(next_state)
    return next_state


def score_player(state: GameState, player_id: str) -> FinalScoreBreakdown:
    """Score implemented final-score categories for a player."""

    player = _get_player(state, player_id)
    bird_points = sum(
        slot.card.victory_points for slots in player.habitats.values() for slot in slots
    )
    egg_points = sum(slot.eggs for slots in player.habitats.values() for slot in slots)
    cached_food_points = sum(
        slot.cached_food for slots in player.habitats.values() for slot in slots
    )
    tucked_card_points = sum(
        slot.tucked_cards for slots in player.habitats.values() for slot in slots
    )
    return FinalScoreBreakdown(
        player_id=player_id,
        bird_points=bird_points,
        bonus_points=0,
        round_goal_points=0,
        egg_points=egg_points,
        cached_food_points=cached_food_points,
        tucked_card_points=tucked_card_points,
    )


def _legal_play_bird_actions(player: PlayerState) -> list[LegalAction]:
    actions: list[LegalAction] = []
    for card in player.hand:
        for habitat in card.habitats:
            slot_index = len(player.habitats[habitat])
            if slot_index >= 5:
                continue
            if not _can_pay_food_cost(player, card.food_cost):
                continue
            if player.total_eggs < egg_cost_for_slot(slot_index):
                continue
            actions.append(
                LegalAction(
                    action_type=ActionType.PLAY_BIRD,
                    player_id=player.player_id,
                    bird_common_name=card.common_name,
                    habitat=habitat,
                )
            )
    return actions


def _legal_gain_food_actions(player: PlayerState, birdfeeder: BirdfeederState) -> list[LegalAction]:
    seen: set[FoodType] = set()
    actions: list[LegalAction] = []
    for food_type in birdfeeder.dice:
        if food_type in seen:
            continue
        seen.add(food_type)
        actions.append(
            LegalAction(
                action_type=ActionType.GAIN_FOOD,
                player_id=player.player_id,
                food_type=food_type,
            )
        )
    return actions


def _legal_lay_eggs_actions(player: PlayerState) -> list[LegalAction]:
    if player.available_egg_capacity <= 0 or not player.played_birds:
        return []
    return [
        LegalAction(
            action_type=ActionType.LAY_EGGS,
            player_id=player.player_id,
            egg_count=min(2, player.available_egg_capacity),
        )
    ]


def _legal_draw_cards_actions(player: PlayerState, state: GameState) -> list[LegalAction]:
    actions = [
        LegalAction(
            action_type=ActionType.DRAW_CARDS,
            player_id=player.player_id,
            tray_index=index,
        )
        for index, _card in enumerate(state.bird_tray)
    ]
    if state.decks.bird_deck:
        actions.append(
            LegalAction(
                action_type=ActionType.DRAW_CARDS,
                player_id=player.player_id,
                draw_from_deck=True,
            )
        )
    return actions


def _apply_play_bird(player: PlayerState, action: LegalAction) -> None:
    if action.bird_common_name is None or action.habitat is None:
        raise ValueError("play bird action requires bird_common_name and habitat")

    hand_index, card = next(
        (index, card)
        for index, card in enumerate(player.hand)
        if card.common_name == action.bird_common_name
    )
    _spend_food_cost(player, card.food_cost)
    _spend_eggs(player, egg_cost_for_slot(len(player.habitats[action.habitat])))
    player.hand.pop(hand_index)
    player.habitats[action.habitat].append(BirdSlot(card=card))


def _apply_gain_food(player: PlayerState, birdfeeder: BirdfeederState, action: LegalAction) -> None:
    if action.food_type is None:
        raise ValueError("gain food action requires food_type")
    die_index = birdfeeder.dice.index(action.food_type)
    birdfeeder.dice.pop(die_index)
    player.food_tokens[action.food_type] = player.food_tokens.get(action.food_type, 0) + 1


def _apply_lay_eggs(player: PlayerState, action: LegalAction) -> None:
    eggs_to_place = action.egg_count or 0
    for habitat in Habitat:
        for slot in player.habitats[habitat]:
            if eggs_to_place <= 0:
                return
            added_eggs = min(slot.available_egg_capacity, eggs_to_place)
            slot.eggs += added_eggs
            eggs_to_place -= added_eggs


def _apply_draw_cards(player: PlayerState, state: GameState, action: LegalAction) -> None:
    if action.draw_from_deck:
        player.hand.append(state.decks.bird_deck.pop(0))
        return

    if action.tray_index is None:
        raise ValueError("draw cards action requires tray_index or draw_from_deck")

    player.hand.append(state.bird_tray.pop(action.tray_index))
    if state.decks.bird_deck:
        state.bird_tray.insert(action.tray_index, state.decks.bird_deck.pop(0))


def _advance_turn(state: GameState) -> None:
    player = state.active_player
    player.action_cubes_available -= 1

    if all(candidate.action_cubes_available == 0 for candidate in state.players):
        if state.round_state.round_number == 4:
            state.round_state.game_over = True
            return
        state.round_state.round_number += 1
        cubes_for_round = 9 - state.round_state.round_number
        for candidate in state.players:
            candidate.action_cubes_available = cubes_for_round
        state.round_state.active_player_index = 0
        state.round_state.turn_number += 1
        return

    next_index = (state.round_state.active_player_index + 1) % len(state.players)
    while state.players[next_index].action_cubes_available == 0:
        next_index = (next_index + 1) % len(state.players)
    state.round_state.active_player_index = next_index
    state.round_state.turn_number += 1


def _can_pay_food_cost(player: PlayerState, food_cost: FoodCost) -> bool:
    remaining_food = dict(player.food_tokens)
    for food_type, count in food_cost.fixed.items():
        if remaining_food.get(food_type, 0) < count:
            return False
        remaining_food[food_type] = remaining_food.get(food_type, 0) - count
    remaining_any_cost = food_cost.wild_food_count + food_cost.choice_food_count
    return sum(remaining_food.values()) >= remaining_any_cost


def _spend_food_cost(player: PlayerState, food_cost: FoodCost) -> None:
    for food_type, count in food_cost.fixed.items():
        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) - count

    remaining_any_cost = food_cost.wild_food_count + food_cost.choice_food_count
    for food_type in BASE_FOOD_TYPES:
        while remaining_any_cost > 0 and player.food_tokens.get(food_type, 0) > 0:
            player.food_tokens[food_type] -= 1
            remaining_any_cost -= 1


def _spend_eggs(player: PlayerState, egg_count: int) -> None:
    remaining = egg_count
    for habitat in Habitat:
        for slot in player.habitats[habitat]:
            if remaining <= 0:
                return
            spent = min(slot.eggs, remaining)
            slot.eggs -= spent
            remaining -= spent


def egg_cost_for_slot(slot_index: int) -> int:
    """Return egg cost for playing into a zero-based habitat slot."""

    if slot_index <= 0:
        return 0
    if slot_index <= 2:
        return 1
    return 2


def _get_player(state: GameState, player_id: str) -> PlayerState:
    return next(player for player in state.players if player.player_id == player_id)


def _draw_many(deck: list, count: int) -> list:
    drawn = deck[:count]
    del deck[:count]
    return drawn


def _roll_birdfeeder(rng: random.Random) -> list[FoodType]:
    return [rng.choice(BASE_FOOD_TYPES) for _ in range(BIRDFEEDER_DICE_COUNT)]


def _default_ruleset(player_count: int, random_seed: int) -> RulesetMetadata:
    return RulesetMetadata(
        ruleset_id="core_base_game_v1",
        content_packs=[ContentPack.CORE],
        rules_modules=[RulesModule.BASE_GAME],
        player_count=player_count,
        random_seed=random_seed,
    )
