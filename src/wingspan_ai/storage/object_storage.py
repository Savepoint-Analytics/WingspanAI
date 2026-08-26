"""S3-compatible artifact upload helpers for local MinIO."""

from __future__ import annotations

from pathlib import Path

from wingspan_ai.config import ObjectStorageConfig


def upload_directory_to_object_storage(
    directory: str | Path,
    config: ObjectStorageConfig,
    *,
    key_prefix: str | None = None,
) -> list[str]:
    """Upload a local directory to S3-compatible object storage and return URIs."""

    boto3 = _import_boto3()
    resolved_dir = Path(directory)
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise ValueError(f"artifact directory does not exist: {resolved_dir}")

    client = _make_client(boto3, config)
    _ensure_bucket(client, config.bucket_name)

    prefix = (key_prefix or config.prefix).strip("/")
    uploaded_uris: list[str] = []
    for path in sorted(item for item in resolved_dir.rglob("*") if item.is_file()):
        relative_key = path.relative_to(resolved_dir).as_posix()
        object_key = f"{prefix}/{relative_key}" if prefix else relative_key
        client.upload_file(str(path), config.bucket_name, object_key)
        uploaded_uris.append(f"s3://{config.bucket_name}/{object_key}")
    return uploaded_uris


def upload_file_to_object_storage(
    path: str | Path,
    config: ObjectStorageConfig,
    *,
    object_key: str,
) -> str:
    """Upload one file to S3-compatible object storage and return its URI."""

    boto3 = _import_boto3()
    resolved_path = Path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        raise ValueError(f"artifact file does not exist: {resolved_path}")

    client = _make_client(boto3, config)
    _ensure_bucket(client, config.bucket_name)
    resolved_key = object_key.strip("/")
    if not resolved_key:
        raise ValueError("object_key must not be empty")
    client.upload_file(str(resolved_path), config.bucket_name, resolved_key)
    return f"s3://{config.bucket_name}/{resolved_key}"


def _make_client(boto3, config: ObjectStorageConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
    )


def _ensure_bucket(client, bucket_name: str) -> None:
    try:
        client.head_bucket(Bucket=bucket_name)
    except Exception as error:
        response = getattr(error, "response", {})
        error_code = response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchBucket", "NotFound"}:
            client.create_bucket(Bucket=bucket_name)
            return
        raise


def _import_boto3():
    try:
        import boto3
    except ImportError as error:
        raise RuntimeError(
            "boto3 is required for MinIO/S3 artifact upload. "
            "Install the storage optional dependencies before using this path."
        ) from error
    return boto3
