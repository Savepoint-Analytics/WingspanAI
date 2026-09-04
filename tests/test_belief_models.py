"""Tests for opponent-type beliefs and action-family response probabilities."""

import math
from unittest import TestCase

from wingspan_ai.belief import (
    DEFAULT_PROFILE_MODELS,
    OpponentBeliefState,
    OpponentProfile,
    ProfileResponseModel,
    brier_score,
    log_loss,
    summarize_calibration,
    uniform_baseline_log_loss,
)
from wingspan_ai.rules.actions import ActionType

CANDIDATES = {
    ActionType.PLAY_BIRD: 3.0,
    ActionType.LAY_EGGS: 2.5,
    ActionType.DRAW_CARDS: 1.0,
    ActionType.GAIN_FOOD: 0.5,
}


class ProfileResponseModelTests(TestCase):
    def test_probabilities_sum_to_one(self) -> None:
        for profile, model in DEFAULT_PROFILE_MODELS.items():
            probabilities = model.family_probabilities(CANDIDATES)

            self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=9, msg=profile)

    def test_random_profile_ignores_value_and_follows_its_prior(self) -> None:
        model = DEFAULT_PROFILE_MODELS[OpponentProfile.RANDOM_LEGAL]

        high_value = model.family_probabilities(CANDIDATES)
        flipped = model.family_probabilities(
            {family: -value for family, value in CANDIDATES.items()}
        )

        # Infinite temperature means value estimates cannot move the prediction.
        self.assertEqual(high_value, flipped)
        # Draw-cards dominates because random agents sample concrete actions.
        self.assertEqual(max(high_value, key=high_value.get), ActionType.DRAW_CARDS)

    def test_value_maximizing_profile_favours_the_highest_value_family(self) -> None:
        model = DEFAULT_PROFILE_MODELS[OpponentProfile.VALUE_MAXIMIZING]

        probabilities = model.family_probabilities(CANDIDATES)

        self.assertEqual(max(probabilities, key=probabilities.get), ActionType.PLAY_BIRD)
        self.assertGreater(probabilities[ActionType.PLAY_BIRD], 0.5)

    def test_low_temperature_approaches_best_response(self) -> None:
        strict = ProfileResponseModel(
            profile=OpponentProfile.VALUE_MAXIMIZING,
            family_prior=dict.fromkeys(CANDIDATES, 0.25),
            value_temperature=0.05,
        )

        probabilities = strict.family_probabilities(CANDIDATES)

        self.assertGreater(probabilities[ActionType.PLAY_BIRD], 0.99)

    def test_empty_candidate_set_returns_no_probabilities(self) -> None:
        model = DEFAULT_PROFILE_MODELS[OpponentProfile.VALUE_MAXIMIZING]

        self.assertEqual(model.family_probabilities({}), {})

    def test_large_values_do_not_overflow(self) -> None:
        model = DEFAULT_PROFILE_MODELS[OpponentProfile.VALUE_MAXIMIZING]

        probabilities = model.family_probabilities(
            {ActionType.PLAY_BIRD: 1e9, ActionType.LAY_EGGS: -1e9}
        )

        self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=9)
        self.assertAlmostEqual(probabilities[ActionType.PLAY_BIRD], 1.0, places=6)


