"""YAML-configured policy guardrails for narrowing legal action choices."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from inspect import signature
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field

from wingspan_ai.agents.setup import InitialSelectionContext
from wingspan_ai.content.schemas import BirdCard, FoodType, Habitat
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action
from wingspan_ai.rules.base_game import (
    InitialSelection,
    choose_default_initial_selection,
    legal_actions_for_current_player,
)
from wingspan_ai.state.models import GameState, PlayerState


class SelectActionPolicy(Protocol):
    """Policy interface required for guardrail-constrained action selection."""

    agent_id: str

    def choose_action(self, state: GameState) -> LegalAction:
        """Choose one legal action for the active player."""


class GuardrailEffectType(StrEnum):
    """Effect labels emitted in guardrail telemetry."""

    EXCLUDE = "exclude"
    PENALIZE = "penalize"
    BOOST = "boost"


class GuardrailConditions(BaseModel):
    """State predicates that decide whether a guardrail is active."""

    model_config = ConfigDict(extra="forbid")

    round_gte: int | None = Field(default=None, ge=1)
    round_lte: int | None = Field(default=None, ge=1)
    turn_gte: int | None = Field(default=None, ge=1)
    turn_lte: int | None = Field(default=None, ge=1)
    round_action_gte: int | None = Field(default=None, ge=1)
    round_action_lte: int | None = Field(default=None, ge=1)
    action_cubes_gte: int | None = Field(default=None, ge=0)
    action_cubes_lte: int | None = Field(default=None, ge=0)
    hand_size_gte: int | None = Field(default=None, ge=0)
    hand_size_lte: int | None = Field(default=None, ge=0)
    total_eggs_gte: int | None = Field(default=None, ge=0)
    total_eggs_lte: int | None = Field(default=None, ge=0)
    available_egg_capacity_gte: int | None = Field(default=None, ge=0)
    available_egg_capacity_lte: int | None = Field(default=None, ge=0)
    played_bird_count_gte: int | None = Field(default=None, ge=0)
    played_bird_count_lte: int | None = Field(default=None, ge=0)
    food_token_total_gte: int | None = Field(default=None, ge=0)
    food_token_total_lte: int | None = Field(default=None, ge=0)
    hand_has_playable_bird: bool | None = None
    hand_has_playable_bird_missing_food: bool | None = None
    food_deficit_exists: bool | None = None


class GuardrailActionMatcher(BaseModel):
    """Action predicates that decide whether a guardrail applies to an action."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action_type: ActionType | None = Field(default=None, alias="type")
    habitat: Habitat | None = None
    food_type_in: list[FoodType] = Field(default_factory=list)
    bird_bonus_tag_any: list[str] = Field(default_factory=list)
    bird_victory_points_gte: int | None = Field(default=None, ge=0)
    bird_victory_points_lte: int | None = Field(default=None, ge=0)
    bird_missing_food: bool | None = None
    uses_extra_conversion: bool | None = None
    reroll_birdfeeder: bool | None = None


class GuardrailEffect(BaseModel):
    """Configured action effect for a matched guardrail."""

    model_config = ConfigDict(extra="forbid")

    exclude: bool = False
    penalize: float = Field(default=0.0, ge=0)
    boost: float = Field(default=0.0, ge=0)
    boost_if_food_matches_hand_deficit: float = Field(default=0.0, ge=0)
    penalize_if_food_unneeded: float = Field(default=0.0, ge=0)
    reason: str | None = None


class PolicyGuardrail(BaseModel):
    """One state/action guardrail loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    id: str
    enabled: bool = True
    description: str | None = None
    when: GuardrailConditions = Field(default_factory=GuardrailConditions)
    action: GuardrailActionMatcher = Field(default_factory=GuardrailActionMatcher)
    guardrail: GuardrailEffect


class GuardrailConfig(BaseModel):
    """YAML-loadable collection of policy guardrails."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "wingspan.guardrails.v1"
    name: str = "unnamed_guardrails"
    fail_open_when_all_excluded: bool = True
    use_score_modifiers_for_pruning: bool = True
    rules: list[PolicyGuardrail] = Field(default_factory=list)


@dataclass(frozen=True)
class GuardrailApplication:
    """One guardrail effect applied to one candidate action."""

    rule_id: str
    effect: GuardrailEffectType
    score_delta: float
    reason: str | None


@dataclass(frozen=True)
class GuardrailActionEvaluation:
    """Guardrail result for one legal action."""

    action: LegalAction
    action_label: str
    allowed: bool
    score_modifier: float
    matched_rules: list[GuardrailApplication]


