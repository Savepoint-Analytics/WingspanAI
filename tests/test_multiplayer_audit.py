"""Regression tests for the 3-5 player rule audit.

These tests are the publication gate for multiplayer results. They encode the
core rulebook's stated values and its worked tie example independently of the
implementation, so a regression in either constant or in
`score_round_goal_competitive` fails here rather than silently skewing a
multiplayer experiment.
"""

from unittest import TestCase

from wingspan_ai.rules.base_game import BASE_ACTION_CUBES_BY_ROUND, ROUND_GOAL_GREEN_SCORES
from wingspan_ai.rules.multiplayer_audit import (
    EXPECTED_ACTION_CUBES_BY_ROUND,
    EXPECTED_GREEN_GOAL_SCORES,
    KNOWN_SIMPLIFICATIONS,
    MultiplayerAuditError,
    _score_with_forest_counts,
    audit_multiplayer_rules,
)


class RulebookConstantTests(TestCase):
    def test_action_cubes_match_the_rulebook_and_ignore_player_count(self) -> None:
        # Core rulebook page 5: 8 / 7 / 6 / 5 turns per player, stated once for a
        # 1-5 player game with no player-count qualifier.
        self.assertEqual(BASE_ACTION_CUBES_BY_ROUND, EXPECTED_ACTION_CUBES_BY_ROUND)
        self.assertEqual(BASE_ACTION_CUBES_BY_ROUND, {1: 8, 2: 7, 3: 6, 4: 5})

    def test_green_goal_tiers_match_the_goal_board(self) -> None:
        # Core rulebook page 11 goal board: 1st 4/5/6/7, 2nd 1/2/3/4,
        # 3rd 0/1/2/3, 4th-5th 0.
        self.assertEqual(
            {round_number: tuple(scores) for round_number, scores in
             ROUND_GOAL_GREEN_SCORES.items()},
            EXPECTED_GREEN_GOAL_SCORES,
        )

    def test_placement_scores_cover_a_five_player_table(self) -> None:
        for round_number, scores in ROUND_GOAL_GREEN_SCORES.items():
            self.assertEqual(len(scores), 5, round_number)


class GoalScoringBehaviourTests(TestCase):
    """The ranking rules that barely matter at two players and matter at 3-5."""

    def test_rulebook_worked_tie_example(self) -> None:
        # Page 11: on a 5/2/1 goal, two players tied for 1st each score
        # (5 + 2) // 2 = 3, and 2nd place is not awarded, so the next player
        # takes 3rd place points.
        scores = _score_with_forest_counts([3, 3, 1], round_number=2)

        self.assertEqual(sorted(scores.values(), reverse=True), [3, 3, 1])

    def test_zero_item_players_never_place(self) -> None:
        # Page 11: "You must have at least 1 of the targeted items to score."
        scores = _score_with_forest_counts([2, 0, 0, 0], round_number=4)

        self.assertEqual(sorted(scores.values(), reverse=True), [7, 0, 0, 0])

    def test_only_the_top_three_places_score(self) -> None:
        scores = _score_with_forest_counts([5, 4, 3, 2, 1], round_number=4)

        self.assertEqual(sorted(scores.values(), reverse=True), [7, 4, 3, 0, 0])

    def test_a_full_table_tie_cannot_inflate_the_round_total(self) -> None:
        scores = _score_with_forest_counts([1, 1, 1, 1, 1], round_number=4)

        available = sum(EXPECTED_GREEN_GOAL_SCORES[4])
        self.assertLessEqual(sum(scores.values()), available)
        # (7 + 4 + 3 + 0 + 0) // 5 = 2 each.
        self.assertEqual(sorted(scores.values()), [2, 2, 2, 2, 2])

    def test_three_way_tie_for_first_skips_second_and_third(self) -> None:
        # Round 4 scores 7/4/3; three tied for 1st share (7 + 4 + 3) // 3 = 4,
        # and the fourth player receives nothing because places 2 and 3 are gone.
        scores = _score_with_forest_counts([2, 2, 2, 1], round_number=4)

        self.assertEqual(sorted(scores.values(), reverse=True), [4, 4, 4, 0])

    def test_two_player_scoring_is_unchanged_by_the_multiplayer_rules(self) -> None:
        scores = _score_with_forest_counts([3, 1], round_number=1)

        self.assertEqual(sorted(scores.values(), reverse=True), [4, 1])


class AuditReportTests(TestCase):
    def test_full_audit_passes_and_is_publication_safe(self) -> None:
        audit = audit_multiplayer_rules()

        self.assertTrue(audit["publication_safe"], audit["failed_checks"])
        self.assertEqual(audit["failed_check_count"], 0)
        self.assertEqual(audit["player_counts_audited"], [2, 3, 4, 5])

    def test_audit_can_be_scoped_to_one_player_count(self) -> None:
        audit = audit_multiplayer_rules(5)

        self.assertEqual(audit["player_counts_audited"], [5])
        self.assertTrue(any("_p5" in check["check_id"] for check in audit["checks"]))

    def test_every_check_carries_a_rulebook_citation(self) -> None:
        for check in audit_multiplayer_rules()["checks"]:
            self.assertTrue(check["rulebook"].endswith(".pdf"), check["check_id"])
            self.assertIn(check["rulebook_page"], (5, 7, 8, 11), check["check_id"])
            self.assertTrue(check["source_section"], check["check_id"])

    def test_audit_rejects_unsupported_player_counts(self) -> None:
        for player_count in (1, 6):
            with self.assertRaises(ValueError):
                audit_multiplayer_rules(player_count)

    def test_known_simplifications_are_declared_not_hidden(self) -> None:
        ids = {item.simplification_id for item in KNOWN_SIMPLIFICATIONS}

        self.assertIn("green_goals_only", ids)
        for item in KNOWN_SIMPLIFICATIONS:
            self.assertTrue(item.impact, item.simplification_id)
            self.assertGreaterEqual(item.player_count_sensitive_from, 2)

    def test_unbounded_supplies_are_verified_rules_not_gaps(self) -> None:
        # Core rulebook page 8: "There is no limit to the egg supply." Capping the
        # supply at the box's 75 miniatures would be the deviation, not the fix.
        checks = {check["check_id"]: check for check in audit_multiplayer_rules()["checks"]}
        simplification_ids = {item.simplification_id for item in KNOWN_SIMPLIFICATIONS}

        self.assertTrue(checks["egg_supply_is_unlimited"]["passed"])
        self.assertTrue(checks["food_supply_is_unlimited"]["passed"])
        self.assertNotIn("unlimited_egg_supply", simplification_ids)
        self.assertNotIn("unlimited_food_supply", simplification_ids)

    def test_egg_miniature_counts_are_recorded_for_provenance(self) -> None:
        from wingspan_ai.rules.multiplayer_audit import EGG_MINIATURE_COUNTS

        self.assertEqual(EGG_MINIATURE_COUNTS["core"], 75)
        self.assertEqual(EGG_MINIATURE_COUNTS["european"], 15)
        self.assertEqual(EGG_MINIATURE_COUNTS["oceania"], 15)
        self.assertEqual(EGG_MINIATURE_COUNTS["asia"], 30)

    def test_audit_payload_is_json_serializable(self) -> None:
        import json

        json.dumps(audit_multiplayer_rules())

    def test_audit_error_names_the_failing_checks(self) -> None:
        error = MultiplayerAuditError(["action_cubes_by_round"])

        self.assertIn("action_cubes_by_round", str(error))
        self.assertIn("publication-grade", str(error))
