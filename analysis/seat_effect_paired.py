"""Paired seat-effect analysis with an automatic stability diagnostic.

Why paired
----------
`summarize_seat_effect` pools every seat observation and compares each seat's win
rate against its fair share. That treats observations as independent, which is
conservative: seat counterbalancing means the *same* agent plays the *same* seed
in every seat, so agent strength and deck luck can be differenced out entirely.

For each (lineup, seed, agent) this script recovers the agent's score in each
seat and contrasts it against that agent's own cross-seat mean.

Why the stability check exists
------------------------------
On 2026-09-03 a four-player run reported seat 3 at +3.24 points (p=0.03) and
seat 4 at -3.65 (p=0.01) over 60 games. Splitting by seed block showed the entire
result came from one 20-game block: excluding seeds 11-15 left seat 3 at +0.01
points (p=0.994). Seat 3 flipped sign across blocks (+2.10, -2.08, +9.69).

Per-game score variance is around 15 points while plausible seat effects are
about 2, so 20-60 game samples produce spurious significance readily. Every
report therefore carries a leave-one-block-out check, and a pooled result that
depends on a single block is labelled FRAGILE rather than reported as a finding.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev

#: Seeds per stability block. Blocks mirror how runs are actually chunked.
DEFAULT_BLOCK_SIZE = 5


@dataclass(frozen=True)
class PairedUnit:
    """One agent's scores across every seat, for one lineup and seed."""

    player_count: int
    seed: int
    agent: str
    scores: dict[int, int]

    @property
    def is_complete(self) -> bool:
        return len(self.scores) == self.player_count

    def delta_for(self, seat: int) -> float:
        return self.scores[seat] - mean(self.scores.values())


def load_games(artifact_root: Path, label_filter: str) -> list[dict]:
    """Read every per-game record from matching round-robin cell manifests."""

    games = []
    for manifest_path in sorted(artifact_root.rglob("batch_manifest.json")):
        if label_filter not in str(manifest_path):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for game in manifest.get("games", []):
            if "seat_rotation" not in game or "player_agent_kinds" not in game:
                continue
            games.append(game)
    return games


def build_paired_units(games: list[dict]) -> list[PairedUnit]:
    """Recover each agent's score in every seat, undoing the rotation."""

    collected: dict[tuple, dict[int, int]] = defaultdict(dict)
    seen: set[tuple] = set()
    for game in games:
        lineup = tuple(game["player_agent_kinds"])
        rotation = game["seat_rotation"]
        player_count = game["player_count"]
        seed = game["outcome"]["random_seed"]
        # De-duplicate repeated runs of the same cell and seed.
        if (lineup, rotation, seed) in seen:
            continue
        seen.add((lineup, rotation, seed))
        scores = game["outcome"]["scores"]
        for lineup_index, agent in enumerate(lineup):
            seat = (lineup_index - rotation) % player_count
            key = (player_count, lineup, seed, lineup_index, agent)
            collected[key][seat] = scores[f"player_{seat + 1}"]

    units = [
        PairedUnit(player_count=key[0], seed=key[2], agent=key[4], scores=scores)
        for key, scores in collected.items()
    ]
    return [unit for unit in units if unit.is_complete]


def paired_test(units: list[PairedUnit], seat: int) -> tuple[float, float, int]:
    """Return (mean delta, two-sided p, n) for one seat against its own mean."""

    deltas = [unit.delta_for(seat) for unit in units if seat in unit.scores]
    if len(deltas) < 2:
        return 0.0, 1.0, len(deltas)
    spread = stdev(deltas)
    if spread == 0:
        return mean(deltas), 1.0, len(deltas)
    standard_error = spread / math.sqrt(len(deltas))
    t_statistic = mean(deltas) / standard_error
    return mean(deltas), math.erfc(abs(t_statistic) / math.sqrt(2)), len(deltas)


