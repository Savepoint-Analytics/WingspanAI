# Wingspan KPI taxonomy: what the persisted archive can answer

> **Re-run 2026-09-27 after the ADR 0006 reload. Read this note first.**
>
> The 2026-09-22 pass read 4,491 games. `game_id` was not unique (it omits the
> lineup and rotation), so a `games.game_id` primary key made 44.5% of the
> archive unrepresentable. After re-keying on `simulation_run_id` and
> reloading, the database holds **10,956 games / 23,346 player-games**.
>
> **Score-based sections are re-run and now trustworthy** (composition, by
> agent, head-to-head). The corrections are large — the champion's win rate
> falls 0.952 → **0.731** and its mean score 88.3 → **75.6** — because the
> collision was dropping champion games specifically.
>
> **Event-based sections are now re-run too** (2026-09-28). The event log was
> loaded from object storage with
> `scripts/load_events_from_object_storage.py`: 10,934 objects, 723,168 rows
> read, 440,437 newly inserted, zero objects failed. Coverage went from
> lopsided (99.9% of one seat, **0% of most seats**, 10.7% of the champion) to
> **99.1-100% on every seat**; 10,936 of 10,956 games now carry events.
>
> One real limit remains: `round_goal_scored` has only 3,208 rows because the
> event was first emitted 2026-09-22, so per-round goal *placement* still
> covers recent games only. Goal totals come from `game_scores` and are
> complete.
>
> Arm results in `results_ledger.md` are unaffected throughout — those read
> local artifacts keyed on (lineup, rotation, seed, ruleset).

Score sections re-run **2026-09-27** against the Savepoint Lab PostgreSQL
(`wingspan_ai.*`, **10,956 games / 23,346 player-games**) with
`analysis/kpi_report.py`. Event sections are from the 2026-09-22 pass
(4,491 games / 1,215,761 events) and are stale; see the note above.

`analysis/kpi_report.py` is the reproducible entry point added with this
re-run — the original pass existed only as
`notebooks/wingspan_kpi_walkthrough.ipynb`, which is why it could not be
re-run or diffed when the archive changed underneath it.

## Where the data is

| | Wingspan | GoT | Irish Gauge |
|---|---|---|---|
| PostgreSQL schema | **`wingspan_ai`** (moved off `public` 2026-09-24) | `game_of_thrones_ai` | `irish_gauge` |
| dbt project | **none** | `analytics.*`, 16 models | none |
| MinIO | `savepoint-ai/board-games/wingspan/` | same bucket | same bucket |

The schema question is settled — Wingspan no longer shares `public` with
MLflow's tables (`runs`, `metrics`, `experiments`…). Still open: the
hand-rolled 16-view layer in `analysis/sql/analysis_views.sql` does the job a
dbt project does for GoT.

## Coverage against the taxonomy

| section | coverage | why |
|---|---|---|
| Core scoring | partial | Final score and its six categories are in `game_scores`. **Per-round cumulative score and per-round delta need a score snapshot at each round end, which is not emitted.** |
| End-of-round goals | partial | Totals supported. Per-round placement needs `round_goal_scored` (emitted only from 2026-09-22, so no persisted game has it). Goal fit, rank volatility and points-left-on-the-table need a counterfactual placement. |
| Bonus cards | partial | Selection, seen pool and end-of-game fulfilment supported. Draft-time eligible pool needs bonus criteria evaluated against the opening hand; tags are recorded only for played birds. |
| Card / bird utilization | **supported** | Draw efficiency, habitat spread, power-colour mix, per-bird yield, activations. |
| Card recycling | partial | Activation counts visible; the cards cycled past and the rejected options are not recorded, so selection quality and best-of-N capture rate are unavailable. |
| **Food economy** | **missing** | **No event carries a player's food tokens.** Unspent food, waste rate, excess by type and engine overshoot cannot be computed at all. |
| Turn / action level | **supported** | Action mix per agent and round, habitat visitation, points per action. |
| Strategic archetype | partial | Specialization index and engine yield supported. Combo density needs power-text cross-references; the pivot flag needs a strategy-change label. |
| Comparative / positional | partial | Win margin, gap to runner-up, head-to-head supported. Relative rank by round needs the per-round snapshot. |

Two events gate most of the partials: `bird_scorecard` exists only for games
run after 2026-09-16 (3,841 of 4,491) and `round_goal_scored` only after
2026-09-22 (none persisted).

## What the archive shows

