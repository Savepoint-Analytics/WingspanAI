# Which egg gets spent, and what that costs

Status: audited 2026-10-08. A guardrail exists and works for round goals. **It
does not cover the two egg-dependent bonus cards, its docstring claims it does,
and it misses wild-nest birds whose eggs the goal scoring counts.**

## Where eggs get spent

Eggs are a currency in three places: playing a bird into slot 2–3 (1 egg) or
4–5 (2 eggs), and powers that trade an egg for cards or food
(`discard_egg_draw_cards`, `discard_egg_gain_wild_food`, 7 cards between them).
All of them route through `_spend_eggs`, which takes positions from
`egg_spend_order` in order until the cost is paid.

**Which egg** is never a player decision. It is resolved in the rules layer, in
the same `heuristic_resolution` spirit as the power handlers — see
`hidden_power_choices.md`, where 112 of 180 powered birds have a choice made for
them.

## The guardrail that exists

`egg_spend_order` sorts candidate positions by

    (goal protection, -eggs on the bird, habitat name, slot index)

so the least-protected egg goes first, then the egg from the fullest bird.
`_egg_scoring_protection` awards +2 when the **current round's** goal mentions
`[egg]` and the bird's habitat matches, and +2 again when the bird's nest type
matches.

Its history is good: the docstring records that traversal "used to be
habitat-by-habitat in enum order, which could spend the very egg an active round
goal was counting." It is behind `VALUE_RESOURCE_SPENDING`, and the ablation
(2026-09-04, 200 games an arm) read it as a **null** — "correctness fixes
retained; no measurable effect on play".

Verified working: on seed 5 with the round-1 goal `[egg] in [ground]`, a
ground-nesting bird with 3 eggs scores protection 2 and a non-ground bird with 1
egg scores 0, so the unprotected egg is spent first. That is the intended
behaviour.

## Defect 1 — the two egg bonus cards are not inputs, and the docstring says they are

`_egg_scoring_protection`'s docstring reads:

> Uses the current round goal **and the player's own bonus cards**; both are
> information the acting player legitimately has.

Its signature is `(habitat, slot, state)`. **It cannot see the player's bonus
cards, and the body never mentions them.** Two base-game bonus cards depend on
eggs:

| card | condition | scoring | how spending hurts it |
|---|---|---|---|
| **Oologist** | birds with ≥1 egg | 7–8 birds: 3; 9+: 6 | emptying a 1-egg bird drops the count |
| **Breeding Manager** | birds with ≥4 eggs | 1 per bird | taking from a 4-egg bird drops it below the threshold |

Demonstrated directly:

- Breeding Manager held, birds at **[4, 2] eggs**, spend 1 → **[3, 2]**. It took
  from the 4-egg bird, destroying the only qualifying bird.
- Oologist held, birds at **[1, 3] eggs**, spend 1 → **[0, 3]**. It emptied the
  1-egg bird, losing a qualifying bird.

A prediction of mine was wrong here and the reason matters. I expected the
`-eggs` term to take from the *fullest* bird and so protect Oologist by
accident. It did not: in the Oologist case the round goal protected the 3-egg
bird by nest type, so the ordering was decided entirely by goal protection.
**The outcome for a bonus card is incidental** — sometimes helpful, sometimes
harmful, never considered.

There is a suggestive link to the KPI pass. **Breeding Manager is the worst of
all 26 base-game bonus cards** on the archive: 0.68 qualifying birds a game
against the best card's 3.79, fulfilment 0.082, measured over 391 games. Its
condition is exactly the one the egg-spend heuristic is most likely to break.
That is a hypothesis, not a measurement — the card is also intrinsically hard —
but it is the cheapest thing to test here.

## Defect 2 — wild-nest birds are unprotected while their eggs still count

The goal **scoring** treats a wild nest as matching any nest type, in three
places in `base_game.py`:

```python
slot.card.nest_type.value == nest_type or slot.card.nest_type.value == "wild"
```

The **protection** does a bare string match:

```python
if nest_type is not None and f"[{nest_type.value}]" in goal_text:
```

so `"[wild]" in "[egg] in [ground]"` is `False`. **A wild-nest bird's egg counts
for a nest-type goal and is never protected from being spent for it.**

Scope: **17 of 180 base-game birds (9.4%)** have wild nests, and **8 of the goal
pool** are nest-type egg goals. So on roughly a quarter of rounds that use a
nest-type egg goal, every wild-nest bird on the board is mis-ranked.

This one is a plain inconsistency between two parts of the same rules layer, not
a judgement call, and it is a two-line fix.

## Defect 3 — only the current round's goal is protected

`goal_index = min(round_number - 1, len(goals) - 1)` reads the active round's
goal only. All four goals are public from setup, so an egg that will score for
round 4 can be spent in round 2 with no protection at all.

Weaker than the other two: eggs laid in round 2 often will not survive to round
4 anyway, and the later goals' placement scale is bigger but further away. The
setup opener weights later goals at a 0.55 discount for the same reason
(`agents/setup.py`), so there is a precedent for how to price it.

Also unhandled: `sets of [egg][egg][egg] in [wetland][grassland][forest]`
mentions all three habitats, so every egg scores +2 and the term stops
discriminating. A sets goal wants *balance* preserved across habitats, which
neither +2-for-all nor fullest-bird-first achieves.

## What is not a defect

- **End-of-game egg points.** Every egg is 1 VP, so spending always costs
  exactly 1 point whichever egg goes. No ordering can help.
- **Egg capacity.** Spending frees capacity on that bird, which is neutral to
  slightly good, and `_place_eggs_on_player_birds` handles wild nests correctly.
- **The agent avoiding the action entirely.** The search evaluates the state
  after an action, so if a goal or bonus loss is visible in the evaluation it can
  decline to spend. It cannot choose *which* egg, so avoidance is its only lever
  — which makes the ordering more load-bearing, not less.

## Suggested order

1. **Fix the wild-nest string match** (defect 2). Two lines, a plain
   inconsistency, 9.4% of birds.
2. **Pass the player's bonus cards into the protection** (defect 1). The
   docstring already promises it. `Oologist` wants a bird at exactly 1 egg
   protected; `Breeding Manager` wants a bird at exactly 4 protected. Both are
   threshold conditions, so the protection should be "does spending cross a
   threshold", not a flat +2.
3. **Weight later goals** (defect 3), on the opener's discount precedent.

All three are rules-layer changes behind `VALUE_RESOURCE_SPENDING`, so they are
testable the way the 2026-09-04 ablation was. Expect small: that ablation read
null at 200 games an arm, and these are narrower still. The case for fixing 1
and 2 is correctness — the code does not do what its own docstring says, and two
parts of the same layer disagree about wild nests — rather than measured points.
