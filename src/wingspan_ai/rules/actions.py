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
    tray_index: int | None = Field(default=None, ge=0, le=2)
    draw_from_deck: bool = False
    egg_count: int | None = Field(default=None, ge=0)
