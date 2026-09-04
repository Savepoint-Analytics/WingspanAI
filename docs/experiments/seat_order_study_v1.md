# Seat Order Study v1: Does Turn Order Matter?

Status: first result, 2026-09-01. **The three-player finding did not replicate**
on 2026-09-03 and reversed sign; see `seat_order_investigation_3p.md`. Do not
quote the three-player result on its own.

Plan: `seat_order_study_plan.md`. Seat handling rationale: ADR 0002.

## Question

Does turn order matter, at which player counts, and by how much?

## Pre-registered prediction

The plan predicted the seat effect would be **largest at three players and
smallest at two**, from round-start accounting. With four rounds and the token
rotating `completed_round % player_count`:

- 2 players: seat 1 starts rounds 1 and 3, seat 2 starts 2 and 4 — balanced.
- 3 players: seat 1 starts rounds 1 **and** 4; seats 2 and 3 start one each.

**This prediction was not supported.**

## Setup

- Roster: `greedy_immediate` plus four archetypes (cheap on purpose — seat effect
  is a property of turn structure, not policy sophistication).
- Seeds 1-15, `control` setup policy only, so openings cannot confound seat.
- Full seat counterbalancing: every agent occupies every seat exactly once per
  lineup per seed (ADR 0002).
- 2 players: 10 lineups x 2 rotations x 15 seeds = **300 games**.
- 3 players: 10 lineups x 3 rotations x 15 seeds = **450 games**.
- Run on the post-ADR-0004 simulator, so results are reproducible.

## Results

### Win rate versus fair share

| Players | Seat | n | Win rate | vs fair | p |
|---:|---:|---:|---:|---:|---:|
| 2 | 1 | 300 | 0.5283 | +0.0283 | 0.326 |
| 2 | 2 | 300 | 0.4717 | −0.0283 | 0.326 |
| 3 | 1 | 450 | 0.3263 | −0.0070 | 0.751 |
| 3 | 2 | 450 | 0.3507 | +0.0174 | 0.433 |
| 3 | 3 | 450 | 0.3230 | −0.0104 | 0.641 |

### Paired score contrast

Counterbalancing lets each agent be compared against *itself* across seats,
differencing out agent skill and deck luck. This is the more powerful test.

| Players | Seat | Paired delta vs own mean | t | p |
|---:|---:|---:|---:|---:|
| 2 | 1 | +0.912 | +1.43 | 0.154 |
| 2 | 2 | −0.912 | −1.43 | 0.154 |
| 3 | 1 | +1.156 | +1.82 | 0.069 |
| 3 | 2 | −0.617 | −0.97 | 0.333 |
| 3 | 3 | −0.539 | −0.81 | 0.418 |

Raw score spread, best to worst seat: **1.82 points at 2 players, 1.77 at 3**.

## Findings

### 1. No statistically significant seat effect at either player count

Nothing reaches p < 0.05. The largest signal is seat 1 at three players
(+1.156 points, p = 0.069), and that is uncorrected — with three seats tested,
a Bonferroni correction puts it at p ≈ 0.21.

### 2. The effect, if real, is about one point

Point estimates cluster around 1.0-1.2 points on a ~53-point average score, so
roughly **2%**. For comparison, the gap between the best and worst agent in the
baseline matrix is over 30 points. Turn order is not a major factor at these
player counts.

### 3. The prediction that three players would show a larger effect is wrong

Score spread is 1.82 at two players and 1.77 at three — indistinguishable. The
round-start asymmetry at three players (seat 1 starting two of four rounds) does
not translate into a measurable advantage. The most likely reason: starting a
round confers only resource *priority*, not extra turns, and every player gets
the same number of action cubes regardless.

### 4. Win-rate and score estimates disagree in direction at three players

Seat 1 scores about 1.2 points **more** on average while winning slightly **less**
often (0.3263 against a 0.3333 fair share). A real seat advantage should move
both together. The disagreement is itself evidence against a genuine effect and
in favour of noise.

## Verdict

At two and three players, with counterbalanced seats and this roster, **turn
order does not measurably matter**. Continue counterbalancing anyway: it costs
`player_count` runs per lineup and removes a variance source that would otherwise
have to be assumed away.

The pre-2026-08-31 round robin appeared to show large per-matchup seat effects
(three matchups reading 0.000 in one seat and 1.000 in the other). Given this
result, those were most likely small-sample artifacts of 5 seeds per cell,
compounded by the then-unfixed cross-process determinism bug.

## Caveats

- 15 seeds, one setup policy, one roster of cheap agents. Underpowered to detect
  an effect smaller than about 1.5 points.
- 4 and 5 players not run. The round-start asymmetry is different again there
  (at 5 players seats 1-4 each start one round and seat 5 starts none), so this
  result does not generalize upward.
- Score levels are not comparable across player counts; only within-count seat
  contrasts are.

## Analysis note

An earlier aggregation of these numbers was contaminated: it swept in the 130
`baseline_matrix10_v2` games, where seat 1 is *always* the weak `random_legal`
agent. That produced an apparent significant seat-1 *disadvantage* at two players
(0.4439, p = 0.023). Restricting to counterbalanced seat-order cells removed it.
Seat statistics must only ever be computed over counterbalanced designs.

## Follow-up

- [ ] Extend to 4 and 5 players, where the round-start asymmetry is strongest.
- [ ] Raise seeds to 30+ if a sub-1-point effect is worth resolving.
- [ ] Fix the shared per-seat agent RNG seed before any mirror-matchup seat work.
- [ ] Re-check the round robin's per-matchup seat artifacts now that the
      aggregate effect is known to be near zero.
