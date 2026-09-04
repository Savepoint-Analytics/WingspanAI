"""Auditable multiplayer rule checks for 3-5 player games.

Why this module exists
----------------------
Every rule in this simulator was written and regression-tested against the
two-player case. Two things are player-count sensitive and would silently
corrupt any multiplayer claim if wrong:

1. **Action cubes per round.** If these varied by player count and the simulator
   assumed otherwise, every multiplayer game would have the wrong length.
2. **End-of-round goal scoring.** The green-side method ranks players against
   each other, so tie-splitting, place-skipping, and the zero-item rule barely
   matter at two players and matter a great deal at three to five.

Rather than trust a one-off reading, this module encodes the rulebook's stated
values and worked example as data with page citations, then checks the live
implementation against them. Run it before publishing anything multiplayer.

Source
------
`rulebook_pdfs/WS_Core_Rulebook.pdf`, verified 2026-08-31:

- Page 5, "Round Structure": "Round 1: 8 turns per player / Round 2: 7 turns per
  player / Round 3: 6 turns per player / Round 4: 5 turns per player." The
  rulebook states these per player with no player-count qualifier, and the game
  is billed as "for 1-5 players", so the schedule is player-count independent.
- Page 11, "Scoring End-of-Round Goals" and the goal board art: 1st place scores
  4/5/6/7 by round, 2nd scores 1/2/3/4, 3rd scores 0/1/2/3, and 4th/5th score 0.
- Page 11, ties: "If players tie, place both cubes on the tied place, and do not
  award the next place. At game end, you will add the points for that place and
  the next place(s), then divide by the number of players who tied and round
  down (4th place scores 0 points)."
- Page 11, worked example: "when using the goal that scores 5, 2, or 1 points,
  if two players tie for 1st place, each gets 3 points (5 + 2 divided by 2
  players, rounded down). Do not award 2nd place to another player."
- Page 11, zero items: "You must have at least 1 of the targeted items to score
  points for a goal."
- Page 8, "Managing egg tokens": "There is no limit to the egg supply. In the
  unlikely event that no eggs remain in the supply, use a temporary substitute."
- Page 7, food: "In the unlikely event that any type of food token is unavailable
  in the supply, use a temporary substitute."

Component counts are therefore convenience, not rules. The core box ships 75 egg
miniatures (European +15, Oceania +15, Asia +30), but the rulebook explicitly
declines to make that a game limit, so an unbounded simulated supply is correct
rather than a simplification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wingspan_ai.content.schemas import (
    BirdCard,
    ContentPack,
    FoodCost,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
    RoundGoal,
)

CORE_RULEBOOK = "rulebook_pdfs/WS_Core_Rulebook.pdf"
MIN_AUDITED_PLAYER_COUNT = 2
MAX_AUDITED_PLAYER_COUNT = 5

#: Turns per player per round. Page 5; identical for every player count.
EXPECTED_ACTION_CUBES_BY_ROUND: dict[int, int] = {1: 8, 2: 7, 3: 6, 4: 5}

#: Green-side placement scores by round, 1st through 5th. Page 11 goal board.
EXPECTED_GREEN_GOAL_SCORES: dict[int, tuple[int, ...]] = {
    1: (4, 1, 0, 0, 0),
    2: (5, 2, 1, 0, 0),
    3: (6, 3, 2, 0, 0),
    4: (7, 4, 3, 0, 0),
}


@dataclass(frozen=True)
class RuleCheck:
    """One pass/fail check against a cited rulebook statement."""

    check_id: str
    passed: bool
    expected: Any
    actual: Any
    rulebook: str
    rulebook_page: int
    source_section: str
    detail: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "expected": _jsonable(self.expected),
            "actual": _jsonable(self.actual),
            "rulebook": self.rulebook,
            "rulebook_page": self.rulebook_page,
            "source_section": self.source_section,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class KnownSimplification:
    """A player-count-sensitive rule the simulator deliberately does not model.

    Recorded explicitly so a multiplayer claim cannot silently rest on one.
    """

    simplification_id: str
    description: str
    player_count_sensitive_from: int
    impact: str
    rulebook_page: int | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "simplification_id": self.simplification_id,
            "description": self.description,
            "player_count_sensitive_from": self.player_count_sensitive_from,
            "impact": self.impact,
            "rulebook_page": self.rulebook_page,
        }


#: Component counts shipped in each box. Recorded for provenance only: the
#: rulebook states there is no supply limit, so these are not game limits.
EGG_MINIATURE_COUNTS: dict[str, int] = {
    "core": 75,
    "european": 15,
    "oceania": 15,
    "asia": 30,
}

#: Rules the simulator deliberately does not model. Kept deliberately short: an
#: entry here is a real gap, not a component-count curiosity.
KNOWN_SIMPLIFICATIONS: tuple[KnownSimplification, ...] = (
    KnownSimplification(
        simplification_id="green_goals_only",
        description=(
            "Only the green (competitive majority) goal side is implemented. The "
            "blue side scoring 1 point per item to a maximum of 5 is not."
        ),
        player_count_sensitive_from=2,
        impact=(
            "Player-count neutral in itself, but green goals are inherently more "
            "swingy at low player counts and blue goals are the usual recommendation "
            "for two players. Results are conditional on the green ruleset."
        ),
        rulebook_page=11,
    ),
)


def audit_multiplayer_rules(player_count: int | None = None) -> dict[str, Any]:
    """Check player-count-sensitive rules against the cited rulebook values.

    Pass ``player_count`` to scope the report to one table size; omit it to audit
    every supported size. The returned payload is JSON-serializable for batch
    manifests.
    """

    checks: list[RuleCheck] = []
    checks.append(_check_action_cubes())
    checks.append(_check_green_goal_tiers())
    checks.extend(_check_unbounded_supplies())

    player_counts = (
        [player_count]
        if player_count is not None
        else list(range(MIN_AUDITED_PLAYER_COUNT, MAX_AUDITED_PLAYER_COUNT + 1))
    )
    for count in player_counts:
        if count < MIN_AUDITED_PLAYER_COUNT or count > MAX_AUDITED_PLAYER_COUNT:
            raise ValueError(
                f"player_count must be between {MIN_AUDITED_PLAYER_COUNT} and "
                f"{MAX_AUDITED_PLAYER_COUNT}, got {count}"
            )
        checks.extend(_behavioural_checks(count))

    failed = [check for check in checks if not check.passed]
    return {
        "audit_id": "multiplayer_rule_audit_v1",
        "rulebook": CORE_RULEBOOK,
        "verified_on": "2026-08-31",
        "player_counts_audited": player_counts,
        "check_count": len(checks),
        "failed_check_count": len(failed),
        # A multiplayer result should not be published unless this is true.
        "publication_safe": not failed,
        "checks": [check.as_payload() for check in checks],
        "failed_checks": [check.check_id for check in failed],
        "known_simplifications": [item.as_payload() for item in KNOWN_SIMPLIFICATIONS],
    }


def _check_action_cubes() -> RuleCheck:
    from wingspan_ai.rules.base_game import BASE_ACTION_CUBES_BY_ROUND

    actual = dict(BASE_ACTION_CUBES_BY_ROUND)
    return RuleCheck(
        check_id="action_cubes_by_round",
        passed=actual == EXPECTED_ACTION_CUBES_BY_ROUND,
        expected=EXPECTED_ACTION_CUBES_BY_ROUND,
        actual=actual,
        rulebook=CORE_RULEBOOK,
        rulebook_page=5,
        source_section="Round Structure",
        detail=(
            "Turns per player per round. The rulebook states one schedule for a "
            "1-5 player game, so this must not vary with player count."
        ),
    )


def _check_green_goal_tiers() -> RuleCheck:
    from wingspan_ai.rules.base_game import ROUND_GOAL_GREEN_SCORES

    actual = {round_number: tuple(scores) for round_number, scores in
              ROUND_GOAL_GREEN_SCORES.items()}
    return RuleCheck(
        check_id="green_goal_placement_scores",
        passed=actual == EXPECTED_GREEN_GOAL_SCORES,
        expected=EXPECTED_GREEN_GOAL_SCORES,
        actual=actual,
        rulebook=CORE_RULEBOOK,
        rulebook_page=11,
        source_section="Scoring End-of-Round Goals / goal board",
        detail=(
            "1st place scores 4/5/6/7 by round, 2nd 1/2/3/4, 3rd 0/1/2/3, and "
            "4th-5th score 0. Five entries are required to rank a five-player table."
        ),
    )


def _check_unbounded_supplies() -> list[RuleCheck]:
    """Confirm the simulator's unbounded supplies match the stated rules.

    This looks like a fidelity gap and is not one. The rulebook explicitly
    declines to make component counts a game limit, so an unbounded supply is
    correct and capping it at the box contents would be the deviation.
    """

    from wingspan_ai.state.models import GameState, PlayerState

    # Neither the game state nor the player state carries a shared supply, which
    # is exactly what "there is no limit to the egg supply" requires.
    game_fields = set(GameState.model_fields)
    player_fields = set(PlayerState.model_fields)
    supply_fields = {
        name
        for name in game_fields | player_fields
        if "supply" in name and name != "food_tokens"
    }
    return [
        RuleCheck(
            check_id="egg_supply_is_unlimited",
            passed=not supply_fields,
            expected="no bounded shared supply modelled",
            actual=sorted(supply_fields) or "none",
            rulebook=CORE_RULEBOOK,
            rulebook_page=8,
            source_section="Managing egg tokens",
            detail=(
                "\"There is no limit to the egg supply. In the unlikely event that "
                "no eggs remain in the supply, use a temporary substitute.\" The box "
                f"ships {EGG_MINIATURE_COUNTS['core']} egg miniatures "
                "(European +15, Oceania +15, Asia +30), but that is a component "
                "count, not a rule. An unbounded simulated supply is correct."
            ),
        ),
        RuleCheck(
            check_id="food_supply_is_unlimited",
            passed=not supply_fields,
            expected="no bounded shared supply modelled",
            actual=sorted(supply_fields) or "none",
            rulebook=CORE_RULEBOOK,
            rulebook_page=7,
            source_section="Gain Food / supply",
            detail=(
                "\"In the unlikely event that any type of food token is unavailable "
                "in the supply, use a temporary substitute.\" Component counts are "
                "not a game limit."
            ),
        ),
    ]


def _behavioural_checks(player_count: int) -> list[RuleCheck]:
    """Run the ranking rules that only bite once more than two players rank."""

    checks: list[RuleCheck] = []

    # Rulebook worked example, page 11: round 2 goal scoring 5/2/1, two players
    # tie for 1st, each scores (5 + 2) // 2 = 3, and 2nd place is not awarded.
    if player_count >= 3:
        forest_counts = [3, 3, 1] + [0] * (player_count - 3)
        scores = _score_with_forest_counts(forest_counts, round_number=2)
        tied = sorted(scores.values(), reverse=True)
        expected = [3, 3, 1] + [0] * (player_count - 3)
        checks.append(
            RuleCheck(
                check_id=f"tie_split_and_place_skip_p{player_count}",
                passed=tied == expected,
                expected=expected,
                actual=tied,
                rulebook=CORE_RULEBOOK,
                rulebook_page=11,
                source_section="Scoring End-of-Round Goals / ties",
                detail=(
                    "Rulebook worked example: two players tied for 1st on a 5/2/1 "
                    "goal each score 3, and 2nd place is not awarded, so the third "
                    "player takes 3rd place points."
                ),
            )
        )

    # "You must have at least 1 of the targeted items to score points for a goal."
    zero_counts = [2] + [0] * (player_count - 1)
    zero_scores = _score_with_forest_counts(zero_counts, round_number=4)
    zero_item_scores = sorted(zero_scores.values(), reverse=True)
    checks.append(
        RuleCheck(
            check_id=f"zero_item_players_score_nothing_p{player_count}",
            passed=zero_item_scores == [7] + [0] * (player_count - 1),
            expected=[7] + [0] * (player_count - 1),
            actual=zero_item_scores,
            rulebook=CORE_RULEBOOK,
            rulebook_page=11,
            source_section="Scoring End-of-Round Goals / minimum quantity",
            detail=(
                "Players holding none of the targeted item place a cube on 0 and "
                "must not receive 2nd or 3rd place points."
            ),
        )
    )

    # 4th and 5th place score 0 even with a positive quantity.
    if player_count >= 4:
        descending = list(range(player_count, 0, -1))
        ranked = _score_with_forest_counts(descending, round_number=4)
        ranked_scores = sorted(ranked.values(), reverse=True)
        expected_ranked = [7, 4, 3] + [0] * (player_count - 3)
        checks.append(
            RuleCheck(
                check_id=f"fourth_and_fifth_place_score_zero_p{player_count}",
                passed=ranked_scores == expected_ranked,
                expected=expected_ranked,
                actual=ranked_scores,
                rulebook=CORE_RULEBOOK,
                rulebook_page=11,
                source_section="Scoring End-of-Round Goals / goal board",
                detail=(
                    "Only the top three places score. 4th and 5th place a cube on "
                    "the 0 space even though they hold the targeted item."
                ),
            )
        )

    # Total points awarded can never exceed the points available for the round.
    saturated = _score_with_forest_counts([1] * player_count, round_number=4)
    available = sum(EXPECTED_GREEN_GOAL_SCORES[4][:player_count])
    awarded = sum(saturated.values())
    checks.append(
        RuleCheck(
            check_id=f"all_tied_does_not_inflate_points_p{player_count}",
            passed=awarded <= available,
            expected=f"<= {available}",
            actual=awarded,
            rulebook=CORE_RULEBOOK,
            rulebook_page=11,
            source_section="Scoring End-of-Round Goals / ties",
            detail=(
                "With every player tied, the pooled places are divided and rounded "
                "down, so the table cannot award more than the round's total."
            ),
        )
    )
    return checks


def _score_with_forest_counts(
    forest_counts: list[int],
    *,
    round_number: int,
) -> dict[str, int]:
    """Score a forest-bird goal for a synthetic table with the given counts."""

    from wingspan_ai.rules.base_game import score_round_goal_competitive
    from wingspan_ai.state.models import BirdSlot, GameState, PlayerState, RoundState

    players = []
    for index, count in enumerate(forest_counts):
        player = PlayerState(player_id=f"player_{index + 1}")
        player.habitats[Habitat.FOREST] = [
            BirdSlot(card=_audit_bird(f"Audit Bird {index}_{slot}"))
            for slot in range(count)
        ]
        players.append(player)

    goals = [
        RoundGoal(name="[bird] in [forest]", content_pack=ContentPack.CORE)
        for _ in range(4)
    ]
    state = GameState(
        game_id="multiplayer_rule_audit",
        ruleset=_audit_ruleset(len(forest_counts)),
        random_seed=0,
        players=players,
        decks=_empty_decks(),
        round_goals=goals,
        round_state=RoundState(round_number=round_number),
    )
    return score_round_goal_competitive(state, round_number - 1)


def _audit_bird(common_name: str) -> BirdCard:
    return BirdCard(
        common_name=common_name,
        scientific_name="Audit avis",
        content_pack=ContentPack.CORE,
        habitats={Habitat.FOREST},
        food_cost=FoodCost(),
        victory_points=1,
        nest_type=NestType.BOWL,
        egg_limit=2,
        wingspan_cm=30,
        power=Power(
            color=PowerColor.NONE,
            implementation_status=PowerImplementationStatus.NO_OP_FOR_V1,
        ),
    )


def _audit_ruleset(player_count: int):
    from wingspan_ai.content.schemas import RulesetMetadata, RulesModule

    return RulesetMetadata(
        ruleset_id="multiplayer_rule_audit",
        content_packs=[ContentPack.CORE],
        rules_modules=[RulesModule.BASE_GAME],
        player_count=player_count,
        random_seed=0,
    )


def _empty_decks():
    from wingspan_ai.state.models import DeckState

    return DeckState()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return list(value)
    return value


@dataclass(frozen=True)
class MultiplayerAuditError(Exception):
    """Raised when a multiplayer batch is run against failing rule checks."""

    failed_check_ids: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            "multiplayer rule audit failed; refusing to treat results as "
            f"publication-grade: {', '.join(self.failed_check_ids)}"
        )
