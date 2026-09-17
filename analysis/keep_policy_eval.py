"""Score opening bonus-card policies against the forced-keep arms without new games.

Each seed in the forced-keep study has two archived games: one per dealt
bonus card, with birds and food chosen by the study agent's own policy
conditional on that card. So any policy that changes *only* the bonus
choice can be evaluated exactly on those seeds: reconstruct the deal, ask
the policy which card it keeps, and read the score of the forced game that
kept it. That is a paired arm for free — the same seeds, the same opponent,
the same downstream play — with the caveat that a policy designed after
looking at these deals is being scored in sample on them. Score it on the
replication arms (a different study agent, different seeds) as well.

    python analysis/keep_policy_eval.py --arm-a artifacts/bonus_keep/force0 \\
        --arm-b artifacts/bonus_keep/force1 --study-agent potential_points
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import load_arm, paired_test  # noqa: E402
from analysis.bonus_card_keep_contrast import KeepObservation, pair_arms  # noqa: E402
from wingspan_ai.agents.setup import (  # noqa: E402
    InitialSelectionContext,
    PotentialPointsSetupPolicy,
)
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.rules.base_game import setup_base_game  # noqa: E402
from wingspan_ai.simulation.runner import _initial_selection_context  # noqa: E402

Chooser = Callable[[object, InitialSelectionContext], str]


def default_chooser(study_agent: str) -> Chooser:
    """The study agent's own opening policy, built the way the flow builds it."""

    from flows.simulation_batch import _make_agent

    agent = _make_agent(study_agent, seat="p1", random_seed=0)
    policy = agent.setup_policy

    def choose(player, context):
        return policy.choose_initial_selection(player, context).kept_bonus_card_names[0]

    return choose


def expected_points_chooser() -> Chooser:
    policy = PotentialPointsSetupPolicy(bonus_scoring="expected_points")

    def choose(player, context):
        return policy.choose_initial_selection(player, context).kept_bonus_card_names[0]

    return choose


def dealt_first_chooser() -> Chooser:
    return lambda player, _context: player.bonus_cards[0].name


def evaluate(
    pairs: list[tuple[KeepObservation, KeepObservation]],
    choosers: dict[str, Chooser],
    *,
    workbook: Path,
) -> dict[str, list[float]]:
    """Score every chooser on every deal; ``oracle`` is the better of the two."""

    catalog = load_base_game_content_catalog(workbook)
    scores: dict[str, list[float]] = {name: [] for name in choosers}
    scores["oracle"] = []
    for a, b in pairs:
        state = setup_base_game(
            catalog,
            player_ids=[f"player_{i + 1}" for i in range(len(a.lineup))],
            random_seed=a.seed,
            apply_initial_selection=False,
        )
        player = state.players[0]
        context = _initial_selection_context(state)
        by_card = {a.kept: a.score, b.kept: b.score}
        for name, chooser in choosers.items():
            chosen = chooser(player, context)
            scores[name].append(by_card[chosen])
        scores["oracle"].append(max(a.score, b.score))
    return scores


def report(scores: dict[str, list[float]], baseline: str) -> str:
    n = len(scores[baseline])
    oracle = scores["oracle"]
    lines = [
        "# Opening bonus-card policy evaluation (free paired arm)",
        "",
        f"Deals: {n}. Baseline: `{baseline}`. Oracle = better of the two forced games.",
        "",
        "| Policy | Mean score | Δ vs baseline | p | Picked the better card |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in scores.items():
        deltas = [v - b for v, b in zip(values, scores[baseline], strict=True)]
        delta, p = paired_test(deltas)
        decided = [(v, o) for v, o in zip(values, oracle, strict=True)]
        judged = len(decided)
        right = sum(1 for v, o in decided if v == o)
        lines.append(
            f"| `{name}` | {mean(values):.2f} | {delta:+.2f} | {p:.3f} | "
            f"{right}/{judged} ({right / judged:.0%}) |"
        )
    gap = mean(o - b for o, b in zip(oracle, scores[baseline], strict=True))
    lines += ["", f"Headroom: the oracle beats the baseline by **{gap:.2f}** points per deal."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arm-a", type=Path, required=True)
    parser.add_argument("--arm-b", type=Path, required=True)
    parser.add_argument("--study-agent", default="potential_points")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    args = parser.parse_args(argv)
    pairs = pair_arms(load_arm(args.arm_a), load_arm(args.arm_b), args.study_agent)
    if not pairs:
        print("No forced-keep pairs found.")
        return 1
    choosers = {
        "study_agent_default": default_chooser(args.study_agent),
        "expected_points": expected_points_chooser(),
        "dealt_first": dealt_first_chooser(),
    }
    scores = evaluate(pairs, choosers, workbook=args.workbook)
    print(report(scores, "study_agent_default"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
