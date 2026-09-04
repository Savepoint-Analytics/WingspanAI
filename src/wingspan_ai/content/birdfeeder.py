"""Birdfeeder dice: faces, what they can supply, and feasibility.

Why faces rather than foods
---------------------------
The birdfeeder die was modelled as a uniform draw over the five base foods, so
every food came up 0.200 of the time. The physical die has **six** faces:
invertebrate, seed, fish, rodent, fruit, and a sixth face showing
**invertebrate + seed**, from which the player takes one.

That makes invertebrate and seed obtainable on two faces of six (0.333 each)
while fish, rodent and fruit sit at one face of six (0.167 each). The uniform
model therefore under-supplied the two cheap foods by 40% and over-supplied the
three expensive ones by 20%, which biases the whole food economy: fish, rodent
and fruit gate the expensive high-value birds.

A face is not a food, because the combined face supplies *either* of two foods at
the player's choice. Representing dice as faces keeps that choice in the model
instead of collapsing it at roll time.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence
from enum import StrEnum

from wingspan_ai.content.schemas import FoodType


class BirdfeederFace(StrEnum):
    """One face of a birdfeeder die.

    The single-food faces deliberately share their string values with `FoodType`
    so that existing state, telemetry and fixtures round-trip unchanged.
    """

    INVERTEBRATE = "invertebrate"
    SEED = "seed"
    FISH = "fish"
    FRUIT = "fruit"
    RODENT = "rodent"
    INVERTEBRATE_OR_SEED = "invertebrate_or_seed"


#: What each face can supply. The combined face offers a choice of one.
FACE_FOODS: dict[BirdfeederFace, tuple[FoodType, ...]] = {
    BirdfeederFace.INVERTEBRATE: (FoodType.INVERTEBRATE,),
    BirdfeederFace.SEED: (FoodType.SEED,),
    BirdfeederFace.FISH: (FoodType.FISH,),
    BirdfeederFace.FRUIT: (FoodType.FRUIT,),
    BirdfeederFace.RODENT: (FoodType.RODENT,),
    BirdfeederFace.INVERTEBRATE_OR_SEED: (FoodType.INVERTEBRATE, FoodType.SEED),
}

#: The six faces of one die, each equally likely.
DIE_FACES: tuple[BirdfeederFace, ...] = tuple(FACE_FOODS)

BIRDFEEDER_DICE_COUNT = 5


def roll_die(rng: random.Random) -> BirdfeederFace:
    return rng.choice(DIE_FACES)


def roll_dice(rng: random.Random, count: int = BIRDFEEDER_DICE_COUNT) -> list[BirdfeederFace]:
    return [roll_die(rng) for _ in range(count)]


def face_foods(face: BirdfeederFace) -> tuple[FoodType, ...]:
    return FACE_FOODS[BirdfeederFace(face)]


def obtainable_foods(faces: Iterable[BirdfeederFace]) -> set[FoodType]:
    """Every food any single die could supply."""

    return {food for face in faces for food in face_foods(face)}


def die_probability(food: FoodType) -> float:
    """Probability that one rolled die can supply `food`."""

    matching = sum(1 for face in DIE_FACES if food in face_foods(face))
    return matching / len(DIE_FACES)


def can_supply(faces: Sequence[BirdfeederFace], foods: Sequence[FoodType]) -> bool:
    """Whether these dice can supply this exact multiset of foods, one die each.

    Solved as a bipartite matching rather than a per-food count check: a
    combined face can cover an invertebrate *or* a seed but not both, so
    counting each food independently would wrongly accept
    `[invertebrate_or_seed] -> (invertebrate, seed)`.
    """

    if not foods:
        return True
    if len(foods) > len(faces):
        return False

    # Greedy augmenting-path matching. At most five dice, so cost is irrelevant.
    assigned_food_by_die: dict[int, FoodType] = {}

    def assign(food: FoodType, seen: set[int]) -> bool:
        for die_index, face in enumerate(faces):
            if die_index in seen or food not in face_foods(face):
                continue
            seen.add(die_index)
            occupant = assigned_food_by_die.get(die_index)
            if occupant is None or assign(occupant, seen):
                assigned_food_by_die[die_index] = food
                return True
        return False

    return all(assign(food, set()) for food in foods)


def supplying_die_index(faces: Sequence[BirdfeederFace], food: FoodType) -> int | None:
    """Index of the die to spend for `food`, or None if no die can supply it.

    Prefers the least flexible qualifying die so a combined face is kept for a
    food only it can still cover.
    """

    candidates = [index for index, face in enumerate(faces) if food in face_foods(face)]
    if not candidates:
        return None
    return min(candidates, key=lambda index: len(face_foods(faces[index])))


def all_supplies(
    faces: Sequence[BirdfeederFace],
    count: int,
    allowed_foods: Sequence[FoodType],
) -> list[tuple[FoodType, ...]]:
    """Every distinct multiset of `count` foods these dice can actually supply."""

    from itertools import combinations_with_replacement

    if count <= 0:
        return [()]
    order = {food: index for index, food in enumerate(allowed_foods)}
    options = {
        tuple(sorted(combo, key=order.__getitem__))
        for combo in combinations_with_replacement(allowed_foods, count)
        if can_supply(faces, combo)
    }
    return sorted(options, key=lambda option: tuple(order[food] for food in option))


def all_faces_match(faces: Sequence[BirdfeederFace]) -> bool:
    """The reroll condition: every die in the feeder shows the same face.

    Compared on faces, not on foods, so a combined face does not count as
    matching a plain invertebrate face.
    """

    return len(set(faces)) <= 1


def counts_by_face(faces: Iterable[BirdfeederFace]) -> Counter[BirdfeederFace]:
    return Counter(BirdfeederFace(face) for face in faces)


def probability_any_available(foods: Sequence[FoodType], dice_count: int) -> float:
    """P(at least one of `dice_count` freshly rolled dice supplies any of `foods`)."""

    if dice_count <= 0 or not foods:
        return 0.0
    wanted = set(foods)
    matching = sum(1 for face in DIE_FACES if wanted & set(face_foods(face)))
    per_die = matching / len(DIE_FACES)
    return 1.0 - (1.0 - per_die) ** dice_count


def probability_food_obtainable(
    faces: Sequence[BirdfeederFace],
    food: FoodType,
    draws: int,
) -> float:
    """P(the player can obtain `food` while taking `draws` dice from this feeder.

    Returns 1.0 when a die already on the table supplies it. Otherwise the
    player only gets another chance if the dice are refreshed, which happens two
    ways:

    - **Reroll.** Legal when every die shows the same face, which is trivially
      true of a lone die. The player sees `len(faces)` fresh dice.
    - **Refill.** Taking more dice than the feeder holds empties it, and an empty
      feeder is refilled with all five dice and rerolled. The player then sees a
      full five.

    Approximation: when both are possible the larger refresh is used rather than
    compounding them, so this is a mild under-estimate in the rare case where a
    reroll fails and the feeder then empties. It is exact in the common cases,
    including the motivating one — a single unwanted die with several draws to
    make.
    """

    if draws <= 0:
        return 0.0
    if food in obtainable_foods(faces):
        return 1.0

    fresh_dice = 0
    if faces and all_faces_match(faces):
        fresh_dice = len(faces)
    if draws > len(faces):
        fresh_dice = max(fresh_dice, BIRDFEEDER_DICE_COUNT)
    return probability_any_available((food,), fresh_dice)


def expected_useful_food(
    faces: Sequence[BirdfeederFace],
    wanted: Sequence[FoodType],
    draws: int,
) -> float:
    """Expected number of the `draws` taken dice that supply a wanted food.

    Counts what the feeder can actually deliver now, then credits any remaining
    draws at the fresh-roll rate. Unlike a membership test this responds to *how
    many* useful dice are showing, which is what distinguishes a feeder holding
    three fish from one holding a single fish.
    """

    if draws <= 0 or not wanted:
        return 0.0
    wanted_set = set(wanted)
    on_table = sum(1 for face in faces if wanted_set & set(face_foods(face)))
    from_table = min(on_table, draws, len(faces))

    remaining_draws = draws - min(draws, len(faces))
    if remaining_draws <= 0:
        return float(from_table)

    matching = sum(1 for face in DIE_FACES if wanted_set & set(face_foods(face)))
    return from_table + remaining_draws * (matching / len(DIE_FACES))
