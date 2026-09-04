"""Delete local artifacts that are already durable in object storage.

Why this is safe to run and why it verifies first
-------------------------------------------------
`artifacts/` is gitignored, so a local delete is unrecoverable. It is a working
cache only because object storage holds the durable copy (ADR 0005) — which was
not true until 2026-09-03, when a 1.7 GB tree turned out to exist nowhere else.

This therefore refuses to delete anything it has not first matched, by key and
byte size, against the bucket. If a single file under a directory is missing or
differs, that whole directory is left alone. Fail closed: the cost of keeping
too much is disk, the cost of deleting too much is unrecoverable data.

In-progress runs must be excluded. A batch uploads when it completes, so a
directory being written right now is legitimately absent from the bucket.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from wingspan_ai.config import ObjectStorageConfig, load_dotenv, object_storage_config_from_env
from wingspan_ai.storage.object_storage import _import_boto3, _make_client


def remote_sizes(client, bucket: str, prefix: str) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            sizes[obj["Key"]] = obj["Size"]
    return sizes


def verify_directory(
    directory: Path,
    root: Path,
    remote: dict[str, int],
    prefix: str,
) -> tuple[bool, int, int, list[str]]:
    """Return (fully_mirrored, file_count, bytes, up-to-five example mismatches)."""

    mismatches: list[str] = []
    count = 0
    total = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        size = path.stat().st_size
        total += size
        relative = path.relative_to(root).as_posix()
        key = f"{prefix}/{relative}" if prefix else relative
        if remote.get(key) != size:
            if len(mismatches) < 5:
                mismatches.append(relative)
    return not mismatches, count, total, mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="top-level directory name to leave alone; repeatable. Use for in-progress runs.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually delete. Without this the script only reports.",
    )
    args = parser.parse_args()

    load_dotenv()
    config: ObjectStorageConfig | None = object_storage_config_from_env()
    if config is None:
        print("object storage is not configured; refusing to prune")
        return 1
    if not args.root.is_dir():
        print(f"artifact root does not exist: {args.root}")
        return 1

    prefix = config.prefix.strip("/")
    client = _make_client(_import_boto3(), config)
    remote = remote_sizes(client, config.bucket_name, prefix)
    print(f"bucket holds {len(remote)} objects under {prefix}\n")

    excluded = set(args.exclude)
    prunable: list[tuple[Path, int, int]] = []
    kept_bytes = 0
    for directory in sorted(p for p in args.root.iterdir() if p.is_dir()):
        if directory.name in excluded:
            print(f"  SKIP     {directory.name} (excluded: in progress)")
            continue
        mirrored, count, total, mismatches = verify_directory(directory, args.root, remote, prefix)
        if mirrored:
            print(f"  VERIFIED {directory.name}: {count} files, {total / 1048576:.0f} MB")
            prunable.append((directory, count, total))
        else:
            kept_bytes += total
            print(f"  KEEP     {directory.name}: not fully mirrored, e.g. {mismatches[0]}")

    reclaimable = sum(total for _, _, total in prunable)
    print(f"\nreclaimable: {reclaimable / 1048576:.0f} MB across {len(prunable)} directories")
    if kept_bytes:
        print(f"retained (unverified): {kept_bytes / 1048576:.0f} MB")

    if not args.confirm:
        print("\ndry run. re-run with --confirm to delete the VERIFIED directories.")
        return 0

    for directory, _, _ in prunable:
        shutil.rmtree(directory)
        print(f"  deleted {directory}")
    print(f"\nreclaimed {reclaimable / 1048576:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
