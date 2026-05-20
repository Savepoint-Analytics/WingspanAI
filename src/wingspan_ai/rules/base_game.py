"""Base-game setup, legal actions, transitions, and scoring skeleton."""

from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import combinations_with_replacement

from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import (
    ContentCatalog,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    RulesetMetadata,
    RulesModule,
)
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.power_registry import classify_power_handler_key
from wingspan_ai.state.models import (
    BirdfeederState,
    BirdSlot,
    DeckState,
    GameState,
    PlayerState,
    RngDrawRecord,
    RoundState,
)

STARTING_HAND_SIZE = 5
STARTING_BONUS_CARD_COUNT = 2
STARTING_SELECTED_BIRD_COUNT = 3
BIRD_FOOD_SELECTION_TOTAL = 5
BIRD_TRAY_SIZE = 3
BIRDFEEDER_DICE_COUNT = 5
CORE_RULEBOOK = "rulebook_pdfs/WS_Core_Rulebook.pdf"
TURN_STRUCTURE_RULE_SOURCE = {
    "rulebook": CORE_RULEBOOK,
    "page": 4,
    "section": "Overview / Turn Structure",
}
ROUND_STRUCTURE_RULE_SOURCE = {
    "rulebook": CORE_RULEBOOK,
    "page": 5,
    "section": "Round Structure",
}
BASE_ACTION_CUBES_BY_ROUND: dict[int, int] = {
    1: 8,
    2: 7,
    3: 6,
    4: 5,
}
ROUND_GOAL_GREEN_SCORES: dict[int, tuple[int, ...]] = {
    1: (4, 1, 0, 0, 0),
    2: (5, 2, 1, 0, 0),
    3: (6, 3, 2, 0, 0),
    4: (7, 4, 3, 0, 0),
}
COLOR_WORDS = {
    "ash",
    "black",
    "blue",
    "bronzed",
    "brown",
    "chestnut",
    "gray",
    "green",
    "indigo",
    "painted",
    "purple",
    "red",
    "rose",
    "ruby",
    "ruddy",
    "scarlet",
    "snowy",
    "white",
    "yellow",
}


@dataclass(frozen=True)
class InitialSelection:
    """Player setup choice for kept cards and starting food."""

    player_id: str
    kept_bird_names: list[str]
    kept_bonus_card_names: list[str]
    starting_food: list[FoodType] = field(default_factory=list)


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
    apply_initial_selection: bool = True,
    initial_selection_strategy: Callable[[PlayerState], InitialSelection] | None = None,
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
    bird_discard: list = []
    bonus_discard: list = []
    for player_id in player_ids:
        hand = _draw_many(bird_deck, STARTING_HAND_SIZE)
        bonus_cards = _draw_many(bonus_deck, STARTING_BONUS_CARD_COUNT)
        player = PlayerState(player_id=player_id, hand=hand, bonus_cards=bonus_cards)
        if apply_initial_selection:
            selection = (
                initial_selection_strategy(player)
                if initial_selection_strategy is not None
                else choose_default_initial_selection(player)
            )
            discarded_birds, discarded_bonus_cards = apply_initial_selection_choice(
                player, selection
            )
            bird_discard.extend(discarded_birds)
            bonus_discard.extend(discarded_bonus_cards)
        players.append(player)

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
        decks=DeckState(
            bird_deck=bird_deck,
            bird_discard=bird_discard,
            bonus_deck=bonus_deck,
            bonus_discard=bonus_discard,
        ),
        bird_tray=bird_tray,
        birdfeeder=BirdfeederState(dice=_roll_birdfeeder(rng)),
        round_goals=round_goals[:4],
        round_state=RoundState(),
    )


def choose_default_initial_selection(player: PlayerState) -> InitialSelection:
    """Choose a deterministic v1 approximation of initial hand/food selection.

    The physical game asks each player to keep any combination of bird cards and
    starting food tokens totaling five, then keep one of two bonus cards. This
    placeholder chooses three birds, one bonus card, and two food tokens biased
    toward the chosen birds' costs.
    """

    kept_hand = sorted(
        player.hand,
        key=lambda card: (card.food_cost.minimum_total, -card.victory_points, card.common_name),
    )[:STARTING_SELECTED_BIRD_COUNT]
    selected_food_count = BIRD_FOOD_SELECTION_TOTAL - len(kept_hand)
    return InitialSelection(
        player_id=player.player_id,
        kept_bird_names=[card.common_name for card in kept_hand],
        kept_bonus_card_names=[card.name for card in player.bonus_cards[:1]],
        starting_food=_preferred_starting_food(kept_hand)[:selected_food_count],
    )


def apply_default_initial_selection(player: PlayerState) -> tuple[list, list]:
    """Apply the default v1 setup choice to a player."""

    return apply_initial_selection_choice(player, choose_default_initial_selection(player))


def apply_initial_selection_choice(
    player: PlayerState,
    selection: InitialSelection,
) -> tuple[list, list]:
    """Apply one player's explicit setup choice and return discarded cards."""

    if selection.player_id != player.player_id:
        raise ValueError("initial selection player_id does not match player")
    if len(selection.kept_bird_names) + len(selection.starting_food) != BIRD_FOOD_SELECTION_TOTAL:
        raise ValueError("kept birds plus starting food must total five")
    if len(selection.kept_bonus_card_names) != 1:
        raise ValueError("initial selection must keep exactly one bonus card")

    hand_by_name = {card.common_name: card for card in player.hand}
    bonus_by_name = {card.name: card for card in player.bonus_cards}
    kept_hand = [_require_card(hand_by_name, name, "bird") for name in selection.kept_bird_names]
    kept_bonus_cards = [
        _require_card(bonus_by_name, name, "bonus") for name in selection.kept_bonus_card_names
    ]
    discarded_birds = [
        card for card in player.hand if card.common_name not in selection.kept_bird_names
    ]
    discarded_bonus_cards = [
        card for card in player.bonus_cards if card.name not in selection.kept_bonus_card_names
    ]

    for food_type in BASE_FOOD_TYPES:
        player.food_tokens[food_type] = 0
    for food_type in selection.starting_food:
        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1

    player.hand = kept_hand
    player.bonus_cards = kept_bonus_cards
    return discarded_birds, discarded_bonus_cards


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
    actions.extend(_legal_gain_food_actions(player, state))
    actions.extend(_legal_lay_eggs_actions(player))
    actions.extend(_legal_draw_cards_actions(player, state))
    return actions


