"""First Monte Carlo rollout agent."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from time import perf_counter

from wingspan_ai.rules.actions import LegalAction, render_action
from wingspan_ai.rules.base_game import (
    apply_action_in_place,
    legal_actions_for_current_player,
    score_player,
)
from wingspan_ai.state.models import GameState


@dataclass(frozen=True)
class RolloutActionEvaluation:
    """Monte Carlo value estimate and completed rollout count for one action."""

    action: LegalAction
    estimated_value: float
    completed_rollouts: int
    used_static_fallback: bool = False


@dataclass
class MonteCarloRolloutAgent:
    """Estimate action value through random legal continuations."""

    agent_id: str = "monte_carlo_rollout"
    rollout_count: int = 8
    rollout_depth: int = 12
    max_decision_time_ms: float | None = None
    min_rollouts_per_action: int = 0
    max_candidate_actions: int | None = 12
    random_seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)
    _last_evaluations: list[RolloutActionEvaluation] = field(default_factory=list, init=False)
    _last_budget_exhausted: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.rollout_count < 1:
            raise ValueError("rollout_count must be at least 1")
        if self.rollout_depth < 1:
            raise ValueError("rollout_depth must be at least 1")
        if self.min_rollouts_per_action < 0:
            raise ValueError("min_rollouts_per_action must be at least 0")
        if self.max_candidate_actions is not None and self.max_candidate_actions < 1:
            raise ValueError("max_candidate_actions must be at least 1 when provided")
        self._rng = random.Random(self.random_seed)

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("MonteCarloRolloutAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        evaluations = self._evaluate_actions(state, legal_actions, player_id)
        self._last_evaluations = evaluations
        return max(
            evaluations,
            key=lambda item: (item.estimated_value, item.completed_rollouts),
        ).action

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        """Expose rollout budget usage without including hidden state."""

        evaluations = self._last_evaluations
        if not evaluations:
            player_id = state.active_player.player_id
            evaluations = self._evaluate_actions(state, legal_actions, player_id)
        ranked = sorted(
            evaluations,
            key=lambda item: (item.estimated_value, item.completed_rollouts),
            reverse=True,
        )
        selected = next(
            evaluation for evaluation in evaluations if evaluation.action == selected_action
        )
        return {
            "policy": "monte_carlo_rollout",
            "legal_action_count": len(legal_actions),
            "evaluated_action_count": len(evaluations),
            "selected_action_type": selected_action.action_type.value,
            "selected_action_label": render_action(selected_action),
            "selected_estimated_value": round(selected.estimated_value, 3),
            "selected_completed_rollouts": selected.completed_rollouts,
            "selected_used_static_fallback": selected.used_static_fallback,
            "configured_rollout_count": self.rollout_count,
            "configured_rollout_depth": self.rollout_depth,
            "configured_max_decision_time_ms": self.max_decision_time_ms,
            "configured_min_rollouts_per_action": self.min_rollouts_per_action,
            "configured_max_candidate_actions": self.max_candidate_actions,
            "budget_exhausted": self._last_budget_exhausted,
            "total_completed_rollouts": sum(
                evaluation.completed_rollouts for evaluation in evaluations
            ),
            "top_alternatives": [
                {
                    "action": evaluation.action.model_dump(mode="json"),
                    "action_label": render_action(evaluation.action),
                    "estimated_value": round(evaluation.estimated_value, 3),
                    "completed_rollouts": evaluation.completed_rollouts,
                    "used_static_fallback": evaluation.used_static_fallback,
                }
                for evaluation in ranked[:5]
            ],
        }

    def _evaluate_actions(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        player_id: str,
    ) -> list[RolloutActionEvaluation]:
        candidate_actions = _candidate_actions(
            legal_actions,
            max_candidate_actions=self.max_candidate_actions,
        )
        deadline = (
            perf_counter() + (self.max_decision_time_ms / 1000)
            if self.max_decision_time_ms is not None
            else None
        )
        self._last_budget_exhausted = False
        scores_by_action: list[list[float]] = [[] for _action in candidate_actions]
        required_rollouts = min(self.min_rollouts_per_action, self.rollout_count)

        for rollout_index in range(self.rollout_count):
            for action_index, action in enumerate(candidate_actions):
                if (
                    deadline is not None
                    and perf_counter() >= deadline
                    and rollout_index >= required_rollouts
                ):
                    self._last_budget_exhausted = True
                    return _rollout_evaluations(candidate_actions, scores_by_action)
                scores_by_action[action_index].append(
                    self._rollout_score(state, action, player_id)
                )

        return _rollout_evaluations(candidate_actions, scores_by_action)

    def _rollout_score(
        self,
        state: GameState,
        action: LegalAction,
        player_id: str,
    ) -> float:
        rollout_state = state.model_copy(deep=True)
        apply_action_in_place(rollout_state, action)
        for _depth_index in range(self.rollout_depth):
            if rollout_state.round_state.game_over:
                break
            legal_actions = legal_actions_for_current_player(rollout_state)
            if not legal_actions:
                break
            apply_action_in_place(rollout_state, self._rng.choice(legal_actions))
        return float(score_player(rollout_state, player_id).total)


def _rollout_evaluations(
    legal_actions: list[LegalAction],
    scores_by_action: list[list[float]],
) -> list[RolloutActionEvaluation]:
    return [
        RolloutActionEvaluation(
            action=action,
            estimated_value=(
                sum(scores) / len(scores) if scores else _static_action_fallback_value(action)
            ),
            completed_rollouts=len(scores),
            used_static_fallback=not scores,
        )
        for action, scores in zip(legal_actions, scores_by_action, strict=True)
    ]


def _candidate_actions(
    legal_actions: list[LegalAction],
    *,
    max_candidate_actions: int | None,
) -> list[LegalAction]:
    if max_candidate_actions is None or len(legal_actions) <= max_candidate_actions:
        return legal_actions

    ranked = sorted(
        legal_actions,
        key=lambda action: (
            _action_family_priority(action),
            _static_action_fallback_value(action),
            render_action(action),
        ),
        reverse=True,
    )
    selected: list[LegalAction] = []
    for action_type in ("play_bird", "lay_eggs", "gain_food", "draw_cards"):
        family_action = next(
            (action for action in ranked if action.action_type.value == action_type),
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


def _action_family_priority(action: LegalAction) -> int:
    if action.action_type.value == "play_bird":
        return 40
    if action.action_type.value == "lay_eggs":
        return 30
    if action.action_type.value == "gain_food":
        return 20
    if action.action_type.value == "draw_cards":
        return 10
    return 0


def _static_action_fallback_value(action: LegalAction) -> float:
    value = float(_action_family_priority(action))
    if action.bird_common_name:
        value += 0.01
    if action.egg_count:
        value += min(action.egg_count, 5) * 0.1
    if action.food_types:
        value += len(action.food_types) * 0.1
    if action.tray_indices or action.tray_index is not None:
        value += 0.1
    if action.draw_from_deck_count:
        value += action.draw_from_deck_count * 0.05
    return value
