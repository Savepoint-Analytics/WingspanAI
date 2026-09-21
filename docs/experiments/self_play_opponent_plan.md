# Self-play and human-trace opponents: is "the opponent barely matters" the game or the roster?

Status: design registered 2026-09-19; A1, A2 and A3 run 2026-09-20 (results at the end); A4 in flight.

## Why

Every strength claim in `results_ledger.md` is against one roster of
scripted opponents (two archetypes, the greedy baseline, the net-value
agent) whose best member wins 60% of its games and whose worst wins 27%.
Three findings rest on that roster and may not survive a strong opponent:

1. **The opponent model is worth ≈0 at two players.** Greedy, belief and
   oracle opponent models sit within ±0.3 of each other (2026-09-18). A
   scripted opponent rarely contests the card or die the search wants; a
   searching opponent will.
2. **Denial is worth nothing.** Opponent-aware denial and pink-power
   valuation came out −0.01 (2026-09-02) — against opponents that do not
   plan, so there was nothing to deny.
3. **"Strong" means strong against this roster.** 78.4 points and 0.875
   win rate say nothing about what the agent does when the other seat also
   plays birds at 35 points a game. The strategy questions the project was
   started for — dominant, dominated, situational play — are questions
   about strong-versus-strong play, and the archive has none.

The cheapest strong opponent is the champion itself. The most informative
one is a human. This plan registers both.

## Design A: mirror matches (self-play)

`potential_points` in every seat, at 2p and 3p, the research configuration
(unbudgeted, deterministic across processes, ADR 0004) so arms stay paired.

### Build (one day)

- `flows/simulation_batch.py::run_simulation_batch` already takes
  `player_agent_kinds`; the same kind twice yields distinct agent ids
  (`potential_points_p1`, `potential_points_p2`). Verify one seeded 2p mirror
  game runs, replays, and hashes identically across two processes.
- **Per-seat search config.** A mirror arm varies one seat's config (say,
  opponent model `belief` vs `greedy`) while the other seat stays at the
  default. Today `potential_points_search` is one config for every seat.
  Add `potential_points_search_by_seat: dict[str, PotentialPointsSearchConfig]`
  (seat → overrides), recorded per seat in the manifest, with the holdout
  draws keyed as they are now (seed, lineup, position) so both seats'
  holdouts stay paired.
- `analysis/arm_contrast.py` pairs on (lineup, rotation, seed); a mirror
  lineup names the same kind twice, so the contrast must read the **study
  seat** by lineup position, not by agent kind. Add `--study-position`.
- Cost: a 2p mirror game is 52 searching decisions at ~7.6 s under four-
  runner load (2 × 26 × 7.6 ≈ 6.6 min); 80 games ≈ 9 runner-hours, ≈ 2.5 h
  on four runners. 3p: 78 decisions ≈ 10 min a game; 90 games ≈ 4 h on
  four. Affordable, twice the cost of a roster arm.

### Registered arms, in order

| # | Arm | Design | Prediction | Reading |
|---|---|---|---|---|
| A1 | **Mirror baseline** `mirror_2p`, `mirror_3p` | 80 2p games (seeds 1–40, both rotations); 90 3p games (seeds 1–30, three rotations); default config both seats | Mean score falls from 78.4 to **70–74** (contested tray and feeder, no free round goals); seat 1 wins **0.52–0.58** at 2p | The strong-play score level and the seat effect in strong play; every later mirror arm pairs against it |
| A2 | **Opponent model in the mirror** | A1 with the study seat on `greedy` (2p and 3p) | 2p: **+1 to +3** for greedy (contention now exists); 3p: **+2 to +4** | If 2p is null here too, "the opponent barely matters at two players" is a property of the game, not the roster, and the opponent-model programme closes at 2p for good |
| A3 | **Denial term in the mirror** | study seat with the opponent-aware denial valuation on | **+1 to +3** (previously −0.01 vs the roster) | A null here means denial is not worth a search node even against a planner; a positive re-opens the net-value template for strong play |
| A4 | **Seat effect at 3p in strong play** | A1 3p, read by seat with the stability check of `seat_effect_power_analysis.md` | seat 1 **+1 to +3** over seat 3 (the champion already loses most from seat 3 vs the roster: 72.5 vs 76.2) | The first seat claim on strong play; needs 179 paired units for 2 points, so it is a pooled reading across mirror arms, not a verdict from A1 alone |

