"""Rules modules, legal action generation, and state transitions."""

from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.audit import audit_rule_coverage
from wingspan_ai.rules.base_game import (
    FinalScoreBreakdown,
    InitialSelection,
    apply_action,
    apply_default_initial_selection,
    apply_initial_selection_choice,
    choose_default_initial_selection,
    egg_cost_for_slot,
    habitat_action_yield,
    legal_actions_for_current_player,
    legal_actions_for_player,
    ordered_habitats,
    resolve_habitat_powers,
    resolve_played_bird_power,
    score_player,
    setup_base_game,
)
from wingspan_ai.rules.multiplayer_audit import (
    EGG_MINIATURE_COUNTS,
    EXPECTED_ACTION_CUBES_BY_ROUND,
    EXPECTED_GREEN_GOAL_SCORES,
    KNOWN_SIMPLIFICATIONS,
    MultiplayerAuditError,
    audit_multiplayer_rules,
)
from wingspan_ai.rules.power_registry import (
    POWER_HANDLER_REGISTRY,
    PowerAuditResult,
    PowerHandlerMetadata,
    audit_power_coverage,
)
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
    "EGG_MINIATURE_COUNTS",
    "EXPECTED_ACTION_CUBES_BY_ROUND",
    "EXPECTED_GREEN_GOAL_SCORES",
    "KNOWN_SIMPLIFICATIONS",
    "MultiplayerAuditError",
    "POWER_HANDLER_REGISTRY",
    "PowerAuditResult",
    "PowerHandlerMetadata",
    "ScoringAuditResult",
    "SCORING_SOURCE_REFERENCES",
    "apply_default_initial_selection",
    "apply_initial_selection_choice",
    "apply_action",
    "audit_multiplayer_rules",
    "audit_power_coverage",
    "audit_rule_coverage",
    "audit_scoring_coverage",
    "choose_default_initial_selection",
    "egg_cost_for_slot",
    "habitat_action_yield",
    "legal_actions_for_current_player",
    "legal_actions_for_player",
    "ordered_habitats",
    "resolve_habitat_powers",
    "resolve_played_bird_power",
    "score_player",
    "setup_base_game",
]
