"""Single-game simulation runner."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from inspect import signature
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from wingspan_ai.agents import profiling
from wingspan_ai.agents.forced_play import grant_opening_food, inject_opening_cards
from wingspan_ai.agents.profiling import DEFAULT_PROFILE_MODE, PROFILE_MODES
from wingspan_ai.agents.setup import InitialSelectionContext
from wingspan_ai.content.schemas import ContentCatalog, Habitat
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import (
    ROUND_GOAL_GREEN_SCORES,
    _count_round_goal_items,
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
    opening_hand_overrides: dict[str, list[str]] | None = None,
    opening_food_bonus: dict[str, int] | None = None,
    decision_profile_mode: str = DEFAULT_PROFILE_MODE,
) -> SimulationResult:
    """Run one seeded game and return final state, outcome, and telemetry.

    ``decision_profile_mode`` is ``"off"``, ``"summary"`` (per-node totals on
    every decision, the default) or ``"tree"`` (the full node tree as well).

    ``opening_hand_overrides`` maps a player id to birds swapped into that
    player's dealt hand from the deck before the opening choice (the forced
    keep-and-play instrument). They are recorded in ``game_started`` and
    re-applied by the replay validator.
    """

    if len(agents) < 1:
        raise ValueError("run_single_game requires at least one agent")
    if decision_profile_mode not in PROFILE_MODES:
        raise ValueError(f"decision_profile_mode must be one of {PROFILE_MODES}")

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
    injection_missing: dict[str, list[str]] = {}
    for player_id, bird_names in (opening_hand_overrides or {}).items():
        missing = inject_opening_cards(state, player_id, list(bird_names))
        if missing:
            injection_missing[player_id] = missing
    bird_discards = []
    bonus_discards = []
    setup_selection_events: list[dict] = []
    for player, agent in zip(state.players, agents, strict=True):
        player.agent_id = agent.agent_id
        with profiling.activate("choose_initial_selection") as setup_profiler:
            selection, selection_source, setup_policy_id = _choose_agent_initial_selection(
                agent,
                player,
                _initial_selection_context(state),
            )
        setup_profile = setup_profiler.finish().payload(decision_profile_mode)
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
                "discarded_bird_names": [card.common_name for card in discarded_birds_for_player],
                "discarded_bonus_card_names": [card.name for card in discarded_bonus_for_player],
                "decision_profile": setup_profile,
            }
        )
    state.decks.bird_discard.extend(bird_discards)
    state.decks.bonus_discard.extend(bonus_discards)
    # A flat food grant (every type) after the opening choice has set the
    # starting food, so forced pairs with awkward costs can complete; identical
    # across a design's arms, so it cancels in contrasts.
    for player_id, count in (opening_food_bonus or {}).items():
        grant_opening_food(state, player_id, count)

    sink = InMemoryEventSink()
    public_state_snapshots: dict[str, dict] = {}
    _record_public_snapshot(public_state_snapshots, state)
    _emit_run_started(sink, state, resolved_run_id, agents)
    for setup_payload in setup_selection_events:
        _emit_setup_selection_applied(sink, state, resolved_run_id, setup_payload)
    _emit_game_started(
        sink,
        state,
        resolved_run_id,
        opening_hand_overrides=opening_hand_overrides,
        injection_missing=injection_missing,
        opening_food_bonus=opening_food_bonus,
    )
    _emit_round_started(sink, state, resolved_run_id)

    turns_played = 0
    terminal_reason = "game_over"
    current_round = state.round_state.round_number
    # (player_id, bird name) -> round it was played, for the end-of-game scorecard.
    rounds_played: dict[tuple[str, str], int] = {}

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
        with profiling.activate("select_action") as decision_profiler:
            action = agent.choose_action(state)
        action_selection_elapsed_ms = (perf_counter() - action_selection_started_at) * 1000
        decision_profile = decision_profiler.finish().payload(decision_profile_mode)
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
            decision_profile=decision_profile,
        )
        action_state = state
        previous_round = state.round_state.round_number
        if action.action_type == ActionType.PLAY_BIRD and action.bird_common_name:
            rounds_played.setdefault(
                (active_player.player_id, action.bird_common_name), previous_round
            )
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
        _notify_agents_of_action(agents, action_state, action, active_player.player_id)

        round_ended = (
            state.round_state.round_number != previous_round or state.round_state.game_over
        )
        if round_ended:
            # Keyed on the transition that ended the round, so the last
            # round's goal is recorded too (the game-over branch of
            # ``_advance_turn`` never reaches a new round number).
            _emit_round_goal_scored(sink, action_state, state, resolved_run_id, previous_round)
            _emit_round_score_snapshot(sink, state, resolved_run_id, previous_round)
        if round_ended and not state.round_state.game_over:
            _emit_round_started(sink, state, resolved_run_id)
            current_round = state.round_state.round_number

    if turns_played >= max_turns and not state.round_state.game_over:
        terminal_reason = "max_turns_reached"

    outcome = _build_outcome(state, resolved_run_id, random_seed, turns_played, terminal_reason)
    _emit_bird_scorecards(sink, state, resolved_run_id, rounds_played)
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


def _notify_agents_of_action(
    agents: Sequence[AgentPolicy],
    state_before: GameState,
    action: LegalAction,
    acting_player_id: str,
) -> None:
    """Let observing agents update beliefs from a resolved action.

    The hook is optional and read-only: it receives the pre-action state so an
    observer sees exactly what was visible when the choice was made, and it must
    not mutate game state. Only non-acting agents are notified, because an agent
    does not need to infer its own type.
    """

    for agent in agents:
        observer = getattr(agent, "observe_action", None)
        if observer is None:
            continue
        observer(state_before, action, acting_player_id)


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


def _emit_game_started(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    *,
    opening_hand_overrides: dict[str, list[str]] | None = None,
    injection_missing: dict[str, list[str]] | None = None,
    opening_food_bonus: dict[str, int] | None = None,
) -> None:
    public_state = to_public_state(state)
    payload = {
        "bird_deck_count": public_state.bird_deck_count,
        "bonus_deck_count": public_state.bonus_deck_count,
        "bird_tray": [card.common_name for card in state.bird_tray],
        "round_goals": [goal.name for goal in state.round_goals],
    }
    if opening_hand_overrides:
        payload["opening_hand_overrides"] = {
            player_id: list(names) for player_id, names in opening_hand_overrides.items()
        }
        payload["injection_missing"] = dict(injection_missing or {})
    if opening_food_bonus:
        payload["opening_food_bonus"] = dict(opening_food_bonus)
    sink.emit(_base_event(EventName.GAME_STARTED, state, simulation_run_id, **payload))


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


def _emit_round_goal_scored(
    sink: InMemoryEventSink,
    before: GameState,
    after: GameState,
    simulation_run_id: str,
    round_number: int,
) -> None:
    """Record one round's competitive goal: counts, placement points, margin.

    Emitted from the transition that ended the round, so ``after`` is the
    state the goal was scored on (teal powers resolve first, the tray
    refresh does not touch boards, so the counts here are the counts at
    scoring time). Points are the per-player delta in ``round_goal_points``,
    which is what ``score_round_goal_competitive`` just awarded.

    The taxonomy has promised this event since 2026-05; until 2026-09-22 the
    only way to read a goal outcome was to replay the game
    (``docs/events/simulation_event_taxonomy.md``).
    """

    goal_index = round_number - 1
    if goal_index < 0 or goal_index >= len(after.round_goals):
        return
    goal = after.round_goals[goal_index]
    counts = {
        player.player_id: _count_round_goal_items(goal.name.lower(), player)
        for player in after.players
    }
    points = {
        player.player_id: player.round_goal_points
        - next(p.round_goal_points for p in before.players if p.player_id == player.player_id)
        for player in after.players
    }
    ranked = sorted(counts.values(), reverse=True)
    top = ranked[0] if ranked else 0
    # Margin over the next *player*, so a tie for first is 0 — the quantity
    # "how many more items would second place have needed".
    runner_up = ranked[1] if len(ranked) > 1 else 0
    winners = [player_id for player_id, count in counts.items() if count == top and count > 0]
    sink.emit(
        _base_event(
            EventName.ROUND_GOAL_SCORED,
            after,
            simulation_run_id,
            goal_round=round_number,
            goal_name=goal.name,
            counts=counts,
            points_awarded=points,
            agent_ids={player.player_id: player.agent_id for player in after.players},
            # Placement scale for this round (4/1, 5/2/1, 6/3/2, 7/4/3): what
            # first place was worth over second, and what the margin was.
            placement_scores=list(ROUND_GOAL_GREEN_SCORES.get(round_number, ())),
            top_count=top,
            margin=top - runner_up,
            winner_player_ids=sorted(winners),
            contested=len(winners) > 1,
            nobody_qualified=top == 0,
        )
    )


def _emit_round_score_snapshot(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    round_number: int,
) -> None:
    """One row per player per round boundary: score so far and engine state.

    The score taxonomy has asked for "cumulative score by round" and
    "per-round delta" since 2026-05 and could not answer either: only the final
    score was ever emitted, so `kpi_taxonomy_findings.md` carries both as
    unsupported. Differencing consecutive snapshots gives both for free.

    It is also the one blocker for any model of score *trajectory* -- a Markov
    chain over rounds cannot be fit without round states
    (`docs/agents/gaussian_markov_value_agent.md`). The fields are therefore
    chosen to be a usable state vector, not just a score: counts that drive
    future scoring (birds, capacity, food, hand) alongside the six score
    categories, all read directly off the state so this costs nothing.

    ``round_number`` is the round that just ended. Emitted after that round's
    goal is scored, so ``round_goal_points`` here includes it.
    """

    for player in state.players:
        breakdown = score_player(state, player.player_id)
        slots = [slot for slots in player.habitats.values() for slot in slots]
        sink.emit(
            SimulationEvent(
                event_name=EventName.ROUND_SCORE_SNAPSHOT,
                simulation_run_id=simulation_run_id,
                game_id=state.game_id,
                ruleset_id=state.ruleset.ruleset_id,
                player_id=player.player_id,
                agent_id=player.agent_id,
                round_number=round_number,
                random_seed=state.random_seed,
                global_turn_number=state.round_state.global_turn_number,
                payload={
                    "round_ended": round_number,
                    "total_score": breakdown.total,
                    "bird_points": breakdown.bird_points,
                    "bonus_points": breakdown.bonus_points,
                    "round_goal_points": breakdown.round_goal_points,
                    "egg_points": breakdown.egg_points,
                    "cached_food_points": breakdown.cached_food_points,
                    "tucked_card_points": breakdown.tucked_card_points,
                    # Engine state: what the next round has to work with.
                    "birds_in_play": len(slots),
                    "birds_by_habitat": {
                        habitat.value: len(player.habitats[habitat]) for habitat in Habitat
                    },
                    "eggs_on_board": sum(slot.eggs for slot in slots),
                    "egg_capacity_left": player.available_egg_capacity,
                    "cached_food_on_board": sum(slot.cached_food for slot in slots),
                    "tucked_cards_on_board": sum(slot.tucked_cards for slot in slots),
                    "food_tokens_held": sum(player.food_tokens.values()),
                    "food_by_type": {
                        food.value: count
                        for food, count in player.food_tokens.items()
                        if count
                    },
                    "hand_size": len(player.hand),
                    "bonus_cards_held": len(player.bonus_cards),
                    "action_cubes_available": player.action_cubes_available,
                },
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
    decision_profile: dict | None = None,
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
        "decision_profile": decision_profile,
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


def _emit_bird_scorecards(
    sink: InMemoryEventSink,
    state: GameState,
    simulation_run_id: str,
    rounds_played: dict[tuple[str, str], int],
) -> None:
    """One event per player listing every played bird and what it ended up holding.

    Feeds the bird-value study: printed points, eggs, cached food, tucked
    cards and power activations per bird, with the round it was played and
    the bonus cards it counts toward.
    """

    for player in state.players:
        birds = []
        for habitat in Habitat:
            for slot_index, slot in enumerate(player.habitats[habitat]):
                birds.append(
                    {
                        "common_name": slot.card.common_name,
                        "habitat": habitat.value,
                        "slot_index": slot_index,
                        "round_played": rounds_played.get(
                            (player.player_id, slot.card.common_name)
                        ),
                        "victory_points": slot.card.victory_points,
                        "eggs": slot.eggs,
                        "cached_food": slot.cached_food,
                        "tucked_cards": slot.tucked_cards,
                        "activations": slot.activations,
                        "power_yield": dict(slot.power_yield),
                        "power_color": slot.card.power.color.value,
                        "bonus_card_tags": sorted(slot.card.bonus_card_tags),
                    }
                )
        sink.emit(
            _base_event(
                EventName.BIRD_SCORECARD,
                state,
                simulation_run_id,
                player_id=player.player_id,
                agent_id=player.agent_id,
                bonus_card_names=[card.name for card in player.bonus_cards],
                birds=birds,
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
