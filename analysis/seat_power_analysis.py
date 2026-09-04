"""How large a seat effect can this design actually detect?

Why this exists
---------------
Four apparent seat findings have now dissolved under scrutiny. The recurring
question — "how many games would settle it?" — was answered by hand-waving
("several hundred") rather than from the measured variance.

This computes it from artifacts. The estimator in `seat_effect_paired.py` is a
one-sample t-test on within-agent seat deltas, so the relevant spread is the
standard deviation of those deltas, not of raw scores. Pairing removes a large
share of the noise and the two differ by roughly 40%; using the raw figure
overstates the games needed.

The second output matters more than the first. A study powered only for effects
far larger than the ones in play does not merely miss real effects — when it
does reach significance, the estimate is inflated, because only an unusually
large sample fluctuation could have crossed the threshold. That is why a 60-game
run reported +3.24 points and a fuller look put the effect near zero.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from statistics import stdev

from seat_effect_paired import build_paired_units, load_games

#: Two-sided 5% test at 80% power: (z(0.975) + z(0.80))^2.
Z_SUM_SQUARED = (1.959964 + 0.841621) ** 2

DEFAULT_EFFECTS = (1.0, 2.0, 3.0, 5.0)


def required_games(delta_sd: float, effect: float) -> int:
    """Paired units needed to detect `effect` points at 80% power, alpha 0.05."""

    if effect <= 0:
        return 0
    return math.ceil(Z_SUM_SQUARED * delta_sd**2 / effect**2)


def minimum_detectable_effect(delta_sd: float, games: int) -> float:
    """Smallest effect this many paired units can detect at 80% power."""

    if games <= 0:
        return float("inf")
    return delta_sd * (Z_SUM_SQUARED / games) ** 0.5


def analyse(artifact_root: Path, label_filter: str, effects: tuple[float, ...]) -> str:
    units = build_paired_units(load_games(artifact_root, label_filter))
    if not units:
        return "no complete paired units found"

    by_count: dict[int, list] = defaultdict(list)
    for unit in units:
        by_count[unit.player_count].append(unit)

    lines = ["# Seat-Effect Power Analysis", ""]
    for player_count, group in sorted(by_count.items()):
        deltas = [
            unit.delta_for(seat)
            for seat in range(player_count)
            for unit in group
            if seat in unit.scores
        ]
        per_seat = len(group)
        delta_sd = stdev(deltas)
        raw_sd = stdev([s for unit in group for s in unit.scores.values()])
        observed = minimum_detectable_effect(delta_sd, per_seat)

        lines += [
            f"## {player_count} players",
            "",
            f"- Paired units per seat: **{per_seat}**",
            f"- Raw per-game score SD: {raw_sd:.2f}",
            f"- Paired seat-delta SD: **{delta_sd:.2f}** "
            f"(pairing removes {100 * (1 - delta_sd / raw_sd):.0f}% of the spread)",
            f"- Smallest effect detectable at this sample size: **{observed:.2f} points**",
            "",
            "| Effect to detect | Paired units needed |",
            "|---:|---:|",
        ]
        for effect in effects:
            needed = required_games(delta_sd, effect)
            marker = "" if needed <= per_seat else "  <- beyond current run"
            lines.append(f"| {effect:.1f} points | {needed}{marker} |")
        lines += [
            "",
            f"> Anything below {observed:.2f} points cannot be reliably detected here. A "
            "'significant' result smaller than that is more likely an inflated estimate "
            "than a real effect.",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--label", default="")
    parser.add_argument("--effects", type=float, nargs="*", default=list(DEFAULT_EFFECTS))
    args = parser.parse_args()
    print(analyse(args.artifact_root, args.label, tuple(args.effects)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
