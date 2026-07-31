"""
File storage factory and public API.

Usage::

    from libs.file_storage import server_file_storage, storage_driver

    result = await server_file_storage.upload(content, UploadOptions(filename="photo.jpg"))
    print(result.source_url)
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from .interface import (
    FileMetadata,
    FileNotFoundError,
    FileStorage,
    UploadOptions,
    UploadResult,
    UploadUrl,
    UploadUrlOptions,
)
from .storage_utils import (
    decode_base64_key,
    encode_key_to_base64,
    get_content_type_from_filename,
    resolve_storage_prefix,
    sanitize_filename,
    storage_key_from_url,
)
from .storage_key import (
    STORAGE_KEY_BASE64_PREFIX,
    decode_storage_key_from_base64_segment,
    decode_storage_key_segments,
    encode_storage_key_for_path,
    encode_storage_key_to_base64_segment,
    is_valid_storage_key,
)

logger = logging.getLogger(__name__)

FileStorageDriver = Literal["s3", "local"]


def _resolve_driver() -> FileStorageDriver:
    candidate = os.environ.get("FILE_STORAGE_TYPE", "").strip().lower()
    if candidate == "s3":
        return "s3"
    # Default to local storage when not configured
    return "local"


def _create_file_storage() -> FileStorage:
    driver = _resolve_driver()
    logger.info("Creating file storage backend: %s", driver)
    if driver == "s3":
        from .s3_file_storage import S3FileStorage
        return S3FileStorage()
    # Default: local filesystem (useful for local development)
    from .local_file_storage import LocalFileStorage
    return LocalFileStorage()


# Module-level singleton — created once on first import.
storage_driver: FileStorageDriver = _resolve_driver()
server_file_storage: FileStorage = _create_file_storage()

__all__ = [
    # Factory / singleton
    "server_file_storage",
    "storage_driver",
    # Interface types
    "FileStorage",
    "FileMetadata",
    "FileNotFoundError",
    "UploadOptions",
    "UploadResult",
    "UploadUrl",
    "UploadUrlOptions",
    # Utilities
    "sanitize_filename",
    "get_content_type_from_filename",
    "resolve_storage_prefix",
    "storage_key_from_url",
    "encode_key_to_base64",
    "decode_base64_key",
    # Storage key helpers
    "is_valid_storage_key",
    "decode_storage_key_segments",
    "encode_storage_key_for_path",
    "encode_storage_key_to_base64_segment",
    "decode_storage_key_from_base64_segment",
    "STORAGE_KEY_BASE64_PREFIX",
]
