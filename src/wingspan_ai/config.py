"""Local environment configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

DEFAULT_ENV_PATH = Path(".env")


@dataclass(frozen=True)
class ObjectStorageConfig:
    """Connection details for S3-compatible simulation artifact storage."""

    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    prefix: str = "wingspan-ai/simulations"
    region_name: str = "us-east-1"


def load_dotenv(path: str | Path = DEFAULT_ENV_PATH) -> None:
    """Load simple KEY=VALUE pairs from a local .env file without printing secrets."""

    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_quotes(value.strip())


def database_url_from_env() -> str | None:
    """Return a PostgreSQL connection URL from project or generic env variables."""

    explicit_url = os.getenv("SAVEPOINT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    host = os.getenv("SAVEPOINT_PG_HOST") or os.getenv("PGHOST")
    user = os.getenv("SAVEPOINT_PG_USER") or os.getenv("PGUSER")
    password = os.getenv("SAVEPOINT_PG_PWD") or os.getenv("PGPASSWORD")
    if not host or not user or password is None:
        return None

    port = os.getenv("SAVEPOINT_PG_PORT") or os.getenv("PGPORT") or "5432"
    database = (
        os.getenv("SAVEPOINT_PG_DB")
        or os.getenv("PGDATABASE")
        or os.getenv("POSTGRES_DB")
        or user
    )
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}@"
        f"{host}:{port}/{quote_plus(database)}"
    )


def object_storage_config_from_env() -> ObjectStorageConfig | None:
    """Return MinIO/S3 artifact storage config when credentials are present."""

    access_key = (
        os.getenv("SAVEPOINT_LOCAL_MINIO_USR")
        or os.getenv("MINIO_ROOT_USER")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    secret_key = (
        os.getenv("SAVEPOINT_LOCAL_MINIO_PWD")
        or os.getenv("MINIO_ROOT_PASSWORD")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    if not access_key or not secret_key:
        return None

    return ObjectStorageConfig(
        endpoint_url=(
            os.getenv("SAVEPOINT_LOCAL_MINIO_ENDPOINT")
            or os.getenv("MINIO_ENDPOINT")
            or "http://127.0.0.1:9000"
        ),
        access_key_id=access_key,
        secret_access_key=secret_key,
        bucket_name=(
            os.getenv("SAVEPOINT_LOCAL_MINIO_BUCKET")
            or os.getenv("MINIO_BUCKET")
            or "wingspan-ai"
        ),
        prefix=(
            os.getenv("SAVEPOINT_LOCAL_MINIO_PREFIX")
            or os.getenv("MINIO_PREFIX")
            or "wingspan-ai/simulations"
        ),
        region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
    )


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
