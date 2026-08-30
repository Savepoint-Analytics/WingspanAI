import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

CALIBRATION_PATH = Path(__file__).parents[1] / "analysis" / "net_value_calibration.py"
CALIBRATION_SPEC = importlib.util.spec_from_file_location(
    "net_value_calibration",
    CALIBRATION_PATH,
)
if CALIBRATION_SPEC is None or CALIBRATION_SPEC.loader is None:
    raise RuntimeError(f"Could not load calibration module from {CALIBRATION_PATH}")
net_value_calibration = importlib.util.module_from_spec(CALIBRATION_SPEC)
CALIBRATION_SPEC.loader.exec_module(net_value_calibration)


class NetValueCalibrationTests(TestCase):
    def test_collects_prediction_rows_from_manifest_events(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manifest_path = _write_manifest_fixture(Path(tmp_dir))

            rows = net_value_calibration.collect_calibration_rows([manifest_path])

            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["prediction_matched"])
            self.assertEqual(rows[0]["observed_candidate_rank"], 1)
            self.assertFalse(rows[1]["prediction_matched"])
            self.assertEqual(rows[1]["observed_candidate_rank"], 2)

    def test_renders_calibration_report(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manifest_path = _write_manifest_fixture(Path(tmp_dir))

            report = net_value_calibration.build_calibration_report([manifest_path])
            markdown = net_value_calibration.render_markdown_report(report)

            self.assertEqual(report["summary"]["prediction_count"], 2)
            self.assertEqual(report["summary"]["exact_match_rate"], 0.5)
            self.assertIn("Net-Value Public Belief Calibration", markdown)
            self.assertIn("| Exact match rate | 0.500 |", markdown)


def _write_manifest_fixture(root: Path) -> Path:
    seed_1 = root / "seed_1"
    seed_1.mkdir(parents=True)
    _write_jsonl(
        seed_1 / "events.jsonl",
        [
            _decision_event(
                turn=2,
                predicted="gain_food",
                candidates=[
                    {"action_type": "gain_food", "value_delta": 1.2},
                    {"action_type": "lay_eggs", "value_delta": 0.8},
                ],
            ),
            _selected_event(turn=3, player_id="player_1", action_type="gain_food"),
            _decision_event(
                turn=4,
                predicted="draw_cards",
                candidates=[
                    {"action_type": "draw_cards", "value_delta": 1.5},
                    {"action_type": "lay_eggs", "value_delta": 1.1},
                ],
            ),
            _selected_event(turn=5, player_id="player_1", action_type="lay_eggs"),
        ],
    )
    manifest = {
        "batch_id": "calibration_fixture",
        "batch_kind": "smoke",
        "batch_label": "public_belief_calibration",
        "games": [
            {
                "artifact_dir": str(seed_1),
                "outcome": {
                    "game_id": "game_1",
                    "random_seed": 1,
                    "scores": {"player_1": 40, "player_2": 44},
                    "winners": ["player_2"],
                },
            }
        ],
    }
    manifest_path = root / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _decision_event(
    *,
    turn: int,
    predicted: str,
    candidates: list[dict],
) -> dict:
    return {
        "event_name": "agent_decision_summary",
        "player_id": "player_2",
        "agent_id": "net_value_response_p2",
        "global_turn_number": turn,
        "payload": {
            "policy": "net_value_opponent_response",
            "selected_breakdown": {
                "net_margin_delta": 2.0,
                "shared_denial_value": 0.3,
            },
            "selected_opponent_response": {
                "opponent_id": "player_1",
                "response_action_type": predicted,
                "response_value_delta": candidates[0]["value_delta"],
                "response_candidate_values": candidates,
            },
        },
    }


def _selected_event(*, turn: int, player_id: str, action_type: str) -> dict:
    return {
        "event_name": "action_selected",
        "player_id": player_id,
        "agent_id": "random_legal_p1",
        "global_turn_number": turn,
        "payload": {
            "action": {
                "action_type": action_type,
                "player_id": player_id,
            },
        },
    }
