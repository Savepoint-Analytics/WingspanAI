"""Play one archived game against the production agent from the terminal.

The human-trace study (``docs/experiments/self_play_opponent_plan.md``, H1–H3)
needs human games that look exactly like agent games to the archive: same
events, replay validation, manifest, viewer. This flow is ``run_simulation_batch``
with a ``human_cli`` seat and the production search configuration on the
other seat (five-second cap, so the human waits about a second a turn), under
``artifacts/human/<label>/``. Seat and seed are recorded so the ten-game study
can be seat-swapped and replayed.

    python flows/human_vs_agent.py --seed 101 --seat 1
    python flows/human_vs_agent.py --seed 101 --seat 2 --opponent greedy_immediate
    python analysis/game_viewer.py artifacts/human/experiment/human_trace/<batch>/seed_101 \\
        --pov player_1

Setup (which birds and bonus card to keep, starting food) is chosen at the
prompt, not by the default opener. Decision telemetry for the human seat
records the legal actions and the choice; the agent seat records its full
search ranking, which is what the disagreement review (H2) reads.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flows.simulation_batch import run_simulation_batch  # noqa: E402
from wingspan_ai.agents.potential_points import (  # noqa: E402
    PRODUCTION_SEARCH_OVERRIDES,
    PotentialPointsSearchConfig,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH  # noqa: E402

#: Opponents a human can face, with the one-line description ``--help`` prints.
OPPONENTS: dict[str, str] = {
    "potential_points": "production agent (default): expected-value search with endgame "
    "lookahead and its own opening-hand policy; 5 s cap per decision",
    "net_value_response": "potential points, net of the estimated opponent reply",
    "greedy_immediate": "greedy baseline: takes the action worth most points right now",
    "monte_carlo_rollout": "Monte Carlo rollouts per candidate action (slow)",
    "archetype_egg_focus": "scripted archetype: egg laying",
    "archetype_engine_builder": "scripted archetype: engine building",
    "archetype_food_acceleration": "scripted archetype: food economy first",
    "archetype_card_draw": "scripted archetype: card draw",
    "archetype_bonus_card_focus": "scripted archetype: bonus-card chasing",
    "archetype_round_goal_chase": "scripted archetype: end-of-round goals",
    "random_legal": "uniformly random legal action (sanity check)",
}

EPILOG = (
    """\
opponents (--opponent):
"""
    + "\n".join(f"  {name:<28} {text}" for name, text in OPPONENTS.items())
    + """

what you see:
  At setup: who is in each seat, the four end-of-round goals and their
  points, the birdfeeder dice, the three face-up tray birds, then your five
  birds and two bonus cards. Keep N birds and take 5-N food.
  After every seat has chosen: each seat's public setup result (birds kept,
  starting food). Opponents' actual cards stay hidden.
  Every turn: all boards with live scores, tray, feeder, round goals, your
  hand and bonus card, then numbered legal actions.

reproducibility:
  The same --seed and --seat deal the same cards, tray, feeder and goals,
  and the opponent makes the same setup choice. After the game, review it
  with analysis/game_viewer.py (the command is printed at the end); add
  --all-private to the viewer to see the opponent's hand. To see what the
  opponent kept without playing, run scripts/inspect_setup.py.

examples:
  python flows/human_vs_agent.py --seed 101 --seat 1
  python flows/human_vs_agent.py --seed 101 --seat 2 --opponent greedy_immediate
"""
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Play one archived two-player game of base Wingspan against an AI agent.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="game seed; fixes the deal, tray, feeder, goals and the opponent's choices",
    )
    parser.add_argument(
        "--seat",
        type=int,
        choices=(1, 2),
        default=1,
        help="your seat: 1 moves first in round 1, 2 moves second (default: 1)",
    )
    parser.add_argument(
        "--opponent",
        default="potential_points",
        choices=tuple(OPPONENTS),
        metavar="AGENT",
        help="opponent agent, listed below (default: potential_points)",
    )
    parser.add_argument(
        "--label",
        default="human_trace",
        help="batch label; the game is archived under <artifact-root>/experiment/<label>/ "
        "(default: human_trace)",
    )
    parser.add_argument(
        "--workbook",
        default=str(DEFAULT_WORKBOOK_PATH),
        help="card list workbook (default: %(default)s)",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/human",
        help="where the archived game is written (default: %(default)s)",
    )
    parser.add_argument(
        "--unbudgeted",
        action="store_true",
        help="potential_points only: research search config with no 5 s cap (slower turns)",
    )
    args = parser.parse_args(argv)

    opponent_seat = 2 if args.seat == 1 else 1
    cap_seconds = PRODUCTION_SEARCH_OVERRIDES["max_decision_time_ms"] / 1000
    budget = (
        "unbudgeted research search"
        if args.unbudgeted
        else f"production search, {cap_seconds:g} s cap"
    )
    print("=" * 72)
    print(f"Wingspan — human vs {args.opponent}   seed {args.seed}")
    # Agent ids follow lineup position, not seat: the human is always
    # ``human_cli_p1`` and the opponent ``<kind>_p2``, whichever seat each sits in.
    print(f"  You:      player_{args.seat} (human_cli_p1)")
    print(f"  Opponent: player_{opponent_seat} ({args.opponent}_p2) — {OPPONENTS[args.opponent]}")
    if args.opponent == "potential_points":
        print(f"            search: {budget}")
    print("=" * 72)

    search = (
        PotentialPointsSearchConfig()
        if args.unbudgeted
        else PotentialPointsSearchConfig(**PRODUCTION_SEARCH_OVERRIDES)
    )
    # Lineup position 0 is the human; ``seat_rotation`` puts it in the seat asked for.
    results = run_simulation_batch(
        workbook_path=args.workbook,
        seeds=[args.seed],
        artifact_root=args.artifact_root,
        persist_postgres=False,
        upload_artifacts=None,
        batch_kind="experiment",
        batch_label=args.label,
        player_agent_kinds=["human_cli", args.opponent],
        seat_rotation=0 if args.seat == 1 else 1,
        setup_policy_kind="agent_default",
        potential_points_search=search,
    )
    result = results[0]
    outcome = result["outcome"]
    human_seat = f"player_{args.seat}"
    print()
    print(f"Final scores: {outcome['scores']}  winners: {outcome['winners']}")
    print(f"You were {human_seat}; replay valid: {result['replay_validation']['is_valid']}")
    print(f"Archived at {result['artifact_dir']}")
    print(f"Review: python analysis/game_viewer.py {result['artifact_dir']} --pov {human_seat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
