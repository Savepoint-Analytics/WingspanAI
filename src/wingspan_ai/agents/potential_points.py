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
from dataclasses import asdict, dataclass, field
from math import ceil

from wingspan_ai.agents.determinization import determinize_state
from wingspan_ai.agents.feeder_odds import food_power_availability_multiplier
from wingspan_ai.agents.greedy import GreedyBaselineAgent
from wingspan_ai.agents.setup import PotentialPointsSetupPolicy, SetupPolicyMixin
from wingspan_ai.content.birdfeeder import (
    BIRDFEEDER_DICE_COUNT,
    probability_any_available,
)
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, FoodCost, FoodType, Habitat, PowerColor
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import (
    TOTAL_ROUNDS,
    apply_action,
    apply_action_in_place,
    egg_cost_for_slot,
    habitat_action_yield,
    legal_actions_for_current_player,
    ordered_habitats,
    score_player,
)
from wingspan_ai.rules.power_registry import classify_power_handler_key
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
    habitat_yield_potential: float
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
            + self.habitat_yield_potential
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


#: Own-turn branches kept per ply below the root of the endgame search.
DEFAULT_SEARCH_BEAM_WIDTH: int | None = 4
#: Defaults set 2026-09-06 from the determinized search test: depth 3 on every
#: turn (8 cubes) over 4 hidden-information samples scored +10.4 points over
#: the previous default (depth 3, last 5 cubes, true state) with no leak.
#: ``PotentialPointsSearchConfig(search_depth=3, final_search_turns=5,
#: determinization_samples=0)`` reproduces the historic agent.
DEFAULT_SEARCH_DEPTH = 3
DEFAULT_FINAL_SEARCH_TURNS = 8
DEFAULT_DETERMINIZATION_SAMPLES = 4


@dataclass(frozen=True)
class PotentialPointsSearchConfig:
    """Endgame-search settings, threaded through batch flows and manifests."""

    search_depth: int = DEFAULT_SEARCH_DEPTH
    final_search_turns: int = DEFAULT_FINAL_SEARCH_TURNS
    search_beam_width: int | None = DEFAULT_SEARCH_BEAM_WIDTH
    #: Hidden-information samples averaged per decision. ``0`` evaluates the
    #: true state, which lets the search read the deck and opponents' hands.
    determinization_samples: int = DEFAULT_DETERMINIZATION_SAMPLES

    def as_manifest_payload(self) -> dict:
        return asdict(self)


@dataclass
class PotentialPointsAgent(SetupPolicyMixin):
    """Choose actions by estimated final-score potential instead of current points only."""

    setup_policy: PotentialPointsSetupPolicy = field(
        default_factory=PotentialPointsSetupPolicy,
        kw_only=True,
    )
    agent_id: str = "potential_points"
    final_search_turns: int = DEFAULT_FINAL_SEARCH_TURNS
    search_depth: int = DEFAULT_SEARCH_DEPTH
    #: Own-turn branches kept at each ply below the root. The root is never
    #: pruned. ``None`` searches every branch.
    search_beam_width: int | None = DEFAULT_SEARCH_BEAM_WIDTH
    #: Hidden-information samples averaged per decision (see
    #: ``wingspan_ai.agents.determinization``). ``0`` scores the true state.
    determinization_samples: int = DEFAULT_DETERMINIZATION_SAMPLES
    top_alternatives: int = 5

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("PotentialPointsAgent cannot select from an empty action list")

        player_id = state.active_player.player_id
        if self.determinization_samples > 0:
            samples = [
                determinize_state(state, player_id, sample_index)
                for sample_index in range(self.determinization_samples)
            ]
            per_sample = [self._score_actions(sample, legal_actions) for sample in samples]
            scores = [
                (
                    sum(sample_scores[index][0] for sample_scores in per_sample) / len(samples),
                    sum(sample_scores[index][1] for sample_scores in per_sample) / len(samples),
                )
                for index in range(len(legal_actions))
            ]
        else:
            scores = self._score_actions(state, legal_actions)
        return max(
            zip(scores, legal_actions, strict=True),
            key=lambda item: (item[0][0], item[0][1], _action_priority(item[1])),
        )[1]

    def _score_actions(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
    ) -> list[tuple[float, float]]:
        """Score each action as ``(primary, tie_break)`` on one fully specified state.

        Inside the endgame-search window the primary value is the search value
        and the tie-break the immediate score delta; outside it, the potential
        delta and the realized-score delta. The same scores drive both the
        true-state and the determinized paths.
        """

        player_id = state.active_player.player_id
        if _turns_remaining_for_player(state, player_id) <= self.final_search_turns:
            depth = min(self.search_depth, _turns_remaining_for_player(state, player_id))
            return [
                (
                    _search_action_value(
                        state,
                        action,
                        player_id,
                        depth=depth,
                        beam_width=self.search_beam_width,
                    ),
                    _immediate_score_delta(state, action, player_id),
                )
                for action in legal_actions
            ]
        return [
            (evaluation.value_delta, evaluation.realized_delta)
            for evaluation in self.evaluate_actions(state, legal_actions)
        ]

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
            "determinization_samples": self.determinization_samples,
        }


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
            habitat_yield_potential=0,
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
        habitat_yield_potential=_habitat_yield_potential(state, player, turns_remaining)
        * phase_discount,
        bonus_card_potential=_bonus_card_potential(player, turns_remaining) * phase_discount,
        round_goal_potential=_round_goal_potential(state, player, turns_remaining),
        endgame_conversion_potential=_endgame_conversion_potential(player, turns_remaining),
        dead_resource_penalty=_dead_resource_penalty(player, turns_remaining),
    )


