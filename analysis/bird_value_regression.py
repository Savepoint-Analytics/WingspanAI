"""Observational bird value: points per appearance, from every archived game.

Layer 2 of the bird-value study (``docs/experiments/bonus_card_selection_study_plan.md``
§5). For every (game, player) under the given artifact roots, the row is the
player's final score and a 0/1 indicator per bird they played, plus a fixed
effect per agent kind so a bird favoured by a strong agent is not credited
with that agent's strength. A ridge regression then gives each bird a
coefficient: the points a game's final score moves when this bird is on the
board, holding the agent constant.

Where games carry ``bird_scorecard`` events (emitted since 2026-09-16), the
report also shows what each bird actually held at game end — eggs, cached
food, tucked cards, power activations — and the round it was played.

This is observational. Agents choose birds they like and play strong birds
early, so the coefficient mixes the bird's worth with the situations that
produce it. It is broad and free, which is its job; the causal layer is the
forced-keep design.

    python analysis/bird_value_regression.py artifacts --min-appearances 20 --top 25
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

NEEDED = ('"action_resolved"', '"game_ended"', '"setup_selection_applied"', '"bird_scorecard"')


def agent_kind(agent_id: str | None) -> str:
    if not agent_id:
        return "unknown"
    kind = agent_id.removeprefix("guardrailed_")
    return kind.rsplit("_p", 1)[0] if "_p" in kind else kind


def load_rows(roots: list[Path]) -> tuple[list[dict], dict[str, list[dict]]]:
    """One row per (game, player); plus per-bird scorecard entries where present."""

    rows: list[dict] = []
    scorecards: dict[str, list[dict]] = defaultdict(list)
    for root in roots:
        for events_path in root.rglob("events.jsonl"):
            birds: dict[str, set[str]] = defaultdict(set)
            agents: dict[str, str] = {}
            scores: dict[str, float] = {}
            with events_path.open() as handle:
                for line in handle:
                    if not any(marker in line for marker in NEEDED):
                        continue
                    event = json.loads(line)
                    name = event.get("event_name")
                    payload = event.get("payload", {})
                    if name == "action_resolved":
                        action = payload.get("action", {})
                        if action.get("action_type") == "play_bird" and action.get(
                            "bird_common_name"
                        ):
                            birds[payload["acting_player_id"]].add(action["bird_common_name"])
                    elif name == "setup_selection_applied":
                        agents[payload["player_id"]] = payload.get("agent_id")
                    elif name == "game_ended":
                        for player_id, score in (
                            payload.get("outcome", {}).get("scores", {}).items()
                        ):
                            scores[player_id] = float(score)
                    elif name == "bird_scorecard":
                        for bird in payload.get("birds", []):
                            scorecards[bird["common_name"]].append(bird)
            if not scores:
                continue
            for player_id, score in scores.items():
                rows.append(
                    {
                        "score": score,
                        "agent_kind": agent_kind(agents.get(player_id)),
                        "birds": birds.get(player_id, set()),
                    }
                )
    return rows, scorecards


def ridge(rows: list[dict], *, min_appearances: int, penalty: float) -> dict:
    appearances = Counter(bird for row in rows for bird in row["birds"])
    birds = sorted(b for b, n in appearances.items() if n >= min_appearances)
    kinds = sorted({row["agent_kind"] for row in rows})
    columns = ["intercept"] + [f"agent:{k}" for k in kinds[1:]] + birds
    index = {name: i for i, name in enumerate(columns)}
    p = len(columns)
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row in rows:
        active = [0]
        if row["agent_kind"] != kinds[0]:
            active.append(index[f"agent:{row['agent_kind']}"])
        active.extend(index[b] for b in row["birds"] if b in index)
        y = row["score"]
        for i in active:
            xty[i] += y
            for j in active:
                xtx[i][j] += 1.0
    # Penalize bird coefficients only; the intercept and agent effects are free.
    for bird in birds:
        i = index[bird]
        xtx[i][i] += penalty
    beta = _solve(xtx, xty)
    weight = sum(appearances[b] for b in birds)
    average = sum(beta[index[b]] * appearances[b] for b in birds) / weight if weight else 0.0
    return {
        "coefficients": {name: beta[index[name]] for name in columns},
        "average_bird": average,
        "appearances": appearances,
        "birds": birds,
        "rows": len(rows),
        "reference_agent": kinds[0],
    }


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting; sizes here are a few hundred."""

    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            continue
        m[col], m[pivot] = m[pivot], m[col]
        pivot_row = m[col]
        inv = 1.0 / pivot_row[col]
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col] * inv
            if factor == 0.0:
                continue
            row = m[r]
            for c in range(col, n + 1):
                row[c] -= factor * pivot_row[c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0 for i in range(n)]


