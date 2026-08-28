"""Expected-value greedy agent for final-score potential.

This agent is intentionally separate from ``GreedyBaselineAgent``. The baseline
maximizes realized score from one action. ``PotentialPointsAgent`` still chooses
one legal action greedily, but ranks actions by the estimated final-score
potential of the resulting state.

Power timing valuation plan:
- Brown powers: value repeated activation potential from the bird's habitat.
  Food, cards, eggs, tucks, caches, and predator hunts are discounted by
  expected remaining habitat activations and current conversion demand.
- Pink powers: value passive opponent-turn triggers from remaining opponent
  actions, capped by egg capacity or point-token ceilings where visible.
- Teal powers: value end-of-round triggers once per remaining round after the
  bird is in play, with sharply lower value in round 4.
- Yellow powers: value end-of-game triggers as one-shot conversion potential
  when the bird can be in play before final scoring. Exact handlers should later
  replace text heuristics for each yellow card pattern.
- White powers: value one-shot "when played" effects on unplayed hand birds.
  White powers already realized by ``apply_action`` should flow through realized
  score/resource deltas; this evaluator estimates only remaining future use.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from math import ceil

from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, FoodCost, FoodType, Habitat, PowerColor
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import (
    apply_action,
    egg_cost_for_slot,
    legal_actions_for_current_player,
    score_player,
)
from wingspan_ai.state.models import BirdSlot, GameState, PlayerState


@dataclass(frozen=True)
class PotentialValueBreakdown:
    """Explainable estimate of a player's current final-score potential."""

    realized_score: float
    playable_bird_potential: float
    food_conversion_potential: float
    egg_conversion_potential: float
    card_conversion_potential: float
    engine_power_potential: float
    bonus_card_potential: float
    round_goal_potential: float
    endgame_conversion_potential: float
    dead_resource_penalty: float

    @property
    def total(self) -> float:
        return (
            self.realized_score
            + self.playable_bird_potential
            + self.food_conversion_potential
            + self.egg_conversion_potential
            + self.card_conversion_potential
            + self.engine_power_potential
            + self.bonus_card_potential
            + self.round_goal_potential
            + self.endgame_conversion_potential
            - self.dead_resource_penalty
        )

    def telemetry_payload(self) -> dict[str, float]:
        payload = asdict(self)
        payload["total"] = self.total
        return payload


@dataclass(frozen=True)
class ActionPotentialEvaluation:
    """Potential-value result for one action candidate."""

    action: LegalAction
    value_delta: float
    realized_delta: float
    before: PotentialValueBreakdown
    after: PotentialValueBreakdown

    def telemetry_payload(self) -> dict:
        return {
            "action": self.action.model_dump(mode="json"),
            "action_label": render_action(self.action),
            "value_delta": round(self.value_delta, 3),
            "realized_delta": round(self.realized_delta, 3),
            "after_total": round(self.after.total, 3),
        }


@dataclass
class PotentialPointsAgent:
    """Choose actions by estimated final-score potential instead of current points only."""

    agent_id: str = "potential_points"
    final_search_turns: int = 5
    search_depth: int = 3
    top_alternatives: int = 5

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("PotentialPointsAgent cannot select from an empty action list")

        turns_remaining = _turns_remaining_for_player(
            state,
            state.active_player.player_id,
        )
        if turns_remaining <= self.final_search_turns:
            return self._select_with_endgame_search(state, legal_actions)

        evaluations = self.evaluate_actions(state, legal_actions)
        return max(
            evaluations,
            key=lambda item: (
                item.value_delta,
                item.realized_delta,
                _action_priority(item.action),
            ),
        ).action

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def evaluate_actions(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
    ) -> list[ActionPotentialEvaluation]:
        player_id = state.active_player.player_id
        before = evaluate_state_potential(state, player_id)
        evaluations: list[ActionPotentialEvaluation] = []
        for action in legal_actions:
            next_state = apply_action(state, action)
            after = evaluate_state_potential(next_state, player_id)
            evaluations.append(
                ActionPotentialEvaluation(
                    action=action,
                    value_delta=after.total - before.total,
                    realized_delta=after.realized_score - before.realized_score,
                    before=before,
                    after=after,
                )
            )
        return evaluations

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        evaluations = self.evaluate_actions(state, legal_actions)
        selected_evaluation = next(
            evaluation for evaluation in evaluations if evaluation.action == selected_action
        )
        ranked = sorted(
            evaluations,
            key=lambda item: (item.value_delta, item.realized_delta, _action_priority(item.action)),
            reverse=True,
        )
        return {
            "policy": "potential_points",
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
            "selected_action_label": render_action(selected_action),
            "selected_value_delta": round(selected_evaluation.value_delta, 3),
            "selected_realized_delta": round(selected_evaluation.realized_delta, 3),
            "selected_after_breakdown": selected_evaluation.after.telemetry_payload(),
            "top_alternatives": [
                evaluation.telemetry_payload() for evaluation in ranked[: self.top_alternatives]
            ],
            "endgame_search_used": _turns_remaining_for_player(
                state,
                state.active_player.player_id,
            )
            <= self.final_search_turns,
        }

    def _select_with_endgame_search(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
    ) -> LegalAction:
        player_id = state.active_player.player_id
        scored_actions = [
            (
                _search_action_value(
                    state,
                    action,
                    player_id,
                    depth=min(self.search_depth, _turns_remaining_for_player(state, player_id)),
                ),
                action,
            )
            for action in legal_actions
        ]
        return max(
            scored_actions,
            key=lambda item: (
                item[0],
                _immediate_score_delta(state, item[1], player_id),
                _action_priority(item[1]),
            ),
        )[1]