**The persisted archive is now the archive, for scores.** The 2026-09-22 pass
said "the persisted archive is not the research archive" and blamed
under-persistence. The real cause was the `game_id` collision (ADR 0006): the
games *were* persisted, and a broken primary key kept 44.5% of them out. After
the reload, `games` holds 10,956 of the 10,934 games object storage carries —
a 1:1 conversion with zero drops.

**Events are now loaded too.** `simulation_events` holds 723k rows across
10,936 of 10,956 games, with per-seat coverage between 99.1% and 100% — so the
event-derived numbers below are archive-wide rather than one study's. Only
`round_goal_scored` is still partial (3,208 rows; the event dates from
2026-09-22).

Either way, a cross-agent number here is a population statistic of what was
persisted, not a controlled contrast. For contrasts, pair by seed with
`analysis/arm_contrast.py`.

### Score composition, all 23,346 player-games (re-run 2026-09-27)

| category | avg | share | % of players scoring | max | was (4,491 games) |
|---|---:|---:|---:|---:|---|
| bird | 27.60 | 45.5% | 99.9% | 74 | 25.23 / 44.4% |
| round goals | 12.18 | 20.1% | 98.1% | 22 | 12.22 / 21.5% |
| eggs | 9.25 | 15.2% | 92.2% | 34 | 8.47 / 14.9% |
| tucked cards | 4.80 | 7.9% | 70.6% | 44 | 4.93 / 8.7% |
| cached food | 3.26 | 5.4% | 53.5% | 34 | 3.45 / 6.1% |
| bonus cards | 3.58 | 5.9% | **62.8%** | 37 | 2.54 / 4.5%, **50.5%** |

The shape of the score is stable under a 2.4× larger sample — birds just
under half, round goals a fifth, and the three fiddly categories (tucked,
cached, bonus) about 19% between them. That stability is worth more than any
single figure here: it is the first cross-check that the reload did not change
what the archive *is*, only how much of it is visible.

**The one claim that moved: "half of all player-games score zero bonus points"
is wrong.** It is **37%**, not 50%. The direction survives — against the
measured 6.4 points that the bonus-card *choice* is worth, a third of
player-games still realise none of it, and it is concentrated in the weak
agents (champion 5.4 bonus points, greedy 1.5). But the headline number was
inflated by the collision dropping champion games, which are the ones that
actually score bonus points.

### By agent (re-run 2026-09-27)

| agent | player-games | win | score | bird | bonus | goals | eggs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `potential_points` | 6,020 | 0.731 | 75.6 | 35.5 | 5.4 | 13.7 | 12.6 |
| `engine_builder` | 6,342 | 0.653 | 64.5 | 32.1 | 3.3 | 12.4 | 7.3 |
| `greedy_immediate` | 6,356 | 0.174 | 45.0 | 16.2 | 1.5 | 11.4 | 9.4 |
| `net_value_response` | 2,546 | 0.259 | 54.5 | 25.0 | 3.3 | 10.9 | 7.5 |
| `bonus_card_focus` | 2,072 | 0.377 | 61.1 | 29.1 | 6.0 | 11.4 | 7.1 |

**How much the collision distorted this:** the champion went from 463
player-games to 6,020 — a 13× increase — while engine builder only went
4,244 → 6,342. The bias was that non-uniform, because which game survived a
collision depended on listing order and `potential_points-vs-...` labels sort
after `archetype_*` and `greedy_*`. Its win rate falls **0.952 → 0.731** and
its mean score **88.3 → 75.6**.

The corrected figure is the credible one, and it cross-checks: `arm_contrast`
independently puts the champion at 75.3 in mirror self-play and 78–80 against
the roster, computed from local artifacts that never touched this database. The
old 88.3 agreed with nothing.

Round goals remain the **flattest** category across agents: greedy scores 83%
of what the champion scores on goals against 46% on bird points. As a share of
its own score greedy gets 25.3% from goals against the champion's 18.1% — the
goal is the category a weak agent can still reach, because qualifying takes one
bird. That claim is unchanged by the reload.

### Utilization, `fp_v2_P3_AcBc` (480 player-games, both agents)

> Scoped to one study by design, and left as-is for continuity. Archive-wide
> utilization is now available too — regenerate with
> `python analysis/kpi_report.py --events`.