def report(fit: dict, scorecards: dict[str, list[dict]], *, top: int) -> str:
    coefs = fit["coefficients"]
    ranked = sorted(fit["birds"], key=lambda b: -coefs[b])
    # Playing any bird is worth points, so every coefficient is positive; the
    # comparison that matters is against the appearance-weighted average bird.
    average = fit["average_bird"]
    lines = [
        "# Bird value, observational (ridge on birds played, agent fixed effects)",
        "",
        f"Rows (game × player): {fit['rows']}; birds with enough appearances: "
        f"{len(fit['birds'])}; reference agent: `{fit['reference_agent']}`.",
        "",
        "Coefficient = points the final score moves when the bird is on the board,",
        "holding agent kind constant. Scorecard columns are means over games that",
        "recorded them (2026-09-16 onward) and are blank otherwise.",
        "",
        f"Average bird (appearance-weighted): {average:+.2f}.",
        "",
        "| Bird | n | Coefficient | vs avg bird | Eggs | Cached | Tucked | Activations | "
        "Round played |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def row(bird: str) -> str:
        cards = scorecards.get(bird, [])
        extra = (
            f"{mean(c['eggs'] for c in cards):.1f} | {mean(c['cached_food'] for c in cards):.1f} | "
            f"{mean(c['tucked_cards'] for c in cards):.1f} | "
            f"{mean(c['activations'] for c in cards):.1f} | "
            f"{mean(c['round_played'] for c in cards if c['round_played'] is not None):.1f}"
            if cards and any(c["round_played"] is not None for c in cards)
            else " |  |  |  | "
        )
        return (
            f"| {bird} | {fit['appearances'][bird]} | {coefs[bird]:+.2f} | "
            f"{coefs[bird] - average:+.2f} | {extra} |"
        )

    lines.extend(row(b) for b in ranked[:top])
    lines.append("| … | | | | | | | | |")
    lines.extend(row(b) for b in ranked[-top:])
    agent_effects = {k: v for k, v in coefs.items() if k.startswith("agent:")}
    lines += ["", "Agent fixed effects (vs reference): "]
    lines.append(
        ", ".join(
            f"`{k.removeprefix('agent:')}` {v:+.1f}" for k, v in sorted(agent_effects.items())
        )
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--min-appearances", type=int, default=20)
    parser.add_argument("--penalty", type=float, default=5.0)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--json", type=Path, default=None, help="write coefficients here")
    args = parser.parse_args(argv)
    rows, scorecards = load_rows(args.roots)
    if not rows:
        print("No games found.")
        return 1
    fit = ridge(rows, min_appearances=args.min_appearances, penalty=args.penalty)
    print(report(fit, scorecards, top=args.top))
    if args.json is not None:
        args.json.write_text(
            json.dumps(
                {
                    "rows": fit["rows"],
                    "penalty": args.penalty,
                    "min_appearances": args.min_appearances,
                    "coefficients": {b: fit["coefficients"][b] for b in fit["birds"]},
                    "average_bird": fit["average_bird"],
                    "appearances": {b: fit["appearances"][b] for b in fit["birds"]},
                },
                indent=1,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
