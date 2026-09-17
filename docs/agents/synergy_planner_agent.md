# Synergy Planner Agent

Status: research programme defined and instruments built, 2026-09-16; agent not yet implemented. Layers A and B run; layer C and the agent term follow their results.

## Purpose

`SynergyPlannerAgent` is the planned successor to `PotentialPointsAgent` that
values *combinations* of cards — what a play accomplishes immediately and
what it sets up for the rest of the game — rather than each card's standalone
potential. It exists because two things are now measured:

- Depth-3 search on a round horizon is the strongest thing in the project
  (+10.4 points), but a game-horizon search costs 12, so sub-strategies that
  need five turns of setup are invisible to the planner and cannot be reached
  by searching further.
- Card-choice terms pay where resource-valuation terms did not: the
  expected-points opener is worth +0.85 on a decision the agent made worse
  than arbitrary, and the keep study put six points per game on the setup
  decision alone.

The agent asks, for a candidate play:

```text
play value =
  immediate value (points, on-play power, resources)
  + engine value of the card alone over the remaining activations
  + synergy value with cards already on the board and in hand
  + option value of the partial combos it completes or enables
```

where the synergy and option terms come from evidence, not intuition: a
rules-computed synergy matrix and counterfactual play attribution on archived
games.

## The Problem It Solves

Specific card combinations are rare in simulated play. A pair that racks up
points together may never be dealt to the same player across thousands of
games, and when it is, the games differ in everything else. Two properties of
this project make the combination question tractable anyway:

1. **The simulator is deterministic given seed and policy**, so the value of
   any recorded decision can be measured exactly by counterfactual rollout —
   what the rest of the game would have been under the same continuation had
   the play not been made — instead of estimated from correlations.
2. **Synergies can be computed from the rules**, not waited for in the data:
   the engine can place any two cards on a controlled board and score what
   they yield together against what they yield apart, for every pair, in
   seconds.

Rarity therefore stops being an obstacle: layer A covers every pair, layer B
attributes value to the plays that did happen, and a mechanic-level model
connects the two so a rare pair inherits evidence from the common mechanics it
is an instance of.

## Current Implementation

### Layer A — rules-computed synergy bench (`analysis/card_synergy_bench.py`)

For each habitat, every brown-powered resident is placed alone on a controlled
board and the habitat activated once; then every ordered pair (right slot
resolves first). Yields are the owner's deltas in food, cards, eggs, tucked
cards and cached food. The mat's own scaling is removed by a size-matched
baseline of power-less birds:

```text
power(config)  = yield(config) − yield(same-size row of blanks)
synergy(A, B)  = power(A, B) − power(A) − power(B)
```

Measured over three seeds and two resource contexts (rich: 3 cards, 2 of
each food; scarce: empty hand, no food), averaged. First run: 194 brown
residents, 12,386 ordered pairs, 47 seconds; **2,029 pairs interact**.

What it found, unprompted: the universal partners are Gray Catbird and
Northern Mockingbird ("repeat another bird's brown power in this habitat") —
+2 eggs next to the "lay an egg on any bird" sparrows, +1.5 next to tuck
birds, +1 next to cachers — and capacity synergies (Baird's Sparrow needs a
neighbour with egg room). Forest yields no pair interaction under one
activation, which is right: forest chains are food-to-play chains that cross
turns, the documented next extension.

Scope of the first bench: brown powers, same-habitat pairs, one activation.
Extensions in order: cross-habitat chains over several activations (draw in
wetland → tuck in grassland), white on-play powers, pink reactions, triples
seeded from the pair matrix.

Output: `artifacts/synergy_bench/synergy_bench.json` (full matrix) and
`synergy_bench.md`.

### Layer B — counterfactual play attribution (`analysis/play_counterfactuals.py`)

