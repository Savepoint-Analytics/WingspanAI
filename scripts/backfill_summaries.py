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

**Do not run this against object storage while a bulk mutation of the same
prefix is in flight.** Paginated listings and concurrent deletes/puts do not
mix: a run overlapping ``scripts/compact_object_storage.py`` on 2026-09-24
saw 5,857 of 10,405 event objects because the page markers shifted underneath
it. The pass is safe to repeat once the mutation has finished.

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


def iter_minio_events(prefix: str | None) -> Iterator[tuple[dict, dict, dict | None]]:
    """Yield a synthesized (manifest, game, game_ended) per archived events object.

    Chunked arms rewrite ``batch_manifest.json`` in a shared batch directory,
    so the surviving manifest lists only the last chunk's games while every
    chunk's event directory persists: 2,433 manifests cover 5,826 of 10,399
    archived games. This mode ignores manifests and reads each events object
    directly — the head for ``game_started`` and the ``setup_selection_applied``
    events that name each seat's agent, the tail for ``game_ended`` — so
    coverage does not depend on which chunk wrote last.
    """

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
    for page in paginator.paginate(Bucket=config.bucket_name, Prefix=base):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key.endswith("events.jsonl"):
                continue
            parts = key[len(config.prefix.rstrip("/")) + 1 :].split("/")
            batch_kind = parts[0] if parts else "experiment"
            batch_label = parts[1] if len(parts) > 1 else "unknown"
            head = client.get_object(Bucket=config.bucket_name, Key=key, Range="bytes=0-65535")[
                "Body"
            ].read()
            start = max(0, item["Size"] - TAIL_BYTES)
            tail = client.get_object(Bucket=config.bucket_name, Key=key, Range=f"bytes={start}-")[
                "Body"
            ].read()
            game_ended = last_json_line(tail.decode("utf-8", "ignore"))
            seats: dict[str, str] = {}
            ruleset = None
            for line in head.decode("utf-8", "ignore").splitlines():
                if '"setup_selection_applied"' not in line and '"game_started"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ruleset = ruleset or event.get("ruleset_id")
                payload = event.get("payload") or {}
                if event.get("event_name") == "setup_selection_applied":
                    seats[str(payload.get("player_id"))] = str(payload.get("agent_id"))
            if game_ended is None:
                # The caller has no ids for these, so they land in its
                # ``skipped_unidentified`` count -- not ``without_scores``,
                # which needs a game the caller could identify. The comment
                # here used to claim otherwise and hid the drop entirely.
                yield {"batch_kind": batch_kind, "batch_label": batch_label}, {}, None
                continue
            # Older games' game_ended payload does not nest an outcome; the
            # event's own envelope carries the ids and seed either way.
            outcome = dict((game_ended.get("payload") or {}).get("outcome") or {})
            outcome.setdefault("game_id", game_ended.get("game_id"))
            outcome.setdefault("simulation_run_id", game_ended.get("simulation_run_id"))
            outcome.setdefault("random_seed", game_ended.get("random_seed"))
            outcome.setdefault("terminal_reason", "game_over")
            if not outcome.get("scores"):
                breakdowns = (game_ended.get("payload") or {}).get("score_breakdowns") or {}
                outcome["scores"] = {
                    player: sum(int(v) for k, v in (b or {}).items() if k in SCORE_CATEGORIES)
                    for player, b in breakdowns.items()
                }
            if not outcome.get("winners") and outcome.get("scores"):
                best = max(outcome["scores"].values())
                outcome["winners"] = [p for p, v in outcome["scores"].items() if v == best]
            manifest = {"batch_kind": batch_kind, "batch_label": batch_label, "batch_id": None}
            game = {
                "outcome": outcome,
                "ruleset_id": ruleset or game_ended.get("ruleset_id"),
                "player_count": len(outcome.get("scores") or {}) or None,
                "seated_agent_ids": [seats[k] for k in sorted(seats)],
            }
            yield manifest, game, game_ended


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", choices=("local", "minio", "minio-events"), default="local")
    parser.add_argument("--root", default="artifacts", help="local artifact root")
    parser.add_argument(
        "--prefix", default=None, help="MinIO sub-prefix under board-games/wingspan"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import psycopg

    load_dotenv()
    if args.source == "local":
        source = iter_local(Path(args.root))
    elif args.source == "minio":
        source = iter_minio(args.prefix)
    else:
        source = iter_minio_events(args.prefix)

    runs: dict[str, tuple] = {}
    games: list[tuple] = []
    scores: list[tuple] = []
    # ADR 0006: dedupe on the run id. ``game_id`` omits the lineup and
    # rotation, so deduping on it silently discarded 44.5% of the archive --
    # 10,831 archived games collapse to 6,014 distinct ``game_id`` values.
    seen_runs: set[str] = set()
    without_scores = 0
    skipped_incomplete = 0
    skipped_unidentified = 0
    duplicate_runs = 0
    candidates = 0
    for manifest, game, game_ended in source:
        candidates += 1
        outcome = game.get("outcome") or {}
        game_id, run_id = outcome.get("game_id"), outcome.get("simulation_run_id")
        if not game_id or not run_id:
            # Chiefly games whose events object has no parseable ``game_ended``;
            # the iterators yield an empty game dict for those.
            skipped_unidentified += 1
            continue
        if run_id in seen_runs:
            duplicate_runs += 1
            continue
        seen_runs.add(run_id)
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
            seen_runs.discard(run_id)
            continue
        games.append(
            (
                run_id,
                game_id,
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
                    run_id,
                    game_id,
                    row["player_id"],
                    row["agent_id"],
                    row["total_score"],
                    *(row[key] for key in SCORE_CATEGORIES),
                    row["is_winner"],
                )
            )

    print(f"source={args.source}: {len(runs)} runs, {len(games)} games, {len(scores)} score rows")
    print(f"  candidates seen: {candidates}")
    if skipped_unidentified:
        print(f"  {skipped_unidentified} skipped: no readable game_id/run_id")
    if duplicate_runs:
        print(f"  {duplicate_runs} skipped: simulation_run_id already seen")
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
                (simulation_run_id, game_id, random_seed, ruleset_id, player_count,
                 terminal_reason, outcome)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (simulation_run_id) DO NOTHING
            """,
            games,
        )
        cursor.executemany(
            f"""
            INSERT INTO game_scores
                (simulation_run_id, game_id, player_id, agent_id, total_score,
                 {", ".join(SCORE_CATEGORIES)}, is_winner)
            VALUES (%s, %s, %s, %s, %s, {", ".join(["%s"] * len(SCORE_CATEGORIES))}, %s)
            ON CONFLICT (simulation_run_id, player_id) DO NOTHING
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