| | engine builder | greedy |
|---|---:|---:|
| birds played | 9.16 | 3.86 |
| cards drawn → played | 0.964 | 0.952 |
| eggs on board | 6.01 | 9.28 |
| activations per bird | 3.25 | 5.87 |
| habitat HHI (1.0 = one row) | 0.415 | 0.534 |
| forest / grassland / wetland | 4.35 / 2.32 / 2.49 | 1.51 / 1.10 / 1.25 |
| first forest round | 1.00 | 1.37 |
| action mix (play / food / eggs / draw) | .352 / .186 / .172 / .290 | .148 / **.524** / .206 / .122 |
| points per action | 2.68 | 1.69 |

Greedy spends **52% of its actions gaining food** and plays 3.9 birds;
the engine builder spends 19% and plays 9.2. Greedy's higher activations per
bird is a denominator effect — few birds, each triggered often — not a better
engine.

### Bonus-card fulfilment by card (re-run 2026-09-28, archive-wide)

Of the birds a player actually played, the share tagged for the bonus card they
kept. The 2026-09-22 version of this table had 8 cards at 22-29 games each, from
one study's decks. This has **26 cards at 262-908 games each**, across every
agent.

| kept card | games | matching birds | fulfilment | was (22-29 games) |
|---|---:|---:|---:|---|
| Bird Feeder | 603 | 3.79 | **0.577** | 3.43 / 0.428 |
| Nest Box Builder | 627 | 3.64 | 0.551 | — |
| Omnivore Expert | 542 | 4.07 | 0.529 | — |
| Large Bird Specialist | 463 | 3.88 | 0.520 | 3.55 / 0.462 |
| Backyard Birder | 485 | 3.67 | 0.509 | — |
| Wildlife Gardener | 582 | 3.12 | 0.488 | 3.50 / 0.542 |
| Photographer | 821 | 3.23 | 0.486 | — |
| Platform Builder | 700 | 3.01 | 0.482 | — |
| Passerine Specialist | 427 | 2.91 | 0.457 | — |
| Enclosure Builder | 437 | 3.33 | 0.437 | 3.16 / 0.430 |
| Wetland Scientist | 568 | 2.66 | 0.401 | — |
| Viticulturalist | 274 | 2.49 | 0.390 | — |
| Food Web Expert | 577 | 2.65 | 0.365 | — |
| Fishery Manager | 262 | 2.60 | 0.353 | — |
| Prairie Manager | 842 | 2.19 | 0.348 | 1.68 / 0.243 |
| Cartographer | 908 | 2.37 | 0.342 | 1.45 / 0.231 |
| Rodentologist | 487 | 2.23 | 0.336 | — |
| Falconer | 611 | 2.12 | 0.330 | — |
| Forester | 394 | 2.28 | 0.303 | — |
| Bird Counter | 536 | 1.83 | 0.287 | 1.58 / 0.265 |
| Historian | 518 | 1.85 | 0.253 | — |
| Visionary Leader | 650 | 1.30 | 0.206 | — |
| Ecologist | 800 | 1.48 | 0.174 | — |
| Oologist | 337 | 1.07 | 0.140 | — |
| Anatomist | 426 | 0.73 | 0.102 | — |
| **Breeding Manager** | 391 | **0.68** | **0.082** | 0.24 / 0.031 |

**Breeding Manager being close to dead on arrival is now a finding, not a
hypothesis.** It was flagged from 25 games as "worth a proper paired study
rather than a claim"; on 391 games it is still last of 26, matching 0.68 birds a
game against the pool's best at 3.79. The old figures were *harsher* than the
truth (0.031 → 0.082) because they came from weaker agents' decks, but the
ranking held.

The spread is **7-fold, not tenfold** as the small sample suggested: 0.082 to
0.577. Every card in the old 8-card table kept its rough position, which is
reassuring about the method, while three of the eight had their levels shift by
more than 0.10 — which is why 25-game card tables should not be quoted.

`Anatomist` at 0.102 is second-worst and is a legitimate core card, not
contamination: the `[swift_start_asia]` suffix is a workbook naming artifact and
the `Set` column reads `core, asia` because the Asia swift-start pack reprints
it. Settled 2026-09-16 in `docs/rules/bonus_card_composition.md`.

### Fulfilment by agent — the archetype does what it says

| agent | games | birds played | matching the kept card | fulfilment |
|---|---:|---:|---:|---:|
| `bonus_card_focus` | 792 | 7.02 | 4.13 | **0.597** |
| `potential_points` | 3,659 | 7.71 | 3.49 | 0.442 |
| `net_value_response` | 792 | 5.59 | 2.17 | 0.368 |
| `engine_builder` | 4,394 | 8.36 | 2.83 | 0.334 |
| `greedy_immediate` | 4,631 | 3.93 | 1.29 | 0.310 |

