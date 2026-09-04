# Opponent Response Belief Model

Status: first Bayesian opponent-type model, 2026-08-31

Implementation: `src/wingspan_ai/belief/models.py`
Model ID: `opponent_type_response_belief_v1`

## Problem this replaces

`NetValueOpponentResponseAgent` predicted the opponent's next move as the single
highest-value public candidate. The first calibration probe
(`public_belief_calibration.md`) showed the failure mode clearly: against a
random-legal opponent the model predicted 39 lay-eggs and 39 play-bird and zero
draw-card or gain-food turns, while the opponent actually drew 35 times and
gained food 18 times. Exact-match accuracy was 16.7%.

A best-response estimate answers "what is the strongest reply available?" The
decision-relevant question is "what is this opponent likely to do?" Those differ
whenever the opponent is not a perfect maximizer, which is every opponent
currently in the roster.

Using best-response also biases the acting agent's own play. Net margin
subtracts the opponent's response value, so assuming the opponent always finds
their best reply systematically overstates the threat and pushes the agent
toward over-defensive choices against weak opponents.

## Model

For opponent type `z` and action family `a` with public value estimate `v(a)`:

```
P(a | z)  ∝  prior(a | z) · exp( v(a) / T(z) )
P(a)      =  Σ_z  P(z) · P(a | z)
```

- `prior(a | z)` is how often type `z` picks family `a` regardless of value.
- `T(z)` is a rationality temperature. `T → ∞` ignores value entirely (a random
  opponent); small `T` collapses to best-response.
- Observing an action family updates `P(z)` by Bayes' rule.

### Profiles

| Profile | Favoured family | Temperature | Rationale |
|---|---|---:|---|
| `random_legal` | draw-cards (0.45 prior) | ∞ | Value cannot move the prediction. |
| `value_maximizing` | none (uniform prior) | 0.75 | Near-argmax; reproduces the old behaviour. |
| `engine_builder` | play-bird (0.45) | 2.0 | Archetype tilt with partial value sensitivity. |
| `egg_focus` | lay-eggs (0.45) | 2.0 | |
| `card_draw` | draw-cards (0.45) | 2.0 | |
| `food_acceleration` | gain-food (0.45) | 2.0 | |

### Why the random-legal prior is not uniform

A random-legal agent samples a **concrete legal action**, not an action family.
Families expand into very different numbers of concrete actions: draw-card
choices enumerate tray/deck combinations, while lay-eggs usually expands to one
or two options. The prior `{draw 0.45, food 0.23, play 0.22, eggs 0.10}` is taken
from the observed action mix of `random_legal_p1` in the 3-seed calibration probe
(draw 35, food 18, play 17, eggs 8 of 78 turns).

This is the one place the model is fitted to observed data rather than reasoned
from first principles, and it should be refitted as the roster grows.

## Information boundary

`belief/models.py` consumes only public candidate values supplied by the caller.
It never reads hidden hands, bonus cards, or deck order. The candidate values
themselves come from `PublicOpponentBeliefModel` (`public_observation_belief_v0`),
which is already restricted to public observations.

The runner calls `observe_action(state_before, action, acting_player_id)` on
every non-acting agent after each resolved action. The hook receives the
pre-action state so an observer sees exactly what was visible when the choice was
made, and it must not mutate game state.

## Usage

```python
from wingspan_ai.belief import OpponentBeliefState
from wingspan_ai.rules.actions import ActionType

belief = OpponentBeliefState.uniform("player_1")
candidates = {ActionType.PLAY_BIRD: 3.0, ActionType.DRAW_CARDS: 1.0}

distribution = belief.predict(candidates)
distribution.expected_value        # probability-weighted, not the best reply
distribution.most_likely_family
distribution.profile_posterior

belief = belief.observe(ActionType.DRAW_CARDS, candidates)
```

Belief states are immutable: `observe` returns a new state, so belief history
stays inspectable and speculative search branches cannot corrupt the caller's
belief.

The agent selects the mode:

```python
NetValueOpponentResponseAgent(response_mode="expected")  # default
NetValueOpponentResponseAgent(response_mode="best")      # ablation control
```

Batch flows expose this as `net_value_response_mode`.

## Observed behaviour

Over one 52-turn game against `random_legal_p1`, the posterior concentrated as
expected and ruled out the maximizer explanation entirely:

| Profile | Posterior after 25 observations |
|---|---:|
| `card_draw` | 0.826 |
| `random_legal` | 0.173 |
| `egg_focus` | 0.000 |
| `food_acceleration` | 0.000 |
| `engine_builder` | 0.000 |
| `value_maximizing` | 0.000 |

Family probabilities became `{eggs 0.33, draw 0.28, play 0.24, food 0.14}`
instead of the previous all-or-nothing split, and expected response value (1.74)
sat well below best-response value (3.00).

## Known limitations

1. **`random_legal` and `card_draw` are not well separated.** Both favour draws,
   so the posterior can settle on either. Distinguishing them needs a signal
   beyond family frequency — value-sensitivity over time, or resource-state
   conditioning.
2. **Profiles are static.** Real opponents shift phase by phase; an engine
   builder plays birds early and lays eggs late. The model has no round-dependent
   prior yet.
3. **Priors are hand-set.** Only the `random_legal` prior is data-fitted, and
   from a 3-seed sample. The archetype tilts (0.45) are chosen, not measured.
4. **One belief per opponent, not per seat.** Fine at two players; needs
   revisiting for three or more.
5. **Calibration is measured against weak opponents.** Predicting a random agent
   is a low bar. The model needs calibration against greedy, potential-points and
   archetype opponents before it should drive blocking decisions.

## Calibration

`analysis/net_value_calibration.py` now scores the distribution, not just the
point prediction:

- `mean_log_loss` — negative log-likelihood of the observed family.
- `uniform_log_loss` — the same metric for a uniform guess.
- `log_loss_improvement` — positive means the belief model beats chance.
- `mean_brier_score` — squared error over the family distribution.
- `mean_observed_family_probability` — average probability placed on what
  actually happened.

Exact-match rate is retained but should not be the headline: it cannot tell a
confidently wrong model from a well-calibrated uncertain one.

## Next steps

- Refit family priors per opponent kind from round-robin telemetry rather than
  the single random-opponent probe.
- Add round-phase conditioning to the priors.
- Calibrate against non-random opponents, then decide which calibrated opponent
  type should drive blocking fixtures.
