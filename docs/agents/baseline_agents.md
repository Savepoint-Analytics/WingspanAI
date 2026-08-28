# Baseline and Archetype Agents

Status: initial draft, 2026-05-04

## Current Agents

| Agent | Module | Purpose |
|---|---|---|
| `RandomLegalAgent` | `src/wingspan_ai/agents/random_legal.py` | Uniformly samples legal actions with seeded randomness. |
| `GreedyBaselineAgent` | `src/wingspan_ai/agents/greedy.py` | Picks the action with the largest immediate implemented score gain, with food-choice tiebreaks based on visible hand deficits. |
| `PotentialPointsAgent` | `src/wingspan_ai/agents/potential_points.py` | Picks the action that creates the best estimated final-score potential, including resource conversion, playable hand value, power timing, bonus-card progress, round-goal pressure, and endgame conversion. |
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

## Potential-Points Agent

Status: first implementation slice, 2026-08-28

`PotentialPointsAgent` is a new greedy-family baseline. It still chooses one legal action at a time, but evaluates the resulting state using an explainable final-score potential breakdown instead of realized points only. The current breakdown includes realized score, playable bird potential, food conversion potential, egg conversion potential, card conversion potential, engine power potential, bonus-card potential, round-goal potential, endgame conversion potential, and dead-resource penalties.

Power timing plan:

- Brown powers: estimate repeated habitat activation value from remaining turns, current habitat demand, and visible conversion paths.
- Pink powers: estimate passive opponent-turn triggers from remaining opponent activity and cap value by visible capacity where possible.
- Teal powers: estimate one end-of-round trigger per remaining round, with low value when played too late to trigger meaningfully.
- Yellow powers: estimate one end-of-game conversion trigger if the bird can be in play before final scoring. Exact yellow handlers should later replace text heuristics.
- White powers: estimate one-shot when-played value for birds still in hand. White powers already resolved by the rules engine are captured through realized/resource deltas after `apply_action`.

Near-term improvements:

- Continue replacing text-token power valuation with registry-backed value handlers aligned to the power handler registry. The first implementation now prefers explicit or classified power `handler_key` values for common gain-food, draw-card, lay-egg, tuck, cache, predator, discard, all-player, and deck-search patterns, then falls back to text-token valuation for unclassified powers.
- Add better probability estimates for drawing playable cards, predator success, bonus-card thresholds, and opponent round-goal movement.
- Expand endgame search from a shallow same-player search into a full remaining-turn planner that accounts for opponent actions and round-end scoring.
- Compare `PotentialPointsAgent` against immediate greedy, guardrailed greedy, archetypes, and Monte Carlo over fixed-seed smoke batches.
