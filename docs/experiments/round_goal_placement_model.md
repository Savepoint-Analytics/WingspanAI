# Round goals: measurement, a placement model, and a four-goal opener

Registered 2026-09-22. Three pieces: a per-round event so goal outcomes are
queryable, a replacement for the evaluator's goal heuristic, and an opener
that reads all four goals.

## 1. What the archive says about round goals (measurement)

`analysis/round_goal_report.py` over the two clean 2p mirror baselines
(A1 + A4, 160 games, equal agents in both seats):

| round | pays 1st/2nd | seat 1 wins | seat 2 wins | tie | nobody | margin ≤1 | seat-1 pts | seat-2 pts |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4/1 | **0.581** | 0.156 | 0.125 | 0.138 | 0.44 | 2.59 | 1.08 |
| 2 | 5/2 | 0.344 | **0.456** | 0.150 | 0.050 | 0.61 | 2.79 | 3.11 |
| 3 | 6/3 | 0.419 | 0.419 | 0.156 | 0.006 | 0.55 | 4.11 | 3.92 |
| 4 | 7/4 | **0.525** | 0.319 | 0.156 | 0.000 | 0.53 | 5.53 | 4.71 |

- **The round-1 goal belongs to the first player**: +1.51 goal points
  (p<0.0001), a quarter of the whole +6.16 first-player advantage. Goals
  over all four rounds are +2.21 of it.
- **The edge follows the first-player token and then fades.** Round 2 (seat
  2 goes first) reverses; round 3 is level. Tempo decides early goals,
  accumulated board decides late ones.
- **Goals are decided at the margin**: 44–61% of decided rounds turn on one
  item or a tie; ties are 13–16% and cost the leader two points.

Emitted from 2026-09-22 as `round_goal_scored` (per round, including round
4), so none of this needs a replay again.

## 2. The placement model (registered arm)

### What the heuristic could not say

```python
gap = best_opponent_count - my_count + 1
leading            -> min(2.0, turns_left * 0.35)
gap > turns_left   -> 0
otherwise          -> (turns_left - gap + 1) * 0.6
```

No placement scale (round 4 pays 7/4/3, round 1 pays 4/1 — scored the
same), no opponent turns, no ties, no player count.

### The replacement

`agents/round_goal_model.py`: each player's final count is their current
count plus a Poisson draw with mean `rate(goal) × turns_left`; placement is
the rank of the final counts; the value is

    E[points] = Σ_placement P(placement) × scale[round][placement]

with ties splitting slots rounded down exactly as
`score_round_goal_competitive` does. Rates are measured, not guessed:
`analysis/fit_round_goal_progress.py` replayed 410 games (mirror + roster,
2p and 3p) for ~30,000 observations of "items gained from here", giving
per-goal rates from 0.078/turn (`[platform] [bird] with [egg]`) to
0.349/turn (`[egg] in [platform]`), pooled 0.19 for unseen goals —
`configs/round_goals/progress_rates.json`.

Sanity, round 1 scale, two players: settled 2–1 = 4.0, settled 1–1 = 2.0
(the tie split), settled 1–2 = 1.0, no items = 0.0. Tied 3–3 with two turns
each is worth **5.35 in round 4 against 2.35 in round 1** — the correction
the heuristic could not express.

### Registration

`round_goal_model="placement"` vs the default `heuristic`.

- **2p, 80 paired games vs `rr_belief_opp`: 0 to +2.** The mechanism is a
  reweighting of a term already in the evaluator, not a new incentive
  (contrast the synergy and denial terms, −4.5 and −5.9, which paid the
  agent to act for reasons outside its plan). The search already sees goal
  scoring exactly in the last turns of a round, so the gain should come
  from the early- and mid-round decisions the heuristic mispriced.
- **3p, 90 paired games vs `rr3p_opp/belief`: +1 to +3.** Second place
  pays at three players (5/2/1, 6/3/2, 7/4/3), which the heuristic ignores
  entirely, so the correction should be larger.
- Cost: one Poisson convolution per evaluated state, ~0.1 ms; expect ≤ 5%
  latency.
- ≥ +1 at either count adopts, with a `heuristic` holdout at 5% and a
  production-config re-check. A negative says the mispricing was load-
  bearing — that the flat term's over-valuation of early goals was
  accidentally correct — and the honest record is a drop with the reason.

### Result at two players (2026-09-22)

`artifacts/rr_goal_placement` vs `rr_belief_opp`, 80 paired games at
`1b380e7`: **+0.41 (p=0.69)**, win 0.875 → 0.912 (+0.037, p=0.41), 8
identical games. Inside the registered 0 to +2 band, under the +1
adoption bar: not adopted at 2p.

The interesting part is the decomposition, because the arm did exactly
what it was built to do and the points did not follow:

| category | heuristic | placement | Δ | p |
|---|---:|---:|---:|---:|
| round goals | 15.62 | 16.46 | **+0.84** | **0.011** |
| birds | 35.54 | 34.79 | −0.75 | 0.26 |
| bonus | 5.58 | 5.16 | −0.41 | 0.36 |
| eggs / cache / tuck | 21.67 | 22.41 | +0.74 | — |
| **total** | **78.41** | **78.83** | **+0.41** | 0.69 |

Goal win share rose 0.656 → 0.700 and goal points a round 3.91 → 4.12
(`round_goal_report.py --by-agent`). So the model wins the goals it aims
at, significantly — and pays for them with birds not played and bonus
progress not made, netting about zero.

**Reading.** At two players a round goal is worth 3 points of placement
swing and an action is worth about 3, so the trade is close to fair by
construction; the old heuristic was structurally wrong (no scale, no
opponent turns, no ties) but *aggregately* well calibrated at 2p — it
over-valued early goals by about as much as it under-valued late ones.
This is the first arm in the project where a term did what it claimed and
the claim turned out to be worth nothing, which is a different and more
useful null than the synergy and denial losses.

The 3p arm is the real test: second place pays there (5/2/1, 6/3/2,
7/4/3), so the marginal action buys placement the 2p game cannot.

### Result at three players, and the decision (2026-09-22)

`artifacts/rr3p_goal_placement` vs `rr3p_opp/belief`, 90 paired games at
`1b380e7`: **+1.12 (p=0.128)**, win 0.761 → 0.789, 18 identical games.
Inside the registered +1 to +3 band at its low edge.

| category | heuristic | placement | Δ | p |
|---|---:|---:|---:|---:|
| round goals | 12.77 | 13.22 | +0.46 | 0.16 |
| eggs | 13.29 | 14.26 | +0.97 | 0.11 |
| birds | 35.12 | 34.86 | −0.27 | 0.66 |
| bonus | 5.41 | 4.96 | −0.46 | 0.24 |
| **total** | **74.19** | **75.31** | **+1.12** | 0.128 |

The three-player composition is *not* the two-player one. At 2p the model
bought +0.84 of goal points and paid −0.75 in birds. At 3p it takes less
goal value (+0.46) and pays almost nothing for it (−0.27 birds), with the
gain showing up in eggs (+0.97). That is what a correctly priced goal term
should do when second place pays: it declines contests it would lose
(three players, one winner, second place worth 2–4) and spends the action
on something certain. The heuristic, which ignores second place entirely,
cannot make that call.

**Decision: adopted**, per the pre-registered rule (≥ +1 at either player
count). The evidence is weak and the record should say so: +1.12 at
p=0.128 against a ~2-point detection limit, +0.41 at 2p, combined +0.79
(p=0.17). Three things carry it past the bar besides the point estimate —
both counts point the same way, the mechanism is confirmed significantly
at 2p (goal points +0.84, p=0.011), and the term is *structurally* correct
where its predecessor was structurally wrong (it reads the round's real
scale, the opponents' remaining turns, ties, and the player count), which
matters more as expansion rulesets bring their own goal scales. Cost is
about 0.1 ms a state.

Guarded as every decided switch is: `Holdout("round_goal_model",
"heuristic")` keeps the old rule alive in a deterministic 5% of games.
**Re-baselined**: `rr_goal_placement` (2p) and `rr3p_goal_placement` (3p)
are the roots later arms pair against. **Registered follow-up**: the
production configuration (`beam_leaf` + 5 s ladder) gets its own 80-game
re-check with the new default, as every search change does.

## 3. Four-goal opener (registered arm, expected null)

All four goals are public at setup; the opener read round 1's alone.
`goal_horizon="all"` (policy id suffix `_allgoals`) adds the later goals
weighted by `0.55^(r-1) × scale[r]/scale[1]`: worth more when scored,
discounted for distance and for the chance they are reached anyway.

**Registered: null, ±1**, on the opener precedent — the `expected_points`
opener (−3.0), the measured opener (−1.9) and the plain opener are all
within two points of each other, and card-choice terms at setup have never
moved the needle. Worth one arm because it is nearly free and because the
round-1 measurement above shows the first goal is a real prize.

## Reading the arms

    python analysis/arm_contrast.py --baseline artifacts/rr_belief_opp --arm artifacts/rr_goal_placement
    python analysis/arm_contrast.py --baseline artifacts/rr3p_opp/belief --arm artifacts/rr3p_goal_placement
    python analysis/round_goal_report.py artifacts/rr_goal_placement --by-agent
    python analysis/decision_profile_report.py artifacts/rr_goal_placement --value-against artifacts/rr_belief_opp