def apply_action(state: GameState, action: LegalAction) -> GameState:
    """Apply one legal action and advance the turn pointer."""

    legal_actions = legal_actions_for_player(state, action.player_id)
    resolved_action = _resolve_legal_action(action, legal_actions)
    if resolved_action is None:
        raise ValueError(f"illegal action for {action.player_id}: {action.model_dump()}")
    action = resolved_action

    next_state = state.model_copy(deep=True)
    player = _get_player(next_state, action.player_id)

    if action.action_type == ActionType.PLAY_BIRD:
        _apply_play_bird(player, action, next_state)
    elif action.action_type == ActionType.GAIN_FOOD:
        _apply_gain_food(player, next_state, action)
    elif action.action_type == ActionType.LAY_EGGS:
        _apply_lay_eggs(player, next_state, action)
    elif action.action_type == ActionType.DRAW_CARDS:
        _apply_draw_cards(player, next_state, action)
    else:
        raise ValueError(f"unsupported action type: {action.action_type}")

    resolve_opponent_reaction_powers(next_state, action.player_id, action)
    _advance_turn(next_state)
    return next_state


def _resolve_legal_action(
    requested_action: LegalAction,
    legal_actions: list[LegalAction],
) -> LegalAction | None:
    if requested_action in legal_actions:
        return requested_action
    for legal_action in legal_actions:
        if _actions_are_compatible(requested_action, legal_action):
            return legal_action
    return None


def _actions_are_compatible(requested_action: LegalAction, legal_action: LegalAction) -> bool:
    if requested_action.action_type != legal_action.action_type:
        return False
    if requested_action.player_id != legal_action.player_id:
        return False
    if requested_action.action_type == ActionType.PLAY_BIRD:
        return (
            requested_action.bird_common_name == legal_action.bird_common_name
            and requested_action.habitat == legal_action.habitat
        )
    if requested_action.action_type == ActionType.GAIN_FOOD:
        requested_food_types = _action_food_types(requested_action)
        return requested_food_types == _action_food_types(legal_action)
    if requested_action.action_type == ActionType.LAY_EGGS:
        return requested_action.egg_count == legal_action.egg_count
    if requested_action.action_type == ActionType.DRAW_CARDS:
        requested_tray_indices = requested_action.tray_indices or (
            (requested_action.tray_index,) if requested_action.tray_index is not None else ()
        )
        legal_tray_indices = legal_action.tray_indices or (
            (legal_action.tray_index,) if legal_action.tray_index is not None else ()
        )
        requested_deck_count = requested_action.draw_from_deck_count or (
            1 if requested_action.draw_from_deck else 0
        )
        legal_deck_count = legal_action.draw_from_deck_count or (
            1 if legal_action.draw_from_deck else 0
        )
        return (
            requested_tray_indices == legal_tray_indices
            and requested_deck_count == legal_deck_count
        )
    return False


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
        bonus_points=_score_bonus_cards(player),
        round_goal_points=_score_round_goals(state, player),
        egg_points=egg_points,
        cached_food_points=cached_food_points,
        tucked_card_points=tucked_card_points,
    )


def _score_bonus_cards(player: PlayerState) -> int:
    points = 0
    for bonus_card in player.bonus_cards:
        bonus_name = bonus_card.name.split("[", maxsplit=1)[0].strip()
        played_slots = player.played_birds
        if bonus_name == "Bird Feeder":
            count = sum(
                1 for slot in played_slots if FoodType.SEED in slot.card.food_cost.fixed
            )
            points += 7 if count >= 8 else 3 if count >= 5 else 0
        elif bonus_name == "Backyard Birder":
            count = sum(1 for slot in played_slots if slot.card.victory_points < 4)
            points += 6 if count >= 7 else 3 if count >= 5 else 0
        elif bonus_name == "Bird Counter":
            points += 2 * sum(1 for slot in played_slots if slot.card.flocking)
        elif bonus_name == "Breeding Manager":
            points += sum(1 for slot in played_slots if slot.eggs >= 4)
        elif bonus_name == "Ecologist":
            points += 2 * min(len(player.habitats[habitat]) for habitat in Habitat)
        elif bonus_name == "Enclosure Builder":
            points += _tiered_count_points(_count_nest_type(played_slots, "ground"), 4, 4, 6, 7)
        elif bonus_name == "Falconer":
            points += 2 * sum(1 for slot in played_slots if slot.card.predator)
        elif bonus_name == "Fishery Manager":
            points += _tiered_count_points(
                _count_food_cost(played_slots, FoodType.FISH), 2, 3, 4, 8
            )
        elif bonus_name == "Food Web Expert":
            points += 2 * sum(
                1
                for slot in played_slots
                if slot.card.food_cost.fixed == {FoodType.INVERTEBRATE: 1}
            )
        elif bonus_name == "Forester":
            points += _tiered_count_points(
                _count_only_habitat(played_slots, Habitat.FOREST), 3, 4, 5, 8
            )
        elif bonus_name == "Large Bird Specialist":
            count = sum(
                1
                for slot in played_slots
                if slot.card.wingspan_cm is not None and slot.card.wingspan_cm > 65
            )
            points += _tiered_count_points(count, 4, 3, 6, 6)
        elif bonus_name == "Nest Box Builder":
            points += _tiered_count_points(_count_nest_type(played_slots, "cavity"), 4, 4, 6, 7)
        elif bonus_name == "Omnivore Expert":
            points += 2 * sum(1 for slot in played_slots if slot.card.food_cost.choice_food_count)
        elif bonus_name == "Oologist":
            count = sum(1 for slot in played_slots if slot.eggs >= 1)
            points += 6 if count >= 9 else 3 if count >= 7 else 0
        elif bonus_name == "Passerine Specialist":
            count = sum(
                1
                for slot in played_slots
                if slot.card.wingspan_cm is not None and slot.card.wingspan_cm <= 30
            )
            points += _tiered_count_points(count, 4, 3, 6, 6)
        elif bonus_name == "Platform Builder":
            points += _tiered_count_points(
                _count_nest_type(played_slots, "platform"), 4, 4, 6, 7
            )
        elif bonus_name == "Prairie Manager":
            points += _tiered_count_points(
                _count_only_habitat(played_slots, Habitat.GRASSLAND), 2, 3, 4, 8
            )
        elif bonus_name == "Rodentologist":
            points += 2 * _count_food_cost(played_slots, FoodType.RODENT)
        elif bonus_name == "Visionary Leader":
            points += 7 if len(player.hand) >= 8 else 4 if len(player.hand) >= 5 else 0
        elif bonus_name == "Viticulturalist":
            points += _tiered_count_points(
                _count_food_cost(played_slots, FoodType.FRUIT), 2, 3, 4, 7
            )
        elif bonus_name == "Wetland Scientist":
            points += _tiered_count_points(
                _count_only_habitat(played_slots, Habitat.WETLAND), 3, 3, 5, 7
            )
        elif bonus_name == "Wildlife Gardener":
            points += _tiered_count_points(_count_nest_type(played_slots, "bowl"), 4, 4, 6, 7)
        elif bonus_name in {"Cartographer", "Historian", "Photographer", "Anatomist"}:
            points += _score_name_based_bonus(bonus_name, played_slots)
    return points