#: Opponent turns inside the search are played by the greedy baseline. It is
#: deterministic, needs no RNG stream, and sits mid-roster in strength, so the
#: search sees the tray and feeder contention it exists to plan around. A
#: pass-through opponent would be cheaper but blind to that contention.
_SEARCH_OPPONENT_MODEL = GreedyBaselineAgent(agent_id="search_opponent_model")


def _search_action_value(
    state: GameState,
    action: LegalAction,
    player_id: str,
    depth: int,
    beam_width: int | None = DEFAULT_SEARCH_BEAM_WIDTH,
) -> float:
    """Best planning value reachable from ``action`` within ``depth`` own turns.

    Until 2026-09-04 this returned the leaf value whenever the active player
    changed. ``apply_action`` always advances the turn, so in every multiplayer
    game the recursion stopped after one ply and ``search_depth`` had no effect.
    Opponent turns are now played out with ``_SEARCH_OPPONENT_MODEL`` on the
    owned branch before descending to the next own turn.
    """

    next_state = apply_action(state, action)
    return _search_value_from_branch(next_state, player_id, depth, beam_width)


def _search_value_from_branch(
    branch: GameState,
    player_id: str,
    depth: int,
    beam_width: int | None,
) -> float:
    if depth <= 1 or branch.round_state.game_over:
        return _terminal_planning_value(branch, player_id)
    _play_opponent_turns_in_place(branch, player_id)
    player = _get_player(branch, player_id)
    if (
        branch.round_state.game_over
        or branch.active_player.player_id != player_id
        or player.action_cubes_available <= 0
    ):
        return _terminal_planning_value(branch, player_id)
    legal_actions = legal_actions_for_current_player(branch)
    if not legal_actions:
        return _terminal_planning_value(branch, player_id)

    children = [apply_action(branch, next_action) for next_action in legal_actions]
    leaf_values = [_terminal_planning_value(child, player_id) for child in children]
    if depth - 1 <= 1:
        return max(leaf_values)
    ranked = sorted(zip(leaf_values, children, strict=True), key=lambda item: item[0], reverse=True)
    if beam_width is not None:
        ranked = ranked[:beam_width]
    return max(
        _search_value_from_branch(child, player_id, depth - 1, beam_width)
        for _leaf_value, child in ranked
    )


