"""Mirror the local `artifacts/` tree into S3-compatible object storage.

Why this exists
---------------
Simulation artifacts accumulated on local disk only: `flows/round_robin.py`
hardcoded `upload_artifacts=False`, overriding the auto-detect in
`flows/simulation_batch.py`, so every round-robin run opted out of upload. The
bucket held nothing but smoke tests while 1.7 GB sat on one laptop with no
durable copy, including runs whose generating code was never committed and is
therefore unreproducible.

The flow default is fixed; this backfills what was already written.

Idempotent: an object whose key and size already match is skipped, so a run
interrupted partway can simply be repeated.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from wingspan_ai.config import ObjectStorageConfig, load_dotenv, object_storage_config_from_env
from wingspan_ai.storage.object_storage import _import_boto3, _make_client


def existing_object_sizes(client, bucket: str, prefix: str) -> dict[str, int]:
    """Return {key: size} for everything already stored under `prefix`."""

    sizes: dict[str, int] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            sizes[obj["Key"]] = obj["Size"]
    return sizes


def backfill(
    root: Path,
    config: ObjectStorageConfig,
    *,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Mirror `root` under the configured prefix. Returns (uploaded, skipped, bytes)."""

    client = _make_client(_import_boto3(), config)
    prefix = config.prefix.strip("/")
    remote = existing_object_sizes(client, config.bucket_name, prefix)

    uploaded = skipped = sent_bytes = 0
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for index, path in enumerate(files, start=1):
        relative = path.relative_to(root).as_posix()
        key = f"{prefix}/{relative}" if prefix else relative
        size = path.stat().st_size
        if remote.get(key) == size:
            skipped += 1
            continue
        if not dry_run:
            client.upload_file(str(path), config.bucket_name, key)
        uploaded += 1
        sent_bytes += size
        if index % 250 == 0:
            print(f"  {index}/{len(files)} scanned, {uploaded} uploaded", flush=True)
    return uploaded, skipped, sent_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    config = object_storage_config_from_env()
    if config is None:
        print("object storage is not configured; set the MinIO variables in .env")
        return 1
    if not args.root.is_dir():
        print(f"artifact root does not exist: {args.root}")
        return 1

    print(f"mirroring {args.root} -> s3://{config.bucket_name}/{config.prefix}")
    started = time.perf_counter()
    uploaded, skipped, sent_bytes = backfill(args.root, config, dry_run=args.dry_run)
    elapsed = time.perf_counter() - started
    verb = "would upload" if args.dry_run else "uploaded"
    print(
        f"{verb} {uploaded} objects ({sent_bytes / 1048576:.1f} MB), "
        f"skipped {skipped} already present, in {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
