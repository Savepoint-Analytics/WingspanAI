"""Load Wingspan simulation telemetry from PostgreSQL, MinIO, or local artifacts.

The analysis layer is event-first: the simulator writes raw events and every
KPI is derived from them, so a number in a notebook can always be traced back
to the events that produced it. Three sources return the same record shape:

* **PostgreSQL** (`public.simulation_events` in the Savepoint Lab database) —
  the persisted archive, best for cross-run questions. Note that Wingspan
  writes unqualified tables into ``public`` rather than its own schema, unlike
  the other simulators in the lab.
* **MinIO** (``savepoint-ai/board-games/wingspan/...``) — the immutable
  per-game ``events.jsonl`` artifacts.
* **Local artifacts** (``artifacts/<root>/...``) — the same files before or
  without upload.

Two cheap tabular loaders sit alongside them. ``load_game_scores`` and
``load_games`` read the summary tables directly, which is enough for the
outcome, composition and head-to-head KPIs over the whole archive without
pulling a million events.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from wingspan_ai.config import (
    database_url_from_env,
    load_dotenv,
    object_storage_config_from_env,
)

EventRecord = dict[str, Any]
Row = dict[str, Any]

#: Wingspan telemetry tables are unqualified; the lab's other simulators use a
#: per-game schema. Kept as a constant so a future migration is one edit.
POSTGRES_SCHEMA = "public"


def _connect(database_url: str | None = None):
    import psycopg

    load_dotenv()
    return psycopg.connect(database_url or database_url_from_env())


def _rows(cursor) -> list[Row]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


# --------------------------------------------------------------------- summary


def list_persisted_runs(limit: int = 50, *, database_url: str | None = None) -> list[Row]:
    """Recent runs with their game counts, newest first."""

    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT r.simulation_run_id, r.run_label, r.ruleset_id, r.run_started_at,
                   COUNT(g.game_id) AS games
            FROM {POSTGRES_SCHEMA}.simulation_runs r
            LEFT JOIN {POSTGRES_SCHEMA}.games g USING (simulation_run_id)
            GROUP BY r.simulation_run_id, r.run_label, r.ruleset_id, r.run_started_at
            ORDER BY r.run_started_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return _rows(cursor)


def load_game_scores(
    *,
    run_labels: Sequence[str] | None = None,
    ruleset_id: str | None = None,
    agent_ids: Sequence[str] | None = None,
    limit: int | None = None,
    database_url: str | None = None,
) -> list[Row]:
    """One row per player per game: final score, its six categories, and the win flag.

    This is the cheap path for the outcome, composition and comparative KPI
    families — it reads the summary tables rather than the event log.
    """

    clauses: list[str] = []
    params: list[Any] = []
    if run_labels:
        clauses.append("r.run_label = ANY(%s)")
        params.append(list(run_labels))
    if ruleset_id:
        clauses.append("g.ruleset_id = %s")
        params.append(ruleset_id)
    if agent_ids:
        clauses.append("s.agent_id = ANY(%s)")
        params.append(list(agent_ids))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    suffix = "LIMIT %s" if limit else ""
    if limit:
        params.append(limit)
    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT s.game_id, s.player_id, s.agent_id, s.total_score, s.bird_points,
                   s.bonus_points, s.round_goal_points, s.egg_points,
                   s.cached_food_points, s.tucked_card_points, s.is_winner,
                   g.random_seed, g.player_count, g.ruleset_id, g.simulation_run_id,
                   r.run_label
            FROM {POSTGRES_SCHEMA}.game_scores s
            JOIN {POSTGRES_SCHEMA}.games g USING (game_id)
            JOIN {POSTGRES_SCHEMA}.simulation_runs r USING (simulation_run_id)
            {where}
            ORDER BY s.game_id, s.player_id
            {suffix}
            """,
            params,
        )
        return _rows(cursor)