def _tiered_count_points(
    count: int,
    low_threshold: int,
    low_points: int,
    high_threshold: int,
    high_points: int,
) -> int:
    if count >= high_threshold:
        return high_points
    if count >= low_threshold:
        return low_points
    return 0


def _count_food_cost(played_slots: list[BirdSlot], food_type: FoodType) -> int:
    return sum(1 for slot in played_slots if food_type in slot.card.food_cost.fixed)


def _count_nest_type(played_slots: list[BirdSlot], nest_type: str) -> int:
    return sum(
        1
        for slot in played_slots
        if slot.card.nest_type is not None
        and (slot.card.nest_type.value == nest_type or slot.card.nest_type.value == "wild")
    )


def _count_only_habitat(played_slots: list[BirdSlot], habitat: Habitat) -> int:
    return sum(1 for slot in played_slots if slot.card.habitats == {habitat})


def _score_name_based_bonus(bonus_name: str, played_slots: list[BirdSlot]) -> int:
    names = [slot.card.common_name.lower() for slot in played_slots]
    if bonus_name == "Photographer":
        count = sum(1 for name in names if any(color in name.split() for color in COLOR_WORDS))
        return _tiered_count_points(count, 4, 3, 6, 6)
    if bonus_name == "Cartographer":
        geography_terms = {
            "american",
            "atlantic",
            "baltimore",
            "california",
            "carolina",
            "eastern",
            "great",
            "kentucky",
            "mexican",
            "mississippi",
            "northern",
            "western",
        }
        count = sum(1 for name in names if any(term in name.split() for term in geography_terms))
        return _tiered_count_points(count, 2, 3, 4, 7)
    if bonus_name == "Historian":
        person_markers = {"baird's", "bell's", "bewick's", "clark's", "say's", "wilson's"}
        return 2 * sum(1 for name in names if any(marker in name for marker in person_markers))
    if bonus_name == "Anatomist":
        body_terms = {
            "back",
            "beak",
            "bellied",
            "bill",
            "billed",
            "breasted",
            "crowned",
            "head",
            "headed",
            "necked",
            "throated",
            "winged",
        }
        count = sum(
            1
            for name in names
            if any(term in name.replace("-", " ").split() for term in body_terms)
        )
        return _tiered_count_points(count, 2, 3, 4, 6)
    return 0


def _score_round_goals(state: GameState, player: PlayerState) -> int:
    if state.round_state.game_over or player.round_goal_points > 0:
        return player.round_goal_points

    points = 0
    for goal in state.round_goals:
        count = _count_round_goal_items(goal.name.lower(), player)
        if count <= 0 or not goal.scoring_values:
            continue
        scoring_key = min(count, max(goal.scoring_values))
        points += goal.scoring_values.get(scoring_key, 0)
    return points


def _count_round_goal_items(goal_name: str, player: PlayerState) -> int:
    if "[bird]" in goal_name and "[forest]" in goal_name:
        return len(player.habitats[Habitat.FOREST])
    if "[bird]" in goal_name and "[grassland]" in goal_name:
        return len(player.habitats[Habitat.GRASSLAND])
    if "[bird]" in goal_name and "[wetland]" in goal_name:
        return len(player.habitats[Habitat.WETLAND])
    for nest_type in ("bowl", "cavity", "ground", "platform"):
        if f"[{nest_type}]" in goal_name and "[bird]" in goal_name and "[egg]" in goal_name:
            return sum(
                1
                for slot in player.played_birds
                if slot.eggs > 0
                and slot.card.nest_type is not None
                and (
                    slot.card.nest_type.value == nest_type
                    or slot.card.nest_type.value == "wild"
                )
            )
        if f"[{nest_type}]" in goal_name and "[egg]" in goal_name:
            return sum(
                slot.eggs
                for slot in player.played_birds
                if slot.card.nest_type is not None
                and (
                    slot.card.nest_type.value == nest_type
                    or slot.card.nest_type.value == "wild"
                )
            )
    if "[egg]" in goal_name and "forest" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.FOREST])
    if "[egg]" in goal_name and "grassland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.GRASSLAND])
    if "[egg]" in goal_name and "wetland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.WETLAND])
    if "[bird]" in goal_name:
        return len(player.played_birds)
    if "sets of" in goal_name and "[egg]" in goal_name:
        return min(
            sum(slot.eggs for slot in player.habitats[Habitat.FOREST]),
            sum(slot.eggs for slot in player.habitats[Habitat.GRASSLAND]),
            sum(slot.eggs for slot in player.habitats[Habitat.WETLAND]),
        )
    return 0


