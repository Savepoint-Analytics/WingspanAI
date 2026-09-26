# ADR 0006 - The run id, not the game id, is a game's identity in the database

_Status: accepted, 2026-09-25. Supersedes nothing; extends ADR 0003 and ADR 0005._

## Context

The backfill of archived games into PostgreSQL kept stalling around 5,960
games while reporting ~10,650 candidates seen. Two earlier fixes (an event
envelope fallback for old `game_ended` payloads, and a pagination/compaction
race) each recovered only a few dozen games, so the ~4,700 gap was assumed to
be a bug in `backfill_summaries.py`.

It is not a bug in the backfill. **`game_id` is not unique.**

`flows/simulation_batch.py` builds it as:

    game_id = f"{resolved_batch_id}_seed_{random_seed}"

which omits the batch label - the component that names the lineup and the
seat rotation. Every game in a batch that shares a batch id and a seed but
faces a different opponent, or sits in a different rotation, gets the same
`game_id`. Those are genuinely different games: different
`simulation_run_id`, different opponents, different scores.

Measured over the whole archive by deriving the id from each object key:

| | count |
|---|---:|
| archived `events.jsonl` objects | 10,831 |
| unique `game_id` values | 6,014 |
| **games erased by collision** | **4,817 (44.5%)** |

Copies per `game_id` run from 1 to 20 (4,499 ids appear once; 149 ids appear
twenty times). The unique count of 6,014 matches the ~5,963 rows the backfill
loaded, which closes the question: nothing was dropped by a code defect, the
rows were unrepresentable because `games.game_id` is the primary key.

## What is and is not affected

**Not affected: every arm result in `results_ledger.md`.** `analysis/arm_contrast.py`
reads local artifact directories and keys games on
`(lineup, rotation, seed, ruleset_id)`. It never reads `game_id` and never
touches PostgreSQL. The same is true of `decision_profile_report.py` and the
other `analysis/` readers. The 25-deck placement confirmation, the mirror
studies, the seat effects and the opponent-model arms all stand.

**Affected: anything read out of PostgreSQL**, which today means the KPI pass
in `kpi_taxonomy_findings.md`. Those KPIs were computed over an arbitrary 55%
of the archive - arbitrary because which colliding game survived depends on
object listing order - and the survivors are biased: for a given batch and
seed, one lineup/rotation is kept and the rest are discarded. Per-agent and
per-matchup KPIs are therefore not trustworthy and are marked as such until
the reload lands.

## Decision

**A game's identity in the analysis database is `simulation_run_id`.**

- `games` is keyed on `simulation_run_id` (already unique, already carried on
  every event, one per game).
- `game_id` is retained as a plain, indexed, non-unique column. It is a
  batch-scoped label, which is what it has always actually been.
- `game_scores` is keyed on `(simulation_run_id, player_id)`.
- Joins from `simulation_events` go through `simulation_run_id`.

**`game_id` generation is left alone.** Under ADR 0003, `random_seed` is the
sole reproducibility key and `game_id` is a storage key only - it was
deliberately removed from RNG seeding because including it made batches with
equal seeds diverge. Changing it now would be safe for determinism
(`base_game_bit_identity.py` hashes `action_resolved` labels only, not ids)
but it would buy nothing: the database no longer depends on it being unique,
and leaving it stable keeps every archived object's internal ids consistent
with its key.

## Alternatives considered

- **Make `game_id` unique by adding the batch label.** Fixes new games only.
  The 4,817 already-archived games would still need ids re-derived from their
  object keys, and those re-derived ids would then disagree with the `game_id`
  recorded inside the events themselves, breaking event joins. Rejected: more
  work, and it corrupts the archive's internal consistency to fix a key the
  database should not have been using.
- **Composite key `(game_id, simulation_run_id)`.** Works, but carries a
  redundant column in the key forever and invites joins on the wrong half.
- **Treat `game_id` as a deck key.** Tempting, and it is nearly that. But the
  deck depends only on `(random_seed, ruleset_id)` under ADR 0003, not on the
  batch, so `random_seed` is already the correct clustering unit and the one
  the 2026-09-25 audit uses. No new column needed.

## Revisit if

- A second simulator or an external producer writes into this schema without
  a `simulation_run_id`.
- Games ever become many-per-run (a run that replays or forks a game), at
  which point run id stops being 1:1 with a game and needs its own surrogate.

## Consequences

- A schema migration and a full reload; `scripts/migrate_postgres_schema.py`
  and `scripts/backfill_summaries.py` both change.
- The backfill must dedupe on `simulation_run_id`, not `game_id`.
- Expected row count after reload: ~10,800 games rather than ~5,960.
- Phase 5 (dbt) stays gated until the reload shows ~10,800 games, since every
  model would otherwise be built on the biased half.
- A separate defect found while reading the backfill: when an events object
  has no parseable `game_ended`, `iter_minio_events` yields an empty game
  dict whose comment claims the caller's `without_scores` counter surfaces it.
  It does not - the caller drops it at the id check first, so those games are
  invisible in the run report. Fix alongside the reload.
