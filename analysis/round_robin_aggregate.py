"""Aggregate round-robin standings across chunked runs, from artifacts.

A full round robin over expensive agents exceeds a single process budget, so it
is run in seed chunks. `random_seed` is the sole reproducibility key (ADR 0003),
so chunks are independent and combinable: this reads every counterbalanced cell
manifest and reuses `summarize_round_robin` to produce one summary over all of
them.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flows.round_robin import (  # noqa: E402
    MatchupCell,
    format_round_robin_report,
    summarize_round_robin,
    summarize_setup_policy_effect,
)


def collect_cells(
    artifact_root: Path,
    label_filter: str,
) -> tuple[list[MatchupCell], list[list[dict]]]:
    """Rebuild (cell, games) pairs from every matching batch manifest."""

    # (lineup, setup_policy_kind, rotation) -> {seed: game}
    grouped: dict[tuple, dict[int, dict]] = defaultdict(dict)
    for manifest_path in sorted(artifact_root.rglob("batch_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        label = manifest.get("batch_label", "")
        if label_filter not in label or "-rot" not in label:
            continue
        for game in manifest.get("games", []):
            if "seat_rotation" not in game or "player_agent_kinds" not in game:
                continue
            key = (
                tuple(game["player_agent_kinds"]),
                game.get("setup_policy_kind", "control"),
                game["seat_rotation"],
            )
            # De-duplicate repeated runs of the same cell/seed.
            grouped[key][game["outcome"]["random_seed"]] = game

    cells: list[MatchupCell] = []
    results: list[list[dict]] = []
    for (lineup, setup_policy_kind, rotation), by_seed in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])
    ):
        cells.append(
            MatchupCell(
                lineup=lineup,
                setup_policy_kind=setup_policy_kind,
                seat_rotation=rotation,
            )
        )
        results.append([by_seed[seed] for seed in sorted(by_seed)])
    return cells, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/experiment"))
    parser.add_argument("--label", default="", help="substring filter on batch_label")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    cells, results = collect_cells(args.artifact_root, args.label)
    if not cells:
        print(f"no counterbalanced cells found under {args.artifact_root}")
        return 1

    seeds = sorted({game["outcome"]["random_seed"] for group in results for game in group})
    rotations_per_lineup: dict[tuple, set[int]] = defaultdict(set)
    for cell in cells:
        rotations_per_lineup[(cell.lineup, cell.setup_policy_kind)].add(cell.seat_rotation)
    incomplete = [
        lineup
        for (lineup, _level), rotations in rotations_per_lineup.items()
        if len(rotations) != len(lineup)
    ]

    summary = summarize_round_robin(cells, results)
    summary.update(
        {
            "batch_label": args.label or "round_robin",
            "batch_id": "aggregated",
            "seeds": seeds,
            "roster": sorted({agent for cell in cells for agent in cell.lineup}),
            "player_count": cells[0].player_count,
            "setup_policy_kinds": sorted({cell.setup_policy_kind for cell in cells}),
            "seat_counterbalanced": not incomplete,
            "setup_policy_effect": summarize_setup_policy_effect(summary),
        }
    )

    if incomplete:
        print(
            f"WARNING: {len(incomplete)} lineup(s) lack a complete rotation set; "
            "seat contrasts for those are not counterbalanced.\n"
        )
    print(format_round_robin_report(summary))
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