def score_round_goal_competitive(
    state: GameState,
    goal_index: int,
) -> dict[str, int]:
    """Score one end-of-round goal with the competitive green-side method."""

    if goal_index < 0 or goal_index >= len(state.round_goals):
        return {player.player_id: 0 for player in state.players}

    goal = state.round_goals[goal_index]
    goal_name = goal.name.lower()
    counts = {
        player.player_id: _count_round_goal_items(goal_name, player) for player in state.players
    }
    scores = {player.player_id: 0 for player in state.players}
    positive_counts = sorted({count for count in counts.values() if count > 0}, reverse=True)
    placement_scores = ROUND_GOAL_GREEN_SCORES.get(goal_index + 1, ROUND_GOAL_GREEN_SCORES[4])
    rank_index = 0
    for count in positive_counts:
        tied_player_ids = [
            player_id for player_id, player_count in counts.items() if player_count == count
        ]
        if rank_index >= len(placement_scores):
            break
        tied_slots = placement_scores[rank_index : rank_index + len(tied_player_ids)]
        tied_score = sum(tied_slots) // len(tied_player_ids) if tied_slots else 0
        for player_id in tied_player_ids:
            scores[player_id] = tied_score
        rank_index += len(tied_player_ids)
    return scores


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


def _legal_gain_food_actions(player: PlayerState, state: GameState) -> list[LegalAction]:
    food_count = _forest_food_count(len(player.habitats[Habitat.FOREST]))
    actions: list[LegalAction] = []
    for reroll_birdfeeder, dice in _available_birdfeeder_rolls(state, food_count):
        for food_types in _food_choice_tuples(dice, food_count):
            actions.append(
                LegalAction(
                    action_type=ActionType.GAIN_FOOD,
                    player_id=player.player_id,
                    food_type=food_types[0] if len(food_types) == 1 else None,
                    food_types=food_types,
                    reroll_birdfeeder=reroll_birdfeeder,
                )
            )

    if _can_spend_card_for_extra_food(player) and actions:
        discard_card_name = _choose_discard_card_for_food(player)
        extra_actions = []
        for reroll_birdfeeder, dice in _available_birdfeeder_rolls(state, food_count + 1):
            for food_types in _food_choice_tuples(dice, food_count + 1):
                extra_actions.append(
                    LegalAction(
                        action_type=ActionType.GAIN_FOOD,
                        player_id=player.player_id,
                        food_type=food_types[0] if len(food_types) == 1 else None,
                        food_types=food_types,
                        reroll_birdfeeder=reroll_birdfeeder,
                        discard_card_common_name=discard_card_name,
                        spend_card_for_extra_food=True,
                    )
                )
        actions.extend(extra_actions)
    return actions


def _legal_lay_eggs_actions(player: PlayerState) -> list[LegalAction]:
    if player.available_egg_capacity <= 0 or not player.played_birds:
        return []
    egg_count = min(
        _grassland_egg_count(len(player.habitats[Habitat.GRASSLAND])),
        player.available_egg_capacity,
    )
    actions = [
        LegalAction(
            action_type=ActionType.LAY_EGGS,
            player_id=player.player_id,
            egg_count=egg_count,
        )
    ]
    if _can_spend_food_for_extra_egg(player):
        for food_type in BASE_FOOD_TYPES:
            if player.food_tokens.get(food_type, 0) > 0:
                actions.append(
                    LegalAction(
                        action_type=ActionType.LAY_EGGS,
                        player_id=player.player_id,
                        egg_count=min(egg_count + 1, player.available_egg_capacity),
                        spend_food_for_extra_egg=food_type,
                    )
                )
    return actions


def _legal_draw_cards_actions(player: PlayerState, state: GameState) -> list[LegalAction]:
    draw_count = _wetland_card_count(len(player.habitats[Habitat.WETLAND]))
    actions = []
    for tray_indices, deck_count in _card_draw_choices(state, draw_count):
        actions.append(
            LegalAction(
                action_type=ActionType.DRAW_CARDS,
                player_id=player.player_id,
                tray_index=tray_indices[0] if len(tray_indices) == 1 and deck_count == 0 else None,
                tray_indices=tray_indices,
                draw_from_deck=deck_count > 0 and not tray_indices,
                draw_from_deck_count=deck_count,
            )
        )
    if _can_spend_egg_for_extra_card(player) and actions:
        for tray_indices, deck_count in _card_draw_choices(state, draw_count + 1):
            actions.append(
                LegalAction(
                    action_type=ActionType.DRAW_CARDS,
                    player_id=player.player_id,
                    tray_index=(
                        tray_indices[0] if len(tray_indices) == 1 and deck_count == 0 else None
                    ),
                    tray_indices=tray_indices,
                    draw_from_deck=deck_count > 0 and not tray_indices,
                    draw_from_deck_count=deck_count,
                    spend_egg_for_extra_card=True,
                )
            )
    return actions


def _apply_play_bird(player: PlayerState, action: LegalAction, state: GameState) -> None:
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
    played_slot = BirdSlot(card=card)
    player.habitats[action.habitat].append(played_slot)
    resolve_played_bird_power(player, played_slot, state)