def _play_opponent_turns_in_place(branch: GameState, player_id: str) -> None:
    """Advance an owned branch through opponent turns until ``player_id`` acts."""

    while not branch.round_state.game_over and branch.active_player.player_id != player_id:
        legal_actions = legal_actions_for_current_player(branch)
        if not legal_actions:
            return
        chosen = _SEARCH_OPPONENT_MODEL.select_action(branch, legal_actions)
        apply_action_in_place(branch, chosen)


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
        candidates.append(
            _projected_bird_value(
                card, player, turns_remaining, state.round_state.round_number, best_action_cost
            )
        )

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


#: Share of an opponent's turns spent on each action family, used to estimate
#: how often a pink (opponent-turn) power will actually trigger. Rough priors
#: from observed agent action mixes; refine from telemetry when available.
_OPPONENT_PLAY_BIRD_SHARE = 0.20
_OPPONENT_LAY_EGGS_SHARE = 0.20
_OPPONENT_GAIN_FOOD_SHARE = 0.35
_DEFAULT_PINK_SHARE = 0.35
#: A predator hunt succeeds when a rodent or fish shows on the birdfeeder dice.
#: Derived from the die model rather than hardcoded: the previous 0.92 was
#: 1 - (3/5)^5, correct only for the uniform five-food die the simulator used to
#: roll. The real die has six faces, so rodent-or-fish is 2/6 per die and the
#: true rate is 1 - (4/6)^5 = 0.868. Predators only hunt when their habitat is
#: activated.
_PREDATOR_SUCCESS_RATE = probability_any_available(
    (FoodType.RODENT, FoodType.FISH), BIRDFEEDER_DICE_COUNT
)


def _pink_trigger_rate(
    state: GameState,
    observer: PlayerState,
    slot: BirdSlot,
    turns_remaining: int,
) -> float:
    """Estimate how many times a pink power will actually fire.

    Pink powers trigger on *opponents'* turns, so their value depends on what
    opponents are positioned to do — not just on how long the game has left.
    Previously every pink power was valued at a flat `turns_remaining * 0.35`,
    so a vulture that pays out only when an opponent's predator succeeds scored
    the same whether opponents held zero predators or five.

    Uses only board state, which is public information.
    """

    opponents = [p for p in state.players if p.player_id != observer.player_id]
    if not opponents or turns_remaining <= 0:
        return 0.0
    opponent_turns = sum(
        min(opponent.action_cubes_available, turns_remaining) for opponent in opponents
    )
    if opponent_turns <= 0:
        return 0.0

    text = (slot.card.power.text or "").lower()

    if "[predator]" in text and "succeed" in text:
        # Pays out only when an opponent's played predator hunts and hits.
        predators = sum(
            1 for opponent in opponents for played in opponent.played_birds if played.card.predator
        )
        if predators == 0:
            return 0.0
        # Each predator fires roughly when its habitat is activated.
        predator_activations = opponent_turns * _OPPONENT_GAIN_FOOD_SHARE * min(predators, 3) / 3
        return predator_activations * _PREDATOR_SUCCESS_RATE

    if "plays a bird" in text:
        habitat = _habitat_from_power_text(text)
        if habitat is None:
            return opponent_turns * _OPPONENT_PLAY_BIRD_SHARE
        # Only opponents with room in that habitat can trigger it.
        with_room = sum(1 for o in opponents if len(o.habitats[habitat]) < 5)
        if with_room == 0:
            return 0.0
        return opponent_turns * _OPPONENT_PLAY_BIRD_SHARE * (with_room / len(opponents))

    if "lay eggs" in text:
        with_capacity = sum(1 for o in opponents if o.available_egg_capacity > 0)
        if with_capacity == 0:
            return 0.0
        return opponent_turns * _OPPONENT_LAY_EGGS_SHARE * (with_capacity / len(opponents))

    if "gain food" in text:
        return opponent_turns * _OPPONENT_GAIN_FOOD_SHARE

    return opponent_turns * _DEFAULT_PINK_SHARE


def _habitat_from_power_text(text: str) -> Habitat | None:
    for habitat in Habitat:
        if f"[{habitat.value}]" in text:
            return habitat
    return None


