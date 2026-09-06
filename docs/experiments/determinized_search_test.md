# Determinized Search Test: Was the Search Gain Planning or Peeking?

Status: complete, 2026-09-06
Code: `0b03196` (clean tree; recorded in every manifest)
Artifacts: `artifacts/rr_det_d3_f8_k4/`, `artifacts/rr_det_d1_f5_k4/`, mirrored to object storage
Predecessor: [search_depth_experiment.md](search_depth_experiment.md)

## The question

The search-depth experiment found +13.55 points for `potential_points` at
depth 3 searching every turn. That number was flagged as an upper bound: the
search applies real actions to the full state, so it sees the true next deck
card and plays the opponent from their real hidden hand. This test asks how
much of the gain survives when the search cannot read hidden information.

## Method

`determinization_samples=K` on `PotentialPointsAgent`
(`wingspan_ai.agents.determinization`). For each decision the agent builds K
copies of the state in which the bird deck is pooled with opponents' hands and
redealt, and the bonus deck is pooled with opponents' bonus cards and redealt.
Every legal action is scored on every sample through the same scoring path as
before — search value inside the trigger window, potential delta outside — and
the scores are averaged. Sample seeds derive from `random_seed`, the global
turn number, the player and the sample index, so seed-matched batches remain
paired. `K=0` reproduces the archived depth-3 outcomes exactly (verified through
the batch flow on seeds 1–2 of both trigger settings).

What the sample assumes the player knows: own hand and bonus cards, all boards,
food, eggs, the tray, the feeder, the round goals, opponents' hand and
bonus-card counts, and the discard piles. What it forgets: which tray cards an
opponent took in public. The sample is therefore slightly *less* informed than
a perfect-memory player.

**Residual leak, not closed.** Birdfeeder rolls are seeded from `random_seed`
and the turn number, and the legal-action generator already bakes the reroll
outcome into each gain-food action. Resampling the seed made the true state's
actions illegal on the sample, so the seed is left alone and future rolls stay
visible to the search. Every agent in the roster chooses "reroll" already
knowing the result; that is a rules-engine fidelity defect with its own
follow-up, and it is constant across all arms here.

Two arms, K=4, same 200-game counterbalanced design, paired by lineup,
rotation and seed:

- `d3_f8_k4`: depth 3, search every turn, determinized.
- `d1_f5_k4`: depth 1, last five cubes (the historic agent), determinized. The
  historic agent already peeked one card ahead on draws, so the clean search
  contrast is determinized-vs-determinized, not determinized-vs-historic.

The 120 games without `potential_points` were bit-identical across every arm.

## Results

`potential_points`, n = 80 paired games per contrast.

| Contrast | Score | Δ | p | Win |
|---|---:|---:|---:|---:|
| historic (d1, last 5, true state) | 68.28 | — | — | 0.738 |
| d1, last 5, determinized | 68.97 | +0.70 vs historic | 0.471 | 0.725 |
| d3, every turn, true state | 81.83 | +13.55 vs historic | <0.001 | 0.925 |
| **d3, every turn, determinized** | **79.40** | **+10.43 vs determinized d1** | **<0.001** | **0.900** |
| | | −2.42 vs true-state d3 | 0.008 | |
| | | +11.12 vs historic | <0.001 | |

Per opponent, determinized d3 vs determinized d1: `archetype_bonus_card_focus`
+12.6, `net_value_response` +11.1, `greedy_immediate` +9.5,
`archetype_engine_builder` +8.6, every one p ≤ 0.001.

### The gain is search

Three quarters of the perfect-information gain survives determinization, and
the leak-free contrast is significant against every opponent. **Roughly +10
points of the +13.5 was planning; roughly +2.4 was reading hidden cards.** The
+13.55 number should not be quoted again without that split.

### The depth-1 peek was worth nothing

Determinizing the historic agent moved it +0.70 (p=0.47). Its one-ply draw
evaluation was already effectively leak-free, which means the three valuation
ablations that used it as a baseline were not contaminated by the leak.

### Where the leak lived

| Category | d3 every turn, true state | d3 every turn, determinized | Δ |
|---|---:|---:|---:|
| bird | 36.16 | 35.67 | −0.49 |
| bonus | 6.72 | 5.75 | **−0.97** |
| round goal | 15.89 | 15.70 | −0.19 |
| egg | 13.12 | 13.07 | −0.05 |
| cached food | 4.34 | 3.66 | **−0.68** |
| tucked | 5.59 | 5.54 | −0.05 |
| total | 81.83 | 79.40 | −2.42 |

The leak paid mostly in bonus-card points — knowing which cards were coming
let the search draw toward bonus-card matches — and in cached food, presumably
from knowing which caching birds would arrive. Eggs, round goals and tucked
cards, which carried the coverage gain in the depth experiment, were untouched.
The action mix is also unchanged by determinization (draw 24.3%, food 20.6%,
eggs 26.7%, bird 28.4%).

Per opponent the leak was worth about 3 points against three opponents and
nothing against `archetype_bonus_card_focus` (+0.45, p=0.81), which is the one
opponent whose strategy depends on its own hidden bonus cards. That is
consistent with the leak being about the deck rather than the opponent's hand,
but at n=20 per cell it is a hint, not a finding.

## What changes

- The headline search result is **+10.4 points, win rate 0.90**, from the
  determinized configuration `search_depth=3, final_search_turns=8,
  determinization_samples=4`. This is the strongest leak-free configuration
  measured and the recommended new default.
- `search_depth_experiment.md` is annotated to point here; its "upper bound"
  caveat is resolved.
- The determinization module is agent-agnostic and can back Monte Carlo
  rollouts or any future search agent.

## Caveats that remain

- Feeder rolls are still visible (above). Closing that requires the rules
  engine to resolve rerolls as a chance node in `apply_action` rather than in
  legal-action generation.
- The opponent model is the greedy baseline, played from a resampled hand.
- The evaluator's planning horizon is still the current round.
- K=4 was chosen for compute, not tuned. More samples would reduce decision
  noise; whether that adds points is untested.
- One roster, two players, as with every result in this series.
