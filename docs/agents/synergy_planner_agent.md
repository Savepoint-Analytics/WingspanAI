# Synergy Planner Agent

Status: research programme defined, instruments built, layers A and B run with first results, 2026-09-16/17. Layer C (forced-play confirmation) and the agent's engine-potential term are next.

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

The bench has four modes (`--mode`): `same_row` (above); `cross` — A alone
in one row and B alone in another, both rows activated once in each order,
against the same two activations with blanks; `onplay` — a white on-play bird
played next to A against next to a blank (board-composition effects such as
"lay an egg on each bird with a cavity nest"); `pink` — a pink reaction bird
on the board while the opponent lays eggs, gains food or plays a bird, alone
and next to a same-row partner (the cowbird class needs a partner with the
right nest). Pink reactions are now also credited to the activation ledger.
Triples seeded from the pair matrix remain the next extension.

**Capacity-aware context (2026-09-17).** `--contexts capped` pre-fills every
row with two egg-full blanks and starts the placed birds one egg below their
own limit. In grassland, **830 ordered pairs with positive egg synergy under
rich/scarce fall to 34 when capped** (mean egg synergy 0.94 → 0.04), and the
layer C P3 pair — Baird's Sparrow next to Northern Mockingbird, +2.00 eggs per
activation with room — reads **0.00**. The bench's egg synergies were the
value of egg room, not of the pair, which is exactly what layer C found in
play. A pair's synergy is a function of the board's spare capacity; the
bench now reports it at both ends, and the realized value sits between them
weighted by how often the cap binds — often, for an egg-laying agent.

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

## Layer C — confirmation by forced play (`agents/forced_play.py`)

Pairs that score high in A and B are confirmed by making them happen.
`inject_opening_cards` swaps named birds into a player's dealt hand from the
deck (recorded in `game_started`, re-applied by the replay validator so
hashes verify); `KeepBirdsSetupPolicy` keeps them, displacing the opener's
birds rather than its food; `ForcedPlayAgent` plays them into a shared row as
soon as legal, waits rather than split the pair when the row is not yet
enterable, steers gain-food toward a waiting bird's fixed cost, and never lets
a forced play consume its partner's food. Flows take `opening_hand_overrides`
and `forced_play_birds` per agent kind.

The design is a 2×2 per seed with matched non-interacting controls,
`{A, B}, {A, B'}, {A', B}, {A', B'}`, and the interaction contrast
`(AB − AB') − (A'B − A'B')` (`analysis/forced_play_contrast.py`) isolates
what the combination is worth beyond each card's own value; forcing is
identical in every arm, so it cancels. Intention-to-treat is the headline;
the completed-pair estimate and the completion rate are reported beside it.
Pairs and controls for the first run, with registered predictions:

| Pair | Mechanics | Evidence | Controls | Prediction |
|---|---|---|---|---|
| P1 Common Grackle + Cooper's Hawk | tuck × deck-search-tuck | layer B +3.0 | Eastern Phoebe / Yellow-Bellied Sapsucker | +1 to +3 |
| P2 Canvasback + Anhinga | all-players-draw × predator | layer B +3.4 | Black-Chinned Hummingbird / Osprey | 0 to +2 |
| P3 Baird's Sparrow + Northern Mockingbird | lay-egg-any × repeat | layer A +2 eggs/activation | Eastern Phoebe / Indigo Bunting | > +2 |

Only combinations that survive all three layers enter the agent.

### Layer C results (2026-09-17)

First run (60 seeds) measured the instrument rather than the pairs: Common
Grackle's tuck-from-hand power was tucking Cooper's Hawk out of the hand, and
the food grant was overwritten by the opening choice, so P1 completed in 11
of 60 seeds and read −8.25. Fixed (`d2ad2d1`): the wrapper rejects any action
whose resolution removes a waiting forced bird from hand, steers to lay-eggs
when the shared row needs one, and `opening_food_bonus` (2 of each, every
arm, so it cancels) is granted after setup and replayed. Completion rose to
88–95%.

Second run, 240 seeds per pair, `archetype_engine_builder` vs greedy:

| Pair | Interaction (ITT) | p | On completed seeds | Completion | Verdict |
|---|---:|---:|---:|---:|---|
| P1 Common Grackle + Cooper's Hawk | −1.06 | 0.41 | −0.68 (p=0.61) | 227/240 | null |
| P2 Canvasback + Anhinga | **+3.48** | **0.021** | +2.00 (p=0.20) | 210/240 | positive |
| P3 Baird's Sparrow + Northern Mockingbird | **−3.38** | **0.005** | −3.23 (p=0.010) | 228/240 | **negative** |

Main effects came out as expected (Cooper's Hawk +3.5 over the sapsucker,
Anhinga +5.0 over Osprey, Baird's Sparrow +10.0 over Eastern Phoebe — an egg
engine for this agent), so the design resolves card value; it is the
interactions that split.

