"""Greedy baseline agent for immediate implemented score gain."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import apply_action, legal_actions_for_current_player, score_player
from wingspan_ai.state.models import GameState


@dataclass
class GreedyBaselineAgent:
    """Choose the action with the largest immediate implemented score delta."""

    agent_id: str = "greedy_immediate_score"

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("GreedyBaselineAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total

        scored_actions = []
        for action in legal_actions:
            next_state = apply_action(state, action)
            score_delta = score_player(next_state, player_id).total - before_score
            scored_actions.append((score_delta, _heuristic_tiebreaker(state, action), action))

        return max(scored_actions, key=lambda item: (item[0], item[1]))[2]

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))


def _heuristic_tiebreaker(state: GameState, action: LegalAction) -> int:
    if action.action_type == ActionType.PLAY_BIRD:
        return 40
    if action.action_type == ActionType.LAY_EGGS:
        return 30
    if action.action_type == ActionType.GAIN_FOOD:
        return 20 + _food_need_score(state, action)
    if action.action_type == ActionType.DRAW_CARDS:
        return 10
    return 0


def _food_need_score(state: GameState, action: LegalAction) -> int:
    player = state.active_player
    deficits: Counter = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    selected_foods = action.food_types or ((action.food_type,) if action.food_type else ())
    return sum(deficits.get(food_type, 0) for food_type in selected_foods)
