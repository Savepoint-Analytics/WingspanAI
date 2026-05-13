"""Legal action models for the base Wingspan rules loop."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from wingspan_ai.content.schemas import FoodType, Habitat


class ActionType(StrEnum):
    """Base action families available on the player mat."""

    PLAY_BIRD = "play_bird"
    GAIN_FOOD = "gain_food"
    LAY_EGGS = "lay_eggs"
    DRAW_CARDS = "draw_cards"


class LegalAction(BaseModel):
    """A concrete legal action that can be selected by an agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: ActionType
    player_id: str
    bird_common_name: str | None = None
    habitat: Habitat | None = None
    food_type: FoodType | None = None
    food_types: tuple[FoodType, ...] = ()
    reroll_birdfeeder: bool = False
    discard_card_common_name: str | None = None
    spend_card_for_extra_food: bool = False
    tray_index: int | None = Field(default=None, ge=0, le=2)
    tray_indices: tuple[int, ...] = ()
    draw_from_deck: bool = False
    draw_from_deck_count: int = Field(default=0, ge=0)
    egg_count: int | None = Field(default=None, ge=0)
    spend_food_for_extra_egg: FoodType | None = None
    spend_egg_for_extra_card: bool = False
