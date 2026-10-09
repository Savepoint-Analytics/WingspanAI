"""Console-backed human player policy for local simulations."""

from __future__ import annotations

from dataclasses import dataclass

from wingspan_ai.agents.setup import InitialSelectionContext
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import LegalAction, render_action
from wingspan_ai.rules.base_game import (
    BIRD_FOOD_SELECTION_TOTAL,
    ROUND_GOAL_GREEN_SCORES,
    InitialSelection,
    choose_default_initial_selection,
    legal_actions_for_current_player,
)
from wingspan_ai.state.models import GameState, PlayerState
from wingspan_ai.state.render import board_lines, card_line, food_str


@dataclass
class HumanCliAgent:
    """Interactive command-line policy that chooses from generated legal actions.

    Shows the same board the archived-game viewer renders (every seat's
    board, live scores, tray, feeder, round goals) plus this seat's own hand
    and bonus card, then the legal actions by number. Its games go through
    the ordinary runner and batch flow, so a human game is archived,
    replay-validated and viewable like any agent game
    (``flows/human_vs_agent.py``, ``docs/experiments/self_play_opponent_plan.md``).
    """

    agent_id: str = "human_cli"
    use_default_setup: bool = True

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        if self.use_default_setup:
            return choose_default_initial_selection(player)

        for line in setup_table_lines(player, context):
            print(line)
        print(f"\nYour setup ({player.player_id})")
        print("Bird hand:")
        for index, card in enumerate(player.hand, start=1):
            print(f"{index}. {card_line(card)}")
        print(
            f"Keep any number of birds; you get {BIRD_FOOD_SELECTION_TOTAL} minus that many food "
            "(e.g. keep 2 birds -> 3 food, keep 3 -> 2 food). Enter 0 to keep none."
        )
        bird_indices = _read_indices(
            "Keep which bird numbers? ",
            max_index=len(player.hand),
            allow_none=True,
        )
        kept_birds = [player.hand[index - 1].common_name for index in bird_indices]

        print("Bonus cards:")
        for index, card in enumerate(player.bonus_cards, start=1):
            print(f"{index}. {card.name} — {card.condition} ({card.victory_point_text})")
        bonus_indices = _read_indices(
            "Keep one bonus number? ", max_index=len(player.bonus_cards), exactly=1
        )
        kept_bonus = [player.bonus_cards[bonus_indices[0] - 1].name]

        starting_food_count = BIRD_FOOD_SELECTION_TOTAL - len(kept_birds)
        starting_food = _read_food_choices(starting_food_count)
        return InitialSelection(
            player_id=player.player_id,
            kept_bird_names=kept_birds,
            kept_bonus_card_names=kept_bonus,
            starting_food=starting_food,
        )

    def observe_setup_complete(self, state: GameState) -> None:
        """Print every seat's public setup result once all seats have chosen.

        Opening choices are simultaneous, so this runs after the last seat
        has chosen. Only public information is shown: how many birds each
        seat kept (hand size), and its starting food. Which birds and which
        bonus card an opponent kept stay hidden, as at the table.
        """

        if self.use_default_setup:
            return
        print("\n" + "=" * 72)
        print("SETUP RESULT (public)")
        for player in state.players:
            kept = len(player.hand)
            food = sum(player.food_tokens.values())
            print(
                f"  {player.player_id} ({player.agent_id}): kept {kept} bird"
                f"{'' if kept == 1 else 's'} + {food} food "
                f"[{food_str(player.food_tokens)}], 1 bonus card"
            )
        print("=" * 72)

    def choose_action(self, state: GameState) -> LegalAction:
        legal_actions = legal_actions_for_current_player(state)
        if not legal_actions:
            raise ValueError("HumanCliAgent cannot select from an empty action list")

        player = state.active_player
        print(
            f"\nRound {state.round_state.round_number}, "
            f"turn {state.round_state.turn_number} "
            f"(action {state.round_state.round_action_number} this round, "
            f"global action {state.round_state.global_turn_number})"
        )
        print(f"Active player: {player.player_id}")
        for line in board_lines(state, pov=player.player_id, all_private=False):
            print(line)
        print("Legal actions:")
        for index, action in enumerate(legal_actions, start=1):
            print(f"{index}. {render_action(action)}")

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


def _read_indices(
    prompt: str,
    *,
    max_index: int,
    allow_none: bool = False,
    exactly: int | None = None,
) -> list[int]:
    while True:
        raw_value = input(prompt).replace(",", " ").split()
        if allow_none and raw_value == ["0"]:
            return []
        if raw_value and all(value.isdigit() for value in raw_value):
            indices = [int(value) for value in raw_value]
            if (
                all(1 <= index <= max_index for index in indices)
                and len(set(indices)) == len(indices)
                and (exactly is None or len(indices) == exactly)
            ):
                return indices
        if exactly == 1:
            print(f"Enter one number from 1 to {max_index}.")
        else:
            print(
                "Enter distinct card numbers separated by spaces"
                + (" (0 for none)." if allow_none else ".")
            )


def setup_table_lines(player: PlayerState, context: InitialSelectionContext | None) -> list[str]:
    """The public table a person sees before choosing an opening hand.

    Round goals (with the green-side placement points this simulator scores),
    the birdfeeder as rolled, the three face-up tray birds, and who is in
    each seat. Shown once, at setup, so an opening can be planned around them.
    """

    lines = ["", "=" * 72, f"GAME SETUP — you are {player.player_id}", "=" * 72]
    if context is None:
        return lines + ["  (no public setup context supplied)"]
    if context.seat_agent_ids:
        lines.append("Seats (player_1 takes the first turn of round 1):")
        for index, agent_id in enumerate(context.seat_agent_ids, start=1):
            you = "  ◀ you" if f"player_{index}" == player.player_id else ""
            lines.append(f"  player_{index}: {agent_id}{you}")
    lines.append("End-of-round goals (green side; points for 1st/2nd/3rd place):")
    for round_number, goal_name in enumerate(context.round_goal_names, start=1):
        points = ROUND_GOAL_GREEN_SCORES.get(round_number, ROUND_GOAL_GREEN_SCORES[4])[:3]
        lines.append(f"  R{round_number}: {goal_name}   ({'/'.join(map(str, points))} pts)")
    feeder = " | ".join(context.birdfeeder_faces) or "empty"
    lines.append(f"Birdfeeder ({len(context.birdfeeder_faces)} dice): {feeder}")
    lines.append("Bird tray (face up):")
    for card in context.bird_tray:
        lines.append(f"  - {card_line(card)}")
    if not context.bird_tray:
        lines.append("  (empty)")
    lines.append("=" * 72)
    return lines


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
