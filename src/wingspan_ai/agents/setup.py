"""Opening hand, bonus-card, and food setup policies."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import combinations, combinations_with_replacement
from typing import Protocol

from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, BonusCard, FoodType, Habitat, PowerColor
from wingspan_ai.rules.base_game import (
    BIRD_FOOD_SELECTION_TOTAL,
    InitialSelection,
    choose_default_initial_selection,
    ordered_habitats,
)
from wingspan_ai.rules.bonus_scoring import normalize_bonus_name, parse_bonus_card_scoring
from wingspan_ai.state.models import PlayerState, RoundState


@dataclass(frozen=True)
class InitialSelectionContext:
    """Public setup information available before opening cards are kept."""

    bird_tray: tuple[BirdCard, ...] = ()
    round_goal_names: tuple[str, ...] = ()
    round_state: RoundState | None = None
    player_count: int = 1


class InitialSetupPolicy(Protocol):
    """Policy interface for choosing opening birds, bonus card, and food."""

    policy_id: str

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        """Choose the opening setup selection for one player."""


@dataclass(frozen=True)
class DefaultSetupPolicy:
    """Existing deterministic v1 setup chooser."""

    policy_id: str = "default_setup_v1"

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        del context
        return choose_default_initial_selection(player)


@dataclass(kw_only=True)
class SetupPolicyMixin:
    """Agent mixin that delegates opening setup to a setup policy."""

    setup_policy: InitialSetupPolicy = field(default_factory=DefaultSetupPolicy)

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        return self.setup_policy.choose_initial_selection(player, context)


#: How the potential-points opener ranks the two dealt bonus cards.
#: ``"tag_overlap"`` is the historic scorer (hand keyword matches plus the
#: card's prevalence). ``"expected_points"`` estimates the points the card
#: will actually score from its printed formula, its printed prevalence and
#: the qualifiers in hand; see ``expected_bonus_points``.
BONUS_SCORING_KINDS = ("tag_overlap", "expected_points")
DEFAULT_BONUS_SCORING = "tag_overlap"


@dataclass(frozen=True)
class PotentialPointsSetupPolicy:
    """Opening setup heuristic for final-score potential and early tempo."""

    policy_id: str = "potential_points_setup_v1"
    target_keep_count: int | None = None
    bonus_scoring: str = DEFAULT_BONUS_SCORING

    def __post_init__(self) -> None:
        if self.bonus_scoring not in BONUS_SCORING_KINDS:
            raise ValueError(
                f"unknown bonus_scoring: {self.bonus_scoring!r}; expected one of "
                f"{BONUS_SCORING_KINDS}"
            )
        if self.bonus_scoring != DEFAULT_BONUS_SCORING and self.policy_id.endswith("_v1"):
            object.__setattr__(self, "policy_id", f"{self.policy_id}:{self.bonus_scoring}")

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        return _best_selection(
            player,
            context,
            card_scorer=_potential_card_score,
            bonus_scorer=(
                expected_bonus_points
                if self.bonus_scoring == "expected_points"
                else _potential_bonus_score
            ),
            target_keep_count=self.target_keep_count,
        )


@dataclass(frozen=True)
class ArchetypeSetupPolicy:
    """Opening setup heuristic aligned to an interpretable strategy archetype."""

    archetype: str
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", f"archetype_{self.archetype}_setup_v1")

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        return _best_selection(
            player,
            context,
            card_scorer=lambda card, selected, bonus, setup_context: _archetype_card_score(
                card,
                selected,
                bonus,
                setup_context,
                archetype=self.archetype,
            ),
            bonus_scorer=_potential_bonus_score,
        )


@dataclass(frozen=True)
class ForcedBonusCardSetupPolicy:
    """Keep the dealt bonus card at ``dealt_index``; let ``base_policy`` do the rest.

    The instrument for the forced-keep bonus-card study
    (``docs/experiments/bonus_card_selection_study_plan.md``): the same seed
    is run once per dealt card, and the paired score difference is the value
    of the keep. Birds and food are still chosen by ``base_policy``, but
    conditional on the forced card, so the arm measures "keep this card and
    play around it" rather than "keep this card and ignore it".
    """

    base_policy: InitialSetupPolicy
    dealt_index: int
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.dealt_index < 0:
            raise ValueError("dealt_index must be non-negative")
        object.__setattr__(
            self, "policy_id", f"forced_bonus_{self.dealt_index}:{self.base_policy.policy_id}"
        )

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        if self.dealt_index >= len(player.bonus_cards):
            raise ValueError(
                f"player {player.player_id} was dealt {len(player.bonus_cards)} bonus cards; "
                f"cannot force index {self.dealt_index}"
            )
        forced = player.bonus_cards[self.dealt_index]
        # The base policy chooses its bonus card first and birds conditional on
        # it, so restricting what it can see to the forced card is exactly
        # "choose the best opening given this card".
        restricted = player.model_copy(update={"bonus_cards": [forced]})
        selection = self.base_policy.choose_initial_selection(restricted, context)
        return InitialSelection(
            player_id=player.player_id,
            kept_bird_names=list(selection.kept_bird_names),
            kept_bonus_card_names=[forced.name],
            starting_food=list(selection.starting_food),
        )


@dataclass(frozen=True)
class NetValueSetupPolicy:
    """Opening setup heuristic with public tray and round-goal denial priors."""

    policy_id: str = "net_value_setup_v1"
    denial_weight: float = 0.45

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        return _best_selection(
            player,
            context,
            card_scorer=lambda card, selected, bonus, setup_context: (
                _potential_card_score(card, selected, bonus, setup_context)
                + self.denial_weight * _setup_public_denial_prior(card, setup_context)
            ),
            bonus_scorer=_potential_bonus_score,
        )


def _best_selection(
    player: PlayerState,
    context: InitialSelectionContext | None,
    *,
    card_scorer,
    bonus_scorer,
    target_keep_count: int | None = None,
) -> InitialSelection:
    setup_context = context or InitialSelectionContext()
    bonus_card = max(
        player.bonus_cards,
        key=lambda bonus: (bonus_scorer(bonus, player.hand), bonus.name),
    )
    best_score: float | None = None
    best_cards: tuple[BirdCard, ...] = ()
    best_food: tuple[FoodType, ...] = ()

    for cards in _opening_card_subsets(player.hand, target_keep_count=target_keep_count):
        food_count = BIRD_FOOD_SELECTION_TOTAL - len(cards)
        food = _best_starting_food(cards, food_count)
        score = _selection_score(
            cards,
            food,
            bonus_card,
            setup_context,
            card_scorer=card_scorer,
        )
        if best_score is None or score > best_score:
            best_score = score
            best_cards = cards
            best_food = food

    return InitialSelection(
        player_id=player.player_id,
        kept_bird_names=[card.common_name for card in best_cards],
        kept_bonus_card_names=[bonus_card.name],
        starting_food=list(best_food),
    )


def _opening_card_subsets(
    cards: list[BirdCard],
    *,
    target_keep_count: int | None,
) -> Iterable[tuple[BirdCard, ...]]:
    if target_keep_count is not None:
        keep_counts = [min(max(target_keep_count, 0), len(cards))]
    else:
        keep_counts = range(1, min(len(cards), BIRD_FOOD_SELECTION_TOTAL) + 1)
    for keep_count in keep_counts:
        yield from combinations(cards, keep_count)


def _selection_score(
    cards: tuple[BirdCard, ...],
    food: tuple[FoodType, ...],
    bonus_card: BonusCard,
    context: InitialSelectionContext,
    *,
    card_scorer,
) -> float:
    selected = tuple(cards)
    score = sum(card_scorer(card, selected, bonus_card, context) for card in cards)
    score += _food_alignment_score(cards, food) * 1.7
    score += _habitat_balance_score(cards)
    score += _opening_playability_score(cards, food) * 2.5
    score += _bonus_alignment_score(bonus_card, cards) * 1.8
    score += _round_goal_setup_score(cards, context)
    score -= max(len(cards) - 3, 0) * 0.45
    score -= max(2 - len(cards), 0) * 0.35
    return score


def _best_starting_food(
    cards: tuple[BirdCard, ...],
    food_count: int,
) -> tuple[FoodType, ...]:
    if food_count <= 0:
        return ()
    food_options = combinations_with_replacement(BASE_FOOD_TYPES, food_count)
    return max(
        food_options,
        key=lambda food: (
            _food_alignment_score(cards, food),
            _opening_playability_score(cards, food),
            tuple(food_type.value for food_type in food),
        ),
    )


def _potential_card_score(
    card: BirdCard,
    selected_cards: tuple[BirdCard, ...],
    bonus_card: BonusCard,
    context: InitialSelectionContext,
) -> float:
    score = card.victory_points * 0.8
    score += max(4 - card.food_cost.minimum_total, 0) * 1.4
    score += min(card.egg_limit, 5) * 0.25
    score += len(card.habitats) * 0.3
    score += _opening_power_score(card)
    score += _bonus_alignment_score(bonus_card, (card,)) * 1.2
    score += _round_goal_setup_score((card,), context) * 0.8
    if any(card is not other and card.habitats & other.habitats for other in selected_cards):
        score += 0.25
    return score


def _potential_bonus_score(bonus_card: BonusCard, hand: list[BirdCard]) -> float:
    aligned_cards = sum(_bonus_alignment_score(bonus_card, (card,)) for card in hand)
    implemented_bonus = 0.5 if bonus_card.handler_key else 0.0
    prevalence = (bonus_card.prevalence_percent or 0.0) / 100
    return aligned_cards + implemented_bonus + prevalence


#: Share of a dealt qualifying bird that ends up played. Opening hands keep
#: three to five cards and the searching agent plays most of what it keeps.
HAND_QUALIFIER_PLAY_RATE = 0.6
#: Birds a two-player game adds from draws after the opening hand: about
#: eleven birds reach the board, three or so of them from the opening hand.
FUTURE_BIRDS_PLAYED = 8.0
#: Cards scored from board state print no prevalence and have no qualifying
#: birds, so they get one neutral prior rather than a formula: the median of
#: the tagged cards' empty-hand expectations, so they are neither preferred
#: nor avoided by construction.
BOARD_STATE_BONUS_PRIOR = 1.5


def expected_bonus_points(bonus_card: BonusCard, hand: list[BirdCard]) -> float:
    """Points this card is expected to score over the game, from its formula.

    Expected qualifiers reaching the board are the qualifying birds in hand at
    ``HAND_QUALIFIER_PLAY_RATE`` plus ``FUTURE_BIRDS_PLAYED`` draws at the
    card's printed prevalence. Per-bird cards pay linearly in that count;
    tiered cards pay the formula's expectation under a Poisson count, which is
    what makes a 5-to-8-bird threshold worth little on an 11-bird board. The
    2026-09-16 forced-keep study found per-bird cards worth +3.25 points over
    their partners and breadth of supply worth nothing, which is exactly what
    this expectation says and the historic tag-overlap scorer did not.
    """

    rule = parse_bonus_card_scoring(bonus_card.victory_point_text)
    if rule is None:
        return 0.0
    name = normalize_bonus_name(bonus_card.name)
    if bonus_card.prevalence_percent is None:
        return BOARD_STATE_BONUS_PRIOR
    in_hand = sum(
        1
        for card in hand
        if any(normalize_bonus_name(tag) == name for tag in card.bonus_card_tags)
    )
    expected_count = (
        HAND_QUALIFIER_PLAY_RATE * in_hand
        + FUTURE_BIRDS_PLAYED * bonus_card.prevalence_percent / 100.0
    )
    if rule.per_bird_points is not None:
        return rule.per_bird_points * expected_count
    # Tiered: E[points_for(K)] for K ~ Poisson(expected_count).
    expected = 0.0
    probability = math.exp(-expected_count)
    for count in range(0, 16):
        if count > 0:
            probability *= expected_count / count
        expected += probability * rule.points_for(count)
    return expected


def _archetype_card_score(
    card: BirdCard,
    selected_cards: tuple[BirdCard, ...],
    bonus_card: BonusCard,
    context: InitialSelectionContext,
    *,
    archetype: str,
) -> float:
    score = _potential_card_score(card, selected_cards, bonus_card, context)
    power_text = card.power.text.lower() if card.power.text else ""
    if archetype == "egg_focus":
        score += (2.0 if Habitat.GRASSLAND in card.habitats else 0.0) + min(card.egg_limit, 5) * 0.5
    elif archetype == "engine_builder":
        score += _opening_power_score(card) + len(card.habitats) * 0.8
    elif archetype == "food_acceleration":
        score += 2.0 if Habitat.FOREST in card.habitats else 0.0
        if "gain" in power_text and _mentions_food(power_text):
            score += 2.0
    elif archetype == "card_draw":
        score += 2.0 if Habitat.WETLAND in card.habitats else 0.0
        if "draw" in power_text and "[card]" in power_text:
            score += 2.0
    elif archetype == "bonus_card_focus":
        score += _bonus_alignment_score(bonus_card, (card,)) * 2.5
        score += 1.5 if card.bonus_card_power or card.bonus_card_tags else 0.0
    elif archetype == "round_goal_chase":
        score += _round_goal_setup_score((card,), context) * 2.5
    return score


def _setup_public_denial_prior(
    card: BirdCard,
    context: InitialSelectionContext,
) -> float:
    value = 0.0
    for tray_card in context.bird_tray:
        if tray_card.habitats & card.habitats:
            value += 0.15
        if tray_card.food_cost.fixed.keys() & card.food_cost.fixed.keys():
            value += 0.2
        if _is_engine_card(tray_card) and _is_engine_card(card):
            value += 0.3
    return value


def _food_alignment_score(
    cards: tuple[BirdCard, ...],
    food: tuple[FoodType, ...],
) -> float:
    available = Counter(food)
    score = 0.0
    for card in cards:
        matched = 0
        for food_type, count in card.food_cost.fixed.items():
            matched += min(available.get(food_type, 0), count)
        score += matched / max(card.food_cost.minimum_total, 1)
    return score


def _opening_playability_score(
    cards: tuple[BirdCard, ...],
    food: tuple[FoodType, ...],
) -> float:
    available = Counter(food)
    score = 0.0
    for card in cards:
        if _can_pay_fixed_food(available, card):
            score += 1.0 + card.victory_points * 0.08 + _opening_power_score(card) * 0.2
    return score


def _can_pay_fixed_food(available: Counter[FoodType], card: BirdCard) -> bool:
    fixed_cost = card.food_cost.fixed
    if not fixed_cost and card.food_cost.minimum_total == 0:
        return True
    return all(available.get(food_type, 0) >= count for food_type, count in fixed_cost.items())


def _habitat_balance_score(cards: tuple[BirdCard, ...]) -> float:
    habitats = Counter(habitat for card in cards for habitat in card.habitats)
    return sum(0.35 for habitat in Habitat if habitats[habitat] > 0)


def _round_goal_setup_score(
    cards: tuple[BirdCard, ...],
    context: InitialSelectionContext,
) -> float:
    if not context.round_goal_names:
        return 0.0
    first_goal = context.round_goal_names[0].lower()
    score = 0.0
    for card in cards:
        if "[bird]" in first_goal:
            for habitat in ordered_habitats(card.habitats):
                if habitat.value in first_goal:
                    score += 1.2
            if all(habitat.value not in first_goal for habitat in card.habitats):
                score += 0.25
        if card.nest_type and card.nest_type.value in first_goal:
            score += 0.8
        if "[egg]" in first_goal:
            score += min(card.egg_limit, 4) * 0.15
    return score


def _bonus_alignment_score(bonus_card: BonusCard, cards: tuple[BirdCard, ...]) -> float:
    bonus_name = bonus_card.name.split("[", maxsplit=1)[0].strip().lower()
    score = 0.0
    for card in cards:
        if "bird feeder" in bonus_name and FoodType.SEED in card.food_cost.fixed:
            score += 1.0
        if "backyard birder" in bonus_name and card.victory_points < 4:
            score += 1.0
        if "falconer" in bonus_name and card.predator:
            score += 1.0
        if "bird counter" in bonus_name and card.flocking:
            score += 1.0
        if "rodentologist" in bonus_name and FoodType.RODENT in card.food_cost.fixed:
            score += 1.0
        if "fishery manager" in bonus_name and FoodType.FISH in card.food_cost.fixed:
            score += 1.0
        if "viticulturalist" in bonus_name and FoodType.FRUIT in card.food_cost.fixed:
            score += 1.0
        if card.bonus_card_tags:
            score += 0.4 * len(card.bonus_card_tags)
    return score


def _opening_power_score(card: BirdCard) -> float:
    if card.power.color == PowerColor.NONE or not card.power.text:
        return 0.0
    power_text = card.power.text.lower()
    score = 0.0
    if card.power.color == PowerColor.BROWN:
        score += 1.0
    if card.power.color == PowerColor.PINK:
        score += 0.7
    if card.power.color == PowerColor.WHITE:
        score += 0.35
    if "tuck" in power_text:
        score += 1.0
    if "cache" in power_text:
        score += 0.8
    if "draw" in power_text and "[card]" in power_text:
        score += 0.9
    if "lay" in power_text and "[egg]" in power_text:
        score += 0.9
    if "gain" in power_text and _mentions_food(power_text):
        score += 0.9
    return score


def _is_engine_card(card: BirdCard) -> bool:
    return _opening_power_score(card) >= 1.5


def _mentions_food(power_text: str) -> bool:
    return (
        any(f"[{food.value}]" in power_text for food in BASE_FOOD_TYPES)
        or "[wild]" in power_text
    )