#: Ablation switch for measuring what mat-yield valuation contributes.
#: Set False to reproduce the pre-2026-09-02 behaviour, where crossing a
#: habitat yield threshold was worth no more than not crossing one.
VALUE_HABITAT_YIELD = True

#: Points-equivalent of one unit produced by a habitat action. Food and cards
#: are inputs that still need converting, so they are worth well under a point.
#:
#: Grassland is deliberately absent: `_egg_conversion_potential` already values
#: egg capacity times the grassland egg rate, so counting it here too double-
#: counts the same points. Including it made the agent pay ~3.7 points to play a
#: 1-point bird purely to unlock egg-laying it was already being credited for.
#: Multiplier on the mat-yield unit values, kept as an explicit ablation knob.
#:
#: Measured 2026-09-03 over 60 seed-matched games per arm. At 1.0 the term
#: changed 0.64% of decisions; at 2.0 it changed 3.37%. Neither moved win rate
#: beyond one game in twenty-four, so the mechanic is modelled because it is
#: real, not because it was shown to pay. Left at 1.0: the doubled weight has
#: no evidence behind it, and the unit values are reasoned from food and cards
#: being inputs rather than points.
HABITAT_YIELD_WEIGHT_SCALE = 1.0

#: A player spreads actions over three habitats, so any one row is used on
#: roughly a third of turns regardless of momentary need.
_NEUTRAL_HABITAT_SHARE = 1.0 / 3.0

_HABITAT_YIELD_UNIT_VALUE: dict[Habitat, float] = {
    Habitat.FOREST: 0.55,
    Habitat.WETLAND: 0.45,
}


def _habitat_yield_potential(
    state: GameState,
    player: PlayerState,
    turns_remaining: int,
) -> float:
    """Value the player-mat yield curve, which is Wingspan's core engine.

    A fuller habitat row makes every future action in it more productive: forest
    gives 1/2/3 food at 0-1, 2-3 and 4-5 birds, grassland 2/3/4 eggs, wetland
    1/2/3 cards. So the 2nd and 4th birds in a row are worth more than the 3rd
    and 5th.

    Nothing valued this before. Adding a powerless bird to the forest moved the
    agent's estimate by a flat +10.70 whether or not it crossed a threshold, so
    agents never preferred the bird that unlocked a bigger row yield.
    """

    if turns_remaining <= 0 or not VALUE_HABITAT_YIELD:
        return 0.0
    # A neutral share per habitat rather than `_expected_habitat_activations`,
    # which scales with *current* food demand. Row yield is a structural
    # property of the board: coupling it to demand meant that gaining the food
    # you needed collapsed the estimate, penalising the agent for satisfying
    # its own requirements.
    expected_uses = turns_remaining * _NEUTRAL_HABITAT_SHARE
    total = 0.0
    for habitat, unit_value in _HABITAT_YIELD_UNIT_VALUE.items():
        yield_per_action = habitat_action_yield(habitat, len(player.habitats[habitat]))
        total += expected_uses * yield_per_action * unit_value
    return total * HABITAT_YIELD_WEIGHT_SCALE


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
            total += _played_power_value(
                slot,
                demand,
                expected_triggers,
                turns_remaining,
                state.round_state.round_number,
                pink_triggers=_pink_trigger_rate(state, player, slot, turns_remaining),
                player=player,
            )
    return total


def _played_power_value(
    slot: BirdSlot,
    demand: Counter[FoodType],
    expected_triggers: float,
    turns_remaining: int,
    round_number: int,
    pink_triggers: float | None = None,
    player=None,
) -> float:
    power = slot.card.power
    if power.color == PowerColor.NONE or (not power.text and not power.handler_key):
        return 0.0
    lowered = power.text.lower() if power.text else ""
    handler_key = _power_handler_key(power.text, power.color, power.handler_key)

    if power.color == PowerColor.BROWN:
        return expected_triggers * _per_trigger_power_value(handler_key, lowered, demand, slot)
    if power.color == PowerColor.PINK:
        # Callers without opponent context fall back to the old flat proxy.
        triggers = pink_triggers if pink_triggers is not None else turns_remaining * 0.35
        return triggers * _per_trigger_power_value(handler_key, lowered, demand, slot, player)
    if power.color == PowerColor.TEAL:
        remaining_triggers = _remaining_teal_triggers(round_number)
        return remaining_triggers * _per_trigger_power_value(handler_key, lowered, demand, slot)
    if power.color == PowerColor.YELLOW:
        return _yellow_end_game_power_value(handler_key, lowered, demand, slot, turns_remaining)
    if power.color == PowerColor.WHITE:
        return 0.0
    return 0.0


