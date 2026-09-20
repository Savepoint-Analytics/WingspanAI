"""Plain-text rendering of a game state from one seat's point of view.

Shared by the archived-game viewer (``analysis/game_viewer.py``) and the
console human player (``agents/human_cli.py``), so a human at the terminal
sees exactly the board the viewer later replays. Public information only,
plus the private hand and bonus card of the seat asked for (``pov``), or of
every seat when ``all_private`` is set (the viewer's debugging mode).
"""

from __future__ import annotations

from wingspan_ai.content.schemas import BirdCard, FoodType, Habitat
from wingspan_ai.rules.base_game import score_player
from wingspan_ai.state.models import GameState, PlayerState

FOOD_ABBR = {
    FoodType.INVERTEBRATE: "inv",
    FoodType.SEED: "seed",
    FoodType.FISH: "fish",
    FoodType.FRUIT: "fruit",
    FoodType.RODENT: "rod",
    FoodType.NECTAR: "nec",
}
HABITAT_ABBR = {Habitat.FOREST: "F", Habitat.GRASSLAND: "G", Habitat.WETLAND: "W"}


def food_str(tokens: dict) -> str:
    parts = [f"{FOOD_ABBR.get(k, str(k))}×{v}" for k, v in tokens.items() if v]
    return " ".join(parts) or "none"


def cost_str(card: BirdCard) -> str:
    cost = card.food_cost
    parts = [f"{FOOD_ABBR[f]}×{n}" if n > 1 else FOOD_ABBR[f] for f, n in cost.fixed.items()]
    if cost.wild_food_count:
        parts.append(f"wild×{cost.wild_food_count}")
    if cost.choice_food_count:
        parts.append(f"choice×{cost.choice_food_count}")
    return "+".join(parts) or "free"


def card_line(card: BirdCard) -> str:
    habitats = "".join(HABITAT_ABBR[h] for h in sorted(card.habitats, key=lambda h: h.value))
    power = card.power.text or "—"
    color = card.power.color.value if card.power.color else "none"
    return (
        f"{card.common_name} [{card.victory_points}vp {habitats} {cost_str(card)} "
        f"eggs≤{card.egg_limit} {card.nest_type.value if card.nest_type else '-'}] "
        f"({color}) {power}"
    )


def board_lines(state: GameState, pov: str, all_private: bool) -> list[str]:
    lines = []
    for player in state.players:
        score = score_player(state, player.player_id)
        who = f"{player.player_id} ({player.agent_id})"
        marker = " ◀ POV" if player.player_id == pov else ""
        lines.append(
            f"  {who}{marker}: score {score.total} "
            f"(birds {score.bird_points}, bonus {score.bonus_points}, goals "
            f"{score.round_goal_points}, eggs {score.egg_points}, cache "
            f"{score.cached_food_points}, tuck {score.tucked_card_points}); "
            f"cubes {player.action_cubes_available}; food {food_str(player.food_tokens)}; "
            f"hand {len(player.hand)}; bonus {len(player.bonus_cards)}"
        )
        for habitat in (Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND):
            slots = player.habitats[habitat]
            if not slots:
                lines.append(f"      {HABITAT_ABBR[habitat]}: —")
                continue
            cells = []
            for slot in slots:
                extras = []
                if slot.eggs:
                    extras.append(f"e{slot.eggs}")
                if slot.cached_food:
                    extras.append(f"c{slot.cached_food}")
                if slot.tucked_cards:
                    extras.append(f"t{slot.tucked_cards}")
                cells.append(
                    f"{slot.card.common_name}({slot.card.victory_points}"
                    + ("," + ",".join(extras) if extras else "")
                    + ")"
                )
            lines.append(f"      {HABITAT_ABBR[habitat]}: " + " | ".join(cells))
        if player.player_id == pov or all_private:
            lines += private_lines(player)
    lines.append(
        "  tray: " + " | ".join(card_line(c).split(" (")[0] for c in state.bird_tray)
        if state.bird_tray
        else "  tray: empty"
    )
    lines.append("  feeder: " + " ".join(face.value for face in state.birdfeeder.dice))
    lines.append(
        "  round goals: "
        + "; ".join(
            f"R{i + 1} {goal.name}" + (" ◀" if i + 1 == state.round_state.round_number else "")
            for i, goal in enumerate(state.round_goals)
        )
    )
    return lines


def private_lines(player: PlayerState) -> list[str]:
    lines = [f"      hand ({len(player.hand)}):"]
    for card in player.hand:
        lines.append(f"        - {card_line(card)}")
    for bonus in player.bonus_cards:
        lines.append(f"      bonus: {bonus.name} — {bonus.condition} ({bonus.victory_point_text})")
    return lines
