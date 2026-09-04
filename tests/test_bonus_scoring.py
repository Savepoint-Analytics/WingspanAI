"""Validate every bonus card against its own printed scoring text.

Bonus scoring used to restate both the qualifying condition and the point tiers
in code. Five of twenty-six cards scored wrongly and nothing caught it:
`Omnivore Expert` tested the wrong food-cost field and always scored zero,
`Food Web Expert` demanded a cost of exactly one invertebrate, and
`Photographer`, `Historian` and `Anatomist` re-derived qualification from bird
names with hand-written word lists.

These tests drive each card across its whole tier range using the workbook's own
per-bird `bonus_card_tags`, so a regression in either the qualifying count or the
point formula fails here.
"""

from unittest import TestCase, skipIf

from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.schemas import BonusCard, Habitat
from wingspan_ai.rules.bonus_scoring import (
    BOARD_STATE_COUNTERS,
    BonusCardScoringRule,
    normalize_bonus_name,
    parse_bonus_card_scoring,
    qualifying_count,
    score_bonus_card,
)
from wingspan_ai.state.models import BirdSlot, PlayerState


class ScoringTextParserTests(TestCase):
    def test_per_bird_form(self) -> None:
        rule = parse_bonus_card_scoring("2 per bird")

        self.assertEqual(rule.per_bird_points, 2)
        self.assertEqual(rule.points_for(0), 0)
        self.assertEqual(rule.points_for(4), 8)

    def test_two_tier_open_ended_form(self) -> None:
        rule = parse_bonus_card_scoring("5 to 7 birds: 3; 8+ birds: 7")

        self.assertEqual(rule.points_for(4), 0)
        self.assertEqual(rule.points_for(5), 3)
        self.assertEqual(rule.points_for(7), 3)
        self.assertEqual(rule.points_for(8), 7)
        self.assertEqual(rule.points_for(20), 7)

    def test_two_tier_exact_upper_form(self) -> None:
        """Forester and Wetland Scientist cap at exactly 5, the reachable max."""

        rule = parse_bonus_card_scoring("3 to 4 birds: 4; 5 birds: 8")

        self.assertEqual(rule.points_for(2), 0)
        self.assertEqual(rule.points_for(3), 4)
        self.assertEqual(rule.points_for(5), 8)

    def test_unknown_text_returns_none_rather_than_guessing(self) -> None:
        self.assertIsNone(parse_bonus_card_scoring(None))
        self.assertIsNone(parse_bonus_card_scoring("score somehow"))

    def test_empty_rule_scores_nothing(self) -> None:
        self.assertEqual(BonusCardScoringRule().points_for(9), 0)


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class WorkbookBonusCardTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        cls.by_tag: dict[str, list] = {}
        for bird in cls.catalog.birds:
            for tag in bird.bonus_card_tags:
                cls.by_tag.setdefault(normalize_bonus_name(tag), []).append(bird)

    @staticmethod
    def _board(cards) -> PlayerState:
        player = PlayerState(player_id="player_1")
        for index, card in enumerate(cards):
            player.habitats[list(Habitat)[index % 3]].append(BirdSlot(card=card))
        return player

    def test_every_bonus_card_has_parseable_printed_text(self) -> None:
        unparsed = [
            bonus.name
            for bonus in self.catalog.bonus_cards
            if parse_bonus_card_scoring(bonus.victory_point_text) is None
        ]

        self.assertEqual(unparsed, [])

    def test_every_tag_based_card_scores_its_printed_tiers(self) -> None:
        checked = 0
        for bonus in self.catalog.bonus_cards:
            name = normalize_bonus_name(bonus.name)
            if name in BOARD_STATE_COUNTERS:
                continue
            rule = parse_bonus_card_scoring(bonus.victory_point_text)
            pool = self.by_tag.get(name, [])
            self.assertTrue(pool, f"{name} has no tagged birds")
            checked += 1
            for count in range(0, min(len(pool), 10) + 1):
                player = self._board(pool[:count])
                self.assertEqual(
                    score_bonus_card(bonus, player),
                    rule.points_for(count),
                    f"{name} at {count} qualifying birds",
                )
        self.assertGreaterEqual(checked, 20)

    def test_board_state_cards_are_exactly_those_without_tagged_birds(self) -> None:
        """The split is derived from the data, not asserted by hand."""

        untagged = {
            normalize_bonus_name(bonus.name)
            for bonus in self.catalog.bonus_cards
            if not self.by_tag.get(normalize_bonus_name(bonus.name))
        }

        self.assertEqual(untagged, set(BOARD_STATE_COUNTERS))

    def test_previously_broken_cards_now_score(self) -> None:
        """Regression guard for the five cards the audit caught."""

        for name in (
            "Omnivore Expert",
            "Food Web Expert",
            "Photographer",
            "Historian",
            "Cartographer",
        ):
            bonus = next(
                b for b in self.catalog.bonus_cards if normalize_bonus_name(b.name) == name
            )
            rule = parse_bonus_card_scoring(bonus.victory_point_text)
            pool = self.by_tag[name]
            # Enough qualifying birds to reach the top tier.
            target = rule.high_threshold or 5
            player = self._board(pool[:target])

            self.assertGreater(
                score_bonus_card(bonus, player), 0, f"{name} still scores zero"
            )

    def test_board_state_counters_read_the_right_signal(self) -> None:
        bird = next(b for b in self.catalog.birds if b.egg_limit >= 4)
        player = self._board([bird, bird, bird])
        for slot in player.played_birds:
            slot.eggs = 4
        player.hand = list(self.catalog.birds[:6])

        def bonus(name: str) -> BonusCard:
            return next(
                b for b in self.catalog.bonus_cards if normalize_bonus_name(b.name) == name
            )

        self.assertEqual(qualifying_count(bonus("Breeding Manager"), player), 3)
        self.assertEqual(qualifying_count(bonus("Oologist"), player), 3)
        self.assertEqual(qualifying_count(bonus("Visionary Leader"), player), 6)
        # Three birds spread one per habitat leaves every habitat at one.
        self.assertEqual(qualifying_count(bonus("Ecologist"), player), 1)