def evaluate_state_potential(state: GameState, player_id: str) -> PotentialValueBreakdown:
    """Estimate current final-score potential for one player."""

    player = _get_player(state, player_id)
    realized_score = float(score_player(state, player_id).total)
    turns_remaining = _turns_remaining_for_player(state, player_id)
    if state.round_state.game_over or turns_remaining <= 0:
        return PotentialValueBreakdown(
            realized_score=realized_score,
            playable_bird_potential=0,
            food_conversion_potential=0,
            egg_conversion_potential=0,
            card_conversion_potential=0,
            engine_power_potential=0,
            bonus_card_potential=0,
            round_goal_potential=0,
            endgame_conversion_potential=0,
            dead_resource_penalty=_dead_resource_penalty(player, turns_remaining),
        )

    demand = _food_demand(player)
    phase_discount = _future_discount(turns_remaining)
    return PotentialValueBreakdown(
        realized_score=realized_score,
        playable_bird_potential=_playable_bird_potential(state, player, turns_remaining)
        * phase_discount,
        food_conversion_potential=_food_conversion_potential(player, demand, turns_remaining),
        egg_conversion_potential=_egg_conversion_potential(player, turns_remaining),
        card_conversion_potential=_card_conversion_potential(player, turns_remaining),
        engine_power_potential=_engine_power_potential(state, player, demand, turns_remaining),
        bonus_card_potential=_bonus_card_potential(player, turns_remaining) * phase_discount,
        round_goal_potential=_round_goal_potential(state, player, turns_remaining),
        endgame_conversion_potential=_endgame_conversion_potential(player, turns_remaining),
        dead_resource_penalty=_dead_resource_penalty(player, turns_remaining),
    )


def _search_action_value(
    state: GameState,
    action: LegalAction,
    player_id: str,
    depth: int,
) -> float:
    next_state = apply_action(state, action)
    if depth <= 1 or next_state.round_state.game_over:
        return _terminal_planning_value(next_state, player_id)
    player = _get_player(next_state, player_id)
    if next_state.active_player.player_id != player_id or player.action_cubes_available <= 0:
        return _terminal_planning_value(next_state, player_id)
    legal_actions = legal_actions_for_current_player(next_state)
    if not legal_actions:
        return _terminal_planning_value(next_state, player_id)
    return max(
        _search_action_value(next_state, next_action, player_id, depth - 1)
        for next_action in legal_actions
    )


def _terminal_planning_value(state: GameState, player_id: str) -> float:
    potential = evaluate_state_potential(state, player_id)
    player = _get_player(state, player_id)
    turns_remaining = _turns_remaining_for_player(state, player_id)
    if turns_remaining <= 1:
        return float(score_player(state, player_id).total) - _dead_resource_penalty(
            player,
            turns_remaining,
        )
    return potential.total


def _playable_bird_potential(
    state: GameState,
    player: PlayerState,
    turns_remaining: int,
) -> float:
    candidates = []
    for card in player.hand:
        best_action_cost = _estimated_actions_to_play(state, player, card)
        if best_action_cost > turns_remaining:
            continue
        candidates.append(_projected_bird_value(card, player, turns_remaining, best_action_cost))

    candidates.sort(reverse=True)
    max_birds_to_play = max(turns_remaining - 1, 0)
    return sum(candidates[:max_birds_to_play])


