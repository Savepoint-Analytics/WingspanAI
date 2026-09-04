# Birdfeeder Awareness and Food Odds: What Agents Actually Do

Status: **fixed 2026-09-03**. Die faces corrected and odds wired into agents; see the "What changed" section at the end.

Two questions: do agents read the birdfeeder when deciding whether to activate
forest or to play a bird whose power draws from the feeder, and do they compute
the odds of getting food they need? Short answers: **partly, by accident** and
**no**.

A third thing surfaced while checking: the simulator's die faces are wrong.

## 1. The die-face distribution is a fidelity bug

`_roll_birdfeeder` is `[rng.choice(BASE_FOOD_TYPES) for _ in range(5)]` — uniform
over five foods, 0.200 each (confirmed empirically over 200k dice).

The physical birdfeeder die has **six** faces: invertebrate, seed, fish, rodent,
fruit, and a sixth face showing **invertebrate + seed**, from which the player
takes one. So invertebrate and seed are each obtainable on two faces of six:

| Food | Real | Simulator | Simulator error |
|---|---:|---:|---:|
| invertebrate | 0.333 | 0.200 | **-40%** |
| seed | 0.333 | 0.200 | **-40%** |
| fish | 0.167 | 0.200 | +20% |
| rodent | 0.167 | 0.200 | +20% |
| fruit | 0.167 | 0.200 | +20% |

This is not a documented simplification; it appears in neither
`docs/rules/` nor the multiplayer audit's `known_simplifications`.

It biases the whole food economy in a direction that matters: birds costing
fish, rodent and fruit are the expensive, high-value ones, and the simulator
makes them roughly 20% easier to feed while making cheap invertebrate/seed birds
40% harder. Any conclusion about engine-building tempo or the value of expensive
birds currently rests on this.

It also silently invalidates the one probability constant in the codebase.
`_PREDATOR_SUCCESS_RATE = 0.92` is documented as `1 - (3/5)^5`, which is correct
*for the simulator*. Under real dice, P(rodent or fish on five dice) is
`1 - (4/6)^5 = 0.868`. The constant was derived from the model rather than the
game.

## 2. Feeder awareness: right answer, wrong reason

Agents do end up taking sensible food, but not because they evaluate the feeder.

Legal actions are enumerated **from the actual dice** (`_available_birdfeeder_rolls`
→ `_food_choice_tuples`), so every `GAIN_FOOD` action already carries a concrete,
available food set. `_food_need_score` then scores that concrete set against the
player's hand deficits. The *which food do I take* choice is therefore feeder-aware
by construction, and correctly so.

What is **not** feeder-aware:

- **Whether to activate forest at all.** Every agent returns a near-constant for
  `GAIN_FOOD` — greedy `20.0 + need`, engine-builder `3.0 + need`, egg-focus
  `1.0 + need * 0.5`. The constant does not move with what the feeder is showing,
  how many dice are in it, or whether a reroll is available.
- **Whether to play a bird whose power gains food from the feeder.**
  `_registered_food_power_value` returns 0.85 if the player currently has demand
  for that food and 0.25 otherwise. A bird that gains fish is valued identically
  whether the feeder is showing three fish or none.
- **Quantity.** Every agent read of the feeder is a membership test — `food_type in
  state.birdfeeder.dice`, `set(public_state.birdfeeder.dice)`, `bool(...dice)`.
  Nothing counts dice. Two fish showing is worth exactly what one fish showing is
  worth, and a feeder with one die looks like a feeder with five.

`net_value` is the only agent that reads the feeder at all outside action
enumeration, and only as a flat `+0.25` presence bonus (`net_value.py:816`) plus a
0.6-vs-0.35 weight in the opponent-response model (`net_value.py:969`).

## 3. Odds calculation: none

There is no probability machinery for food anywhere in the agents. The only
probability constant is `_PREDATOR_SUCCESS_RATE`, it is hardcoded, it assumes a
full five-dice feeder regardless of the actual count, and it is calibrated to the
wrong distribution.

### The specific scenario

Forest yields three food, the player needs at least one fish, the feeder holds a
single non-fish die.

The rules make this favourable, and the simulator already implements them
correctly. A lone die trivially satisfies "all dice show the same face", so a
reroll is legal (`_can_reroll_birdfeeder` returns True — verified); and the feeder
refills to five when emptied. The player is therefore effectively drawing against
a fresh roll of five dice, not against the one bad die in front of them.

| | P(at least one fish available) |
|---|---:|
| Real dice | **0.598** |
| Simulator | 0.672 |

So the correct read is "roughly a coin flip, slightly better" — and an agent that
looked only at the single non-fish die would wrongly conclude the fish is
unavailable. No agent computes this. They cannot currently weigh "activate forest
and probably get the fish" against "play a cheaper bird now".

## Recommended fix, in order

1. **Fix the die faces.** Model six faces with the invertebrate/seed choice face.
   This is a rules-fidelity fix and should land before any odds work, because odds
   built on the current distribution would be calibrated to a bug. Re-derive
   `_PREDATOR_SUCCESS_RATE` from the die model rather than hardcoding it.
2. **Add a food-availability estimator** — `P(food f obtainable within n dice
   draws)` given the current feeder contents, dice count, and reroll legality.
   Pure function, directly unit-testable against hand-computed values.
3. **Use it in three places**: the `GAIN_FOOD` action score, the valuation of
   birds with feeder-drawing powers, and the affordability shortfall term in
   `tray_preference.base_card_affinity`, which currently uses the crude
   `1 / (1 + shortfall)`.
4. **Measure.** Ablate as a switch like `VALUE_HABITAT_YIELD` so the contribution
   is attributable rather than assumed.

Step 1 is a correctness fix worth doing regardless of whether steps 2-4 pay off.

---

## What changed (2026-09-03)

All four steps landed.

1. **Die faces corrected.** `wingspan_ai.content.birdfeeder` models six faces
   including the combined invertebrate/seed face. `BirdfeederState.dice` holds
   faces rather than foods, and supply feasibility is a bipartite matching, so
   one combined die can no longer pay for both an invertebrate and a seed. Full
   rules write-up in `docs/rules/birdfeeder_dice.md`.
2. **`_PREDATOR_SUCCESS_RATE` re-derived** from the die model: 0.868, not the
   hardcoded 0.92.
3. **Odds are available as pure functions.** `probability_food_obtainable`
   accounts for reroll legality and refill-on-empty;
   `expected_useful_food` counts useful dice rather than testing membership.
4. **Wired into the three places**, behind `VALUE_FEEDER_ODDS` and
   `FEEDER_ODDS_WEIGHT_SCALE` so the contribution can be ablated:
   - the `GAIN_FOOD` action score, via a feeder-outlook term in
     `_food_need_score` for greedy and every archetype;
   - `_registered_food_power_value`, so a seed-gaining power is worth twice a
     fish-gaining one rather than the same;
   - `base_card_affinity`'s affordability term, which used
     `1 / (1 + shortfall)` and treated every missing food as equally hard to find.

The full suite passed unchanged after the die fix (269 tests), which is worth
noting: no existing test constrained the distribution. `tests/test_birdfeeder.py`
and `tests/test_feeder_odds.py` now do.

**Not yet measured.** The switch exists so the contribution can be attributed,
but no ablation has been run. Until then this is a correctness fix with a
plausible but unproven strategic benefit — the same standing the mat-scaling work
ended in.
