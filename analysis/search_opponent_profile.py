"""Time potential-points decisions under each search opponent model, back to back.

Walks one seeded two-player game along the trajectory the greedy-modelled
agent actually plays, and on every potential-points turn times ``select_action``
on the identical state for both opponent models. Both agents observe the same
real actions, so the belief model's posterior is what it would be in a live
game. Because both timings come from one process on one state, the contrast is
not confounded by machine load the way concurrent arms are.

Usage:
    python analysis/search_opponent_profile.py --seed 1 --opponent archetype_engine_builder
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent
from wingspan_ai.agents.archetypes import StrategyArchetype, StrategyArchetypeAgent
from wingspan_ai.agents.net_value import NetValueOpponentResponseAgent
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    setup_base_game,
)

OPPONENTS = {
    "greedy_immediate": lambda: GreedyBaselineAgent(agent_id="greedy_immediate"),
    "archetype_engine_builder": lambda: StrategyArchetypeAgent(
        StrategyArchetype.ENGINE_BUILDER, agent_id="engine_builder"
    ),
    "archetype_bonus_card_focus": lambda: StrategyArchetypeAgent(
        StrategyArchetype.BONUS_CARD_FOCUS, agent_id="bonus_card_focus"
    ),
    "net_value_response": lambda: NetValueOpponentResponseAgent(agent_id="net_value_response"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--opponent", choices=sorted(OPPONENTS), default="archetype_engine_builder")
    parser.add_argument("--max-decisions", type=int, default=None)
    parser.add_argument("--json", type=Path, default=None, help="write per-decision rows here")
    args = parser.parse_args(argv)

    catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
    greedy_model = PotentialPointsAgent(agent_id="pp", search_opponent_model="greedy")
    belief_model = PotentialPointsAgent(agent_id="pp", search_opponent_model="belief")
    opponent = OPPONENTS[args.opponent]()
    state = setup_base_game(catalog, player_ids=["player_1", "player_2"], random_seed=args.seed)
    for player in state.players:
        player.agent_id = "pp" if player.player_id == "player_1" else opponent.agent_id

    rows: list[dict] = []
    while not state.round_state.game_over:
        legal_actions = legal_actions_for_current_player(state)
        if not legal_actions:
            break
        acting = state.active_player.player_id
        if acting == "player_1":
            started = time.perf_counter()
            chosen = greedy_model.select_action(state, legal_actions)
            greedy_seconds = time.perf_counter() - started
            started = time.perf_counter()
            belief_choice = belief_model.select_action(state, legal_actions)
            belief_seconds = time.perf_counter() - started
            rows.append(
                {
                    "turn": state.round_state.global_turn_number,
                    "round": state.round_state.round_number,
                    "legal_actions": len(legal_actions),
                    "greedy_seconds": round(greedy_seconds, 3),
                    "belief_seconds": round(belief_seconds, 3),
                    "same_choice": chosen == belief_choice,
                }
            )
            print(
                f"turn {rows[-1]['turn']:>3} r{rows[-1]['round']} "
                f"actions {len(legal_actions):>3}  greedy {greedy_seconds:7.2f}s  "
                f"belief {belief_seconds:7.2f}s  same={chosen == belief_choice}",
                flush=True,
            )
            if args.max_decisions is not None and len(rows) >= args.max_decisions:
                break
        else:
            chosen = opponent.select_action(state, legal_actions)
        greedy_model.observe_action(state, chosen, acting)
        belief_model.observe_action(state, chosen, acting)
        state = apply_action(state, chosen)

    greedy_times = [row["greedy_seconds"] for row in rows]
    belief_times = [row["belief_seconds"] for row in rows]
    summary = {
        "seed": args.seed,
        "opponent": args.opponent,
        "decisions": len(rows),
        "greedy_total_s": round(sum(greedy_times), 2),
        "belief_total_s": round(sum(belief_times), 2),
        "greedy_mean_s": round(statistics.mean(greedy_times), 3) if rows else None,
        "belief_mean_s": round(statistics.mean(belief_times), 3) if rows else None,
        "greedy_max_s": max(greedy_times, default=None),
        "belief_max_s": max(belief_times, default=None),
        "time_reduction": (
            round(1 - sum(belief_times) / sum(greedy_times), 4) if sum(greedy_times) else None
        ),
        "same_choice_share": (
            round(sum(row["same_choice"] for row in rows) / len(rows), 4) if rows else None
        ),
        "belief_posterior": belief_model.opponent_model.telemetry_payload(),
    }
    print(json.dumps(summary, indent=2))
    if args.json is not None:
        args.json.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
