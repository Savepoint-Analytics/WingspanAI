# Birdfeeder Dice

_Encoded 2026-09-03. Source: WS_Core_Rulebook.pdf, "Gain food" / birdfeeder._

## The die

Five identical dice sit in the birdfeeder. Each has **six** faces:

| Face | Supplies |
|---|---|
| invertebrate | invertebrate |
| seed | seed |
| fish | fish |
| rodent | rodent |
| fruit | fruit |
| invertebrate + seed | **either** invertebrate or seed, player's choice |

Per-die probability that a food is obtainable:

| Food | Probability |
|---|---:|
| invertebrate | 2/6 = 0.333 |
| seed | 2/6 = 0.333 |
| fish | 1/6 = 0.167 |
| rodent | 1/6 = 0.167 |
| fruit | 1/6 = 0.167 |

## Why faces and not foods

Modelling a die as a food loses the sixth face's choice. The simulator previously
drew uniformly from the five foods, giving every food 0.200 — under-supplying
invertebrate and seed by 40% and over-supplying fish, rodent and fruit by 20%.
That biased the food economy in the direction that matters most, since fish,
rodent and fruit gate the expensive high-value birds.

`BirdfeederState.dice` therefore holds `BirdfeederFace` values. The five
single-food faces share their string values with `FoodType`, so existing state,
telemetry and fixtures round-trip unchanged.

One consequence worth stating: **one die yields one food**. A single combined
face can pay for an invertebrate *or* a seed, never both. Feasibility is
therefore a bipartite matching between requested foods and dice
(`can_supply`), not a per-food count comparison.

## Reroll and refill

- **Reroll.** Legal when every die in the feeder shows the same face. This is
  trivially true of a lone die, so a single unwanted die can always be rerolled.
  Compared on faces: a combined face is not the same face as a plain
  invertebrate.
- **Refill.** An emptied feeder is refilled with all five dice and rerolled.

Together these make a depleted feeder far less punishing than it looks. With one
unwanted die showing and three food to take, the player is effectively drawing
against a fresh roll of five, so a specific needed food arrives
`1 - (5/6)^5 = 0.598` of the time rather than never.

## Implementation

`src/wingspan_ai/content/birdfeeder.py` holds the die model and the derived
probabilities as pure functions. It lives under `content/` rather than `rules/`
because the die is a game component, and because `rules/__init__` imports
`base_game`, which imports state — importing the face enum from state would
close that cycle.

Constants derived from the die rather than hardcoded:

- `_PREDATOR_SUCCESS_RATE` in `potential_points` is now
  `probability_any_available((rodent, fish), 5) = 0.868`. It was hardcoded 0.92,
  documented as `1 - (3/5)^5` — correct for the uniform die the simulator used to
  roll, and therefore a constant calibrated to a bug rather than to the game.
