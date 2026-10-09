"""Show every seat's dealt and kept opening for a human-vs-agent seed, without playing.

The opening is fixed by the seed: the deal, tray, feeder and goals come from
the game RNG, and the opponent's setup policy sees only its own hand and the
public table, so what it keeps does not depend on what the human keeps. This
runs ``flows/human_vs_agent.py``'s exact batch call, records each seat's
opening as it is chosen, and stops before the first turn. Nothing is archived.

    python scripts/inspect_setup.py --seed 101 --seat 1
    python scripts/inspect_setup.py --seed 101 --seat 2 --opponent greedy_immediate

This prints private information (the opponent's hand and bonus card), so use
it to review a game, not during one. For a finished, archived game, read the
``setup_selection_applied`` events instead:

    jq -c 'select(.event_name=="setup_selection_applied") | .payload
        | {player_id, agent_id, setup_policy_id, kept_bird_names,
           kept_bonus_card_names, starting_food, discarded_bird_names}' \\
        artifacts/human/experiment/human_trace/<batch>/seed_101/events.jsonl
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import flows.human_vs_agent as human_vs_agent  # noqa: E402
import wingspan_ai.simulation.runner as runner  # noqa: E402
from wingspan_ai.agents.human_cli import HumanCliAgent, setup_table_lines  # noqa: E402
from wingspan_ai.rules.base_game import choose_default_initial_selection  # noqa: E402
from wingspan_ai.state.render import card_line  # noqa: E402


class _SetupDone(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seat", type=int, choices=(1, 2), default=1, help="the human's seat")
    parser.add_argument(
        "--opponent", default="potential_points", choices=tuple(human_vs_agent.OPPONENTS)
    )
    parser.add_argument("--unbudgeted", action="store_true")
    args = parser.parse_args(argv)

    openings: list[dict] = []
    original_choose = runner._choose_agent_initial_selection

    def recording_choose(agent, player, context):
        dealt = list(player.hand)
        dealt_bonus = list(player.bonus_cards)
        result = original_choose(agent, player, context)
        openings.append(
            {
                "player": player,
                "agent": agent,
                "dealt": dealt,
                "dealt_bonus": dealt_bonus,
                "selection": result[0],
                "setup_policy_id": result[2],
                "context": context,
            }
        )
        return result

    def stop_after_setup(self, state):
        raise _SetupDone

    # The human seat takes the default opener here; it does not change the
    # other seat's choice (see module docstring). Stop at the post-setup hook.
    runner._choose_agent_initial_selection = recording_choose
    HumanCliAgent.choose_initial_selection = lambda self, player, context=None: (
        choose_default_initial_selection(player)
    )
    HumanCliAgent.observe_setup_complete = stop_after_setup

    flow_args = ["--seed", str(args.seed), "--seat", str(args.seat), "--opponent", args.opponent]
    if args.unbudgeted:
        flow_args.append("--unbudgeted")
    with tempfile.TemporaryDirectory() as scratch:
        try:
            human_vs_agent.main([*flow_args, "--artifact-root", scratch])
        except _SetupDone:
            pass

    if not openings:
        print("setup was not reached", file=sys.stderr)
        return 1
    for line in setup_table_lines(openings[0]["player"], openings[0]["context"])[3:]:
        print(line)
    for opening in openings:
        player, agent, selection = opening["player"], opening["agent"], opening["selection"]
        is_human = agent.agent_id.startswith("human_cli")
        print(f"\n{player.player_id}  {agent.agent_id}  ({type(agent).__name__})")
        if is_human:
            print("  (human seat: the keep below is the default opener, not yours)")
        else:
            print(f"  setup policy: {opening['setup_policy_id']}")
        kept = set(selection.kept_bird_names)
        print("  dealt birds (* = kept):")
        for card in opening["dealt"]:
            print(f"    {'*' if card.common_name in kept else ' '} {card_line(card)}")
        print(f"  dealt bonus: {', '.join(b.name for b in opening['dealt_bonus'])}")
        print(f"  kept bonus:  {', '.join(selection.kept_bonus_card_names)}")
        food = ", ".join(f.value for f in selection.starting_food) or "none"
        print(
            f"  kept {len(selection.kept_bird_names)} birds + "
            f"{len(selection.starting_food)} food: {food}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
