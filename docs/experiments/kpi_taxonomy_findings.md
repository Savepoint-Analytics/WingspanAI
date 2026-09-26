# Wingspan KPI taxonomy: what the persisted archive can answer

> **Every per-agent and per-matchup number below is suspect as of 2026-09-25.**
> `game_id` turned out not to be unique (ADR 0006): it omits the lineup and
> rotation, so 44.5% of archived games could not be represented under a
> `games.game_id` primary key. The 4,491 games this pass read are an arbitrary
> ~55% subset - arbitrary because which colliding game survived depended on
> object listing order - and the survivors are biased, keeping one
> lineup/rotation per (batch, seed) and discarding the rest.
>
> What survives the finding: the coverage and taxonomy mapping (which KPIs the
> archive can answer at all, and from which table), and anything read per event
> rather than per game. What does not: every win rate, per-agent mean, and
> matchup split. Re-run after the schema migration and reload; expect ~10,800
> games.
>
> Arm results in `results_ledger.md` are **not** affected - those read local
> artifacts and never touch this database.


Run 2026-09-22 against the Savepoint Lab PostgreSQL (`public.*`, 4,491 games /
8,982 player-games / 1,215,761 events) with
`notebooks/wingspan_kpi_walkthrough.ipynb` and the functions in
`wingspan_ai.analysis`.

## Where the data is

| | Wingspan | GoT | Irish Gauge |
|---|---|---|---|
| PostgreSQL schema | **`public`** (unqualified) | `game_of_thrones_ai` | `irish_gauge` |
| dbt project | **none** | `analytics.*`, 16 models | none |
| MinIO | `savepoint-ai/board-games/wingspan/` | same bucket | same bucket |

Two things worth deciding: Wingspan's tables share `public` with MLflow's
(`runs`, `metrics`, `experiments`…) and with any other simulator that writes
an unqualified `simulation_events`; and the hand-rolled 16-view layer in
`analysis/sql/analysis_views.sql` does the job a dbt project does for GoT.

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

**The persisted archive is not the research archive.** 78 run labels, but
2,880 of 4,491 games are the forced-play study (`fp_v2_*`) of engine builder
vs greedy, and only 463 player-games are the champion. The paired 80-game
arms that carry the project's findings live in local `artifacts/` and MinIO,
largely unpersisted to PostgreSQL. Any cross-agent number below is a
population statistic of *what was persisted*, not a controlled contrast — for
those, pair by seed with `analysis/arm_contrast.py`.

### Score composition, all 8,982 player-games

| category | avg | share | % of players scoring | max |
|---|---:|---:|---:|---:|
| bird | 25.23 | 44.4% | 99.8% | 74 |
| round goals | 12.22 | 21.5% | 98.1% | 22 |
| eggs | 8.47 | 14.9% | 90.7% | 34 |
| tucked cards | 4.93 | 8.7% | 68.7% | 44 |
| cached food | 3.45 | 6.1% | 49.3% | 34 |
| bonus cards | 2.54 | 4.5% | **50.5%** | 27 |

**Half of all player-games score zero bonus points.** Against the measured
finding that the bonus-card *choice* is worth 6.4 points, that is a large
pool of unrealised value — and it is concentrated in the weak agents
(champion 7.1 bonus points, greedy 1.3).

### By agent

| agent | player-games | win | score | bird | bonus | goals | eggs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `potential_points` | 463 | 0.952 | 88.3 | 39.9 | 7.1 | 16.3 | 15.4 |
| `engine_builder` | 4,244 | 0.794 | 66.6 | 33.5 | 3.3 | 12.7 | 7.1 |
| `greedy_immediate` | 4,269 | 0.170 | 43.7 | 15.4 | 1.3 | 11.3 | 9.1 |

Round goals are the **flattest** category across agents: greedy scores 89% of
what the champion scores on bird points' 39%. As a share of its own score,
greedy gets 25.8% from goals against the champion's 18.4% — the goal is the
category a weak agent can still reach, because qualifying takes one bird.

### Utilization, `fp_v2_P3_AcBc` (480 player-games, both agents)

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

### Bonus-card fulfilment by card

Of the birds a player actually played, the share tagged for the bonus card
they kept:

| card | games | matching birds | fulfilment |
|---|---:|---:|---:|
| Wildlife Gardener | 22 | 3.50 | 0.542 |
| Large Bird Specialist | 29 | 3.55 | 0.462 |
| Enclosure Builder | 25 | 3.16 | 0.430 |
| Bird Feeder | 23 | 3.43 | 0.428 |
| Bird Counter | 26 | 1.58 | 0.265 |
| Prairie Manager | 22 | 1.68 | 0.243 |
| Cartographer | 22 | 1.45 | 0.231 |
| **Breeding Manager** | 25 | **0.24** | **0.031** |

A tenfold spread in how often a kept card matches what gets played, on one
study's decks. Breeding Manager is close to dead on arrival — it matched 0.24
birds a game. That is a card-choice signal worth a proper paired study rather
than a claim; the existing `bonus_card_keep_contrast.py` instrument is the way
to test it.

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
