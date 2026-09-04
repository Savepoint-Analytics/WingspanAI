"""Apply and inspect the analysis view layer in PostgreSQL.

The raw telemetry tables stay append-only. Every derived metric definition lives
in `analysis/sql/analysis_views.sql` so a metric has exactly one definition that
Python, R, and SQL callers all share.

Usage:
    python analysis/apply_sql_views.py                 # create/replace views
    python analysis/apply_sql_views.py --list          # list view names in the file
    python analysis/apply_sql_views.py --check         # verify each view is queryable
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import database_url_from_env, load_dotenv  # noqa: E402

DEFAULT_SQL_PATH = Path(__file__).resolve().parent / "sql" / "analysis_views.sql"
VIEW_NAME_PATTERN = re.compile(
    r"create\s+or\s+replace\s+view\s+([a-z0-9_]+)\s+as",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ViewStatement:
    """One `create or replace view` statement parsed from the SQL file."""

    view_name: str
    statement: str


def parse_view_statements(sql_text: str) -> list[ViewStatement]:
    """Split the SQL file into individual view statements, preserving order.

    Statements are separated on semicolons at end of line, which is sufficient
    for this file and avoids taking a SQL-parser dependency.
    """

    statements: list[ViewStatement] = []
    for raw_statement in sql_text.split(";\n"):
        statement = raw_statement.strip()
        if not statement:
            continue
        match = VIEW_NAME_PATTERN.search(statement)
        if match is None:
            continue
        statements.append(ViewStatement(view_name=match.group(1), statement=statement))
    return statements


def load_view_statements(sql_path: Path = DEFAULT_SQL_PATH) -> list[ViewStatement]:
    """Read and parse the analysis view definitions."""

    return parse_view_statements(sql_path.read_text(encoding="utf-8"))


def apply_views(database_url: str, sql_path: Path = DEFAULT_SQL_PATH) -> list[str]:
    """Create or replace every analysis view. Returns the applied view names."""

    import psycopg

    statements = load_view_statements(sql_path)
    applied: list[str] = []
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for view in statements:
                cursor.execute(view.statement)
                applied.append(view.view_name)
        connection.commit()
    return applied


def check_views(database_url: str, sql_path: Path = DEFAULT_SQL_PATH) -> dict[str, str]:
    """Run a zero-row probe against every view and report per-view status."""

    import psycopg

    results: dict[str, str] = {}
    with psycopg.connect(database_url) as connection:
        for view in load_view_statements(sql_path):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"select * from {view.view_name} limit 0")
                results[view.view_name] = "ok"
            except Exception as error:  # noqa: BLE001 - surfaced verbatim to the caller
                connection.rollback()
                results[view.view_name] = f"{type(error).__name__}: {error}"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql-path", type=Path, default=DEFAULT_SQL_PATH)
    parser.add_argument("--list", action="store_true", help="list parsed view names and exit")
    parser.add_argument("--check", action="store_true", help="probe each view for queryability")
    args = parser.parse_args()

    if args.list:
        for view in load_view_statements(args.sql_path):
            print(view.view_name)
        return 0

    load_dotenv()
    database_url = database_url_from_env()
    if not database_url:
        print(
            "No database URL configured. Set SAVEPOINT_PG_* variables in .env "
            "before applying analysis views.",
            file=sys.stderr,
        )
        return 1

    if args.check:
        failures = 0
        for view_name, status in check_views(database_url, args.sql_path).items():
            print(f"{view_name}: {status}")
            failures += status != "ok"
        return 1 if failures else 0

    applied = apply_views(database_url, args.sql_path)
    print(f"Applied {len(applied)} analysis views:")
    for view_name in applied:
        print(f"  {view_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
