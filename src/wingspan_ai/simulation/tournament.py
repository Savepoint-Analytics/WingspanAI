"""Tournament runner and matchup summaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wingspan_ai.content.schemas import ContentCatalog
from wingspan_ai.rules import audit_rule_coverage
from wingspan_ai.simulation.runner import AgentPolicy, SimulationResult, run_single_game

AgentFactory = Callable[[int, int], AgentPolicy]


@dataclass(frozen=True)
class TournamentSummary:
    """Aggregate tournament metrics by agent id."""

    games_played: int
    win_counts: dict[str, int]
    win_rates: dict[str, float]
    mean_scores: dict[str, float]
    mean_turns_played: float
    rule_audits: dict[str, Any] | None = None


@dataclass(frozen=True)
class TournamentResult:
    """Full tournament output with per-game results and summary metrics."""

    tournament_id: str
    results: list[SimulationResult]
    summary: TournamentSummary


def run_tournament(
    catalog: ContentCatalog,
    agent_factories: list[AgentFactory],
    *,
    seeds: list[int],
    tournament_id: str = "tournament_1",
) -> TournamentResult:
    """Run a seeded fixed-roster tournament."""

    if not seeds:
        raise ValueError("run_tournament requires at least one seed")
    if len(agent_factories) < 1:
        raise ValueError("run_tournament requires at least one agent factory")

    results: list[SimulationResult] = []
    for game_index, seed in enumerate(seeds, start=1):
        agents = [
            factory(seed, player_index)
            for player_index, factory in enumerate(agent_factories, start=1)
        ]
        results.append(
            run_single_game(
                catalog,
                agents,
                random_seed=seed,
                game_id=f"{tournament_id}_game_{game_index}",
                simulation_run_id=tournament_id,
            )
        )

    return TournamentResult(
        tournament_id=tournament_id,
        results=results,
        summary=summarize_tournament(results, catalog=catalog),
    )


def summarize_tournament(
    results: list[SimulationResult],
    *,
    catalog: ContentCatalog | None = None,
) -> TournamentSummary:
    """Summarize scores, wins, and game lengths by agent id."""

    score_totals: dict[str, int] = {}
    score_counts: dict[str, int] = {}
    win_counts: dict[str, int] = {}

    for result in results:
        player_to_agent = {
            player.player_id: player.agent_id or player.player_id for player in result.state.players
        }
        for player_id, score in result.outcome.scores.items():
            agent_id = player_to_agent[player_id]
            score_totals[agent_id] = score_totals.get(agent_id, 0) + score
            score_counts[agent_id] = score_counts.get(agent_id, 0) + 1
            win_counts.setdefault(agent_id, 0)
        for winner_id in result.outcome.winners:
            agent_id = player_to_agent[winner_id]
            win_counts[agent_id] = win_counts.get(agent_id, 0) + 1

    games_played = len(results)
    return TournamentSummary(
        games_played=games_played,
        win_counts=win_counts,
        win_rates={
            agent_id: wins / games_played for agent_id, wins in sorted(win_counts.items())
        },
        mean_scores={
            agent_id: score_totals[agent_id] / score_counts[agent_id]
            for agent_id in sorted(score_totals)
        },
        mean_turns_played=sum(result.outcome.turns_played for result in results) / games_played,
        rule_audits=audit_rule_coverage(catalog) if catalog is not None else None,
    )
