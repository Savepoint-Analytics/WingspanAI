"""Compare local simulation batch manifests and event artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def load_batch_manifest(path: str | Path) -> dict[str, Any]:
    """Load a batch manifest written by ``flows/simulation_batch.py``."""

    resolved_path = Path(path)
    return json.loads(resolved_path.read_text(encoding="utf-8"))


def compare_batch_manifests(paths: list[str | Path]) -> dict[str, Any]:
    """Return score, action, and decision summaries for batch manifests."""

    manifests = [load_batch_manifest(path) for path in paths]
    batch_summaries = [_summarize_manifest(manifest) for manifest in manifests]
    action_rows = [
        row
        for manifest in manifests
        for row in _action_frequency_rows(manifest)
    ]
    decision_rows = [
        row
        for manifest in manifests
        for row in _decision_summary_rows(manifest)
    ]
    return {
        "batch_count": len(manifests),
        "batch_summaries": batch_summaries,
        "action_frequency": action_rows,
        "decision_summaries": decision_rows,
    }


def render_markdown_report(comparison: dict[str, Any]) -> str:
    """Render a compact Markdown report for console or docs use."""

    lines = [
        "# Simulation Batch Comparison",
        "",
        "## Batch Outcomes",
        "",
        "| Batch | Player 2 agent | Games | P2 wins | P2 win rate | P1 avg | P2 avg | Avg margin |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["batch_summaries"]:
        lines.append(
            "| {batch_label} | {player_two_agent_id} | {game_count} | "
            "{player_two_wins:.1f} | {player_two_win_rate:.3f} | "
            "{player_one_avg_score:.2f} | {player_two_avg_score:.2f} | "
            "{average_margin:.2f} |".format(**row)
        )

    if comparison["decision_summaries"]:
        lines.extend(
            [
                "",
                "## Decision Telemetry",
                "",
                "| Batch | Agent | Decisions | Avg score delta | Avg value delta | "
                "Avg realized delta | Endgame search share | Avg guardrail candidates |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in comparison["decision_summaries"]:
            lines.append(
                "| {batch_label} | {agent_id} | {decision_count} | "
                "{average_selected_score_delta} | "
                "{average_selected_value_delta} | "
                "{average_selected_realized_delta} | "
                "{endgame_search_share} | "
                "{average_guardrail_candidate_count} |".format(
                    batch_label=row["batch_label"],
                    agent_id=row["agent_id"],
                    decision_count=row["decision_count"],
                    average_selected_score_delta=_format_optional(
                        row["average_selected_score_delta"],
                        3,
                    ),
                    average_selected_value_delta=_format_optional(
                        row["average_selected_value_delta"],
                        3,
                    ),
                    average_selected_realized_delta=_format_optional(
                        row["average_selected_realized_delta"],
                        3,
                    ),
                    endgame_search_share=_format_optional(row["endgame_search_share"], 3),
                    average_guardrail_candidate_count=_format_optional(
                        row["average_guardrail_candidate_count"],
                        2,
                    ),
                )
            )

    if comparison["action_frequency"]:
        lines.extend(
            [
                "",
                "## Player 2 Action Mix",
                "",
                "| Batch | Agent | Action | Count | Share |",
                "|---|---|---|---:|---:|",
            ]
        )
        for row in comparison["action_frequency"]:
            lines.append(
                "| {batch_label} | {agent_id} | {action_type} | {count} | {share:.3f} |".format(
                    **row
                )
            )

    return "\n".join(lines) + "\n"


def _summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    games = manifest["games"]
    player_two_agent_id = _single_or_joined(manifest.get("player_two_agent_ids", []))
    p1_scores = [game["outcome"]["scores"]["player_1"] for game in games]
    p2_scores = [game["outcome"]["scores"]["player_2"] for game in games]
    p2_wins = sum(_fractional_win(game["outcome"]["winners"], "player_2") for game in games)
    return {
        "batch_id": manifest["batch_id"],
        "batch_kind": manifest["batch_kind"],
        "batch_label": manifest["batch_label"],
        "player_two_agent_id": player_two_agent_id,
        "player_two_agent_kind": _single_or_joined(manifest.get("player_two_agent_kinds", [])),
        "guardrail_config_names": manifest.get("guardrail_config_names", []),
        "game_count": len(games),
        "player_two_wins": p2_wins,
        "player_two_win_rate": p2_wins / len(games) if games else 0.0,
        "player_one_avg_score": mean(p1_scores) if p1_scores else 0.0,
        "player_two_avg_score": mean(p2_scores) if p2_scores else 0.0,
        "average_margin": mean(p2 - p1 for p1, p2 in zip(p1_scores, p2_scores, strict=True))
        if games
        else 0.0,
        "event_count": manifest["event_count"],
        "all_replays_valid": manifest["replay_validation"]["all_valid"],
    }


def _action_frequency_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    player_two_agent_ids = set(manifest.get("player_two_agent_ids", []))
    counts: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    for event in _iter_events(manifest):
        if event.get("event_name") != "action_selected":
            continue
        agent_id = str(event.get("agent_id"))
        if agent_id not in player_two_agent_ids:
            continue
        action_type = str(event.get("payload", {}).get("action", {}).get("action_type"))
        counts[(agent_id, action_type)] += 1
        totals[agent_id] += 1

    rows = []
    for (agent_id, action_type), count in sorted(counts.items()):
        rows.append(
            {
                "batch_label": manifest["batch_label"],
                "agent_id": agent_id,
                "action_type": action_type,
                "count": count,
                "share": count / totals[agent_id] if totals[agent_id] else 0.0,
            }
        )
    return rows


def _decision_summary_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    player_two_agent_ids = set(manifest.get("player_two_agent_ids", []))
    summaries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in _iter_events(manifest):
        if event.get("event_name") != "agent_decision_summary":
            continue
        agent_id = str(event.get("agent_id"))
        if agent_id not in player_two_agent_ids:
            continue
        summaries[agent_id].append(event.get("payload", {}))

    rows = []
    for agent_id, payloads in sorted(summaries.items()):
        value_deltas = [
            delta
            for payload in payloads
            if (delta := _nested_number(payload, "selected_value_delta")) is not None
        ]
        score_deltas = [
            delta
            for payload in payloads
            if (delta := _nested_number(payload, "score_delta")) is not None
        ]
        realized_deltas = [
            delta
            for payload in payloads
            if (delta := _nested_number(payload, "selected_realized_delta")) is not None
        ]
        endgame_flags = [
            bool(flag)
            for payload in payloads
            if (flag := _nested_value(payload, "endgame_search_used")) is not None
        ]
        guardrail_candidates = [
            count
            for payload in payloads
            if (count := _nested_number(payload, "guardrail_candidate_action_count")) is not None
        ]
        rows.append(
            {
                "batch_label": manifest["batch_label"],
                "agent_id": agent_id,
                "decision_count": len(payloads),
                "average_selected_score_delta": mean(score_deltas) if score_deltas else None,
                "average_selected_value_delta": mean(value_deltas) if value_deltas else None,
                "average_selected_realized_delta": mean(realized_deltas)
                if realized_deltas
                else None,
                "endgame_search_share": mean(endgame_flags) if endgame_flags else None,
                "average_guardrail_candidate_count": mean(guardrail_candidates)
                if guardrail_candidates
                else None,
            }
        )
    return rows


def _iter_events(manifest: dict[str, Any]):
    for game in manifest["games"]:
        artifact_dir = game.get("artifact_dir")
        if artifact_dir is None:
            continue
        events_path = Path(artifact_dir) / "events.jsonl"
        if not events_path.exists():
            continue
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line:
                yield json.loads(line)


def _fractional_win(winners: list[str], player_id: str) -> float:
    if player_id not in winners:
        return 0.0
    return 1.0 / len(winners)


def _single_or_joined(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values)


def _format_optional(value: float | None, digits: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _nested_number(payload: dict[str, Any], key: str) -> float | None:
    value = _nested_value(payload, key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _nested_value(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]
    base_summary = payload.get("base_decision_summary")
    if isinstance(base_summary, dict) and key in base_summary:
        return base_summary[key]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", help="Path(s) to batch_manifest.json files.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args()

    comparison = compare_batch_manifests(args.manifests)
    if args.json:
        print(json.dumps(comparison, indent=2, sort_keys=True))
    else:
        print(render_markdown_report(comparison), end="")


if __name__ == "__main__":
    main()
