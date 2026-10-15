"""Opening hand, bonus-card, and food setup policies."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import combinations, combinations_with_replacement
from typing import Protocol

from wingspan_ai.agents import profiling
from wingspan_ai.agents.bird_values import BirdPlayValues, load_bird_play_values
from wingspan_ai.content.loader import BASE_FOOD_TYPES
from wingspan_ai.content.schemas import BirdCard, BonusCard, FoodType, Habitat, PowerColor
from wingspan_ai.rules.base_game import (
    BIRD_FOOD_SELECTION_TOTAL,
    ROUND_GOAL_GREEN_SCORES,
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
    #: Birdfeeder faces as rolled at setup (``BirdfeederFace`` values).
    birdfeeder_faces: tuple[str, ...] = ()
    #: Agent id per seat, in seat order, so a seat can see who it is playing.
    seat_agent_ids: tuple[str, ...] = ()


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
#: card's prevalence; policy id ``potential_points_setup_v1``).
#: ``"expected_points"`` estimates the points the card will actually score
#: from its printed formula, its printed prevalence and the qualifiers in
#: hand (``potential_points_setup_v2``); see ``expected_bonus_points``. The
#: default moved to ``"expected_points"`` on 2026-09-16 (Alex's call) after
#: it scored +0.85 (p=0.011) and 61% vs 52% over 322 measured deals; see
#: ``docs/experiments/bonus_card_selection_study_plan.md``.
#: ``"joint"`` is ``"expected_points"`` plus two fixes found 2026-10-06 while
#: checking whether the agent can coordinate its setup the way a human can.
#: Measured over 240 openings, the old opener's sequencing cost nothing (joint
#: enumeration was never strictly better, 0/240) and reading all four goals
#: moved one hand in 240. The real defect was which scorer saw which cards:
#: ``expected_bonus_points`` -- which prices every card from its parsed rule
#: and printed prevalence -- chose the bonus against the **dealt five**,
#: including birds about to be discarded, while the joint tradeoff inside the
#: keep loop was priced by ``_bonus_alignment_score``, a hand-written if-chain
#: covering about a dozen named cards and returning 0 for the rest. So the
#: good scorer saw the wrong card set and the crude one made the decision,
#: which is why the two bonus cards tied at the optimum in 37% of hands.
#: ``"joint"`` enumerates (bonus x keep set) together and prices the bonus
#: inside the loop with ``expected_bonus_points`` against the **kept** cards.
BONUS_SCORING_KINDS = ("tag_overlap", "expected_points", "joint")
#: Adopted 2026-10-06 **on mechanism, not on a significance test**, which the
#: standing registration rule allows when no affordable sample can resolve the
#: band. The old default pointed ``expected_bonus_points`` -- the scorer that
#: prices every card from its parsed rule and prevalence -- at the *dealt five*
#: including birds about to be discarded, while the joint tradeoff inside the
#: keep loop was priced by ``_bonus_alignment_score``, an if-chain covering a
#: dozen named cards and returning 0 for the rest. The good scorer saw the
#: wrong card set and the crude one made the decision, which is why both bonus
#: cards tied at the optimum in 37% of 240 openings.
#:
#: ``"joint"`` enumerates (bonus x keep set) together and prices the bonus
#: inside the loop with ``expected_bonus_points``, dropping the crude alignment
#: term so it is not counted twice at two different qualities.
#:
#: **Measured, the kept-set half of that is nearly inert**, and the first
#: version of this comment overstated it: the opener keeps all five birds in
#: 570 of 600 openings, so the kept set *is* the dealt hand, and subset pricing
#: changes the figure in 0.3% of openings. What actually drives the 9.6% of
#: hands whose opening changes is the in-loop pricing -- 36 of 41 bonus-card
#: changes happen at keep==5. The bonus is now chosen by the whole opening
#: score *including* its expected points, rather than by its expected points
#: alone followed by a crude alignment tie-break.
#:
#: That the opener keeps five birds and no starting food in 95% of hands is a
#: separate and probably larger problem; forcing three was measured at -1.9.
#: See ``docs/experiments/joint_opener.md``.
DEFAULT_BONUS_SCORING = "joint"

#: How the potential-points opener values the dealt birds.
#: ``"heuristic"`` is the hand-written ``_potential_card_score`` plus the
#: alignment, playability and habitat terms in ``_selection_score``. Its keep
#: count floats and it keeps five birds and no food in 119 of 120 deals; it
#: lost −3.0 (p=0.022) to the plain opener on 2026-09-16 with the same bonus
#: choice that is worth +0.85 on its own.
#: ``"measured"`` scores a keep set in final-score points: each kept bird's
#: measured round-1 play value (``agents/bird_values.py``, K=4 counterfactual
#: attribution), discounted when the starting food cannot pay for it, plus a
#: price per starting food token when the keep count floats. The registered
#: 2026-09-17 arm (``potential_points_setup_v3_keep3``) holds the plain
#: opener's structure — three birds, two food — and changes only *which*
#: birds and food, so the arm reads the bird values alone. The default stays
#: ``"heuristic"`` until it is read.
BIRD_SCORING_KINDS = ("heuristic", "measured")
DEFAULT_BIRD_SCORING = "heuristic"
#: Points one starting food token is worth to the measured opener when the
#: keep count floats. A gain-food action yields one to two tokens and the
#: search values an early action at roughly five points; 2.5 is the midpoint
#: and a registered parameter, not a measurement. Unused at a fixed count.
DEFAULT_OPENING_FOOD_VALUE = 2.5
#: Share of a bird's play value the measured opener credits when the starting
#: food cannot pay its cost (it must first be earned with an action).
DEFAULT_UNAFFORDABLE_DISCOUNT = 0.5
#: How many of the four end-of-round goals the opener scores kept birds
#: against. All four are public from setup, but only round 1's was ever
#: read. ``"all"`` weights round ``r`` by ``GOAL_HORIZON_DISCOUNT ** (r - 1)``:
#: a later goal is worth more when scored (4/1 → 7/4/3) but is further away
#: and more likely to be reached by other means. Registered 2026-09-22 as a
#: null (±1), on the opener precedent: three previous opener variants all
#: landed within 2 points.
SETUP_GOAL_HORIZONS = ("first", "all")
DEFAULT_SETUP_GOAL_HORIZON = "first"
#: Per-round discount for the later goals, and the round's own placement
#: scale relative to round 1's (5/4, 6/4, 7/4) — the product is the weight.
GOAL_HORIZON_DISCOUNT = 0.55
#: How heavily the ``"joint"`` opener weights a bonus card's expected points
#: against the rest of the keep score. 1.0 means "one expected bonus point is
#: worth one point of opening score", which is the honest default: both sides
#: are already denominated in final-score points. A registered parameter, not
#: a measurement.
JOINT_BONUS_WEIGHT = 1.0

_SETUP_POLICY_IDS = {
    ("tag_overlap", "heuristic"): "potential_points_setup_v1",
    ("expected_points", "heuristic"): "potential_points_setup_v2",
    ("expected_points", "measured"): "potential_points_setup_v3",
    ("tag_overlap", "measured"): "potential_points_setup_v3_tag",
    ("joint", "heuristic"): "potential_points_setup_v4",
    ("joint", "measured"): "potential_points_setup_v4_measured",
}
#: Appended to the policy id when the opener reads all four goals, so a
#: manifest and a holdout can name the variant.
_ALL_GOALS_SUFFIX = "_allgoals"
_KEEP_SUFFIX = re.compile(r"^(?P<base>.+?)_keep(?P<count>\d+)$")


def potential_points_setup_policy(policy_id: str) -> PotentialPointsSetupPolicy:
    """Build the potential-points opener variant a policy id names.

    ``potential_points_setup_v3_keep3`` is the measured opener at the plain
    opener's keep structure; a bare ``..._v3`` lets the keep count float
    against the food price. An ``_allgoals`` segment reads all four
    end-of-round goals instead of round 1's alone.
    """

    base_id, target_keep_count, goal_horizon = _parse_setup_policy_id(policy_id)
    for (bonus_scoring, bird_scoring), known in _SETUP_POLICY_IDS.items():
        if known == base_id:
            return PotentialPointsSetupPolicy(
                bonus_scoring=bonus_scoring,
                bird_scoring=bird_scoring,
                target_keep_count=target_keep_count,
                goal_horizon=goal_horizon,
            )
    raise ValueError(
        f"unknown potential_points setup policy id: {policy_id!r}; expected one of "
        f"{tuple(_SETUP_POLICY_IDS.values())} with optional {_ALL_GOALS_SUFFIX} and _keepN suffixes"
    )


def _parse_setup_policy_id(policy_id: str) -> tuple[str, int | None, str]:
    """``<base>[_allgoals][_keepN]`` → (base id, keep count, goal horizon)."""

    base_id, target_keep_count = policy_id, None
    match = _KEEP_SUFFIX.match(policy_id)
    if match:
        base_id, target_keep_count = match["base"], int(match["count"])
    goal_horizon = DEFAULT_SETUP_GOAL_HORIZON
    if base_id.endswith(_ALL_GOALS_SUFFIX):
        base_id, goal_horizon = base_id[: -len(_ALL_GOALS_SUFFIX)], "all"
    return base_id, target_keep_count, goal_horizon


def is_potential_points_setup_policy_id(policy_id: str) -> bool:
    return _parse_setup_policy_id(policy_id)[0] in _SETUP_POLICY_IDS.values()


@dataclass(frozen=True)
class PotentialPointsSetupPolicy:
    """Opening setup heuristic for final-score potential and early tempo."""

    policy_id: str = field(init=False)
    target_keep_count: int | None = None
    bonus_scoring: str = DEFAULT_BONUS_SCORING
    bird_scoring: str = DEFAULT_BIRD_SCORING
    bird_play_values_path: str | None = None
    opening_food_value: float = DEFAULT_OPENING_FOOD_VALUE
    unaffordable_discount: float = DEFAULT_UNAFFORDABLE_DISCOUNT
    #: ``"first"`` or ``"all"``; see ``SETUP_GOAL_HORIZONS``.
    goal_horizon: str = DEFAULT_SETUP_GOAL_HORIZON

    def __post_init__(self) -> None:
        if self.bonus_scoring not in BONUS_SCORING_KINDS:
            raise ValueError(
                f"unknown bonus_scoring: {self.bonus_scoring!r}; expected one of "
                f"{BONUS_SCORING_KINDS}"
            )
        if self.bird_scoring not in BIRD_SCORING_KINDS:
            raise ValueError(
                f"unknown bird_scoring: {self.bird_scoring!r}; expected one of {BIRD_SCORING_KINDS}"
            )
        if self.goal_horizon not in SETUP_GOAL_HORIZONS:
            raise ValueError(
                f"unknown goal_horizon: {self.goal_horizon!r}; expected one of "
                f"{SETUP_GOAL_HORIZONS}"
            )
        policy_id = _SETUP_POLICY_IDS[(self.bonus_scoring, self.bird_scoring)]
        if self.goal_horizon == "all":
            policy_id = f"{policy_id}{_ALL_GOALS_SUFFIX}"
        if self.target_keep_count is not None:
            policy_id = f"{policy_id}_keep{self.target_keep_count}"
        object.__setattr__(self, "policy_id", policy_id)

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        if self.bird_scoring == "measured":
            values = load_bird_play_values(self.bird_play_values_path)

            def selection_scorer(cards, food, bonus_card, setup_context):
                return _measured_selection_score(
                    cards,
                    food,
                    values,
                    food_value=self.opening_food_value,
                    unaffordable_discount=self.unaffordable_discount,
                ) + _round_goal_setup_score(cards, setup_context, self.goal_horizon)
        elif self.bonus_scoring == "joint":

            def selection_scorer(cards, food, bonus_card, setup_context):
                # The bonus is priced here, against the cards actually kept,
                # and the crude alignment term is dropped so it is not counted
                # twice at two different qualities.
                return (
                    _selection_score(
                        cards,
                        food,
                        bonus_card,
                        setup_context,
                        card_scorer=_potential_card_score,
                        goal_horizon=self.goal_horizon,
                        bonus_alignment_weight=0.0,
                    )
                    + expected_bonus_points(bonus_card, list(cards)) * JOINT_BONUS_WEIGHT
                )
        else:

            def selection_scorer(cards, food, bonus_card, setup_context):
                return _selection_score(
                    cards,
                    food,
                    bonus_card,
                    setup_context,
                    card_scorer=_potential_card_score,
                    goal_horizon=self.goal_horizon,
                )

        return _best_selection(
            player,
            context,
            selection_scorer=selection_scorer,
            bonus_scorer=(
                expected_bonus_points
                if self.bonus_scoring in ("expected_points", "joint")
                else _potential_bonus_score
            ),
            target_keep_count=self.target_keep_count,
            joint_bonus=self.bonus_scoring == "joint",
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
    bonus_scorer,
    card_scorer=None,
    selection_scorer=None,
    target_keep_count: int | None = None,
    joint_bonus: bool = False,
) -> InitialSelection:
    if selection_scorer is None:
        if card_scorer is None:
            raise ValueError("_best_selection needs a card_scorer or a selection_scorer")

        def selection_scorer(cards, food, bonus_card, setup_context):
            return _selection_score(cards, food, bonus_card, setup_context, card_scorer=card_scorer)

    setup_context = context or InitialSelectionContext()
    if joint_bonus:
        bonus_candidates = list(player.bonus_cards)
    else:
        with profiling.node("bonus_card_choice", candidate_count=len(player.bonus_cards)):
            bonus_candidates = [
                max(
                    player.bonus_cards,
                    key=lambda bonus: (bonus_scorer(bonus, player.hand), bonus.name),
                )
            ]
    best_key: tuple[float, float, str] | None = None
    best_cards: tuple[BirdCard, ...] = ()
    best_food: tuple[FoodType, ...] = ()
    best_bonus = bonus_candidates[0]

    for bonus_card in bonus_candidates:
        for cards in _opening_card_subsets(player.hand, target_keep_count=target_keep_count):
            food_count = BIRD_FOOD_SELECTION_TOTAL - len(cards)
            with profiling.node("opening_subset_score"):
                food = _best_starting_food(cards, food_count)
                score = selection_scorer(cards, food, bonus_card, setup_context)
            # Ties are the common case -- the two bonus cards scored equally at
            # the optimum in 37% of 240 openings -- so the richer bonus scorer
            # breaks them rather than iteration order, which would otherwise
            # make joint enumeration arbitrarily worse than choosing first.
            key = (score, bonus_scorer(bonus_card, list(cards)), bonus_card.name)
            if best_key is None or key > best_key:
                best_key = key
                best_cards = cards
                best_food = food
                best_bonus = bonus_card

    return InitialSelection(
        player_id=player.player_id,
        kept_bird_names=[card.common_name for card in best_cards],
        kept_bonus_card_names=[best_bonus.name],
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
    goal_horizon: str = DEFAULT_SETUP_GOAL_HORIZON,
    bonus_alignment_weight: float = 1.8,
) -> float:
    selected = tuple(cards)
    score = sum(card_scorer(card, selected, bonus_card, context) for card in cards)
    score += _food_alignment_score(cards, food) * 1.7
    score += _habitat_balance_score(cards)
    score += _opening_playability_score(cards, food) * 2.5
    score += _bonus_alignment_score(bonus_card, cards) * bonus_alignment_weight
    score += _round_goal_setup_score(cards, context, goal_horizon)
    score -= max(len(cards) - 3, 0) * 0.45
    score -= max(2 - len(cards), 0) * 0.35
    return score


def _measured_selection_score(
    cards: tuple[BirdCard, ...],
    food: tuple[FoodType, ...],
    values: BirdPlayValues,
    *,
    food_value: float,
    unaffordable_discount: float,
) -> float:
    """Keep-set value in points: measured play values, food-gated, plus the food kept.

    Birds are paid for greedily in value order from the starting food, so two
    birds cannot both count as affordable on the same two tokens.
    """

    available: Counter[FoodType] = Counter(food)
    score = food_value * len(food)
    for card in sorted(cards, key=lambda c: (-values.value(c.common_name), c.common_name)):
        value = values.value(card.common_name)
        if _pay_from_pool(available, card):
            score += value
        else:
            score += value * unaffordable_discount
    return score


def _pay_from_pool(available: Counter[FoodType], card: BirdCard) -> bool:
    """Deduct the card's food cost from ``available`` if it can be paid; else leave it."""

    cost = card.food_cost
    if cost.minimum_total <= 0:
        return True
    if not _can_pay_fixed_food(available, card):
        return False
    total = sum(available.values())
    if total < cost.minimum_total:
        return False
    for food_type, count in cost.fixed.items():
        available[food_type] -= count
    wild = cost.minimum_total - sum(cost.fixed.values())
    for food_type in sorted(available, key=lambda f: (-available[f], f.value)):
        while wild > 0 and available[food_type] > 0:
            available[food_type] -= 1
            wild -= 1
    return True


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
        1 for card in hand if any(normalize_bonus_name(tag) == name for tag in card.bonus_card_tags)
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
    goal_horizon: str = DEFAULT_SETUP_GOAL_HORIZON,
) -> float:
    """Alignment of kept birds with the end-of-round goals.

    All four goals are public at setup, but until 2026-09-22 only round 1's
    was read. ``goal_horizon="all"`` adds the later goals at a discount that
    trades their higher placement scale (4/1 → 7/4/3) against the chance
    they are reached anyway.
    """

    if not context.round_goal_names:
        return 0.0
    goals = context.round_goal_names if goal_horizon == "all" else context.round_goal_names[:1]
    score = 0.0
    for index, goal_name in enumerate(goals):
        weight = 1.0
        if index:
            scale = ROUND_GOAL_GREEN_SCORES.get(index + 1, ROUND_GOAL_GREEN_SCORES[4])
            base = ROUND_GOAL_GREEN_SCORES[1][0]
            weight = (GOAL_HORIZON_DISCOUNT**index) * (scale[0] / base)
        score += weight * _single_goal_setup_score(cards, goal_name.lower())
    return score


def _single_goal_setup_score(cards: tuple[BirdCard, ...], goal: str) -> float:
    score = 0.0
    for card in cards:
        if "[bird]" in goal:
            for habitat in ordered_habitats(card.habitats):
                if habitat.value in goal:
                    score += 1.2
            if all(habitat.value not in goal for habitat in card.habitats):
                score += 0.25
        if card.nest_type and card.nest_type.value in goal:
            score += 0.8
        if "[egg]" in goal:
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
        any(f"[{food.value}]" in power_text for food in BASE_FOOD_TYPES) or "[wild]" in power_text
    )
