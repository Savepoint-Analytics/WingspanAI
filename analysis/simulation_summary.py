"""Small analysis helpers for simulation event outputs."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from wingspan_ai.simulation.runner import SimulationResult
from wingspan_ai.telemetry.events import EventName, SimulationEvent


def outcome_rows(results: list[SimulationResult]) -> list[dict[str, Any]]:
    """Flatten simulation outcomes into row dictionaries."""

    rows: list[dict[str, Any]] = []
    for result in results:
        outcome = asdict(result.outcome)
        for player_id, score in result.outcome.scores.items():
            rows.append(
                {
                    "simulation_run_id": outcome["simulation_run_id"],
                    "game_id": outcome["game_id"],
                    "random_seed": outcome["random_seed"],
                    "player_id": player_id,
                    "score": score,
                    "is_winner": player_id in result.outcome.winners,
                    "turns_played": outcome["turns_played"],
                    "terminal_reason": outcome["terminal_reason"],
                }
            )
    return rows


def action_frequency(events: list[SimulationEvent]) -> Counter[str]:
    """Count selected actions by action type."""

    counter: Counter[str] = Counter()
    for event in events:
        if event.event_name != EventName.ACTION_SELECTED:
            continue
        action = event.payload.get("action", {})
        action_type = action.get("action_type")
        if action_type:
            counter[str(action_type)] += 1
    return counter


def event_counts(events: list[SimulationEvent]) -> Counter[str]:
    """Count events by event name."""

    return Counter(event.event_name.value for event in events)