def _food_conversion_potential(
    player: PlayerState,
    demand: Counter[FoodType],
    turns_remaining: int,
) -> float:
    if turns_remaining <= 1:
        return 0.0
    value = 0.0
    for food_type, token_count in player.food_tokens.items():
        needed_count = min(token_count, demand.get(food_type, 0))
        surplus_count = max(token_count - needed_count, 0)
        value += needed_count * 0.9
        value += surplus_count * (0.15 if turns_remaining > 3 else 0.0)
    return value


def _egg_conversion_potential(player: PlayerState, turns_remaining: int) -> float:
    if not player.played_birds:
        return 0.0
    if turns_remaining <= 1:
        return float(min(player.available_egg_capacity, 1))
    return min(player.available_egg_capacity, turns_remaining * _egg_rate(player)) * 0.85


def _card_conversion_potential(player: PlayerState, turns_remaining: int) -> float:
    if turns_remaining <= 1:
        return _hand_cards_that_can_still_score(player) * 0.2
    playable_count = sum(1 for card in player.hand if _food_deficit(player, card.food_cost) <= 1)
    speculative_count = max(len(player.hand) - playable_count, 0)
    return playable_count * 0.65 + speculative_count * 0.2


def _engine_power_potential(
    state: GameState,
    player: PlayerState,
    demand: Counter[FoodType],
    turns_remaining: int,
) -> float:
    total = 0.0
    for habitat, slots in player.habitats.items():
        expected_triggers = _expected_habitat_activations(state, player, habitat, turns_remaining)
        for slot in slots:
            total += _played_power_value(slot, demand, expected_triggers, turns_remaining)
    return total


def _played_power_value(
    slot: BirdSlot,
    demand: Counter[FoodType],
    expected_triggers: float,
    turns_remaining: int,
) -> float:
    power = slot.card.power
    if power.color == PowerColor.NONE or not power.text:
        return 0.0
    lowered = power.text.lower()

    if power.color == PowerColor.BROWN:
        return expected_triggers * _per_trigger_power_value(lowered, demand, slot)
    if power.color == PowerColor.PINK:
        return (turns_remaining * 0.35) * _per_trigger_power_value(lowered, demand, slot)
    if power.color == PowerColor.TEAL:
        remaining_triggers = _remaining_teal_triggers(turns_remaining)
        return remaining_triggers * _per_trigger_power_value(lowered, demand, slot)
    if power.color == PowerColor.YELLOW:
        return _yellow_end_game_power_value(lowered, demand, slot, turns_remaining)
    if power.color == PowerColor.WHITE:
        return 0.0
    return 0.0


def _per_trigger_power_value(
    lowered_power_text: str,
    demand: Counter[FoodType],
    slot: BirdSlot,
) -> float:
    value = 0.0
    if "tuck" in lowered_power_text:
        value += 1.0
    if "cache" in lowered_power_text:
        value += 1.0
    if "predator" in lowered_power_text or "roll" in lowered_power_text:
        value += 0.35
    if "draw" in lowered_power_text and "[card]" in lowered_power_text:
        value += 0.55
    if "lay" in lowered_power_text and "[egg]" in lowered_power_text:
        value += 0.9 if slot.available_egg_capacity > 0 else 0.0
    for food_type in BASE_FOOD_TYPES:
        if f"[{_food_power_token(food_type)}]" in lowered_power_text:
            value += 0.85 if demand.get(food_type, 0) > 0 else 0.25
    if "[wild]" in lowered_power_text or "[die]" in lowered_power_text:
        value += 0.85 if sum(demand.values()) > 0 else 0.25
    return value


def _bonus_card_potential(player: PlayerState, turns_remaining: int) -> float:
    if not player.bonus_cards or turns_remaining <= 0:
        return 0.0

    matching_hand_cards = 0
    bonus_names = {
        bonus.name.split("[", maxsplit=1)[0].strip().lower() for bonus in player.bonus_cards
    }
    for card in player.hand:
        matching_hand_cards += _card_bonus_match_count(card, bonus_names)
    return min(matching_hand_cards, turns_remaining) * 0.75


def _round_goal_potential(
    state: GameState,
    player: PlayerState,
    turns_remaining: int,
) -> float:
    goal_index = state.round_state.round_number - 1
    if goal_index < 0 or goal_index >= len(state.round_goals):
        return 0.0
    turns_left_in_round = min(player.action_cubes_available, turns_remaining)
    if turns_left_in_round <= 0:
        return 0.0

    goal = state.round_goals[goal_index]
    goal_name = goal.name.lower()
    current_count = _round_goal_count(goal_name, player)
    opponent_counts = [
        _round_goal_count(goal_name, candidate)
        for candidate in state.players
        if candidate.player_id != player.player_id
    ]
    best_other = max(opponent_counts, default=0)
    gap = max(best_other - current_count + 1, 0)
    if gap == 0:
        return min(2.0, turns_left_in_round * 0.35)
    if gap > turns_left_in_round:
        return 0.0
    return max(0.0, (turns_left_in_round - gap + 1) * 0.6)


