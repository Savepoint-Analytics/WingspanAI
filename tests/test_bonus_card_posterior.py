"""Tests for the posterior over an opponent's hidden bonus cards."""

from unittest import TestCase, skipIf

from wingspan_ai.belief import (
    bonus_fit_value,
    estimate_bonus_card_posterior,
    normalize_bonus_name,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.state.models import BirdSlot


class BonusNameTests(TestCase):
    def test_expansion_suffixes_are_stripped_so_tags_match_card_names(self) -> None:
        self.assertEqual(normalize_bonus_name("Anatomist [swift_start_asia]"), "Anatomist")
        self.assertEqual(normalize_bonus_name("Wildlife Gardener"), "Wildlife Gardener")


class PosteriorEdgeCaseTests(TestCase):
    def test_no_bonus_cards_held_yields_no_posterior(self) -> None:
        self.assertEqual(estimate_bonus_card_posterior([], 0), {})

    def test_too_few_played_birds_yields_no_posterior(self) -> None:
        """One bird is not evidence of a plan."""

        self.assertEqual(estimate_bonus_card_posterior([], 1), {})


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class PosteriorInferenceTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)

    def _board(self, predicate, count=4):
        birds = [bird for bird in self.catalog.birds if predicate(bird)][:count]
        return [BirdSlot(card=bird) for bird in birds]

    def test_bowl_nest_board_infers_the_bowl_nest_bonus_card(self) -> None:
        board = self._board(
            lambda b: b.nest_type is not None and b.nest_type.value == "bowl"
        )

        posterior = estimate_bonus_card_posterior(board, bonus_card_count=1)
        top = max(posterior, key=posterior.get)

        self.assertEqual(top, "Wildlife Gardener")
        self.assertGreater(posterior[top], 0.25)

    def test_posterior_mass_is_bounded_by_cards_actually_held(self) -> None:
        board = self._board(lambda b: b.victory_points >= 5)

        for held in (1, 2):
            posterior = estimate_bonus_card_posterior(board, bonus_card_count=held)
            self.assertLessEqual(sum(posterior.values()), held + 1e-6)
            for probability in posterior.values():
                self.assertGreaterEqual(probability, 0.0)
                self.assertLessEqual(probability, 1.0)

    def test_bonus_fit_rewards_a_niche_card_matching_a_likely_held_card(self) -> None:
        """The case intrinsic card-strength scoring misses entirely."""

        board = self._board(
            lambda b: b.nest_type is not None and b.nest_type.value == "bowl"
        )
        posterior = estimate_bonus_card_posterior(board, bonus_card_count=1)

        niche_bowl = min(
            (
                b
                for b in self.catalog.birds
                if b.nest_type is not None and b.nest_type.value == "bowl"
            ),
            key=lambda b: b.victory_points,
        )
        high_vp_other = max(
            (
                b
                for b in self.catalog.birds
                if b.nest_type is None or b.nest_type.value != "bowl"
            ),
            key=lambda b: b.victory_points,
        )

        self.assertLess(niche_bowl.victory_points, high_vp_other.victory_points)
        self.assertGreater(
            bonus_fit_value(niche_bowl, posterior),
            bonus_fit_value(high_vp_other, posterior),
        )

    def test_bonus_fit_is_zero_without_a_posterior(self) -> None:
        card = self.catalog.birds[0]

        self.assertEqual(bonus_fit_value(card, {}), 0.0)
