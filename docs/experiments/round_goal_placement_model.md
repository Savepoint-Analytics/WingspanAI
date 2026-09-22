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
