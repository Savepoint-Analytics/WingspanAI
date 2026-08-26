"""Artifact storage helpers."""

from wingspan_ai.storage.object_storage import (
    upload_directory_to_object_storage,
    upload_file_to_object_storage,
)

__all__ = ["upload_directory_to_object_storage", "upload_file_to_object_storage"]
