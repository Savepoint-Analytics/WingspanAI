# Baseline and Archetype Agents

Status: initial draft, 2026-05-04

## Current Agents

| Agent | Module | Purpose |
|---|---|---|
| `RandomLegalAgent` | `src/wingspan_ai/agents/random_legal.py` | Uniformly samples legal actions with seeded randomness. |
| `GreedyBaselineAgent` | `src/wingspan_ai/agents/greedy.py` | Picks the action with the largest immediate implemented score gain, with food-choice tiebreaks based on visible hand deficits. |
| `PotentialPointsAgent` | `src/wingspan_ai/agents/potential_points.py` | Picks the action that creates the best estimated final-score potential, including resource conversion, playable hand value, power timing, bonus-card progress, round-goal pressure, and endgame conversion. |
| `NetValueOpponentResponseAgent` | `src/wingspan_ai/agents/net_value.py` | Estimates score-margin impact after the next opponent response using public observations plus a first belief heuristic for shared-resource denial. |
| `StrategyArchetypeAgent` | `src/wingspan_ai/agents/archetypes.py` | Produces interpretable behavioural signatures for early strategy analysis, including resource-biased food choices. |
| `MonteCarloRolloutAgent` | `src/wingspan_ai/agents/monte_carlo.py` | Estimates action value through sampled random legal continuations, with optional decision-time and rollout-count budget controls. |

## Strategy Archetypes

Implemented archetype names:

- `egg_focus`: prioritizes laying eggs and building egg capacity.
- `engine_builder`: prioritizes playing birds, especially into less-developed habitats.
- `food_acceleration`: prioritizes gaining food and enabling future bird plays.
- `card_draw`: prioritizes card acquisition.
- `bonus_card_focus`: prioritizes birds with bonus-card tags or bonus-card powers.
- `round_goal_chase`: prioritizes birds that appear aligned with the current round goal.

These are not intended to be strong yet. Their near-term job is to create distinct telemetry signatures so later analysis can detect strategy differences and compare them against random, greedy, and rollout policies. Food-oriented heuristics now prefer dice that help pay for visible cards in hand, which is especially important when choosing from the birdfeeder during normal gain-food actions or deterministic reaction powers.

## Opening Setup

Opening setup is now policy-driven. Random, greedy, and Monte Carlo use `default_setup_v1`; `PotentialPointsAgent` uses `potential_points_setup_v1`; each archetype uses `archetype_<name>_setup_v1`; and `NetValueOpponentResponseAgent` uses `net_value_setup_v1`. Guardrailed agents delegate setup to their wrapped base agent.

See `docs/agents/opening_setup_policies.md` for the exact opening dimensions and current caveats.

## Rollout Agent Caveats

The first Monte Carlo agent uses random legal continuations and the current implemented scoring surface. It does not yet model hidden information, most unimplemented bird powers, or opponent strategy adaptation. Treat it as a plumbing test for action-value estimation, not as a claim of strong play.

Monte Carlo now supports `max_decision_time_ms`, `rollout_count`, `rollout_depth`, `max_candidate_actions`, and `min_rollouts_per_action`. The default `min_rollouts_per_action=0` supports stricter wall-clock behaviour; unevaluated candidates receive static fallback scores and are marked in telemetry. Raise `min_rollouts_per_action` only when candidate fairness matters more than throughput.

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
- Endgame search now descends through opponent turns (modelled with the deterministic greedy baseline) to the next own turn, with a beam of four continuations. Before 2026-09-04 it stopped after one ply in every multiplayer game, so `search_depth` had no effect. Depth 2 on every turn is worth roughly +7 points per game against this roster; searching every turn rather than the last five cubes of a round adds about +6 more (`docs/experiments/search_depth_experiment.md`). With `determinization_samples=4` the search scores actions over resampled decks and opponent hands instead of the true state; the leak-free gain is +10.4 at depth 3 every turn (`docs/experiments/determinized_search_test.md`). Remaining gaps: feeder rerolls are still resolved in legal-action generation so their outcome is visible, the opponent model is fixed to greedy, and the planning horizon is the current round rather than the game.
- Compare `PotentialPointsAgent` against immediate greedy, guardrailed greedy, archetypes, and Monte Carlo over fixed-seed smoke batches.