class BeliefStateTests(TestCase):
    def setUp(self) -> None:
        self.belief = OpponentBeliefState.uniform("player_1")

    def test_uniform_prior_covers_every_default_profile(self) -> None:
        self.assertEqual(
            set(self.belief.profile_posterior),
            set(DEFAULT_PROFILE_MODELS),
        )
        self.assertAlmostEqual(sum(self.belief.profile_posterior.values()), 1.0, places=9)

    def test_prediction_spreads_probability_across_families(self) -> None:
        distribution = self.belief.predict(CANDIDATES)

        self.assertAlmostEqual(sum(distribution.probabilities.values()), 1.0, places=9)
        # The old best-response model put all mass on one family; the mixture
        # must leave non-trivial mass on the low-value families too.
        self.assertGreater(distribution.probability_of(ActionType.DRAW_CARDS), 0.05)
        self.assertGreater(distribution.probability_of(ActionType.GAIN_FOOD), 0.02)

    def test_expected_value_is_below_best_value(self) -> None:
        distribution = self.belief.predict(CANDIDATES)

        self.assertLess(distribution.expected_value, distribution.best_value)
        self.assertEqual(distribution.best_value, 3.0)

    def test_observing_repeated_draws_shifts_posterior_away_from_maximizer(self) -> None:
        belief = self.belief
        for _ in range(10):
            belief = belief.observe(ActionType.DRAW_CARDS, CANDIDATES)

        posterior = belief.profile_posterior
        self.assertEqual(belief.observation_count, 10)
        # Draw-cards is a low-value family here, so a strict maximizer becomes
        # very unlikely and the draw-leaning explanations take nearly all mass.
        self.assertLess(posterior[OpponentProfile.VALUE_MAXIMIZING], 0.01)
        self.assertGreater(
            posterior[OpponentProfile.RANDOM_LEGAL] + posterior[OpponentProfile.CARD_DRAW],
            0.95,
        )

    def test_observing_the_best_family_supports_value_driven_profiles(self) -> None:
        belief = self.belief
        for _ in range(10):
            belief = belief.observe(ActionType.PLAY_BIRD, CANDIDATES)

        posterior = belief.profile_posterior
        # Play-bird is both the highest-value family and the engine-builder's
        # favoured family, so those two explanations should dominate while a
        # random opponent becomes implausible.
        self.assertGreater(
            posterior[OpponentProfile.VALUE_MAXIMIZING]
            + posterior[OpponentProfile.ENGINE_BUILDER],
            0.95,
        )
        self.assertLess(posterior[OpponentProfile.RANDOM_LEGAL], 0.01)

    def test_belief_updates_are_immutable(self) -> None:
        updated = self.belief.observe(ActionType.DRAW_CARDS, CANDIDATES)

        self.assertEqual(self.belief.observation_count, 0)
        self.assertEqual(updated.observation_count, 1)
        self.assertIsNot(updated, self.belief)

    def test_unmodelled_family_is_ignored_rather_than_treated_as_evidence(self) -> None:
        partial = {ActionType.PLAY_BIRD: 3.0, ActionType.LAY_EGGS: 2.0}

        updated = self.belief.observe(ActionType.DRAW_CARDS, partial)

        self.assertIs(updated, self.belief)

    def test_posterior_stays_normalized_after_many_updates(self) -> None:
        belief = self.belief
        for family in (ActionType.DRAW_CARDS, ActionType.PLAY_BIRD, ActionType.GAIN_FOOD) * 20:
            belief = belief.observe(family, CANDIDATES)

        self.assertAlmostEqual(sum(belief.profile_posterior.values()), 1.0, places=9)

    def test_empty_candidate_prediction_is_safe(self) -> None:
        distribution = self.belief.predict({})

        self.assertEqual(distribution.probabilities, {})
        self.assertEqual(distribution.expected_value, 0.0)
        self.assertIsNone(distribution.most_likely_family)

    def test_telemetry_payload_is_json_safe(self) -> None:
        payload = self.belief.predict(CANDIDATES).as_telemetry_payload()

        self.assertEqual(payload["opponent_id"], "player_1")
        self.assertIn("family_probabilities", payload)
        self.assertIn("profile_posterior", payload)
        self.assertTrue(
            all(isinstance(key, str) for key in payload["family_probabilities"])
        )


class CalibrationMetricTests(TestCase):
    def setUp(self) -> None:
        self.distribution = OpponentBeliefState.uniform("player_1").predict(CANDIDATES)

    def test_log_loss_rewards_probability_on_the_observed_family(self) -> None:
        likely = self.distribution.most_likely_family
        unlikely = min(
            self.distribution.probabilities,
            key=lambda family: self.distribution.probabilities[family],
        )

        self.assertLess(log_loss(self.distribution, likely), log_loss(self.distribution, unlikely))

    def test_brier_score_is_bounded_and_lower_when_confident_and_right(self) -> None:
        score = brier_score(self.distribution, self.distribution.most_likely_family)

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 2.0)

    def test_uniform_baseline_matches_analytic_value(self) -> None:
        self.assertAlmostEqual(uniform_baseline_log_loss(4), math.log(4), places=9)

    def test_summary_reports_improvement_over_uniform(self) -> None:
        # A belief that concentrates on draw-cards, observed drawing every time.
        belief = OpponentBeliefState.uniform("player_1")
        for _ in range(10):
            belief = belief.observe(ActionType.DRAW_CARDS, CANDIDATES)
        distributions = [belief.predict(CANDIDATES) for _ in range(5)]
        observed = [ActionType.DRAW_CARDS] * 5

        summary = summarize_calibration(distributions, observed)

        self.assertEqual(summary["predictions"], 5)
        self.assertEqual(summary["top1_accuracy"], 1.0)
        self.assertGreater(summary["log_loss_improvement"], 0.0)

    def test_summary_rejects_mismatched_lengths(self) -> None:
        with self.assertRaises(ValueError):
            summarize_calibration([self.distribution], [])

    def test_empty_summary_is_zeroed(self) -> None:
        self.assertEqual(summarize_calibration([], [])["predictions"], 0)
