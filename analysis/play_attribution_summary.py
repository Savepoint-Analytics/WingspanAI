"""Aggregate the counterfactual play attribution: card value, timing value, context lift.

Reads the rows written by ``play_counterfactuals.py`` and answers, from the
plays that actually happened:

- how much a play is worth on average, and how much of that is immediate;
- per bird, its card value and timing value across contexts;
- per bird, how its card value moves when a given partner is already on the
  board ("context lift"), which is the observed counterpart of the
  rules-computed synergy bench; and the same at the mechanic level (power
  handler key), where the data is dense enough to read;
- agreement between observed lift and the bench's synergy where both exist.

    python analysis/play_attribution_summary.py artifacts/play_counterfactuals/pp_shard*.jsonl \\
        --bench artifacts/synergy_bench/synergy_bench.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.power_registry import classify_power_handler_key


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open() as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def se(values: list[float]) -> float:
    return stdev(values) / math.sqrt(len(values)) if len(values) > 1 else float("nan")


def mechanics(catalog) -> dict[str, str]:
    """Bird name → power handler key (``none`` for power-less birds)."""

    keys = {}
    for card in catalog.birds:
        if card.power.color.value == "none" or not card.power.text:
            keys[card.common_name] = "none"
        else:
            keys[card.common_name] = card.power.handler_key or classify_power_handler_key(
                card.power.text, card.power.color
            )
    return keys


def report(rows: list[dict], *, bench: dict | None, catalog, min_n: int, top: int) -> str:
    keys = mechanics(catalog)
    card = [r["card_advantage"] for r in rows]
    timing = [r["timing_advantage"] for r in rows]
    immediate = [r["immediate_delta"] for r in rows]
    lines = ["# Play attribution summary (counterfactual rollouts)", ""]
    lines.append(
        f"Plays: {len(rows)} over {len({r['game_id'] for r in rows})} games. "
        f"Mean card value **{mean(card):+.2f}** (SE {se(card):.2f}), of which immediate "
        f"{mean(immediate):+.2f}; mean timing value **{mean(timing):+.2f}** (SE {se(timing):.2f})."
    )
    by_round: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_round[r["round"]].append(r)
    lines += [
        "",
        "| Round | plays | card value | immediate | downstream | timing value |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for rnd in sorted(by_round):
        rs = by_round[rnd]
        c = mean(r["card_advantage"] for r in rs)
        i = mean(r["immediate_delta"] for r in rs)
        lines.append(
            f"| {rnd} | {len(rs)} | {c:+.2f} | {i:+.2f} | {c - i:+.2f} | "
            f"{mean(r['timing_advantage'] for r in rs):+.2f} |"
        )

    per_bird: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        per_bird[r["bird"]].append(r)
    eligible = {b: rs for b, rs in per_bird.items() if len(rs) >= min_n}
    ranked = sorted(eligible, key=lambda b: -mean(r["card_advantage"] for r in eligible[b]))
    lines += [
        "",
        f"## Per bird (≥{min_n} plays): card value, timing value, and what it did",
        "",
        "| Bird | n | card value | SE | immediate | timing | activations | eggs | cache | tuck |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def bird_line(b: str) -> str:
        rs = eligible[b]
        c = [r["card_advantage"] for r in rs]
        led = [r["ledger_at_end"] for r in rs if r["ledger_at_end"]]
        act = mean(x["activations"] for x in led) if led else float("nan")
        eggs = mean(x["eggs"] for x in led) if led else float("nan")
        cache = mean(x["cached_food"] for x in led) if led else float("nan")
        tuck = mean(x["tucked_cards"] for x in led) if led else float("nan")
        return (
            f"| {b} | {len(rs)} | {mean(c):+.2f} | {se(c):.2f} | "
            f"{mean(r['immediate_delta'] for r in rs):+.2f} | "
            f"{mean(r['timing_advantage'] for r in rs):+.2f} | {act:.1f} | {eggs:.1f} | "
            f"{cache:.1f} | {tuck:.1f} |"
        )

    lines.extend(bird_line(b) for b in ranked[:top])
    lines.append("| … | | | | | | | | | |")
    lines.extend(bird_line(b) for b in ranked[-top:])

    # Context lift: card value of X with partner Y on board, minus X's overall mean.
    lifts = []
    for b, rs in eligible.items():
        base = mean(r["card_advantage"] for r in rs)
        with_partner: dict[str, list[float]] = defaultdict(list)
        for r in rs:
            for partner in set(r["board_before"]):
                with_partner[partner].append(r["card_advantage"])
        for partner, vals in with_partner.items():
            if len(vals) >= min_n:
                lifts.append((b, partner, len(vals), mean(vals) - base))
    lifts.sort(key=lambda t: -t[3])
    lines += [
        "",
        f"## Context lift: card value of X when Y is already on the board (≥{min_n} cases)",
        "",
        "| Played X | With Y on board | n | lift |",
        "|---|---|---:|---:|",
    ]
    lines.extend(f"| {x} | {y} | {n} | {lift:+.2f} |" for x, y, n, lift in lifts[:top])
    lines.append("| … | | | |")
    lines.extend(f"| {x} | {y} | {n} | {lift:+.2f} |" for x, y, n, lift in lifts[-min(top, 8) :])

    # Mechanic-level lift: handler key of X × handler key present on board.
    mech_base: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        mech_base[keys.get(r["bird"], "unknown")].append(r["card_advantage"])
    mech_pairs: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        kx = keys.get(r["bird"], "unknown")
        for ky in {keys.get(p, "unknown") for p in r["board_before"]}:
            mech_pairs[(kx, ky)].append(r["card_advantage"])
    mech_lifts = [
        (kx, ky, len(v), mean(v) - mean(mech_base[kx]))
        for (kx, ky), v in mech_pairs.items()
        if len(v) >= 3 * min_n
    ]
    mech_lifts.sort(key=lambda t: -t[3])
    lines += [
        "",
        f"## Mechanic-level lift: played power × power already on board (≥{3 * min_n} cases)",
        "",
        "| Played power | With power on board | n | lift |",
        "|---|---|---:|---:|",
    ]
    lines.extend(f"| {kx} | {ky} | {n} | {lift:+.2f} |" for kx, ky, n, lift in mech_lifts[:top])
    lines.append("| … | | | |")
    lines.extend(
        f"| {kx} | {ky} | {n} | {lift:+.2f} |" for kx, ky, n, lift in mech_lifts[-min(top, 8) :]
    )

    if bench is not None:
        # Observed lift vs bench synergy for pairs the bench scored (either order).
        bench_pairs: dict[tuple[str, str], list[float]] = defaultdict(list)
        for habitat_pairs in bench["pairs"].values():
            for p in habitat_pairs.values():
                bench_pairs[(p["left"], p["right"])].append(p["synergy_points"])
                bench_pairs[(p["right"], p["left"])].append(p["synergy_points"])
        xs, ys = [], []
        for x, y, _n, lift in lifts:
            if (x, y) in bench_pairs:
                xs.append(mean(bench_pairs[(x, y)]))
                ys.append(lift)
        if len(xs) >= 5:
            rho = _spearman(xs, ys)
            lines += [
                "",
                f"Observed context lift vs bench synergy over {len(xs)} pairs both scored: "
                f"Spearman **{rho:+.3f}**.",
            ]
            hits = sum(1 for x, y in zip(xs, ys, strict=True) if x > 0 and y > 0)
            positives = sum(1 for x in xs if x > 0)
            if positives:
                lines.append(
                    f"Of {positives} bench-positive pairs, {hits} show positive observed lift."
                )
    return "\n".join(lines) + "\n"


def _spearman(x: list[float], y: list[float]) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for rk, i in enumerate(order):
            r[i] = rk
        return r

    rx, ry = rank(x), rank(y)
    n = len(x)
    return 1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry, strict=True)) / (n * (n * n - 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("rows", nargs="+", type=Path)
    parser.add_argument("--bench", type=Path, default=None)
    parser.add_argument("--min-n", type=int, default=8)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    args = parser.parse_args(argv)
    rows = load_rows(args.rows)
    if not rows:
        print("No rows.")
        return 1
    bench = json.loads(args.bench.read_text()) if args.bench is not None else None
    catalog = load_base_game_content_catalog(args.workbook)
    print(report(rows, bench=bench, catalog=catalog, min_n=args.min_n, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
