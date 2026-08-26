import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from wingspan_ai.config import (
    database_url_from_env,
    load_dotenv,
    object_storage_config_from_env,
)


class ConfigTests(TestCase):
    def test_load_dotenv_sets_missing_values_without_overwriting_existing_env(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "SAVEPOINT_PG_HOST=localhost\n"
                "SAVEPOINT_PG_USER=file_user\n"
                "SAVEPOINT_PG_PWD='secret value'\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"SAVEPOINT_PG_USER": "existing_user"},
                clear=True,
            ):
                load_dotenv(env_path)

                self.assertEqual(os.environ["SAVEPOINT_PG_HOST"], "localhost")
                self.assertEqual(os.environ["SAVEPOINT_PG_USER"], "existing_user")
                self.assertEqual(os.environ["SAVEPOINT_PG_PWD"], "secret value")

    def test_database_url_from_savepoint_env_defaults_database_to_user(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SAVEPOINT_PG_HOST": "localhost",
                "SAVEPOINT_PG_PORT": "5433",
                "SAVEPOINT_PG_USER": "wingspan_user",
                "SAVEPOINT_PG_PWD": "secret/password",
            },
            clear=True,
        ):
            url = database_url_from_env()

        self.assertEqual(
            url,
            "postgresql://wingspan_user:secret%2Fpassword@localhost:5433/wingspan_user",
        )

    def test_object_storage_config_uses_local_minio_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SAVEPOINT_LOCAL_MINIO_USR": "minio_user",
                "SAVEPOINT_LOCAL_MINIO_PWD": "minio_password",
            },
            clear=True,
        ):
            config = object_storage_config_from_env()

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.endpoint_url, "http://127.0.0.1:9000")
        self.assertEqual(config.bucket_name, "wingspan-ai")
        self.assertEqual(config.prefix, "wingspan-ai/simulations")
