# Playing a Weaker Bird to Develop a Habitat

Status: gap analysis, 2026-09-04. Base game partly handled; Oceania unmodelled.

## The decision

A habitat row pays more as it fills. Playing a mediocre bird into the forest can
be correct if it moves that row from 1 food per activation to 2, because the
gain repeats for the rest of the game while the bird's weakness is paid once.

Oceania sharpens this. Its player mat gives the first bird placed in a habitat a
bonus resource on subsequent activations, so the first placement roughly doubles
that row's baseline productivity. The bird's own quality becomes close to
irrelevant next to unlocking the row.

## What the agents do now

`potential_points` values row yield through `_habitat_yield_potential`
(`potential_points.py`, behind `VALUE_HABITAT_YIELD`). It credits crossing a
yield threshold using a **neutral one-third share** per habitat:

```python
expected_uses = turns_remaining * _NEUTRAL_HABITAT_SHARE
```

The neutral share is deliberate — coupling it to current food demand meant that
gaining needed food *reduced* the estimate of the row that produced it. But it
also means the term cannot express the decision above: it values the row the same
whether the agent intends to use it or not.

Grassland is deliberately absent from `_HABITAT_YIELD_UNIT_VALUE`, so grassland
development is currently worth zero.

No other agent values row development at all. `greedy_immediate` returns a flat
40.0 for every `PLAY_BIRD`. `archetype_engine_builder` is the only one that reads
placement depth (`archetypes.py:225-227`), and it rewards depth directly rather
than rewarding *crossing a threshold*.

**Measured contribution: none.** The ablation over 60 seed-matched games per arm
moved 0.64% of decisions at weight 1.0 and 3.37% at 2.0, with no win-rate effect.

## How this should be handled

### 1. Value the threshold, not the depth
The payoff is a step function, not linear. Placing the third forest bird when the
tier boundary is at three is worth much more than placing the fourth. The current
code does this correctly; the archetypes do not, and should call the same helper
rather than rewarding depth.

### 2. Weight by intended use, without the feedback loop
The neutral one-third share is a workaround for a real problem: demand-coupling
created a perverse gradient. The fix is to weight by **structural** intent rather
than momentary demand — how many of the player's *hand and board* need that
habitat's output over the remaining turns, which does not fall just because a
need was met this turn.

Concretely: `expected_uses = turns_remaining * share`, where `share` is derived
from the fraction of unplayed hand cards whose food costs that row can supply,
floored at the neutral third so it never collapses to zero.

### 3. Make the tradeoff explicit
The decision is a comparison the agents never state:

```
value(weak bird in developing row) - value(strong bird in saturated row)
  = [P_weak + threshold_gain x remaining_activations]
  - [P_strong + 0]
```

`threshold_gain x remaining_activations` is exactly what `_habitat_yield_potential`
computes. What is missing is applying it to the *comparison* rather than to each
option in isolation, and doing it in the archetypes at all.

### 4. Oceania
Nothing in the simulator models the Oceania mat. It needs, at minimum:

- Per-mat yield tiers rather than the hardcoded `_HABITAT_YIELD_TIERS`.
- A first-placement bonus per habitat.
- Nectar as a spendable food with end-game majority scoring, which changes what a
  surplus is worth and therefore the whole conversion calculus.

Until the mat is configurable per expansion, treat any Oceania strategy claim as
unsupported.

## Recommended sequence

1. Make the archetypes call the shared threshold helper instead of rewarding depth.
2. Replace the neutral share with the hand-derived share described above, floored.
3. Re-ablate. If it stays null a second time, stop investing here: two nulls
   already suggest these agents are not limited by habitat valuation.
4. Treat the Oceania mat as an expansion-scope project, not a tweak.

## Open question worth testing

Whether row development matters at all may depend on game length. With 8/7/6/5
turns, a row unlocked in round 1 activates far more often than one unlocked in
round 3. If the term ever pays, it should pay *only* early — an interaction the
current flat `turns_remaining` scaling would capture, but which no experiment has
isolated.
