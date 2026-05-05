"""Machine-readable game content models and loaders."""

from wingspan_ai.content.loader import (
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
    load_content_catalog,
    resolve_workbook_path,
)
from wingspan_ai.content.sample_catalog import make_sample_catalog
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
    RulesetMetadata,
    RulesModule,
)

__all__ = [
    "BirdCard",
    "BonusCard",
    "ContentCatalog",
    "ContentPack",
    "FoodCost",
    "FoodType",
    "Habitat",
    "DEFAULT_WORKBOOK_PATH",
    "load_base_game_content_catalog",
    "load_content_catalog",
    "make_sample_catalog",
    "Power",
    "PowerColor",
    "PowerImplementationStatus",
    "RoundGoal",
    "RulesModule",
    "RulesetMetadata",
    "resolve_workbook_path",
]
