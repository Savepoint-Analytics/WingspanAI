# How Big a Seat Effect Can This Design Detect?

Status: 2026-09-04. Supersedes the hand-waved "several hundred games per player
count" quoted in earlier seat write-ups.

## Why

Four apparent seat findings have dissolved under scrutiny, and each time the
answer to "how many games would settle it?" was asserted rather than computed.
This computes it from the measured variance in `artifacts/rrv5`.

## The right variance

The estimator is a one-sample t-test on **within-agent seat deltas**, so the
relevant spread is the standard deviation of those deltas, not of raw scores:

| Quantity | Value |
|---|---:|
| Raw per-game score SD | 16.40 |
| Paired seat-delta SD | **9.54** |

Counterbalancing removes **42%** of the spread by differencing out agent strength
and deck luck. Using the raw 16.40 would overstate the games needed by a factor
of roughly three, which is where the inflated earlier estimate came from.

## What each sample size buys

Two-sided test at alpha 0.05, 80% power:

| Paired units | Smallest detectable effect |
|---:|---:|
| 20 | 5.98 points |
| 60 | 3.45 points |
| 200 | 1.89 points |
| 400 | 1.34 points |

| Effect to detect | Paired units needed |
|---:|---:|
| 5.0 points | 29 |
| 3.0 points | 80 |
| 2.0 points | 179 |
| 1.5 points | 318 |
| 1.0 points | 714 |

## The important consequence

The failure mode is not mainly false positives. It is **inflated estimates**.

A study powered only for large effects does not merely miss small ones. When it
*does* reach significance, the estimate is necessarily large, because only an
unusually big sample fluctuation could have crossed the threshold. Significance
and overestimation arrive together.

That is exactly what happened at four players. With 60 paired units the design
could only detect effects of **3.45 points or more**. It reported **+3.24** —
sitting right at its own detection limit, which is the signature of this problem
rather than of a real effect. A leave-one-block-out check put the effect near
zero, as expected.

Read the earlier seat numbers with this in mind: **+3.63 (3 players, p=0.0009)**
and **+3.24 / -3.65 (4 players)** are all near the detection limits of the runs
that produced them.

## What this means for the seat question

Plausible seat effects in this game are around 2 points. Detecting that reliably
needs **~179 paired units per player count** — not the "300+" previously quoted,
and well within reach: the 200-game two-player run already clears it.

So the seat question is answerable, and more cheaply than assumed. The two-player
answer, at adequate power, is **null**. Three, four and five players have never
been run at adequate power; the 60-game runs were roughly a third of what they
needed.

Whether that is worth ~4 hours of compute is a judgement call, but it should be
made against 179 rather than a guess.

## Reproducing

```bash
PYTHONPATH="$PWD/src:$PWD:$PWD/analysis" \
  ./.venv/bin/python analysis/seat_power_analysis.py --artifact-root artifacts/rrv5
```

Runs per player count present in the artifacts, so a future multi-count run
reports each separately.
