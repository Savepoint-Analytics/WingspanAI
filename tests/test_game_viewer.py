"""The step-through game viewer renders a replayed game from one seat's point of view."""

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.simulation.artifacts import write_simulation_artifacts
from wingspan_ai.simulation.runner import run_single_game


@skipIf(not DEFAULT_WORKBOOK_PATH.exists(), "workbook required")
class GameViewerTests(TestCase):
    def test_transcript_shows_board_private_hand_ranking_and_choice(self) -> None:
        from analysis.game_viewer import view

        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        result = run_single_game(
            catalog,
            [
                PotentialPointsAgent(
                    agent_id="potential_points_p1",
                    search_depth=1,
                    final_search_turns=8,
                    determinization_samples=1,
                ),
                GreedyBaselineAgent(agent_id="greedy_immediate_p2"),
            ],
            random_seed=4,
            max_turns=6,
        )
        with TemporaryDirectory() as tmp:
            game_dir = write_simulation_artifacts(result, Path(tmp) / "game")
            out = io.StringIO()
            view(
                game_dir,
                pov=None,
                turns=None,
                interactive=False,
                all_actions=True,
                all_private=False,
                others=False,
                out=out,
            )
        text = out.getvalue()
        self.assertIn("## Setup", text)
        self.assertIn("◀ POV", text)
        self.assertIn("hand (", text)
        self.assertIn("basis: search", text)
        self.assertIn("CHOSE:", text)
        self.assertIn("legal actions (", text)
        self.assertIn("effect:", text)
        # Only the POV seat's private information is shown.
        self.assertEqual(text.count("bonus: "), text.count("=== turn"))
