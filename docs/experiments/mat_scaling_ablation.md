# Mat-Scaling Ablation

Status: result, 2026-09-03

## Question

Wingspan's core engine is the player-mat yield curve: a fuller habitat row makes
every action in that row more productive. Forest gives 1/2/3 food at 0-1, 2-3 and
4-5 birds; grassland 2/3/4 eggs; wetland 1/2/3 cards. So the 2nd and 4th birds in
a row are worth more than the 3rd and 5th.

No agent valued this. Adding a powerless bird to the forest moved
`potential_points`' estimate by a flat +10.70 whether or not it crossed a
threshold. Does closing that gap improve play?

## Design

`VALUE_HABITAT_YIELD` and `HABITAT_YIELD_WEIGHT_SCALE` are explicit ablation
switches flipped **before any agent is constructed**, so every arm runs identical
code differing only in those values. Three arms over the same seeds, same roster,
`control` setup, full seat counterbalancing: **60 games each**.

Only `potential_points` and `net_value_response` consult
`evaluate_state_potential`, so greedy and the two archetypes act as internal
controls — their movement reflects only their opponents changing.

## Results

| Agent | OFF | 1x | 2x | win delta (2x) | score delta (2x) |
|---|---:|---:|---:|---:|---:|
| `potential_points` | 0.792 | 0.792 | 0.792 | 0.000 | +1.0 |
| `net_value_response` | 0.583 | 0.583 | 0.625 | +0.042 | +1.8 |
| `archetype_engine_builder` | 0.417 | 0.417 | 0.375 | -0.042 | -0.2 |
| `archetype_bonus_card_focus` | 0.417 | 0.417 | 0.417 | 0.000 | +0.3 |
| `greedy_immediate` | 0.292 | 0.292 | 0.292 | 0.000 | -0.1 |

Decision-level sensitivity, which resolves far finer than win rate:

| Scale | Decisions changed | Games changed |
|---|---:|---:|
| 1x | 20 / 3120 (0.64%) | 4 / 60 (7%) |
| 2x | 105 / 3120 (3.37%) | 11 / 60 (18%) |

## Findings

### 1. The gap was real; closing it does not measurably pay

At 1x the term changed 0.64% of decisions and moved win rate by exactly zero for
every agent. Doubling the weight made it five times more active, and win rate
still moved by at most one game in twenty-four, which is noise.

Both statements are true and should stay separate: the agent now values something
it genuinely should, and that has no demonstrated strategic payoff.

### 2. Why it barely changes rankings

The term depends on habitat bird counts, which change only when a bird is played,
and then only at the 2nd and 4th slot. It shifts the value *level* of a position
but rarely the *ordering* of the actions being compared, and argmax reads only the
ordering.

The one divergence inspected was the intended behaviour: with the feature on,
`net_value` played Hermit Thrush into its forest rather than drawing cards.

### 3. Two implementation traps found by measurement

- **Double counting.** The first version included grassland, but
  `_egg_conversion_potential` already values egg capacity times the grassland egg
  rate. That made the agent pay ~3.7 points to play a 1-point bird purely to
  unlock egg-laying it was already credited for. Grassland is excluded.
- **Demand coupling.** Using `_expected_habitat_activations` meant that gaining
  the food you needed collapsed forest demand to zero and *reduced* the yield
  estimate, penalising the agent for satisfying its own requirements. Row yield is
  structural, so the term now uses a neutral per-habitat share.

Both were caught by an existing test failing rather than by the ablation, which is
an argument against updating tests to match new behaviour without investigating.

## Decision

Keep the feature at 1x. It is retained for correctness and model fidelity, not on
measured performance. `_egg_rate` no longer keeps a hand-copied duplicate of the
grassland curve — all three curves now read `habitat_action_yield`, so a rules
change cannot silently leave the agent valuing a stale table.

## Caveat

60 games per arm, 24 per agent. A genuine effect of one or two points per game
could not be resolved at this sample size; the zero win-rate delta rules out a
large effect, not a small one.

## Contrast

For scale, changes measured the same way on the same harness:

| Change | Win-rate delta |
|---|---:|
| Opponent-aware denial (`net_value`) | **+0.182** |
| Tray-card tie-break (`greedy`) | **+0.112** |
| Mat-scaling valuation | 0.000 |

The harness resolves effects of that size easily, which is what makes the null
here informative rather than merely underpowered.
