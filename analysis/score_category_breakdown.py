"""Score composition analysis: where do points actually come from?

Answers two questions from one pass over simulation artifacts:

1. **Composition.** What share of a final score comes from birds, bonus cards,
   round goals, eggs, cached food and tucked cards, and how does that differ
   between winners and losers?
2. **Integrity.** Do the six categories actually sum to the reported total, and
   is every category ever non-zero? A category that is always zero is more
   likely unimplemented than genuinely never scored, and would silently remove a
   whole scoring path from every strategy conclusion.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

CATEGORIES = (
    "bird_points",
    "bonus_points",
    "round_goal_points",
    "egg_points",
    "cached_food_points",
    "tucked_card_points",
)


def load_player_scores(artifact_root: Path) -> list[dict[str, Any]]:
    """Read one row per player per game from `game_ended` telemetry."""

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for events_path in sorted(artifact_root.rglob("events.jsonl")):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        # `game_ended` carries only the acting player's agent_id, so build the
        # per-player mapping from setup telemetry instead of mislabelling every
        # row with whoever happened to take the final turn.
        agent_by_player = {
            event["payload"]["player_id"]: event["payload"]["agent_id"]
            for event in events
            if event.get("event_name") == "setup_selection_applied"
        }
        for event in events:
            if event.get("event_name") != "game_ended":
                continue
            payload = event["payload"]
            outcome = payload["outcome"]
            winners = set(outcome.get("winners", []))
            for player_id, breakdown in payload.get("score_breakdowns", {}).items():
                key = (outcome["game_id"], player_id)
                if key in seen:
                    continue
                seen.add(key)
                row = {category: int(breakdown.get(category, 0)) for category in CATEGORIES}
                row.update(
                    {
                        "game_id": outcome["game_id"],
                        "player_id": player_id,
                        "agent_id": agent_by_player.get(player_id),
                        "reported_total": int(outcome["scores"][player_id]),
                        "is_winner": player_id in winners,
                    }
                )
                row["category_sum"] = sum(row[category] for category in CATEGORIES)
                rows.append(row)
    return rows


def check_integrity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify categories sum to the reported total and that each is reachable."""

    mismatches = [
        {
            "game_id": row["game_id"],
            "player_id": row["player_id"],
            "reported_total": row["reported_total"],
            "category_sum": row["category_sum"],
        }
        for row in rows
        if row["category_sum"] != row["reported_total"]
    ]
    nonzero_counts = {
        category: sum(1 for row in rows if row[category] > 0) for category in CATEGORIES
    }
    never_scored = [category for category, count in nonzero_counts.items() if count == 0]
    return {
        "rows": len(rows),
        "sum_mismatches": len(mismatches),
        "mismatch_examples": mismatches[:5],
        "nonzero_counts": nonzero_counts,
        "never_scored_categories": never_scored,
        "integrity_ok": not mismatches and not never_scored,
    }


def summarize_composition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean points and share of total per category, overall and by outcome."""

    def block(subset: list[dict[str, Any]]) -> dict[str, Any]:
        if not subset:
            return {}
        total = mean(row["reported_total"] for row in subset)
        out = {"n": len(subset), "avg_total": round(total, 2), "categories": {}}
        for category in CATEGORIES:
            value = mean(row[category] for row in subset)
            out["categories"][category] = {
                "avg_points": round(value, 2),
                "share_pct": round(100 * value / total, 1) if total else 0.0,
                "pct_of_players_scoring": round(
                    100 * sum(1 for row in subset if row[category] > 0) / len(subset), 1
                ),
            }
        return out

    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["agent_id"]:
            by_agent[row["agent_id"]].append(row)

    return {
        "overall": block(rows),
        "winners": block([row for row in rows if row["is_winner"]]),
        "losers": block([row for row in rows if not row["is_winner"]]),
        "by_agent": {agent: block(subset) for agent, subset in sorted(by_agent.items())},
    }


def render(integrity: dict[str, Any], composition: dict[str, Any]) -> str:
    lines = ["# Score Composition", ""]

    lines += ["## Integrity checks", ""]
    status = "PASS" if integrity["integrity_ok"] else "FAIL"
    lines += [
        f"- Player-game rows: {integrity['rows']}",
        f"- Categories sum to reported total: **{integrity['rows'] - integrity['sum_mismatches']}"
        f"/{integrity['rows']}**",
        f"- Categories never scored by anyone: "
        f"{integrity['never_scored_categories'] or 'none'}",
        f"- **{status}**",
        "",
    ]
    if integrity["mismatch_examples"]:
        lines += ["Mismatch examples:", ""]
        for item in integrity["mismatch_examples"]:
            lines.append(
                f"- `{item['game_id']}` {item['player_id']}: "
                f"reported {item['reported_total']} vs categories {item['category_sum']}"
            )
        lines.append("")

    for label in ("overall", "winners", "losers"):
        block = composition.get(label) or {}
        if not block:
            continue
        lines += [
            f"## {label.title()} (n={block['n']}, avg total {block['avg_total']})",
            "",
            "| Category | Avg points | Share of total | % of players scoring any |",
            "|---|---:|---:|---:|",
        ]
        ordered = sorted(
            block["categories"].items(),
            key=lambda item: -item[1]["avg_points"],
        )
        for category, stats in ordered:
            lines.append(
                f"| {category} | {stats['avg_points']:.2f} | {stats['share_pct']:.1f}% | "
                f"{stats['pct_of_players_scoring']:.0f}% |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--by-agent", action="store_true")
    args = parser.parse_args()

    rows = load_player_scores(args.artifact_root)
    if not rows:
        print(f"no game_ended telemetry found under {args.artifact_root}")
        return 1
    integrity = check_integrity(rows)
    composition = summarize_composition(rows)
    print(render(integrity, composition))

    if args.by_agent:
        print("## By agent\n")
        header = " | ".join(c.replace("_points", "") for c in CATEGORIES)
        print(f"| Agent | n | Avg total | {header} |")
        print("|---|---:|---:|" + "---:|" * len(CATEGORIES))
        for agent, block in composition["by_agent"].items():
            cells = " | ".join(
                f"{block['categories'][c]['avg_points']:.1f}" for c in CATEGORIES
            )
            print(f"| `{agent}` | {block['n']} | {block['avg_total']:.1f} | {cells} |")
        print()

    if args.json_out:
        args.json_out.write_text(
            json.dumps({"integrity": integrity, "composition": composition}, indent=2) + "\n"
        )
    return 0 if integrity["integrity_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
