"""Console-backed human player policy for local simulations."""

from __future__ import annotations

from dataclasses import dataclass

from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import LegalAction
from wingspan_ai.rules.base_game import (
    BIRD_FOOD_SELECTION_TOTAL,
    InitialSelection,
    choose_default_initial_selection,
    legal_actions_for_current_player,
)
from wingspan_ai.state.models import GameState, PlayerState


@dataclass
class HumanCliAgent:
    """Interactive command-line policy that chooses from generated legal actions."""

    agent_id: str = "human_cli"
    use_default_setup: bool = True

    def choose_initial_selection(self, player: PlayerState) -> InitialSelection:
        if self.use_default_setup:
            return choose_default_initial_selection(player)

        print(f"\nSetup for {player.player_id}")
        print("Bird hand:")
        for index, card in enumerate(player.hand, start=1):
            print(f"{index}. {card.common_name} ({card.food_cost.minimum_total} food)")
        bird_indices = _read_indices(
            "Keep which bird numbers? ",
            max_index=len(player.hand),
        )
        kept_birds = [player.hand[index - 1].common_name for index in bird_indices]

        print("Bonus cards:")
        for index, card in enumerate(player.bonus_cards, start=1):
            print(f"{index}. {card.name}")
        bonus_indices = _read_indices("Keep one bonus number? ", max_index=len(player.bonus_cards))
        kept_bonus = [player.bonus_cards[bonus_indices[0] - 1].name]

        starting_food_count = BIRD_FOOD_SELECTION_TOTAL - len(kept_birds)
        starting_food = _read_food_choices(starting_food_count)
        return InitialSelection(
            player_id=player.player_id,
            kept_bird_names=kept_birds,
            kept_bonus_card_names=kept_bonus,
            starting_food=starting_food,
        )

    def choose_action(self, state: GameState) -> LegalAction:
        legal_actions = legal_actions_for_current_player(state)
        if not legal_actions:
            raise ValueError("HumanCliAgent cannot select from an empty action list")

        player = state.active_player
        print(
            f"\nRound {state.round_state.round_number}, "
            f"round turn {state.round_state.round_turn_number} "
            f"(global turn {state.round_state.turn_number})"
        )
        print(f"Active player: {player.player_id}")
        print(f"Food: {dict(player.food_tokens)}")
        print(f"Hand: {[card.common_name for card in player.hand]}")
        print("Legal actions:")
        for index, action in enumerate(legal_actions, start=1):
            print(f"{index}. {action.model_dump(mode='json')}")

        while True:
            raw_value = input("Choose action number: ").strip()
            if raw_value.isdigit() and 1 <= int(raw_value) <= len(legal_actions):
                return legal_actions[int(raw_value) - 1]
            print("Invalid action number.")

    def summarize_decision(
        self,
        _state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        return {
            "policy": "human_cli",
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
        }


def _read_indices(prompt: str, *, max_index: int) -> list[int]:
    while True:
        raw_value = input(prompt).replace(",", " ").split()
        if raw_value and all(value.isdigit() for value in raw_value):
            indices = [int(value) for value in raw_value]
            if all(1 <= index <= max_index for index in indices):
                return indices
        print("Enter valid card numbers separated by spaces.")


def _read_food_choices(count: int) -> list[FoodType]:
    if count <= 0:
        return []
    food_by_name = {food.value: food for food in BASE_FOOD_TYPES}
    print(f"Choose {count} starting food from: {', '.join(food_by_name)}")
    while True:
        raw_food = input("Food choices: ").replace(",", " ").split()
        if len(raw_food) == count and all(food in food_by_name for food in raw_food):
            return [food_by_name[food] for food in raw_food]
        print("Enter valid food names separated by spaces.")