@dataclass(frozen=True)
class GuardrailEvaluation:
    """Guardrail evaluation for one decision point."""

    legal_action_count: int
    action_evaluations: list[GuardrailActionEvaluation]
    fail_open: bool = False

    @property
    def allowed_action_count(self) -> int:
        return len(self.allowed_actions)

    @property
    def excluded_action_count(self) -> int:
        return sum(1 for evaluation in self.action_evaluations if not evaluation.allowed)

    @property
    def allowed_actions(self) -> list[LegalAction]:
        if self.fail_open:
            return [evaluation.action for evaluation in self.action_evaluations]
        return [
            evaluation.action
            for evaluation in self.action_evaluations
            if evaluation.allowed
        ]

    def candidate_actions(self, *, use_score_modifiers: bool = True) -> list[LegalAction]:
        allowed_evaluations = [
            evaluation
            for evaluation in self.action_evaluations
            if self.fail_open or evaluation.allowed
        ]
        if not allowed_evaluations:
            return []
        if not use_score_modifiers:
            return [evaluation.action for evaluation in allowed_evaluations]
        max_modifier = max(evaluation.score_modifier for evaluation in allowed_evaluations)
        if max_modifier == min(evaluation.score_modifier for evaluation in allowed_evaluations):
            return [evaluation.action for evaluation in allowed_evaluations]
        return [
            evaluation.action
            for evaluation in allowed_evaluations
            if evaluation.score_modifier == max_modifier
        ]

    def telemetry_payload(self, selected_action: LegalAction) -> dict[str, Any]:
        selected_evaluation = self.evaluation_for_action(selected_action)
        rule_hit_counts: Counter[str] = Counter()
        for evaluation in self.action_evaluations:
            for application in evaluation.matched_rules:
                rule_hit_counts[application.rule_id] += 1

        return {
            "legal_action_count": self.legal_action_count,
            "guardrail_allowed_action_count": self.allowed_action_count,
            "guardrail_excluded_action_count": self.excluded_action_count,
            "guardrail_fail_open": self.fail_open,
            "guardrail_candidate_action_count": len(self.candidate_actions()),
            "guardrail_rule_hit_counts": dict(sorted(rule_hit_counts.items())),
            "guardrail_selected_score_modifier": (
                selected_evaluation.score_modifier if selected_evaluation else 0.0
            ),
            "guardrail_selected_rules": [
                {
                    "rule_id": application.rule_id,
                    "effect": application.effect.value,
                    "score_delta": application.score_delta,
                    "reason": application.reason,
                }
                for application in (
                    selected_evaluation.matched_rules if selected_evaluation else []
                )
            ],
        }

    def evaluation_for_action(
        self,
        action: LegalAction,
    ) -> GuardrailActionEvaluation | None:
        return next(
            (evaluation for evaluation in self.action_evaluations if evaluation.action == action),
            None,
        )


@dataclass
class ActionGuardrailEvaluator:
    """Evaluate configured guardrails against legal action candidates."""

    config: GuardrailConfig

    def evaluate(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
    ) -> GuardrailEvaluation:
        evaluations = [
            self._evaluate_action(state, action)
            for action in legal_actions
        ]
        allowed_count = sum(1 for evaluation in evaluations if evaluation.allowed)
        fail_open = (
            self.config.fail_open_when_all_excluded
            and bool(evaluations)
            and allowed_count == 0
        )
        return GuardrailEvaluation(
            legal_action_count=len(legal_actions),
            action_evaluations=evaluations,
            fail_open=fail_open,
        )

    def _evaluate_action(
        self,
        state: GameState,
        action: LegalAction,
    ) -> GuardrailActionEvaluation:
        allowed = True
        score_modifier = 0.0
        matched_rules: list[GuardrailApplication] = []

        for rule in self.config.rules:
            if not rule.enabled:
                continue
            if not _conditions_match(rule.when, state):
                continue
            if not _action_matches(rule.action, state, action):
                continue

            reason = rule.guardrail.reason or rule.description
            if rule.guardrail.exclude:
                allowed = False
                matched_rules.append(
                    GuardrailApplication(
                        rule_id=rule.id,
                        effect=GuardrailEffectType.EXCLUDE,
                        score_delta=0.0,
                        reason=reason,
                    )
                )
            if rule.guardrail.penalize:
                delta = -rule.guardrail.penalize
                score_modifier += delta
                matched_rules.append(
                    GuardrailApplication(rule.id, GuardrailEffectType.PENALIZE, delta, reason)
                )
            if rule.guardrail.boost:
                delta = rule.guardrail.boost
                score_modifier += delta
                matched_rules.append(
                    GuardrailApplication(rule.id, GuardrailEffectType.BOOST, delta, reason)
                )

            selected_foods = _selected_foods(action)
            if selected_foods:
                deficit_foods = set(_hand_food_deficits(state.active_player))
                food_matches_deficit = bool(deficit_foods.intersection(selected_foods))
                if rule.guardrail.boost_if_food_matches_hand_deficit and food_matches_deficit:
                    delta = rule.guardrail.boost_if_food_matches_hand_deficit
                    score_modifier += delta
                    matched_rules.append(
                        GuardrailApplication(rule.id, GuardrailEffectType.BOOST, delta, reason)
                    )
                if rule.guardrail.penalize_if_food_unneeded and not food_matches_deficit:
                    delta = -rule.guardrail.penalize_if_food_unneeded
                    score_modifier += delta
                    matched_rules.append(
                        GuardrailApplication(rule.id, GuardrailEffectType.PENALIZE, delta, reason)
                    )

        return GuardrailActionEvaluation(
            action=action,
            action_label=render_action(action),
            allowed=allowed,
            score_modifier=score_modifier,
            matched_rules=matched_rules,
        )