def _endgame_conversion_potential(player: PlayerState, turns_remaining: int) -> float:
    if turns_remaining > 5:
        return 0.0
    egg_room = min(player.available_egg_capacity, max(turns_remaining, 0) * _egg_rate(player))
    tuck_or_cache_power_count = sum(
        1
        for slot in player.played_birds
        if slot.card.power.text
        and any(token in slot.card.power.text.lower() for token in ("tuck", "cache"))
    )
    playable_birds = sum(1 for card in player.hand if _food_deficit(player, card.food_cost) == 0)
    return egg_room * 0.5 + min(tuck_or_cache_power_count, turns_remaining) + playable_birds * 0.4


def _yellow_end_game_power_value(
    lowered_power_text: str,
    demand: Counter[FoodType],
    slot: BirdSlot,
    turns_remaining: int,
) -> float:
    if turns_remaining <= 0:
        return 0.0
    value = _per_trigger_power_value(lowered_power_text, demand, slot)
    if "end of the game" in lowered_power_text or "game end" in lowered_power_text:
        value += 0.5
    return min(value, 3.0)


def _dead_resource_penalty(player: PlayerState, turns_remaining: int) -> float:
    if turns_remaining > 2:
        return 0.0
    hand_demand = _food_demand(player)
    dead_food = 0
    for food_type, count in player.food_tokens.items():
        dead_food += max(count - hand_demand.get(food_type, 0), 0)
    dead_cards = max(len(player.hand) - _hand_cards_that_can_still_score(player), 0)
    multiplier = 0.45 if turns_remaining == 1 else 0.2
    return dead_food * multiplier + dead_cards * 0.15


def _projected_bird_value(
    card: BirdCard,
    player: PlayerState,
    turns_remaining: int,
    action_cost: int,
) -> float:
    time_weight = max((turns_remaining - action_cost + 1) / max(turns_remaining, 1), 0.0)
    power_value = _unplayed_power_value(card, player, turns_remaining)
    egg_capacity_value = min(card.egg_limit, max(turns_remaining - action_cost, 0) * 0.5) * 0.35
    return (card.victory_points + power_value + egg_capacity_value) * time_weight


def _unplayed_power_value(card: BirdCard, player: PlayerState, turns_remaining: int) -> float:
    power = card.power
    if power.color == PowerColor.NONE or not power.text:
        return 0.0
    lowered = power.text.lower()
    demand = _food_demand(player)
    if power.color == PowerColor.WHITE:
        return _per_trigger_power_value(lowered, demand, BirdSlot(card=card))
    if power.color == PowerColor.YELLOW:
        return _yellow_end_game_power_value(lowered, demand, BirdSlot(card=card), turns_remaining)
    if power.color == PowerColor.TEAL:
        return _remaining_teal_triggers(turns_remaining) * _per_trigger_power_value(
            lowered,
            demand,
            BirdSlot(card=card),
        )
    if power.color == PowerColor.BROWN:
        return min(turns_remaining, 4) * 0.35 * _per_trigger_power_value(
            lowered,
            demand,
            BirdSlot(card=card),
        )
    if power.color == PowerColor.PINK:
        return turns_remaining * 0.15 * _per_trigger_power_value(
            lowered,
            demand,
            BirdSlot(card=card),
        )
    return 0.0


def _estimated_actions_to_play(state: GameState, player: PlayerState, card: BirdCard) -> int:
    food_actions = ceil(_food_deficit(player, card.food_cost) / max(_forest_food_rate(player), 1))
    open_habitats = [habitat for habitat in card.habitats if len(player.habitats[habitat]) < 5]
    if not open_habitats:
        return 999
    egg_cost = min(egg_cost_for_slot(len(player.habitats[habitat])) for habitat in open_habitats)
    egg_actions = ceil(max(egg_cost - player.total_eggs, 0) / max(_egg_rate(player), 1))
    return food_actions + egg_actions + 1


def _food_deficit(player: PlayerState, food_cost: FoodCost) -> int:
    remaining_food = dict(player.food_tokens)
    deficit = 0
    for food_type, count in food_cost.fixed.items():
        available = remaining_food.get(food_type, 0)
        if available < count:
            deficit += count - available
            remaining_food[food_type] = 0
        else:
            remaining_food[food_type] = available - count
    any_cost = food_cost.wild_food_count + food_cost.choice_food_count
    return deficit + max(any_cost - sum(remaining_food.values()), 0)


