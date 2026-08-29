# Lookahead Compute Profile

Status: second profiling pass, 2026-08-29

## Purpose

Lookahead-heavy agents repeatedly call `apply_action`, so their scaling depends on transition cost. This profile was added before attempting any 50-100 seed matrix.

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
