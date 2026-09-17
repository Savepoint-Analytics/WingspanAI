"""Layer C: the 2×2 forced-play interaction contrast for a card pair.

Four arms share every seed. The study agent is dealt and forced to play
{A, B}, {A, B'}, {A', B} or {A', B'}, where A' and B' are matched controls
with non-interacting powers. Per seed,

    interaction = (AB − AB') − (A'B − A'B')

is what the *combination* is worth beyond each card's own contribution; the
main effects (A − A', B − B') come out of the same four numbers. Forcing is
applied identically in every arm, so it cancels. Intention-to-treat is the
headline (every seed counts, played or not); the completed-pair estimate
restricts to seeds where the AB arm got both birds onto the board in the
same row, and reports the completion rate so the two can be read together.

    python analysis/forced_play_contrast.py --pair "Common Grackle" "Cooper's Hawk" \\
        --ab artifacts/forced_play/P1/AB --ab-ctrl artifacts/forced_play/P1/ABc \\
        --a-ctrl-b artifacts/forced_play/P1/AcB --ctrl-ctrl artifacts/forced_play/P1/AcBc
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import GameKey, agent_result, load_arm, paired_test  # noqa: E402


def study_score(game: dict, agent: str) -> float | None:
    result = agent_result(game, agent)
    return None if result is None else result[0]


def pair_completed(game: dict, agent: str, pair: tuple[str, str]) -> tuple[bool, bool]:
    """(both forced birds on the board at game end, in the same row)."""

    artifact_dir = game.get("artifact_dir")
    if not artifact_dir:
        return False, False
    lineup = game["player_agent_kinds"]
    seat = (lineup.index(agent) - game["seat_rotation"]) % game["player_count"]
    player_id = f"player_{seat + 1}"
    with (Path(artifact_dir) / "events.jsonl").open() as handle:
        for line in handle:
            if '"bird_scorecard"' not in line:
                continue
            event = json.loads(line)
            if (
                event["event_name"] != "bird_scorecard"
                or event["payload"]["player_id"] != player_id
            ):
                continue
            rows = {b["common_name"]: b["habitat"] for b in event["payload"]["birds"]}
            both = all(name in rows for name in pair)
            same_row = both and rows[pair[0]] == rows[pair[1]]
            return both, same_row
    return False, False


def contrast(arms: dict[str, dict[GameKey, dict]], agent: str, pair: tuple[str, str]) -> dict:
    keys = set.intersection(*(set(arm) for arm in arms.values()))
    keys = sorted(
        (k for k in keys if agent in k.lineup), key=lambda k: (k.lineup, k.rotation, k.seed)
    )
    interactions, a_effects, b_effects, completed_interactions = [], [], [], []
    both_count = same_row_count = 0
    for key in keys:
        scores = {name: study_score(arm[key], agent) for name, arm in arms.items()}
        if any(v is None for v in scores.values()):
            continue
        ab, abc, acb, acbc = scores["AB"], scores["ABc"], scores["AcB"], scores["AcBc"]
        interaction = (ab - abc) - (acb - acbc)
        interactions.append(interaction)
        a_effects.append((ab + abc) / 2 - (acb + acbc) / 2)
        b_effects.append((ab + acb) / 2 - (abc + acbc) / 2)
        both, same_row = pair_completed(arms["AB"][key], agent, pair)
        both_count += both
        same_row_count += same_row
        if same_row:
            completed_interactions.append(interaction)
    n = len(interactions)
    inter, inter_p = paired_test(interactions)
    a_eff, a_p = paired_test(a_effects)
    b_eff, b_p = paired_test(b_effects)
    comp, comp_p = paired_test(completed_interactions) if completed_interactions else (0.0, 1.0)
    return {
        "seeds": n,
        "interaction": inter,
        "interaction_p": inter_p,
        "a_main_effect": a_eff,
        "a_main_p": a_p,
        "b_main_effect": b_eff,
        "b_main_p": b_p,
        "ab_both_played": both_count,
        "ab_same_row": same_row_count,
        "completed_interaction": comp,
        "completed_p": comp_p,
        "completed_n": len(completed_interactions),
        "mean_scores": {
            name: mean(study_score(arm[k], agent) for k in keys) for name, arm in arms.items()
        },
    }


def report(pair: tuple[str, str], controls: tuple[str, str], result: dict) -> str:
    lines = [
        f"# Forced-play 2×2: {pair[0]} + {pair[1]} (controls {controls[0]} / {controls[1]})",
        "",
        f"Seeds with all four arms: {result['seeds']}.",
        "",
        "| Arm | mean score |",
        "|---|---:|",
    ]
    labels = {
        "AB": f"{pair[0]} + {pair[1]}",
        "ABc": f"{pair[0]} + {controls[1]}",
        "AcB": f"{controls[0]} + {pair[1]}",
        "AcBc": f"{controls[0]} + {controls[1]}",
    }
    for name, score in result["mean_scores"].items():
        lines.append(f"| {labels[name]} | {score:.2f} |")
    r = result
    lines += [
        "",
        f"- **Interaction** (AB − AB') − (A'B − A'B'): **{r['interaction']:+.2f}** "
        f"(p = {r['interaction_p']:.3f}), intention to treat",
        f"- Main effect of {pair[0]} over {controls[0]}: {r['a_main_effect']:+.2f} "
        f"(p = {r['a_main_p']:.3f})",
        f"- Main effect of {pair[1]} over {controls[1]}: {r['b_main_effect']:+.2f} "
        f"(p = {r['b_main_p']:.3f})",
        f"- AB arm completion: both played {r['ab_both_played']}/{r['seeds']}, "
        f"same row {r['ab_same_row']}/{r['seeds']}",
        f"- Interaction on completed seeds (n = {r['completed_n']}): "
        f"{r['completed_interaction']:+.2f} (p = {r['completed_p']:.3f})",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pair", nargs=2, required=True, metavar=("A", "B"))
    parser.add_argument("--controls", nargs=2, required=True, metavar=("A_CTRL", "B_CTRL"))
    parser.add_argument("--ab", type=Path, required=True)
    parser.add_argument("--ab-ctrl", type=Path, required=True)
    parser.add_argument("--a-ctrl-b", type=Path, required=True)
    parser.add_argument("--ctrl-ctrl", type=Path, required=True)
    parser.add_argument("--study-agent", default="archetype_engine_builder")
    args = parser.parse_args(argv)
    arms = {
        "AB": load_arm(args.ab),
        "ABc": load_arm(args.ab_ctrl),
        "AcB": load_arm(args.a_ctrl_b),
        "AcBc": load_arm(args.ctrl_ctrl),
    }
    result = contrast(arms, args.study_agent, tuple(args.pair))
    if result["seeds"] == 0:
        print("No seeds shared by all four arms.")
        return 1
    print(report(tuple(args.pair), tuple(args.controls), result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