def _food_demand(player: PlayerState) -> Counter[FoodType]:
    demand: Counter[FoodType] = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            demand[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    return demand


def _forest_food_rate(player: PlayerState) -> int:
    forest_count = len(player.habitats[Habitat.FOREST])
    if forest_count >= 4:
        return 3
    if forest_count >= 2:
        return 2
    return 1


def _egg_rate(player: PlayerState) -> int:
    grassland_count = len(player.habitats[Habitat.GRASSLAND])
    if grassland_count >= 4:
        return 4
    if grassland_count >= 2:
        return 3
    return 2


def _expected_habitat_activations(
    state: GameState,
    player: PlayerState,
    habitat: Habitat,
    turns_remaining: int,
) -> float:
    if turns_remaining <= 0:
        return 0.0
    demand = _food_demand(player)
    if habitat == Habitat.FOREST:
        share = 0.45 if sum(demand.values()) else 0.18
    elif habitat == Habitat.GRASSLAND:
        share = 0.4 if player.available_egg_capacity else 0.05
    else:
        share = 0.28 if len(player.hand) < max(3, turns_remaining // 2) else 0.14
    if state.round_state.round_number >= 4:
        share *= 0.75
    return min(float(turns_remaining), turns_remaining * share)


def _remaining_teal_triggers(turns_remaining: int) -> int:
    if turns_remaining <= 0:
        return 0
    return min(4, max(1, ceil(turns_remaining / 6)))


def _round_goal_count(goal_name: str, player: PlayerState) -> int:
    if "[bird]" in goal_name and "[forest]" in goal_name:
        return len(player.habitats[Habitat.FOREST])
    if "[bird]" in goal_name and "[grassland]" in goal_name:
        return len(player.habitats[Habitat.GRASSLAND])
    if "[bird]" in goal_name and "[wetland]" in goal_name:
        return len(player.habitats[Habitat.WETLAND])
    if "[egg]" in goal_name and "forest" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.FOREST])
    if "[egg]" in goal_name and "grassland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.GRASSLAND])
    if "[egg]" in goal_name and "wetland" in goal_name:
        return sum(slot.eggs for slot in player.habitats[Habitat.WETLAND])
    if "[bird]" in goal_name:
        return len(player.played_birds)
    if "[egg]" in goal_name:
        return player.total_eggs
    return 0


def _card_bonus_match_count(card: BirdCard, bonus_names: set[str]) -> int:
    count = 0
    if "bird feeder" in bonus_names and FoodType.SEED in card.food_cost.fixed:
        count += 1
    if "backyard birder" in bonus_names and card.victory_points < 4:
        count += 1
    if "falconer" in bonus_names and card.predator:
        count += 1
    if "bird counter" in bonus_names and card.flocking:
        count += 1
    if "rodentologist" in bonus_names and FoodType.RODENT in card.food_cost.fixed:
        count += 1
    if "fishery manager" in bonus_names and FoodType.FISH in card.food_cost.fixed:
        count += 1
    if "viticulturalist" in bonus_names and FoodType.FRUIT in card.food_cost.fixed:
        count += 1
    if card.bonus_card_tags:
        count += len(card.bonus_card_tags)
    return count


def _hand_cards_that_can_still_score(player: PlayerState) -> int:
    return sum(1 for card in player.hand if _food_deficit(player, card.food_cost) == 0)


def _future_discount(turns_remaining: int) -> float:
    if turns_remaining <= 1:
        return 0.15
    if turns_remaining <= 3:
        return 0.45
    if turns_remaining <= 5:
        return 0.7
    return 1.0


def _immediate_score_delta(state: GameState, action: LegalAction, player_id: str) -> float:
    before_score = score_player(state, player_id).total
    after_score = score_player(apply_action(state, action), player_id).total
    return float(after_score - before_score)


def _turns_remaining_for_player(state: GameState, player_id: str) -> int:
    player = _get_player(state, player_id)
    return player.action_cubes_available


def _action_priority(action: LegalAction) -> int:
    if action.action_type == ActionType.PLAY_BIRD:
        return 40
    if action.action_type == ActionType.LAY_EGGS:
        return 30
    if action.action_type == ActionType.GAIN_FOOD:
        return 20
    if action.action_type == ActionType.DRAW_CARDS:
        return 10
    return 0


def _get_player(state: GameState, player_id: str) -> PlayerState:
    return next(player for player in state.players if player.player_id == player_id)


def _food_power_token(food_type: FoodType) -> str:
    if food_type == FoodType.INVERTEBRATE:
        return "invertebrate"
    return food_type.value
