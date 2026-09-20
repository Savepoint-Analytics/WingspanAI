# Self-play and human-trace opponents: is "the opponent barely matters" the game or the roster?

Status: design registered 2026-09-19; nothing run yet.

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
