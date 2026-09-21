"""Paired contrast of one or more experimental arms against a baseline arm.

Each arm is a full round robin under one setting (an ablation switch, a search
depth, a roster twin). Because `random_seed` is the sole reproducibility key
(ADR 0003) and every arm runs the same counterbalanced cells, a game in one arm
has an exact counterpart in every other arm: same lineup, same seat rotation,
same seed. Differencing those pairs removes deck and seat luck entirely, which
is what makes 200-game arms readable at all — the raw score SD is around 16
points; the paired-delta SD is around 9.5.

Three earlier ablations (mat scaling, feeder odds, resource spending) computed
this by hand. This script is the standing version, so every future arm gets the
same report and the same fragility flags.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev


@dataclass(frozen=True)
class GameKey:
    lineup: tuple[str, ...]
    rotation: int
    seed: int
    #: Games under different rulesets (content packs, rules modules) never
    #: pair: the decks differ, so the seed does not difference anything out.
    ruleset_id: str = "core_base_game_v1"


def load_arm(artifact_root: Path) -> dict[GameKey, dict]:
    """Every counterbalanced game under one artifact root, keyed for pairing."""

    games: dict[GameKey, dict] = {}
    for manifest_path in sorted(artifact_root.rglob("batch_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for game in manifest.get("games", []):
            if "seat_rotation" not in game or "player_agent_kinds" not in game:
                continue
            key = GameKey(
                lineup=tuple(game["player_agent_kinds"]),
                rotation=game["seat_rotation"],
                seed=game["outcome"]["random_seed"],
                ruleset_id=game.get("ruleset_id") or "core_base_game_v1",
            )
            games[key] = game
    return games


def split_agent(agent: str) -> tuple[str, int | None]:
    """``kind`` or ``kind@position`` → (kind, lineup position or None)."""

    kind, _, position = agent.partition("@")
    return kind, (int(position) if position else None)


def lineup_position(lineup: tuple[str, ...] | list[str], agent: str) -> int | None:
    """Lineup index of ``agent``; ``kind@N`` names position N, which must hold that kind.

    A mirror match names the same kind in two positions, so the study seat
    has to be addressed by position — it travels with the policy through
    every seat rotation, exactly like the holdout key.
    """

    kind, position = split_agent(agent)
    if position is not None:
        return position if position < len(lineup) and lineup[position] == kind else None
    return lineup.index(kind) if kind in lineup else None


def agent_result(game: dict, agent: str) -> tuple[float, float] | None:
    """(score, win share) for `agent` in one game, or None if it did not play."""

    lineup = game["player_agent_kinds"]
    position = lineup_position(lineup, agent)
    if position is None:
        return None
    seat = (position - game["seat_rotation"]) % game["player_count"]
    scores = game["outcome"]["scores"]
    own = scores[f"player_{seat + 1}"]
    best = max(scores.values())
    if own < best:
        win = 0.0
    else:
        win = 1.0 / sum(1 for value in scores.values() if value == best)
    return float(own), win


def paired_test(deltas: list[float]) -> tuple[float, float]:
    """(mean delta, two-sided p) under a normal approximation to the paired t."""

    if len(deltas) < 2:
        return (mean(deltas) if deltas else 0.0), 1.0
    spread = stdev(deltas)
    if spread == 0:
        return mean(deltas), 1.0
    t_statistic = mean(deltas) / (spread / math.sqrt(len(deltas)))
    return mean(deltas), math.erfc(abs(t_statistic) / math.sqrt(2))


def contrast(
    baseline: dict[GameKey, dict],
    arm: dict[GameKey, dict],
    agent: str,
) -> dict:
    """Per-agent paired contrast of `arm` against `baseline`."""

    shared = sorted(
        (key for key in baseline if key in arm and lineup_position(key.lineup, agent) is not None),
        key=lambda key: (key.lineup, key.rotation, key.seed),
    )
    base_scores, arm_scores, base_wins, arm_wins = [], [], [], []
    by_opponent: dict[str, list[float]] = defaultdict(list)
    for key in shared:
        base = agent_result(baseline[key], agent)
        other = agent_result(arm[key], agent)
        assert base is not None and other is not None
        base_scores.append(base[0])
        arm_scores.append(other[0])
        base_wins.append(base[1])
        arm_wins.append(other[1])
        own_position = lineup_position(key.lineup, agent)
        opponents = tuple(kind for index, kind in enumerate(key.lineup) if index != own_position)
        by_opponent["+".join(opponents)].append(other[0] - base[0])

    score_deltas = [a - b for a, b in zip(arm_scores, base_scores, strict=True)]
    win_deltas = [a - b for a, b in zip(arm_wins, base_wins, strict=True)]
    score_delta, score_p = paired_test(score_deltas)
    win_delta, win_p = paired_test(win_deltas)
    return {
        "agent": agent,
        "n": len(shared),
        "baseline_score": mean(base_scores) if base_scores else 0.0,
        "arm_score": mean(arm_scores) if arm_scores else 0.0,
        "score_delta": score_delta,
        "score_p": score_p,
        "baseline_win": mean(base_wins) if base_wins else 0.0,
        "arm_win": mean(arm_wins) if arm_wins else 0.0,
        "win_delta": win_delta,
        "win_p": win_p,
        "by_opponent": {
            name: paired_test(deltas) + (len(deltas),) for name, deltas in by_opponent.items()
        },
    }


def unchanged_games(baseline: dict[GameKey, dict], arm: dict[GameKey, dict]) -> tuple[int, int]:
    """(identical, compared) outcome counts over shared games.

    Games whose lineup excludes the varied agent should be bit-identical across
    arms; a mismatch means the arms differ in more than the intended factor.
    """

    identical = compared = 0
    for key, game in baseline.items():
        if key not in arm:
            continue
        compared += 1
        identical += game["outcome"]["scores"] == arm[key]["outcome"]["scores"]
    return identical, compared


def render(
    baseline_name: str,
    baseline: dict[GameKey, dict],
    arms: dict[str, dict[GameKey, dict]],
    agents: list[str],
) -> str:
    rulesets = sorted({key.ruleset_id for key in baseline})
    lines = [
        "# Arm Contrast",
        "",
        f"Baseline: `{baseline_name}` ({len(baseline)} games; ruleset {', '.join(rulesets)})",
        "",
    ]
    for arm_name, arm in arms.items():
        identical, compared = unchanged_games(baseline, arm)
        lines += [
            f"## `{arm_name}` vs baseline",
            "",
            f"- Shared games: {compared}; identical outcomes: {identical}",
            "",
            "| Agent | n | Score base → arm | Δ score | p | Win base → arm | Δ win | p |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for agent in agents:
            row = contrast(baseline, arm, agent)
            if row["n"] == 0:
                continue
            mark = "**" if row["score_p"] < 0.05 else ""
            lines.append(
                f"| `{agent}` | {row['n']} | {row['baseline_score']:.2f} → {row['arm_score']:.2f} "
                f"| {mark}{row['score_delta']:+.2f}{mark} | {row['score_p']:.3f} "
                f"| {row['baseline_win']:.3f} → {row['arm_win']:.3f} "
                f"| {row['win_delta']:+.3f} | {row['win_p']:.3f} |"
            )
        lines.append("")
        for agent in agents:
            row = contrast(baseline, arm, agent)
            if row["n"] == 0 or len(row["by_opponent"]) < 2:
                continue
            lines += [
                f"### `{agent}` score Δ by opponent",
                "",
                "| Opponent | n | Δ | p |",
                "|---|---:|---:|---:|",
            ]
            for name, (delta, p_value, n) in sorted(row["by_opponent"].items()):
                lines.append(f"| `{name}` | {n} | {delta:+.2f} | {p_value:.3f} |")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, required=True, help="artifact root of the baseline arm"
    )
    parser.add_argument(
        "--arm", type=Path, action="append", required=True, help="artifact root(s) to contrast"
    )
    parser.add_argument(
        "--agent",
        action="append",
        help="agent(s) to report; default: all in the baseline. ``kind@N`` reads lineup "
        "position N (the study seat of a mirror match, e.g. potential_points@1)",
    )
    args = parser.parse_args()

    baseline = load_arm(args.baseline)
    if not baseline:
        print(f"no games under {args.baseline}")
        return 1
    arms = {str(path): load_arm(path) for path in args.arm}
    agents = args.agent or sorted({kind for key in baseline for kind in key.lineup})
    print(render(str(args.baseline), baseline, arms, agents))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
