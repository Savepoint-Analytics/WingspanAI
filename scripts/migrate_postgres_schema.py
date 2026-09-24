"""Move Wingspan telemetry from the shared ``public`` schema into ``wingspan_ai``.

Why
---
Wingspan wrote unqualified tables into ``public``, sharing the namespace with
MLflow's own tables (``runs``, ``metrics``, ``experiments``…) and with any
other simulator in the lab that persists a ``simulation_events``. The lab's
other two simulators are namespaced (``game_of_thrones_ai``, ``irish_gauge``);
this brings Wingspan in line.

What it does
------------
Creates the schema, moves the five telemetry tables into it with
``ALTER TABLE ... SET SCHEMA`` (indexes and constraints follow the table), and
drops the derived view layer so ``analysis/apply_sql_views.py`` can rebuild it
in the new schema. No row is copied or rewritten, so the move is fast and the
data is never duplicated.

Idempotent: tables already in the target schema are skipped. Reversible with
``--to public``.

    python scripts/migrate_postgres_schema.py --dry-run
    python scripts/migrate_postgres_schema.py
    python analysis/apply_sql_views.py          # rebuild the views in the new schema
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import database_url_from_env, load_dotenv  # noqa: E402
from wingspan_ai.telemetry.postgres import POSTGRES_SCHEMA, TELEMETRY_TABLES  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--to", default=POSTGRES_SCHEMA, help="target schema")
    parser.add_argument("--from", dest="source", default="public", help="source schema")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import psycopg

    load_dotenv()
    with psycopg.connect(database_url_from_env()) as connection, connection.cursor() as cursor:
        # These table names are not unique across the lab: game_of_thrones_ai and
        # irish_gauge also hold a simulation_events. Always filter by schema.
        def tables_in(schema: str) -> set[str]:
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s AND table_name = ANY(%s) AND table_type = 'BASE TABLE'
                """,
                (schema, list(TELEMETRY_TABLES)),
            )
            return {row[0] for row in cursor.fetchall()}

        in_source, in_target = tables_in(args.source), tables_in(args.to)
        to_move = [table for table in TELEMETRY_TABLES if table in in_source]
        already = [table for table in TELEMETRY_TABLES if table in in_target]
        missing = [table for table in TELEMETRY_TABLES if table not in in_source | in_target]

        print(f"target schema: {args.to}")
        print(f"  to move from {args.source}: {to_move or 'none'}")
        print(f"  already in {args.to}: {already or 'none'}")
        if missing:
            print(f"  not found (will be created on first write): {missing}")

        cursor.execute(
            "SELECT table_name FROM information_schema.views WHERE table_schema = %s "
            "AND table_name LIKE 'v\\_%%' ORDER BY table_name",
            (args.source,),
        )
        views = [row[0] for row in cursor.fetchall()]
        print(f"  derived views to drop from {args.source}: {len(views)}")

        if args.dry_run:
            print("\ndry run: nothing changed")
            return 0
        if not to_move and not views:
            print("\nnothing to do")
            return 0

        # Views are fully derived from the tables; dropping them first keeps the
        # table move from failing on dependencies.
        for view in views:
            cursor.execute(f'DROP VIEW IF EXISTS {args.source}."{view}" CASCADE')
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{args.to}"')
        for table in to_move:
            cursor.execute(f'ALTER TABLE {args.source}."{table}" SET SCHEMA "{args.to}"')
            print(f"  moved {table}")
        connection.commit()

        cursor.execute(
            """
            SELECT table_name, (SELECT COUNT(*) FROM information_schema.columns c
                                WHERE c.table_schema = t.table_schema
                                  AND c.table_name = t.table_name) AS columns
            FROM information_schema.tables t
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (args.to,),
        )
        print(f"\n{args.to} now holds:")
        for name, columns in cursor.fetchall():
            cursor.execute(f'SELECT COUNT(*) FROM "{args.to}"."{name}"')
            print(f"  {name:20s} {cursor.fetchone()[0]:>9,} rows, {columns} columns")
    print("\nnext: python analysis/apply_sql_views.py   # rebuild the view layer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
