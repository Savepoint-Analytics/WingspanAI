"""Combined rule-fidelity audit helpers for simulation batches."""

from __future__ import annotations

from typing import Any

from wingspan_ai.content.schemas import ContentCatalog
from wingspan_ai.rules.power_registry import audit_power_coverage
from wingspan_ai.rules.scoring_audit import audit_scoring_coverage


def audit_rule_coverage(catalog: ContentCatalog) -> dict[str, Any]:
    """Return JSON-ready rule coverage summaries for powers and scoring."""

    power_audit = audit_power_coverage(catalog)
    scoring_audit = audit_scoring_coverage(catalog)
    return {
        "powers": {
            "total_birds": power_audit.total_birds,
            "powered_card_count": power_audit.powered_card_count,
            "no_power_count": power_audit.no_power_count,
            "classified_power_count": power_audit.classified_power_count,
            "implemented_power_count": power_audit.implemented_power_count,
            "unclassified_power_count": power_audit.unclassified_power_count,
            "unsupported_power_count": power_audit.unsupported_power_count,
            "handler_coverage": power_audit.handler_coverage,
            "implementation_coverage": power_audit.implementation_coverage,
            "handler_counts": power_audit.handler_counts,
            "status_counts": power_audit.status_counts,
            "unsupported_power_cards": power_audit.unsupported_power_cards,
            "handler_source_references": power_audit.handler_source_references,
        },
        "scoring": {
            "bonus_card_coverage": scoring_audit.bonus_card_coverage,
            "round_goal_coverage": scoring_audit.round_goal_coverage,
            "supported_bonus_card_count": len(scoring_audit.supported_bonus_cards),
            "unsupported_bonus_card_count": len(scoring_audit.unsupported_bonus_cards),
            "supported_round_goal_count": len(scoring_audit.supported_round_goals),
            "unsupported_round_goal_count": len(scoring_audit.unsupported_round_goals),
            "supported_bonus_cards": scoring_audit.supported_bonus_cards,
            "unsupported_bonus_cards": scoring_audit.unsupported_bonus_cards,
            "supported_round_goals": scoring_audit.supported_round_goals,
            "unsupported_round_goals": scoring_audit.unsupported_round_goals,
            "source_references": scoring_audit.source_references,
        },
    }
