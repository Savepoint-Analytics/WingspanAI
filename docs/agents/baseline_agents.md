# Baseline and Archetype Agents

Status: initial draft, 2026-05-04

## Current Agents

| Agent | Module | Purpose |
|---|---|---|
| `RandomLegalAgent` | `src/wingspan_ai/agents/random_legal.py` | Uniformly samples legal actions with seeded randomness. |
| `GreedyBaselineAgent` | `src/wingspan_ai/agents/greedy.py` | Picks the action with the largest immediate implemented score gain. |
| `StrategyArchetypeAgent` | `src/wingspan_ai/agents/archetypes.py` | Produces interpretable behavioural signatures for early strategy analysis. |
| `MonteCarloRolloutAgent` | `src/wingspan_ai/agents/monte_carlo.py` | Estimates action value through sampled random legal continuations. |

## Strategy Archetypes

Implemented archetype names:

- `egg_focus`: prioritizes laying eggs and building egg capacity.
- `engine_builder`: prioritizes playing birds, especially into less-developed habitats.
- `food_acceleration`: prioritizes gaining food and enabling future bird plays.
- `card_draw`: prioritizes card acquisition.
- `bonus_card_focus`: prioritizes birds with bonus-card tags or bonus-card powers.
- `round_goal_chase`: prioritizes birds that appear aligned with the current round goal.

These are not intended to be strong yet. Their near-term job is to create distinct telemetry signatures so later analysis can detect strategy differences and compare them against random, greedy, and rollout policies.

## Rollout Agent Caveats

The first Monte Carlo agent uses random legal continuations and the current implemented score skeleton. It does not yet model hidden information, unimplemented bird powers, true round-goal placement scoring, or opponent strategy adaptation. Treat it as a plumbing test for action-value estimation, not as a claim of strong play.