def load_games(
    *, run_labels: Sequence[str] | None = None, database_url: str | None = None
) -> list[Row]:
    """One row per game: seed, player count, ruleset, terminal reason, outcome."""

    where = "WHERE r.run_label = ANY(%s)" if run_labels else ""
    params = [list(run_labels)] if run_labels else []
    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT g.game_id, g.simulation_run_id, g.random_seed, g.ruleset_id,
                   g.player_count, g.terminal_reason, g.outcome, r.run_label
            FROM {POSTGRES_SCHEMA}.games g
            JOIN {POSTGRES_SCHEMA}.simulation_runs r USING (simulation_run_id)
            {where}
            ORDER BY g.game_id
            """,
            params,
        )
        return _rows(cursor)


# ---------------------------------------------------------------------- events


def load_postgres_event_records(
    *,
    run_label: str | None = None,
    simulation_run_id: str | None = None,
    game_ids: Sequence[str] | None = None,
    event_names: Sequence[str] | None = None,
    limit: int | None = None,
    database_url: str | None = None,
) -> list[EventRecord]:
    """Normalized event records for a run, a game subset, or an event subset.

    ``event_names`` is the lever that keeps this affordable: most KPI families
    need two or three event types, not the whole log (the archive holds over a
    million events, of which 94% are the four per-turn decision events).
    """

    clauses: list[str] = []
    params: list[Any] = []
    if run_label:
        clauses.append("r.run_label = %s")
        params.append(run_label)
    if simulation_run_id:
        clauses.append("e.simulation_run_id = %s")
        params.append(simulation_run_id)
    if game_ids:
        clauses.append("e.game_id = ANY(%s)")
        params.append(list(game_ids))
    if event_names:
        clauses.append("e.event_name = ANY(%s)")
        params.append(list(event_names))
    if not clauses:
        raise ValueError(
            "refusing to load the whole event log; pass run_label, simulation_run_id, "
            "game_ids or event_names"
        )
    suffix = "LIMIT %s" if limit else ""
    if limit:
        params.append(limit)
    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT e.event_name, e.game_id, e.simulation_run_id, e.ruleset_id,
                   e.player_id, e.agent_id, e.round_number, e.turn_number,
                   e.global_turn_number, e.random_seed, e.payload, r.run_label
            FROM {POSTGRES_SCHEMA}.simulation_events e
            JOIN {POSTGRES_SCHEMA}.simulation_runs r USING (simulation_run_id)
            WHERE {" AND ".join(clauses)}
            ORDER BY e.game_id, e.global_turn_number, e.event_id
            {suffix}
            """,
            params,
        )
        return [_normalize(row) for row in _rows(cursor)]


def load_local_event_records(
    paths: str | Path | Iterable[str | Path],
    *,
    event_names: Sequence[str] | None = None,
) -> list[EventRecord]:
    """Read ``events.jsonl`` files from artifact directories or explicit paths."""

    if isinstance(paths, str | Path):
        paths = [paths]
    wanted = set(event_names) if event_names else None
    records: list[EventRecord] = []
    for entry in paths:
        path = Path(entry)
        files = sorted(path.rglob("events.jsonl")) if path.is_dir() else [path]
        for file in files:
            with file.open(encoding="utf-8") as handle:
                for line in handle:
                    if wanted and not any(f'"{name}"' in line for name in wanted):
                        continue
                    event = json.loads(line)
                    if wanted and event.get("event_name") not in wanted:
                        continue
                    records.append(_normalize_artifact(event))
    return records


def load_minio_event_records(
    root: str,
    *,
    event_names: Sequence[str] | None = None,
    max_games: int | None = None,
) -> list[EventRecord]:
    """Read per-game ``events.jsonl`` objects under one artifact root in MinIO.

    ``root`` is the path under the configured prefix, e.g.
    ``"experiment/rr_belief_opp"`` — the same layout the local ``artifacts/``
    tree uses.
    """

    import boto3

    load_dotenv()
    config = object_storage_config_from_env()
    if config is None:
        raise ValueError("object storage is not configured; set the MinIO environment variables")
    client = boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
    )
    prefix = f"{config.prefix.rstrip('/')}/{root.strip('/')}/"
    paginator = client.get_paginator("list_objects_v2")
    keys = [
        item["Key"]
        for page in paginator.paginate(Bucket=config.bucket_name, Prefix=prefix)
        for item in page.get("Contents", [])
        if item["Key"].endswith("events.jsonl")
    ]
    if max_games:
        keys = keys[:max_games]
    wanted = set(event_names) if event_names else None
    records: list[EventRecord] = []
    for key in keys:
        body = client.get_object(Bucket=config.bucket_name, Key=key)["Body"].read()
        for line in body.decode("utf-8").splitlines():
            if not line.strip():
                continue
            if wanted and not any(f'"{name}"' in line for name in wanted):
                continue
            event = json.loads(line)
            if wanted and event.get("event_name") not in wanted:
                continue
            records.append(_normalize_artifact(event))
    return records


def _normalize(row: Row) -> EventRecord:
    payload = row.get("payload")
    return {
        "name": row.get("event_name"),
        "game_id": row.get("game_id"),
        "run_label": row.get("run_label"),
        "simulation_run_id": row.get("simulation_run_id"),
        "ruleset_id": row.get("ruleset_id"),
        "player_id": row.get("player_id"),
        "agent_id": row.get("agent_id"),
        "round_number": row.get("round_number"),
        "turn_number": row.get("turn_number"),
        "global_turn_number": row.get("global_turn_number"),
        "seed": row.get("random_seed"),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _normalize_artifact(event: Row) -> EventRecord:
    return {
        "name": event.get("event_name"),
        "game_id": event.get("game_id"),
        "run_label": None,
        "simulation_run_id": event.get("simulation_run_id"),
        "ruleset_id": event.get("ruleset_id"),
        "player_id": event.get("player_id"),
        "agent_id": event.get("agent_id"),
        "round_number": event.get("round_number"),
        "turn_number": event.get("turn_number"),
        "global_turn_number": event.get("global_turn_number"),
        "seed": event.get("random_seed"),
        "payload": event.get("payload") if isinstance(event.get("payload"), dict) else {},
    }
