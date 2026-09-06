# Search Depth Experiment: The First Positive Result

Status: complete, 2026-09-05
Code: `5830657` (clean tree; every manifest records it)
Artifacts: `artifacts/rr_depth_<arm>/`, mirrored to object storage

## Why this experiment

Three faithful improvements to `potential_points`' evaluation function — mat
scaling, feeder odds on a corrected six-face die, and resource-spending
selection — each came back null ([resource_spending_ablation.md](resource_spending_ablation.md)).
The standing conclusion was that these agents are not limited by the fidelity
of their resource valuation. This experiment tests the alternative hypothesis:
that they are limited by how far ahead they look.

## What had to be fixed first

Two defects would have made the experiment meaningless as specified.

### `search_depth` was a dead parameter

`_search_action_value` returned the leaf value whenever the active player
changed. `apply_action` always advances the turn, so in every multiplayer game
the "endgame search" stopped after one ply. An instrumented probe over three
games counted 954 search calls, all at recursion level 1; 562 of them were
passed `depth=3`. Varying the knob would have produced a guaranteed null.

The search now plays opponent turns on the owned branch with the deterministic
greedy baseline, then descends to the next own turn, with a beam of four
own-turn continuations below the root. Depth 1 reproduces the previous agent
exactly.

### State copies cloned the whole deck

Depth 2 could not finish one game in nine minutes. A `GameState` deep copy took
47 ms — six times the figure in the compute profile — because
`DeckState.bird_deck` holds 180 full `BirdCard` models and every copy cloned
them all. Content models are now frozen and shared across copies: 0.53 ms.

The depth-1 arm below came out **bit-identical in all 200 games** to the
resource-spending on-arm run before the change, which is the regression check
that the sharing is semantically neutral.

## Design

Same 200-game counterbalanced design as the three ablations: five-agent roster
(`greedy_immediate`, `potential_points`, `net_value_response`,
`archetype_engine_builder`, `archetype_bonus_card_focus`), two players,
`control` setup, seeds 1–10 in 2-seed chunks, every lineup in both seat
rotations. `potential_points` plays 80 of the 200 games per arm.

Two factors on `potential_points`:

- `search_depth` — own turns the search looks ahead: 1 (the historic agent),
  2, 3, 4.
- `final_search_turns` — the search fires when the player has at most this many
  action cubes left in the round: 5 (the historic default) or 8 (every turn).

Games are paired across arms by lineup, rotation and seed
(`analysis/arm_contrast.py`). Only `potential_points` games can differ between
arms; the other 120 must be identical, and were in every contrast.

## Results

Paired score and win contrasts for `potential_points`, n = 80 per arm.

| Arm | Avg score | Δ vs depth 1 | p | Win rate |
|---|---:|---:|---:|---:|
| depth 1, last 5 cubes (historic) | 68.28 | — | — | 0.738 |
| depth 2, last 5 cubes | 75.34 | **+7.06** | <0.001 | 0.844 |
| depth 3, last 5 cubes | 75.66 | **+7.39** | <0.001 | 0.856 |
| depth 4, last 5 cubes | 78.09 | **+9.81** | <0.001 | 0.881 |
| depth 2, every turn | 78.81 | **+10.54** | <0.001 | 0.869 |
| depth 3, every turn | 81.83 | **+13.55** | <0.001 | **0.925** |

Adjacent contrasts:

| Contrast | Δ score | p |
|---|---:|---:|
| depth 3 vs depth 2 (last 5 cubes) | +0.33 | 0.736 |
| depth 3 every turn vs depth 3 last 5 cubes | **+6.16** | <0.001 |
| depth 2 every turn vs depth 2 last 5 cubes | **+3.48** | 0.001 |
| depth 3 every turn vs depth 2 every turn | **+3.01** | 0.005 |
| depth 4 vs depth 3 (last 5 cubes) | **+2.42** | 0.018 |

### Finding 1: the second ply is the big one, but depth is not saturated

Depth 2 is worth seven points over depth 1 against every opponent (+6.2 to
+8.1, each significant at n=20). On the historic last-five-cubes trigger, depth
3 adds nothing measurable (+0.33, p=0.74), yet depth 4 adds +2.4 over depth 3
(p=0.018), and when the search fires on every turn, depth 3 beats depth 2 by
+3.0 (p=0.005). So the depth-2/depth-3 plateau is not saturation; it is a
feature of where the last-five trigger places the leaves. A plausible reading
is that on the last five cubes a third own-turn ply usually ends at or across
the round boundary, where the round-scoped evaluator (see caveats) has little
left to discriminate, while a fourth ply reaches the round's final placements.
That reading is untested; what the data support is that more depth keeps
paying, unevenly, and the gain depends on the trigger.

