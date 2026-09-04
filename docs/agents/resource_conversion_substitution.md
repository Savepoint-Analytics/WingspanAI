# Resources as Substitutes: The Conversion Chain

Status: gap analysis, 2026-09-04. **Implemented in the rules, valued by no agent.**

## The mechanic

Each habitat action lets a player convert a surplus resource into the resource
that habitat produces:

| Habitat | Conversion | Enumerated as |
|---|---|---|
| Forest | discard 1 card → 1 extra food | `spend_card_for_extra_food` |
| Grassland | discard 1 food → 1 extra egg | `spend_food_for_extra_egg` |
| Wetland | discard 1 egg → 1 extra card | `spend_egg_for_extra_card` |

The three form a cycle: food → egg → card → food. A player who is long on one
resource is never truly stuck, only paying a conversion rate.

## What the agents do now

The rules implement all three (`base_game.py:648`, `:682`, `:710`) and enumerate
them as distinct legal actions. **No agent scores them.** The only agent-side
mention is in `guardrails.py:501-503`, which pattern-matches the flags to
*restrict* actions — a rule filter, not a valuation.

The practical consequence differs by agent:

- `potential_points` scores actions by simulating them, so a conversion is valued
  at whatever the resulting state scores. It will take a conversion that happens
  to raise its estimate, but it never reasons about the exchange rate, and its
  potential terms do not model a resource it does not yet hold.
- `greedy_immediate` and every archetype score by action *type*. A conversion
  variant and a plain variant of the same habitat action land in the same branch,
  so the extra resource is invisible except through `_food_need_score`.

So conversions happen only by accident.

## Why this matters more than it looks

### Surpluses are common and dead
An egg-focused board accumulates eggs it cannot spend; a food-heavy board holds
tokens no bird in hand needs. Each conversion turns a dead resource into a live
one at 1:1 plus a turn, which is usually better than the alternative of doing
nothing with it.

### It changes what "surplus" means
Valuing conversions requires a marginal value per resource, which the agents do
not have. `feeder_odds` values a *wanted* food at 0.45 points; there is no
corresponding figure for an unwanted one, and no notion that the fifth spare egg
is worth less than the first.

### It is the missing half of multi-habitat placement
This is where the Common Raven case lives. The Raven is playable in forest or
grassland. Placing it in grassland supports the egg supply that feeds the
food-for-egg and egg-for-card conversions; placing it in forest gains food
immediately at the cost of an egg the player may then have to go and re-lay.

The agents already enumerate placement correctly — `_legal_play_bird_actions`
loops `ordered_habitats(card.habitats)`, so every legal habitat is a separate
action, and 244 of the 707 catalogued birds are multi-habitat. `potential_points`
chooses by lookahead; `archetype_engine_builder` reads placement depth;
`greedy_immediate` returns a flat 40.0 and cannot distinguish placements at all.

But **none of them can reason about the Raven correctly, because the reasoning
runs through conversions that carry no value.** Fixing placement without fixing
conversion valuation will not produce the right answer.

## How this should be handled

### 1. Give each resource a marginal value that decays
```
marginal_value(resource, held) = base_value(resource) x decay^max(0, held - live_need)
```
Above what the hand and board can actually use, each further unit is worth
sharply less. This single function makes "surplus" expressible and is the
prerequisite for everything else here.

### 2. Score a conversion as the difference of marginals
```
value(convert A -> B) = marginal_value(B, held_B) - marginal_value(A, held_A)
```
Take it when positive. This is the whole decision, and it falls out of step 1.

### 3. Do not model the full cycle
It is tempting to chain food → egg → card → food and reason about multi-step
arbitrage. Don't. Each hop costs an action cube, which is the scarcest resource
in the game; a two-hop conversion is almost never worth two turns. Value one hop
at a time and let the search find sequences if they exist.

### 4. Fix placement afterwards, not before
Once conversions carry value, `potential_points`'s lookahead will pick up the
Raven case on its own, because the downstream egg cost becomes visible in the
score. The archetypes will still need an explicit placement term; the greedy
agent needs one at all.

## Success criteria

A conversion-aware agent should show:

- A measurable rate of conversion actions in telemetry — currently near zero for
  the heuristic agents except by accident.
- Habitat choice for multi-habitat birds that shifts with board state rather than
  with `ordered_habitats` enumeration order.
- No change, or an improvement, in win rate. Given that the last two valuation
  improvements landed null, the honest prior is that this one does too, and it
  should be ablated behind a switch on the same terms.
