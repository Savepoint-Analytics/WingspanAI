"""Gzip the bulky per-game files under finished artifact roots.

Each game writes ``events.jsonl`` (what every analysis reads),
``public_state_snapshots.json`` (a full public state per turn, ~1 MB, read
by nothing in ``analysis/``; games replay from events) and
``replay_debug.json``. Snapshots are about half of the 14 GB archive. This
gzips snapshots and replay debug in place (``*.json.gz``), leaves events
and manifests untouched, and skips any root whose batch is still running
(a ``launch/*.log`` without ``GROUP COMPLETE`` for every runner, or a game
directory without ``outcome.json``). Reversible with ``--restore``.

    python analysis/compact_artifacts.py artifacts/rr_depth_* artifacts/forced_play
    python analysis/compact_artifacts.py --restore artifacts/rr_depth_d3_f8
"""

from __future__ import annotations

import argparse
import gzip
import shutil
from pathlib import Path

BULKY = ("public_state_snapshots.json", "replay_debug.json")


def root_is_finished(root: Path) -> bool:
    launch = root / "launch"
    if launch.exists():
        logs = [p for p in launch.rglob("*.log") if p.name not in ("queue.log", "queue_runner.log")]
        started = [p for p in logs if "start" in p.read_text(errors="ignore")]
        if any("GROUP COMPLETE" not in p.read_text(errors="ignore") for p in started):
            return False
    for events in root.rglob("events.jsonl"):
        if not (events.parent / "outcome.json").exists():
            return False
    return True


def compact(root: Path) -> tuple[int, int]:
    files = saved = 0
    for name in BULKY:
        for path in root.rglob(name):
            before = path.stat().st_size
            with path.open("rb") as src, gzip.open(path.with_suffix(".json.gz"), "wb", 6) as dst:
                shutil.copyfileobj(src, dst)
            path.unlink()
            files += 1
            saved += before - path.with_suffix(".json.gz").stat().st_size
    return files, saved


def restore(root: Path) -> int:
    files = 0
    for name in BULKY:
        for path in root.rglob(name + ".gz"):
            with gzip.open(path, "rb") as src, path.with_suffix("").open("wb") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink()
            files += 1
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument(
        "--force", action="store_true", help="compact even if the root looks unfinished"
    )
    args = parser.parse_args(argv)
    total_saved = 0
    for root in args.roots:
        if not root.is_dir():
            print(f"{root}: not a directory, skipped")
            continue
        if args.restore:
            print(f"{root}: restored {restore(root)} files")
            continue
        if not args.force and not root_is_finished(root):
            print(f"{root}: still running, skipped")
            continue
        files, saved = compact(root)
        total_saved += saved
        print(f"{root}: {files} files, {saved / 1e9:.2f} GB saved")
    if not args.restore:
        print(f"total {total_saved / 1e9:.2f} GB saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
