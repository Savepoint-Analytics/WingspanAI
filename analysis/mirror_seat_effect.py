"""Seat effect in mirror matches, pooled across roots, one observation per seed.

In a mirror match every seat runs the same agent, so the seat rotations of one
seed are the same game apart from agent ids, holdout draws and (in a study
arm) which seat carries the study config. Averaging the seat-1-minus-last-seat
margin over a seed's rotations therefore cancels the study config and leaves
turn order alone — and it makes one observation per seed, which is the right
count (the rotations are not independent games).

    python analysis/mirror_seat_effect.py artifacts/mirror_2p artifacts/mirror_2p_greedy
    python analysis/mirror_seat_effect.py artifacts/mirror_3p artifacts/mirror_3p_greedy
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


def load_games(root: Path) -> list[dict]:
    games = []
    for manifest_path in sorted(root.rglob("batch_manifest.json")):
        for game in json.loads(manifest_path.read_text(encoding="utf-8")).get("games", []):
            games.append(game)
    return games


def seat_effect(roots: list[Path]) -> dict:
    per_seed: dict[tuple[str, int], list[float]] = defaultdict(list)
    seat_scores: dict[str, list[float]] = defaultdict(list)
    seat_wins: dict[str, list[float]] = defaultdict(list)
    rotations_seen: dict[tuple[str, int], set[int]] = defaultdict(set)
    player_count = None
    for root in roots:
        for game in load_games(root):
            scores = game["outcome"]["scores"]
            player_count = player_count or len(scores)
            if len(scores) != player_count:
                raise ValueError("mixed player counts")
            key = (str(root), game["outcome"]["random_seed"])
            per_seed[key].append(scores["player_1"] - scores[f"player_{player_count}"])
            rotations_seen[key].add(game["seat_rotation"])
            winners = game["outcome"]["winners"]
            for seat, score in scores.items():
                seat_scores[seat].append(score)
                seat_wins[seat].append((1.0 / len(winners)) if seat in winners else 0.0)
    complete = [k for k, r in rotations_seen.items() if len(r) == player_count]
    deltas = [mean(per_seed[k]) for k in complete]
    n = len(deltas)
    if n < 2:
        return {"n": n}
    spread = stdev(deltas)
    t = mean(deltas) / (spread / math.sqrt(n)) if spread else 0.0
    return {
        "player_count": player_count,
        "n_seeds": n,
        "n_games": sum(len(v) for v in per_seed.values()),
        "seat1_minus_last": mean(deltas),
        "p": math.erfc(abs(t) / math.sqrt(2)) if spread else 1.0,
        "detection_limit": 2.8 * spread / math.sqrt(n),
        "seat_mean": {s: mean(v) for s, v in sorted(seat_scores.items())},
        "seat_win": {s: mean(v) for s, v in sorted(seat_wins.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args(argv)
    result = seat_effect(args.roots)
    if result.get("n_seeds", result.get("n", 0)) < 2:
        print("fewer than two complete seeds")
        return 1
    pooled = ", ".join(map(str, args.roots))
    print(f"# Mirror seat effect ({result['player_count']}p), pooled over {pooled}")
    print(f"- {result['n_games']} games, {result['n_seeds']} seeds with every rotation")
    mark = "**" if result["p"] < 0.05 else ""
    print(
        f"- seat 1 − seat {result['player_count']}: {mark}{result['seat1_minus_last']:+.2f}{mark} "
        f"(p = {result['p']:.3f}); detection limit at 80% power ≈ "
        f"{result['detection_limit']:.1f} points"
    )
    print("| Seat | mean score | win rate |")
    print("|---|---:|---:|")
    for seat in result["seat_mean"]:
        print(f"| {seat} | {result['seat_mean'][seat]:.2f} | {result['seat_win'][seat]:.3f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
