import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

COMPARISON_PATH = Path(__file__).parents[1] / "analysis" / "simulation_batch_comparison.py"
COMPARISON_SPEC = importlib.util.spec_from_file_location(
    "simulation_batch_comparison",
    COMPARISON_PATH,
)
if COMPARISON_SPEC is None or COMPARISON_SPEC.loader is None:
    raise RuntimeError(f"Could not load comparison module from {COMPARISON_PATH}")
simulation_batch_comparison = importlib.util.module_from_spec(COMPARISON_SPEC)
COMPARISON_SPEC.loader.exec_module(simulation_batch_comparison)


class SimulationBatchComparisonTests(TestCase):
    def test_compare_batch_manifests_summarizes_scores_actions_and_decisions(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest_path = _write_manifest(root)

            comparison = simulation_batch_comparison.compare_batch_manifests([manifest_path])
            summary = comparison["batch_summaries"][0]
            decision = comparison["decision_summaries"][0]
            score_mix = comparison["score_breakdowns"][0]
            action_rounds = {
                row["round_number"]: row
                for row in comparison["action_frequency_by_round"]
            }
            actions = {
                row["action_type"]: row
                for row in comparison["action_frequency"]
            }

            self.assertEqual(summary["player_two_agent_id"], "potential_points_p2")
            self.assertEqual(summary["player_two_wins"], 1.5)
            self.assertEqual(summary["player_two_win_rate"], 0.75)
            self.assertEqual(summary["player_two_avg_score"], 32)
            self.assertEqual(summary["average_margin"], 7)
            self.assertEqual(actions["play_bird"]["count"], 1)
            self.assertEqual(actions["gain_food"]["count"], 1)
            self.assertAlmostEqual(decision["average_selected_value_delta"], 1.0)
            self.assertAlmostEqual(decision["average_selected_realized_delta"], 0.25)
            self.assertAlmostEqual(decision["endgame_search_share"], 0.5)
            self.assertAlmostEqual(decision["average_action_selection_elapsed_ms"], 10.0)
            self.assertAlmostEqual(decision["average_decision_total_elapsed_ms"], 13.0)
            self.assertAlmostEqual(score_mix["bird_points"], 16.0)
            self.assertAlmostEqual(score_mix["egg_points"], 7.5)
            self.assertAlmostEqual(score_mix["total"], 32.0)
            self.assertAlmostEqual(action_rounds[1]["play_bird"], 1.0)
            self.assertAlmostEqual(action_rounds[2]["gain_food"], 1.0)

    def test_render_markdown_report_includes_batch_table(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manifest_path = _write_manifest(Path(tmp_dir))
            report = simulation_batch_comparison.render_markdown_report(
                simulation_batch_comparison.compare_batch_manifests([manifest_path])
            )

            self.assertIn("| comparison | potential_points_p2 |", report)
            self.assertIn("## Player 2 Action Mix", report)
            self.assertIn("## Player 2 Action Mix By Round", report)
            self.assertIn("## Player 2 Score Mix", report)


def _write_manifest(root: Path) -> Path:
    seed_1 = root / "seed_1"
    seed_2 = root / "seed_2"
    seed_1.mkdir()
    seed_2.mkdir()
    _write_events(
        seed_1 / "events.jsonl",
        [
            _action_event("potential_points_p2", "play_bird"),
            _decision_event(
                "potential_points_p2",
                {
                    "selected_value_delta": 2.0,
                    "selected_realized_delta": 1.0,
                    "endgame_search_used": False,
                    "action_selection_elapsed_ms": 12.0,
                    "decision_summary_elapsed_ms": 4.0,
                    "decision_total_elapsed_ms": 16.0,
                },
            ),
            _game_ended_event(
                {
                    "bird_points": 15,
                    "bonus_points": 2,
                    "round_goal_points": 3,
                    "egg_points": 8,
                    "cached_food_points": 1,
                    "tucked_card_points": 1,
                }
            ),
        ],
    )
    _write_events(
        seed_2 / "events.jsonl",
        [
            _action_event("potential_points_p2", "gain_food"),
            _decision_event(
                "potential_points_p2",
                {
                    "policy": "guardrailed_policy",
                    "guardrail_candidate_action_count": 2,
                    "action_selection_elapsed_ms": 8.0,
                    "decision_summary_elapsed_ms": 2.0,
                    "decision_total_elapsed_ms": 10.0,
                    "base_decision_summary": {
                        "selected_value_delta": 0.0,
                        "selected_realized_delta": -0.5,
                        "endgame_search_used": True,
                    },
                },
            ),
            _game_ended_event(
                {
                    "bird_points": 17,
                    "bonus_points": 3,
                    "round_goal_points": 4,
                    "egg_points": 7,
                    "cached_food_points": 2,
                    "tucked_card_points": 1,
                }
            ),
        ],
    )
    manifest = {
        "batch_id": "comparison_batch",
        "batch_kind": "smoke",
        "batch_label": "comparison",
        "event_count": 4,
        "games": [
            {
                "artifact_dir": str(seed_1),
                "outcome": {
                    "scores": {"player_1": 20, "player_2": 30},
                    "winners": ["player_2"],
                },
            },
            {
                "artifact_dir": str(seed_2),
                "outcome": {
                    "scores": {"player_1": 30, "player_2": 34},
                    "winners": ["player_1", "player_2"],
                },
            },
        ],
        "guardrail_config_names": [],
        "player_two_agent_ids": ["potential_points_p2"],
        "player_two_agent_kinds": ["potential_points"],
        "replay_validation": {"all_valid": True},
    }
    manifest_path = root / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


def _action_event(agent_id: str, action_type: str) -> dict:
    return {
        "event_name": "action_selected",
        "agent_id": agent_id,
        "round_number": 1 if action_type == "play_bird" else 2,
        "payload": {"action": {"action_type": action_type}},
    }


def _decision_event(agent_id: str, payload: dict) -> dict:
    return {
        "event_name": "agent_decision_summary",
        "agent_id": agent_id,
        "payload": payload,
    }


def _game_ended_event(player_two_breakdown: dict) -> dict:
    return {
        "event_name": "game_ended",
        "agent_id": "potential_points_p2",
        "payload": {
            "score_breakdowns": {
                "player_1": {},
                "player_2": player_two_breakdown,
            }
        },
    }