@dataclass
class GuardrailedAgent:
    """Agent wrapper that applies YAML guardrails before delegating selection."""

    base_agent: SelectActionPolicy
    guardrails: ActionGuardrailEvaluator | GuardrailConfig
    agent_id: str | None = None
    _last_evaluation: GuardrailEvaluation | None = field(default=None, init=False, repr=False)
    _last_candidate_actions: list[LegalAction] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.guardrails, GuardrailConfig):
            self.guardrails = ActionGuardrailEvaluator(self.guardrails)
        if self.agent_id is None:
            self.agent_id = f"guardrailed_{self.base_agent.agent_id}"

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        chooser = getattr(self.base_agent, "choose_initial_selection", None)
        if callable(chooser):
            parameters = signature(chooser).parameters
            if len(parameters) == 1:
                return chooser(player)
            return chooser(player, context)
        return choose_default_initial_selection(player)

    def choose_action(self, state: GameState) -> LegalAction:
        legal_actions = legal_actions_for_current_player(state)
        if not legal_actions:
            raise ValueError("GuardrailedAgent cannot select from an empty action list")

        evaluation = self.guardrails.evaluate(state, legal_actions)
        candidate_actions = evaluation.candidate_actions(
            use_score_modifiers=self.guardrails.config.use_score_modifiers_for_pruning
        )
        if not candidate_actions:
            raise ValueError("Guardrails removed every action and fail-open is disabled")

        self._last_evaluation = evaluation
        self._last_candidate_actions = candidate_actions
        return _select_with_base_agent(self.base_agent, state, candidate_actions)

    def summarize_decision(
        self,
        state: GameState,
        legal_actions: list[LegalAction],
        selected_action: LegalAction,
    ) -> dict[str, Any]:
        evaluation = self._last_evaluation or self.guardrails.evaluate(state, legal_actions)
        candidate_actions = self._last_candidate_actions or evaluation.candidate_actions(
            use_score_modifiers=self.guardrails.config.use_score_modifiers_for_pruning
        )
        base_summary = _summarize_base_agent(
            self.base_agent,
            state,
            candidate_actions or legal_actions,
            selected_action,
        )
        payload = {
            "policy": "guardrailed_policy",
            "base_agent_id": self.base_agent.agent_id,
            "selected_action_type": selected_action.action_type.value,
            "guardrail_config_name": self.guardrails.config.name,
            "base_decision_summary": base_summary,
        }
        payload.update(evaluation.telemetry_payload(selected_action))
        return payload


def load_guardrail_config(path: str | Path) -> GuardrailConfig:
    """Load and validate a policy guardrail YAML file."""

    resolved_path = Path(path)
    with resolved_path.open(encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}
    return GuardrailConfig.model_validate(raw_config)


def _select_with_base_agent(
    base_agent: SelectActionPolicy,
    state: GameState,
    legal_actions: list[LegalAction],
) -> LegalAction:
    selector = getattr(base_agent, "select_action", None)
    if callable(selector):
        parameters = signature(selector).parameters
        if len(parameters) == 1:
            return selector(legal_actions)
        return selector(state, legal_actions)
    if len(legal_actions) == 1:
        return legal_actions[0]
    raise TypeError(
        f"{base_agent.agent_id} must expose select_action(...) to be guardrail-constrained"
    )


def _summarize_base_agent(
    base_agent: SelectActionPolicy,
    state: GameState,
    legal_actions: list[LegalAction],
    selected_action: LegalAction,
) -> dict[str, Any]:
    summarizer = getattr(base_agent, "summarize_decision", None)
    if callable(summarizer):
        return summarizer(state, legal_actions, selected_action)
    return {
        "policy": "unknown",
        "legal_action_count": len(legal_actions),
        "selected_action_type": selected_action.action_type.value,
    }


