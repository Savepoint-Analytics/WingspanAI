"""Run a local human-vs-greedy game in the terminal."""

from __future__ import annotations

from wingspan_ai.agents import GreedyBaselineAgent, HumanCliAgent
from wingspan_ai.content.loader import load_base_game_content_catalog
from wingspan_ai.simulation import run_single_game


def main() -> None:
    catalog = load_base_game_content_catalog()
    result = run_single_game(
        catalog,
        [
            HumanCliAgent(agent_id="human_player"),
            GreedyBaselineAgent(agent_id="greedy_opponent"),
        ],
        random_seed=1,
        game_id="human_vs_greedy",
    )
    print(result.outcome)


if __name__ == "__main__":
    main()