What the split says:

- **P2 confirms layer B.** All-players-draw next to a predator, in the same
  wetland row, is worth about +3 to a cheap pursuer — the same +3.4 the
  counterfactual attribution measured. One of three pairs surviving all
  three layers is the honest confirmation rate.
- **P1 does not.** The tuck × deck-search-tuck effect measured under a
  one-ply continuation on the searching agent's plays does not appear when
  a non-searching agent plays the pair. Either it needs the pursuer to
  plan around it, or layer B's +3.0 was a pursuer artefact — the same
  pursuit confound the bonus-card study found.
- **P3 reverses, and the reason is general.** The bench scored +2 eggs per
  activation on an egg-empty board. In play, egg capacity binds: the sparrow
  holds 2, the mockingbird 4, the grassland action already lays 2 a turn,
  and the repeated "lay an egg on any bird" hits the cap while the
  mockingbird's slot and cost displaced a bird that gains food. **A synergy
  that spends a shared cap is worth only what the cap allows** — the
  "partial combo" question again, from the other side. Layer A needs a
  capacity-aware context (a full board, eggs near limit) before its egg
  synergies mean anything.

## The Agent

`SynergyPlannerAgent` = `PotentialPointsAgent(mechanic_synergy=True)`: the
evaluator gains `mechanic_synergy_potential`, built from
`configs/synergy/mechanic_pair_effects_v1.json` (584 shrunken
played-power × board-power effects from the lme4 fit). For the board it sums
the measured effect between every pair of played birds, scaled by the turns
left in the round like every other term; for the hand it credits each card's
positive lift against the current board (or its first-play value on an empty
board) at a 0.6 play rate. Threaded through the search's terminal values, the
config and the manifest; off by default; ablated in the 80-game paired design
against `rr_belief_opp` (`artifacts/rr_synergy_term`).

### Result of the first ablation (2026-09-17): a clear negative

| | baseline | with term | Δ | p |
|---|---:|---:|---:|---:|
| `potential_points` score | 78.41 | 73.90 | **−4.51** | **0.001** |
| win rate | 0.875 | 0.800 | −0.075 | 0.14 |

Negative against all four opponents (−6.75 vs bonus-focus, p=0.01; −4.70 vs
net-value, p=0.03). The registered prediction (+1 to +3) failed outright.
The mechanism engaged exactly as designed and that is what cost the points:
draws rose from 24.3% to 27.9% of turns while plays and egg-lays fell, bird
points −2.8, round goals −0.9, eggs −0.8 — and tucked cards −0.5, so the
tuck engines the term was built to reward produced *fewer* tucks.

Diagnosis, in order of likelihood:

1. **The hand term pays for holding.** Crediting each hand card's potential
   lift at a 0.6 play rate rewards *having* combo pieces, so the evaluator
   prefers drawing toward a combination over laying eggs or playing the
   bird in front of it. The search then compounds the preference.
2. **Double counting with the search.** The mechanic-pair effects were
   measured under a one-ply continuation; a depth-3 search already realizes
   part of that downstream value when it looks ahead, so adding it again
   inflates every engine-shaped line.
3. **Effects measured on a different pursuer.** The table comes from plays
   made by the searching agent but valued by the one-ply continuation; the
   same pair may be worth less to an agent that already plans.

Standing decision: the term stays off. The next variant worth one arm is
**board-only** (drop the hand term entirely) with the board effects halved,
which tests (1) and (2) at once; if that is also negative, the synergy
evidence belongs in the opener and the draw choice (card-selection
decisions, where card-choice terms have paid) rather than in the evaluator.

Registered prior: four resource-valuation terms have landed null, but the one
card-choice term measured so far paid; a synergy term is a card-choice term.
Prediction to register before the arm: +1 to +3 points, concentrated in bird
points and eggs, with draws rising as the agent holds partial combos.

## First Results (2026-09-16/17)

### Layer B: 2,698 plays, 382 archived `potential_points` games

| | card value | immediate | downstream | timing value |
|---|---:|---:|---:|---:|
| all plays | **+4.21** (SE 0.17) | +5.16 | −0.95 | **+1.42** (SE 0.15) |
| round 1 (772) | +6.00 | +4.52 | **+1.48** | +1.16 |
| round 2 (590) | +4.13 | +4.41 | −0.29 | +1.42 |
| round 3 (773) | +3.25 | +5.40 | −2.15 | +1.29 |
| round 4 (563) | +3.13 | +6.51 | **−3.38** | +1.96 |

The shape is the finding: a play's printed and on-arrival value overstates
it more the later it comes, because the alternative (laying eggs, mostly)
was worth more; in round 1 the downstream share is positive — the engine
is real — and the value of *when* you play (timing) is a steady 1–2 points
throughout. Plays whose bird went on to activate three or more times
(1,145 of 2,698) are worth +4.9 against +4.3 on arrival.

