# Seat-Order Investigation at Three Players

Status: **the effect did not replicate**, 2026-09-03

## What prompted it

The 2026-09-02 seat study measured, at three players, a significant advantage to
seat 3 and a penalty to seat 1:

| Seat | Paired delta | p |
|---:|---:|---:|
| 1 | -2.505 | 0.025 |
| 2 | -1.130 | 0.396 |
| 3 | **+3.634** | **0.0009** |

Two players showed nothing (0.09 points). The question was why acting last would
help, and why only at three players.

## Step 1: decompose the effect by score category

Over the 72 paired units from that run:

| Category | Seat 1 | Seat 2 | Seat 3 | Seat-3 edge | p |
|---|---:|---:|---:|---:|---:|
| round_goal_points | 9.19 | 9.79 | 10.89 | **+0.931** | **0.0096** |
| tucked_card_points | 5.10 | 4.62 | 6.07 | +0.806 | 0.120 |
| bonus_points | 2.50 | 4.00 | 4.26 | +0.676 | 0.061 |
| cached_food_points | 3.85 | 2.72 | 4.15 | +0.579 | 0.125 |
| egg_points | 8.79 | 8.81 | 9.33 | +0.356 | 0.480 |
| bird_points | 32.00 | 32.86 | 32.86 | +0.287 | 0.688 |

End-of-round goals were the largest single contributor and the only significant
one, but only about a quarter of the total, and **every** category favoured seat
3. That breadth argued against a purely goal-information explanation.

## Step 2: the structural asymmetry is real

Turn order follows `active_player_index = completed_round % player_count`, so
across four rounds:

| Players | Rounds started | Rounds ended | Symmetric? |
|---|---|---|---|
| 2 | [2, 2] | [2, 2] | yes |
| 3 | [**2**, 1, 1] | [1, 1, **2**] | **no** |
| 4 | [1, 1, 1, 1] | [1, 1, 1, 1] | yes |
| 5 | [1, 1, 1, 1, **0**] | [1, 1, 1, **0**, 1] | **no** |

At three players seat 1 starts two rounds while seat 3 ends two and also takes
the final action of the game. At two and four players the schedule is perfectly
balanced.

This is derived from the rules, not measured, so it is not sample-dependent. It
also explains the two-player null cleanly: there was no asymmetry to detect.

## Step 3: the effect did not replicate

Re-ran three-player games on the corrected simulator with current agents
(`potential_points`, `guardrailed:potential_points`, `net_value_response`,
`guardrailed:net_value_response`), 60 games, full seat counterbalancing.

| Seat | 2026-09-02 | 2026-09-03 |
|---:|---:|---:|
| 1 | -2.505 (p=0.025) | **+2.017** (p=0.075) |
| 2 | -1.130 | -1.300 |
| 3 | **+3.634** (p=0.0009) | -0.717 (p=0.575) |

Seats 1 and 3 swapped sign and nothing reaches significance.

## Step 4: removing end-of-round goals

Identical design with the competitive goals stripped at the content boundary, so
no agent can chase or score them:

| Seat | With goals | Without goals |
|---:|---:|---:|
| 1 | +2.017 | +1.272 |
| 2 | -1.300 | -0.078 |
| 3 | -0.717 | -1.194 |
| **spread** | **3.32** | **2.47** |

Removing goals shrinks the spread from 3.32 to 2.47 points, consistent with goals
contributing something, but neither arm has a significant seat and the ordering is
unchanged. Average scores fall from ~58 to ~47, confirming the goals were removed.

## Conclusion

**The seat-3 advantage is not a robust property of the game.** It appeared once,
strongly, and reversed sign when re-measured after the agents changed.

The most likely reading is that it was a *policy* artifact. Between the two runs
the agents gained opponent-aware denial, corrected bonus scoring, tray-card
preference and mat-yield valuation, and `net_value_response` was in both rosters.
A seat effect that flips direction when agents improve is more likely a property
of how those agents played than of the turn structure.

What survives:

- The **structural asymmetry** at 3 and 5 players is real and derived, and
  explains why 2 players shows nothing.
- Whether that asymmetry produces a measurable advantage, and in which direction,
  is **not established**.

## Falsifiable prediction, still open

If the asymmetry does drive a real effect, it should appear at 3 and 5 players and
vanish at 4. Four players is the cheapest decisive test: an effect there would
falsify the structural explanation outright.

## Caveats

- 60 games per arm, one roster. Underpowered for effects below ~2 points.
- The two runs differ in roster and seed range as well as agent version, so this
  is not a strict replication.
- `seat_order_study_v1.md` should be read alongside this document; its three-player
  result should no longer be quoted on its own.
