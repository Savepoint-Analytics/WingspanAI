"""Tests for the SQL analysis view layer.

These tests do not need a database: they check that the view file parses into
discrete statements, that view names stay stable, and that every view carries a
documented grain comment. Live-database checks belong in the gated persistence
integration test.
"""

import sys
from pathlib import Path
from unittest import TestCase

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from apply_sql_views import (  # noqa: E402
    DEFAULT_SQL_PATH,
    load_view_statements,
    parse_view_statements,
)

EXPECTED_VIEWS = {
    "v_simulation_runs",
    "v_game_player_scores",
    "v_action_events",
    "v_agent_decisions",
    "v_setup_selections",
    "v_agent_action_mix",
    "v_agent_performance",
    "v_head_to_head_games",
    "v_head_to_head_summary",
    "v_decision_cost",
    "v_setup_policy_outcomes",
    "v_run_quality",
    "v_seat_effect",
    "v_seat_effect_magnitude",
    "v_score_integrity_failures",
    "v_score_composition",
}


class ViewParsingTests(TestCase):
    def test_sql_file_exists(self) -> None:
        self.assertTrue(DEFAULT_SQL_PATH.exists(), DEFAULT_SQL_PATH)

    def test_all_expected_views_are_parsed(self) -> None:
        view_names = {view.view_name for view in load_view_statements()}

        self.assertEqual(view_names, EXPECTED_VIEWS)

    def test_statements_are_create_or_replace(self) -> None:
        for view in load_view_statements():
            self.assertIn("create or replace view", view.statement.lower(), view.view_name)

    def test_every_view_documents_its_grain(self) -> None:
        sql_text = DEFAULT_SQL_PATH.read_text(encoding="utf-8")

        # Each view is preceded by a comment block stating its row grain.
        self.assertEqual(sql_text.lower().count("-- grain:"), len(EXPECTED_VIEWS))

    def test_parser_ignores_leading_comments_and_blank_statements(self) -> None:
        statements = parse_view_statements(
            "-- a comment\n\n"
            "create or replace view v_one as select 1 as x;\n"
            "\n"
            "create or replace view v_two as select 2 as y;\n"
        )

        self.assertEqual([view.view_name for view in statements], ["v_one", "v_two"])

    def test_parser_returns_nothing_for_non_view_sql(self) -> None:
        self.assertEqual(parse_view_statements("select 1;\n"), [])


class ViewQualityGateTests(TestCase):
    def test_claim_grade_gate_requires_replay_validity_and_coverage(self) -> None:
        statement = next(
            view.statement
            for view in load_view_statements()
            if view.view_name == "v_run_quality"
        ).lower()

        self.assertIn("replay_invalid", statement)
        self.assertIn("low_power_coverage", statement)
        self.assertIn("multiplayer_rules_unverified", statement)
        self.assertIn("claim_grade", statement)

    def test_performance_views_exclude_invalid_replays(self) -> None:
        for view_name in ("v_agent_performance", "v_head_to_head_summary"):
            statement = next(
                view.statement
                for view in load_view_statements()
                if view.view_name == view_name
            ).lower()

            self.assertIn("replay_is_valid is not false", statement, view_name)
