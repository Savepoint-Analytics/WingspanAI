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
Rebuilds ``games`` and ``game_scores`` with ``simulation_run_id`` as the key,
keeping ``game_id`` as the plain, indexed, batch-scoped label it always was.
Existing rows are **not** migrated: they are the arbitrary ~55% subset that
survived the collision, so they are dropped and reloaded from object storage,
which is the durable log under ADR 0005. Nothing is lost that the archive does
not still hold.

The derived views are dropped so ``analysis/apply_sql_views.py`` rebuilds them
against the new keys.

    python scripts/migrate_game_identity.py --dry-run
    python scripts/migrate_game_identity.py
    python scripts/backfill_summaries.py --source minio-events   # reload
    python analysis/apply_sql_views.py

Expect roughly 10,800 games after the reload rather than ~5,960.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import database_url_from_env, load_dotenv  # noqa: E402
from wingspan_ai.telemetry.postgres import (  # noqa: E402
    POSTGRES_SCHEMA,
    PostgresEventRepository,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--keep-rows",
        action="store_true",
        help=(
            "migrate surviving rows instead of dropping them. Kept for "
            "completeness; the reload is preferred because the survivors are a "
            "biased subset (one lineup/rotation per batch+seed)."
        ),
    )
    args = parser.parse_args(argv)

    load_dotenv()
    database_url = database_url_from_env()
    if not database_url:
        print("no database url configured")
        return 1

    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            select column_name from information_schema.columns
            where table_schema = %s and table_name = 'game_scores'
              and column_name = 'simulation_run_id'
            """,
            (POSTGRES_SCHEMA,),
        )
        if cursor.fetchone() is not None:
            print("already re-keyed: game_scores.simulation_run_id exists")
            return 0

        cursor.execute(f"select count(*) from {POSTGRES_SCHEMA}.games")
        before = cursor.fetchone()[0]
        print(f"games before: {before:,} (the ~55% that survived the collision)")

        statements = [
            f"drop view if exists {POSTGRES_SCHEMA}.v_head_to_head_games cascade",
            f"drop view if exists {POSTGRES_SCHEMA}.v_game_player_scores cascade",
            f"drop table if exists {POSTGRES_SCHEMA}.game_scores",
            f"drop table if exists {POSTGRES_SCHEMA}.games",
        ]
        if args.keep_rows:
            print("--keep-rows is not implemented; the reload is the supported path")
            return 1
        if args.dry_run:
            print("dry run, would run:")
            for statement in statements:
                print(f"  {statement}")
            print("  then ensure_schema() to recreate both tables re-keyed")
            return 0
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
        print("dropped games, game_scores and the two dependent views")

    PostgresEventRepository(database_url).ensure_schema()
    print("recreated games (pk simulation_run_id) and game_scores (pk run_id, player_id)")
    print("next: python scripts/backfill_summaries.py --source minio-events")
    print("      python analysis/apply_sql_views.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
