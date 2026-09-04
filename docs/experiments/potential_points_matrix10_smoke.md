# Potential-Points Matrix Smoke Run

Status: SUPERSEDED by `baseline_matrix10_v2.md`, 2026-08-31

> This run predates the ADR 0003 and ADR 0004 fixes, the power-coverage sweep,
> and the archetype repair. It is not reproducible and its archetype rows
> measured a bug rather than a strategy. Retained as a record only.

## Purpose

This run checks whether `PotentialPointsAgent` is winning for interpretable strategic reasons or because one current scoring category is obviously distorted. It also measures decision-time telemetry before scaling larger baseline comparisons.

> **Seed-matching caveat added 2026-08-31.** `game_id` participates in RNG seed
> material and is derived from `batch_id`. If the player-two variants below were
> run as separate batches with their own batch IDs, they did **not** share deck
> order, birdfeeder rolls, or setup deals, and the "seeds 1-10" pairing does not
> hold. The comparison is noisier than reported. Re-run under a single shared
> `batch_id` before treating any ordering here as a finding. See the 2026-08-31
> entry in `PROJECT_CONTEXT.md`.

> **Power coverage caveat.** This run used 71.8% power coverage. Coverage is now
> 100%, and five opponent-affecting powers that previously resolved as pure
> self-benefit have been fixed, so these numbers predate real rule changes.

## Setup

- Seeds: 1-10.
- Batch kind: `smoke`.
- Player 1: `RandomLegalAgent`.
- Player 2 variants: random legal, immediate greedy, potential-points, guardrailed immediate greedy, guardrailed potential-points, six strategy archetypes, and Monte Carlo rollout.
- Persistence and object upload disabled.
- Replay validation enabled for all games.

## Outcome Summary

| Player 2 agent | P2 wins | P2 avg score | Avg margin | Avg decision ms |
|---|---:|---:|---:|---:|
| `random_legal_p2` | 5.0 / 10 | 36.00 | 3.00 | 0.106 |
| `greedy_immediate_p2` | 7.0 / 10 | 44.50 | 15.10 | 138.022 |
| `potential_points_p2` | 10.0 / 10 | 64.50 | 30.50 | 406.797 |
| `guardrailed_greedy_immediate_p2` | 10.0 / 10 | 52.70 | 20.60 | 82.876 |
| `guardrailed_potential_points_p2` | 9.0 / 10 | 57.80 | 22.00 | 153.297 |
| `egg_focus_p2` | 5.5 / 10 | 46.10 | 8.20 | 131.591 |
| `engine_builder_p2` | 8.0 / 10 | 48.90 | 14.50 | 127.092 |
| `food_acceleration_p2` | 0.0 / 10 | 12.90 | -20.80 | 106.662 |
| `card_draw_p2` | 0.0 / 10 | 2.00 | -37.00 | 115.395 |
| `bonus_card_focus_p2` | 9.0 / 10 | 48.00 | 15.20 | 130.210 |
| `round_goal_chase_p2` | 8.0 / 10 | 51.90 | 20.10 | 133.564 |
| `monte_carlo_rollout_p2` | 9.0 / 10 | 66.10 | 35.00 | 11004.710 |

## Interpretation

`PotentialPointsAgent` appears to win because it keeps converting resources into played birds and late-game points instead of getting trapped in food or draw loops. Compared with immediate greedy, potential-points played 67 birds instead of 34, laid 65 egg actions instead of 45, and used fewer gain-food actions. Its score mix was also broad: higher bird points, solid round-goal points, eggs, cached food, and tucked cards.

The result does not look like a single obvious scoring-category artifact. Potential-points had average player-two score mix of 32.30 bird points, 2.70 bonus points, 13.70 round-goal points, 9.30 egg points, 3.10 cached-food points, and 3.40 tucked-card points. That said, the current power audit still reports 49 unsupported powered cards and about 71.8% implemented power coverage, so this is not yet strategic proof.

Guardrails helped immediate greedy but reduced potential-points in this run. Guardrailed potential-points gained food much more often than unguardrailed potential-points, suggesting the current guardrail config may over-prune or over-boost food decisions for an agent that already values future conversion.

Monte Carlo had the strongest average score and margin in this 10-seed matrix, but the current implementation averaged about 11 seconds per player-two decision. It should not be scaled to 50-100 seed matrices without either smaller rollout settings or a faster planning path.

## Follow-Up

- Add compute-budget controls for `MonteCarloRolloutAgent` in batch configs.
- Profile `apply_action` deep-copy cost for greedy, archetypes, potential-points, and Monte Carlo.
- Compare potential-points against non-random opponents; random-vs-agent is useful smoke evidence but not enough for strategy claims.
- Tune guardrails separately for potential-points instead of reusing the immediate-greedy config unchanged.
