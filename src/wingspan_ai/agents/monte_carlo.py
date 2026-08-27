"""First Monte Carlo rollout agent."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    score_player,
)
from wingspan_ai.state.models import GameState


@dataclass
class MonteCarloRolloutAgent:
    """Estimate action value through random legal continuations."""

    agent_id: str = "monte_carlo_rollout"
    rollout_count: int = 8
    rollout_depth: int = 12
    random_seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.random_seed)

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("MonteCarloRolloutAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        scored_actions = [
            (self._estimate_action_value(state, action, player_id), action)
            for action in legal_actions
        ]
        return max(scored_actions, key=lambda item: item[0])[1]

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def _estimate_action_value(
        self,
        state: GameState,
        action: LegalAction,
        player_id: str,
    ) -> float:
        rollout_scores: list[float] = []
        for _rollout_index in range(self.rollout_count):
            rollout_state = apply_action(state, action)
            for _depth_index in range(self.rollout_depth):
                if rollout_state.round_state.game_over:
                    break
                legal_actions = legal_actions_for_current_player(rollout_state)
                if not legal_actions:
                    break
                rollout_state = apply_action(rollout_state, self._rng.choice(legal_actions))
            rollout_scores.append(float(score_player(rollout_state, player_id).total))
        return sum(rollout_scores) / len(rollout_scores)
