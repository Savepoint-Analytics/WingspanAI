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


def render_action(action: LegalAction) -> str:
    """Return a concise player-facing description of a concrete legal action."""

    if action.action_type == ActionType.PLAY_BIRD:
        habitat = f" in {_format_enum(action.habitat)}" if action.habitat else ""
        bird = action.bird_common_name or "a bird"
        return f"Play {bird}{habitat}"

    if action.action_type == ActionType.GAIN_FOOD:
        selected_food = action.food_types or (
            (action.food_type,) if action.food_type else ()
        )
        foods = _format_foods(selected_food)
        parts = [f"Gain {foods or 'food'}"]
        if action.reroll_birdfeeder:
            parts.append("if rolled, after rerolling the birdfeeder")
        if action.spend_card_for_extra_food:
            discarded = (
                f" ({action.discard_card_common_name})"
                if action.discard_card_common_name
                else ""
            )
            parts.append(f"by discarding a card{discarded}")
        return " ".join(parts)

    if action.action_type == ActionType.LAY_EGGS:
        egg_count = action.egg_count if action.egg_count is not None else 0
        egg_word = "egg" if egg_count == 1 else "eggs"
        parts = [f"Lay {egg_count} {egg_word}"]
        if action.spend_food_for_extra_egg:
            parts.append(f"by spending {_format_enum(action.spend_food_for_extra_egg)} for +1 egg")
        return " ".join(parts)

    if action.action_type == ActionType.DRAW_CARDS:
        sources: list[str] = []
        if action.draw_from_deck_count:
            card_word = "card" if action.draw_from_deck_count == 1 else "cards"
            sources.append(f"{action.draw_from_deck_count} deck {card_word}")
        elif action.draw_from_deck:
            sources.append("1 deck card")
        if action.tray_indices:
            tray_numbers = ", ".join(str(index + 1) for index in action.tray_indices)
            sources.append(f"tray cards {tray_numbers}")
        elif action.tray_index is not None:
            sources.append(f"tray card {action.tray_index + 1}")
        parts = [f"Draw {' and '.join(sources) if sources else 'cards'}"]
        if action.spend_egg_for_extra_card:
            parts.append("by spending 1 egg for +1 card")
        return " ".join(parts)

    return action.action_type.value.replace("_", " ").title()


def _format_foods(food_types: tuple[FoodType | None, ...]) -> str:
    foods = [_format_enum(food_type) for food_type in food_types if food_type is not None]
    if not foods:
        return ""
    if len(foods) == 1:
        return foods[0]
    return ", ".join(foods[:-1]) + f" and {foods[-1]}"


def _format_enum(value: FoodType | Habitat | None) -> str:
    if value is None:
        return ""
    return value.value.replace("_", " ")
