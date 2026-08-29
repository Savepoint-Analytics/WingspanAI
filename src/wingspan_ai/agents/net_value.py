"""Margin-aware agent that estimates the next opponent response."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from wingspan_ai.agents.potential_points import evaluate_state_potential
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, FoodType
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import apply_action, legal_actions_for_current_player
from wingspan_ai.state.models import GameState, PlayerState


@dataclass(frozen=True)
class OpponentResponseEstimate:
    """Best visible next response for the next active opponent."""

    opponent_id: str | None
    response_action_type: str | None
    response_value_delta: float
    response_legal_action_count: int

    def telemetry_payload(self) -> dict:
        return {
            **asdict(self),
            "response_value_delta": round(self.response_value_delta, 3),
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


@dataclass
class NetValueOpponentResponseAgent:
    """Choose actions by expected score-margin gain after the next opponent response.

    This first template uses simulator full state to score opponent potential. That is
    useful for controlled research plumbing, but later versions should replace it with
    public observations plus a belief model before making strategy claims.
    """

    agent_id: str = "net_value_opponent_response"
    denial_weight: float = 1.0
    max_candidate_actions: int | None = 12
    max_opponent_response_actions: int | None = 8
    top_alternatives: int = 5
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
            opponent_id: evaluate_state_potential(state, opponent_id).total
            for opponent_id in opponent_ids
        }

        evaluations = []
        for action in candidate_actions:
            own_next_state = apply_action(state, action)
            self_delta = evaluate_state_potential(own_next_state, player_id).total - before_self
            opponent_immediate_delta = sum(
                evaluate_state_potential(own_next_state, opponent_id).total
                - before_opponents[opponent_id]
                for opponent_id in opponent_ids
            )
            opponent_response = _estimate_next_opponent_response(
                own_next_state,
                max_response_actions=self.max_opponent_response_actions,
            )
            denial_value = (
                self.denial_weight
                * _shared_resource_denial_value(state, action, opponent_ids=opponent_ids)
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
            "opponent_model": "full_state_oracle_v0",
            "private_state_assumption": (
                "Scores opponent response with simulator full state; replace with beliefs "
                "before claim-grade experiments."
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
    max_response_actions: int | None,
) -> OpponentResponseEstimate:
    if state.round_state.game_over:
        return OpponentResponseEstimate(
            opponent_id=None,
            response_action_type=None,
            response_value_delta=0.0,
            response_legal_action_count=0,
        )

    opponent = state.active_player
    legal_actions = legal_actions_for_current_player(state)
    if not legal_actions:
        return OpponentResponseEstimate(
            opponent_id=opponent.player_id,
            response_action_type=None,
            response_value_delta=0.0,
            response_legal_action_count=0,
        )

    before = evaluate_state_potential(state, opponent.player_id).total
    response_actions = _candidate_actions(
        state,
        legal_actions,
        max_candidate_actions=max_response_actions,
    )
    response_scores = [
        (
            evaluate_state_potential(apply_action(state, response_action), opponent.player_id).total
            - before,
            response_action,
        )
        for response_action in response_actions
    ]
    response_delta, response_action = max(response_scores, key=lambda item: item[0])
    return OpponentResponseEstimate(
        opponent_id=opponent.player_id,
        response_action_type=response_action.action_type.value,
        response_value_delta=response_delta,
        response_legal_action_count=len(legal_actions),
    )


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
        return 10 + _food_denial_value(state, action, opponent_ids=opponent_ids)
    return 0


def _shared_resource_denial_value(
    state: GameState,
    action: LegalAction,
    *,
    opponent_ids: list[str],
) -> float:
    if action.action_type == ActionType.DRAW_CARDS:
        return _tray_card_denial_value(state, action)
    if action.action_type == ActionType.GAIN_FOOD:
        return _food_denial_value(state, action, opponent_ids=opponent_ids)
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
    opponent_ids: list[str],
) -> float:
    selected_foods = action.food_types or ((action.food_type,) if action.food_type else ())
    if not selected_foods:
        return 0.0
    opponent_demand = {
        food_type
        for player in state.players
        if player.player_id in opponent_ids
        for food_type in _visible_food_deficits(player)
    }
    value = 0.0
    for food_type in selected_foods:
        if food_type in state.birdfeeder.dice:
            value += 0.25
        if food_type in opponent_demand:
            value += 0.5
    return value


def _public_card_threat_value(card: BirdCard) -> float:
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


def _visible_food_deficits(player: PlayerState) -> set[FoodType]:
    deficits = set()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            if player.food_tokens.get(food_type, 0) < count:
                deficits.add(food_type)
    return deficits
