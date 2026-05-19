import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

FLOW_PATH = Path(__file__).parents[1] / "flows" / "simulation_batch.py"
FLOW_SPEC = importlib.util.spec_from_file_location("simulation_batch", FLOW_PATH)
if FLOW_SPEC is None or FLOW_SPEC.loader is None:
    raise RuntimeError(f"Could not load flow module from {FLOW_PATH}")
simulation_batch = importlib.util.module_from_spec(FLOW_SPEC)
FLOW_SPEC.loader.exec_module(simulation_batch)


class SimulationBatchFlowTests(TestCase):
    def test_simulation_batch_writes_labelled_artifacts(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[1],
                artifact_root=tmp_dir,
            )

            artifact_dir = results[0]["artifact_dir"]

            self.assertIsNotNone(artifact_dir)
            self.assertEqual(results[0]["outcome"]["terminal_reason"], "game_over")
            self.assertTrue((Path(artifact_dir) / "events.jsonl").exists())