A1 is the baseline and the most useful of the four on its own: its games are
the first strong-versus-strong archive, and the strategy analysis below
runs on them.

### What the mirror archive answers descriptively (no new arms)

- **What does optimal-ish play look like?** Category composition (birds /
  eggs / goals / bonus / cache / tuck) of winners vs losers in the mirror,
  against the roster games' profile (2p roster games: the champion scores
  35.5 bird, 15.6 goal, 13.1 egg, 5.6 bonus points — a generalist, not a
  specialist).
- **Which archetype does the champion resemble?** The belief posterior's
  reading of `potential_points` seats (the oracle table has no row for it
  yet): a self-play row in `configs/belief/oracle_type_posteriors.json`.
- **Round-goal contention.** How often both seats commit to the same goal,
  and who wins it; the first real measurement of the competitive-goal
  scoring path.
- **Engine timing.** Turn of first brown-power activation, birds on the
  board by round, versus roster games.

### Production-config self-play for volume

The production configuration (`beam_leaf` + 5 s ladder, 1.1 s a decision)
plays a 2p mirror game in about a minute. It is load-dependent, so it is
not for paired arms, but for descriptive volume — 400 mirror games in an
afternoon on four runners — it is the instrument. Use it for the seed
coverage the card-value and round-goal questions need (the 2p roster
archive covers ten seeds), never for a ledger row.

## Design B: human traces

The project's one unrepresented opponent type. A human plays differently
from every scripted agent and from the search (longer horizons, weaker
arithmetic, real denial); a human archive tests the belief model's
calibration on the kind of player it was built for, and is the imitation
target `AGENTS.md` names.

### Build (one to two days)

- `HumanCliAgent` and `flows/human_vs_greedy.py` exist; make the opponent
  configurable (`potential_points` in production config, so the human waits
  ~1 s a turn) and the action renderer friendlier than raw `LegalAction`
  JSON (a standing backlog item since 2026-05-16). `render_action` from the
  game viewer is most of it.
- Telemetry is unchanged: a human game emits the same events, replays and
  hashes, and the game viewer steps through it from either seat.
- Setup choice through the CLI (`use_default_setup=False`).

### Registered study

- **H1, calibration.** Alex plays 10 games vs the production agent, seat
  swapped, seeds recorded. Score the belief model's family prediction on
  the human's decisions by sequential log loss (the instrument in
  `analysis/fit_response_model.py`), against its score on each roster kind.
  Prediction: log loss **worse than on every scripted kind** (the profiles
  were fitted to scripts); the fitted `random_legal` catch-all carries most
  of the posterior mass by round 2. A human row in the profile table is the
  follow-up if so.
- **H2, disagreement review.** Every decision where the human and the
  search's root ranking disagree by more than 2 points, through the game
  viewer. Output: a list of candidate registered arms (a strategy the human
  used that the search does not value), the purpose the viewer was built
  for.
- **H3, headline.** Human vs production agent, 10 games, seat-swapped:
  win rate and mean margin. Not a strength claim at n=10 (detection limit
  ~±8 points); the number the case study will be asked for first.

Ten games at ~30 minutes each is a weekend. More than ten is not worth
scheduling until H2 has produced its first arm.

## What we would conclude

| Outcome | Conclusion | Next |
|---|---|---|
| A2 null at 2p, positive at 3p | The 2p game is low-interaction: plan quality dominates; opponent modelling is a 3p+ concern | Close the 2p opponent programme; spend on 3p/4p |
| A2 positive at 2p | The roster masked interaction; the belief model needs a `potential_points`-like profile and denial is back on the table | A3, then a mirror-fitted profile row |
| A1 seat 1 ≥ 0.58 | First-player tempo is a real edge in strong play | Counterbalancing stays mandatory; a seat-equalizing rule variant is a fair study |
| H1 worse than every scripted kind | The belief model is a roster model, not an opponent model | Fit a human profile from the traces; test on the next 10 games |

## Success criteria for the plan as a whole

- A1 archived and read (score level, seat split, category profile) and one
  ledger row per mirror arm with its detection limit.