Every archived game is reconstructed to the state before each `play_bird`
decision by the study agent (the replay validator's own path). Three branches
are rolled out to the end of the game under the same cheap continuation
policies for both seats:

| Branch | Meaning | Contrast |
|---|---|---|
| actual | the bird played as recorded | — |
| not now | the bird withheld this turn only; may be played later | `actual − not_now` = **timing value** |
| never | the bird removed from hand before deciding | `actual − never` = **card value in context** |

Each row also records the immediate score delta, the board and hand before
the play, and the bird's own end-of-rollout ledger — eggs, cache, tucks,
activations and the new `power_yield` — so value splits into what the card
did on arrival and what it did afterwards. First run: 382 archived
`potential_points` games (~9 s each with one-ply continuations).

The continuation policy defines the value. This run's number is "what the
play was worth to a competent, non-searching continuation"; a searching
continuation on a sample is the check. Per-play values are noisy by
construction (one deterministic path per branch), so the deliverable is the
aggregate: per bird, per mechanic, and per (bird, board-composition).

### Activation ledger (`BirdSlot.power_yield`, `bird_scorecard`)

Since 2026-09-16 every power resolution credits its owner-level deltas
(food, cards, eggs, tucked, cached) to the bird, alongside an activation
count. Both fields are excluded from state dumps so archived hashes and
replays are unchanged; the `bird_scorecard` event carries them at game end.
Nested resolutions (a repeater's target) count as activations but are
credited to the repeater, so the ledger sums to the player's counters.

## Model Plan

### Mechanic-level interactions with shrinkage (layer B model)

Card-pair effects are sparse; mechanic-pair effects are not. Each card is
described by its mechanics (power handler key, habitat, nest, food types,
egg capacity, predator/flocking, tuck/cache/draw/lay). The play-attribution
dataset is fitted as

```text
card_advantage ~ bird + mechanics(bird) × mechanics(board) + round + agent
```

with card-pair random effects shrunk toward their mechanic-pair interaction —
a hierarchical model, done in R. The synergy matrix from layer A enters as a
prior mean for the pair effect, so the two evidence sources combine rather
than compete. A rare pair that the bench scores high and that the data has
seen twice gets a posterior that says so, with the uncertainty attached.

### Partial combos

The value of *holding* the first card of a pair is the difference between the
card-advantage of the second card when the first is on the board and when it
is not — both directly estimable from the same dataset — and the value of
*completing* it is the second card's advantage conditional on the first.

## Layer C — confirmation by forced play

Pairs that score high in A and B are confirmed with the forced-keep
instrument generalized to plays: force keep-and-play of A then B against the
agent's free choice, paired by seed. Only combinations that survive all three
layers enter the agent.

## The Agent

`SynergyPlannerAgent` = `PotentialPointsAgent` + an **engine-potential term**
in the evaluator and the opener: the predicted downstream value of the current
board + hand from the fitted synergy model, replacing the standalone
`engine_power_potential` and `playable_bird_potential` where the model is
confident. It is built behind a switch, ablated in the usual 80-game paired
design against `rr_belief_opp`, and adopted only on a positive result.

Registered prior: four resource-valuation terms have landed null, but the one
card-choice term measured so far paid; a synergy term is a card-choice term.
Prediction to register before the arm: +1 to +3 points, concentrated in bird
points and eggs, with draws rising as the agent holds partial combos.

## Telemetry

- `bird_scorecard` per player at game end: `power_yield`, `activations`,
  `round_played`, tokens per bird.
- Play-attribution rows: `artifacts/play_counterfactuals/*.jsonl`
  (`timing_advantage`, `card_advantage`, `immediate_delta`, `ledger_at_end`,
  `board_before`).
- When the agent exists, its decision summary will record the synergy term's
  contribution per candidate so the ablation can tell which plays it changed.

## Evaluation Plan

1. Layer A: full bench, top-50 pairs, cross-check against the archived
   `power_yield` for pairs that did co-occur.
2. Layer B: per-bird card and timing advantage over 382 games; agreement with
   the observational ridge (`bird_value_regression.py`) and with layer A's
   engine yields; immediate-vs-downstream split by round.
3. Hierarchical model in R; held-out prediction of card advantage on the
   engine-builder deals.
4. Layer C forced-play arms for the top combinations.
5. Agent ablation, 80 games paired, registered prediction above.

## Caveats

- Layer A measures one activation in two contexts; multi-turn chains, on-play
  and reactive powers are not yet benched.
- Layer B's counterfactuals are exact but path-dependent: a single different
  action changes the whole deterministic continuation, so per-play values
  carry butterfly variance. Aggregate before reading; a determinized
  continuation (several samples per branch) is the fix if the aggregates
  are too noisy.
- Value is defined by the continuation policy; a searching continuation may
  price engines higher.
- Two players, one roster, base game.
