"""Round-goal outcomes: who wins each round's goal, by how much, and what it pays.

Reads ``round_goal_scored`` events where a root has them (emitted from
2026-09-22) and falls back to replaying the game otherwise, so the whole
archive is readable with one command. Reports, per round: win share by
lineup position, tie rate, margin distribution, points, and how often
nobody qualified.

    python analysis/round_goal_report.py artifacts/mirror_2p artifacts/mirror_2p_b
    python analysis/round_goal_report.py artifacts/rr_belief_opp --by-agent
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.play_counterfactuals import load_events, reconstruct_decisions  # noqa: E402
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.rules.base_game import (  # noqa: E402
    ROUND_GOAL_GREEN_SCORES,
    TOTAL_ROUNDS,
    _count_round_goal_items,
    apply_action,
)


def rows_from_events(events: list[dict]) -> list[dict]:
    """One row per scored round, from the emitted event."""

    rows = []
    for event in events:
        if event["event_name"] != "round_goal_scored":
            continue
        payload = event["payload"]
        rows.append(
            {
                "round": payload["goal_round"],
                "goal_name": payload["goal_name"],
                "counts": payload["counts"],
                "points": payload["points_awarded"],
                "agent_ids": payload.get("agent_ids", {}),
                "margin": payload["margin"],
                "contested": payload["contested"],
                "nobody_qualified": payload["nobody_qualified"],
            }
        )
    return rows


def rows_from_replay(catalog, events: list[dict]) -> list[dict]:
    """Same rows for a game archived before the event existed."""

    agent_ids = {
        event["payload"]["player_id"]: event["payload"]["agent_id"]
        for event in events
        if event["event_name"] == "setup_selection_applied"
    }
    rows = []
    for state, action, _event in reconstruct_decisions(catalog, events):
        after = apply_action(state, action)
        ended = (
            after.round_state.round_number != state.round_state.round_number
            or after.round_state.game_over
        )
        if not ended:
            continue
        round_number = state.round_state.round_number
        goal = after.round_goals[round_number - 1]
        counts = {
            player.player_id: _count_round_goal_items(goal.name.lower(), player)
            for player in after.players
        }
        points = {
            player.player_id: player.round_goal_points
            - next(p.round_goal_points for p in state.players if p.player_id == player.player_id)
            for player in after.players
        }
        ranked = sorted(counts.values(), reverse=True)
        winners = [p for p, c in counts.items() if c == ranked[0] and c > 0]
        rows.append(
            {
                "round": round_number,
                "goal_name": goal.name,
                "counts": counts,
                "points": points,
                "agent_ids": agent_ids,
                "margin": ranked[0] - ranked[1],
                "contested": len(winners) > 1,
                "nobody_qualified": ranked[0] == 0,
            }
        )
    return rows


def collect(roots: list[Path], workbook: Path) -> tuple[list[dict], int, int]:
    catalog = None
    rows: list[dict] = []
    games = replayed = 0
    for root in roots:
        for path in sorted(root.rglob("events.jsonl")):
            events = load_events(path)
            games += 1
            from_events = rows_from_events(events)
            if from_events:
                rows.extend(from_events)
                continue
            if catalog is None:
                catalog = load_base_game_content_catalog(workbook)
            rows.extend(rows_from_replay(catalog, events))
            replayed += 1
    return rows, games, replayed


def report(rows: list[dict], by_agent: bool) -> str:
    lines = ["# Round-goal outcomes", ""]
    lines.append(
        "| round | pays 1st/2nd | n | seat-1 wins | ties | nobody | margin 0-1 | "
        "mean margin | mean pts to 1st |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for round_number in range(1, TOTAL_ROUNDS + 1):
        group = [row for row in rows if row["round"] == round_number]
        if not group:
            continue
        scale = ROUND_GOAL_GREEN_SCORES[round_number]
        seat_one = sum(
            1
            for row in group
            if row["counts"].get("player_1", 0) == max(row["counts"].values())
            and not row["contested"]
            and not row["nobody_qualified"]
        )
        decided = [row for row in group if not row["nobody_qualified"]]
        ties = sum(1 for row in group if row["contested"])
        nobody = sum(1 for row in group if row["nobody_qualified"])
        close = sum(1 for row in decided if row["margin"] <= 1)
        top_points = [max(row["points"].values()) for row in decided] or [0]
        lines.append(
            f"| {round_number} | {scale[0]}/{scale[1]} | {len(group)} | "
            f"{seat_one / len(group):.3f} | {ties / len(group):.3f} | {nobody / len(group):.3f} | "
            f"{close / max(len(decided), 1):.3f} | {mean(row['margin'] for row in group):.2f} | "
            f"{mean(top_points):.2f} |"
        )
    total_points = sum(sum(row["points"].values()) for row in rows)
    lines += [
        "",
        f"{len(rows)} scored rounds; {total_points} goal points awarded "
        f"({total_points / max(len(rows), 1):.2f} a round).",
    ]
    if by_agent:
        wins: dict[str, Counter] = defaultdict(Counter)
        points: dict[str, list[int]] = defaultdict(list)
        for row in rows:
            best = max(row["counts"].values())
            for player_id, count in row["counts"].items():
                kind = row["agent_ids"].get(player_id, player_id)
                kind = kind.removeprefix("guardrailed_").rsplit("_p", 1)[0]
                wins[kind]["rounds"] += 1
                wins[kind]["won"] += 1 if count == best and best > 0 else 0
                points[kind].append(row["points"][player_id])
        lines += [
            "",
            "| agent | scored rounds | goal win share | mean points a round |",
            "|---|---:|---:|---:|",
        ]
        for kind in sorted(wins, key=lambda k: -mean(points[k])):
            lines.append(
                f"| `{kind}` | {wins[kind]['rounds']} | "
                f"{wins[kind]['won'] / wins[kind]['rounds']:.3f} | {mean(points[kind]):.2f} |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--by-agent", action="store_true")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--out", type=Path, default=None, help="also write the rows as JSON")
    args = parser.parse_args(argv)
    rows, games, replayed = collect(args.roots, args.workbook)
    if not rows:
        print("no scored rounds found")
        return 1
    print(report(rows, args.by_agent))
    print(f"\n{games} games ({replayed} replayed; the rest read their round_goal_scored events).")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