- Ten human games archived, replay-valid, viewable.
- The self-play and human rows added to `results_ledger.md` under a new
  "Strong-opponent studies" table, so the case study's limitations section
  ("one roster, no human games, no self-play") can be rewritten.

## Not in scope

Learning from the archive (imitation, value-function training) waits for
the human traces and the mirror archive to exist; the holdout design
(`standing_holdouts.md`) already guarantees a learner sees the losing side
of every decision. Expansion content is a separate track
(`docs/rules/expansion_configuration.md`, unwritten).

## Results

### A1 (2026-09-20): the strong-play baseline

`artifacts/mirror_2p` (80 games, seeds 1–40, both rotations) and
`artifacts/mirror_3p` (90 games, seeds 1–30, three rotations), default
research config in every seat, at `519cffb`. Read with the rotations of a
seed collapsed to one observation, because identical configs in every
seat make the two rotations the same game except for agent ids and
holdout draws (28 of 40 seeds identical at 2p, 15 of 30 at 3p).

| | 2p mirror | 2p vs roster | 3p mirror | 3p vs roster |
|---|---:|---:|---:|---:|
| mean score | **75.3** (sd 12.8) | 78.4 | **78.3** (sd 12.8) | 74.2 |
| birds / seat-game | 7.33 | 7.35 | 7.82 | — |
| seat-1 win rate | **0.575** | — | 0.400 (seat 3: 0.228) | — |
| seat 1 − last seat | **+5.1** (p=0.051, n=40) | — | +2.9 (p=0.17, n=30) | — |
| winners' profile (birds / goals / eggs) | 36.4 / 15.8 / 14.0 | — | 39.7 / 14.2 / 16.2 | — |
| losers' profile | 32.8 / 12.0 / 11.4 | — | 35.4 / 10.0 / 14.4 | — |

Predictions: 2p score 70–74 (**missed high**: 75.3 — contention costs
three points, not four to eight); seat-1 win 0.52–0.58 (**hit**: 0.575).
At three players the mirror scores *higher* than against the roster
(78.3 vs 74.2): searching opponents play more birds (7.8 a seat) and
contest the round goals less effectively than the scripted bots' flat
gain-food / draw mix does, so the goal category is where the 3p mirror
gains. The champion's round-shaped action mix (draws 27% → 11%, eggs
22% → 40% from round 1 to 4 at 2p) is unchanged against itself.

**Seat.** The first seat signal in strong play: +5.1 points and a 0.575
win rate for the first player at two players, at the edge of what 40
seeds can resolve (limit ≈ 7 points at 80% power). It is the same sign and
about the size the plan predicted, and it needs A2's 80 games pooled
before it is a finding. At three players seat 3 wins 0.23 of games against
0.40 for seat 1 — the same "third seat is hardest" pattern the roster
games showed for the champion (0.67 vs 0.83).

**Holdouts in a mirror.** With five 5% holdouts drawn independently per
position, 30 of 80 two-player mirror games and 48 of 90 three-player
games deviate from the default somewhere. Paired arms are unaffected (the
draws are keyed on seed, lineup, position), but a mirror baseline is a
noisier estimate of "default vs default" than its game count suggests;
retire holdouts as they become readable (`standing_holdouts.md`).

### A2 at 2p (2026-09-20): null; the two-player opponent question closes

`mirror_2p_greedy` (position 1 on `search_opponent_model="greedy"`, 80 games
paired vs `mirror_2p`, `8d35fdd`): study seat **+0.46 (p=0.62)**, win
−0.006; the other seat +0.68 (p=0.51) — both inside noise, 7 identical
games. Decision 3.9 → 6.0 s (×1.55), so the greedy model is a **drop or
gate** on the price list. Registered +1 to +3 failed.

This was the arm the plan said would decide the question: against the
scripted roster every opponent model tied at 2p, and the objection was
that scripted opponents never contest anything. Now the opponent is the
champion itself, contention exists (score fell 78.4 → 75.3), and the
imagined opponent's family still does not matter. **At two players the
opponent model is a cost knob, not a strength knob: keep the cheapest one
that plays coherently.** `belief` stays; nothing to hold out.

