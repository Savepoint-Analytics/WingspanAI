# End-of-Round (Teal) Powers

Status: gap analysis, 2026-09-04. **A concrete defect found: teal powers are
undervalued by roughly 2x in rounds 1-3.**

## The defect

`potential_points.py`:

```python
def _remaining_teal_triggers(turns_remaining: int) -> int:
    if turns_remaining <= 0:
        return 0
    return min(4, max(1, ceil(turns_remaining / 6)))
```

Teal powers fire once at the **end of each round**, so remaining triggers is
`4 - current_round + 1` — a property of the round number, not of turns left. The
function instead infers rounds from turns by dividing by 6, and turns per round
are 8/7/6/5, not 6.

| Round | Turns left | Estimated triggers | Actual |
|---:|---:|---:|---:|
| 1 | 8 | **2** | **4** |
| 2 | 7 | **2** | **3** |
| 3 | 6 | **1** | **2** |
| 4 | 5 | 1 | 1 |

Only round 4 is correct. A teal bird played in round 1 — precisely when it is
most valuable, because it has the most firings ahead of it — is valued at half
its worth. The error shrinks exactly as the bird becomes less worth playing, so
it systematically discourages the correct play.

The fix is one line: derive from `state.round_state.round_number` rather than
from turns.

```python
def _remaining_teal_triggers(round_number: int) -> int:
    return max(0, TOTAL_ROUNDS - round_number + 1)
```

The caller has `state` available at both call sites.

## Scope note

Teal is an expansion colour — 63 of the 707 catalogued birds, none of them core.
Base-game runs never exercise this path, which is why no test caught it. It will
matter the moment expansion content is enabled, and the fix should land before
then rather than after a batch of expansion results is published.

## What proper evaluation needs beyond the fix

A teal power's value is not just `triggers x per-trigger value`. Four things the
current model does not express:

### 1. Conditional requirements
Many teal powers are conditional — "if you have at least N eggs", "for each bird
in this habitat". Value should be the trigger count times the **probability the
condition holds at end of round**, which is forecastable from the board's current
trajectory rather than its present state. A bird whose condition is not met now
but will be by round end is undervalued at zero today.

### 2. Timing that bypasses habitat activation
The most strategically interesting teal powers place eggs at end of round without
spending an action cube — and, critically, **without activating grassland**. In
the base game, laying eggs means taking the grassland action, which advances your
own row but also gives nothing to opponents. In expansions with reactive pinks,
activating a habitat can trigger an opponent's power. A teal egg sidesteps that.

Valuing this requires knowing what an opponent's board would take from your
grassland activation — machinery that already exists in `net_value`'s denial
path, applied in the opposite direction.

### 3. Nectar sinks
Oceania and European nectar is lost at end of round if unspent, and scores by
majority. A teal power that converts surplus nectar into something permanent is
worth more the more nectar the player is holding and the less likely they are to
win the majority. Neither quantity is modelled: nectar exists in `FoodType` and
the loader, and nowhere else.

### 4. Interaction with round goals
A teal power that adds eggs or birds at end of round resolves in the same window
as round-goal scoring. Whether it resolves **before or after** the goal is scored
determines whether it can win the goal — a rules-order question that must be
encoded correctly before any valuation is trustworthy. This should be confirmed
against the rulebook and pinned by a test.

## Sequence

1. **Fix `_remaining_teal_triggers`.** One line, unambiguously a bug, do it now.
2. Encode the end-of-round resolution order and pin it with a test.
3. Add condition-probability weighting.
4. Treat nectar and the activation-bypass value as expansion-scope work, blocked
   on nectar being modelled at all.

Item 1 is correctness. Items 3-4 are strategy terms and should be ablated on the
same terms as everything else.
