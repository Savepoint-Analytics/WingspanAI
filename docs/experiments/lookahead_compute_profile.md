# Lookahead Compute Profile

Status: first profiling pass, 2026-08-28

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
| Legal action generation | 0.045 |
| `GameState.model_copy(deep=True)` | 7.887 |
| Full `apply_action` | 8.468 |
| Estimated transition after copy | 0.581 |

Deep copy accounted for about 93.1% of `apply_action` time in this profile. This explains why greedy, archetype, potential-points, Monte Carlo, and net-value opponent-response agents become expensive: their action evaluation loops mostly pay repeated full-state copy cost.

## Budgeted Monte Carlo Probe

Settings:

- Seeds: 1-3.
- `rollout_count=4`.
- `rollout_depth=4`.
- `max_decision_time_ms=100.0`.

Result:

- Player 2 wins: 3.0 / 3.
- Player 2 average score: 61.33.
- Average decision total: 625.921 ms.
- Average completed rollouts per decision: 14.73.
- Budget exhausted on all player-two decisions.

The nominal 100 ms budget is not a strict wall-clock cap because the current implementation guarantees at least one rollout per legal action before checking the deadline. That is strategically fairer than starving late-listed actions, but it means early turns with many legal actions can exceed the nominal budget.

## Net-Value Response Probe

Initial uncapped summary recomputation made the net-value scaffold too slow even at 3 seeds. The agent now caches its last evaluation for telemetry and caps:

- own candidate actions with `max_candidate_actions`
- opponent response actions with `max_opponent_response_actions`

Balanced probe settings:

- Seeds: 1-3.
- `max_candidate_actions=5`.
- `max_opponent_response_actions=3`.

Result:

- Player 2 wins: 2.0 / 3.
- Player 2 average score: 35.00.
- Average decision total: 175.410 ms.
- Action mix: 52.6% draw, 17.9% food, 14.1% eggs, 15.4% play.

The candidate-diversity fix improved behaviour over the first fast probe, which selected draw cards 78.2% of the time and never selected gain food. The agent still appears over-attracted to tray denial and needs calibration before tournament-scale tests.

## Next Optimization Targets

- Reduce or avoid `GameState.model_copy(deep=True)` inside speculative action evaluation.
- Add candidate pruning before expensive lookahead for all greedy-family agents.
- Add strict wall-clock options that can skip the minimum rollout guarantee when batch throughput matters.
- Add lower-cost public-observation opponent scoring before expanding net-value response beyond controlled probes.
