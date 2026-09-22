"""Fit how fast a player advances a round goal, for the placement model.

Why
---
``potential_points`` valued the current round's goal with a reachability
heuristic: a gap in items, a fixed 0.6 a turn, no placement table, no
opponent turns, no ties. The 2026-09-22 mirror data showed what that
misses — goals are decided by one item or a tie in half of rounds, and
round 4 pays 7/4 where round 1 pays 4/1.

The replacement needs one empirical input: given a player with ``t`` turns
left in the round, how many more goal items do they gain? This script
measures it from the archive, per goal and per turns-left, by replaying
every game and recording each player's count at each of their turns
against their count when the round was scored.

Output (``configs/round_goals/progress_rates.json``) is a per-goal rate in
items per remaining turn, plus a pooled fallback for goals with too little
data and the per-goal dispersion the model uses.

    python analysis/fit_round_goal_progress.py artifacts/mirror_2p artifacts/rr_belief_opp \\
        --out configs/round_goals/progress_rates.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.play_counterfactuals import load_events, reconstruct_decisions  # noqa: E402
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.rules.base_game import _count_round_goal_items, apply_action  # noqa: E402

#: Below this many observations a goal uses the pooled rate instead.
MIN_OBSERVATIONS = 40


def observations(catalog, events: list[dict]) -> list[dict]:
    """(goal, player turns left, items gained by the end of the round) per turn."""

    rows: list[dict] = []
    pending: list[dict] = []
    for state, action, _event in reconstruct_decisions(catalog, events):
        round_number = state.round_state.round_number
        goal = state.round_goals[round_number - 1]
        goal_name = goal.name.lower()
        for player in state.players:
            pending.append(
                {
                    "goal": goal.name,
                    "round": round_number,
                    "player_id": player.player_id,
                    "turns_left": player.action_cubes_available,
                    "count_now": _count_round_goal_items(goal_name, player),
                }
            )
        after = apply_action(state, action)
        ended = after.round_state.round_number != round_number or after.round_state.game_over
        if not ended:
            continue
        finals = {
            player.player_id: _count_round_goal_items(goal_name, player) for player in after.players
        }
        for row in pending:
            row["gained"] = finals[row["player_id"]] - row["count_now"]
            rows.append(row)
        pending = []
    return rows


def fit(rows: list[dict]) -> dict:
    by_goal: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["turns_left"] > 0:
            by_goal[row["goal"]].append(row)

    def rate(group: list[dict]) -> float:
        # Items per remaining turn, pooled over turns-left (the gain is
        # close to linear in turns left, which the report prints).
        turns = sum(row["turns_left"] for row in group)
        gained = sum(max(row["gained"], 0) for row in group)
        return gained / turns if turns else 0.0

    pooled = rate([row for group in by_goal.values() for row in group])
    goals = {}
    for goal, group in sorted(by_goal.items()):
        goals[goal] = {
            "observations": len(group),
            "rate_per_turn": round(rate(group) if len(group) >= MIN_OBSERVATIONS else pooled, 4),
            "measured_rate": round(rate(group), 4),
            "mean_gain_by_turns_left": {
                str(turns): round(mean([r["gained"] for r in group if r["turns_left"] == turns]), 3)
                for turns in sorted({r["turns_left"] for r in group})
                if any(r["turns_left"] == turns for r in group)
            },
            "pooled_fallback": len(group) < MIN_OBSERVATIONS,
        }
    return {
        "version": "round_goal_progress_v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "observations": len(rows),
        "pooled_rate_per_turn": round(pooled, 4),
        "goals": goals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("configs/round_goals/progress_rates.json"))
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    args = parser.parse_args(argv)

    catalog = load_base_game_content_catalog(args.workbook)
    rows: list[dict] = []
    games = 0
    for root in args.roots:
        for path in sorted(root.rglob("events.jsonl")):
            rows.extend(observations(catalog, load_events(path)))
            games += 1
            if games % 50 == 0:
                print(f"{games} games, {len(rows)} observations", flush=True)
    if not rows:
        print("no observations")
        return 1
    payload = fit(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"{games} games, {len(rows)} observations; pooled {payload['pooled_rate_per_turn']}/turn")
    for goal, entry in payload["goals"].items():
        flag = " (pooled)" if entry["pooled_fallback"] else ""
        print(
            f"  {goal[:44]:44s} {entry['rate_per_turn']:.3f}/turn  n={entry['observations']}{flag}"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