def _apply_gain_food(player: PlayerState, state: GameState, action: LegalAction) -> None:
    food_types = _action_food_types(action)
    if not food_types:
        raise ValueError("gain food action requires at least one food choice")
    if action.spend_card_for_extra_food:
        _discard_card_for_action(player, action.discard_card_common_name)
    if action.reroll_birdfeeder or not state.birdfeeder.dice:
        state.birdfeeder.dice = _roll_birdfeeder_for_state(
            state,
            f"legal_{len(food_types)}",
            player_id=player.player_id,
            action_type=action.action_type.value,
            record=True,
        )
    for food_type in food_types:
        if food_type not in state.birdfeeder.dice and _can_reroll_birdfeeder(state.birdfeeder):
            state.birdfeeder.dice = _roll_birdfeeder_for_state(
                state,
                f"gain_food_action_{food_type}",
                player_id=player.player_id,
                action_type=action.action_type.value,
                record=True,
            )
        if food_type not in state.birdfeeder.dice:
            raise ValueError(f"selected food is not available in the birdfeeder: {food_type}")
        die_index = state.birdfeeder.dice.index(food_type)
        state.birdfeeder.dice.pop(die_index)
        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1
    resolve_habitat_powers(player, Habitat.FOREST, state)


def _apply_lay_eggs(player: PlayerState, state: GameState, action: LegalAction) -> None:
    if action.spend_food_for_extra_egg is not None:
        food_type = action.spend_food_for_extra_egg
        if player.food_tokens.get(food_type, 0) <= 0:
            raise ValueError(f"cannot spend unavailable food for extra egg: {food_type}")
        player.food_tokens[food_type] -= 1
    eggs_to_place = action.egg_count or 0
    for habitat in Habitat:
        for slot in player.habitats[habitat]:
            if eggs_to_place <= 0:
                resolve_habitat_powers(player, Habitat.GRASSLAND, state)
                return
            added_eggs = min(slot.available_egg_capacity, eggs_to_place)
            slot.eggs += added_eggs
            eggs_to_place -= added_eggs
    resolve_habitat_powers(player, Habitat.GRASSLAND, state)


def _apply_draw_cards(player: PlayerState, state: GameState, action: LegalAction) -> None:
    if action.spend_egg_for_extra_card:
        _spend_eggs(player, 1)
    tray_indices = action.tray_indices or (
        (action.tray_index,) if action.tray_index is not None else ()
    )
    deck_count = action.draw_from_deck_count or (1 if action.draw_from_deck else 0)
    if not tray_indices and deck_count <= 0:
        raise ValueError("draw cards action requires tray_indices or draw_from_deck_count")

    for tray_index in sorted(tray_indices, reverse=True):
        player.hand.append(state.bird_tray.pop(tray_index))
        if state.decks.bird_deck:
            replacement_card = state.decks.bird_deck.pop(0)
            _record_deck_draw(
                state,
                player.player_id,
                "bird_tray_replenish",
                [replacement_card.common_name],
            )
            state.bird_tray.insert(tray_index, replacement_card)
    drawn_from_deck = []
    for _index in range(deck_count):
        if state.decks.bird_deck:
            drawn_card = state.decks.bird_deck.pop(0)
            player.hand.append(drawn_card)
            drawn_from_deck.append(drawn_card.common_name)
    if drawn_from_deck:
        _record_deck_draw(
            state,
            player.player_id,
            "draw_cards_from_deck",
            drawn_from_deck,
        )
    resolve_habitat_powers(player, Habitat.WETLAND, state)


def resolve_played_bird_power(
    player: PlayerState,
    slot: BirdSlot,
    state: GameState | None = None,
) -> None:
    """Resolve a narrow set of implemented white powers when a bird is played."""

    if slot.card.power.color.value != "white":
        return
    _resolve_power_text(player, slot, slot.card.power.text, state)


def resolve_habitat_powers(
    player: PlayerState,
    habitat: Habitat,
    state: GameState | None = None,
) -> None:
    """Resolve a narrow set of implemented brown powers in habitat order."""

    for slot in reversed(player.habitats[habitat]):
        if slot.card.power.color.value != "brown":
            continue
        _resolve_power_text(player, slot, slot.card.power.text, state)


def _resolve_power_text(
    player: PlayerState,
    slot: BirdSlot,
    power_text: str | None,
    state: GameState | None = None,
) -> None:
    if not power_text:
        return
    handler_key = slot.card.power.handler_key or classify_power_handler_key(
        power_text,
        slot.card.power.color,
    )
    if handler_key == "tuck_card":
        _resolve_tuck_card_power(player, slot, power_text, state)
        return
    if handler_key == "cache_food":
        slot.cached_food += 1
        return
    if handler_key == "predator_hunt":
        _resolve_predator_hunt_power(player, slot, state)
        return
    if handler_key == "discard_egg_gain_wild_food":
        _resolve_discard_egg_gain_wild_food_power(player, state)
        return
    if handler_key == "discard_to_tuck":
        _resolve_discard_to_tuck_power(player, slot, power_text, state)
        return
    if handler_key == "draw_card":
        _draw_cards_from_deck(player, state, 1)
        return
    if handler_key == "lay_egg":
        _place_eggs_on_player_birds(player, 1)
        return
    if handler_key == "gain_food_from_birdfeeder" and state is not None:
        _gain_preferred_food_from_birdfeeder(player, state)
        return
    if handler_key == "gain_food_from_supply":
        _resolve_gain_food_from_supply_power(player, power_text)
        return
    if handler_key == "all_players_gain_food" and state is not None:
        _resolve_all_players_gain_food_power(state, power_text)
        return
    if handler_key == "all_players_lay_eggs" and state is not None:
        for candidate in state.players:
            _place_eggs_on_player_birds(candidate, 1)
        return
    if handler_key == "deck_search_tuck_by_wingspan":
        _resolve_deck_search_tuck_by_wingspan_power(player, slot, power_text, state)
        return

    lowered = power_text.lower()
    for food_type in BASE_FOOD_TYPES:
        token = f"gain 1 [{_food_power_token(food_type)}]"
        if token in lowered:
            if lowered.startswith("all players") and state is not None:
                for candidate in state.players:
                    candidate.food_tokens[food_type] = (
                        candidate.food_tokens.get(food_type, 0) + 1
                    )
                return
            if "birdfeeder" in lowered and state is not None:
                _gain_food_from_birdfeeder(player, state, food_type)
            else:
                player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1
            return

    if "draw 1 [card]" in lowered:
        _draw_cards_from_deck(player, state, 1)
        return

    if "lay 1 [egg]" in lowered:
        _place_eggs_on_player_birds(player, 1)


