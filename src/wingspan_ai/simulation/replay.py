"""Replay and audit helpers for deterministic simulation traces."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from wingspan_ai.content.schemas import ContentCatalog, FoodType
from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import (
    InitialSelection,
    apply_action,
    apply_initial_selection_choice,
    setup_base_game,
)
from wingspan_ai.state.models import GameState
from wingspan_ai.telemetry.events import EventName, SimulationEvent


def canonical_state_payload(state: GameState) -> dict[str, Any]:
    """Return a stable JSON-compatible full-state payload for hashing."""

    return state.model_dump(mode="json")


def canonical_state_json(state: GameState) -> str:
    """Return stable serialized full state for replay/debug comparisons."""

    return json.dumps(canonical_state_payload(state), sort_keys=True, separators=(",", ":"))


def state_hash(state: GameState) -> str:
    """Return a deterministic SHA-256 hash of the full simulator state."""

    return hashlib.sha256(canonical_state_json(state).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReplayValidationResult:
    """Outcome of replaying action events against recorded state hashes."""

    is_valid: bool
    checked_transitions: int
    errors: list[str]


def validate_simulation_replay(
    catalog: ContentCatalog,
    events: list[SimulationEvent],
) -> ReplayValidationResult:
    """Reconstruct a game from telemetry and verify action state hashes."""

    errors: list[str] = []
    run_started = _first_event(events, EventName.SIMULATION_RUN_STARTED)
    game_started = _first_event(events, EventName.GAME_STARTED)
    if run_started is None or game_started is None:
        return ReplayValidationResult(
            is_valid=False,
            checked_transitions=0,
            errors=["missing simulation_run_started or game_started event"],
        )

    player_count = int(run_started.payload.get("player_count", 0))
    random_seed = game_started.random_seed
    if player_count <= 0 or random_seed is None:
        return ReplayValidationResult(
            is_valid=False,
            checked_transitions=0,
            errors=["missing player_count or random_seed for replay setup"],
        )

    player_ids = [f"player_{index + 1}" for index in range(player_count)]
    state = setup_base_game(
        catalog,
        player_ids=player_ids,
        random_seed=random_seed,
        game_id=game_started.game_id or "game_1",
        apply_initial_selection=False,
    )
    for setup_event in _events_named(events, EventName.SETUP_SELECTION_APPLIED):
        player = next(
            candidate for candidate in state.players if candidate.player_id == setup_event.player_id
        )
        player.agent_id = setup_event.agent_id
        selection = InitialSelection(
            player_id=player.player_id,
            kept_bird_names=list(setup_event.payload["kept_bird_names"]),
            kept_bonus_card_names=list(setup_event.payload["kept_bonus_card_names"]),
            starting_food=[FoodType(food) for food in setup_event.payload["starting_food"]],
        )
        discarded_birds, discarded_bonus_cards = apply_initial_selection_choice(player, selection)
        state.decks.bird_discard.extend(discarded_birds)
        state.decks.bonus_discard.extend(discarded_bonus_cards)

    checked = 0
    for event in _events_named(events, EventName.ACTION_RESOLVED):
        expected_before = event.payload.get("state_hash_before")
        actual_before = state_hash(state)
        if expected_before != actual_before:
            errors.append(
                f"turn {event.turn_number}: before hash mismatch "
                f"expected={expected_before} actual={actual_before}"
            )
            break

        action = LegalAction.model_validate(event.payload["action"])
        state = apply_action(state, action)
        expected_after = event.payload.get("state_hash_after")
        actual_after = state_hash(state)
        if expected_after != actual_after:
            errors.append(
                f"turn {event.turn_number}: after hash mismatch "
                f"expected={expected_after} actual={actual_after}"
            )
            break
        checked += 1

    return ReplayValidationResult(
        is_valid=not errors,
        checked_transitions=checked,
        errors=errors,
    )


def _first_event(
    events: list[SimulationEvent],
    event_name: EventName,
) -> SimulationEvent | None:
    return next((event for event in events if event.event_name == event_name), None)


def _events_named(
    events: list[SimulationEvent],
    event_name: EventName,
) -> list[SimulationEvent]:
    return [event for event in events if event.event_name == event_name]
