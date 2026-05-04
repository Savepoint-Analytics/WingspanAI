"""Seeded random legal-action agent."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import legal_actions_for_current_player
from wingspan_ai.state.models import GameState


@dataclass
class RandomLegalAgent:
    """Select uniformly from the legal action list using local seeded randomness."""

    agent_id: str = "random_legal"
    random_seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.random_seed)

    def select_action(self, legal_actions: list[LegalAction]) -> LegalAction:
        """Choose one legal action from a non-empty action list."""

        if not legal_actions:
            raise ValueError("RandomLegalAgent cannot select from an empty legal action list")
        return self._rng.choice(legal_actions)

    def choose_action(self, state: GameState) -> LegalAction:
        """Choose an action for the active player in the provided game state."""

        return self.select_action(legal_actions_for_current_player(state))
