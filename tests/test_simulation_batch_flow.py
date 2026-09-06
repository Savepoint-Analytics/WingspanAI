import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig
from wingspan_ai.simulation import ReplayValidationResult

FLOW_PATH = Path(__file__).parents[1] / "flows" / "simulation_batch.py"
FLOW_SPEC = importlib.util.spec_from_file_location("simulation_batch", FLOW_PATH)
if FLOW_SPEC is None or FLOW_SPEC.loader is None:
    raise RuntimeError(f"Could not load flow module from {FLOW_PATH}")
simulation_batch = importlib.util.module_from_spec(FLOW_SPEC)
FLOW_SPEC.loader.exec_module(simulation_batch)


class SimulationBatchFlowTests(TestCase):
    def test_simulation_batch_writes_namespaced_artifacts_and_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="experiment",
                batch_label="policy_trial",
                batch_id="batch_test",
            )

            artifact_dir = Path(results[0]["artifact_dir"])
            manifest_path = Path(results[0]["batch_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(
                artifact_dir,
                Path(tmp_dir) / "experiment" / "policy_trial" / "batch_test" / "seed_1",
            )
            self.assertEqual(results[0]["outcome"]["terminal_reason"], "game_over")
            self.assertEqual(results[0]["outcome"]["game_id"], "batch_test_seed_1")
            self.assertTrue((artifact_dir / "events.jsonl").exists())
            self.assertEqual(manifest["schema_version"], "wingspan.simulation_batch_manifest.v1")
            self.assertEqual(manifest["batch_kind"], "experiment")
            self.assertEqual(manifest["seeds"], [1])
            self.assertTrue(results[0]["replay_validation"]["is_valid"])
            self.assertTrue(manifest["replay_validation"]["all_valid"])
            self.assertEqual(manifest["replay_validation"]["valid_game_count"], 1)
            self.assertEqual(manifest["games"][0]["outcome"], results[0]["outcome"])
            self.assertEqual(
                manifest["games"][0]["replay_validation"],
                results[0]["replay_validation"],
            )
            self.assertIn("powers", results[0]["rule_audits"])
            self.assertIn("scoring", results[0]["rule_audits"])
            self.assertEqual(manifest["rule_audits"], results[0]["rule_audits"])
            self.assertEqual(results[0]["postgres"], {"enabled": False, "inserted": None})
            self.assertEqual(
                results[0]["object_storage"],
                {"enabled": False, "uploaded": None},
            )
            self.assertEqual(
                results[0]["batch_manifest"]["object_storage"],
                {"enabled": False, "uploaded": None},
            )

    def test_simulation_batch_can_wrap_greedy_with_guardrails(self) -> None:
        guardrail_path = (
            Path(__file__).parents[1] / "configs" / "guardrails" / "base_heuristic.yaml"
        )
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="smoke",
                batch_label="guardrail_trial",
                batch_id="guardrail_batch",
                guardrail_config_path=str(guardrail_path),
            )

            manifest_path = Path(results[0]["batch_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(results[0]["guardrail_config_name"], "base_heuristic_guardrails")
            self.assertEqual(manifest["guardrail_config_names"], ["base_heuristic_guardrails"])
            self.assertEqual(
                manifest["games"][0]["guardrail_config_name"],
                "base_heuristic_guardrails",
            )

    def test_simulation_batch_can_use_potential_points_agent(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="smoke",
                batch_label="potential_points_trial",
                batch_id="potential_points_batch",
                player_two_agent_kind="potential_points",
                # Plumbing test: the default search (depth 3, every turn, 4
                # samples) takes minutes per game on the sample catalog.
                potential_points_search=PotentialPointsSearchConfig(
                    search_depth=1, final_search_turns=0, determinization_samples=0
                ),
            )

            manifest_path = Path(results[0]["batch_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(results[0]["player_two_agent_kind"], "potential_points")
            self.assertEqual(
                manifest["potential_points_search"],
                {
                    "search_depth": 1,
                    "final_search_turns": 0,
                    "search_beam_width": 4,
                    "determinization_samples": 0,
                },
            )
            self.assertEqual(results[0]["player_two_agent_id"], "potential_points_p2")
            self.assertEqual(manifest["player_two_agent_kinds"], ["potential_points"])
            self.assertEqual(
                manifest["games"][0]["player_two_agent_id"],
                "potential_points_p2",
            )

    def test_player_two_agent_factory_supports_matrix_variants(self) -> None:
        expected_agent_ids = {
            "random_legal": "random_legal_p2",
            "greedy_immediate": "greedy_immediate_p2",
            "potential_points": "potential_points_p2",
            "net_value_response": "net_value_response_p2",
            "archetype_egg_focus": "egg_focus_p2",
            "archetype_engine_builder": "engine_builder_p2",
            "archetype_food_acceleration": "food_acceleration_p2",
            "archetype_card_draw": "card_draw_p2",
            "archetype_bonus_card_focus": "bonus_card_focus_p2",
            "archetype_round_goal_chase": "round_goal_chase_p2",
            "monte_carlo_rollout": "monte_carlo_rollout_p2",
        }

        for agent_kind, expected_agent_id in expected_agent_ids.items():
            with self.subTest(agent_kind=agent_kind):
                agent = simulation_batch._make_player_two_agent(
                    agent_kind,
                    random_seed=11,
                )

                self.assertEqual(agent.agent_id, expected_agent_id)

    def test_simulation_batch_records_monte_carlo_budget_controls(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="smoke",
                batch_label="monte_budget_trial",
                batch_id="monte_budget_batch",
                player_two_agent_kind="monte_carlo_rollout",
                monte_carlo_rollout_count=2,
                monte_carlo_rollout_depth=2,
                monte_carlo_max_decision_time_ms=5.0,
                monte_carlo_max_candidate_actions=4,
            )

            manifest_path = Path(results[0]["batch_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(results[0]["monte_carlo_rollout_count"], 2)
            self.assertEqual(results[0]["monte_carlo_rollout_depth"], 2)
            self.assertEqual(results[0]["monte_carlo_max_decision_time_ms"], 5.0)
            self.assertEqual(results[0]["monte_carlo_max_candidate_actions"], 4)
            self.assertEqual(manifest["monte_carlo_rollout_count"], 2)
            self.assertEqual(manifest["monte_carlo_max_candidate_actions"], 4)
            self.assertEqual(manifest["games"][0]["monte_carlo_rollout_depth"], 2)

    def test_simulation_batch_records_net_value_budget_controls(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="smoke",
                batch_label="net_value_budget_trial",
                batch_id="net_value_budget_batch",
                player_two_agent_kind="net_value_response",
                net_value_max_candidate_actions=4,
                net_value_max_opponent_response_actions=3,
            )

            manifest_path = Path(results[0]["batch_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(results[0]["net_value_max_candidate_actions"], 4)
            self.assertEqual(results[0]["net_value_max_opponent_response_actions"], 3)
            self.assertEqual(manifest["net_value_max_candidate_actions"], 4)
            self.assertEqual(
                manifest["games"][0]["net_value_max_opponent_response_actions"],
                3,
            )

    def test_replay_gate_rejects_invalid_replay_before_writing_artifacts(self) -> None:
        invalid_replay = ReplayValidationResult(
            is_valid=False,
            checked_transitions=0,
            errors=["forced mismatch"],
        )
        with TemporaryDirectory() as tmp_dir:
            with patch.object(
                simulation_batch,
                "validate_simulation_replay",
                return_value=invalid_replay,
            ):
                with self.assertRaisesRegex(RuntimeError, "Replay validation failed"):
                    simulation_batch.run_simulation_batch(
                        workbook_path="missing-workbook.xlsx",
                        seeds=[1],
                        artifact_root=tmp_dir,
                        persist_postgres=False,
                        upload_artifacts=False,
                        batch_kind="experiment",
                        batch_label="policy_trial",
                        batch_id="invalid_replay_batch",
                    )

            self.assertFalse(
                (Path(tmp_dir) / "experiment" / "policy_trial" / "invalid_replay_batch").exists()
            )

    def test_object_prefix_separates_workload_kinds(self) -> None:
        prefixes = {
            kind: simulation_batch._batch_object_prefix(
                "board-games/wingspan", kind, "core_random_vs_greedy", "batch_123"
            )
            for kind in ("smoke", "experiment", "production")
        }

        self.assertEqual(
            prefixes,
            {
                "smoke": "board-games/wingspan/smoke/core_random_vs_greedy/batch_123",
                "experiment": ("board-games/wingspan/experiment/core_random_vs_greedy/batch_123"),
                "production": ("board-games/wingspan/production/core_random_vs_greedy/batch_123"),
            },
        )

    def test_batch_kind_rejects_unrecognised_namespace(self) -> None:
        with self.assertRaisesRegex(ValueError, "batch_kind must be one of"):
            simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=None,
                persist_postgres=False,
                upload_artifacts=False,
                batch_kind="adhoc",
            )
