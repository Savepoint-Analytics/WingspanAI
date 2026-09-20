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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(1, 2), default=1, help="the human's seat")
    parser.add_argument("--opponent", default="potential_points")
    parser.add_argument("--label", default="human_trace")
    parser.add_argument("--workbook", default=str(DEFAULT_WORKBOOK_PATH))
    parser.add_argument("--artifact-root", default="artifacts/human")
    parser.add_argument(
        "--unbudgeted",
        action="store_true",
        help="research config instead of the 5 s production cap",
    )
    args = parser.parse_args(argv)

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