def _blocks(units: list[PairedUnit], block_size: int) -> dict[str, list[PairedUnit]]:
    grouped: dict[str, list[PairedUnit]] = defaultdict(list)
    for unit in units:
        start = ((unit.seed - 1) // block_size) * block_size + 1
        grouped[f"seeds {start}-{start + block_size - 1}"].append(unit)
    return dict(sorted(grouped.items(), key=lambda item: int(item[0].split()[1].split("-")[0])))


def stability_report(
    units: list[PairedUnit],
    player_count: int,
    block_size: int = DEFAULT_BLOCK_SIZE,
    alpha: float = 0.05,
) -> dict:
    """Leave-one-block-out check on every seat's pooled result.

    A pooled effect that loses significance when any single block is removed is
    driven by that block, not by the sample, and is reported as FRAGILE.
    """

    blocks = _blocks(units, block_size)
    seats = range(player_count)
    per_block = {
        name: {seat: paired_test(block, seat)[:2] for seat in seats}
        for name, block in blocks.items()
    }
    drop_one = {}
    for name in blocks:
        remaining = [u for other, block in blocks.items() if other != name for u in block]
        drop_one[name] = {seat: paired_test(remaining, seat)[:2] for seat in seats}

    verdicts = {}
    for seat in seats:
        pooled_delta, pooled_p, _ = paired_test(units, seat)
        if pooled_p >= alpha:
            verdicts[seat] = "not significant"
            continue
        if len(blocks) < 2:
            verdicts[seat] = "UNVERIFIABLE (one block)"
            continue
        # Significant pooled: does it survive removing each block in turn?
        survives = all(drop_one[name][seat][1] < alpha for name in blocks)
        signs = {math.copysign(1, per_block[name][seat][0]) for name in blocks}
        verdicts[seat] = (
            "robust"
            if survives and len(signs) == 1
            else "FRAGILE (depends on one block)"
            if not survives
            else "FRAGILE (sign flips across blocks)"
        )
    return {
        "blocks": per_block,
        "drop_one": drop_one,
        "verdicts": verdicts,
        "block_count": len(blocks),
    }


def render(units: list[PairedUnit], block_size: int) -> str:
    by_count: dict[int, list[PairedUnit]] = defaultdict(list)
    for unit in units:
        by_count[unit.player_count].append(unit)

    lines = ["# Paired Seat-Effect Analysis", ""]
    for player_count, group in sorted(by_count.items()):
        lines += [
            f"## {player_count} players",
            "",
            f"- Paired units (agent x lineup x seed): {len(group)}",
            "",
            "| Seat | n | Mean score | Paired delta vs own mean | p |",
            "|---:|---:|---:|---:|---:|",
        ]
        for seat in range(player_count):
            delta, p_value, n = paired_test(group, seat)
            mean_score = mean(u.scores[seat] for u in group if seat in u.scores)
            mark = "**" if p_value < 0.05 else ""
            lines.append(
                f"| {seat + 1} | {n} | {mean_score:.2f} | "
                f"{mark}{delta:+.3f}{mark} | {p_value:.4f} |"
            )
        seat_means = [
            mean(u.scores[s] for u in group if s in u.scores) for s in range(player_count)
        ]
        lines += [
            "",
            f"Raw score spread between best and worst seat: "
            f"**{max(seat_means) - min(seat_means):.2f} points**",
            "",
            "### Stability (leave-one-block-out)",
            "",
        ]
        report = stability_report(group, player_count, block_size)
        if report["block_count"] < 2:
            lines += ["Only one seed block; stability cannot be assessed.", ""]
            continue

        header = " | ".join(f"seat {s + 1}" for s in range(player_count))
        lines += [
            f"| Subset | {header} |",
            "|---|" + "---:|" * player_count,
        ]
        for name, seats in report["blocks"].items():
            cells = " | ".join(
                f"{seats[s][0]:+.2f} (p={seats[s][1]:.2f})" for s in range(player_count)
            )
            lines.append(f"| {name} | {cells} |")
        for name, seats in report["drop_one"].items():
            cells = " | ".join(
                f"{seats[s][0]:+.2f} (p={seats[s][1]:.2f})" for s in range(player_count)
            )
            lines.append(f"| excluding {name} | {cells} |")

        lines += ["", "| Seat | Verdict |", "|---:|---|"]
        for seat, verdict in report["verdicts"].items():
            lines.append(f"| {seat + 1} | {verdict} |")
        fragile = [s + 1 for s, v in report["verdicts"].items() if v.startswith("FRAGILE")]
        if fragile:
            lines += [
                "",
                f"> **Do not report seats {fragile} as findings.** Their pooled "
                "significance disappears when a single seed block is removed, which "
                "means one block is carrying the result.",
            ]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/experiment"))
    parser.add_argument("--label", default="", help="substring filter on manifest paths")
    parser.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    args = parser.parse_args()

    games = load_games(args.artifact_root, args.label)
    if not games:
        print(f"no games found under {args.artifact_root} matching '{args.label}'")
        return 1
    units = build_paired_units(games)
    if not units:
        print("no complete paired units; seat rotations may be incomplete")
        return 1
    print(f"loaded {len(games)} games\n")
    print(render(units, args.block_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
