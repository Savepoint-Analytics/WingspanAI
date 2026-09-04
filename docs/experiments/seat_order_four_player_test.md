# Four-Player Seat Test, and Why Seat Claims Need a Stability Check

Status: **no reliable effect; sample sizes shown to be inadequate**, 2026-09-03

## The test

The structural account (`seat_order_investigation_3p.md`) noted that four rounds
divide evenly among two and four players but not three or five:

| Players | Rounds started | Rounds ended | Symmetric? |
|---|---|---|---|
| 2 | [2, 2] | [2, 2] | yes |
| 3 | [2, 1, 1] | [1, 1, 2] | no |
| 4 | [1, 1, 1, 1] | [1, 1, 1, 1] | yes |
| 5 | [1, 1, 1, 1, 0] | [1, 1, 1, 0, 1] | no |

It predicts no seat effect at four players. Because the current agents already
show no effect at three, this was framed as a **falsification** test: a
significant four-player effect would refute the account. Confirmation would prove
little.

Setup: four tray-aware agents, seeds 1-15, `control` setup, full seat
counterbalancing, 60 games. Same roster and game count as the three-player
control. The multiplayer rule audit passed all eight checks for four players, so
green-goal placement (7/4/3/0, where fourth place scoring zero is load-bearing at
this table size) was verified rather than assumed.

## Pooled result looked significant

| Seat | Paired delta | p |
|---:|---:|---:|
| 1 | -1.129 | 0.464 |
| 2 | +1.538 | 0.301 |
| 3 | **+3.237** | **0.032** |
| 4 | **-3.646** | **0.006** |

Score spread 6.88 points. Seat 4 survives a Bonferroni correction across four
seats (p ~ 0.023). Taken at face value this refutes the structural account.

## It does not survive a stability check

Splitting the 60 games into three 20-game blocks:

| Subset | seat 1 | seat 2 | seat 3 | seat 4 |
|---|---:|---:|---:|---:|
| seeds 1-5 | +0.20 (0.93) | -1.50 (0.52) | +2.10 (0.47) | -0.80 (0.73) |
| seeds 6-10 | -1.18 (0.65) | +5.58 (0.08) | -2.08 (0.27) | -2.33 (0.36) |
| seeds 11-15 | -2.41 (0.45) | +0.54 (0.77) | **+9.69 (0.00)** | **-7.81 (0.00)** |
| excluding seeds 1-5 | -1.79 (0.38) | +3.06 (0.10) | +3.81 (0.03) | -5.07 (0.00) |
| excluding seeds 6-10 | -1.11 (0.57) | -0.48 (0.74) | +5.89 (0.00) | -4.31 (0.01) |
| **excluding seeds 11-15** | -0.49 (0.77) | +2.04 (0.32) | **+0.01 (0.99)** | **-1.56 (0.36)** |

Remove one block of 20 games and seat 3 goes from +3.24 (p=0.03) to **+0.01
(p=0.994)**. Seat 3 also flips sign across blocks: +2.10, -2.08, +9.69.

The pooled significance was one outlier block masquerading as a result across 60
games.

## Conclusion

**No conclusion about four-player seat order.** The structural account is neither
confirmed nor refuted, because there is no reliable effect to test it against.

The transferable finding is about method, not seats: per-game score variance is
roughly 15 points while plausible seat effects are about 2, so 20-60 game samples
produce spurious significance readily. Distinguishing a real seat effect needs
several hundred games per player count.

## State of the seat question

| Players | Structure | Measured |
|---|---|---|
| 2 | balanced | null, 0.09 points. Confident. |
| 3 | asymmetric | +3.63 on old agents (p=0.0009), -0.72 on current. Did not replicate. |
| 4 | balanced | fragile; nothing survives a stability check. |
| 5 | asymmetric | not run. |

Three apparent seat findings have now evaporated under scrutiny. Recommendation
is to park the question rather than keep sampling at this size, and to keep seat
counterbalancing regardless, since it removes the variance for free.

## Tooling added

`analysis/seat_effect_paired.py` now runs a leave-one-block-out check on every
report automatically. Any pooled effect that loses significance when a single
seed block is removed, or that flips sign across blocks, is labelled **FRAGILE**
with an explicit "do not report as a finding" warning.

This diagnostic was applied by hand here after the p-values had already been
computed and quoted. It now runs unprompted so that cannot happen again.
`tests/test_seat_effect_stability.py` pins the behaviour, including the exact
failure mode seen here: two quiet blocks plus one extreme block.
