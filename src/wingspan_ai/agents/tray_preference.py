"""Shared valuation for *which* face-up tray card an agent should take.

Why this exists
---------------
The rules engine enumerates every tray card as its own `LegalAction`, so the
choice has always been expressible. But seven of nine agents scored every draw
identically — `GreedyBaselineAgent` because a draw yields no immediate points, and
every strategy archetype because it applied a flat family bonus. Measured across
30 seeded openings, those agents were indifferent in 100% of states while the
tray options differed by a mean of 3.0 victory points. With all options tied they
took whichever action was enumerated first, which is always tray index 0.

This module gives them a reason to prefer one card over another, using only the
acting player's own information: their board, their hand, their food, their bonus
cards, and the public tray.
"""

from __future__ import annotations

from wingspan_ai.agents.feeder_odds import affordability_outlook
from wingspan_ai.content.schemas import BirdCard, FoodCost, FoodType, Habitat, PowerColor
from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import habitat_action_yield
from wingspan_ai.state.models import GameState, PlayerState

MAX_HABITAT_SLOTS = 5


def drawn_tray_cards(state: GameState, action: LegalAction) -> list[BirdCard]:
    """Return the face-up cards a draw action actually takes.

    Deck draws are excluded: their identity is unknown at decision time, so an
    agent cannot prefer one over another.
    """

    indices = action.tray_indices or (
        (action.tray_index,) if action.tray_index is not None else ()
    )
    return [
        state.bird_tray[index]
        for index in indices
        if index is not None and 0 <= index < len(state.bird_tray)
    ]


def can_afford(player: PlayerState, food_cost: FoodCost) -> bool:
    """Whether the player could pay a card's food cost right now."""

    remaining = dict(player.food_tokens)
    for food_type, count in food_cost.fixed.items():
        if remaining.get(food_type, 0) < count:
            return False
        remaining[food_type] = remaining.get(food_type, 0) - count
    flexible = food_cost.wild_food_count + food_cost.choice_food_count
    return sum(remaining.values()) >= flexible


def has_habitat_room(player: PlayerState, card: BirdCard) -> bool:
    return any(
        len(player.habitats[habitat]) < MAX_HABITAT_SLOTS for habitat in card.habitats
    )


def base_card_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    """Generic usefulness of a card to this player, ignoring strategy flavour.

    Returns 0 for a card the player has nowhere to play, since an unplayable
    card is worth no more than an unknown deck draw.

    `state` is optional so this stays usable where no game state is at hand; it
    only sharpens the affordability term.
    """

    if not has_habitat_room(player, card):
        return 0.0

    value = card.victory_points * 0.30
    value += card.egg_limit * 0.20

    if can_afford(player, card.food_cost):
        value += 1.00
    elif state is not None:
        # How likely the feeder is to cover what is missing, given the dice
        # showing and how many the player's forest row lets them take. The
        # fallback below treats every missing food as equally hard to find,
        # which is wrong by a factor of two between seed and fish.
        draws = habitat_action_yield(Habitat.FOREST, len(player.habitats[Habitat.FOREST]))
        value += affordability_outlook(state, player, card, draws)
    else:
        # Partial credit: the shortfall may be gained before the card is played.
        shortfall = max(card.food_cost.minimum_total - sum(player.food_tokens.values()), 1)
        value += 1.00 / (1 + shortfall)

    # A brown power repeats on every habitat activation; the rest fire once.
    if card.power.color == PowerColor.BROWN:
        value += 1.00
    elif card.power.color != PowerColor.NONE:
        value += 0.50
    return value


def _power_text(card: BirdCard) -> str:
    return (card.power.text or "").lower()


def _bonus_name(name: str) -> str:
    return name.split("[", maxsplit=1)[0].strip()


def egg_focus_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    return base_card_affinity(card, player, state) + card.egg_limit * 0.60


def engine_builder_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    value = base_card_affinity(card, player, state)
    if card.power.color == PowerColor.BROWN:
        value += 1.50
    # Deepening an existing habitat compounds activations.
    best_depth = max(
        (
            len(player.habitats[habitat])
            for habitat in card.habitats
            if len(player.habitats[habitat]) < MAX_HABITAT_SLOTS
        ),
        default=0,
    )
    return value + best_depth * 0.30


def food_acceleration_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    value = base_card_affinity(card, player, state)
    text = _power_text(card)
    if "gain" in text and any(f"[{food.value}]" in text for food in FoodType):
        value += 1.50
    if "[die]" in text or "birdfeeder" in text:
        value += 1.00
    # Cheap birds convert a food surplus into board presence fastest.
    return value + max(0.0, 3.0 - card.food_cost.minimum_total) * 0.30


def card_draw_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    value = base_card_affinity(card, player, state)
    text = _power_text(card)
    if "draw" in text and "[card]" in text:
        value += 1.50
    if "tuck" in text:
        value += 0.75
    return value


def bonus_card_focus_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState | None = None,
) -> float:
    """Prefer cards satisfying the bonus cards this player actually holds."""

    value = base_card_affinity(card, player, state)
    held = {_bonus_name(bonus.name) for bonus in player.bonus_cards}
    matches = len(held & {_bonus_name(tag) for tag in card.bonus_card_tags})
    value += 2.50 * matches
    if card.bonus_card_power:
        value += 1.00
    return value


def round_goal_chase_affinity(
    card: BirdCard,
    player: PlayerState,
    state: GameState,
) -> float:
    """Prefer cards advancing the current end-of-round goal."""

    value = base_card_affinity(card, player, state)
    goal_index = min(state.round_state.round_number - 1, len(state.round_goals) - 1)
    if goal_index < 0:
        return value
    goal_text = state.round_goals[goal_index].name.lower()

    for habitat in card.habitats:
        if f"[{habitat.value}]" in goal_text:
            value += 2.00
            break
    if "[egg]" in goal_text:
        value += card.egg_limit * 0.40
        if card.nest_type is not None and f"[{card.nest_type.value}]" in goal_text:
            value += 1.50
    elif "[bird]" in goal_text:
        value += 0.50
    return value


def habitat_room_for(player: PlayerState, card: BirdCard) -> list[Habitat]:
    return [
        habitat
        for habitat in card.habitats
        if len(player.habitats[habitat]) < MAX_HABITAT_SLOTS
    ]
