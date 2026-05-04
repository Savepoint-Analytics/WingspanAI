"""Rules modules, legal action generation, and state transitions."""

from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    FinalScoreBreakdown,
    apply_action,
    egg_cost_for_slot,
    legal_actions_for_current_player,
    legal_actions_for_player,
    score_player,
    setup_base_game,
)

__all__ = [
    "ActionType",
    "FinalScoreBreakdown",
    "LegalAction",
    "apply_action",
    "egg_cost_for_slot",
    "legal_actions_for_current_player",
    "legal_actions_for_player",
    "score_player",
    "setup_base_game",
]
