# Bayesian Belief Model Plan

Status: initial plan, 2026-05-04

## Research Goal

The Bayesian agent should improve decisions under partial information by maintaining beliefs over opponent strategy, hidden score potential, and future action likelihood. The first useful version should be interpretable and measurable before any neural value function enters the project.

## Recommended First Belief Variables

Prioritize variables with strong signal and likely outcome impact:

| Belief | Why first | Observable signals |
|---|---|---|
| Opponent strategy archetype | Strategy type changes which future actions and scoring paths are likely. | Action frequencies, habitat investments, food choices, egg tempo, card draw behaviour. |
| Hidden score potential | Bonus cards, tucked cards, cached food, and unplayed hand can swing final scores. | Played birds, bonus-card-compatible tags, visible engine shape, hand count. |
| Near-term action likelihood | Useful for blocking, round-goal races, and food/tray contention. | Current resources, legal action set, habitat state, birdfeeder/tray state. |
| End-game score distribution | Directly supports win-probability-oriented action choice. | Current score skeleton, remaining turns, engine capacity, opponent archetype. |

## State Representation

Initial belief state should include:

- Prior over archetypes: random, greedy, egg focus, engine builder, food acceleration, card draw, bonus focus, round-goal chase.
- Per-opponent hidden score distribution: mean, variance, and source contributions.
- Per-opponent next-action probabilities over action families.
- Confidence/calibration fields for analysis.

## Update Loop

1. Start with a broad prior over opponent archetypes.
2. On each observed action, score likelihood under each archetype's expected action preferences.
3. Renormalize archetype probabilities.
4. Update hidden score estimates from visible birds, bonus-card tags, hand count, tucked/cached/egg state, and remaining turns.
5. Estimate next-action probabilities from current legal actions and archetype posterior.
6. Log belief snapshots for calibration analysis.

## Decision Policy

The first Bayesian policy should be a hybrid:

- Generate legal actions from the rules engine.
- Estimate immediate score and resource impact.
- Estimate future value using archetype-weighted opponent continuations.
- Prefer actions that improve expected win probability, not just own final score.

## Evaluation

Success criteria:

- Archetype posterior becomes better than uniform by mid-game in scripted matchups.
- Hidden score estimate error decreases as the game progresses.
- Next-action family predictions beat a frequency baseline.
- Bayesian policy improves win rate or expected score against at least one non-random archetype.
- Belief logs explain why a move was chosen.

## Dependencies

Before implementation:

- More faithful scoring handlers for bonus cards and round goals.
- Stable action-family telemetry.
- A tournament runner with matchup summaries.
- Public/private state snapshot artifacts.
