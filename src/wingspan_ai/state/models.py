"""Base-game state models for Wingspan simulation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from wingspan_ai.content.schemas import (
    BirdCard,
    BonusCard,
    FoodType,
    Habitat,
    RoundGoal,
    RulesetMetadata,
)

BASE_GAME_FOOD = (
    FoodType.INVERTEBRATE,
    FoodType.SEED,
    FoodType.FISH,
    FoodType.FRUIT,
    FoodType.RODENT,
)


def empty_habitat_board() -> dict[Habitat, list["BirdSlot"]]:
    """Create an empty three-habitat player board."""

    return {Habitat.FOREST: [], Habitat.GRASSLAND: [], Habitat.WETLAND: []}


def empty_food_tokens() -> dict[FoodType, int]:
    """Create zeroed base-game food token counts."""

    return {food: 0 for food in BASE_GAME_FOOD}


class BirdSlot(BaseModel):
    """A played bird and the scoring tokens attached to it."""

    model_config = ConfigDict(extra="forbid")

    card: BirdCard
    eggs: int = Field(default=0, ge=0)
    cached_food: int = Field(default=0, ge=0)
    tucked_cards: int = Field(default=0, ge=0)

    @property
    def available_egg_capacity(self) -> int:
        return max(self.card.egg_limit - self.eggs, 0)


class PlayerState(BaseModel):
    """Complete state for one player, including private hand and bonus cards."""

    model_config = ConfigDict(extra="forbid")

    player_id: str
    agent_id: str | None = None
    hand: list[BirdCard] = Field(default_factory=list)
    bonus_cards: list[BonusCard] = Field(default_factory=list)
    food_tokens: dict[FoodType, int] = Field(default_factory=empty_food_tokens)
    habitats: dict[Habitat, list[BirdSlot]] = Field(default_factory=empty_habitat_board)
    action_cubes_available: int = Field(default=8, ge=0)

    @property
    def total_eggs(self) -> int:
        return sum(slot.eggs for slots in self.habitats.values() for slot in slots)

    @property
    def available_egg_capacity(self) -> int:
        return sum(
            slot.available_egg_capacity for slots in self.habitats.values() for slot in slots
        )

    @property
    def played_birds(self) -> list[BirdSlot]:
        return [slot for habitat in Habitat for slot in self.habitats[habitat]]


class DeckState(BaseModel):
    """Card decks, discards, and public bird tray."""

    model_config = ConfigDict(extra="forbid")

    bird_deck: list[BirdCard] = Field(default_factory=list)
    bird_discard: list[BirdCard] = Field(default_factory=list)
    bonus_deck: list[BonusCard] = Field(default_factory=list)
    bonus_discard: list[BonusCard] = Field(default_factory=list)


class BirdfeederState(BaseModel):
    """Current birdfeeder dice faces."""

    model_config = ConfigDict(extra="forbid")

    dice: list[FoodType] = Field(default_factory=list)


class RoundState(BaseModel):
    """Turn order and round progress."""

    model_config = ConfigDict(extra="forbid")

    round_number: int = Field(default=1, ge=1, le=4)
    turn_number: int = Field(default=1, ge=1)
    active_player_index: int = Field(default=0, ge=0)
    game_over: bool = False


class GameState(BaseModel):
    """Full simulator state for a seeded Wingspan game."""

    model_config = ConfigDict(extra="forbid")

    game_id: str
    ruleset: RulesetMetadata
    random_seed: int
    players: list[PlayerState]
    decks: DeckState
    bird_tray: list[BirdCard] = Field(default_factory=list, max_length=3)
    birdfeeder: BirdfeederState = Field(default_factory=BirdfeederState)
    round_goals: list[RoundGoal] = Field(default_factory=list, max_length=4)
    round_state: RoundState = Field(default_factory=RoundState)

    @property
    def active_player(self) -> PlayerState:
        return self.players[self.round_state.active_player_index]


class PublicPlayerState(BaseModel):
    """Player information visible to opponents and analytics views."""

    model_config = ConfigDict(extra="forbid")

    player_id: str
    agent_id: str | None = None
    food_tokens: dict[FoodType, int]
    habitats: dict[Habitat, list[BirdSlot]]
    action_cubes_available: int
    hand_count: int
    bonus_card_count: int


class PrivatePlayerState(BaseModel):
    """Private information visible to one player or training/debug logs."""

    model_config = ConfigDict(extra="forbid")

    player_id: str
    hand: list[BirdCard]
    bonus_cards: list[BonusCard]


class PublicGameState(BaseModel):
    """Public observation boundary for the current game state."""

    model_config = ConfigDict(extra="forbid")

    game_id: str
    ruleset: RulesetMetadata
    players: list[PublicPlayerState]
    bird_tray: list[BirdCard]
    birdfeeder: BirdfeederState
    round_goals: list[RoundGoal]
    round_state: RoundState
    bird_deck_count: int
    bonus_deck_count: int


def to_public_state(state: GameState) -> PublicGameState:
    """Strip hidden hands, bonus cards, and deck order from full game state."""

    return PublicGameState(
        game_id=state.game_id,
        ruleset=state.ruleset,
        players=[
            PublicPlayerState(
                player_id=player.player_id,
                agent_id=player.agent_id,
                food_tokens=dict(player.food_tokens),
                habitats=player.habitats,
                action_cubes_available=player.action_cubes_available,
                hand_count=len(player.hand),
                bonus_card_count=len(player.bonus_cards),
            )
            for player in state.players
        ],
        bird_tray=state.bird_tray,
        birdfeeder=state.birdfeeder,
        round_goals=state.round_goals,
        round_state=state.round_state,
        bird_deck_count=len(state.decks.bird_deck),
        bonus_deck_count=len(state.decks.bonus_deck),
    )


def to_private_state(state: GameState, player_id: str) -> PrivatePlayerState:
    """Return one player's private hand and bonus-card information."""

    player = next(player for player in state.players if player.player_id == player_id)
    return PrivatePlayerState(
        player_id=player.player_id,
        hand=player.hand,
        bonus_cards=player.bonus_cards,
    )
