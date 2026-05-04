"""Pydantic models for machine-readable Wingspan content.

The models in this module describe normalized game concepts. Source-specific
workbook column names and parsing rules belong in loader/audit modules.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmptyString = Annotated[str, Field(min_length=1)]


class ContentPack(StrEnum):
    """A content pack adds cards or other game content."""

    CORE = "core"
    EUROPEAN = "european"
    OCEANIA = "oceania"
    ASIA = "asia"
    AMERICAS = "americas"
    PROMO_US = "promo_us"
    PROMO_EUROPE = "promo_europe"
    PROMO_ASIA = "promo_asia"
    PROMO_NZ = "promo_nz"
    PROMO_CA = "promo_ca"
    PROMO_UK = "promo_uk"
    FAN_ART = "fan_art"


class RulesModule(StrEnum):
    """A rules module changes legal actions, resources, scoring, or setup."""

    BASE_GAME = "base_game_rules"
    NECTAR = "nectar_rules"
    REVISED_PLAYER_MAT = "revised_player_mat"
    DUET_MODE = "duet_mode"
    FLOCK_MODE = "flock_mode"
    AUTOMA = "automa_rules"
    EXPANSION_SCORING = "expansion_specific_scoring"


class FoodType(StrEnum):
    """Food/resource symbols that can appear in costs and effects."""

    INVERTEBRATE = "invertebrate"
    SEED = "seed"
    FISH = "fish"
    FRUIT = "fruit"
    RODENT = "rodent"
    NECTAR = "nectar"
    WILD = "wild"


class Habitat(StrEnum):
    """Player-board habitats where birds can be played."""

    FOREST = "forest"
    GRASSLAND = "grassland"
    WETLAND = "wetland"


class PowerColor(StrEnum):
    """Power timing/color categories used by Wingspan cards."""

    WHITE = "white"
    BROWN = "brown"
    PINK = "pink"
    TEAL = "teal"
    YELLOW = "yellow"
    NONE = "none"


class NestType(StrEnum):
    """Nest categories used for placement, goals, and bonus scoring."""

    GROUND = "ground"
    BOWL = "bowl"
    CAVITY = "cavity"
    PLATFORM = "platform"
    WILD = "wild"


class BeakDirection(StrEnum):
    """Beak direction metadata used by Asia flock/duet content."""

    LEFT = "left"
    RIGHT = "right"
    NONE = "none"
    LEFT_RIGHT = "left_right"
    LEFT_LEFT = "left_left"
    UNKNOWN = "unknown"


class PowerImplementationStatus(StrEnum):
    """Current implementation fidelity for a card power or scoring rule."""

    READY = "ready"
    NOT_IMPLEMENTED = "not_implemented"
    NO_OP_FOR_V1 = "no_op_for_v1"
    EXPECTED_VALUE_APPROXIMATION = "expected_value_approximation"
    HEURISTIC_RESOLUTION = "heuristic_resolution"
    EXCLUDED_FROM_V1_DECK = "excluded_from_v1_deck"
    MUST_IMPLEMENT_BEFORE_EXPERIMENT = "must_implement_before_experiment"


class FoodCost(BaseModel):
    """Normalized food cost for playing a bird."""

    model_config = ConfigDict(extra="forbid")

    fixed: dict[FoodType, int] = Field(default_factory=dict)
    wild_food_count: int = Field(default=0, ge=0)
    choice_food_count: int = Field(default=0, ge=0)
    variable_food: bool = False

    @field_validator("fixed")
    @classmethod
    def validate_fixed_food_counts(cls, value: dict[FoodType, int]) -> dict[FoodType, int]:
        invalid = {food: count for food, count in value.items() if count < 0}
        if invalid:
            msg = f"food counts must be non-negative: {invalid}"
            raise ValueError(msg)
        return value

    @property
    def minimum_total(self) -> int:
        """Minimum number of food tokens implied by this cost."""

        return sum(self.fixed.values()) + self.wild_food_count + self.choice_food_count


class Power(BaseModel):
    """Bird power text plus implementation metadata."""

    model_config = ConfigDict(extra="forbid")

    color: PowerColor
    text: str | None = None
    categories: list[str] = Field(default_factory=list)
    implementation_status: PowerImplementationStatus = PowerImplementationStatus.NOT_IMPLEMENTED
    handler_key: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_handler_for_ready_power(self) -> "Power":
        if self.implementation_status == PowerImplementationStatus.READY and not self.handler_key:
            raise ValueError("ready powers must include a handler_key")
        return self


class BirdCard(BaseModel):
    """Normalized bird card content needed by the simulator."""

    model_config = ConfigDict(extra="forbid")

    common_name: NonEmptyString
    scientific_name: NonEmptyString
    content_pack: ContentPack
    habitats: set[Habitat]
    food_cost: FoodCost
    victory_points: int = Field(ge=0)
    nest_type: NestType | None = None
    egg_limit: int = Field(ge=0)
    wingspan_cm: int | None = Field(default=None, ge=0)
    wingspan_is_variable: bool = False
    power: Power
    predator: bool = False
    flocking: bool = False
    bonus_card_power: bool = False
    beak_direction: BeakDirection | None = None
    automa_banned: bool = False
    swift_start: bool = False
    geography: set[str] = Field(default_factory=set)
    bonus_card_tags: set[str] = Field(default_factory=set)
    source_row: int | None = Field(default=None, ge=1)

    @field_validator("habitats")
    @classmethod
    def require_at_least_one_habitat(cls, value: set[Habitat]) -> set[Habitat]:
        if not value:
            raise ValueError("bird cards must have at least one legal habitat")
        return value

    @model_validator(mode="after")
    def variable_wingspan_needs_missing_measurement(self) -> "BirdCard":
        if self.wingspan_is_variable and self.wingspan_cm is not None:
            raise ValueError("variable wingspan cards should not also set wingspan_cm")
        return self


class BonusCard(BaseModel):
    """Normalized bonus-card scoring definition."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    content_packs: set[ContentPack]
    condition: NonEmptyString
    victory_point_text: str | None = None
    automa_compatible: bool = False
    explanatory_text: str | None = None
    prevalence_percent: float | None = Field(default=None, ge=0, le=100)
    implementation_status: PowerImplementationStatus = PowerImplementationStatus.NOT_IMPLEMENTED
    handler_key: str | None = None
    source_row: int | None = Field(default=None, ge=1)

    @field_validator("content_packs")
    @classmethod
    def require_content_pack(cls, value: set[ContentPack]) -> set[ContentPack]:
        if not value:
            raise ValueError("bonus cards must belong to at least one content pack")
        return value


