# Game Horizon Ablation: The Round Horizon Is Load-Bearing

Status: complete, 2026-09-07
Code: `042f2d2` on branch `game-horizon-ablation` (39 of 40 manifests report
`dirty: true`; the only change was a tracked `.DS_Store` that Finder rewrote
during the run, now untracked — no source differed from the commit)
Artifacts: `artifacts/rr_horizon_game/`, mirrored to object storage
Baseline: `artifacts/rr_reroll_fix/` from
[reroll_chance_node.md](reroll_chance_node.md)

## The question

`potential_points` evaluates a state by summing "potential" terms — playable
birds, food and egg conversion, engine powers, habitat yield, round goals —
each scaled by the turns the player has left. `_turns_remaining_for_player`
has always returned the player's remaining action cubes *this round*, so at a
round's last cube every potential term is discounted to nothing and the search
leaf scores realized points only. The search-depth write-up flagged this as
the next ablation: an agent that counts the whole game's remaining turns
should, on the face of it, value engine-building more accurately in rounds
1–3.

## Method

`PotentialPointsAgent(planning_horizon="game")` makes
`_turns_remaining_for_player` return this round's cubes plus every later
round's (8/7/6/5 → 26 at the start of round 1). The horizon is threaded
through the evaluator, the search leaf and the terminal-value rule; the
endgame-search *trigger* still counts round cubes so the search fires on the
same turns in both arms. `"round"` reproduces the baseline bit-for-bit.

Only the four `potential_points` lineups were run (80 games, seeds 1–10, both
seat rotations, `control` setup, depth 3, every turn, K=4). The other 120 games
of the full design never touch the horizon and are identical to the baseline
by construction. Games are paired by lineup, rotation and seed.

## Results

| Arm | Score | Δ | p | Win rate |
|---|---:|---:|---:|---:|
| round horizon (baseline) | 79.09 | — | — | 0.906 |
| game horizon | 67.09 | **−12.00** | <0.001 | 0.631 |

Per opponent: `net_value_response` −13.7, `greedy_immediate` −12.9,
`archetype_bonus_card_focus` −11.8, `archetype_engine_builder` −9.7, all
p<0.001. Zero of 80 games were identical.

### Where the points went

| Category | round | game | Δ |
|---|---:|---:|---:|
| bird | 35.94 | 35.16 | −0.78 |
| round goal | 16.04 | 11.22 | **−4.82** |
| egg | 13.11 | 9.45 | **−3.66** |
| tucked | 4.91 | 3.77 | −1.14 |
| bonus | 5.71 | 4.91 | −0.80 |
| cached food | 3.38 | 2.56 | −0.82 |
| total | 79.09 | 67.09 | −12.00 |

Action mix, round → game: draw 23.8% → **37.3%**, eggs 27.5% → **18.7%**,
food 20.3% → 16.9%, bird 28.4% → 27.1%.

### Reading

The game-horizon agent draws cards on more than a third of its turns and lays
eggs on fewer than a fifth, and it loses almost exactly the round-goal and egg
points that the searching agent had gained over the historic one. The
mechanism is in the evaluator, not the search: every potential term is
linear in `turns_remaining`, so with 26 turns on the clock a card in hand or a
brown power on the board is worth several times what it was under the round
horizon, while a realized egg is still worth one point. The terminal rule
that scored realized points at a round's last cube — the thing the round
horizon "discounted to nothing" — was doing the work of telling the agent
when to cash in. Remove it and the agent optimises an inflated forecast it
never collects on.

So the round horizon is not a limitation to be lifted; it is the evaluator's
implicit model of Wingspan's round structure — goals are scored per round and
the action-cube clock resets — and the potential coefficients were tuned
against it. A true game-horizon evaluator would need discounting per round,
round-goal terms that know which rounds remain, and re-tuned coefficients.
That is a different evaluator, not a switch.

### Cost

Per game, `potential_points` spent a mean 737 s deciding under the game
horizon against 551 s under the round horizon (median 620 vs 395). Both arms
shared a heavily loaded machine, so treat this as indicative. The slowest
single decisions in *either* arm (1262 s baseline, 492 s game) were root nodes
with 70–107 gain-food preference actions, the cost flagged in
[reroll_chance_node.md](reroll_chance_node.md); the horizon is not the driver.

## What changes

- `planning_horizon` stays a supported switch with `"round"` as the default,
  recorded in manifests and decision summaries. `"game"` is a documented
  negative result, not an option to reach for.
- The search-depth write-up's "round horizon" caveat is resolved in the
  opposite direction from the one it anticipated.

## Caveats

- This ablates the horizon with the evaluator's coefficients held fixed. It
  shows the current evaluator does not extrapolate; it does not show that a
  properly built game-horizon evaluator would not beat the round horizon.
- The 80-game reduced design is exactly the 80 informative games of the
  200-game design; the paired contrast is the same test as before.
- One roster, two players, as with every result in this series.