This is a clean behavioural validation that was impossible before the load:
`bonus_card_focus` really does steer its plays toward its kept card, at nearly
twice greedy's rate, and it does so while playing *fewer* birds than
`engine_builder` — 8.36 birds at 0.334 fulfilment against 7.02 at 0.597. The
archetypes are doing what their names claim, which is worth knowing before any
of them is used as a baseline.

Note the champion sits mid-table at 0.442. It is not chasing its bonus card; it
scores 5.4 bonus points by playing well and taking the card's points where they
fall. Against `bonus_card_focus`'s 0.597 fulfilment and 6.0 bonus points — the
highest of any agent — for 14 fewer points overall, that is the whole
engine-vs-objective tradeoff in two rows.

### Head-to-head, all 23,346 player-games (re-run 2026-10-05)

> Restored 2026-10-05. This section was written on 2026-09-27 and silently
> deleted on 2026-09-28 by an index-based splice that replaced everything
> between two headings, including the section that sat between them. Found
> because the case study cited `+32.2` and a source check could not find it
> anywhere. Regenerated from the database, so the numbers are current rather
> than recovered.

Mean score margin and **outscored rate** (share of shared games where the agent
scored strictly more than that opponent — not the game win rate, and ties count
for neither side). Population statistics over whatever lineups were run, **not**
a balanced tournament.

| | vs `greedy` | vs `net_value` | vs `bonus_focus` | vs `engine_builder` |
|---|---|---|---|---|
| `potential_points` | **+32.2** (0.91) | +17.6 (0.82) | +15.0 (0.80) | +17.0 (0.86) |
| `engine_builder` | +22.5 (0.80) | +6.6 (0.69) | +1.1 (0.52) | — |
| `bonus_card_focus` | +10.4 (0.76) | +5.2 (0.63) | — | −1.1 (0.47) |
| `net_value_response` | +9.5 (0.68) | — | −5.2 (0.37) | −6.6 (0.29) |
| `greedy_immediate` | — | −9.5 (0.31) | −10.4 (0.23) | −22.5 (0.19) |

Champion cell sizes: 1,418 player-games against engine builder and greedy,
1,174 against bonus-card focus, 1,878 against net value.

**The ordering is strict and transitive**: `potential_points` >
`engine_builder` > `bonus_card_focus` > `net_value_response` >
`greedy_immediate`, with no intransitive triple in any of the ten pairs. There
is no rock-paper-scissors among these policies — no archetype beats a stronger
one by exploiting it.

Two readings worth keeping:

- **The champion's edge is roughly constant against everything** (+15.0 to
  +17.6 against the three mid agents), not opponent-specific. That is the same
  story the opponent-model arms tell from the other direction: play quality is
  nearly separable from who you are facing.
- **`engine_builder` vs `bonus_card_focus` is the one near-tie** (+1.1,
  outscored rate 0.52 over 390 player-games). It is the only pair in the matrix
  where the archetypes are genuinely close, and the only one where a
  seed-paired arm might find an interaction worth having.

Self-play cells read margin 0.0 at an outscored rate of 0.485–0.493 rather than
exactly 0.5 purely because ties are excluded from the numerator: the same-agent
tie rate is 2.87%, so a symmetric cell should sit at (1 − 0.0287)/2 = **0.486**,
which is what they do. Nothing about seat advantage is visible here — a
self-play cell aggregates both seats and is symmetric by construction, so the
established 2p first-player advantage of about +6 cancels out. Read seat effects
from `mirror_seat_effect.py`, not from this table.

## What to instrument, in order

1. **A per-turn food snapshot.** One field closes the entire food-economy
   section — six KPIs — and it is the only section that is wholly missing.
2. **A per-round score snapshot** (or persist `round_goal_scored`, now
   emitted). That closes cumulative-score-by-round, per-round delta, relative
   rank by round and rank volatility across four taxonomy sections.
3. **Bonus-card criteria evaluated against the opening hand** at setup, which
   turns the draft-time eligible pool from a gap into a measurement and makes
   the Breeding Manager result above testable.
4. **Persist the arm archives.** The paired 80-game arms are the project's
   real evidence and they are not in the database; the KPI layer can only see
   what was persisted.