class RoundGoal(BaseModel):
    """End-of-round or map-style goal definition."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    content_pack: ContentPack
    scoring_values: dict[int, int] = Field(default_factory=dict)
    reverse_goal_name: str | None = None
    rules_module: RulesModule = RulesModule.BASE_GAME
    implementation_status: PowerImplementationStatus = PowerImplementationStatus.NOT_IMPLEMENTED
    handler_key: str | None = None
    source_row: int | None = Field(default=None, ge=1)

    @field_validator("scoring_values")
    @classmethod
    def validate_player_count_keys(cls, value: dict[int, int]) -> dict[int, int]:
        invalid_keys = [key for key in value if key < 1]
        invalid_values = [score for score in value.values() if score < 0]
        if invalid_keys or invalid_values:
            raise ValueError("round goal scoring values must use positive keys and non-negative scores")
        return value


class RulesetMetadata(BaseModel):
    """Expansion-aware configuration for a simulation run."""

    model_config = ConfigDict(extra="forbid")

    ruleset_id: NonEmptyString
    content_packs: list[ContentPack]
    rules_modules: list[RulesModule]
    player_count: int = Field(ge=1, le=7)
    automa_enabled: bool = False
    random_seed: int | None = None
    ruleset_version: str = "v1"

    @field_validator("content_packs", "rules_modules")
    @classmethod
    def require_non_empty_config_list(cls, value: list[StrEnum]) -> list[StrEnum]:
        if not value:
            raise ValueError("ruleset configuration lists cannot be empty")
        return value

    @model_validator(mode="after")
    def automa_requires_automa_module(self) -> "RulesetMetadata":
        if self.automa_enabled and RulesModule.AUTOMA not in self.rules_modules:
            raise ValueError("automa_enabled requires the automa_rules module")
        return self


class ContentCatalog(BaseModel):
    """A validated content bundle for one or more rulesets."""

    model_config = ConfigDict(extra="forbid")

    birds: list[BirdCard] = Field(default_factory=list)
    bonus_cards: list[BonusCard] = Field(default_factory=list)
    round_goals: list[RoundGoal] = Field(default_factory=list)
    rulesets: list[RulesetMetadata] = Field(default_factory=list)
