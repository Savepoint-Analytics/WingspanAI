"""Which food tokens and which eggs to spend when a cost allows a choice.

Why this exists
---------------
Costs that permit a choice were resolved positionally. Wild and choice food costs
walked `BASE_FOOD_TYPES` in declaration order, so invertebrate was always spent
first. Eggs were spent habitat-by-habitat in `Habitat` enum order.

Neither is a decision the rules should be making arbitrarily. The egg case is the
more serious of the two: round goals and bonus cards count eggs **in specific
habitats and on specific nest types**, so a fixed order can spend exactly the egg
the player is scoring on.

These remain rules-layer default resolutions rather than agent choices, in the
same `heuristic_resolution` spirit as the power handlers: making every payment an
enumerated legal action would multiply the action space for a decision that is
usually forced. The selection is at least principled now, and isolated here so it
can be tested and later promoted to a real choice.

Ablation
--------
`VALUE_RESOURCE_SPENDING = False` restores the previous positional behaviour, so
the contribution of choosing well is measurable rather than assumed.
"""

from __future__ import annotations

from collections import Counter

from wingspan_ai.content.birdfeeder import die_probability
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import FoodCost, FoodType, Habitat

#: Ablation switch. False reproduces the pre-2026-09-04 positional ordering.
VALUE_RESOURCE_SPENDING = True

#: Floor on die probability so an unobtainable food never divides by zero.
_MIN_DIE_PROBABILITY = 1e-6


def _hand_food_demand(player) -> Counter[FoodType]:
    """Food the player still needs for birds in hand."""

    demand: Counter[FoodType] = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            shortfall = count - player.food_tokens.get(food_type, 0)
            if shortfall > 0:
                demand[food_type] += shortfall
    return demand


def food_replacement_cost(food_type: FoodType, demand: Counter[FoodType]) -> float:
    """How costly this token is to give up: how badly needed, over how easily replaced.

    A fish the player needs is expensive twice over — it is wanted, and it shows
    on one die face of six. A spare invertebrate is cheap on both counts.
    """

    probability = max(die_probability(food_type), _MIN_DIE_PROBABILITY)
    return (demand.get(food_type, 0) + 1.0) / probability


def flexible_food_spend_order(player, food_cost: FoodCost) -> list[FoodType]:
    """Tokens to spend for the wild/choice portion, cheapest to give up first.

    The fixed portion of the cost is assumed already deducted, so this only
    chooses among what genuinely may be substituted.
    """

    flexible = food_cost.wild_food_count + food_cost.choice_food_count
    if flexible <= 0:
        return []
    if not VALUE_RESOURCE_SPENDING:
        return list(BASE_FOOD_TYPES)

    demand = _hand_food_demand(player)
    return sorted(
        BASE_FOOD_TYPES,
        key=lambda food_type: (food_replacement_cost(food_type, demand), food_type.value),
    )


def _egg_scoring_protection(habitat: Habitat, slot, state) -> int:
    """How many active scoring conditions this egg's position contributes to.

    Higher means the egg is worth protecting. Uses the current round goal and the
    player's own bonus cards; both are information the acting player legitimately
    has.
    """

    if state is None:
        return 0

    protection = 0
    goals = getattr(state, "round_goals", None) or []
    round_number = getattr(getattr(state, "round_state", None), "round_number", 1)
    goal_index = min(round_number - 1, len(goals) - 1)
    if goal_index >= 0:
        goal_text = goals[goal_index].name.lower()
        if "[egg]" in goal_text:
            if f"[{habitat.value}]" in goal_text:
                protection += 2
            nest_type = getattr(slot.card, "nest_type", None)
            if nest_type is not None and f"[{nest_type.value}]" in goal_text:
                protection += 2
    return protection


def egg_spend_order(player, state=None) -> list[tuple[Habitat, int]]:
    """(habitat, slot index) positions to take eggs from, least costly first.

    Eggs protected by the active round goal are spent last, so a fixed traversal
    order can no longer destroy the scoring the player is chasing.
    """

    positions: list[tuple[Habitat, int]] = [
        (habitat, index)
        for habitat in Habitat
        for index, slot in enumerate(player.habitats[habitat])
        if slot.eggs > 0
    ]
    if not VALUE_RESOURCE_SPENDING:
        return positions

    return sorted(
        positions,
        key=lambda position: (
            _egg_scoring_protection(position[0], player.habitats[position[0]][position[1]], state),
            -player.habitats[position[0]][position[1]].eggs,
            position[0].value,
            position[1],
        ),
    )


def _bonus_name(name: str) -> str:
    return name.split("[", maxsplit=1)[0].strip()


def discard_priority(card, player, state=None) -> tuple:
    """Sort key for choosing what to throw away: lowest is discarded first.

    The previous rule was `min(victory_points, -food_cost)` — printed points
    alone. It would discard a cheap bird that completes a held bonus card in
    order to keep an unaffordable high-point bird that will never be played.

    Ranks on what the card can still do for *this* player: bonus-card fit, room
    to play it, affordability, then printed points.
    """

    if not VALUE_RESOURCE_SPENDING:
        return (card.victory_points, -card.food_cost.minimum_total, card.common_name)

    held_bonus = {_bonus_name(bonus.name) for bonus in getattr(player, "bonus_cards", [])}
    bonus_fit = len(held_bonus & {_bonus_name(tag) for tag in card.bonus_card_tags})

    has_room = any(len(player.habitats[habitat]) < 5 for habitat in card.habitats)

    remaining = dict(player.food_tokens)
    affordable = True
    for food_type, count in card.food_cost.fixed.items():
        if remaining.get(food_type, 0) < count:
            affordable = False
            break
        remaining[food_type] -= count
    if affordable:
        flexible = card.food_cost.wild_food_count + card.food_cost.choice_food_count
        affordable = sum(remaining.values()) >= flexible

    # Ascending: the first entry is discarded, so unplayable and unwanted first.
    return (
        bonus_fit,
        int(has_room),
        int(affordable),
        card.victory_points,
        -card.food_cost.minimum_total,
        card.common_name,
    )
