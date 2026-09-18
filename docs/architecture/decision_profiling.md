# Decision Profiling and Value per Millisecond

Status: built 2026-09-17. Profiling is on (`summary` mode) for every batch by
default; the report runs over any artifact root.

## Why

A shipped agent is judged on latency as much as strength: a player waiting
ten seconds for a bot's turn stops playing. Until now the project timed each
decision as one number, which says an agent is slow but not why. The rule
from here is **value per millisecond**: every calculation an agent does must
be justified by a measured gain against a measured cost, and the ones that
cannot be justified are dropped, gated to the states where they pay, or
optimized.

## What is measured

### Per decision, always

`agent_decision_summary.action_selection_elapsed_ms` — the wall-clock cost of
`choose_action`, recorded for every decision of every agent since the first
batch. The whole archive has it, which is why the value ledger below could be
computed retroactively.

### Inside a decision: the node tree (`agents/profiling.py`)

A `DecisionProfiler` is active for each decision (`select_action`) and each
opening choice (`choose_initial_selection`). Code records nodes with

```python
with profiling.node("opponent_select"):                  # aggregated: count + total ms
    ...
with profiling.node("score_sample", aggregate=False,     # structural: one tree entry
                    sample_index=i) as node:
    ...
    node.set(candidate_count=len(actions), cache_hit=True)
```

The context manager is a no-op without an active profiler (measured ~0.3 µs),
so instrumentation stays in hot paths permanently. Hot nodes **aggregate**
(one entry per name per parent, with a count) because a depth-3 search visits
thousands of branches per decision; structural nodes stay separate. The
summary reports **self time** (exclusive of children) so shares add up across
nesting, and an `unprofiled_ms` remainder. Overhead measured on a default
decision: 2–3% in either mode, within run-to-run noise. Payload: ~1.5 KB per
decision in `summary` mode, ~5 KB with the tree.

`run_single_game(decision_profile_mode="off" | "summary" | "tree")`, threaded
through the batch and round-robin flows and recorded in every manifest.

Instrumented nodes today:

| Agent | Nodes |
|---|---|
| `potential_points` | `determinize`, `score_sample[i]` / `score_true_state`, `search_root_action`, `immediate_delta`, `branch_legal_actions`, `food_candidate_prune`, `expand_children`, `terminal_value`, `opponent_legal_actions`, `opponent_select`, `opponent_apply`, `evaluate_actions`, `apply_action`, `state_potential` |
| search opponent models | `greedy_opponent_model`, `belief_predict_family`, `belief_within_family_pick` |
| `net_value_response` | `candidate_actions`, `apply_action`, `own_potential`, `opponent_immediate_potential`, `opponent_response`, `denial_value` |
| Monte Carlo | `rollout` |
| guardrails | `guardrail_evaluate` (input/output counts), `base_agent_select` |
| openers | `bonus_card_choice`, `opening_subset_score` |

The layer knows nothing about Wingspan; it belongs to the reusable
board-game template. Another game's agents record nodes the same way and
the same report reads them.

## The report (`analysis/decision_profile_report.py`)

Per agent kind and player count: decisions, mean / p50 / p90 / p95 / p99 /
max latency, seconds per game, latency by round, and — for profiled runs —
the node table (share of self time, ms per decision, calls per decision, ms
per call, cache hit rate). With `--value-against BASELINE_ROOT` it adds the
paired score delta, the latency delta, **points per second of latency** and a
suggested class:

| Class | Rule |
|---|---|
| keep | significant gain, latency ≤ +20% |
| optimize | significant gain at a latency cost |
| drop or gate | no gain, latency > +20% |
| drop | significant loss |
| keep (cheaper) | latency < −20%, no measured loss |

The classes are suggestions from thresholds; the numbers are the deliverable.

## The ledger so far (2026-09-17, from the archive)

Latencies are wall-clock on a shared laptop; arms ran under different load,
so ratios are indicative and back-to-back probes are the clean measure.