def _resolve_tuck_card_power(
    player: PlayerState,
    slot: BirdSlot,
    power_text: str,
    state: GameState | None,
) -> None:
    if not player.hand:
        return
    _discard_card_for_action(player, _choose_discard_card_for_food(player))
    slot.tucked_cards += 1
    lowered = power_text.lower()
    if "draw 1 [card]" in lowered:
        _draw_cards_from_deck(player, state, 1)
    if "lay 1 [egg]" in lowered:
        _place_eggs_on_player_birds(player, 1, preferred_slot=slot)


def _resolve_predator_hunt_power(
    player: PlayerState,
    slot: BirdSlot,
    state: GameState | None,
) -> None:
    if state is None:
        return
    dice = _roll_birdfeeder_for_state(
        state,
        f"predator_hunt_{player.player_id}_{slot.card.common_name}",
        draw_type="predator_hunt",
        player_id=player.player_id,
        action_type="bird_power",
        record=True,
    )
    target_food = FoodType.RODENT if FoodType.RODENT in dice else FoodType.FISH
    if target_food in dice:
        slot.cached_food += 1


def _resolve_discard_egg_gain_wild_food_power(
    player: PlayerState,
    state: GameState | None,
) -> None:
    if player.total_eggs <= 0:
        return
    _spend_eggs(player, 1)
    preferred_food = _preferred_food_for_hand(player)[0]
    player.food_tokens[preferred_food] = player.food_tokens.get(preferred_food, 0) + 1


def _resolve_discard_to_tuck_power(
    player: PlayerState,
    slot: BirdSlot,
    power_text: str,
    state: GameState | None,
) -> None:
    lowered = power_text.lower()
    food_match = re.search(r"discard 1 \[(invertebrate|seed|fish|fruit|rodent)\]", lowered)
    if food_match is None or state is None:
        return
    food_type = _food_type_from_power_token(food_match.group(1))
    if player.food_tokens.get(food_type, 0) <= 0:
        return
    player.food_tokens[food_type] -= 1
    tuck_count_match = re.search(r"tuck (\d+) \[card\]", lowered)
    tuck_count = int(tuck_count_match.group(1)) if tuck_count_match else 1
    actual_tucks = min(tuck_count, len(state.decks.bird_deck))
    tucked_cards = state.decks.bird_deck[:actual_tucks]
    _record_deck_draw(
        state,
        player.player_id,
        "bird_power_tuck_from_deck",
        [card.common_name for card in tucked_cards],
    )
    del state.decks.bird_deck[:actual_tucks]
    slot.tucked_cards += actual_tucks


def _resolve_gain_food_from_supply_power(player: PlayerState, power_text: str) -> None:
    lowered = power_text.lower()
    for food_type in BASE_FOOD_TYPES:
        if f"gain 1 [{_food_power_token(food_type)}]" in lowered:
            player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1
            return
    if "gain 1 [wild]" in lowered:
        preferred_food = _preferred_food_for_hand(player)[0]
        player.food_tokens[preferred_food] = player.food_tokens.get(preferred_food, 0) + 1


def _resolve_all_players_gain_food_power(state: GameState, power_text: str) -> None:
    lowered = power_text.lower()
    for food_type in BASE_FOOD_TYPES:
        if f"gain 1 [{_food_power_token(food_type)}]" in lowered:
            for candidate in state.players:
                candidate.food_tokens[food_type] = candidate.food_tokens.get(food_type, 0) + 1
            return


def _resolve_deck_search_tuck_by_wingspan_power(
    player: PlayerState,
    slot: BirdSlot,
    power_text: str,
    state: GameState | None,
) -> None:
    if state is None or not state.decks.bird_deck:
        return
    revealed_card = state.decks.bird_deck.pop(0)
    _record_deck_draw(
        state,
        player.player_id,
        "bird_power_deck_search",
        [revealed_card.common_name],
    )
    threshold_match = re.search(r"less than (\d+)cm", power_text.lower())
    threshold = int(threshold_match.group(1)) if threshold_match else 100
    if revealed_card.wingspan_cm is not None and revealed_card.wingspan_cm < threshold:
        slot.tucked_cards += 1
    else:
        state.decks.bird_discard.append(revealed_card)


def resolve_opponent_reaction_powers(
    state: GameState,
    acting_player_id: str,
    action: LegalAction,
) -> None:
    """Resolve a small deterministic slice of pink powers after another player's action."""

    for player in state.players:
        if player.player_id == acting_player_id:
            continue
        for slot in player.played_birds:
            if slot.card.power.color.value != "pink" or not slot.card.power.text:
                continue
            lowered = slot.card.power.text.lower()
            if action.action_type == ActionType.LAY_EGGS and "takes the" in lowered:
                nest_match = re.search(r"\[(bowl|cavity|ground|platform)\] nest", lowered)
                _place_eggs_on_player_birds(
                    player,
                    1,
                    nest_type=nest_match.group(1) if nest_match else None,
                )
            elif action.action_type == ActionType.GAIN_FOOD:
                if "gain 1 [die] from the birdfeeder" in lowered:
                    _gain_preferred_food_from_birdfeeder(player, state)
                if "[rodent]" in lowered and FoodType.RODENT in _action_food_types(action):
                    slot.cached_food += 1
            elif (
                action.action_type == ActionType.PLAY_BIRD
                and action.habitat is not None
                and action.habitat.value in lowered
            ):
                for food_type in BASE_FOOD_TYPES:
                    if f"gain 1 [{_food_power_token(food_type)}]" in lowered:
                        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1
                if "tuck 1 [card]" in lowered and player.hand:
                    _discard_card_for_action(player, _choose_discard_card_for_food(player))
                    slot.tucked_cards += 1


