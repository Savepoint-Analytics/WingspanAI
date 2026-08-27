"""Scripted strategy archetype baseline agents."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import apply_action, legal_actions_for_current_player, score_player
from wingspan_ai.state.models import GameState


class StrategyArchetype(StrEnum):
    """Named strategy archetypes for early behavioural signatures."""

    EGG_FOCUS = "egg_focus"
    ENGINE_BUILDER = "engine_builder"
    FOOD_ACCELERATION = "food_acceleration"
    CARD_DRAW = "card_draw"
    BONUS_CARD_FOCUS = "bonus_card_focus"
    ROUND_GOAL_CHASE = "round_goal_chase"


@dataclass
class StrategyArchetypeAgent:
    """A simple weighted policy for one interpretable Wingspan strategy."""

    archetype: StrategyArchetype
    agent_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent_id is None:
            self.agent_id = f"archetype_{self.archetype.value}"

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("StrategyArchetypeAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total
        scored_actions = [
            (
                _score_action_for_archetype(state, action, self.archetype, before_score),
                action,
            )
            for action in legal_actions
        ]
        return max(scored_actions, key=lambda item: item[0])[1]

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        """Explain the archetype-weighted action for telemetry."""

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total
        return {
            "policy": "strategy_archetype",
            "archetype": self.archetype.value,
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
            "action_score": _score_action_for_archetype(
                state,
                selected_action,
                self.archetype,
                before_score,
            ),
            "food_need_score": _food_need_score(state, selected_action),
        }


def _score_action_for_archetype(
    state: GameState,
    action: LegalAction,
    archetype: StrategyArchetype,
    before_score: int,
) -> float:
    score = _base_immediate_score(state, action, before_score)

    if archetype == StrategyArchetype.EGG_FOCUS:
        return score + _egg_focus_bonus(action)
    if archetype == StrategyArchetype.ENGINE_BUILDER:
        return score + _engine_builder_bonus(state, action)
    if archetype == StrategyArchetype.FOOD_ACCELERATION:
        return score + _food_acceleration_bonus(state, action)
    if archetype == StrategyArchetype.CARD_DRAW:
        return score + _card_draw_bonus(action)
    if archetype == StrategyArchetype.BONUS_CARD_FOCUS:
        return score + _bonus_card_focus_bonus(state, action)
    if archetype == StrategyArchetype.ROUND_GOAL_CHASE:
        return score + _round_goal_chase_bonus(state, action)
    return score


def _base_immediate_score(state: GameState, action: LegalAction, before_score: int) -> float:
    player_id = state.active_player.player_id
    next_state = apply_action(state, action)
    return float(score_player(next_state, player_id).total - before_score)


def _egg_focus_bonus(action: LegalAction) -> float:
    if action.action_type == ActionType.LAY_EGGS:
        return 8
    if action.action_type == ActionType.PLAY_BIRD:
        return 2
    return 0


def _engine_builder_bonus(state: GameState, action: LegalAction) -> float:
    if action.action_type != ActionType.PLAY_BIRD or action.habitat is None:
        return 0
    player = state.active_player
    return 6 - len(player.habitats[action.habitat])


def _food_acceleration_bonus(state: GameState, action: LegalAction) -> float:
    if action.action_type == ActionType.GAIN_FOOD:
        return 8 + _food_need_score(state, action)
    if action.action_type == ActionType.PLAY_BIRD:
        return 2
    return 0


def _card_draw_bonus(action: LegalAction) -> float:
    if action.action_type == ActionType.DRAW_CARDS:
        return 8
    return 0


def _bonus_card_focus_bonus(state: GameState, action: LegalAction) -> float:
    if action.action_type != ActionType.PLAY_BIRD or action.bird_common_name is None:
        return 0
    card = next(
        card for card in state.active_player.hand if card.common_name == action.bird_common_name
    )
    return float(len(card.bonus_card_tags) + (3 if card.bonus_card_power else 0))


def _round_goal_chase_bonus(state: GameState, action: LegalAction) -> float:
    if action.action_type != ActionType.PLAY_BIRD:
        return 0
    current_goal = state.round_goals[state.round_state.round_number - 1]
    goal_text = current_goal.name.lower()
    if action.habitat and action.habitat.value in goal_text:
        return 8
    if action.habitat and "[bird]" in goal_text:
        return 3
    return 0


def _food_need_score(state: GameState, action: LegalAction) -> float:
    player = state.active_player
    deficits: Counter = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    selected_foods = action.food_types or ((action.food_type,) if action.food_type else ())
    return float(sum(deficits.get(food_type, 0) for food_type in selected_foods))
