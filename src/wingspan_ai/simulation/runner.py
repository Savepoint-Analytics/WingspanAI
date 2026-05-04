"""Single-game simulation runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import uuid4

from wingspan_ai.content.schemas import ContentCatalog
from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    score_player,
    setup_base_game,
)
from wingspan_ai.state.models import GameState, to_public_state
from wingspan_ai.telemetry.events import EventName, InMemoryEventSink, SimulationEvent


class AgentPolicy(Protocol):
    """Minimum interface for agents used by the simulation runner."""

    agent_id: str

    def choose_action(self, state: GameState) -> LegalAction:
        """Choose one legal action for the active player."""


@dataclass(frozen=True)
class GameOutcome:
    """Final score and winner summary for one simulated game."""

    game_id: str
    simulation_run_id: str
    random_seed: int
    scores: dict[str, int]
    winners: list[str]
    turns_played: int
    terminal_reason: str


@dataclass(frozen=True)
class SimulationResult:
    """Complete result returned by a single-game simulation."""

    state: GameState
    outcome: GameOutcome
    events: list[SimulationEvent]
    public_state_snapshots: dict[str, dict]


def run_single_game(
    catalog: ContentCatalog,
    agents: list[AgentPolicy],
    *,
    random_seed: int,
    game_id: str | None = None,
    simulation_run_id: str | None = None,
    max_turns: int = 200,
) -> SimulationResult:
    """Run one seeded game and return final state, outcome, and telemetry."""

    if len(agents) < 1:
        raise ValueError("run_single_game requires at least one agent")

    resolved_game_id = game_id or f"game_{random_seed}"
    resolved_run_id = simulation_run_id or str(uuid4())
    player_ids = [f"player_{index + 1}" for index, _agent in enumerate(agents)]
    state = setup_base_game(
        catalog,
        player_ids=player_ids,
        random_seed=random_seed,
        game_id=resolved_game_id,
    )
    for player, agent in zip(state.players, agents, strict=True):
        player.agent_id = agent.agent_id

    sink = InMemoryEventSink()
    public_state_snapshots: dict[str, dict] = {}
    _record_public_snapshot(public_state_snapshots, state)
    _emit_run_started(sink, state, resolved_run_id, agents)
    _emit_game_started(sink, state, resolved_run_id)
    _emit_round_started(sink, state, resolved_run_id)

    turns_played = 0
    terminal_reason = "game_over"
    current_round = state.round_state.round_number

    while not state.round_state.game_over and turns_played < max_turns:
        if state.round_state.round_number != current_round:
            current_round = state.round_state.round_number
            _emit_round_started(sink, state, resolved_run_id)

        active_player = state.active_player
        agent = agents[state.round_state.active_player_index]
        legal_actions = legal_actions_for_current_player(state)
        _record_public_snapshot(public_state_snapshots, state)
        _emit_turn_started(sink, state, resolved_run_id)
        _emit_legal_actions(sink, state, resolved_run_id, legal_actions)

        if not legal_actions:
            terminal_reason = "no_legal_actions"
            break

        action = agent.choose_action(state)
        if action not in legal_actions:
            raise ValueError(f"agent {agent.agent_id} selected an illegal action: {action}")

        _emit_action_selected(sink, state, resolved_run_id, active_player.agent_id, action)
        previous_round = state.round_state.round_number
        state = apply_action(state, action)
        _record_public_snapshot(public_state_snapshots, state)
        turns_played += 1
        _emit_action_resolved(sink, state, resolved_run_id, active_player.player_id, action)

        if state.round_state.round_number != previous_round and not state.round_state.game_over:
            _emit_round_started(sink, state, resolved_run_id)
            current_round = state.round_state.round_number

    if turns_played >= max_turns and not state.round_state.game_over:
        terminal_reason = "max_turns_reached"

    outcome = _build_outcome(state, resolved_run_id, random_seed, turns_played, terminal_reason)
    _emit_game_ended(sink, state, resolved_run_id, outcome)
    return SimulationResult(
        state=state,
        outcome=outcome,
        events=sink.events,
        public_state_snapshots=public_state_snapshots,
    )


def _build_outcome(
    state: GameState,
    simulation_run_id: str,
    random_seed: int,
    turns_played: int,
    terminal_reason: str,
) -> GameOutcome:
    scores = {
        player.player_id: score_player(state, player.player_id).total for player in state.players
    }
    high_score = max(scores.values()) if scores else 0
    winners = [player_id for player_id, score in scores.items() if score == high_score]
    return GameOutcome(
        game_id=state.game_id,
        simulation_run_id=simulation_run_id,
        random_seed=random_seed,
        scores=scores,
        winners=winners,
        turns_played=turns_played,
        terminal_reason=terminal_reason,
    )


def _base_event(
    event_name: EventName,
    state: GameState,
    simulation_run_id: str,
    **payload,
) -> SimulationEvent:
    return SimulationEvent(
        event_name=event_name,
        simulation_run_id=simulation_run_id,
        game_id=state.game_id,
        ruleset_id=state.ruleset.ruleset_id,
        player_id=state.active_player.player_id,
        agent_id=state.active_player.agent_id,
        round_number=state.round_state.round_number,
        turn_number=state.round_state.turn_number,
        random_seed=state.random_seed,
        public_state_ref=_public_state_ref(state),
        payload=payload,
    )


def _public_state_ref(state: GameState) -> str:
    return f"{state.game_id}:turn:{state.round_state.turn_number}"


def _record_public_snapshot(snapshots: dict[str, dict], state: GameState) -> None:
    snapshots[_public_state_ref(state)] = to_public_state(state).model_dump(mode="json")


def _emit_run_started(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    agents: list[AgentPolicy],
) -> None:
    sink.emit(
        _base_event(
            EventName.SIMULATION_RUN_STARTED,
            state,
            simulation_run_id,
            player_count=len(state.players),
            agents=[agent.agent_id for agent in agents],
        )
    )


def _emit_game_started(sink: InMemoryEventSink, state: GameState, simulation_run_id: str) -> None:
    public_state = to_public_state(state)
    sink.emit(
        _base_event(
            EventName.GAME_STARTED,
            state,
            simulation_run_id,
            bird_deck_count=public_state.bird_deck_count,
            bonus_deck_count=public_state.bonus_deck_count,
            bird_tray=[card.common_name for card in state.bird_tray],
            round_goals=[goal.name for goal in state.round_goals],
        )
    )


def _emit_round_started(sink: InMemoryEventSink, state: GameState, simulation_run_id: str) -> None:
    sink.emit(
        _base_event(
            EventName.ROUND_STARTED,
            state,
            simulation_run_id,
            action_cubes={
                player.player_id: player.action_cubes_available for player in state.players
            },
        )
    )


def _emit_turn_started(sink: InMemoryEventSink, state: GameState, simulation_run_id: str) -> None:
    sink.emit(_base_event(EventName.TURN_STARTED, state, simulation_run_id))


def _emit_legal_actions(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    legal_actions: list[LegalAction],
) -> None:
    sink.emit(
        _base_event(
            EventName.LEGAL_ACTIONS_GENERATED,
            state,
            simulation_run_id,
            legal_action_count=len(legal_actions),
            legal_actions=[action.model_dump(mode="json") for action in legal_actions],
        )
    )


def _emit_action_selected(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    agent_id: str | None,
    action: LegalAction,
) -> None:
    sink.emit(
        _base_event(
            EventName.ACTION_SELECTED,
            state,
            simulation_run_id,
            agent_id=agent_id,
            action=action.model_dump(mode="json"),
        )
    )


def _emit_action_resolved(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    player_id: str,
    action: LegalAction,
) -> None:
    sink.emit(
        _base_event(
            EventName.ACTION_RESOLVED,
            state,
            simulation_run_id,
            acting_player_id=player_id,
            action=action.model_dump(mode="json"),
        )
    )


def _emit_game_ended(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    outcome: GameOutcome,
) -> None:
    score_breakdowns = {
        player.player_id: asdict(score_player(state, player.player_id)) for player in state.players
    }
    sink.emit(
        _base_event(
            EventName.GAME_ENDED,
            state,
            simulation_run_id,
            outcome=asdict(outcome),
            score_breakdowns=score_breakdowns,
        )
    )
