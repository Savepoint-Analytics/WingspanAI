# Bounding Gain-Food Continuations in the Search

Status: complete, 2026-09-07. **Adopted for compute, at a measured cost of ~1 point.**
Code: `4506bdf` (clean tree; every manifest records it)
Artifacts: `artifacts/rr_food_cand6/`, baseline `artifacts/rr_reroll_fix/`

## Why this experiment

Search depth and coverage were the project's first positive result
([search_depth_experiment.md](search_depth_experiment.md)), and the defaults
moved to `search_depth=3, final_search_turns=8, determinization_samples=4`.
The bill arrived with them: in the reroll-fix arm, `potential_points` spent
**551 s per game** deciding, with a worst single decision of **1262 s** and a
worst game of **70 minutes**. At that price a 200-game arm is a day of laptop
time, which is the binding constraint on every experiment that follows.

Profiling the heaviest decisions put the cost in branching, not depth. One
decision issued 15,429 `apply_action` calls, about half the time in state
copying. The cause is gain-food preference actions: when the birdfeeder cannot
pay a bird's cost outright, the legal-action generator enumerates preference
multisets, 5/15/35/70 of them depending on how many dice are wanted. Measured
over the 2,080 `potential_points` decisions in this arm, a root has a median of
4 gain-food options but a mean of 10.7, a 90th percentile of 36, and a maximum
of **100** (of 134 legal actions). Every node in the search re-listed them, so
the multisets multiplied down the tree.

## What changed

`PotentialPointsAgent.search_food_candidates` (default **6**, `None` restores
the old behaviour). Below the root, the search keeps every non-gain-food action
plus the best N gain-food actions, ranked by expected demand-weighted units:
`Σ expected units × (1 + hand demand for that food type)`, where the expectation
comes from `expected_gain_food` — the same chance-node model the reroll fix
introduced ([reroll_chance_node.md](reroll_chance_node.md)). The root still
scores every legal action, so the agent's own move is never pruned away; only
its imagined continuations are.

On a 40-action probe decision the change took **33.7 s → 9.4 s**. About 40% of
what remains is the greedy opponent model, which evaluates all of its own legal
actions on each modelled opponent turn (~18 ms per turn); that was left alone
to keep this to one variable.

Pruning binds on **30% of `potential_points` roots** (those with more than six
gain-food options) and on their descendants.

## Design

Reduced paired design: only the four two-agent lineups containing
`potential_points`, both seat rotations, seeds 1-10 — **80 games**, contrasted
against the same 80 games inside the 200-game `rr_reroll_fix` baseline. A game
depends only on (lineup, rotation, seed), so the 120 untouched games are
identical by construction and are not re-run. Paired with
`analysis/arm_contrast.py`. Arms ran from a separate git worktree at `4506bdf`;
all 40 manifests record `dirty: false`.

## Result: a small negative, not a null

| Metric | baseline | pruned | Δ | p |
|---|---:|---:|---:|---:|
| Avg score | 79.09 | 78.10 | **-0.99** | 0.074 |
| Win rate | 0.906 | 0.863 | **-0.044** | 0.048 |

Identical outcomes: 46 of 80. By opponent, every cell is negative and none is
significant at n=20: `archetype_bonus_card_focus` -1.35, `net_value_response`
-1.30, `archetype_engine_builder` -0.65, `greedy_immediate` -0.65.

The honest reading is a real but small cost, of the order of one point.
The score contrast is not significant at 0.05 and the win contrast barely is;
with four negative cells out of four, treating this as a null would be wishful.

### Where the point goes

| Category | baseline | pruned | Δ |
|---|---:|---:|---:|
| bird | 35.94 | 35.81 | -0.13 |
| round goal | 16.04 | 15.57 | -0.47 |
| egg | 13.11 | 12.90 | -0.21 |
| bonus | 5.71 | 5.66 | -0.05 |
| tucked | 4.91 | 5.06 | +0.15 |
| cached food | 3.38 | 3.09 | -0.29 |
| total | 79.09 | 78.10 | -0.99 |

The loss is round goals and engine output, which is what a food-planning
restriction should cost: the pruned branches are the ones where an unusual food
mix would have set up a goal or a cache. The action mix barely moves
(`gain_food` 20.3% → 20.6%, `play_bird` 28.4% → 28.3%, `lay_eggs` 27.5% →
27.3%, `draw_cards` 23.8% both), so the agent is not playing a different game;
it is planning the same one slightly less well.

## What it buys

`potential_points` decision cost, 2,080 decisions per arm:

| | baseline | pruned |
|---|---:|---:|
| mean | 21.20 s | **17.47 s** |
| median | 6.74 s | 6.78 s |
| p95 | 79.7 s | 69.9 s |
| p99 | 234.4 s | 161.3 s |
| max | 1261.7 s | **491.5 s** |
| per game | 551.3 s | 454.1 s |
| worst game | 4230 s | 1788 s |
| arm total | 12.25 h | 10.09 h |

The median is untouched — most decisions never hit the branching problem — and
the tail is cut by a third to a half. **These figures understate the gain:**
the pruned arm ran concurrently with the feeder-odds arm on one laptop, while
the baseline had the machine to itself. The back-to-back probe (33.7 s → 9.4 s)
is the cleaner measurement of the same change.

## Decision

`search_food_candidates=6` **stays the default**, and this document is the
receipt for what it costs. The reasoning is that the constraint on this project
is arms per week, not the last point of agent strength, and a third off the tail
is worth ~1 point of a 78-point agent.

Two rules follow:

- Any headline claim about how strong `potential_points` *is* should use
  `search_food_candidates=None`, or state that the number is the pruned agent's.
- Any contrast between arms is unaffected as long as both arms share the
  setting, which is why the feeder-odds re-run
  ([feeder_odds_search_rerun.md](feeder_odds_search_rerun.md)) is baselined on
  this arm rather than on `rr_reroll_fix`.

Revisit if: the cost grows in a design with more players or more birds in play
(more gain-food options, so more pruning); a cheaper opponent model removes the
other 40% of the search cost and makes a larger N affordable; or the ranking
heuristic is replaced by something that does not depend on current hand demand.

## Caveats

- Manifests record `potential_points_search: null` for these arms, meaning
  "agent defaults", because no explicit config was passed. The per-decision
  `agent_decision_summary` payload records `search_food_candidates: 6` on all
  2,080 decisions, which is what proves the arm.
- One roster, two players, n=80.
- The ranking is a heuristic on expected units and current hand demand. It does
  not know about bird powers that consume specific food later, so a branch that
  would have been valuable two turns out can be pruned.

## Next

1. **N=12 arm** if the ~1 point matters: it would still cut the 35- and 70-action
   nodes by 3-6x. 80 games, ~10 h.
2. **Cheap opponent model in the search** — the remaining 40%. A single-action
   greedy shortcut would not change the modelled opponent's choice in most
   positions and would make deeper or wider search affordable.
