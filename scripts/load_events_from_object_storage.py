"""Load archived ``events.jsonl`` into ``wingspan_ai.simulation_events``.

Why
---
``backfill_summaries.py`` loads runs, games and scores from object storage but
not events, so after the ADR 0006 reload ``simulation_events`` covered 4,491 of
10,956 games -- and lopsidedly, because the covered games are whatever happened
to be live-persisted: 99.9% of ``greedy_immediate_p2`` seats, 93% of
``engine_builder_p1``, 10.7% of the champion, and 0% of every other seat. Every
event-derived KPI therefore described one forced-play study rather than the
archive.

How
---
Streams each archived events object, keeps the families the view layer and the
KPI functions actually read (``ANALYSIS_EVENT_NAMES``), and bulk-loads them with
``COPY``. ``executemany`` over ~3M rows is far too slow; ``COPY`` from an
in-memory text buffer is the whole difference between minutes and hours.

Rows are written to a staging table and merged with ``on conflict do nothing``
on ``event_id``, so the load is **idempotent and additive**: re-running it, or
running it while some games are already present, inserts only what is missing
and deletes nothing.

    python scripts/load_events_from_object_storage.py --dry-run
    python scripts/load_events_from_object_storage.py --limit 50
    python scripts/load_events_from_object_storage.py
    python scripts/load_events_from_object_storage.py --prefix experiment/rr3p_oracle15

Roughly 10,900 objects and ~3M retained rows; expect a long unattended run.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import (  # noqa: E402
    database_url_from_env,
    load_dotenv,
    object_storage_config_from_env,
)
from wingspan_ai.telemetry.postgres import (  # noqa: E402
    ANALYSIS_EVENT_NAMES,
    POSTGRES_SCHEMA,
)

#: Column order for the COPY. Must match the insert below and the live table.
COLUMNS = (
    "event_id",
    "event_name",
    "event_version",
    "occurred_at",
    "simulation_run_id",
    "game_id",
    "ruleset_id",
    "player_id",
    "agent_id",
    "round_number",
    "turn_number",
    "round_action_number",
    "global_turn_number",
    "random_seed",
    "public_state_ref",
    "private_state_included",
    "payload",
)

STAGING = "simulation_events_staging"


def object_client(config):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
    )


def event_rows(body: bytes, keep: set[str]) -> list[tuple[Any, ...]]:
    """Retained rows from one ``events.jsonl`` body, in ``COLUMNS`` order."""

    rows: list[tuple[Any, ...]] = []
    for line in body.decode("utf-8", "ignore").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        # Cheap pre-filter: skip the ~80% of lines we do not keep without
        # paying json.loads on them. action_selected/turn_started and friends
        # dominate the file.
        if not any(f'"{name}"' in line for name in keep):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = event.get("event_name")
        if name not in keep:
            continue
        event_id = event.get("event_id")
        run_id = event.get("simulation_run_id")
        if not event_id or not run_id:
            continue
        rows.append(
            (
                event_id,
                name,
                event.get("event_version") or "1",
                event.get("occurred_at"),
                run_id,
                event.get("game_id"),
                event.get("ruleset_id"),
                event.get("player_id"),
                event.get("agent_id"),
                event.get("round_number"),
                event.get("turn_number"),
                event.get("round_action_number"),
                event.get("global_turn_number"),
                event.get("random_seed"),
                event.get("public_state_ref"),
                bool(event.get("private_state_included") or False),
                json.dumps(event.get("payload") or {}),
            )
        )
    return rows


def copy_rows(cursor, rows: list[tuple[Any, ...]]) -> None:
    columns = ", ".join(COLUMNS)
    with cursor.copy(f"copy {POSTGRES_SCHEMA}.{STAGING} ({columns}) from stdin") as copy:
        for row in rows:
            copy.write_row(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prefix", default=None, help="sub-prefix under board-games/wingspan")
    parser.add_argument("--limit", type=int, default=None, help="only this many objects")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--batch-objects",
        type=int,
        default=200,
        help="flush to postgres every N objects",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    database_url = database_url_from_env()
    storage = object_storage_config_from_env()
    if not database_url or storage is None:
        print("need both a database url and object storage configured")
        return 1

    keep = set(ANALYSIS_EVENT_NAMES)
    client = object_client(storage)
    base = f"{storage.prefix.rstrip('/')}/{(args.prefix or '').strip('/')}".rstrip("/") + "/"
    paginator = client.get_paginator("list_objects_v2")
    keys = [
        item["Key"]
        for page in paginator.paginate(Bucket=storage.bucket_name, Prefix=base)
        for item in page.get("Contents", [])
        if item["Key"].endswith(("events.jsonl", "events.jsonl.gz"))
    ]
    if args.limit:
        keys = keys[: args.limit]
    print(f"{len(keys):,} event objects under {base}")
    print(f"keeping {len(keep)} event families: {', '.join(sorted(keep))}")
    if args.dry_run or not keys:
        print("dry run: nothing written" if args.dry_run else "nothing to do")
        return 0

    import psycopg

    inserted = read = 0
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                create unlogged table if not exists {POSTGRES_SCHEMA}.{STAGING}
                (like {POSTGRES_SCHEMA}.simulation_events including defaults)
                """
            )
            cursor.execute(f"truncate {POSTGRES_SCHEMA}.{STAGING}")
        connection.commit()

        pending: list[tuple[Any, ...]] = []

        def flush() -> int:
            nonlocal pending
            if not pending:
                return 0
            with connection.cursor() as cursor:
                copy_rows(cursor, pending)
                columns = ", ".join(COLUMNS)
                cursor.execute(
                    f"""
                    insert into {POSTGRES_SCHEMA}.simulation_events ({columns})
                    select {columns} from {POSTGRES_SCHEMA}.{STAGING}
                    on conflict (event_id) do nothing
                    """
                )
                written = cursor.rowcount
                cursor.execute(f"truncate {POSTGRES_SCHEMA}.{STAGING}")
            connection.commit()
            pending = []
            return max(written, 0)

        for index, key in enumerate(keys, start=1):
            try:
                body = client.get_object(Bucket=storage.bucket_name, Key=key)["Body"].read()
                if key.endswith(".gz"):
                    body = gzip.decompress(body)
                rows = event_rows(body, keep)
            except Exception as error:  # one bad object must not end the load
                print(f"  skipped {key}: {type(error).__name__}: {error}", flush=True)
                continue
            read += len(rows)
            pending.extend(rows)
            if index % args.batch_objects == 0:
                inserted += flush()
                print(
                    f"  {index:,}/{len(keys):,} objects, {read:,} rows read, "
                    f"{inserted:,} inserted",
                    flush=True,
                )
        inserted += flush()

        with connection.cursor() as cursor:
            cursor.execute(f"drop table if exists {POSTGRES_SCHEMA}.{STAGING}")
        connection.commit()

    print(f"done: {len(keys):,} objects, {read:,} rows read, {inserted:,} newly inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
