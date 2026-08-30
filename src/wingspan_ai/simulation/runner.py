"""Single-game simulation runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from inspect import signature
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from wingspan_ai.agents.setup import InitialSelectionContext
from wingspan_ai.content.schemas import ContentCatalog
from wingspan_ai.rules.actions import LegalAction, render_action
from wingspan_ai.rules.base_game import (
    apply_action,
    apply_initial_selection_choice,
    choose_default_initial_selection,
    legal_actions_for_current_player,
    score_player,
    setup_base_game,
)
from wingspan_ai.simulation.replay import state_hash
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
        apply_initial_selection=False,
    )
    bird_discards = []
    bonus_discards = []
    setup_selection_events: list[dict] = []
    for player, agent in zip(state.players, agents, strict=True):
        player.agent_id = agent.agent_id
        selection, selection_source, setup_policy_id = _choose_agent_initial_selection(
            agent,
            player,
            _initial_selection_context(state),
        )
        discarded_birds_for_player, discarded_bonus_for_player = apply_initial_selection_choice(
            player, selection
        )
        bird_discards.extend(discarded_birds_for_player)
        bonus_discards.extend(discarded_bonus_for_player)
        setup_selection_events.append(
            {
                "player_id": player.player_id,
                "agent_id": agent.agent_id,
                "selection_source": selection_source,
                "setup_policy_id": setup_policy_id,
                "kept_bird_names": list(selection.kept_bird_names),
                "kept_bonus_card_names": list(selection.kept_bonus_card_names),
                "starting_food": [food.value for food in selection.starting_food],
                "discarded_bird_names": [
                    card.common_name for card in discarded_birds_for_player
                ],
                "discarded_bonus_card_names": [
                    card.name for card in discarded_bonus_for_player
                ],
            }
        )
    state.decks.bird_discard.extend(bird_discards)
    state.decks.bonus_discard.extend(bonus_discards)

    sink = InMemoryEventSink()
    public_state_snapshots: dict[str, dict] = {}
    _record_public_snapshot(public_state_snapshots, state)
    _emit_run_started(sink, state, resolved_run_id, agents)
    for setup_payload in setup_selection_events:
        _emit_setup_selection_applied(sink, state, resolved_run_id, setup_payload)
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

        action_selection_started_at = perf_counter()
        action = agent.choose_action(state)
        action_selection_elapsed_ms = (perf_counter() - action_selection_started_at) * 1000
        if action not in legal_actions:
            raise ValueError(f"agent {agent.agent_id} selected an illegal action: {action}")

        state_hash_before = state_hash(state)
        rng_record_count_before = len(state.rng_draw_records)
        _emit_action_selected(
            sink,
            state,
            resolved_run_id,
            active_player.agent_id,
            action,
            state_hash_before=state_hash_before,
        )
        _emit_agent_decision_summary(
            sink,
            state,
            resolved_run_id,
            agent,
            legal_actions,
            action,
            action_selection_elapsed_ms=action_selection_elapsed_ms,
        )
        action_state = state
        previous_round = state.round_state.round_number
        state = apply_action(state, action)
        _record_public_snapshot(public_state_snapshots, state)
        turns_played += 1
        _emit_action_resolved(
            sink,
            action_state,
            state,
            resolved_run_id,
            active_player.player_id,
            action,
            state_hash_before=state_hash_before,
            state_hash_after=state_hash(state),
            rng_draws=[
                record.model_dump(mode="json")
                for record in state.rng_draw_records[rng_record_count_before:]
            ],
        )

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


def _initial_selection_context(state: GameState) -> InitialSelectionContext:
    return InitialSelectionContext(
        bird_tray=tuple(state.bird_tray),
        round_goal_names=tuple(goal.name for goal in state.round_goals),
        round_state=state.round_state,
        player_count=len(state.players),
    )


def _choose_agent_initial_selection(
    agent: AgentPolicy,
    player,
    context: InitialSelectionContext,
):
    selection_chooser = getattr(agent, "choose_initial_selection", None)
    if callable(selection_chooser):
        parameters = signature(selection_chooser).parameters
        selection = (
            selection_chooser(player)
            if len(parameters) == 1
            else selection_chooser(player, context)
        )
        setup_policy = getattr(agent, "setup_policy", None)
        return selection, "agent", getattr(setup_policy, "policy_id", None)
    return choose_default_initial_selection(player), "default", "default_setup_v1"


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
        round_action_number=state.round_state.round_action_number,
        global_turn_number=state.round_state.global_turn_number,
        random_seed=state.random_seed,
        public_state_ref=_public_state_ref(state),
        payload=payload,
    )


def _public_state_ref(state: GameState) -> str:
    return f"{state.game_id}:global_turn:{state.round_state.global_turn_number}"


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


def _emit_setup_selection_applied(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    payload: dict,
) -> None:
    sink.emit(
        SimulationEvent(
            event_name=EventName.SETUP_SELECTION_APPLIED,
            simulation_run_id=simulation_run_id,
            game_id=state.game_id,
            ruleset_id=state.ruleset.ruleset_id,
            player_id=payload["player_id"],
            agent_id=payload["agent_id"],
            round_number=state.round_state.round_number,
            turn_number=state.round_state.turn_number,
            round_action_number=state.round_state.round_action_number,
            global_turn_number=state.round_state.global_turn_number,
            random_seed=state.random_seed,
            public_state_ref=_public_state_ref(state),
            private_state_included=True,
            payload=payload,
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
            legal_action_labels=[render_action(action) for action in legal_actions],
        )
    )


def _emit_action_selected(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    agent_id: str | None,
    action: LegalAction,
    *,
    state_hash_before: str,
) -> None:
    sink.emit(
        _base_event(
            EventName.ACTION_SELECTED,
            state,
            simulation_run_id,
            agent_id=agent_id,
            action=action.model_dump(mode="json"),
            action_label=render_action(action),
            state_hash_before=state_hash_before,
        )
    )


def _emit_agent_decision_summary(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    agent: AgentPolicy,
    legal_actions: list[LegalAction],
    action: LegalAction,
    *,
    action_selection_elapsed_ms: float,
) -> None:
    summarizer = getattr(agent, "summarize_decision", None)
    summary_started_at = perf_counter()
    if callable(summarizer):
        payload = summarizer(state, legal_actions, action)
    else:
        payload = {
            "policy": "unknown",
            "legal_action_count": len(legal_actions),
            "selected_action_type": action.action_type.value,
        }
    summary_elapsed_ms = (perf_counter() - summary_started_at) * 1000
    payload = {
        **payload,
        "action_selection_elapsed_ms": round(action_selection_elapsed_ms, 3),
        "decision_summary_elapsed_ms": round(summary_elapsed_ms, 3),
        "decision_total_elapsed_ms": round(
            action_selection_elapsed_ms + summary_elapsed_ms,
            3,
        ),
    }
    sink.emit(
        _base_event(
            EventName.AGENT_DECISION_SUMMARY,
            state,
            simulation_run_id,
            **payload,
        )
    )


def _emit_action_resolved(
    sink: InMemoryEventSink,
    action_state: GameState,
    next_state: GameState,
    simulation_run_id: str,
    player_id: str,
    action: LegalAction,
    *,
    state_hash_before: str,
    state_hash_after: str,
    rng_draws: list[dict],
) -> None:
    sink.emit(
        _base_event(
            EventName.ACTION_RESOLVED,
            action_state,
            simulation_run_id,
            acting_player_id=player_id,
            action=action.model_dump(mode="json"),
            action_label=render_action(action),
            state_hash_before=state_hash_before,
            state_hash_after=state_hash_after,
            next_public_state_ref=_public_state_ref(next_state),
            next_round_number=next_state.round_state.round_number,
            next_turn_number=next_state.round_state.turn_number,
            next_round_action_number=next_state.round_state.round_action_number,
            next_global_turn_number=next_state.round_state.global_turn_number,
            next_active_player_id=next_state.active_player.player_id,
            rng_draws=rng_draws,
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