def _board_egg_capacity(player, lowered_power_text: str) -> int:
    """Egg capacity available to a power that lays on *other* birds.

    Powers phrased "lay 1 [egg] on a bird with a [bowl] nest" place the egg
    elsewhere on the board, so the power card's own capacity is the wrong test.
    Both brood-parasite cowbirds have `egg_limit` 0 and were therefore valued at
    exactly zero despite being 5 VP and 3 VP cards with a recurring power.
    """

    nest_type = None
    for candidate in ("bowl", "cavity", "ground", "platform"):
        if f"[{candidate}]" in lowered_power_text:
            nest_type = candidate
            break
    total = 0
    for played in getattr(player, "played_birds", []):
        if played.available_egg_capacity <= 0:
            continue
        if nest_type is not None:
            card_nest = played.card.nest_type
            if card_nest is None or card_nest.value not in {nest_type, "wild"}:
                continue
        total += played.available_egg_capacity
    return total


def _per_trigger_power_value(
    handler_key: str | None,
    lowered_power_text: str,
    demand: Counter[FoodType],
    slot: BirdSlot,
    player=None,
) -> float:
    handler_value = _registered_per_trigger_power_value(
        handler_key,
        lowered_power_text,
        demand,
        slot,
    )
    if handler_value is not None:
        return handler_value

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
        targets_other_birds = "another bird" in lowered_power_text or "nest" in lowered_power_text
        if targets_other_birds and player is not None:
            capacity = _board_egg_capacity(player, lowered_power_text)
        else:
            capacity = slot.available_egg_capacity
        value += 0.9 if capacity > 0 else 0.0
    for food_type in BASE_FOOD_TYPES:
        if f"[{_food_power_token(food_type)}]" in lowered_power_text:
            value += 0.85 if demand.get(food_type, 0) > 0 else 0.25
    if "[wild]" in lowered_power_text or "[die]" in lowered_power_text:
        value += 0.85 if sum(demand.values()) > 0 else 0.25
    return value


def _registered_per_trigger_power_value(
    handler_key: str | None,
    lowered_power_text: str,
    demand: Counter[FoodType],
    slot: BirdSlot,
) -> float | None:
    """Value common power-handler registry entries before falling back to text tokens."""

    if handler_key is None:
        return None
    if handler_key == "tuck_card":
        return 1.15 if "draw" in lowered_power_text else 1.0
    if handler_key == "cache_food":
        return 1.0
    if handler_key == "predator_hunt":
        return 0.45
    if handler_key == "draw_card":
        return 0.55
    if handler_key == "lay_egg":
        return 0.9 if slot.available_egg_capacity > 0 else 0.0
    if handler_key in {
        "gain_food_from_birdfeeder",
        "gain_food_from_supply",
        "all_players_gain_food",
        "discard_egg_gain_wild_food",
    }:
        return _registered_food_power_value(lowered_power_text, demand)
    if handler_key == "all_players_lay_eggs":
        return 0.75 if slot.available_egg_capacity > 0 else 0.0
    if handler_key == "discard_to_tuck":
        return 0.8
    if handler_key == "deck_search_tuck_by_wingspan":
        return 0.4
    if handler_key == "pink_reaction":
        return None
    return None