def _conditions_match(conditions: GuardrailConditions, state: GameState) -> bool:
    player = state.active_player
    round_state = state.round_state
    food_total = sum(player.food_tokens.values())
    playable_birds = _hand_birds_with_open_habitat(player)
    food_deficits = _hand_food_deficits(player)

    comparisons = (
        (conditions.round_gte, round_state.round_number, ">="),
        (conditions.round_lte, round_state.round_number, "<="),
        (conditions.turn_gte, round_state.turn_number, ">="),
        (conditions.turn_lte, round_state.turn_number, "<="),
        (conditions.round_action_gte, round_state.round_action_number, ">="),
        (conditions.round_action_lte, round_state.round_action_number, "<="),
        (conditions.action_cubes_gte, player.action_cubes_available, ">="),
        (conditions.action_cubes_lte, player.action_cubes_available, "<="),
        (conditions.hand_size_gte, len(player.hand), ">="),
        (conditions.hand_size_lte, len(player.hand), "<="),
        (conditions.total_eggs_gte, player.total_eggs, ">="),
        (conditions.total_eggs_lte, player.total_eggs, "<="),
        (conditions.available_egg_capacity_gte, player.available_egg_capacity, ">="),
        (conditions.available_egg_capacity_lte, player.available_egg_capacity, "<="),
        (conditions.played_bird_count_gte, len(player.played_birds), ">="),
        (conditions.played_bird_count_lte, len(player.played_birds), "<="),
        (conditions.food_token_total_gte, food_total, ">="),
        (conditions.food_token_total_lte, food_total, "<="),
    )
    if any(
        not _compare_optional(threshold, actual, operator)
        for threshold, actual, operator in comparisons
    ):
        return False

    booleans = (
        (conditions.hand_has_playable_bird, bool(playable_birds)),
        (
            conditions.hand_has_playable_bird_missing_food,
            any(_bird_missing_food(player, bird) for bird in playable_birds),
        ),
        (conditions.food_deficit_exists, bool(food_deficits)),
    )
    return all(expected is None or expected == actual for expected, actual in booleans)


def _action_matches(
    matcher: GuardrailActionMatcher,
    state: GameState,
    action: LegalAction,
) -> bool:
    player = state.active_player
    if matcher.action_type is not None and action.action_type != matcher.action_type:
        return False
    if matcher.habitat is not None and action.habitat != matcher.habitat:
        return False
    if (
        matcher.reroll_birdfeeder is not None
        and action.reroll_birdfeeder != matcher.reroll_birdfeeder
    ):
        return False
    if matcher.uses_extra_conversion is not None:
        uses_conversion = bool(
            action.spend_card_for_extra_food
            or action.spend_food_for_extra_egg
            or action.spend_egg_for_extra_card
        )
        if matcher.uses_extra_conversion != uses_conversion:
            return False
    if matcher.food_type_in:
        if not set(matcher.food_type_in).intersection(_selected_foods(action)):
            return False

    bird = _bird_for_action(player, action)
    if matcher.bird_bonus_tag_any:
        if bird is None or not set(matcher.bird_bonus_tag_any).intersection(bird.bonus_card_tags):
            return False
    if matcher.bird_victory_points_gte is not None:
        if bird is None or bird.victory_points < matcher.bird_victory_points_gte:
            return False
    if matcher.bird_victory_points_lte is not None:
        if bird is None or bird.victory_points > matcher.bird_victory_points_lte:
            return False
    if matcher.bird_missing_food is not None:
        if bird is None or matcher.bird_missing_food != _bird_missing_food(player, bird):
            return False
    return True


def _compare_optional(threshold: int | None, actual: int, operator: str) -> bool:
    if threshold is None:
        return True
    if operator == ">=":
        return actual >= threshold
    return actual <= threshold


def _hand_food_deficits(player: PlayerState) -> Counter[FoodType]:
    deficits: Counter[FoodType] = Counter()
    for card in player.hand:
        for food_type, count in card.food_cost.fixed.items():
            deficits[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
    return +deficits


def _selected_foods(action: LegalAction) -> tuple[FoodType, ...]:
    return action.food_types or ((action.food_type,) if action.food_type else ())


def _bird_for_action(player: PlayerState, action: LegalAction) -> BirdCard | None:
    if action.bird_common_name is None:
        return None
    return next(
        (bird for bird in player.hand if bird.common_name == action.bird_common_name),
        None,
    )


def _bird_missing_food(player: PlayerState, bird: BirdCard) -> bool:
    return any(
        player.food_tokens.get(food_type, 0) < count
        for food_type, count in bird.food_cost.fixed.items()
    )


def _hand_birds_with_open_habitat(player: PlayerState) -> list[BirdCard]:
    return [
        bird
        for bird in player.hand
        if any(len(player.habitats[habitat]) < 5 for habitat in bird.habitats)
    ]
