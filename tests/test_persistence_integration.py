import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from urllib.parse import urlparse
from uuid import uuid4

from wingspan_ai.config import database_url_from_env, load_dotenv, object_storage_config_from_env

REPO_ROOT = Path(__file__).parents[1]
load_dotenv(REPO_ROOT / ".env")

FLOW_PATH = REPO_ROOT / "flows" / "simulation_batch.py"
FLOW_SPEC = importlib.util.spec_from_file_location("persistence_simulation_batch", FLOW_PATH)
if FLOW_SPEC is None or FLOW_SPEC.loader is None:
    raise RuntimeError(f"Could not load flow module from {FLOW_PATH}")
simulation_batch = importlib.util.module_from_spec(FLOW_SPEC)
FLOW_SPEC.loader.exec_module(simulation_batch)


@skipUnless(
    os.getenv("RUN_DB_INTEGRATION") == "1",
    "set RUN_DB_INTEGRATION=1 to run the live PostgreSQL and MinIO regression test",
)
class PersistenceIntegrationTests(TestCase):
    def test_seeded_batch_persists_database_rows_artifacts_and_manifest(self) -> None:
        database_url = database_url_from_env()
        storage_config = object_storage_config_from_env()
        self.assertIsNotNone(database_url, "PostgreSQL credentials are not configured")
        self.assertIsNotNone(storage_config, "MinIO credentials are not configured")
        assert database_url is not None
        assert storage_config is not None

        batch_id = f"integration_{uuid4().hex[:12]}"
        with TemporaryDirectory() as tmp_dir:
            results = simulation_batch.run_simulation_batch(
                workbook_path="missing-workbook.xlsx",
                seeds=[901],
                artifact_root=tmp_dir,
                persist_postgres=True,
                upload_artifacts=True,
                batch_kind="smoke",
                batch_label="persistence_integration",
                batch_id=batch_id,
            )

            result = results[0]
            run_id = result["outcome"]["simulation_run_id"]
            game_id = result["outcome"]["game_id"]
            self.assertGreater(result["postgres"]["inserted"]["events"], 0)
            self.assertEqual(result["object_storage"]["uploaded"]["count"], 4)
            self.assertEqual(
                result["batch_manifest"]["object_storage"]["uploaded"]["count"],
                1,
            )

            self._assert_database_records(database_url, run_id, game_id, batch_id)
            artifact_uris = result["object_storage"]["uploaded"]["uris"]
            manifest_uris = result["batch_manifest"]["object_storage"]["uploaded"]["uris"]
            self._assert_objects_exist(storage_config, artifact_uris + manifest_uris)

    def _assert_database_records(
        self,
        database_url: str,
        run_id: str,
        game_id: str,
        batch_id: str,
    ) -> None:
        import psycopg

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select run_label, metadata ->> 'batch_id'
                    from simulation_runs
                    where simulation_run_id = %s
                    """,
                    (run_id,),
                )
                self.assertEqual(
                    cursor.fetchone(),
                    ("smoke:persistence_integration", batch_id),
                )
                cursor.execute("select count(*) from games where game_id = %s", (game_id,))
                self.assertEqual(cursor.fetchone()[0], 1)
                cursor.execute(
                    "select count(*) from simulation_events where simulation_run_id = %s",
                    (run_id,),
                )
                self.assertGreater(cursor.fetchone()[0], 0)
                cursor.execute("select count(*) from game_scores where game_id = %s", (game_id,))
                self.assertEqual(cursor.fetchone()[0], 2)

    def _assert_objects_exist(self, storage_config, uris: list[str]) -> None:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=storage_config.endpoint_url,
            aws_access_key_id=storage_config.access_key_id,
            aws_secret_access_key=storage_config.secret_access_key,
            region_name=storage_config.region_name,
        )
        for uri in uris:
            parsed = urlparse(uri)
            self.assertEqual(parsed.scheme, "s3")
            client.head_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
