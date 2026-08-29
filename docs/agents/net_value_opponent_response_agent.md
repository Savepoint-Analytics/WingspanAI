# Net-Value Opponent-Response Agent

Status: public-observation implementation scaffold, 2026-08-29

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

This is the bridge between `PotentialPointsAgent` and a later Bayesian/game-theoretic policy. It makes blocking, resource denial, and opponent response first-class while enforcing that opponent estimates come from public observations plus an explicit belief heuristic.

## Current Implementation

The first scaffold:

- Scores each legal action with `evaluate_state_potential`.
- Applies the action, then estimates the next active opponent's best response from public board state, public tray cards, birdfeeder dice, hand counts, bonus-card counts, round goals, and visible resources.
- Caps own candidate breadth with `max_candidate_actions` and opponent-response breadth with `max_opponent_response_actions`.
- Adds denial value when drawing a public tray card or taking birdfeeder food.
- Emits telemetry with the selected net-margin breakdown and opponent response estimate.
- Uses `public_observation_belief_v0` for opponent potential, denial, and response estimates. The acting player's own value still uses their private hand and bonus cards, matching the information available to that player.

Telemetry avoids emitting opponent hand details. The current response estimate records only opponent ID, response action type, response value delta, and response candidate count.

## Public Belief Template

`PublicOpponentBeliefModel` is a first non-oracle belief boundary, not a calibrated Bayesian model. It estimates:

- Food demand from face-up tray card costs, visible food tokens, hand count, open board slots, and early forest-development pressure.
- Hidden card quality from the visible tray's threat profile.
- Bonus-card pressure from visible bonus-card count and played-bird count.
- Opponent response value from public action-family candidates: gain food, lay eggs, draw cards, or play bird.

The model deliberately ignores hidden opponent hand contents, hidden bonus cards, and deck order. A regression test mutates the opponent's hidden hand and verifies the public belief score is unchanged.

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

Future calibrated versions should estimate:

- Opponent archetype posterior.
- Opponent hidden hand usefulness.
- Opponent bonus-card likelihood.
- Opponent response probability, not only best response.
- Whether a denial action is worth its opportunity cost.

## Evaluation Plan

Short-term tests:

- Compare `net_value_response` against `potential_points` in 10-seed random-vs-agent smoke batches.
- Measure decision time against potential-points and Monte Carlo.
- Design the controlled blocking-fixture suite before implementing it. Each fixture should have a stated hypothesis, expected public signal, required simulator support, and data needed to justify the expected direction.

Medium-term experiments:

- Calibrate the public belief model against observed action choices and batch outcomes.
- Evaluate against archetype opponents, not only random.
- Track whether blocking actions improve win probability even when they lower the active player's immediate score.
- Add by-habitat threat metrics: forest food denial, grassland conversion threat, wetland tuck/draw engine threat.

## Caveats

The current implementation is a template, not a finished strategic agent. It is intentionally useful for research plumbing, telemetry shape, and early ablations. It should not be used for public strategy claims until the public belief model is calibrated and the blocking/response assumptions are backed by controlled data.
