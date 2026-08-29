# Net-Value Opponent-Response Agent

Status: first design template and implementation scaffold, 2026-08-28

## Purpose

`NetValueOpponentResponseAgent` evaluates moves by expected score-margin gain, not only by the active player's own score or potential score. The first implementation lives in `src/wingspan_ai/agents/net_value.py`.

The agent asks:

```text
net value =
  my expected potential gain
  - opponent immediate benefit from my move
  - opponent best next-response gain
  + shared-resource denial or blocking value
```

This is the bridge between `PotentialPointsAgent` and a later Bayesian/game-theoretic policy. It makes blocking, resource denial, and opponent response first-class without requiring a full belief model yet.

## Current Implementation

The first scaffold:

- Scores each legal action with `evaluate_state_potential`.
- Applies the action, then estimates the next active opponent's best potential-value response.
- Caps own candidate breadth with `max_candidate_actions` and opponent-response breadth with `max_opponent_response_actions`.
- Adds denial value when drawing a public tray card or taking birdfeeder food.
- Emits telemetry with the selected net-margin breakdown and opponent response estimate.
- Uses `full_state_oracle_v0`, meaning it can inspect simulator full state for opponent potential. This is acceptable for plumbing and ablation tests, but should be replaced with public observations plus beliefs before claim-grade experiments.

Telemetry avoids emitting opponent hand details. The current response estimate records only opponent ID, response action type, response value delta, and response legal-action count.

## Habitat Dimensions

### Forest / Woodland

Forest actions create food tempo and can also trigger opponent incentives through pink/passive powers.

Agent dimensions:

- Food denial: taking a scarce die face the opponent likely needs.
- Food enablement: whether gaining food lets the agent play higher-value birds before the opponent can respond.
- Passive liability: whether the action triggers opponent pink food/cache/tuck reactions.
- Engine displacement: whether the agent can ignore forest because grassland or wetland engines produce food elsewhere.

Important patterns:

- Food-generating passive birds can make opponents hesitate to activate forest.
- If the opponent has visible high-value birds but lacks one food type, blocking that food can be worth more than the active player's immediate gain.
- If grassland ravens or other conversion powers are active, forest food may become less strategically important for that player.

### Grassland / Plains

Grassland actions convert board capacity into direct points and, with ravens or similar powers, can become a food engine.

Agent dimensions:

- Egg conversion value: direct egg points plus egg costs needed for future birds.
- Raven-like conversion threat: whether eggs become food, cards, or tempo.
- Capacity pressure: whether laying eggs now risks wasting future egg production.
- Opponent trigger liability: whether egg laying activates opponent pink powers.
- Round-goal race: whether eggs in a habitat swing current end-of-round placement.

Important patterns:

- Egg engines can become both scoring and resource production.
- A grassland action may be strong for the active player but dangerous if it triggers opponent passive value or fails to block a higher-value opponent conversion.
- Capacity and timing matter: late grassland value is much higher when enough nests remain.

### Wetland / Coastal / Water

Wetlands control card flow. Public tray cards are shared opportunities, and card draw engines can compound into tuck/card scoring loops.

Agent dimensions:

- Tray-card denial: drawing a card because it is more valuable to the opponent than to the active player.
- Card-engine enablement: whether a bird increases future draw rate, tuck rate, or hand-quality selection.
- Tuck loop threat: whether wetland card draw combines with tuck powers for repeatable points.
- Hand saturation: whether extra cards are useful or become dead endgame resources.
- Public information value: tray cards are clean blocking targets because every player can see them.

Important patterns:

- A visible wetland tuck/draw engine card can be a denial target even when the active player has only moderate use for it.
- Draw-heavy agents can fail badly if they never convert cards into birds, eggs, tucks, or bonus progress.
- Wetland tempo should be valued by downstream conversion paths, not card count alone.

## Shared Resource Dimensions

The agent should score blocking and opponent impact across:

- Public tray cards.
- Birdfeeder dice.
- Round-goal race positions.
- Opponent-visible engine triggers.
- Food/card/egg conversion bottlenecks.
- Bonus-card-compatible visible birds.
- Endgame scoring capacity.

Future versions should estimate:

- Opponent archetype posterior.
- Opponent hidden hand usefulness.
- Opponent bonus-card likelihood.
- Opponent response probability, not only best response.
- Whether a denial action is worth its opportunity cost.

## Evaluation Plan

Short-term tests:

- Compare `net_value_response` against `potential_points` in 10-seed random-vs-agent smoke batches.
- Add controlled fixtures where a public tray card is valuable to the opponent and verify the agent assigns denial value.
- Add controlled fixtures where an action triggers opponent pink/passive benefit and verify the agent penalizes it.
- Measure decision time against potential-points and Monte Carlo.

Medium-term experiments:

- Replace full-state opponent scoring with public observation plus belief-state estimates.
- Evaluate against archetype opponents, not only random.
- Track whether blocking actions improve win probability even when they lower the active player's immediate score.
- Add by-habitat threat metrics: forest food denial, grassland conversion threat, wetland tuck/draw engine threat.

## Caveats

The first implementation is a template, not a finished strategic agent. It is intentionally useful for research plumbing, telemetry shape, and controlled ablations. It should not be used for public strategy claims until hidden information is handled through observations and beliefs rather than simulator full state.
