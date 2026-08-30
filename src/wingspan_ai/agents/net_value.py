"""Margin-aware agent that estimates the next opponent response."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from wingspan_ai.agents.potential_points import evaluate_state_potential
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, FoodType, Habitat
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import apply_action, legal_actions_for_current_player
from wingspan_ai.state.models import (
    GameState,
    PublicGameState,
    PublicPlayerState,
    to_public_state,
)

PUBLIC_OBSERVATION_BELIEF_MODEL_ID = "public_observation_belief_v0"


@dataclass(frozen=True)
class OpponentResponseEstimate:
    """Best visible next response for the next active opponent."""

    opponent_id: str | None
    response_action_type: str | None
    response_value_delta: float
    response_legal_action_count: int
    response_candidate_values: tuple[dict[str, float | str], ...] = ()

    def telemetry_payload(self) -> dict:
        return {
            "opponent_id": self.opponent_id,
            "response_action_type": self.response_action_type,
            "response_value_delta": round(self.response_value_delta, 3),
            "response_legal_action_count": self.response_legal_action_count,
            "response_candidate_values": [
                {
                    **candidate,
                    "value_delta": round(float(candidate["value_delta"]), 3),
                }
                for candidate in self.response_candidate_values
            ],
        }


@dataclass(frozen=True)
class NetValueBreakdown:
    """Score-margin-oriented value estimate for an action."""

    self_potential_delta: float
    opponent_immediate_delta: float
    opponent_response_delta: float
    shared_denial_value: float

    @property
    def net_margin_delta(self) -> float:
        return (
            self.self_potential_delta
            - self.opponent_immediate_delta
            - self.opponent_response_delta
            + self.shared_denial_value
        )

    def telemetry_payload(self) -> dict:
        payload = asdict(self)
        payload["net_margin_delta"] = self.net_margin_delta
        return {key: round(value, 3) for key, value in payload.items()}


@dataclass(frozen=True)
class ActionNetValueEvaluation:
    """Net-value estimate for one legal action."""

    action: LegalAction
    breakdown: NetValueBreakdown
    opponent_response: OpponentResponseEstimate

    def telemetry_payload(self) -> dict:
        return {
            "action": self.action.model_dump(mode="json"),
            "action_label": render_action(self.action),
            "breakdown": self.breakdown.telemetry_payload(),
            "opponent_response": self.opponent_response.telemetry_payload(),
        }


@dataclass(frozen=True)
class PublicOpponentBelief:
    """Opponent estimates derived without hidden hand, bonus, or deck-order access."""

    player_id: str
    hand_count: int
    bonus_card_count: int
    food_demand: dict[FoodType, float]
    expected_card_quality: float
    expected_bonus_value: float


@dataclass(frozen=True)
class PublicResponseCandidate:
    """Publicly estimated opponent action-family response."""

    action_type: ActionType
    value_delta: float


@dataclass
class PublicOpponentBeliefModel:
    """Lightweight public-observation belief model for opponent potential.

    This is not Bayesian sampling yet. It is the first enforceable information
    boundary: estimates use public player boards, visible resources, tray cards,
    hand counts, bonus-card counts, round goals, and birdfeeder dice.
    """

    model_id: str = PUBLIC_OBSERVATION_BELIEF_MODEL_ID

    def estimate(
        self,
        state: GameState,
        *,
        observer_player_id: str,
        opponent_id: str,
    ) -> PublicOpponentBelief:
        del observer_player_id
        public_state = to_public_state(state)
        public_player = _public_player(public_state, opponent_id)
        food_demand = _public_food_demand(public_state, public_player)
        return PublicOpponentBelief(
            player_id=opponent_id,
            hand_count=public_player.hand_count,
            bonus_card_count=public_player.bonus_card_count,
            food_demand=food_demand,
            expected_card_quality=_visible_card_quality_prior(public_state),
            expected_bonus_value=_public_bonus_prior(public_player),
        )

    def potential_total(
        self,
        state: GameState,
        *,
        observer_player_id: str,
        opponent_id: str,
    ) -> float:
        public_state = to_public_state(state)
        public_player = _public_player(public_state, opponent_id)
        belief = self.estimate(
            state,
            observer_player_id=observer_player_id,
            opponent_id=opponent_id,
        )
        return _public_potential_total(public_state, public_player, belief)

    def best_response(
        self,
        state: GameState,
        *,
        observer_player_id: str,
        opponent_id: str,
        max_response_actions: int | None,
    ) -> OpponentResponseEstimate:
        if state.round_state.game_over:
            return OpponentResponseEstimate(
                opponent_id=None,
                response_action_type=None,
                response_value_delta=0.0,
                response_legal_action_count=0,
            )

        public_state = to_public_state(state)
        public_player = _public_player(public_state, opponent_id)
        if public_player.action_cubes_available <= 0:
            return OpponentResponseEstimate(
                opponent_id=opponent_id,
                response_action_type=None,
                response_value_delta=0.0,
                response_legal_action_count=0,
            )

        belief = self.estimate(
            state,
            observer_player_id=observer_player_id,
            opponent_id=opponent_id,
        )
        candidates = _public_response_candidates(public_state, public_player, belief)
        candidate_count = len(candidates)
        if max_response_actions is not None:
            candidates = sorted(candidates, key=lambda item: item.value_delta, reverse=True)[
                :max_response_actions
            ]
        if not candidates:
            return OpponentResponseEstimate(
                opponent_id=opponent_id,
                response_action_type=None,
                response_value_delta=0.0,
                response_legal_action_count=0,
            )

        response = max(candidates, key=lambda item: item.value_delta)
        return OpponentResponseEstimate(
            opponent_id=opponent_id,
            response_action_type=response.action_type.value,
            response_value_delta=response.value_delta,
            response_legal_action_count=candidate_count,
            response_candidate_values=tuple(
                {
                    "action_type": candidate.action_type.value,
                    "value_delta": candidate.value_delta,
                }
                for candidate in sorted(candidates, key=lambda item: item.value_delta, reverse=True)
            ),
        )


@dataclass
class NetValueOpponentResponseAgent:
    """Choose actions by expected score-margin gain after the next opponent response.

    Opponent estimates use public observations plus a first belief heuristic.
    The acting player's own value can still use their private hand and bonus cards,
    matching the information available to that player.
    """

    agent_id: str = "net_value_opponent_response"
    denial_weight: float = 1.0
    max_candidate_actions: int | None = 12
    max_opponent_response_actions: int | None = 8
    top_alternatives: int = 5
    opponent_belief_model: PublicOpponentBeliefModel = field(
        default_factory=PublicOpponentBeliefModel,
    )
    _last_evaluations: list[ActionNetValueEvaluation] = field(default_factory=list, init=False)

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError(
                "NetValueOpponentResponseAgent cannot select from an empty action list"
            )

        evaluations = self.evaluate_actions(state, legal_actions)
        self._last_evaluations = evaluations
        return max(
            evaluations,
            key=lambda item: (
                item.breakdown.net_margin_delta,
                item.breakdown.self_potential_delta,
                item.breakdown.shared_denial_value,
            ),
        ).action

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def evaluate_actions(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
    ) -> list[ActionNetValueEvaluation]:
        player_id = state.active_player.player_id
        candidate_actions = _candidate_actions(
            state,
            legal_actions,
            max_candidate_actions=self.max_candidate_actions,
        )
        before_self = evaluate_state_potential(state, player_id).total
        opponent_ids = [
            player.player_id for player in state.players if player.player_id != player_id
        ]
        before_opponents = {
            opponent_id: self.opponent_belief_model.potential_total(
                state,
                observer_player_id=player_id,
                opponent_id=opponent_id,
            )
            for opponent_id in opponent_ids
        }

        evaluations = []
        for action in candidate_actions:
            own_next_state = apply_action(state, action)
            self_delta = evaluate_state_potential(own_next_state, player_id).total - before_self
            opponent_immediate_delta = sum(
                self.opponent_belief_model.potential_total(
                    own_next_state,
                    observer_player_id=player_id,
                    opponent_id=opponent_id,
                )
                - before_opponents[opponent_id]
                for opponent_id in opponent_ids
            )
            opponent_response = _estimate_next_opponent_response(
                own_next_state,
                observer_player_id=player_id,
                belief_model=self.opponent_belief_model,
                max_response_actions=self.max_opponent_response_actions,
            )
            denial_value = (
                self.denial_weight
                * _shared_resource_denial_value(
                    state,
                    action,
                    observer_player_id=player_id,
                    opponent_ids=opponent_ids,
                    belief_model=self.opponent_belief_model,
                )
            )
            evaluations.append(
                ActionNetValueEvaluation(
                    action=action,
                    breakdown=NetValueBreakdown(
                        self_potential_delta=self_delta,
                        opponent_immediate_delta=opponent_immediate_delta,
                        opponent_response_delta=opponent_response.response_value_delta,
                        shared_denial_value=denial_value,
                    ),
                    opponent_response=opponent_response,
                )
            )
        return evaluations

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        evaluations = self._last_evaluations or self.evaluate_actions(state, legal_actions)
        selected = next(
            evaluation for evaluation in evaluations if evaluation.action == selected_action
        )
        ranked = sorted(
            evaluations,
            key=lambda item: (
                item.breakdown.net_margin_delta,
                item.breakdown.self_potential_delta,
                item.breakdown.shared_denial_value,
            ),
            reverse=True,
        )
        return {
            "policy": "net_value_opponent_response",
            "opponent_model": self.opponent_belief_model.model_id,
            "information_boundary": (
                "Opponent potential, denial, and response estimates use public observations "
                "plus belief heuristics rather than hidden opponent hands or bonus cards."
            ),
            "legal_action_count": len(legal_actions),
            "evaluated_action_count": len(evaluations),
            "max_candidate_actions": self.max_candidate_actions,
            "max_opponent_response_actions": self.max_opponent_response_actions,
            "selected_action_type": selected_action.action_type.value,
            "selected_action_label": render_action(selected_action),
            "selected_breakdown": selected.breakdown.telemetry_payload(),
            "selected_opponent_response": selected.opponent_response.telemetry_payload(),
            "top_alternatives": [
                evaluation.telemetry_payload() for evaluation in ranked[: self.top_alternatives]
            ],
        }


def _estimate_next_opponent_response(
    state: GameState,
    *,
    observer_player_id: str,
    belief_model: PublicOpponentBeliefModel,
    max_response_actions: int | None,
) -> OpponentResponseEstimate:
    if state.round_state.game_over:
        return OpponentResponseEstimate(
            opponent_id=None,
            response_action_type=None,
            response_value_delta=0.0,
            response_legal_action_count=0,
    )

    opponent_id = _next_opponent_player_id(state, observer_player_id)
    if opponent_id is None:
        return OpponentResponseEstimate(
            opponent_id=None,
            response_action_type=None,
            response_value_delta=0.0,
            response_legal_action_count=0,
        )
    return belief_model.best_response(
        state,
        observer_player_id=observer_player_id,
        opponent_id=opponent_id,
        max_response_actions=max_response_actions,
    )


def _next_opponent_player_id(state: GameState, observer_player_id: str) -> str | None:
    player_count = len(state.players)
    if player_count <= 1:
        return None
    for offset in range(player_count):
        player_index = (state.round_state.active_player_index + offset) % player_count
        player = state.players[player_index]
        if player.player_id != observer_player_id and player.action_cubes_available > 0:
            return player.player_id
    return None


def _candidate_actions(
    state: GameState,
    legal_actions: list[LegalAction],
    *,
    max_candidate_actions: int | None,
) -> list[LegalAction]:
    if max_candidate_actions is None or len(legal_actions) <= max_candidate_actions:
        return legal_actions
    ranked = sorted(
        legal_actions,
        key=lambda action: _candidate_priority(state, action),
        reverse=True,
    )
    selected: list[LegalAction] = []
    for action_type in (
        ActionType.PLAY_BIRD,
        ActionType.LAY_EGGS,
        ActionType.DRAW_CARDS,
        ActionType.GAIN_FOOD,
    ):
        family_action = next(
            (action for action in ranked if action.action_type == action_type),
            None,
        )
        if family_action is not None:
            selected.append(family_action)
        if len(selected) >= max_candidate_actions:
            return selected

    for action in ranked:
        if action not in selected:
            selected.append(action)
        if len(selected) >= max_candidate_actions:
            return selected
    return selected


def _candidate_priority(state: GameState, action: LegalAction) -> float:
    if action.action_type == ActionType.PLAY_BIRD:
        return 40
    if action.action_type == ActionType.LAY_EGGS:
        return 30
    if action.action_type == ActionType.DRAW_CARDS:
        return 20 + _tray_card_denial_value(state, action)
    if action.action_type == ActionType.GAIN_FOOD:
        opponent_ids = [
            player.player_id
            for player in state.players
            if player.player_id != state.active_player.player_id
        ]
        return 10 + _food_denial_value(
            state,
            action,
            observer_player_id=state.active_player.player_id,
            opponent_ids=opponent_ids,
            belief_model=PublicOpponentBeliefModel(),
        )
    return 0


def _shared_resource_denial_value(
    state: GameState,
    action: LegalAction,
    *,
    observer_player_id: str,
    opponent_ids: list[str],
    belief_model: PublicOpponentBeliefModel,
) -> float:
    if action.action_type == ActionType.DRAW_CARDS:
        return _tray_card_denial_value(state, action)
    if action.action_type == ActionType.GAIN_FOOD:
        return _food_denial_value(
            state,
            action,
            observer_player_id=observer_player_id,
            opponent_ids=opponent_ids,
            belief_model=belief_model,
        )
    return 0.0


def _tray_card_denial_value(state: GameState, action: LegalAction) -> float:
    tray_indices = action.tray_indices or (
        (action.tray_index,) if action.tray_index is not None else ()
    )
    value = 0.0
    for tray_index in tray_indices:
        if tray_index is None or tray_index >= len(state.bird_tray):
            continue
        value += _public_card_threat_value(state.bird_tray[tray_index])
    return value


def _food_denial_value(
    state: GameState,
    action: LegalAction,
    *,
    observer_player_id: str,
    opponent_ids: list[str],
    belief_model: PublicOpponentBeliefModel,
) -> float:
    selected_foods = action.food_types or ((action.food_type,) if action.food_type else ())
    if not selected_foods:
        return 0.0
    opponent_demand: Counter[FoodType] = Counter()
    for opponent_id in opponent_ids:
        belief = belief_model.estimate(
            state,
            observer_player_id=observer_player_id,
            opponent_id=opponent_id,
        )
        opponent_demand.update(
            {
                food_type: demand
                for food_type, demand in belief.food_demand.items()
                if demand > 0
            }
        )
    value = 0.0
    for food_type in selected_foods:
        if food_type in state.birdfeeder.dice:
            value += 0.25
        value += min(opponent_demand.get(food_type, 0.0), 1.5) * 0.35
    return value


def _public_player(public_state: PublicGameState, player_id: str) -> PublicPlayerState:
    return next(player for player in public_state.players if player.player_id == player_id)


def _public_potential_total(
    public_state: PublicGameState,
    player: PublicPlayerState,
    belief: PublicOpponentBelief,
) -> float:
    turns_remaining = player.action_cubes_available
    visible_score = _visible_score(player)
    if public_state.round_state.game_over or turns_remaining <= 0:
        return visible_score

    food_tokens = sum(player.food_tokens.values())
    food_demand = sum(belief.food_demand.values())
    playable_bird_prior = min(player.hand_count, turns_remaining) * belief.expected_card_quality
    food_conversion = min(food_tokens, food_demand) * 0.7 + max(food_tokens - food_demand, 0) * 0.1
    egg_conversion = min(
        player.action_cubes_available * _public_egg_rate(player),
        _egg_room(player),
    )
    card_conversion = min(player.hand_count, turns_remaining) * 0.25
    engine_value = sum(
        _public_habitat_engine_value(public_state, player, habitat)
        for habitat in (Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND)
    )
    return (
        visible_score
        + playable_bird_prior
        + food_conversion
        + egg_conversion * 0.55
        + card_conversion
        + engine_value
        + belief.expected_bonus_value
        + _public_round_goal_potential(public_state, player)
    )


def _visible_score(player: PublicPlayerState) -> float:
    return float(
        sum(slot.card.victory_points for slot in player.played_birds)
        + sum(slot.eggs for slot in player.played_birds)
        + sum(slot.cached_food for slot in player.played_birds)
        + sum(slot.tucked_cards for slot in player.played_birds)
        + player.round_goal_points
    )


def _public_food_demand(
    public_state: PublicGameState,
    player: PublicPlayerState,
) -> dict[FoodType, float]:
    if player.hand_count <= 0:
        return {food_type: 0.0 for food_type in BASE_FOOD_TYPES}

    demand: Counter[FoodType] = Counter()
    tray_threat_total = 0.0
    for card in public_state.bird_tray:
        card_threat = _public_card_threat_value(card)
        tray_threat_total += card_threat
        for food_type, count in card.food_cost.fixed.items():
            demand[food_type] += count * min(card_threat / 3, 1.0)

    open_slots = sum(max(5 - len(player.habitats[habitat]), 0) for habitat in Habitat)
    hidden_play_pressure = min(player.hand_count, open_slots, player.action_cubes_available)
    food_prior = max(hidden_play_pressure * 0.35, 0.0)
    if tray_threat_total <= 0:
        for food_type in BASE_FOOD_TYPES:
            demand[food_type] += food_prior / len(BASE_FOOD_TYPES)
    else:
        for food_type in BASE_FOOD_TYPES:
            demand[food_type] += food_prior

    forest_gap = max(2 - len(player.habitats[Habitat.FOREST]), 0)
    if forest_gap and player.hand_count:
        demand[FoodType.SEED] += 0.25 * forest_gap
        demand[FoodType.INVERTEBRATE] += 0.2 * forest_gap

    return {
        food_type: max(demand.get(food_type, 0.0) - player.food_tokens.get(food_type, 0), 0.0)
        for food_type in BASE_FOOD_TYPES
    }


def _visible_card_quality_prior(public_state: PublicGameState) -> float:
    if not public_state.bird_tray:
        return 1.25
    tray_values = [_public_card_threat_value(card) for card in public_state.bird_tray]
    return max(sum(tray_values) / len(tray_values), 0.75)


def _public_bonus_prior(player: PublicPlayerState) -> float:
    if player.bonus_card_count <= 0:
        return 0.0
    played_count = len(player.played_birds)
    return min(player.bonus_card_count * (1.0 + played_count * 0.12), 3.0)


def _public_response_candidates(
    public_state: PublicGameState,
    player: PublicPlayerState,
    belief: PublicOpponentBelief,
) -> list[PublicResponseCandidate]:
    candidates: list[PublicResponseCandidate] = []
    if _can_publicly_gain_food(public_state, player):
        candidates.append(
            PublicResponseCandidate(
                action_type=ActionType.GAIN_FOOD,
                value_delta=_public_gain_food_delta(public_state, player, belief),
            )
        )
    if _egg_room(player) > 0 and player.played_birds:
        candidates.append(
            PublicResponseCandidate(
                action_type=ActionType.LAY_EGGS,
                value_delta=_public_lay_eggs_delta(public_state, player),
            )
        )
    if public_state.bird_tray or public_state.bird_deck_count > 0:
        candidates.append(
            PublicResponseCandidate(
                action_type=ActionType.DRAW_CARDS,
                value_delta=_public_draw_cards_delta(public_state, player, belief),
            )
        )
    if player.hand_count > 0 and _has_open_habitat_slot(player):
        candidates.append(
            PublicResponseCandidate(
                action_type=ActionType.PLAY_BIRD,
                value_delta=_public_play_bird_delta(public_state, player, belief),
            )
        )
    return candidates


def _can_publicly_gain_food(public_state: PublicGameState, player: PublicPlayerState) -> bool:
    return bool(public_state.birdfeeder.dice) or bool(player.habitats[Habitat.FOREST])


def _public_gain_food_delta(
    public_state: PublicGameState,
    player: PublicPlayerState,
    belief: PublicOpponentBelief,
) -> float:
    food_count = _public_forest_food_rate(player)
    demand_value = 0.0
    available_food = set(public_state.birdfeeder.dice)
    for food_type, demand in belief.food_demand.items():
        if demand <= 0:
            continue
        demand_value += min(demand, food_count) * (0.6 if food_type in available_food else 0.35)
    return min(food_count * 0.9, demand_value + food_count * 0.2) + _public_habitat_engine_value(
        public_state,
        player,
        Habitat.FOREST,
    )


def _public_lay_eggs_delta(public_state: PublicGameState, player: PublicPlayerState) -> float:
    egg_count = min(_public_egg_rate(player), _egg_room(player))
    return egg_count + _public_habitat_engine_value(public_state, player, Habitat.GRASSLAND)


def _public_draw_cards_delta(
    public_state: PublicGameState,
    player: PublicPlayerState,
    belief: PublicOpponentBelief,
) -> float:
    draw_count = _public_wetland_card_rate(player)
    tray_value = sum(
        sorted((_public_card_threat_value(card) for card in public_state.bird_tray), reverse=True)[
            :draw_count
        ]
    )
    deck_prior = max(draw_count - min(draw_count, len(public_state.bird_tray)), 0) * (
        belief.expected_card_quality * 0.5
    )
    return tray_value * 0.45 + deck_prior + _public_habitat_engine_value(
        public_state,
        player,
        Habitat.WETLAND,
    )


def _public_play_bird_delta(
    public_state: PublicGameState,
    player: PublicPlayerState,
    belief: PublicOpponentBelief,
) -> float:
    del public_state
    food_ready = sum(player.food_tokens.values()) >= 1
    egg_ready = player.total_eggs >= _minimum_public_egg_cost(player)
    readiness = 1.0 if food_ready and egg_ready else 0.45 if food_ready or egg_ready else 0.2
    return readiness * (belief.expected_card_quality + belief.expected_bonus_value * 0.25 + 1.0)


def _public_habitat_engine_value(
    public_state: PublicGameState,
    player: PublicPlayerState,
    habitat: Habitat,
) -> float:
    turns_remaining = player.action_cubes_available
    if turns_remaining <= 0:
        return 0.0
    value = 0.0
    for slot in player.habitats[habitat]:
        power_text = slot.card.power.text.lower() if slot.card.power.text else ""
        if "tuck" in power_text:
            value += 0.45
        if "cache" in power_text:
            value += 0.35
        if "draw" in power_text and "[card]" in power_text:
            value += 0.3
        if "lay" in power_text and "[egg]" in power_text and slot.available_egg_capacity:
            value += 0.35
        if "gain" in power_text and any(
            f"[{food.value}]" in power_text for food in BASE_FOOD_TYPES
        ):
            value += 0.35
        if "when another player" in power_text:
            opponent_turns = sum(
                other.action_cubes_available
                for other in public_state.players
                if other.player_id != player.player_id
            )
            value += min(opponent_turns, 4) * 0.12
    return min(value, turns_remaining * 0.75)


def _public_round_goal_potential(
    public_state: PublicGameState,
    player: PublicPlayerState,
) -> float:
    goal_index = public_state.round_state.round_number - 1
    if goal_index < 0 or goal_index >= len(public_state.round_goals):
        return 0.0
    goal = public_state.round_goals[goal_index]
    goal_name = goal.name.lower()
    current_count = _public_round_goal_count(goal_name, player)
    best_other = max(
        (
            _public_round_goal_count(goal_name, other)
            for other in public_state.players
            if other.player_id != player.player_id
        ),
        default=0,
    )
    gap = max(best_other - current_count + 1, 0)
    if gap == 0:
        return 1.0
    if gap <= player.action_cubes_available:
        return 0.5
    return 0.0


def _public_round_goal_count(goal_name: str, player: PublicPlayerState) -> int:
    if "[bird]" in goal_name and "[forest]" in goal_name:
        return len(player.habitats[Habitat.FOREST])
    if "[bird]" in goal_name and "[grassland]" in goal_name:
        return len(player.habitats[Habitat.GRASSLAND])
    if "[bird]" in goal_name and "[wetland]" in goal_name:
        return len(player.habitats[Habitat.WETLAND])
    if "[egg]" in goal_name and "forest" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.FOREST])
    if "[egg]" in goal_name and "grassland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.GRASSLAND])
    if "[egg]" in goal_name and "wetland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.WETLAND])
    if "[bird]" in goal_name:
        return len(player.played_birds)
    if "[egg]" in goal_name:
        return player.total_eggs
    return 0


def _public_card_threat_value(card: BirdCard) -> float:
    return _public_card_threat_value_uncapped(card)


def _public_card_threat_value_uncapped(card: BirdCard) -> float:
    value = card.victory_points * 0.12
    if card.flocking:
        value += 0.5
    if card.predator:
        value += 0.3
    if card.bonus_card_power or card.bonus_card_tags:
        value += 0.4
    if card.power.text:
        lowered = card.power.text.lower()
        if "tuck" in lowered:
            value += 0.7
        if "cache" in lowered:
            value += 0.4
        if "draw" in lowered and "[card]" in lowered:
            value += 0.4
        if "lay" in lowered and "[egg]" in lowered:
            value += 0.4
        if "gain" in lowered and any(f"[{food.value}]" in lowered for food in BASE_FOOD_TYPES):
            value += 0.4
    return value


def _public_forest_food_rate(player: PublicPlayerState) -> int:
    forest_count = len(player.habitats[Habitat.FOREST])
    if forest_count >= 4:
        return 3
    if forest_count >= 2:
        return 2
    return 1


def _public_egg_rate(player: PublicPlayerState) -> int:
    grassland_count = len(player.habitats[Habitat.GRASSLAND])
    if grassland_count >= 4:
        return 4
    if grassland_count >= 2:
        return 3
    return 2


def _public_wetland_card_rate(player: PublicPlayerState) -> int:
    wetland_count = len(player.habitats[Habitat.WETLAND])
    if wetland_count >= 4:
        return 3
    if wetland_count >= 2:
        return 2
    return 1


def _egg_room(player: PublicPlayerState) -> int:
    return sum(slot.available_egg_capacity for slot in player.played_birds)


def _has_open_habitat_slot(player: PublicPlayerState) -> bool:
    return any(len(player.habitats[habitat]) < 5 for habitat in Habitat)


def _minimum_public_egg_cost(player: PublicPlayerState) -> int:
    open_slot_indexes = [
        len(player.habitats[habitat])
        for habitat in Habitat
        if len(player.habitats[habitat]) < 5
    ]
    if not open_slot_indexes:
        return 999
    slot_index = min(open_slot_indexes)
    if slot_index >= 4:
        return 2
    if slot_index >= 2:
        return 1
    return 0
