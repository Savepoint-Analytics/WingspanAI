"""Simulation event contracts for Wingspan AI runs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventName(StrEnum):
    """Stable simulation event names."""

    SIMULATION_RUN_STARTED = "simulation_run_started"
    GAME_STARTED = "game_started"
    SETUP_SELECTION_APPLIED = "setup_selection_applied"
    ROUND_STARTED = "round_started"
    TURN_STARTED = "turn_started"
    LEGAL_ACTIONS_GENERATED = "legal_actions_generated"
    ACTION_SELECTED = "action_selected"
    ACTION_RESOLVED = "action_resolved"
    GAME_ENDED = "game_ended"
    AGENT_DECISION_SUMMARY = "agent_decision_summary"


class SimulationEvent(BaseModel):
    """Versioned telemetry event emitted by simulations and services."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_name: EventName
    event_version: str = "1.0"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    simulation_run_id: str
    game_id: str | None = None
    ruleset_id: str | None = None
    player_id: str | None = None
    agent_id: str | None = None
    round_number: int | None = Field(default=None, ge=1)
    turn_number: int | None = Field(default=None, ge=1)
    random_seed: int | None = None
    public_state_ref: str | None = None
    private_state_included: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    """Batch payload accepted by local ingestion adapters."""

    model_config = ConfigDict(extra="forbid")

    events: list[SimulationEvent]


class InMemoryEventSink:
    """Small event sink for tests, notebooks, and local simulation runs."""

    def __init__(self) -> None:
        self.events: list[SimulationEvent] = []

    def emit(self, event: SimulationEvent) -> None:
        self.events.append(event)

    def extend(self, events: list[SimulationEvent]) -> None:
        self.events.extend(events)
