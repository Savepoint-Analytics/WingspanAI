"""Machine-readable game content models and loaders."""

from wingspan_ai.content.loader import load_base_game_content_catalog, load_content_catalog
from wingspan_ai.content.schemas import (
    BirdCard,
    BonusCard,
    ContentCatalog,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    Power,
    PowerColor,
    PowerImplementationStatus,
    RoundGoal,
    RulesModule,
    RulesetMetadata,
)

__all__ = [
    "BirdCard",
    "BonusCard",
    "ContentCatalog",
    "ContentPack",
    "FoodCost",
    "FoodType",
    "Habitat",
    "load_base_game_content_catalog",
    "load_content_catalog",
    "Power",
    "PowerColor",
    "PowerImplementationStatus",
    "RoundGoal",
    "RulesModule",
    "RulesetMetadata",
]