**Seat, pooled A1 + A2** (`analysis/mirror_seat_effect.py`, one observation
per seed and root, rotations averaged so the study config cancels): seat 1
**+3.89 (p=0.014)**, win 0.559 / 0.441, over 160 games. The caveat: both
arms use seeds 1–40, so these are 80 observations on 40 decks and the p is
optimistic. The 2p first-player advantage is now the best-supported seat
claim in the project (sign predicted, size ≈ 4 points, two arms agree), one
independent-deck replication short of established. **A3 keeps seeds 1–40
to stay paired with A1; A4's seat reading should add a fresh-seed mirror
(seeds 41–80) rather than more arms on the same decks.**

### A2 at 3p (2026-09-20): ≈+2 again; real, and priced

`mirror_3p_greedy` (position 1 on `greedy`, 90 games paired vs `mirror_3p`,
`8d35fdd`): study seat **+1.89 (p=0.072)**, win −0.011; the two other
seats +0.53 and +0.18 (n.s.); 10 identical games. Decision 5.5 → 8.5 s
(×1.55), +0.18 points per second: **drop or gate** on the price list.
Registered +2 to +4: the point estimate sits just under the band.

Read with the roster arm (`rr3p_opp/greedy` − belief: +2.12, p=0.073), this
is the second independent 90-game contrast at three players to land at
≈+2 with p≈0.07, against different opponents (scripted, then the champion
itself). Combined, p≈0.01: **the greedy opponent model is worth about two
points at three players, and nothing at two.** It is a score effect, not a
win effect (win rate flat in both), and four cheaper models that tried to
reproduce it — oracle type, `belief_apply`, the refit, `competent` — all
failed, so what greedy has is the applied branch state itself, at its full
cost. The pooled greedy holdout (51 games, mostly 2p) reads the other way
and is unreadable at its limit; the 3p holdout games will accrue.

**Decision.** `belief` stays the default at every player count. The
production agent at 3p already runs against its 5 s cap with belief
(p95 by round 3–11 s unbudgeted), so greedy cannot ship there; for
research arms +2 at ×1.55 is the same price class as the fourth
determinization sample (+0.33/s, kept) and the K arm (−2.0 for ÷5), a
judgement call the ledger records rather than makes. If a 3p production
budget above ~10 s is ever acceptable, greedy is the first thing to buy.
Registered for the record: **`rr3p` re-baseline on greedy only if a 3p
strength question needs the two points** — there is none queued.

**Seat at 3p, pooled A1 + A2** (180 games, 30 decks): seat 1 − seat 3
+1.44 (p=0.30), win 0.344 / 0.372 / 0.283. Seat 3 remains the hard seat
in every 3p root the project has (roster: 0.67 vs 0.83), never at
significance; a fresh-deck 3p mirror (A4) is the replication.

### A3 (2026-09-20): denial is a liability, not a term

`mirror_2p_denial` (position 1 with `search_denial_weight=1.0` — the
`net_value` shared-resource denial value added to every root action's
search value; 80 games paired vs `mirror_2p`, `dfa2d71`): study seat
**−5.94 (p<0.001)**, win 0.500 → 0.344; the other seat +0.42 with win
0.656; 0 identical games. Registered +1 to +3: failed by nine points.

The mechanism is in the action mix. With the term on, the study seat's
draw share rises from 24% to 33% of actions (tray draws 371 → 657 over
the 80 games; in round 4 draws go 10% → 23% of actions) and it plays 6.7
birds a game instead of 7.4, laying 2.2 fewer egg points. The term prices
a tray card at what it would do on the opponent's board, and against a
searching opponent that price is real — but the opponent simply draws the
next card, the tray refills, and the denying seat has spent an action
and holds a card it did not want. Denial against a refilling supply is
paid on every turn and repaid on none. It is the synergy hand term's
lesson again (−4.5, 2026-09-17): any term that pays the agent to take a
card for a reason other than its own plan loses more than the reason is
worth.

**Decision.** Dropped; `search_denial_weight` stays 0. No holdout, on the
precedent of the synergy hand term: the loss is large, the cause is
understood, and a 5% minority of games played six points worse would be
a cost with nothing to learn. The 3p arm (`mirror_3p_denial`, same weight,
same mechanism) was stopped four minutes in as answered. A lower weight
(0.25) is a legitimate follow-up if anyone wants to know whether *some*
denial is free; the registered prediction would be a null, and it is not
queued. The plan's reading stands as written: denial is not worth a
search node even against a planner.
