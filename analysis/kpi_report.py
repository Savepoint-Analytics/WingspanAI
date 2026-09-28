"""Run the KPI taxonomy against the persisted archive and print it as Markdown.

Why a script and not only the notebook
--------------------------------------
``notebooks/wingspan_kpi_walkthrough.ipynb`` was the only way to produce these
numbers, so the 2026-09-22 pass could not be re-run or diffed when the archive
changed underneath it -- and it did change: ``game_id`` was not unique
(ADR 0006), so that pass silently read an arbitrary ~55% of the games. This
gives the same figures a reproducible entry point.

    python analysis/kpi_report.py                       # scores only (fast)
    python analysis/kpi_report.py --events              # adds the event-driven KPIs
    python analysis/kpi_report.py --run-labels rr3p_goal_place25
    python analysis/kpi_report.py --out docs/experiments/kpi_pass.md
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wingspan_ai.analysis import kpis  # noqa: E402
from wingspan_ai.analysis.persistence import (  # noqa: E402
    load_game_scores,
    load_games,
    load_postgres_event_records,
)

Row = Mapping[str, Any]

#: Columns worth printing per section, in order. Anything else in the row is
#: still computed, just not shown -- the point is a readable report, not a dump.
COLUMNS: dict[str, tuple[str, ...]] = {
    "scoring.by_agent": (
        "agent",
        "player_games",
        "win_rate",
        "avg_total_score",
        "avg_bird_points",
        "avg_bonus_points",
        "avg_round_goal_points",
        "avg_egg_points",
        "avg_cached_food_points",
        "avg_tucked_card_points",
    ),
    "scoring.composition": (
        "category",
        "avg_points",
        "share_of_total",
        "players_scoring_pct",
        "max_points",
    ),
    "comparative.head_to_head": (
        "agent",
        "opponent",
        "player_games",
        "avg_score_margin",
        "win_rate",
    ),
    "comparative.margins": ("winner_agent", "wins", "avg_winning_score", "avg_margin"),
}


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}" if abs(value) < 100 else f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def table(rows: Sequence[Row], columns: Sequence[str] | None = None, limit: int = 40) -> str:
    rows = list(rows)
    if not rows:
        return "_no rows_\n"
    keys = list(columns) if columns else list(rows[0].keys())
    keys = [k for k in keys if any(k in row for row in rows)]
    out = ["| " + " | ".join(keys) + " |", "|" + "|".join("---" for _ in keys) + "|"]
    for row in rows[:limit]:
        out.append("| " + " | ".join(fmt(row.get(k, "")) for k in keys) + " |")
    if len(rows) > limit:
        out.append(f"\n_{len(rows) - limit} further rows omitted_")
    return "\n".join(out) + "\n"


def section(title: str, payload: dict[str, list[Row]], prefix: str) -> list[str]:
    lines = [f"\n### {title}\n"]
    for name, rows in payload.items():
        lines.append(f"\n**{name}**\n")
        lines.append(table(rows, COLUMNS.get(f"{prefix}.{name}")))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run-labels", nargs="*", default=None)
    parser.add_argument(
        "--events",
        action="store_true",
        help="also run the event-driven KPIs (round goals, bonus cards, birds, actions, tempo)",
    )
    parser.add_argument("--out", default=None, help="write Markdown here instead of stdout")
    args = parser.parse_args(argv)

    scores = load_game_scores(run_labels=args.run_labels)
    games = load_games(run_labels=args.run_labels)
    runs = {row.get("simulation_run_id") for row in games}
    lines = [
        "# Wingspan KPI pass",
        "",
        f"- games: **{len(games):,}**",
        f"- player-games: **{len(scores):,}**",
        f"- distinct runs: **{len(runs):,}**",
        f"- run labels: {'all' if not args.run_labels else ', '.join(args.run_labels)}",
    ]
    lines += section("Scoring", kpis.scoring_kpis(scores), "scoring")
    lines += section("Comparative", kpis.comparative_kpis(scores), "comparative")

    if args.events:
        # Load per family rather than the whole log. action_resolved alone is
        # 606k rows; pulling every family at once costs gigabytes for no gain,
        # and load_postgres_event_records' own docstring says as much.
        def load(*names: str) -> list[dict]:
            return load_postgres_event_records(
                run_label=args.run_labels[0] if args.run_labels else None,
                event_names=list(names),
            )

        goals = load("round_goal_scored", "game_ended")
        lines.append(f"\n_round-goal events: {len(goals):,}_\n")
        lines += section("Round goals", kpis.round_goal_kpis(scores, goals), "round_goal")

        cards = load("setup_selection_applied", "bird_scorecard")
        lines.append(f"\n_selection + scorecard events: {len(cards):,}_\n")
        lines += section("Bonus cards", kpis.bonus_card_kpis(cards), "bonus_card")
        lines += section("Tempo", kpis.tempo_kpis(cards), "tempo")

        actions = load("action_resolved")
        lines.append(f"\n_action events: {len(actions):,}_\n")
        lines += section("Actions", kpis.action_kpis(actions, scores), "action")
        lines += section(
            "Bird utilization", kpis.bird_utilization_kpis(actions + cards), "bird"
        )

    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"wrote {args.out} ({len(report):,} chars)")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
