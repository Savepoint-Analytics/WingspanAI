"""Policy-side valuation of what the birdfeeder is likely to supply.

Why this exists
---------------
Agents were feeder-aware only by accident. Legal actions are enumerated from the
real dice, so *which* food an agent takes was already sensible. But every read of
the feeder in agent code was a membership test — `food in state.birdfeeder.dice`
— so nothing distinguished a feeder showing three fish from one showing a single
fish, or a feeder holding one die from one holding five. And no agent estimated
the odds of getting a food it did not yet have.

The concrete case: forest yields three food, the player needs a fish, and the
feeder holds one non-fish die. Reading the die alone says the fish is
unavailable. In fact a lone die may be rerolled and the feeder refills to five
when emptied, so the fish arrives about 60% of the time.

The probability model lives in `wingspan_ai.content.birdfeeder`, which knows the
die. This module holds only the policy weighting, so the rules stay separable
from how strongly an agent cares.
"""

from __future__ import annotations

from collections import Counter

from wingspan_ai.content.birdfeeder import (
    DIE_FACES,
    die_probability,
    expected_useful_food,
    face_foods,
    probability_food_obtainable,
)
from wingspan_ai.content.schemas import BirdCard, FoodType
from wingspan_ai.state.models import GameState, PlayerState

#: Ablation switch for measuring what feeder-odds valuation contributes. Set
#: False to reproduce the pre-2026-09-03 behaviour, where the feeder was only
#: ever membership-tested.
VALUE_FEEDER_ODDS = True

#: Scales every term in this module, for weight sweeps without touching callers.
FEEDER_ODDS_WEIGHT_SCALE = 1.0

#: Points-equivalent of one wanted food the feeder is expected to deliver. Food
#: is an input that still needs converting into a bird, so it is worth well
#: under a point — consistent with `_HABITAT_YIELD_UNIT_VALUE`.
_WANTED_FOOD_VALUE = 0.45

#: Average per-die availability across the five distinct foods, used to
#: normalize a food's own availability so this term recentres rather than
#: inflates. Iterates distinct foods: summing over faces would count
#: invertebrate and seed twice via the combined face.
_DISTINCT_FOODS = sorted({food for face in DIE_FACES for food in face_foods(face)})
_MEAN_DIE_PROBABILITY = sum(die_probability(food) for food in _DISTINCT_FOODS) / len(
    _DISTINCT_FOODS
)


def hand_food_deficits(player: PlayerState) -> Counter[FoodType]:
    """Food the player still needs to play the birds already in hand."""

    deficits: Counter[FoodType] = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            shortfall = count - player.food_tokens.get(food_type, 0)
            if shortfall > 0:
                deficits[food_type] += shortfall
    return deficits


def feeder_supply_value(state: GameState, player: PlayerState, draws: int) -> float:
    """How well the feeder, as it stands, serves this player's unmet needs.

    Unlike a membership test this scales with the number of useful dice showing
    and with how many dice the player's mat lets them take.
    """

    if not VALUE_FEEDER_ODDS or draws <= 0:
        return 0.0
    deficits = hand_food_deficits(player)
    if not deficits:
        return 0.0
    expected = expected_useful_food(state.birdfeeder.dice, list(deficits), draws)
    return expected * _WANTED_FOOD_VALUE * FEEDER_ODDS_WEIGHT_SCALE


def food_power_availability_multiplier(food: FoodType | None) -> float:
    """Weight a feeder-drawing bird power by how often its food actually shows.

    A bird gaining fish and a bird gaining seed were valued identically. Seed is
    obtainable on two die faces of six and fish on one, so the fish bird pays out
    half as often.
    """

    if not VALUE_FEEDER_ODDS or food is None:
        return 1.0
    ratio = die_probability(food) / _MEAN_DIE_PROBABILITY
    return 1.0 + (ratio - 1.0) * FEEDER_ODDS_WEIGHT_SCALE


def affordability_outlook(
    state: GameState,
    player: PlayerState,
    card: BirdCard,
    draws: int,
) -> float:
    """Probability-flavoured estimate that this card becomes payable soon.

    Replaces a `1 / (1 + shortfall)` placeholder that treated every missing food
    as equally hard to find, regardless of what the feeder was showing or how
    common that food is on the die.
    """

    if not VALUE_FEEDER_ODDS:
        return 0.0
    missing = [
        food_type
        for food_type, count in card.food_cost.fixed.items()
        if player.food_tokens.get(food_type, 0) < count
    ]
    if not missing:
        return 1.0
    chances = [
        probability_food_obtainable(state.birdfeeder.dice, food_type, draws)
        for food_type in missing
    ]
    outlook = 1.0
    for chance in chances:
        outlook *= chance
    return outlook
