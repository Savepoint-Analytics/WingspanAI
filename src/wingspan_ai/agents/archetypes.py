"""Scripted strategy archetype baseline agents."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from wingspan_ai.agents.setup import ArchetypeSetupPolicy, InitialSelectionContext
from wingspan_ai.agents.tray_preference import (
    bonus_card_focus_affinity,
    card_draw_affinity,
    drawn_tray_cards,
    egg_focus_affinity,
    engine_builder_affinity,
    food_acceleration_affinity,
    round_goal_chase_affinity,
)
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    InitialSelection,
    apply_action,
    legal_actions_for_current_player,
    score_player,
)
from wingspan_ai.state.models import GameState, PlayerState


class StrategyArchetype(StrEnum):
    """Named strategy archetypes for early behavioural signatures."""

    EGG_FOCUS = "egg_focus"
    ENGINE_BUILDER = "engine_builder"
    FOOD_ACCELERATION = "food_acceleration"
    CARD_DRAW = "card_draw"
    BONUS_CARD_FOCUS = "bonus_card_focus"
    ROUND_GOAL_CHASE = "round_goal_chase"


@dataclass
class StrategyArchetypeAgent:
    """A simple weighted policy for one interpretable Wingspan strategy."""

    archetype: StrategyArchetype
    agent_id: str | None = None
    setup_policy: ArchetypeSetupPolicy | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.agent_id is None:
            self.agent_id = f"archetype_{self.archetype.value}"
        if self.setup_policy is None:
            self.setup_policy = ArchetypeSetupPolicy(self.archetype.value)

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        if self.setup_policy is None:
            self.setup_policy = ArchetypeSetupPolicy(self.archetype.value)
        return self.setup_policy.choose_initial_selection(player, context)

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("StrategyArchetypeAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total
        scored_actions = [
            (
                _score_action_for_archetype(state, action, self.archetype, before_score),
                action,
            )
            for action in legal_actions
        ]
        return max(scored_actions, key=lambda item: item[0])[1]

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict:
        """Explain the archetype-weighted action for telemetry."""

        player_id = state.active_player.player_id
        before_score = score_player(state, player_id).total
        return {
            "policy": "strategy_archetype",
            "archetype": self.archetype.value,
            "legal_action_count": len(legal_actions),
            "selected_action_type": selected_action.action_type.value,
            "action_score": _score_action_for_archetype(
                state,
                selected_action,
                self.archetype,
                before_score,
            ),
            "food_need_score": _food_need_score(state, selected_action),
        }


def _score_action_for_archetype(
    state: GameState,
    action: LegalAction,
    archetype: StrategyArchetype,
    before_score: int,
) -> float:
    score = _base_immediate_score(state, action, before_score)
    score += _tray_preference(state, action, archetype)

    if archetype == StrategyArchetype.EGG_FOCUS:
        return score + _egg_focus_bonus(state, action)
    if archetype == StrategyArchetype.ENGINE_BUILDER:
        return score + _engine_builder_bonus(state, action)
    if archetype == StrategyArchetype.FOOD_ACCELERATION:
        return score + _food_acceleration_bonus(state, action)
    if archetype == StrategyArchetype.CARD_DRAW:
        return score + _card_draw_bonus(state, action)
    if archetype == StrategyArchetype.BONUS_CARD_FOCUS:
        return score + _bonus_card_focus_bonus(state, action)
    if archetype == StrategyArchetype.ROUND_GOAL_CHASE:
        return score + _round_goal_chase_bonus(state, action)
    return score


def _base_immediate_score(state: GameState, action: LegalAction, before_score: int) -> float:
    player_id = state.active_player.player_id
    next_state = apply_action(state, action)
    return float(score_player(next_state, player_id).total - before_score)


#: A tray card of unremarkable quality. Affinities above this are preferred,
#: below it avoided, so the term is roughly zero-mean across a typical tray.
_TYPICAL_TRAY_AFFINITY = 3.0
_TRAY_PREFERENCE_SCALE = 0.25
#: Bounded so tray choice never overrides which action family to take.
_TRAY_PREFERENCE_LIMIT = 0.75


def _tray_preference(
    state: GameState,
    action: LegalAction,
    archetype: StrategyArchetype,
) -> float:
    """Archetype-specific value of the face-up cards a draw would take.

    Without this every archetype scored all draws identically and took tray
    index 0 regardless of the cards on offer.
    """

    if action.action_type != ActionType.DRAW_CARDS:
        return 0.0
    cards = drawn_tray_cards(state, action)
    if not cards:
        return 0.0
    player = state.active_player
    if archetype == StrategyArchetype.EGG_FOCUS:
        scorer = egg_focus_affinity
    elif archetype == StrategyArchetype.ENGINE_BUILDER:
        scorer = engine_builder_affinity
    elif archetype == StrategyArchetype.FOOD_ACCELERATION:
        scorer = food_acceleration_affinity
    elif archetype == StrategyArchetype.CARD_DRAW:
        scorer = card_draw_affinity
    elif archetype == StrategyArchetype.BONUS_CARD_FOCUS:
        scorer = bonus_card_focus_affinity
    else:
        def scorer(card, owner):
            return round_goal_chase_affinity(card, owner, state)

    best = max(scorer(card, player) for card in cards)
    # Centre on a typical affinity and bound the result. Added directly, this
    # term raised the value of *drawing* relative to playing or laying, which
    # pushed bonus-card-focus from a 37% draw rate to 63% and cost it 17 points
    # per game. It must order draws among themselves, not shift family choice.
    centred = (best - _TYPICAL_TRAY_AFFINITY) * _TRAY_PREFERENCE_SCALE
    return max(-_TRAY_PREFERENCE_LIMIT, min(_TRAY_PREFERENCE_LIMIT, centred))


def _played_card(state: GameState, action: LegalAction):
    """Return the hand card a play-bird action refers to, if any."""

    if action.action_type != ActionType.PLAY_BIRD or action.bird_common_name is None:
        return None
    return next(
        (
            card
            for card in state.active_player.hand
            if card.common_name == action.bird_common_name
        ),
        None,
    )


def _hand_pressure(state: GameState) -> float:
    """Positive when the hand is thin enough that drawing is worth a detour."""

    return max(0.0, 4.0 - len(state.active_player.hand))


def _egg_focus_bonus(state: GameState, action: LegalAction) -> float:
    """Maximize eggs: lay whenever possible, and prefer high-capacity birds."""

    if action.action_type == ActionType.LAY_EGGS:
        return 8.0 + float(action.egg_count or 0)
    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        # Egg capacity is what sustains the strategy, so weight it heavily.
        return 2.0 + (float(card.egg_limit) * 1.5 if card is not None else 0.0)
    if action.action_type == ActionType.GAIN_FOOD:
        # Food only matters as a route to more egg-capable birds.
        return 1.0 + _food_need_score(state, action) * 0.5
    return 0.5


def _engine_builder_bonus(state: GameState, action: LegalAction) -> float:
    """Stack brown powers in one habitat so each activation cascades."""

    player = state.active_player
    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        score = 8.0
        if action.habitat is not None:
            # Deepening an occupied habitat compounds; a full row does not.
            depth = len(player.habitats[action.habitat])
            score += 1.5 * depth if depth < 5 else -4.0
        if card is not None and card.power.color.value == "brown":
            score += 4.0
        return score
    if action.action_type == ActionType.GAIN_FOOD:
        # Food is the main gate on playing the next engine piece.
        return 3.0 + _food_need_score(state, action)
    if action.action_type == ActionType.DRAW_CARDS:
        return 1.0 + _hand_pressure(state)
    return 0.5


def _food_acceleration_bonus(state: GameState, action: LegalAction) -> float:
    """Hoard food, then convert it into whatever is cheapest to play."""

    if action.action_type == ActionType.GAIN_FOOD:
        # Diminishing returns: food hoarded beyond what the hand can spend is
        # dead weight. Without this the archetype loops on gain-food forever.
        stock = float(sum(state.active_player.food_tokens.values()))
        appetite = max(1.0, 8.0 - 0.8 * max(0.0, stock - 4.0))
        return appetite + _food_need_score(state, action)
    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        cheap_bonus = 0.0
        if card is not None:
            cheap_bonus = max(0.0, 4.0 - float(card.food_cost.minimum_total))
        return 2.0 + cheap_bonus
    if action.action_type == ActionType.DRAW_CARDS:
        return 1.0 + _hand_pressure(state)
    return 0.5


def _card_draw_bonus(state: GameState, action: LegalAction) -> float:
    """Draw aggressively and convert the widest hand into played birds."""

    if action.action_type == ActionType.DRAW_CARDS:
        # Diminishing returns: an unplayable hand scores nothing, so drawing
        # must yield to playing once the hand is deep.
        hand_size = float(len(state.active_player.hand))
        return max(1.0, 8.0 - 1.0 * max(0.0, hand_size - 5.0))
    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        # Favour birds whose powers keep cards flowing.
        power_text = (card.power.text or "").lower() if card is not None else ""
        return 2.0 + (3.0 if "card" in power_text else 0.0)
    if action.action_type == ActionType.GAIN_FOOD:
        return 1.0 + _food_need_score(state, action) * 0.5
    return 0.5


def _bonus_name(name: str) -> str:
    """Normalize a bonus-card name or tag for matching."""

    return name.split("[", maxsplit=1)[0].strip()


def _bonus_card_focus_bonus(state: GameState, action: LegalAction) -> float:
    """Play birds that satisfy held bonus cards, and dig for more of them."""

    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        if card is None:
            return 0.0
        # Score against the bonus cards this player actually holds. Counting
        # every tag instead matches all 26 bonus cards in the game, which is a
        # near-constant across the 180-bird deck and discriminates nothing.
        held = {_bonus_name(bonus.name) for bonus in state.active_player.bonus_cards}
        matches = len(held & {_bonus_name(tag) for tag in card.bonus_card_tags})
        # A player holds one bonus card and ~83% of hand cards match nothing, so
        # the match term fires rarely. The play-bird floor must therefore sit
        # clearly above the draw floor, or the agent digs instead of building:
        # at equal floors it drew 63% of its turns and lost 17 points per game.
        return (
            6.0
            + 6.0 * float(matches)
            + (3.0 if card.bonus_card_power else 0.0)
        )
    if action.action_type == ActionType.DRAW_CARDS:
        # Digging for tag-matching birds is the strategy, but a subordinate one.
        return 3.0 + _hand_pressure(state)
    if action.action_type == ActionType.GAIN_FOOD:
        return 2.0 + _food_need_score(state, action) * 0.5
    return 0.5


def _round_goal_chase_bonus(state: GameState, action: LegalAction) -> float:
    """Chase the current round goal, which may be egg-based or bird-based."""

    goal_index = min(state.round_state.round_number - 1, len(state.round_goals) - 1)
    if goal_index < 0:
        return 0.0
    goal_text = state.round_goals[goal_index].name.lower()
    egg_goal = "[egg]" in goal_text

    if action.action_type == ActionType.LAY_EGGS:
        # Previously scored 0, which left every egg-based round goal unchased.
        return (8.0 + float(action.egg_count or 0)) if egg_goal else 1.0
    if action.action_type == ActionType.PLAY_BIRD:
        card = _played_card(state, action)
        if egg_goal:
            # More egg capacity means more room to chase the goal.
            capacity = float(card.egg_limit) if card is not None else 0.0
            nest_match = 0.0
            if card is not None and card.nest_type is not None:
                nest_match = 3.0 if f"[{card.nest_type.value}]" in goal_text else 0.0
            return 2.0 + capacity + nest_match
        if action.habitat is not None and action.habitat.value in goal_text:
            return 8.0
        return 3.0 if "[bird]" in goal_text else 1.0
    if action.action_type == ActionType.GAIN_FOOD:
        return 2.0 + _food_need_score(state, action) * 0.5
    return 1.0


def _food_need_score(state: GameState, action: LegalAction) -> float:
    player = state.active_player
    deficits: Counter = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    selected_foods = action.food_types or ((action.food_type,) if action.food_type else ())
    return float(sum(deficits.get(food_type, 0) for food_type in selected_foods))
