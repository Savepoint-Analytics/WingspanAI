"""Standing controls: games where a decided switch kept its losing side.

Every arm the project adopts or drops keeps its other side alive in a
deterministic minority of games (``agents/holdout.py``; the registry is
``docs/experiments/standing_holdouts.md``). The first was the search opponent
model (2026-09-16: ``belief`` default, 5% keep ``greedy``); since 2026-09-17
the mechanism is generic and every ``PotentialPointsSearchConfig`` field can
carry a holdout. Held-out games accumulate across every batch that runs with
the defaults, which turns each decision into a long-run experiment: a
false-positive drop, or a later change (an agent learning from past games,
say) that drifts in a way only the default sees, shows up here.

The comparison is unpaired — held-out games are different games, not
re-runs — so it needs many more games than an arm contrast to say anything,
and it says so. Pool every root you want counted:

    python analysis/holdout_guardrail.py artifacts/rr_belief_opp artifacts/rr_next_arm ...
    python analysis/holdout_guardrail.py artifacts/* --field search_child_expansion
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import agent_result  # noqa: E402

AGENT = "potential_points"


def load_games(roots: list[Path]) -> list[dict]:
    games: list[dict] = []
    for root in roots:
        for manifest_path in sorted(root.rglob("batch_manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for game in manifest.get("games", []):
                has_record = "search_holdouts" in game or "search_opponent_models" in game
                if has_record and "player_agent_kinds" in game:
                    games.append(game)
    return games


def split_by_model(games: list[dict]) -> dict[str, list[tuple[float, float, str]]]:
    """``{model: [(score, win, opponents), ...]}`` over every potential_points seat."""

    return split_by_field(games, "search_opponent_model")


def _seat_entry(game: dict) -> dict | None:
    """Effective fields and applied holdouts for the potential_points seat, any manifest vintage."""

    holdouts = game.get("search_holdouts") or {}
    entries = [e for aid, e in holdouts.items() if aid.startswith(AGENT)]
    if len(entries) == 1:
        return entries[0]
    models = game.get("search_opponent_models") or {}
    legacy = [e for aid, e in models.items() if aid.startswith(AGENT)]
    if len(legacy) == 1:
        return {
            "applied": ["search_opponent_model"] if legacy[0]["holdout"] else [],
            "effective": {"search_opponent_model": legacy[0]["model"]},
        }
    return None


def holdout_fields(games: list[dict]) -> list[str]:
    fields: set[str] = set()
    for game in games:
        entry = _seat_entry(game)
        if entry:
            fields.update(entry["applied"])
    return sorted(fields)


def split_by_field(games: list[dict], field: str) -> dict[str, list[tuple[float, float, str]]]:
    """``{value: [(score, win, opponents), ...]}`` by the seat's effective value of ``field``."""

    rows: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for game in games:
        result = agent_result(game, AGENT)
        entry = _seat_entry(game)
        if result is None or entry is None or field not in entry["effective"]:
            continue
        opponents = "+".join(kind for kind in game["player_agent_kinds"] if kind != AGENT)
        rows[str(entry["effective"][field])].append((result[0], result[1], opponents))
    return rows


def welch(a: list[float], b: list[float]) -> tuple[float, float]:
    """(mean difference a - b, two-sided p) by Welch's t under a normal approximation."""

    if len(a) < 2 or len(b) < 2:
        return (mean(a) - mean(b)) if a and b else 0.0, 1.0
    var_a, var_b = stdev(a) ** 2, stdev(b) ** 2
    se = math.sqrt(var_a / len(a) + var_b / len(b))
    if se == 0:
        return mean(a) - mean(b), 1.0
    t = (mean(a) - mean(b)) / se
    return mean(a) - mean(b), math.erfc(abs(t) / math.sqrt(2))


def detectable_difference(a: list[float], b: list[float]) -> float | None:
    """Smallest score difference this sample would call significant at 80% power."""

    if len(a) < 2 or len(b) < 2:
        return None
    se = math.sqrt(stdev(a) ** 2 / len(a) + stdev(b) ** 2 / len(b))
    return (1.96 + 0.84) * se


def report(rows: dict[str, list[tuple[float, float, str]]], preferred: str = "belief") -> str:
    lines = ["Standing control: preferred value versus games held out to the losing side.", ""]
    lines.append("| Model | n | Avg score | Win rate |")
    lines.append("|---|---:|---:|---:|")
    for model in sorted(rows):
        scores = [row[0] for row in rows[model]]
        wins = [row[1] for row in rows[model]]
        lines.append(f"| `{model}` | {len(scores)} | {mean(scores):.2f} | {mean(wins):.3f} |")
    others = [model for model in rows if model != preferred]
    if preferred in rows and others:
        pref_scores = [row[0] for row in rows[preferred]]
        pref_wins = [row[1] for row in rows[preferred]]
        for model in others:
            held_scores = [row[0] for row in rows[model]]
            held_wins = [row[1] for row in rows[model]]
            score_delta, score_p = welch(pref_scores, held_scores)
            win_delta, win_p = welch(pref_wins, held_wins)
            lines += [
                "",
                f"## `{preferred}` minus `{model}` (unpaired)",
                "",
                f"- Score: **{score_delta:+.2f}** (p = {score_p:.3f})",
                f"- Win rate: **{win_delta:+.3f}** (p = {win_p:.3f})",
            ]
            limit = detectable_difference(pref_scores, held_scores)
            if limit is not None:
                lines.append(
                    f"- Detection limit at 80% power: about **{limit:.1f} points**; "
                    "differences below this are not resolvable at this sample."
                )
            if len(held_scores) < 40:
                lines.append(
                    f"- **{len(held_scores)} held-out games is too few to read.** "
                    "The guardrail accrues across batches; keep pooling roots."
                )
            by_opp: dict[str, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
            for score, _win, opp in rows[preferred]:
                by_opp[opp][0].append(score)
            for score, _win, opp in rows[model]:
                by_opp[opp][1].append(score)
            lines += [
                "",
                "| Opponent | n preferred | n held out | Δ score |",
                "|---|---:|---:|---:|",
            ]
            for opp in sorted(by_opp):
                pref, held = by_opp[opp]
                delta = (mean(pref) - mean(held)) if pref and held else float("nan")
                lines.append(f"| `{opp}` | {len(pref)} | {len(held)} | {delta:+.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path, help="artifact roots to pool")
    parser.add_argument(
        "--field",
        default=None,
        help="one held-out field to report; default: every field with a holdout in the roots",
    )
    parser.add_argument("--preferred", default=None, help="the default value (inferred if omitted)")
    args = parser.parse_args(argv)
    games = load_games(args.roots)
    if not games:
        print("No games with holdout records found under the given roots.")
        return 1
    fields = [args.field] if args.field else holdout_fields(games)
    if not fields:
        print("No holdouts applied in these roots.")
        return 1
    for field in fields:
        rows = split_by_field(games, field)
        # The preferred value is the one the non-held-out games carry.
        preferred = args.preferred
        if preferred is None:
            counts = {value: len(v) for value, v in rows.items()}
            preferred = max(counts, key=counts.get)
        print(f"# Holdout field `{field}`\n")
        print(report(rows, preferred=preferred))
    return 0


if __name__ == "__main__":
    sys.exit(main())
