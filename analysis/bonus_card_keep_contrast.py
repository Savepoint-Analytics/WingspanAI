"""Value of keeping each bonus card, from the forced-keep paired arms.

Two arms share every seed: arm A forces the study agent to keep the first
dealt bonus card, arm B the second. Everything else in the game is identical
by construction (ADR 0003), so ``score_A - score_B`` is the value of keeping
card A over card B on that deal, with deck, opponent and seat luck differenced
out. Each seed therefore contributes one paired unit to each of its two cards:
``+delta`` to the card kept in A, ``-delta`` to the card kept in B.

Reported per card: how many deals it appeared in, its mean advantage over the
cards it was dealt alongside, a paired-t p-value, the bonus points it actually
scored when kept, and how often it scored anything at all. Plus, across all
deals: how much the keep choice is worth in absolute terms, and how often the
study agent's own opening policy would have picked the better side, computed
from the dealt hand without running any extra games.

    python analysis/bonus_card_keep_contrast.py \\
        --arm-a artifacts/bonus_keep/force0 --arm-b artifacts/bonus_keep/force1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import GameKey, agent_result, load_arm, paired_test  # noqa: E402

AGENT = "potential_points"


@dataclass(frozen=True)
class KeepObservation:
    seed: int
    lineup: tuple[str, ...]
    kept: str
    discarded: str
    score: float
    win: float
    bonus_points: int


def read_keep(game: dict, agent: str) -> KeepObservation | None:
    """What the study agent kept and scored in one game, from its artifacts."""

    artifact_dir = game.get("artifact_dir")
    if not artifact_dir:
        return None
    events_path = Path(artifact_dir) / "events.jsonl"
    if not events_path.exists():
        return None
    result = agent_result(game, agent)
    if result is None:
        return None
    lineup = game["player_agent_kinds"]
    seat = (lineup.index(agent) - game["seat_rotation"]) % game["player_count"]
    player_id = f"player_{seat + 1}"
    kept = discarded = None
    bonus_points = 0
    with events_path.open() as handle:
        for line in handle:
            event = json.loads(line)
            name = event.get("event_name")
            payload = event.get("payload", {})
            if name == "setup_selection_applied" and payload.get("player_id") == player_id:
                kept = payload["kept_bonus_card_names"][0]
                discarded_names = payload.get("discarded_bonus_card_names", [])
                discarded = discarded_names[0] if discarded_names else None
            elif name == "game_ended":
                breakdown = payload.get("score_breakdowns", {}).get(player_id, {})
                bonus_points = int(breakdown.get("bonus_points", 0))
    if kept is None or discarded is None:
        return None
    return KeepObservation(
        seed=game["outcome"]["random_seed"],
        lineup=tuple(lineup),
        kept=kept,
        discarded=discarded,
        score=result[0],
        win=result[1],
        bonus_points=bonus_points,
    )


def pair_arms(
    arm_a: dict[GameKey, dict], arm_b: dict[GameKey, dict], agent: str
) -> list[tuple[KeepObservation, KeepObservation]]:
    pairs = []
    for key in sorted(arm_a, key=lambda k: (k.lineup, k.rotation, k.seed)):
        if key not in arm_b or agent not in key.lineup:
            continue
        a = read_keep(arm_a[key], agent)
        b = read_keep(arm_b[key], agent)
        if a is None or b is None:
            continue
        if {a.kept, a.discarded} != {b.kept, b.discarded} or a.kept == b.kept:
            # Not a forced pair on the same deal; skip rather than mis-attribute.
            continue
        pairs.append((a, b))
    return pairs


def policy_choices(seeds: list[int], player_count: int, workbook: Path | None) -> dict[int, str]:
    """Which card the study agent's own opening policy keeps on each deal.

    Reconstructs the dealt state from the seed alone and asks the policy with
    the same context the runner gives it, so no extra games are needed.
    """

    from wingspan_ai.agents.setup import PotentialPointsSetupPolicy
    from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
    from wingspan_ai.rules.base_game import setup_base_game
    from wingspan_ai.simulation.runner import _initial_selection_context

    catalog = load_base_game_content_catalog(workbook or DEFAULT_WORKBOOK_PATH)
    policy = PotentialPointsSetupPolicy()
    choices: dict[int, str] = {}
    for seed in seeds:
        state = setup_base_game(
            catalog,
            player_ids=[f"player_{i + 1}" for i in range(player_count)],
            random_seed=seed,
            apply_initial_selection=False,
        )
        selection = policy.choose_initial_selection(
            state.players[0], _initial_selection_context(state)
        )
        choices[seed] = selection.kept_bonus_card_names[0]
    return choices


def report(
    pairs: list[tuple[KeepObservation, KeepObservation]],
    *,
    hindsight: dict[int, str] | None = None,
) -> str:
    per_card_delta: dict[str, list[float]] = defaultdict(list)
    per_card_bonus: dict[str, list[int]] = defaultdict(list)
    per_card_win: dict[str, list[float]] = defaultdict(list)
    deltas = []
    for a, b in pairs:
        delta = a.score - b.score
        deltas.append(delta)
        per_card_delta[a.kept].append(delta)
        per_card_delta[b.kept].append(-delta)
        per_card_bonus[a.kept].append(a.bonus_points)
        per_card_bonus[b.kept].append(b.bonus_points)
        per_card_win[a.kept].append(a.win - b.win)
        per_card_win[b.kept].append(b.win - a.win)

    lines = ["# Bonus-card keep value (forced-keep paired arms)", ""]
    lines.append(f"Paired deals: {len(pairs)}; distinct cards: {len(per_card_delta)}")
    if deltas:
        abs_mean = mean(abs(d) for d in deltas)
        big = sum(1 for d in deltas if abs(d) >= 5)
        lines.append(
            f"Mean |keep A − keep B|: **{abs_mean:.2f} points**; "
            f"{big} of {len(deltas)} deals swing 5+ points."
        )
    if hindsight:
        judged = 0
        right = 0
        for a, b in pairs:
            choice = hindsight.get(a.seed)
            if choice is None or a.score == b.score:
                continue
            judged += 1
            better = a.kept if a.score > b.score else b.kept
            right += choice == better
        if judged:
            lines.append(
                f"Study agent's own opening policy picked the better keep on "
                f"**{right} of {judged}** decided deals ({right / judged:.0%})."
            )
    lines += [
        "",
        "| Card | n | Mean advantage | p | Win Δ | Bonus pts when kept | Scored ≥1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(per_card_delta, key=lambda name: -mean(per_card_delta[name]))
    for name in ranked:
        d = per_card_delta[name]
        adv, p = paired_test(d)
        win = mean(per_card_win[name])
        bonus = per_card_bonus[name]
        scored = sum(1 for value in bonus if value > 0) / len(bonus)
        lines.append(
            f"| {name} | {len(d)} | {adv:+.2f} | {p:.3f} | {win:+.3f} | "
            f"{mean(bonus):.2f} | {scored:.0%} |"
        )
    lines += [
        "",
        "Advantage is the card's mean paired score margin over whichever card it was",
        "dealt alongside, so it is relative to the field of partners it drew, not an",
        "absolute point value. A card that only ever appears next to strong partners",
        "is under-rated by this column and over-rated by its bonus points.",
    ]
    if per_card_delta:
        smallest = min(len(v) for v in per_card_delta.values())
        if smallest < 8:
            lines.append(
                f"\n**Thinnest card has {smallest} paired units**; per-card p-values below "
                "8 units are not worth quoting."
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arm-a", type=Path, required=True, help="forced index 0 root")
    parser.add_argument("--arm-b", type=Path, required=True, help="forced index 1 root")
    parser.add_argument("--agent", default=AGENT)
    parser.add_argument("--no-hindsight", action="store_true")
    parser.add_argument("--workbook", type=Path, default=None)
    args = parser.parse_args(argv)
    pairs = pair_arms(load_arm(args.arm_a), load_arm(args.arm_b), args.agent)
    if not pairs:
        print("No forced-keep pairs found.")
        return 1
    hindsight = None
    if not args.no_hindsight:
        player_count = len(pairs[0][0].lineup)
        hindsight = policy_choices(sorted({a.seed for a, _ in pairs}), player_count, args.workbook)
    print(report(pairs, hindsight=hindsight))
    return 0


if __name__ == "__main__":
    sys.exit(main())
