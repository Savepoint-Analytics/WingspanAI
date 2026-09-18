"""Write the end-of-game type posterior the belief model reaches for each opponent kind.

The oracle-type search opponent model (``search_opponent_model="oracle"``)
starts every game already holding, for each opponent seat, the posterior
the belief model converges to for that agent kind after a full game of
observation — perfect type knowledge *within the model's own type space*,
known from turn one instead of learned over 25 observations. This script
computes that table from archived default-agent games: for every
``potential_points`` seat, the last recorded ``opponent_belief_states`` per
opponent, averaged by the opponent's agent kind.

The table is also a calibration finding in its own right: which nominal
profile each roster agent actually looks like to the model.

    python analysis/oracle_type_posteriors.py artifacts/rr_belief_opp \\
        --out configs/belief/oracle_type_posteriors.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


def agent_kind(agent_id: str) -> str:
    kind = agent_id.removeprefix("guardrailed_")
    return kind.rsplit("_p", 1)[0] if "_p" in kind else kind


def collect(roots: list[Path]) -> tuple[dict[str, dict[str, float]], Counter, dict[str, float]]:
    sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    games: Counter = Counter()
    observations: dict[str, float] = defaultdict(float)
    for root in roots:
        for events_path in root.rglob("events.jsonl"):
            kinds: dict[str, str] = {}
            last: dict[str, dict] = {}
            with events_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if '"agent_decision_summary"' not in line:
                        continue
                    event = json.loads(line)
                    if event.get("player_id") and event.get("agent_id"):
                        kinds[event["player_id"]] = event["agent_id"]
                    model = event["payload"].get("opponent_model")
                    if not isinstance(model, dict) or "opponent_belief_states" not in model:
                        continue
                    for player_id, belief in model["opponent_belief_states"].items():
                        last[player_id] = belief
            for player_id, belief in last.items():
                kind = agent_kind(kinds.get(player_id, player_id))
                games[kind] += 1
                observations[kind] += belief["observation_count"]
                for profile, probability in belief["profile_posterior"].items():
                    sums[kind][profile] += probability
    table = {}
    for kind, totals in sums.items():
        mass = sum(totals.values())
        table[kind] = {
            p: round(v / mass, 4) for p, v in sorted(totals.items(), key=lambda kv: -kv[1])
        }
    return table, games, {k: v / games[k] for k, v in observations.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument(
        "--out", type=Path, default=Path("configs/belief/oracle_type_posteriors.json")
    )
    args = parser.parse_args(argv)
    table, games, observations = collect(args.roots)
    if not table:
        print("No belief telemetry found.")
        return 1
    payload = {
        "version": "oracle_type_posteriors_v1",
        "source": f"end-of-game opponent_belief_states of potential_points seats in "
        f"{', '.join(str(r) for r in args.roots)}, averaged by opponent agent kind",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "games_by_kind": dict(sorted(games.items())),
        "mean_observations_by_kind": {k: round(v, 1) for k, v in sorted(observations.items())},
        "posteriors": dict(sorted(table.items())),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for kind, posterior in payload["posteriors"].items():
        top = list(posterior.items())[:2]
        print(f"{kind} ({games[kind]} games): " + ", ".join(f"{p} {v:.2f}" for p, v in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
