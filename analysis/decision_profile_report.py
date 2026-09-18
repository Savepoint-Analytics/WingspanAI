"""Decision latency and value-per-millisecond report.

Reads ``agent_decision_summary`` events under one or more artifact roots and
reports, per agent kind (and per player count where several exist):

- decisions, mean / p50 / p90 / p95 / p99 / max latency, per-game total;
- latency by round;
- where the time goes — self-time share, count per decision and ms per call
  per profiled node — for games recorded with ``decision_profile`` (2026-09-17
  onward), plus cache hit rates where nodes report them;
- with ``--value-against BASELINE_ROOT``: the paired score delta (from
  ``arm_contrast``), the latency delta, and the resulting
  **points per extra second per decision** and per game, with a suggested
  class: keep (value, no cost), optimize (value at a cost), drop or gate (cost
  without value), and the per-node attribution of the extra time when both
  roots carry profiles.

Every arm the project has run recorded per-decision latency, so the value
side works on the whole archive; the node breakdown needs profiled runs.

    python analysis/decision_profile_report.py artifacts/rr_belief_opp
    python analysis/decision_profile_report.py artifacts/rr_synergy_board \\
        --value-against artifacts/rr_belief_opp
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import contrast, load_arm  # noqa: E402


def agent_kind(agent_id: str | None) -> str:
    if not agent_id:
        return "unknown"
    kind = agent_id.removeprefix("guardrailed_")
    return kind.rsplit("_p", 1)[0] if "_p" in kind else kind


def load_decisions(root: Path) -> list[dict]:
    rows: list[dict] = []
    for events_path in root.rglob("events.jsonl"):
        player_count = None
        with events_path.open() as handle:
            for line in handle:
                if '"simulation_run_started"' in line:
                    player_count = json.loads(line)["payload"].get("player_count")
                    continue
                if '"agent_decision_summary"' not in line:
                    continue
                event = json.loads(line)
                payload = event["payload"]
                rows.append(
                    {
                        "game": str(events_path.parent),
                        "agent": agent_kind(event.get("agent_id")),
                        "player_count": player_count,
                        "round": event.get("round_number"),
                        "ms": float(payload.get("action_selection_elapsed_ms", 0.0)),
                        "profile": payload.get("decision_profile"),
                    }
                )
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
    return ordered[index]


def latency_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Agent | players | decisions | mean ms | p50 | p90 | p95 | p99 | max | s/game |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    groups: dict[tuple[str, int | None], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["agent"], row["player_count"])].append(row)
    for (agent, players), group in sorted(
        groups.items(), key=lambda kv: -mean(r["ms"] for r in kv[1])
    ):
        ms = [r["ms"] for r in group]
        games = len({r["game"] for r in group})
        lines.append(
            f"| `{agent}` | {players} | {len(ms)} | {mean(ms):.1f} | "
            f"{percentile(ms, 0.5):.1f} | {percentile(ms, 0.9):.1f} | "
            f"{percentile(ms, 0.95):.1f} | {percentile(ms, 0.99):.1f} | "
            f"{max(ms):.1f} | {sum(ms) / games / 1000:.1f} |"
        )
    return lines


def round_table(rows: list[dict], agent: str) -> list[str]:
    by_round: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if row["agent"] == agent and row["round"] is not None:
            by_round[row["round"]].append(row["ms"])
    if not by_round:
        return []
    lines = [
        f"Latency by round for `{agent}`: "
        + ", ".join(
            f"r{rnd} {mean(v):.0f} ms (p95 {percentile(v, 0.95):.0f})"
            for rnd, v in sorted(by_round.items())
        )
    ]
    return lines


def node_table(rows: list[dict], agent: str, top: int = 12) -> list[str]:
    profiled = [r for r in rows if r["agent"] == agent and r["profile"]]
    if not profiled:
        return [f"No decision profiles for `{agent}` under these roots (pre-2026-09-17 archive)."]
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"self_ms": 0.0, "count": 0, "hits": 0, "misses": 0}
    )
    total_ms = sum(r["profile"]["total_ms"] for r in profiled)
    unprofiled = sum(r["profile"].get("unprofiled_ms", 0.0) for r in profiled)
    for r in profiled:
        for name, node in r["profile"]["nodes"].items():
            entry = totals[name]
            entry["self_ms"] += node["self_ms"]
            entry["count"] += node["count"]
            entry["hits"] += node.get("cache_hits", 0)
            entry["misses"] += node.get("cache_misses", 0)
    lines = [
        f"Where `{agent}`'s time goes ({len(profiled)} profiled decisions, "
        f"{unprofiled / max(total_ms, 1e-9):.1%} unprofiled):",
        "",
        "| Node | share | ms/decision | calls/decision | ms/call | cache hit rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(totals.items(), key=lambda kv: -kv[1]["self_ms"])[:top]
    n = len(profiled)
    for name, entry in ranked:
        calls = entry["count"]
        hit_rate = (
            f"{entry['hits'] / (entry['hits'] + entry['misses']):.0%}"
            if entry["hits"] + entry["misses"]
            else "—"
        )
        lines.append(
            f"| `{name}` | {entry['self_ms'] / max(total_ms, 1e-9):.1%} | "
            f"{entry['self_ms'] / n:.1f} | {calls / n:.0f} | "
            f"{(entry['self_ms'] / calls if calls else 0):.3f} | {hit_rate} |"
        )
    return lines


def classify(score_delta: float, score_p: float, latency_ratio: float) -> str:
    significant_gain = score_delta > 0 and score_p < 0.05
    significant_loss = score_delta < 0 and score_p < 0.05
    if significant_loss:
        return "drop"
    if significant_gain and latency_ratio <= 1.2:
        return "keep"
    if significant_gain:
        return "optimize"
    if latency_ratio > 1.2:
        return "drop or gate"
    if latency_ratio < 0.8:
        return "keep (cheaper, no measured loss)"
    return "no measured value; cost neutral"


def value_section(
    arm_root: Path, baseline_root: Path, arm_rows: list[dict], agent: str
) -> list[str]:
    base_rows = load_decisions(baseline_root)
    base_ms = [r["ms"] for r in base_rows if r["agent"] == agent]
    arm_ms = [r["ms"] for r in arm_rows if r["agent"] == agent]
    if not base_ms or not arm_ms:
        return [f"No `{agent}` decisions in both roots."]
    result = contrast(load_arm(baseline_root), load_arm(arm_root), agent)
    delta = result["score_delta"]
    p = result["score_p"]
    base_mean, arm_mean = mean(base_ms), mean(arm_ms)
    extra_ms = arm_mean - base_mean
    base_games = len({r["game"] for r in base_rows if r["agent"] == agent})
    arm_games = len({r["game"] for r in arm_rows if r["agent"] == agent})
    per_game_base = sum(base_ms) / base_games / 1000
    per_game_arm = sum(arm_ms) / arm_games / 1000
    ratio = arm_mean / base_mean if base_mean else float("inf")
    lines = [
        f"## Value per millisecond: `{arm_root}` vs `{baseline_root}` for `{agent}`",
        "",
        f"- Paired score Δ **{delta:+.2f}** (p = {p:.3f}) over {result['n']} games",
        f"- Mean decision {base_mean:.0f} → {arm_mean:.0f} ms (×{ratio:.2f}); "
        f"per game {per_game_base:.0f} → {per_game_arm:.0f} s",
    ]
    extra_s_game = per_game_arm - per_game_base
    if abs(extra_ms) >= 50:
        per_second = delta / (extra_ms / 1000)
        direction = "extra" if extra_ms > 0 else "saved"
        lines.append(
            f"- **{per_second:+.2f} points per second {direction} per decision** "
            f"({delta / extra_s_game:+.3f} points per second {direction} per game)"
        )
    else:
        lines.append("- Latency unchanged within 50 ms per decision; value per ms not defined")
    lines.append(f"- Suggested class: **{classify(delta, p, ratio)}**")
    lines.append(
        "- Caveat: latencies are wall-clock on a shared machine; arms run under "
        "different load are not directly comparable. Back-to-back probes are the clean measure."
    )

    # Node attribution of the latency delta, when both sides carry profiles.
    def node_means(rows: list[dict]) -> dict[str, float]:
        profiled = [r for r in rows if r["agent"] == agent and r["profile"]]
        if not profiled:
            return {}
        acc: dict[str, float] = defaultdict(float)
        for r in profiled:
            for name, node in r["profile"]["nodes"].items():
                acc[name] += node["self_ms"]
        return {name: total / len(profiled) for name, total in acc.items()}

    base_nodes, arm_nodes = node_means(base_rows), node_means(arm_rows)
    if base_nodes and arm_nodes:
        names = sorted(
            set(base_nodes) | set(arm_nodes),
            key=lambda n: -(arm_nodes.get(n, 0) - base_nodes.get(n, 0)),
        )
        lines += [
            "",
            "| Node | baseline ms/decision | arm ms/decision | Δ |",
            "|---|---:|---:|---:|",
        ]
        for name in names[:10]:
            b, a = base_nodes.get(name, 0.0), arm_nodes.get(name, 0.0)
            lines.append(f"| `{name}` | {b:.1f} | {a:.1f} | {a - b:+.1f} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument(
        "--agent", default="potential_points", help="agent for the node and value sections"
    )
    parser.add_argument("--value-against", type=Path, default=None, metavar="BASELINE_ROOT")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args(argv)
    rows = [row for root in args.roots for row in load_decisions(root)]
    if not rows:
        print("No decisions found.")
        return 1
    lines = ["# Decision latency report", "", f"Roots: {', '.join(str(r) for r in args.roots)}", ""]
    lines += latency_table(rows)
    lines += ["", *round_table(rows, args.agent), "", *node_table(rows, args.agent, top=args.top)]
    if args.value_against is not None:
        if len(args.roots) != 1:
            print("--value-against needs exactly one arm root.")
            return 1
        lines += ["", *value_section(args.roots[0], args.value_against, rows, args.agent)]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
