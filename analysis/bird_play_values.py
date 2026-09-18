"""Write the per-bird play-value table the measured opener reads.

Source: the K=4 hierarchical play-attribution fit
(``analysis/r/play_attribution_hierarchical.R``), which gives each bird a
shrunken random effect around a round-1 intercept in final-score points.
``value = intercept + effect`` is the expected final-score gain of playing
the bird in round 1, shrunk toward the mean play for thinly observed birds;
birds never observed get the intercept.

    python analysis/bird_play_values.py \\
        --fit artifacts/play_counterfactuals/hierarchical_k4 \\
        --out configs/bird_values/bird_play_values_k4.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path


def build_table(fit_dir: Path, *, version: str, source: str) -> dict:
    fixed = {
        row["term"]: float(row["estimate"])
        for row in csv.DictReader((fit_dir / "fixed_effects.csv").open(encoding="utf-8"))
    }
    intercept = fixed["(Intercept)"]
    values = {}
    with (fit_dir / "bird_effects.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            effect = float(row["shrunken_effect"])
            values[row["bird"]] = {
                "value": round(intercept + effect, 3),
                "effect": round(effect, 3),
                "cond_sd": round(float(row["cond_sd"]), 3),
                "n": int(row["n"]),
            }
    return {
        "version": version,
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "unit": "final-score points from playing the bird in round 1 (K=4 counterfactual, "
        "lme4 shrunken bird effect + round-1 intercept); unlisted birds take the intercept",
        "intercept_round1": round(intercept, 3),
        "round_offsets": {k: round(v, 3) for k, v in fixed.items() if k != "(Intercept)"},
        "values": dict(sorted(values.items(), key=lambda kv: -kv[1]["value"])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--fit", type=Path, default=Path("artifacts/play_counterfactuals/hierarchical_k4")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("configs/bird_values/bird_play_values_k4.json")
    )
    parser.add_argument("--version", default="bird_play_values_k4")
    parser.add_argument(
        "--source",
        default="analysis/r/play_attribution_hierarchical.R on 2,698 counterfactual plays "
        "(K=4 continuations, 302 archived potential_points games), 2026-09-17",
    )
    args = parser.parse_args(argv)
    table = build_table(args.fit, version=args.version, source=args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    top = list(table["values"].items())[:5]
    print(
        f"{len(table['values'])} birds, intercept {table['intercept_round1']:+.2f}; top: "
        + ", ".join(f"{name} {entry['value']:+.1f}" for name, entry in top)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