def _forest_food_count(forest_bird_count: int) -> int:
    if forest_bird_count >= 4:
        return 3
    if forest_bird_count >= 2:
        return 2
    return 1


def _grassland_egg_count(grassland_bird_count: int) -> int:
    if grassland_bird_count >= 4:
        return 4
    if grassland_bird_count >= 2:
        return 3
    return 2


def _wetland_card_count(wetland_bird_count: int) -> int:
    if wetland_bird_count >= 4:
        return 3
    if wetland_bird_count >= 2:
        return 2
    return 1


def _can_spend_card_for_extra_food(player: PlayerState) -> bool:
    forest_count = len(player.habitats[Habitat.FOREST])
    return forest_count in {1, 3} and bool(player.hand)


def _can_spend_food_for_extra_egg(player: PlayerState) -> bool:
    grassland_count = len(player.habitats[Habitat.GRASSLAND])
    return grassland_count in {1, 3} and any(
        player.food_tokens.get(food, 0) > 0 for food in BASE_FOOD_TYPES
    )


def _can_spend_egg_for_extra_card(player: PlayerState) -> bool:
    wetland_count = len(player.habitats[Habitat.WETLAND])
    return wetland_count in {1, 3} and player.total_eggs > 0


def _available_birdfeeder_rolls(
    state: GameState,
    food_count: int,
) -> list[tuple[bool, list[FoodType]]]:
    if food_count <= 0:
        return []
    options: list[tuple[bool, list[FoodType]]] = []
    if state.birdfeeder.dice:
        options.append((False, list(state.birdfeeder.dice)))
    if (
        not state.birdfeeder.dice
        or _can_reroll_birdfeeder(state.birdfeeder)
        or len(state.birdfeeder.dice) < food_count
    ):
        options.append((True, _roll_birdfeeder_for_state(state, f"legal_{food_count}")))
    return options


def _food_choice_tuples(
    dice: list[FoodType],
    food_count: int,
) -> list[tuple[FoodType, ...]]:
    if food_count <= 0:
        return [()]
    dice_counts = Counter(dice)
    choices: set[tuple[FoodType, ...]] = set()
    for combo in combinations_with_replacement(BASE_FOOD_TYPES, food_count):
        combo_counts = Counter(combo)
        if all(combo_counts[food] <= dice_counts.get(food, 0) for food in combo_counts):
            choices.add(tuple(sorted(combo, key=BASE_FOOD_TYPES.index)))
    return sorted(choices, key=lambda option: tuple(BASE_FOOD_TYPES.index(food) for food in option))


def _card_draw_choices(state: GameState, draw_count: int) -> list[tuple[tuple[int, ...], int]]:
    if draw_count <= 0:
        return []
    choices: set[tuple[tuple[int, ...], int]] = set()
    tray_indices = tuple(range(len(state.bird_tray)))
    max_tray_draws = min(len(tray_indices), draw_count)
    for tray_draw_count in range(max_tray_draws + 1):
        deck_count = draw_count - tray_draw_count
        if deck_count > len(state.decks.bird_deck):
            continue
        if tray_draw_count == 0:
            choices.add(((), deck_count))
            continue
        for indices in combinations_with_replacement(tray_indices, tray_draw_count):
            if len(set(indices)) == len(indices):
                choices.add((tuple(sorted(indices)), deck_count))
    return sorted(choices, key=lambda item: (item[1], item[0]))


def _action_food_types(action: LegalAction) -> tuple[FoodType, ...]:
    if action.food_types:
        return action.food_types
    if action.food_type is not None:
        return (action.food_type,)
    return ()


def _can_reroll_birdfeeder(birdfeeder: BirdfeederState) -> bool:
    return len(set(birdfeeder.dice)) <= 1


def _roll_birdfeeder_for_state(
    state: GameState,
    salt: str,
    *,
    draw_type: str = "birdfeeder_reroll",
    player_id: str | None = None,
    action_type: str | None = None,
    record: bool = False,
) -> list[FoodType]:
    seed = f"{state.random_seed}:{state.game_id}:{state.round_state.global_turn_number}:{salt}"
    result = _roll_birdfeeder(random.Random(seed))
    if record:
        state.rng_draw_records.append(
            RngDrawRecord(
                draw_type=draw_type,
                seed_material=seed,
                result=list(result),
                round_number=state.round_state.round_number,
                turn_number=state.round_state.turn_number,
                round_action_number=state.round_state.round_action_number,
                global_turn_number=state.round_state.global_turn_number,
                player_id=player_id,
                action_type=action_type,
            )
        )
    return result


def _choose_discard_card_for_food(player: PlayerState) -> str:
    card = min(player.hand, key=lambda card: (card.victory_points, -card.food_cost.minimum_total))
    return card.common_name


def _discard_card_for_action(player: PlayerState, card_name: str | None) -> None:
    if not player.hand:
        return
    resolved_card_name = card_name or _choose_discard_card_for_food(player)
    for index, card in enumerate(player.hand):
        if card.common_name == resolved_card_name:
            player.hand.pop(index)
            return
    raise ValueError(f"cannot discard card not in hand: {resolved_card_name}")


def _draw_cards_from_deck(player: PlayerState, state: GameState | None, count: int) -> None:
    if state is None:
        return
    drawn_cards = []
    for _index in range(count):
        if state.decks.bird_deck:
            drawn_card = state.decks.bird_deck.pop(0)
            player.hand.append(drawn_card)
            drawn_cards.append(drawn_card.common_name)
    if drawn_cards:
        _record_deck_draw(state, player.player_id, "bird_power_draw_cards", drawn_cards)


