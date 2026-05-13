# Baseline and Archetype Agents

Status: initial draft, 2026-05-04

## Current Agents

| Agent | Module | Purpose |
|---|---|---|
| `RandomLegalAgent` | `src/wingspan_ai/agents/random_legal.py` | Uniformly samples legal actions with seeded randomness. |
| `GreedyBaselineAgent` | `src/wingspan_ai/agents/greedy.py` | Picks the action with the largest immediate implemented score gain, with food-choice tiebreaks based on visible hand deficits. |
| `StrategyArchetypeAgent` | `src/wingspan_ai/agents/archetypes.py` | Produces interpretable behavioural signatures for early strategy analysis, including resource-biased food choices. |
| `MonteCarloRolloutAgent` | `src/wingspan_ai/agents/monte_carlo.py` | Estimates action value through sampled random legal continuations. |

## Strategy Archetypes

Implemented archetype names:

- `egg_focus`: prioritizes laying eggs and building egg capacity.
- `engine_builder`: prioritizes playing birds, especially into less-developed habitats.
- `food_acceleration`: prioritizes gaining food and enabling future bird plays.
- `card_draw`: prioritizes card acquisition.
- `bonus_card_focus`: prioritizes birds with bonus-card tags or bonus-card powers.
- `round_goal_chase`: prioritizes birds that appear aligned with the current round goal.

These are not intended to be strong yet. Their near-term job is to create distinct telemetry signatures so later analysis can detect strategy differences and compare them against random, greedy, and rollout policies. Food-oriented heuristics now prefer dice that help pay for visible cards in hand, which is especially important when choosing from the birdfeeder during normal gain-food actions or deterministic reaction powers.

## Rollout Agent Caveats

The first Monte Carlo agent uses random legal continuations and the current implemented scoring surface. It does not yet model hidden information, most unimplemented bird powers, or opponent strategy adaptation. Treat it as a plumbing test for action-value estimation, not as a claim of strong play.