Wall-clock per game is not reported: the arms ran with two to four batches
sharing one machine, so timings are not comparable across arms.

### Finding 2: when the search fires matters as much as how deep

With the historic trigger, the search skips the first three turns of round 1,
two of round 2, and one of round 3 — the engine-building turns. Searching every
turn adds +3.5 at depth 2 and +6.2 at depth 3 on top of the depth gain; depth 3
on every turn takes the win rate against this roster to 0.925. The two factors
interact: coverage is worth more when the search is deeper, and depth is worth
more when the search covers the whole round.

### Where the points come from

| Category | d1 | d2 | d3 | d4 | d2, every turn | d3, every turn |
|---|---:|---:|---:|---:|---:|---:|
| bird | 32.76 | 35.84 | 36.83 | 37.10 | 36.80 | 36.16 |
| round goal | 12.72 | 14.54 | 14.29 | 14.44 | 15.12 | 15.89 |
| egg | 10.39 | 11.70 | 10.84 | 12.01 | 11.85 | 13.12 |
| tucked | 4.14 | 4.59 | 4.49 | 4.34 | 4.84 | 5.59 |
| bonus | 5.08 | 5.40 | 5.99 | 6.75 | 6.31 | 6.72 |
| cached food | 3.19 | 3.27 | 3.24 | 3.45 | 3.89 | 4.34 |
| total | 68.28 | 75.34 | 75.66 | 78.09 | 78.81 | 81.83 |

(d1–d4 use the last-five-cubes trigger.)

Depth buys bird points and round goals: two-ply search on a round's last two
cubes sees the goal being scored at the leaf and places eggs against it.
Searching every turn buys engine output — eggs, cached food, tucked cards —
with bird points flat. The agent's draw share falls with search coverage —
29.2% (depth 1), 27.2–27.5% (depths 2–4), 24.5% (every turn, at either depth) —
while bird plays and egg lays rise.

## Caveats that bound the claim

**Information leakage.** The search applies actions to a copy of the full
state. When it evaluates a draw it sees the actual next deck card; the greedy
opponent model plays from the opponent's actual hidden hand. Depth 1 already
had the one-ply deck peek; deeper search widens it. The evidence that the gain
is planning rather than peeking is that draws *fall* as search grows and the
points arrive in eggs, goals and engine output rather than in bird quality —
but that is circumstantial. The definitive test is a determinized search that
shuffles the unseen deck and re-samples the opponent's hand inside each
branch. Until that runs, "+13.55" is an upper bound on the planning benefit.

**Resolved 2026-09-06:** the determinized test
([determinized_search_test.md](determinized_search_test.md)) puts the
leak-free gain at **+10.43** (p<0.001) and the leak at −2.42 (p=0.008). The
depth-1 peek was worth +0.70 (n.s.). Quote +10.4, not +13.5.

**The opponent model is exact against one opponent.** The search models the
opponent as `greedy_immediate`. Against the real `greedy_immediate` that model
is perfect. At depth 3 the gain was larger against `greedy_immediate` and
`net_value_response` (+10.8, +11.5) than against the archetypes (+4.6, +2.7,
n.s.), though at n=20 per cell those differences are not themselves
significant.

**Round horizon.** The evaluator's planning horizon is the current round, not
the game: `_turns_remaining_for_player` returns `action_cubes_available`. At a
round's last cube it discounts all future potential to 0.15× and the search
leaf scores realized points only. This is constant across arms and is the next
ablation candidate; fixing it may change how much search is worth.

**One roster, two players.** As with the three nulls.

## What changes

- `PotentialPointsAgent` defaults stay at `search_depth=3`,
  `final_search_turns=5` for now so existing comparisons remain reproducible;
  a default change should follow the determinization test, not precede it.
- Every future `potential_points` result must state its search configuration;
  manifests now record it under `potential_points_search`.
- The three valuation nulls are reinterpreted: they were measured on an agent
  whose search was one ply. Whether valuation fidelity matters *given* real
  search is an open question, not a settled null.

## Next

1. ~~**Determinized search.**~~ Done; see above.
2. **Game horizon.** Replace the round horizon with remaining game turns and
   ablate.
3. **Re-run one valuation ablation** (feeder odds is cheapest) on the searching
   agent, to test whether the nulls were conditional on the dead search.
