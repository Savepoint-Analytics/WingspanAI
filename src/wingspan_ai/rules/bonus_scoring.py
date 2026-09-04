"""Bonus-card scoring driven by each card's own printed text.

Why this replaces the previous approach
---------------------------------------
Scoring used to be a long hand-written branch per bonus card, with both the
qualifying condition and the point tiers restated in code. An audit against the
cards' own printed `victory_point_text` found five of twenty-six scoring wrongly:

- **Omnivore Expert** ("Birds that eat [wild]") tested `choice_food_count` while
  every qualifying bird uses `wild_food_count`. It always scored zero.
- **Food Web Expert** ("Birds that eat *only* [invertebrate]") required a cost of
  exactly one invertebrate, so a bird costing two invertebrates scored nothing.
- **Photographer**, **Historian** and **Anatomist** re-derived qualification from
  bird names using hand-written word lists, and missed most qualifying birds —
  Photographer found almost none of its 63 tagged birds.

The workbook already records, on every one of the 180 birds, exactly which bonus
cards it satisfies (`BirdCard.bonus_card_tags`), and every bonus card carries its
own printed scoring formula. Deriving both from the data removes the duplicated
conditions and the fragile name heuristics, and makes the card text the single
source of truth.

Four cards score from board state rather than bird identity and keep explicit
counters: they are exactly the four with no tagged birds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from wingspan_ai.content.schemas import BonusCard, Habitat

#: "2 per bird"
_PER_BIRD = re.compile(r"^\s*(\d+)\s*per\s+bird", re.IGNORECASE)
#: "5 to 7 birds: 3; 8+ birds: 7" and the "…; 5 birds: 8" variant used where the
#: upper tier is the maximum reachable count, which means the same thing.
_TWO_TIER = re.compile(
    r"(\d+)\s*to\s*(\d+)[^:;]*:\s*(\d+)\s*;\s*(\d+)\s*\+?[^:;]*:\s*(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BonusCardScoringRule:
    """Point formula parsed from a bonus card's printed text."""

    per_bird_points: int | None = None
    low_threshold: int | None = None
    low_points: int | None = None
    high_threshold: int | None = None
    high_points: int | None = None

    def points_for(self, count: int) -> int:
        if self.per_bird_points is not None:
            return self.per_bird_points * count
        if self.high_threshold is not None and count >= self.high_threshold:
            return self.high_points or 0
        if self.low_threshold is not None and count >= self.low_threshold:
            return self.low_points or 0
        return 0


def parse_bonus_card_scoring(victory_point_text: str | None) -> BonusCardScoringRule | None:
    """Parse a printed scoring formula. Returns None when the text is unknown."""

    if not victory_point_text:
        return None
    text = victory_point_text.strip()

    per_bird = _PER_BIRD.match(text)
    if per_bird:
        return BonusCardScoringRule(per_bird_points=int(per_bird.group(1)))

    tier = _TWO_TIER.search(text)
    if tier:
        low, _low_upper, low_points, high, high_points = (int(x) for x in tier.groups())
        return BonusCardScoringRule(
            low_threshold=low,
            low_points=low_points,
            high_threshold=high,
            high_points=high_points,
        )
    return None


def normalize_bonus_name(name: str) -> str:
    """Strip expansion suffixes so bird tags and card names compare equal."""

    return name.split("[", maxsplit=1)[0].strip()


def _count_birds_with_at_least_eggs(player, minimum: int) -> int:
    return sum(1 for slot in player.played_birds if slot.eggs >= minimum)


def _count_fewest_habitat(player) -> int:
    return min(len(player.habitats[habitat]) for habitat in Habitat)


#: Bonus cards scored from board state rather than bird identity. These are
#: exactly the four cards with no tagged birds in the workbook.
BOARD_STATE_COUNTERS = {
    "Breeding Manager": lambda player: _count_birds_with_at_least_eggs(player, 4),
    "Oologist": lambda player: _count_birds_with_at_least_eggs(player, 1),
    "Ecologist": _count_fewest_habitat,
    "Visionary Leader": lambda player: len(player.hand),
}


def qualifying_count(bonus_card: BonusCard, player) -> int:
    """How many of the player's items satisfy this bonus card."""

    name = normalize_bonus_name(bonus_card.name)
    counter = BOARD_STATE_COUNTERS.get(name)
    if counter is not None:
        return counter(player)
    return sum(
        1
        for slot in player.played_birds
        if any(normalize_bonus_name(tag) == name for tag in slot.card.bonus_card_tags)
    )


def score_bonus_card(bonus_card: BonusCard, player) -> int:
    """Score one bonus card against a player's board using its printed formula."""

    rule = parse_bonus_card_scoring(bonus_card.victory_point_text)
    if rule is None:
        return 0
    return rule.points_for(qualifying_count(bonus_card, player))
