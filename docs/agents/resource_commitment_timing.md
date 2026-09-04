# Paying More Now to Get a Bird Down

Status: gap analysis, 2026-09-04. **A real defect found: the agent never chooses
which food or egg to spend.**

## The decision

Playing a bird before the round ends is often worth overpaying for. A bird played
in round 2 activates for three more rounds; the same bird played in round 4
activates once. Spending a scarce food, or converting a card into food to close a
one-token gap, can be correct even when the exchange looks bad in isolation.

The mirror decision matters too: paying a *wild* cost with the wrong token can
strand a later bird.

## The defect: payment is not a choice

`base_game.py:1733`:

```python
def _spend_food_cost(player: PlayerState, food_cost: FoodCost) -> None:
    for food_type, count in food_cost.fixed.items():
        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) - count

    remaining_any_cost = food_cost.wild_food_count + food_cost.choice_food_count
    for food_type in BASE_FOOD_TYPES:
        while remaining_any_cost > 0 and player.food_tokens.get(food_type, 0) > 0:
            player.food_tokens[food_type] -= 1
            remaining_any_cost -= 1
```

Wild and choice costs are paid by walking `BASE_FOOD_TYPES` in declaration order:
invertebrate, seed, fish, fruit, rodent. **Invertebrate is always spent first.**
The player never chooses, so an agent holding one fish and three invertebrates
pays a wild cost with an invertebrate by luck of ordering, not by reasoning.

Worse, this is exactly backwards under the corrected die. Invertebrate and seed
are obtainable on two die faces of six; fish, rodent and fruit on one. Spending
the *most* replaceable token first is right by accident here — but the rule is
positional, not principled, and it silently produces the wrong answer whenever
the player's own hand makes a common food scarce for them.

The same problem applies to eggs, `base_game.py:1744`:

```python
def _spend_eggs(player: PlayerState, egg_count: int) -> None:
    for habitat in Habitat:
        for slot in player.habitats[habitat]:
```

Eggs are spent habitat-by-habitat in enum order. Round goals and bonus cards
count eggs **in specific habitats and on specific nest types**, so a fixed order
can destroy scoring progress the agent is actively chasing. This is a live
scoring bug whenever an egg-in-habitat goal is on the board, not merely a missing
heuristic.

## What the agents do about timing

`potential_points` discounts future value by `turns_remaining` throughout, and
switches to exact search inside `final_search_turns`. That captures "a bird played
later is worth less" implicitly.

What no agent has is the *opportunity cost of the action cube*. Actions are
compared by the value of the resulting state, so spending a turn on food rather
than a bird is only penalised to the extent the lookahead sees it. There is no
explicit tempo term, and no agent reasons "this is the last turn of the round, so
a bird in hand that I cannot pay for is worth zero until next round."

## How this should be handled

### 1. Make payment a decision, not an ordering
Choose which tokens pay a wild or choice cost by **replacement cost**:

```
replacement_cost(food) = own_need(food) / die_probability(food)
```

Spend the token with the lowest replacement cost. `die_probability` already
exists in `wingspan_ai.content.birdfeeder`; `own_need` is the hand deficit
already computed by `feeder_odds.hand_food_deficits`. This is a small function
using two things that are already built.

### 2. Make egg spending goal-aware
Spend eggs from the slot whose loss costs least against the active round goals
and held bonus cards, breaking ties toward habitats with spare capacity. This is
a correctness fix and should be treated as one.

### 3. Add an explicit end-of-round urgency term
A bird playable now but not next round is worth its full engine value; the same
bird held is worth its value discounted by the chance of affording it later. The
machinery exists — `probability_food_obtainable` gives exactly that chance.

```
urgency = engine_value x (1 - P(affordable before it stops mattering))
```

Add `urgency` to `PLAY_BIRD` when the round is about to end, so a marginal
overpayment is accepted only when the alternative is likely to lose the bird's
productive window.

### 4. Do not add a generic "overpay" bonus
The temptation is a flat bonus for playing birds early. That would double-count:
`turns_remaining` already scales engine value. The gap is specifically about
*which token* and *end-of-round cliffs*, not about earliness in general.

## Priority

Items 1 and 2 are correctness work and should land regardless of whether they
help play — item 2 in particular can actively cost points today. Item 3 is a
strategy term and should be ablated like the others, with the prior that it lands
null, since the last two did.
