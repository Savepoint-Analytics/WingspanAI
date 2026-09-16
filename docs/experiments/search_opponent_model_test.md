# Belief-Driven Opponent Model in the Search

Status: **planned, prediction registered 2026-09-16; arm not yet run.**
Code: `src/wingspan_ai/agents/search_opponent.py`,
`PotentialPointsAgent(search_opponent_model="greedy" | "belief")`
Baseline: `artifacts/rr_food_cand6/` (the current default agent:
depth 3, every turn, K=4, `search_food_candidates=6`, greedy opponent model)

## Why this experiment

Two open threads point at the same piece of code.

**Compute.** After gain-food pruning
([search_food_candidates.md](search_food_candidates.md)), about 40% of a
`potential_points` decision was the greedy model playing the opponent's turns
inside the search. On every modelled opponent turn it prices every legal
action through `apply_action` — about 16 ms a turn, multiplied across every
node of a depth-3 tree over four determinization samples. Arms per week is
the binding constraint on the project, so this is the next thing to cut.

**The thesis.** `COMPANY_CONTEXT.md` puts Bayesian opponent modelling at the
centre of the project, and `wingspan_ai.belief` has existed since 2026-08-31
with a calibrated posterior over six opponent profiles. But the only agent
that consumed it, `net_value_response`, sits near the bottom of every round
robin, and no experiment has yet shown a belief changing a decision for the
better. The search is the first place in the codebase where a belief can do
real work: the question "what will the opponent do next?" is asked thousands
of times per decision, and currently answered by a fixed greedy heuristic.

## What changed

`BeliefSearchOpponentModel` plays each opponent turn in two steps:

1. **Family.** Compute public candidate values for the four action families
   (the same `_public_response_candidates` template `net_value_response`
   uses), ask the opponent's `OpponentBeliefState` for the marginal
   distribution over families, and take the most likely family that has a
   legal action. Cost ~0.2 ms; reads only `to_public_state` and the posterior.
2. **Action.** Within that family, pick by a proxy that never applies an
   action: printed points less the slot's egg cost for a bird, eggs laid for
   lay-eggs, otherwise greedy's own tie-break (food need, tray-card quality).
   The proxy agrees with greedy inside play-bird on every probe state tested;
   what it drops is points a power would add on activation.

The posterior is updated only from the real game, through the runner's
existing `observe_action` hook, which `PotentialPointsAgent` now implements.
Search branches read it and never write it. Each decision's telemetry records
`search_opponent_model` and the current posterior per opponent, so the arm
is identifiable from artifacts and the belief's sharpening can be inspected.

The greedy model is unchanged and remains the default. A regression test
pins it to `GreedyBaselineAgent` so archived decisions replay bit for bit.

## Registered predictions

Written before the arm runs.

1. **Compute (primary, expected to hold).** Mean `potential_points` decision
   time falls by **≥30%** against the same states. The back-to-back probe
   (`analysis/search_opponent_profile.py`, seed 1 vs `archetype_engine_builder`)
   is the clean measurement; the arm's wall-clock telemetry is the noisy one.
2. **Score (prior: null or small negative).** Paired delta on the 80
   `potential_points` games is within **−1.0 … +1.0 points**, not
   significant. Reasoning: the modelled opponent is cruder within a family
   (no activation points), which should cost about what pruning cost; a
   better-calibrated *family* choice might give it back. Four valuation
   changes in a row have been null; the prior is that this one is too.
3. **Non-inferiority gate.** The switch becomes the default only if the
   paired score delta is **≥ −1.0** and the win-rate delta is not
   significantly negative. A larger loss means the cheaper model is not
   cheap enough to be worth it, and the search-cost problem needs a different
   answer (a cached greedy pick, or a shallower opponent).
4. **Belief sharpening (diagnostic, not a gate).** By the last round, the
   most likely profile in the belief-arm telemetry should be
   `value_maximizing` against `greedy_immediate` and `engine_builder` against
   `archetype_engine_builder` in a majority of games. If the posterior stays
   near uniform, the family choice is driven by the priors and candidate
   values alone, and the result says nothing about *Bayesian* modelling.

What would make the compute result uninteresting: if the reduction is real
but the score loss exceeds the pruning loss, the right comparison is
`search_food_candidates=None` plus the belief model against the current
default, and that has to be run before either is adopted.

## Design

Reduced paired design, identical to the last two arms: the four two-agent
lineups containing `potential_points`, both seat rotations, seeds 1–10, `control`
setup — **80 games**, contrasted against the same 80 inside `rr_food_cand6`
with `analysis/arm_contrast.py`. The 120 games without `potential_points` are
bit-identical by construction and are not re-run.

Arm settings: agent defaults plus
`PotentialPointsSearchConfig(search_opponent_model="belief")`, passed
explicitly so the manifest records it. Run from a clean worktree at the
committed revision with an absolute `workbook_path`. Chunked as before:
three lineup groups × five two-seed chunks.

```python
from flows.round_robin import run_round_robin
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

run_round_robin(
    roster=["potential_points", "greedy_immediate"],   # then the other three lineups
    seeds=[1, 2],
    setup_policy_kinds=["control"],
    artifact_root="artifacts/rr_belief_opp",
    batch_label="rrbelief_grepot_s1_2",
    potential_points_search=PotentialPointsSearchConfig(search_opponent_model="belief"),
)
```

```bash
python analysis/arm_contrast.py --baseline artifacts/rr_food_cand6 --arm artifacts/rr_belief_opp
```

## Compute probe (prediction 1: holds)

`analysis/search_opponent_profile.py --seed 1 --opponent archetype_engine_builder`,
one process, both models timed back to back on each of the 26 `potential_points`
decisions along the greedy-modelled agent's trajectory. Machine load was ~7 on
8 cores throughout, so absolute times are inflated; the ratio is not.

| | greedy model | belief model |
|---|---:|---:|
| total decision time | 142.9 s | **84.2 s** |
| mean decision | 5.50 s | 3.24 s |
| worst decision (48-action root) | 32.5 s | 20.5 s |
| reduction, all 26 decisions | | **41.1%** |
| reduction, 11 decisions over 5 s | | 40.8% |
| same action chosen | | 24 of 26 (92.3%) |

The reduction clears the registered 30% and is larger than the 40% share
estimated from profiling, because the opponent model is paid at every node of
the tree and its share grows with depth. The two decisions that differed were
at turns 5 and 22, both in the first two rounds; every endgame decision agreed.

**Diagnostic worth carrying into the arm.** After 25 observations of
`archetype_engine_builder`, the posterior sat at `food_acceleration` 0.9995,
`engine_builder` 0.0000. Two readings, both probably true: the archetype does
gain food on a plurality of turns (36% gain-food, 26% play-bird over five games vs greedy), so
the label is behaviourally defensible; and the posterior is far too confident,
because each observation is scored as an independent draw from hand-tilted
profile priors that were never fitted to this roster. Prediction 4 as written
(the most likely profile "should be `engine_builder`") is therefore the wrong
test; the honest version is whether the posterior *concentrates*, and whether
the family it predicts matches the family the opponent actually plays. The
2026-08-31 follow-up "refit belief family priors per opponent kind from
round-robin telemetry" is the fix and is still open.

## Result

_Not yet run._
