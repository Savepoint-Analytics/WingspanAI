"""Re-key ``games`` and ``game_scores`` on ``simulation_run_id`` (ADR 0006).

Why
---
``game_id`` is built as ``{batch_id}_seed_{seed}``, which omits the lineup and
the seat rotation. Every game in a batch that shares a seed therefore carries
the same ``game_id`` while being a genuinely different game: different
``simulation_run_id``, different opponents, different scores. Measured over the
archive, 10,831 games collapse to 6,014 distinct ``game_id`` values, so a
``games.game_id`` primary key made **44.5% of the archive unrepresentable**.
That, not any defect in ``backfill_summaries.py``, is why the backfill kept
stalling near 5,960 games.

What it does
------------
Migrates the keys **in place**, deleting nothing:

1. adds ``game_scores.simulation_run_id`` and fills it from ``games`` (a 1:1
   join today, because ``game_id`` is still that table's primary key);
2. drops the two foreign keys that pointed at ``games(game_id)`` -- a
   reference that requires uniqueness ``game_id`` never had;
3. swaps ``games`` onto ``simulation_run_id`` and ``game_scores`` onto
   ``(simulation_run_id, player_id)``;
4. re-adds ``game_scores -> games`` on the new key with ``on delete cascade``,
   and indexes ``games.game_id`` so grouping by batch stays cheap.

The existing rows are kept. They are a biased subset -- the arbitrary ~55% that
survived the collision -- but they are *valid* rows, and a reload inserts the
~4,800 missing games alongside them rather than replacing them. So no row is
deleted at any point, and a re-run of the backfill is additive.

Idempotent: re-running after a successful migration is a no-op.

    python scripts/migrate_game_identity.py --dry-run
    python scripts/migrate_game_identity.py
    python scripts/backfill_summaries.py --source minio-events   # adds the rest
    python analysis/apply_sql_views.py                           # rebuild views

Expect roughly 10,800 games afterwards rather than ~5,960.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import database_url_from_env, load_dotenv  # noqa: E402
from wingspan_ai.telemetry.postgres import POSTGRES_SCHEMA  # noqa: E402

#: Ordered, and every step is additive or a constraint swap. No DROP TABLE, no
#: DELETE: the rows that survived the collision are valid and are kept.
STEPS: tuple[tuple[str, str], ...] = (
    (
        "add game_scores.simulation_run_id",
        "alter table {s}.game_scores add column if not exists simulation_run_id text",
    ),
    (
        "fill it from games (1:1 while game_id is still the games pk)",
        "update {s}.game_scores t set simulation_run_id = g.simulation_run_id "
        "from {s}.games g where g.game_id = t.game_id "
        "and t.simulation_run_id is distinct from g.simulation_run_id",
    ),
    (
        "drop the fk from game_scores to games(game_id)",
        "alter table {s}.game_scores drop constraint if exists game_scores_game_id_fkey",
    ),
    (
        "drop the fk from simulation_events to games(game_id)",
        "alter table {s}.simulation_events drop constraint if exists "
        "simulation_events_game_id_fkey",
    ),
    (
        "swap the games primary key onto simulation_run_id",
        "alter table {s}.games drop constraint if exists games_pkey",
    ),
    (
        "  add it",
        "alter table {s}.games add primary key (simulation_run_id)",
    ),
    (
        "require game_scores.simulation_run_id",
        "alter table {s}.game_scores alter column simulation_run_id set not null",
    ),
    (
        "swap the game_scores primary key onto (simulation_run_id, player_id)",
        "alter table {s}.game_scores drop constraint if exists game_scores_pkey",
    ),
    (
        "  add it",
        "alter table {s}.game_scores add primary key (simulation_run_id, player_id)",
    ),
    (
        "re-add game_scores -> games on the new key",
        "alter table {s}.game_scores add constraint game_scores_simulation_run_id_fkey "
        "foreign key (simulation_run_id) references {s}.games(simulation_run_id) "
        "on delete cascade",
    ),
    (
        "index games.game_id so grouping by batch stays cheap",
        "create index if not exists games_game_id_idx on {s}.games (game_id)",
    ),
    (
        "index simulation_events by run and turn",
        "create index if not exists simulation_events_run_turn_idx "
        "on {s}.simulation_events (simulation_run_id, global_turn_number)",
    ),
)


def already_migrated(cursor) -> bool:
    cursor.execute(
        """
        select 1 from pg_constraint con
        join pg_class rel on rel.oid = con.conrelid
        join pg_namespace n on n.oid = rel.relnamespace
        where n.nspname = %s and rel.relname = 'games' and con.contype = 'p'
          and pg_get_constraintdef(con.oid) = 'PRIMARY KEY (simulation_run_id)'
        """,
        (POSTGRES_SCHEMA,),
    )
    return cursor.fetchone() is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    database_url = database_url_from_env()
    if not database_url:
        print("no database url configured")
        return 1

    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        if already_migrated(cursor):
            print("already migrated: games is keyed on simulation_run_id")
            return 0

        cursor.execute(f"select count(*) from {POSTGRES_SCHEMA}.games")
        games_before = cursor.fetchone()[0]
        cursor.execute(f"select count(*) from {POSTGRES_SCHEMA}.game_scores")
        scores_before = cursor.fetchone()[0]
        print(f"before: {games_before:,} games, {scores_before:,} score rows (all kept)")

        if args.dry_run:
            print("dry run, would run:")
            for label, statement in STEPS:
                print(f"  {label}")
                print(f"      {statement.format(s=POSTGRES_SCHEMA)}")
            return 0

        for label, statement in STEPS:
            cursor.execute(statement.format(s=POSTGRES_SCHEMA))
            print(f"  {label}: {cursor.rowcount if cursor.rowcount >= 0 else 'ok'}")
        connection.commit()

        cursor.execute(f"select count(*) from {POSTGRES_SCHEMA}.games")
        games_after = cursor.fetchone()[0]
        cursor.execute(f"select count(*) from {POSTGRES_SCHEMA}.game_scores")
        scores_after = cursor.fetchone()[0]
        print(f"after:  {games_after:,} games, {scores_after:,} score rows")
        if (games_after, scores_after) != (games_before, scores_before):
            print("WARNING: row counts changed; this migration should not lose rows")
            return 1

    print("\nnext: python scripts/backfill_summaries.py --source minio-events")
    print("      python analysis/apply_sql_views.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
