# Round Robin v5: Corrected Dice, and a Feeder-Odds Ablation

Status: complete, 2026-09-04. **Correctness fix retained; valuation term is a null.**

## Design

Five-agent roster, seeds 1-10, `control` setup, full seat counterbalancing, run
in five 2-seed chunks. 10 unordered pairs x 2 rotations x 10 seeds = **200 games
per arm**, 400 total. Same roster and seeds as v2, so the standings are
comparable.

Two arms differing in one flag:

- **on** — `VALUE_FEEDER_ODDS = True`
- **off** — `VALUE_FEEDER_ODDS = False`

The six-face die fix is active in **both** arms. It is a rules-correctness fix,
not a variable, so the contrast isolates exactly what the policy valuation
contributes. Arms ran sequentially, never concurrently, so neither distorted the
other's per-decision timing telemetry.

## Result 1: the feeder-odds valuation does nothing measurable

| Agent | Win on | Win off | Delta | p | Score delta | p |
|---|---:|---:|---:|---:|---:|---:|
| `potential_points` | 0.688 | 0.762 | -0.075 | 0.289 | -1.27 | 0.506 |
| `archetype_engine_builder` | 0.613 | 0.600 | +0.013 | 0.872 | -0.33 | 0.857 |
| `archetype_bonus_card_focus` | 0.487 | 0.525 | -0.038 | 0.637 | -0.52 | 0.846 |
| `net_value_response` | 0.463 | 0.400 | +0.062 | 0.427 | +0.96 | 0.687 |
| `greedy_immediate` | 0.287 | 0.263 | +0.025 | 0.725 | +1.11 | 0.691 |

Pooled average score: **59.38 on vs 59.39 off, delta -0.01 (p=0.993)**. Not a
weak effect — no effect at all.

This is the second modelling improvement in a row to measure as a null, after
mat-scaling valuation. Both closed a real gap between the simulator and the
game; neither changed outcomes. The consistent reading is that these heuristic
agents are not limited by the fidelity of their food or habitat valuation, so
sharpening it has nothing to bite on.

`VALUE_FEEDER_ODDS` stays `True`: the terms are more faithful than what they
replaced, and they cost nothing. But they are retained on correctness grounds
alone, and nothing downstream should treat them as an improvement.

## Result 2: the standings survived the corrected simulator

| Agent | Win rate | v2 | Avg score | v2 |
|---|---:|---:|---:|---:|
| `potential_points` | **0.681** | 0.756 | 68.46 | 66.81 |
| `archetype_engine_builder` | 0.606 | 0.550 | 61.77 | 56.77 |
| `archetype_bonus_card_focus` | 0.475 | 0.487 | 61.64 | 55.98 |
| `net_value_response` | 0.463 | 0.431 | 57.17 | 50.86 |
| `greedy_immediate` | **0.275** | 0.275 | 47.86 | 46.88 |

`potential_points` first and `greedy_immediate` last both hold, the latter at an
identical 0.275. Scores rose across the board, consistent with the bonus-scoring
fix roughly doubling bonus points.

**Do not read the per-agent movement as an effect.** v2 predates the
bonus-scoring rebuild, mat scaling, the die fix and feeder odds; any difference
is a four-change contrast. The middle three (0.463 to 0.606 at 80 games each)
are not separated.

Score integrity: categories sum to the reported total on every player-game
checked, and no category went unscored by everyone.

## Result 3: a fourth seat finding evaporates

Pooled, seat 1 reads **+1.567 points (p=0.0186)**.

At the default 5-seed blocking this looked like it might be a power artifact —
both halves agreed in sign (+1.31, +1.82) and leave-one-out halves the sample.
At the 2-seed blocking matching how the run was actually chunked, it is clearly
one block:

| Subset | seat 1 |
|---|---:|
| seeds 1-2 | +0.05 (p=0.97) |
| seeds 3-4 | +0.57 (p=0.60) |
| seeds 5-6 | **+5.54 (p=0.00)** |
| seeds 7-8 | +2.30 (p=0.16) |
| seeds 9-10 | -0.62 (p=0.73) |
| **excluding seeds 5-6** | **+0.57 (p=0.43)** |

Consistent with the earlier two-player null. Four apparent seat findings have now
dissolved.

**Method note:** set the stability block size to match how the run was actually
chunked. The default of 5 was less informative here than the 2 that mirrored the
run. A block size unrelated to how work was batched can both hide and manufacture
fragility.

## Follow-up

The power analysis this motivated is in `seat_effect_power_analysis.md`. It
supersedes the hand-waved "several hundred games" figure quoted in earlier
write-ups.
