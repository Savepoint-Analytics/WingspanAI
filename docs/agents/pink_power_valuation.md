# Valuing Pink (Between-Turn) Powers

Status: gap analysis, 2026-09-04. Partly handled; the priors behind it are
unmeasured, and telemetry to fix that now exists.

## What is already there

`_pink_trigger_rate` in `potential_points.py` is one of the better-developed
pieces of agent reasoning, and it is genuinely opponent-aware. It:

- Sums `action_cubes_available` across opponents, so the estimate **does scale
  with player count** — a five-player table offers roughly four times the
  trigger opportunities of a two-player one.
- Gates predator-reaction powers on whether opponents actually hold predators,
  and returns 0.0 when they hold none. This fixed a case where a vulture scored
  the same against a board with zero predators as against one with five.
- Gates "when an opponent plays a bird in [habitat]" on whether opponents have
  **room** in that habitat, scaled by the fraction who do.
- Gates egg-laying reactions on opponents having egg capacity.

Uses only public board state, so the information boundary is respected.

## The gaps

### 1. The action-share priors are guesses, and telemetry now exists
```python
_OPPONENT_PLAY_BIRD_SHARE = 0.20
_OPPONENT_LAY_EGGS_SHARE = 0.20
_OPPONENT_GAIN_FOOD_SHARE = 0.35
_DEFAULT_PINK_SHARE = 0.35
```
The comment says "rough priors from observed agent action mixes; refine from
telemetry when available." Telemetry is available: `action_selected` events carry
the action family for every turn of every simulated game, and the SQL views
already aggregate action mix by round.

These should be **measured per opponent archetype and per round**, not held as
four global constants. An engine-builder's action mix differs sharply from an
egg-focused bot's, and every agent's mix shifts across rounds as boards fill.

### 2. Shares are static across rounds
Opponents play more birds early and lay more eggs late. A single share flattens
that, which biases pink valuation in opposite directions at the two ends of the
game — the point where the decision to play the pink bird is actually made.

### 3. The opponent belief model is not consulted
The project already has `OpponentBeliefState` and a bonus-card posterior
(`wingspan_ai/belief/`), which estimate what an opponent is steering toward.
`_pink_trigger_rate` does not use them. An opponent whose posterior says
"egg-focused" should raise the estimate for egg-reaction pinks specifically,
rather than every opponent contributing the same flat share.

### 4. Player count changes *which* pinks are good, not just how many triggers
Trigger count scales linearly with opponents, but the variance does not. In a
two-player game a narrow pink (fires only on predator success) is a gamble on one
opponent's board; in a five-player game it is close to a reliable income stream.
The current model captures the mean and ignores the spread, so it cannot express
"prefer the narrow-but-high pink at five players, the broad-but-low one at two."

## How this should be handled

### Replace the constants with a measured, conditional table
```
P(action_family | opponent_archetype, round)
```
Estimated from `action_selected` telemetry, stored as content rather than code,
and versioned alongside the agent. Fall back to the current global constants when
an archetype is unseen.

### Weight by belief, not by uniform assumption
```
trigger_rate = sum over opponents of
    opponent_turns_remaining
  x sum over families of P(family | belief(opponent), round) x fires_on(power, family)
```
This subsumes the current special cases: predator gating becomes a `fires_on`
term conditioned on the opponent's visible predators, rather than a separate
branch.

### Model spread as well as mean at higher player counts
For a power with per-opponent trigger probability `p` and `n` opponents, the
count is Poisson-binomial. Carrying its variance lets the agent prefer reliable
income when it is behind on tempo and accept variance when it needs a swing.
This is the one part here that is genuinely a novel approach rather than a
refinement, and it should be built only after the measured table exists.

## Sequence

1. Measure the action-mix table from existing telemetry. Cheap, and it is
   evidence rather than assumption.
2. Condition on round. Same data, one more dimension.
3. Wire in the existing belief posterior.
4. Only then consider variance-aware selection, and only if 1-3 move anything.

Steps 1-3 are refinements of a model that already works and respects the
information boundary. Expect them to sharpen valuation without moving win rate —
that has been the pattern for the last two improvements, and there is no reason
yet to think this one differs.
