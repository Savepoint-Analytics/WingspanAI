"""Greedy baseline agent for immediate implemented score gain."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from wingspan_ai.agents.feeder_odds import feeder_supply_value
from wingspan_ai.agents.setup import SetupPolicyMixin
from wingspan_ai.agents.tray_preference import base_card_affinity, drawn_tray_cards
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    apply_action,
    expected_gain_food,
    legal_actions_for_current_player,
    score_player,
)
from wingspan_ai.state.models import GameState


@dataclass
class GreedyBaselineAgent(SetupPolicyMixin):
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

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        """Explain the greedy action in terms of immediate score and resource need."""

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total
        next_state = apply_action(state, selected_action)
        score_delta = score_player(next_state, player_id).total - before_score
        return {
            "policy": "greedy_immediate_score",
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
            "score_delta": score_delta,
            "food_need_score": _food_need_score(state, selected_action),
        }


def _heuristic_tiebreaker(state: GameState, action: LegalAction) -> float:
    if action.action_type == ActionType.PLAY_BIRD:
        return 40.0
    if action.action_type == ActionType.LAY_EGGS:
        return 30.0
    if action.action_type == ActionType.GAIN_FOOD:
        return 20.0 + _food_need_score(state, action)
    if action.action_type == ActionType.DRAW_CARDS:
        # Every draw yields zero immediate points, so without this the agent
        # was indifferent between tray cards and always took index 0.
        return 10.0 + _tray_card_quality(state, action)
    return 0.0


def _tray_card_quality(state: GameState, action: LegalAction) -> float:
    """Best face-up card this draw would take, scaled to stay a tie-break.

    Capped below 1.0 so it orders equal-scoring draws without ever
    outranking a genuinely higher-scoring action.
    """

    player = state.active_player
    cards = drawn_tray_cards(state, action)
    if not cards:
        return 0.0
    best = max(base_card_affinity(card, player, state) for card in cards)
    return min(best / 10.0, 0.99)


def _food_need_score(state: GameState, action: LegalAction) -> float:
    player = state.active_player
    deficits: Counter = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    # Foods behind a reroll or refill are preferences; credit them at the odds
    # the roll supplies them rather than as if already in hand.
    matched = sum(
        deficits.get(food_type, 0) * weight
        for food_type, weight in expected_gain_food(state, action).items()
    )
    return matched + _feeder_outlook(state, action)


def _feeder_outlook(state: GameState, action: LegalAction) -> float:
    """Value of what the feeder still stands to supply after this action.

    `_food_need_score` only credits the foods this action already takes. It
    cannot distinguish a feeder that will keep supplying what the player needs
    from one that is about to run dry, because a legal action carries no
    information about the dice left behind.
    """

    if action.action_type != ActionType.GAIN_FOOD:
        return 0.0
    taken = len(action.food_types or ((action.food_type,) if action.food_type else ()))
    return feeder_supply_value(state, state.active_player, max(taken, 1))
