# Lookahead Compute Profile

Status: third profiling pass, 2026-09-04

## Purpose

Lookahead-heavy agents repeatedly call `apply_action`, so their scaling depends on transition cost. This profile was added before attempting any 50-100 seed matrix.

## Content Sharing (2026-09-04)

Re-measured before the search-depth experiment, a single `GameState` deep copy
took **47 ms** on a representative mid-game state, six times the figure below.
The cause was the deck: `DeckState.bird_deck` holds 180 full `BirdCard` models
and every copy cloned all of them.

Content never changes after loading, so `BirdCard`, `BonusCard`, `RoundGoal`,
`FoodCost` and `Power` are now frozen and return `self` from `__deepcopy__`.
Copies share cards instead of cloning them.

| Copy strategy | Before | After |
|---|---:|---:|
| `model_copy(deep=True)` | 47.02 ms | **0.53 ms** |
| `copy.deepcopy` | 48.40 ms | 0.44 ms |
| pickle round-trip | 25.84 ms | 32.45 ms |
| `model_validate(model_dump())` | 32.52 ms | 35.95 ms |

A depth-1 `potential_points` game against `greedy_immediate` (seed 1) went from
63 s to 8 s with an identical outcome. The same measurement also exposed that
`canonical_state_json` was not canonical: set-valued card fields serialized in
iteration order, which differs between a set and its copy. Those fields now
serialize sorted.

The earlier figures below are kept for the record; every absolute number in
them is now roughly 90x smaller.

## Apply Action Profile

Command:

```bash
UV_CACHE_DIR=.uv-cache uv run python analysis/apply_action_profile.py --iterations 25
```

Workbook-backed initial state, seed 1:

| Segment | Avg ms |
|---|---:|
| Legal action generation | 0.044 |
| `GameState.model_copy(deep=True)` | 8.092 |
| Full `apply_action` | 9.960 |
| Branch copy + `apply_action_in_place` | 8.101 |
| Isolated in-place transition | 0.062 |
| Estimated transition after copy | 1.867 |

Deep copy accounted for about 81.3% of `apply_action` time in this profile. Because the copy and transition timings are close, the exact share is noisy across short runs. The stable finding is that branch creation dominates speculative search cost, while mutating an already-isolated branch with `apply_action_in_place` is cheap.

`apply_action` still deep-copies before mutating and remains the safe default for normal simulator execution. `apply_action_in_place` is explicit and should only be used by callers that already own a throwaway branch state.

## Strict Monte Carlo Probe

Settings:

- Seeds: 1.
- `rollout_count=4`.
- `rollout_depth=6`.
- `max_decision_time_ms=75.0`.
- `max_candidate_actions=4`.

Result:

- Player 2 score: 66.
- Player 1 score: 35.
- Replay validation: valid.

The Monte Carlo agent now supports strict breadth control with `max_candidate_actions`. Its default `min_rollouts_per_action=0` lets the time budget stop before any rollout is launched; actions without rollouts receive a static fallback score and are marked with `used_static_fallback=true` in telemetry. Set `min_rollouts_per_action` above zero only when fairness across candidate actions matters more than a hard wall-clock cap.

## Net-Value Response Probe

Initial uncapped summary recomputation made the net-value scaffold too slow even at 3 seeds. The agent now caches its last evaluation for telemetry and caps:

- own candidate actions with `max_candidate_actions`
- opponent response actions with `max_opponent_response_actions`

Public-belief probe settings:

- Seeds: 1.
- `max_candidate_actions=5`.
- `max_opponent_response_actions=3`.

Result:

- Player 2 score: 66.
- Player 1 score: 38.
- Replay validation: valid.

The net-value response agent now uses `public_observation_belief_v0` for opponent scoring instead of full-state opponent hand and bonus-card access. This is still an uncalibrated heuristic, but it enforces the correct information boundary for opponent estimates.

## Next Optimization Targets

- Reuse isolated branch states inside deeper search wherever a branch is already owned by the caller.
- Add candidate pruning before expensive lookahead for all greedy-family agents.
- Calibrate `public_observation_belief_v0` against observed action choices and batch outcomes.
- Design the controlled blocking-fixture suite before implementing it; each fixture should be backed by a stated hypothesis and data requirement.
