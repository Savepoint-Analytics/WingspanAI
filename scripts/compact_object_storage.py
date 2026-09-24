"""Compact the bulky per-game artifacts in object storage.

Why
---
``public_state_snapshots.json`` is 12.0 GB of the 21.1 GB Wingspan bucket —
57% — and nothing reads it: every analysis replays from ``events.jsonl`` and
replay validation reconstructs state from the same place
(``analysis/compact_artifacts.py`` makes the same point about the local
cache). ``replay_debug.json`` is smaller but equally unread.

This gzips those objects in place: download, compress, upload as
``*.json.gz``, delete the original. JSON of this shape compresses about
tenfold, so the bucket should fall to roughly 10 GB without losing anything.

Reversible with ``--restore``. Use ``--delete`` instead of gzip only if you
have decided the snapshots are not worth keeping at all — that is not
reversible, so it is never the default.

    python scripts/compact_object_storage.py --dry-run
    python scripts/compact_object_storage.py --prefix experiment/rr_belief_opp
    python scripts/compact_object_storage.py
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.config import load_dotenv, object_storage_config_from_env  # noqa: E402

#: Objects that are safe to compact: read by nothing, reconstructible from
#: ``events.jsonl``. ``events.jsonl``, ``outcome.json`` and the manifests are
#: never touched.
BULKY = ("public_state_snapshots.json", "replay_debug.json")


def _client(config):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prefix", default=None, help="sub-prefix under board-games/wingspan")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--restore", action="store_true", help="gunzip previously compacted objects"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="delete instead of compressing; not reversible",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    config = object_storage_config_from_env()
    if config is None:
        print("object storage is not configured")
        return 1
    client = _client(config)
    base = f"{config.prefix.rstrip('/')}/{(args.prefix or '').strip('/')}".rstrip("/") + "/"

    suffixes = tuple(f"{name}.gz" for name in BULKY) if args.restore else BULKY
    paginator = client.get_paginator("list_objects_v2")
    targets = [
        (item["Key"], item["Size"])
        for page in paginator.paginate(Bucket=config.bucket_name, Prefix=base)
        for item in page.get("Contents", [])
        if item["Key"].endswith(suffixes)
    ]
    if args.limit:
        targets = targets[: args.limit]
    total = sum(size for _key, size in targets)
    verb = "restore" if args.restore else ("delete" if args.delete else "compact")
    print(f"{verb}: {len(targets):,} objects, {total / 1e9:.2f} GB under {base}")
    if args.dry_run or not targets:
        print("dry run: nothing changed" if args.dry_run else "nothing to do")
        return 0

    done = saved = 0
    for key, size in targets:
        body = client.get_object(Bucket=config.bucket_name, Key=key)["Body"].read()
        if args.delete:
            client.delete_object(Bucket=config.bucket_name, Key=key)
            saved += size
        elif args.restore:
            payload = gzip.decompress(body)
            client.put_object(Bucket=config.bucket_name, Key=key.removesuffix(".gz"), Body=payload)
            client.delete_object(Bucket=config.bucket_name, Key=key)
        else:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=6) as handle:
                handle.write(body)
            payload = buffer.getvalue()
            client.put_object(Bucket=config.bucket_name, Key=f"{key}.gz", Body=payload)
            client.delete_object(Bucket=config.bucket_name, Key=key)
            saved += size - len(payload)
        done += 1
        if done % 250 == 0:
            print(f"  {done:,}/{len(targets):,} objects, {saved / 1e9:.2f} GB saved", flush=True)
    print(f"done: {done:,} objects, {saved / 1e9:.2f} GB saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
