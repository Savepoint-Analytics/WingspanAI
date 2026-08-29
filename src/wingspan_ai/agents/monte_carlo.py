"""First Monte Carlo rollout agent."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from time import perf_counter

from wingspan_ai.rules.actions import LegalAction, render_action
from wingspan_ai.rules.base_game import (
    apply_action,
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


@dataclass
class MonteCarloRolloutAgent:
    """Estimate action value through random legal continuations."""

    agent_id: str = "monte_carlo_rollout"
    rollout_count: int = 8
    rollout_depth: int = 12
    max_decision_time_ms: float | None = None
    min_rollouts_per_action: int = 1
    random_seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)
    _last_evaluations: list[RolloutActionEvaluation] = field(default_factory=list, init=False)
    _last_budget_exhausted: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.rollout_count < 1:
            raise ValueError("rollout_count must be at least 1")
        if self.rollout_depth < 1:
            raise ValueError("rollout_depth must be at least 1")
        if self.min_rollouts_per_action < 1:
            raise ValueError("min_rollouts_per_action must be at least 1")
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
            "selected_action_type": selected_action.action_type.value,
            "selected_action_label": render_action(selected_action),
            "selected_estimated_value": round(selected.estimated_value, 3),
            "selected_completed_rollouts": selected.completed_rollouts,
            "configured_rollout_count": self.rollout_count,
            "configured_rollout_depth": self.rollout_depth,
            "configured_max_decision_time_ms": self.max_decision_time_ms,
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
        deadline = (
            perf_counter() + (self.max_decision_time_ms / 1000)
            if self.max_decision_time_ms is not None
            else None
        )
        self._last_budget_exhausted = False
        scores_by_action: list[list[float]] = [[] for _action in legal_actions]
        required_rollouts = min(self.min_rollouts_per_action, self.rollout_count)

        for action_index, action in enumerate(legal_actions):
            for _rollout_index in range(required_rollouts):
                scores_by_action[action_index].append(
                    self._rollout_score(state, action, player_id)
                )

        for _rollout_index in range(required_rollouts, self.rollout_count):
            for action_index, action in enumerate(legal_actions):
                if deadline is not None and perf_counter() >= deadline:
                    self._last_budget_exhausted = True
                    return _rollout_evaluations(legal_actions, scores_by_action)
                scores_by_action[action_index].append(
                    self._rollout_score(state, action, player_id)
                )

        return _rollout_evaluations(legal_actions, scores_by_action)

    def _rollout_score(
        self,
        state: GameState,
        action: LegalAction,
        player_id: str,
    ) -> float:
        rollout_state = apply_action(state, action)
        for _depth_index in range(self.rollout_depth):
            if rollout_state.round_state.game_over:
                break
            legal_actions = legal_actions_for_current_player(rollout_state)
            if not legal_actions:
                break
            rollout_state = apply_action(rollout_state, self._rng.choice(legal_actions))
        return float(score_player(rollout_state, player_id).total)


def _rollout_evaluations(
    legal_actions: list[LegalAction],
    scores_by_action: list[list[float]],
) -> list[RolloutActionEvaluation]:
    return [
        RolloutActionEvaluation(
            action=action,
            estimated_value=sum(scores) / len(scores),
            completed_rollouts=len(scores),
        )
        for action, scores in zip(legal_actions, scores_by_action, strict=True)
        if scores
    ]