| Change | Δ score | p | decision ms | points / s | class |
|---|---:|---:|---:|---:|---|
| search depth 3 every turn vs depth 1 (K=4 both) | +10.43 | <0.001 | 121 → 9,366 | +1.13 per s extra | **optimize** |
| gain-food pruning (6 candidates) vs none | −0.99 | 0.074 | 21,202 → 17,466 | +0.26 per s saved | cost neutral |
| belief opponent model vs greedy | +0.31 | 0.73 | 17,466 → 7,577 | ≈0 per s saved | **keep (cheaper)** |
| board-only synergy term vs none | +1.31 | 0.17 | 7,577 → 8,419 | +1.56 per s extra | cost neutral |
| full synergy term (hand) vs none | −4.51 | 0.001 | 7,577 → 10,066 | −1.81 per s extra | **drop** |
| v2 opener (agent_default) vs control | −3.00 | 0.022 | 7,577 → 5,668 | — | **drop** |

The one entry that matters for production is the first: the search is
worth ten points and costs 77× the latency. Everything else is a
refinement of that trade.

## Where a default decision's time goes

Four profiled games of the default agent vs `archetype_engine_builder`,
104 decisions, `artifacts/profile_default` (a back-to-back single-state probe
agreed within a few points):

| Node | share | ms/decision | calls/decision | ms/call |
|---|---:|---:|---:|---:|
| `expand_children` — `apply_action` on every child of every branch | **73.4%** | 3,261 | 260 | 12.5 |
| `terminal_value` — evaluator on every leaf | **18.8%** | 835 | 4,677 | 0.18 |
| `search_root_action` (own overhead) | 2.5% | 109 | 74 | 1.5 |
| `immediate_delta` | 1.1% | 49 | 74 | 0.66 |
| `opponent_apply` — the same transition **without** a copy | 1.0% | 44 | 260 | **0.17** |
| `branch_legal_actions`, `opponent_legal_actions` | 1.5% | 67 | 260 each | 0.13 |
| `belief_predict_family` + `belief_within_family_pick` | 1.2% | 54 | 260 each | 0.10 |
| `food_candidate_prune` | 0.4% | 18 | 260 | 0.07 |
| `determinize` | 0.0% | 2 | 1 | 1.7 |

92% of a decision is copying states and evaluating leaves, and the copy is
the cost: `expand_children` applies an action *with* a `GameState` deep copy
at 12.5 ms per call, while `opponent_apply` applies one in place at 0.17 ms.
The copy is ~98% of expanding a child. The opponent model, 40% of a decision
a week ago, is now 3%. The optimization targets are therefore:

1. **State copies** (73%). Incremental apply/undo on one working state, or
   copy-on-write of the parts an action touches, attacks the copy directly.
   Expected: most of the 3.3 s per decision.
2. **Leaf evaluations** (19%). 4,677 per decision at 0.18 ms. Children are
   all expanded and evaluated before the beam keeps four; a cheap pre-ranking
   (immediate score, no copy) that expands only the beam cuts both nodes.
3. **Budgeting.** `MonteCarloRolloutAgent` already has `max_decision_time_ms`;
   `PotentialPointsAgent` does not. A time budget that degrades gracefully —
   fewer samples, then shallower depth, then the one-ply evaluator — is the
   production knob, and the ledger says what each step costs in points:
   depth 3 → 1 is −10.4 at −99% latency; K=4 → 0 is unmeasured on its own.

## Latency by round (production shape)

Default agent over 2,080 decisions: round 1 ≈ 1.8 s mean (p95 5.4 s), round 2
≈ 5.9 s, round 3 ≈ 10.5 s, round 4 ≈ 15.7 s (p95 52 s). Latency grows with
the board because branching and leaf cost grow with birds in play. A
production budget has to be a per-round budget or a per-decision cap.

## How to use it

```bash
# latency + node table for a root
python analysis/decision_profile_report.py artifacts/<root> --agent potential_points
# value per second against a baseline
python analysis/decision_profile_report.py artifacts/<arm> --value-against artifacts/<baseline>
# full trees for a small batch (bigger artifacts)
run_simulation_batch(..., decision_profile_mode="tree")
```

Every new arm should be read through this report as well as `arm_contrast`:
the question is never only "did it win" but "what did the points cost".