def _record_deck_draw(
    state: GameState,
    player_id: str | None,
    draw_type: str,
    card_names: list[str],
) -> None:
    state.rng_draw_records.append(
        RngDrawRecord(
            draw_type=draw_type,
            seed_material=f"{state.random_seed}:{state.game_id}:deck_order",
            result=card_names,
            round_number=state.round_state.round_number,
            turn_number=state.round_state.turn_number,
            round_action_number=state.round_state.round_action_number,
            global_turn_number=state.round_state.global_turn_number,
            player_id=player_id,
            action_type="draw_cards",
        )
    )


def _place_eggs_on_player_birds(
    player: PlayerState,
    count: int,
    *,
    nest_type: str | None = None,
    preferred_slot: BirdSlot | None = None,
) -> int:
    placed = 0
    candidate_slots = player.played_birds
    if preferred_slot is not None:
        candidate_slots = [preferred_slot] + [
            slot for slot in candidate_slots if slot is not preferred_slot
        ]
    for slot in candidate_slots:
        if placed >= count:
            return placed
        if nest_type is not None and (
            slot.card.nest_type is None
            or slot.card.nest_type.value not in {nest_type, "wild"}
        ):
            continue
        if slot.available_egg_capacity <= 0:
            continue
        slot.eggs += 1
        placed += 1
    return placed


def _gain_preferred_food_from_birdfeeder(player: PlayerState, state: GameState) -> FoodType | None:
    preferred_foods = _preferred_food_for_hand(player)
    if not state.birdfeeder.dice or _can_reroll_birdfeeder(state.birdfeeder):
        state.birdfeeder.dice = _roll_birdfeeder_for_state(
            state,
            f"reaction_{player.player_id}",
            draw_type="pink_reaction_birdfeeder",
            player_id=player.player_id,
            action_type="bird_power",
            record=True,
        )
    for food_type in preferred_foods:
        if food_type in state.birdfeeder.dice:
            _gain_food_from_birdfeeder(player, state, food_type)
            return food_type
    if state.birdfeeder.dice:
        food_type = state.birdfeeder.dice[0]
        _gain_food_from_birdfeeder(player, state, food_type)
        return food_type
    return None


def _gain_food_from_birdfeeder(
    player: PlayerState,
    state: GameState,
    food_type: FoodType,
) -> None:
    if food_type not in state.birdfeeder.dice:
        return
    state.birdfeeder.dice.pop(state.birdfeeder.dice.index(food_type))
    player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + 1


def _preferred_food_for_hand(player: PlayerState) -> list[FoodType]:
    deficits: Counter[FoodType] = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            if food_type in BASE_FOOD_TYPES:
                deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    ordered = [
        food_type
        for food_type, _count in deficits.most_common()
        if food_type in BASE_FOOD_TYPES
    ]
    ordered.extend(food_type for food_type in BASE_FOOD_TYPES if food_type not in ordered)
    return ordered


def _advance_turn(state: GameState) -> None:
    player = state.active_player
    player.action_cubes_available -= 1

    if all(candidate.action_cubes_available == 0 for candidate in state.players):
        _score_completed_round_goal(state)
        _refresh_bird_tray(state)
        if state.round_state.round_number == 4:
            state.round_state.game_over = True
            return
        completed_round = state.round_state.round_number
        state.round_state.round_number += 1
        cubes_for_round = BASE_ACTION_CUBES_BY_ROUND[state.round_state.round_number]
        for candidate in state.players:
            candidate.action_cubes_available = cubes_for_round
        state.round_state.active_player_index = completed_round % len(state.players)
        state.round_state.turn_number = 1
        state.round_state.round_action_number = 1
        state.round_state.global_turn_number += 1
        return

    next_index = (state.round_state.active_player_index + 1) % len(state.players)
    while state.players[next_index].action_cubes_available == 0:
        next_index = (next_index + 1) % len(state.players)
    state.round_state.active_player_index = next_index
    next_player = state.players[next_index]
    action_cubes_for_round = BASE_ACTION_CUBES_BY_ROUND[state.round_state.round_number]
    state.round_state.turn_number = action_cubes_for_round - next_player.action_cubes_available + 1
    state.round_state.round_action_number += 1
    state.round_state.global_turn_number += 1


def _score_completed_round_goal(state: GameState) -> None:
    goal_index = state.round_state.round_number - 1
    scores = score_round_goal_competitive(state, goal_index)
    for player in state.players:
        player.round_goal_points += scores.get(player.player_id, 0)


def _refresh_bird_tray(state: GameState) -> None:
    state.decks.bird_discard.extend(state.bird_tray)
    state.bird_tray = _draw_many(state.decks.bird_deck, BIRD_TRAY_SIZE)
    if state.bird_tray:
        _record_deck_draw(
            state,
            None,
            "round_end_bird_tray_refresh",
            [card.common_name for card in state.bird_tray],
        )


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


def _preferred_starting_food(hand: list) -> list[FoodType]:
    preferred: list[FoodType] = []
    for card in hand:
        for food_type, count in card.food_cost.fixed.items():
            if food_type in BASE_FOOD_TYPES:
                preferred.extend([food_type] * count)

    for food_type in BASE_FOOD_TYPES:
        if food_type not in preferred:
            preferred.append(food_type)
    return preferred


def _food_power_token(food_type: FoodType) -> str:
    if food_type == FoodType.INVERTEBRATE:
        return "invertebrate"
    return food_type.value


def _food_type_from_power_token(token: str) -> FoodType:
    if token == "invertebrate":
        return FoodType.INVERTEBRATE
    return FoodType(token)


def _require_card(cards_by_name: dict, name: str, card_type: str):
    try:
        return cards_by_name[name]
    except KeyError as error:
        raise ValueError(f"unknown {card_type} card in initial selection: {name}") from error


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
