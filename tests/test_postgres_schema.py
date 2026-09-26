"""The telemetry schema's keys, asserted without a live database.

ADR 0006: ``game_id`` is not unique -- it omits the lineup and seat rotation,
so every game in a batch sharing a seed carries the same one. Keying ``games``
on it made 44.5% of the archive unrepresentable and the backfill silently
stalled at ~5,960 of 10,831 games. These tests pin the corrected keys so the
regression cannot come back quietly.
"""

from __future__ import annotations

import re
from unittest import TestCase

from wingspan_ai.telemetry.postgres import SCHEMA_STATEMENTS


def table_ddl(name: str) -> str:
    for statement in SCHEMA_STATEMENTS:
        if re.search(rf"create table if not exists {name}\b", statement):
            return statement
    raise AssertionError(f"no DDL for {name}")


class GameIdentityTests(TestCase):
    def test_games_is_keyed_on_the_run_id(self) -> None:
        ddl = table_ddl("games")
        self.assertRegex(ddl, r"simulation_run_id text primary key")

    def test_games_does_not_key_on_the_game_id(self) -> None:
        ddl = table_ddl("games")
        self.assertNotRegex(ddl, r"game_id text primary key")
        # still present, as the batch-scoped label it always was
        self.assertRegex(ddl, r"game_id text not null")

    def test_game_scores_is_keyed_on_the_run_id_and_player(self) -> None:
        ddl = table_ddl("game_scores")
        self.assertIn("primary key (simulation_run_id, player_id)", ddl)
        self.assertNotIn("primary key (game_id, player_id)", ddl)

    def test_no_table_declares_a_foreign_key_to_games_game_id(self) -> None:
        """A FK would require uniqueness that ``game_id`` does not have."""

        for statement in SCHEMA_STATEMENTS:
            self.assertNotIn("references games(game_id)", statement)

    def test_game_scores_cascades_from_games(self) -> None:
        """Reloading a game must not leave its old score rows orphaned."""

        self.assertIn(
            "references games(simulation_run_id) on delete cascade",
            table_ddl("game_scores"),
        )

    def test_game_id_is_indexed_for_grouping_by_batch(self) -> None:
        joined = "\n".join(SCHEMA_STATEMENTS)
        self.assertIn("games_game_id_idx on games (game_id)", joined)


class ManifestObjectKeyTests(TestCase):
    """Several invocations can share a batch_kind/batch_label/batch_id triple.

    The manifest object key was built from that triple alone, so each
    invocation overwrote the last: 120 of 120 sampled batch directories held a
    manifest listing one game while archiving up to 240. The segment below is
    what keeps them apart.
    """

    def test_segment_separates_invocations_by_seed_range(self) -> None:
        from flows.simulation_batch import _manifest_segment

        started = "2026-09-17T10:40:17+00:00"
        self.assertNotEqual(
            _manifest_segment(started, [1, 2]), _manifest_segment(started, [3, 4])
        )

    def test_segment_separates_invocations_by_start_time(self) -> None:
        from flows.simulation_batch import _manifest_segment

        self.assertNotEqual(
            _manifest_segment("2026-09-17T10:40:17+00:00", [1]),
            _manifest_segment("2026-09-17T10:40:18+00:00", [1]),
        )

    def test_segment_is_a_safe_single_path_element(self) -> None:
        from flows.simulation_batch import _manifest_segment

        segment = _manifest_segment("2026-09-17T10:40:17.123456+00:00", [1, 4])
        self.assertNotIn("/", segment)
        self.assertNotIn(":", segment)
        self.assertEqual(segment, "20260917T104017_seeds_1-4")

    def test_segment_tolerates_a_missing_start_time_and_no_seeds(self) -> None:
        from flows.simulation_batch import _manifest_segment

        self.assertEqual(_manifest_segment("", []), "unknown_seeds_noseeds")

    def test_filename_is_unchanged_so_existing_readers_still_match(self) -> None:
        """``rglob("batch_manifest.json")`` and ``endswith`` readers must keep working."""

        from flows.simulation_batch import MANIFEST_FILENAME

        self.assertEqual(MANIFEST_FILENAME, "batch_manifest.json")
