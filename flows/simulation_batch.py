"""Prefect-compatible simulation batch flow."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.sample_catalog import make_sample_catalog
from wingspan_ai.simulation import run_single_game

try:
    from prefect import flow, task
except ImportError:

    def flow(func=None, **_kwargs):
        if func is None:
            return lambda wrapped: wrapped
        return func

    def task(func=None, **_kwargs):
        if func is None:
            return lambda wrapped: wrapped
        return func


@task
def run_seeded_game(workbook_path: str, random_seed: int) -> dict[str, Any]:
    resolved_workbook_path = Path(workbook_path)
    catalog = (
        load_base_game_content_catalog(resolved_workbook_path)
        if resolved_workbook_path.exists()
        else make_sample_catalog()
    )
    result = run_single_game(
        catalog,
        [
            RandomLegalAgent(agent_id="random_legal_p1", random_seed=random_seed),
            GreedyBaselineAgent(agent_id="greedy_immediate_p2"),
        ],
        random_seed=random_seed,
    )
    return {
        "outcome": asdict(result.outcome),
        "event_count": len(result.events),
    }


@flow(name="wingspan-simulation-batch")
def run_simulation_batch(
    workbook_path: str = str(DEFAULT_WORKBOOK_PATH),
    seeds: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Run a small seeded batch for local smoke tests or Prefect orchestration."""

    resolved_seeds = seeds or [1, 2, 3]
    return [run_seeded_game(workbook_path, seed) for seed in resolved_seeds]


if __name__ == "__main__":
    print(run_simulation_batch())