Per bird, shrunken by the hierarchical model (points above the mean play):
Brown Pelican +6.2, Turkey Vulture +5.6, Barn Swallow +5.4, Common Grackle
+5.4, Black-Billed Magpie +5.1, Golden Eagle +5.0, Black Vulture +4.8; at
the bottom Northern Harrier −4.6 (n=36), Mourning Dove −4.8, and thin
extreme cases (Mallard, two plays, −42 raw). Variance components: bird SD
3.0, mechanic-pair SD 1.8, residual SD 4.7 per play.

Mechanic-pair interactions (played power × power already on board, shrunken):
`tuck_card × deck_search_tuck_by_wingspan` **+3.0** (n=51),
`all_players_draw_cards × predator_hunt` +3.4 (n=32),
`play_additional_bird × predator_hunt` +3.4 (n=20); and the strongest
"first play" effects on an empty board: `deck_search_tuck_by_wingspan` +5.2,
`lay_egg` +5.1, `gain_food_from_birdfeeder` +4.7. Tuck engines compound;
the first engine bird is the most valuable play of the game.

### Determinized continuations: the K=0 pair table was mostly noise (2026-09-17)

Re-running the attribution with four determinized continuations per branch
(`--continuation-samples 4`, 12 rollouts per play) leaves the aggregate
unchanged and removes a large share of the per-play noise:

| | K=0 | K=4 |
|---|---:|---:|
| mean card value / timing value | +4.21 / +1.42 | +4.27 / +1.62 |
| within-bird SD (588 matched plays) | 8.28 | **5.27** |
| lme4 residual SD | 4.69 | **3.03** |
| bird SD / mechanic-pair SD | 3.04 / 1.82 | 2.33 / 1.16 |
| per-bird rank agreement, K=0 vs K=4 | | ρ = 0.54 |
| mechanic-pair rank agreement (n ≥ 10) | | **ρ = 0.31** |

The round-level shape is robust (round-1 downstream +0.9, round-4 −3.2,
timing a steady +1.5), and so is the top of the bird table (Barn Swallow,
Turkey Vulture, Black Vulture, Black-Billed Magpie). The mechanic-pair
effects are not: `tuck_card × deck_search_tuck` goes **+2.96 → −0.04** and
`all_players_draw_cards × predator_hunt` **+3.39 → −0.18**. The K=0 table
that chose two of layer C's three pairs and fed the engine-potential term was
largely path noise. `configs/synergy/mechanic_pair_effects_v2.json` (from
the K=4 fit) replaces v1 as the term's table; nothing has been re-measured
with it yet. Read together with layer C: P1's null now matches the K=4
table; P2's +3.48 (p=0.021, one of three tests) is the single surviving
positive and is borderline once corrected for three comparisons.

### Observed value is not causal value

The counterfactual card value correlates at **ρ = 0.07** with the
observational ridge coefficient (`bird_value_regression.py`) over the 106
birds both cover. Turkey Vulture is the clearest case: −6.7 against the
average bird observationally, **+5.6** causally — it is played in losing
positions (a pink predator reaction is what you play when you have nothing
better), but playing it helps. The observational layer measures who plays
a bird and when; the counterfactual layer measures what the play does. Only
the second belongs in an agent's evaluator.

### Layer A meets layer B

Bench single-bird power yield correlates ρ = 0.20 with counterfactual card
value over 70 brown birds — right sign, weak, as expected for a one-activation
bench against whole-game value. Card-pair context lift is too sparse to
compare pairwise at n ≥ 10 (nine pairs); the mechanic-level table is where
the two evidence sources meet, and `tuck_card × deck_search_tuck` is the
first pair both the bench (tuck engines) and the data (+3.0) call out.

Outputs: `artifacts/play_counterfactuals/summary.md`,
`artifacts/play_counterfactuals/hierarchical/{bird_effects,mechanic_pair_effects}.csv`
(`analysis/r/play_attribution_hierarchical.R`, lme4; empirical-Bayes
shrinkage, not a full posterior).

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

## Where the programme stands (2026-09-17)

Three instruments built and validated; one first-order result per layer.
Layer A: 12,386 same-row pairs benched, plus cross-row, on-play and pink
modes; egg synergies need a capacity-aware context (P3). Layer B: 2,698
plays attributed, twice; the aggregate shape is robust and the per-pair
table needed determinized continuations to mean anything. Layer C: the
instrument works (88–95% completion after two fixes) and confirmed one of
three pairs. The engine-potential term, built on the K=0 table with a
hand-holding term, cost 4.5 points; its next variant (board-only, v2 table,
halved) is a single arm away. The reusable lesson is the one the whole
project keeps finding: measure the instrument before believing the number.

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