def _registered_food_power_value(
    lowered_power_text: str,
    demand: Counter[FoodType],
) -> float:
    """Value a food-gaining power, weighted by how often its food shows.

    A bird gaining fish and a bird gaining seed scored identically. Seed is
    obtainable on two die faces of six and fish on one, so the fish bird pays out
    roughly half as often. A wild or [die] power takes whatever the feeder offers
    and so needs no weighting.
    """

    if "wild" in lowered_power_text or "[die]" in lowered_power_text:
        return 0.85 if sum(demand.values()) > 0 else 0.25
    for food_type in BASE_FOOD_TYPES:
        token = f"[{_food_power_token(food_type)}]"
        if token in lowered_power_text:
            base = 0.85 if demand.get(food_type, 0) > 0 else 0.25
            return base * food_power_availability_multiplier(food_type)
    return 0.85 if sum(demand.values()) > 0 else 0.25


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
    handler_key: str | None,
    lowered_power_text: str,
    demand: Counter[FoodType],
    slot: BirdSlot,
    turns_remaining: int,
) -> float:
    if turns_remaining <= 0:
        return 0.0
    value = _per_trigger_power_value(handler_key, lowered_power_text, demand, slot)
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
    round_number: int,
    action_cost: int,
) -> float:
    time_weight = max((turns_remaining - action_cost + 1) / max(turns_remaining, 1), 0.0)
    power_value = _unplayed_power_value(card, player, turns_remaining, round_number)
    egg_capacity_value = min(card.egg_limit, max(turns_remaining - action_cost, 0) * 0.5) * 0.35
    return (card.victory_points + power_value + egg_capacity_value) * time_weight


def _unplayed_power_value(
    card: BirdCard,
    player: PlayerState,
    turns_remaining: int,
    round_number: int,
) -> float:
    power = card.power
    if power.color == PowerColor.NONE or (not power.text and not power.handler_key):
        return 0.0
    lowered = power.text.lower() if power.text else ""
    handler_key = _power_handler_key(power.text, power.color, power.handler_key)
    demand = _food_demand(player)
    if power.color == PowerColor.WHITE:
        return _per_trigger_power_value(handler_key, lowered, demand, BirdSlot(card=card))
    if power.color == PowerColor.YELLOW:
        return _yellow_end_game_power_value(
            handler_key,
            lowered,
            demand,
            BirdSlot(card=card),
            turns_remaining,
        )
    if power.color == PowerColor.TEAL:
        return _remaining_teal_triggers(round_number) * _per_trigger_power_value(
            handler_key,
            lowered,
            demand,
            BirdSlot(card=card),
        )
    if power.color == PowerColor.BROWN:
        return (
            min(turns_remaining, 4)
            * 0.35
            * _per_trigger_power_value(
                handler_key,
                lowered,
                demand,
                BirdSlot(card=card),
            )
        )
    if power.color == PowerColor.PINK:
        return (
            turns_remaining
            * 0.15
            * _per_trigger_power_value(
                handler_key,
                lowered,
                demand,
                BirdSlot(card=card),
            )
        )
    return 0.0


def _power_handler_key(
    power_text: str | None,
    power_color: PowerColor,
    explicit_handler_key: str | None,
) -> str | None:
    return explicit_handler_key or classify_power_handler_key(power_text, power_color)


def _estimated_actions_to_play(state: GameState, player: PlayerState, card: BirdCard) -> int:
    food_actions = ceil(_food_deficit(player, card.food_cost) / max(_forest_food_rate(player), 1))
    open_habitats = [
        habitat for habitat in ordered_habitats(card.habitats) if len(player.habitats[habitat]) < 5
    ]
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
    # Reads the rule rather than duplicating the curve, so a rules change
    # cannot silently leave the agent valuing a stale yield table.
    return habitat_action_yield(Habitat.GRASSLAND, len(player.habitats[Habitat.GRASSLAND]))


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


def _remaining_teal_triggers(round_number: int) -> int:
    """Teal powers fire once at the end of each remaining round.

    This previously inferred rounds from turns remaining via `ceil(turns / 6)`,
    but turns per round are 8/7/6/5, not 6. It returned 2 in round 1 where the
    answer is 4, and 2 in round 2 where it is 3 — undervaluing teal powers about
    twofold in rounds 1-3, which is exactly when playing them is most valuable.
    The error shrank as the bird became less worth playing, so it systematically
    discouraged the correct play.
    """

    return max(0, TOTAL_ROUNDS - round_number + 1)


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
