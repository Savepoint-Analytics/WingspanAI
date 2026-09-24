"""Backfill run, game and score rows from artifacts that were never persisted.

Why
---
``flows/round_robin.py`` defaults to ``persist_postgres=False``, so the paired
arms that carry the project's findings upload to MinIO (ADR 0005) but never
reach PostgreSQL. The result: 4,491 of about 10,400 archived games are
queryable, and the persisted slice is dominated by one forced-play study
rather than the arms. Every score-based KPI in ``wingspan_ai.analysis``
therefore describes the wrong population.

This backfills the three summary tables — ``simulation_runs``, ``games``,
``game_scores`` — for every archived game. It does **not** backfill events:
those stay in object storage, which is the durable copy, and the event table
is loaded selectively for the runs under analysis.

How
---
Run and game rows come from ``batch_manifest.json``, which carries the
ruleset, seed, player count, seat rotation, agent ids and outcome. The six
score categories live only in the ``game_ended`` event, which is the last line
of ``events.jsonl`` — so for object storage this reads the **tail** of each
object with a ranged GET (about 6 KB instead of the whole 8.7 GB archive) and
for local artifacts it reads the last line directly.

Idempotent: existing rows are left alone (``ON CONFLICT DO NOTHING``).

    python scripts/backfill_summaries.py --source local --dry-run
    python scripts/backfill_summaries.py --source local
    python scripts/backfill_summaries.py --source minio
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import (  # noqa: E402
    database_url_from_env,
    load_dotenv,
    object_storage_config_from_env,
)
from wingspan_ai.telemetry.postgres import POSTGRES_SCHEMA  # noqa: E402

#: Bytes read from the end of an events file to recover the game_ended line.
#: A bird_scorecard event runs to ~9 KB and game_ended to ~2 KB, so this is
#: comfortably more than the last line and far less than the whole file.
TAIL_BYTES = 16384
SCORE_CATEGORIES = (
    "bird_points",
    "bonus_points",
    "round_goal_points",
    "egg_points",
    "cached_food_points",
    "tucked_card_points",
)


def last_json_line(text: str) -> dict[str, Any] | None:
    """Parse the last complete JSON object in a chunk of JSONL."""

    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _score_rows(game_ended: dict[str, Any], seated: list[str], winners: list[str]) -> list[dict]:
    breakdowns = game_ended.get("payload", {}).get("score_breakdowns") or {}
    rows = []
    for index, player_id in enumerate(sorted(breakdowns)):
        breakdown = breakdowns[player_id] or {}
        rows.append(
            {
                "player_id": player_id,
                "agent_id": seated[index] if index < len(seated) else "unknown",
                "total_score": sum(int(breakdown.get(key, 0)) for key in SCORE_CATEGORIES),
                "is_winner": player_id in winners,
                **{key: int(breakdown.get(key, 0)) for key in SCORE_CATEGORIES},
            }
        )
    return rows


def iter_local(root: Path) -> Iterator[tuple[dict, dict, dict | None]]:
    """Yield (manifest, game entry, game_ended) for every local archived game."""

    for manifest_path in sorted(root.rglob("batch_manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for game in manifest.get("games", []):
            artifact_dir = game.get("artifact_dir")
            events = Path(artifact_dir) / "events.jsonl" if artifact_dir else None
            game_ended = None
            if events and events.exists():
                with events.open("rb") as handle:
                    handle.seek(0, 2)
                    handle.seek(max(0, handle.tell() - TAIL_BYTES))
                    game_ended = last_json_line(handle.read().decode("utf-8", "ignore"))
            yield manifest, game, game_ended


def iter_minio(prefix: str | None) -> Iterator[tuple[dict, dict, dict | None]]:
    """Same, reading manifests and the tail of each events object from MinIO."""

    import boto3

    config = object_storage_config_from_env()
    if config is None:
        raise ValueError("object storage is not configured")
    client = boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
    )
    base = f"{config.prefix.rstrip('/')}/{(prefix or '').strip('/')}".rstrip("/") + "/"
    paginator = client.get_paginator("list_objects_v2")
    manifests = [
        item["Key"]
        for page in paginator.paginate(Bucket=config.bucket_name, Prefix=base)
        for item in page.get("Contents", [])
        if item["Key"].endswith("batch_manifest.json")
    ]
    for key in manifests:
        body = client.get_object(Bucket=config.bucket_name, Key=key)["Body"].read()
        try:
            manifest = json.loads(body)
        except json.JSONDecodeError:
            continue
        batch_prefix = key.rsplit("/", 1)[0]
        # The layout is <batch>/seed_N/<uuid>/events.jsonl. List the batch once
        # and index its event objects by seed, rather than once per game.
        events_by_seed: dict[str, list[tuple[str, int]]] = {}
        for page in paginator.paginate(Bucket=config.bucket_name, Prefix=f"{batch_prefix}/"):
            for item in page.get("Contents", []):
                if not item["Key"].endswith("events.jsonl"):
                    continue
                parts = item["Key"].split("/")
                seed_part = next((p for p in parts if p.startswith("seed_")), "")
                events_by_seed.setdefault(seed_part, []).append((item["Key"], item["Size"]))
        for game in manifest.get("games", []):
            outcome = game.get("outcome") or {}
            game_id = outcome.get("game_id")
            game_ended = None
            for object_key, size in events_by_seed.get(f"seed_{outcome.get('random_seed')}", []):
                start = max(0, size - TAIL_BYTES)
                tail = client.get_object(
                    Bucket=config.bucket_name, Key=object_key, Range=f"bytes={start}-"
                )["Body"].read()
                candidate = last_json_line(tail.decode("utf-8", "ignore"))
                if candidate and candidate.get("game_id") == game_id:
                    game_ended = candidate
                    break
            yield manifest, game, game_ended


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", choices=("local", "minio"), default="local")
    parser.add_argument("--root", default="artifacts", help="local artifact root")
    parser.add_argument(
        "--prefix", default=None, help="MinIO sub-prefix under board-games/wingspan"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import psycopg

    load_dotenv()
    source = iter_local(Path(args.root)) if args.source == "local" else iter_minio(args.prefix)

    runs: dict[str, tuple] = {}
    games: list[tuple] = []
    scores: list[tuple] = []
    seen_games: set[str] = set()
    without_scores = 0
    skipped_incomplete = 0
    for manifest, game, game_ended in source:
        outcome = game.get("outcome") or {}
        game_id, run_id = outcome.get("game_id"), outcome.get("simulation_run_id")
        if not game_id or not run_id or game_id in seen_games:
            continue
        seen_games.add(game_id)
        run_label = f"{manifest.get('batch_kind')}:{manifest.get('batch_label')}"
        runs.setdefault(
            run_id,
            (
                run_id,
                run_label,
                game.get("ruleset_id"),
                outcome.get("random_seed"),
                json.dumps(
                    {
                        "batch_id": manifest.get("batch_id"),
                        "backfilled_from": args.source,
                        "code_provenance": manifest.get("code_provenance"),
                    }
                ),
            ),
        )
        # Older manifests predate some per-game fields; derive what is missing
        # from the outcome rather than writing a null into a NOT NULL column.
        player_count = game.get("player_count") or len(outcome.get("scores") or {}) or None
        if player_count is None:
            skipped_incomplete += 1
            seen_games.discard(game_id)
            continue
        games.append(
            (
                game_id,
                run_id,
                outcome.get("random_seed"),
                game.get("ruleset_id") or "core_base_game_v1",
                player_count,
                outcome.get("terminal_reason"),
                json.dumps(outcome),
            )
        )
        if game_ended is None:
            without_scores += 1
            continue
        seated = list(game.get("seated_agent_ids") or [])
        for row in _score_rows(game_ended, seated, outcome.get("winners") or []):
            scores.append(
                (
                    game_id,
                    row["player_id"],
                    row["agent_id"],
                    row["total_score"],
                    *(row[key] for key in SCORE_CATEGORIES),
                    row["is_winner"],
                )
            )

    print(f"source={args.source}: {len(runs)} runs, {len(games)} games, {len(scores)} score rows")
    if without_scores:
        print(f"  {without_scores} games had no readable game_ended event (no score rows)")
    if skipped_incomplete:
        print(f"  {skipped_incomplete} games skipped: manifest too old to determine player_count")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    if not games:
        print("nothing to write")
        return 0

    with psycopg.connect(database_url_from_env()) as connection, connection.cursor() as cursor:
        cursor.execute(f'SET search_path TO "{POSTGRES_SCHEMA}"')
        cursor.executemany(
            """
            INSERT INTO simulation_runs
                (simulation_run_id, run_label, ruleset_id, random_seed, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (simulation_run_id) DO NOTHING
            """,
            list(runs.values()),
        )
        cursor.executemany(
            """
            INSERT INTO games
                (game_id, simulation_run_id, random_seed, ruleset_id, player_count,
                 terminal_reason, outcome)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (game_id) DO NOTHING
            """,
            games,
        )
        cursor.executemany(
            f"""
            INSERT INTO game_scores
                (game_id, player_id, agent_id, total_score,
                 {", ".join(SCORE_CATEGORIES)}, is_winner)
            VALUES (%s, %s, %s, %s, {", ".join(["%s"] * len(SCORE_CATEGORIES))}, %s)
            ON CONFLICT (game_id, player_id) DO NOTHING
            """,
            scores,
        )
        connection.commit()
        for table in ("simulation_runs", "games", "game_scores"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table:18s} now {cursor.fetchone()[0]:>9,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
