"""Rules modules, legal action generation, and state transitions."""

from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    FinalScoreBreakdown,
    InitialSelection,
    apply_action,
    apply_default_initial_selection,
    apply_initial_selection_choice,
    choose_default_initial_selection,
    egg_cost_for_slot,
    legal_actions_for_current_player,
    legal_actions_for_player,
    resolve_habitat_powers,
    resolve_played_bird_power,
    score_player,
    setup_base_game,
)
from wingspan_ai.rules.power_registry import POWER_HANDLER_REGISTRY, PowerHandlerMetadata
from wingspan_ai.rules.scoring_audit import (
    SCORING_SOURCE_REFERENCES,
    ScoringAuditResult,
    audit_scoring_coverage,
)

__all__ = [
    "ActionType",
    "FinalScoreBreakdown",
    "InitialSelection",
    "LegalAction",
    "POWER_HANDLER_REGISTRY",
    "PowerHandlerMetadata",
    "ScoringAuditResult",
    "SCORING_SOURCE_REFERENCES",
    "apply_default_initial_selection",
    "apply_initial_selection_choice",
    "apply_action",
    "audit_scoring_coverage",
    "choose_default_initial_selection",
    "egg_cost_for_slot",
    "legal_actions_for_current_player",
    "legal_actions_for_player",
    "resolve_habitat_powers",
    "resolve_played_bird_power",
    "score_player",
    "setup_base_game",
]
